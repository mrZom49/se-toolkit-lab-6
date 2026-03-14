#!/usr/bin/env python3
"""CLI agent that answers questions using an LLM with tools.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": "...", "tool_calls": [...]}
"""

import json
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """LLM configuration from .env.agent.secret."""

    llm_api_key: str
    llm_api_base: str
    llm_model: str

    class Config:
        env_file = ".env.agent.secret"
        env_file_encoding = "utf-8"


# Project root for path security
PROJECT_ROOT = Path(__file__).parent.resolve()

# Tool schemas for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file from the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file (e.g., 'wiki/git.md')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path to list (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful documentation assistant. You answer questions by reading files from the project wiki.

Available tools:
- list_files: List files in a directory
- read_file: Read contents of a file

Instructions:
1. First use list_files to discover relevant wiki files
2. Then use read_file to find the specific information you need
3. Always include a source reference in your answer (e.g., "wiki/git-workflow.md#resolving-merge-conflicts")
4. Be concise and accurate
5. Stop calling tools once you have found the answer
"""


def validate_path(path: str) -> Path:
    """Validate and resolve a relative path to within the project.
    
    Args:
        path: Relative path from project root
        
    Returns:
        Resolved absolute Path
        
    Raises:
        ValueError: If path is outside project directory
    """
    # Resolve to absolute path
    full_path = (PROJECT_ROOT / path).resolve()
    
    # Security check: must be within project
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        raise ValueError(f"Access denied: path outside project directory")
    
    return full_path


def read_file(path: str) -> str:
    """Read contents of a file from the project repository.
    
    Args:
        path: Relative path to the file
        
    Returns:
        File contents as a string, or error message
    """
    try:
        full_path = validate_path(path)
        
        if not full_path.exists():
            return f"Error: File not found: {path}"
        
        if full_path.is_dir():
            return f"Error: Path is a directory, not a file: {path}"
        
        return full_path.read_text(encoding="utf-8")
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.
    
    Args:
        path: Relative directory path to list
        
    Returns:
        Newline-separated list of entries, or error message
    """
    try:
        full_path = validate_path(path)
        
        if not full_path.exists():
            return f"Error: Directory not found: {path}"
        
        if not full_path.is_dir():
            return f"Error: Path is not a directory: {path}"
        
        entries = []
        for entry in sorted(full_path.iterdir()):
            # Skip hidden files and __pycache__
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            entries.append(entry.name)
        
        return "\n".join(entries)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files,
}


def call_llm(
    messages: list[dict[str, Any]],
    settings: AgentSettings,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Call the LLM API and return the response.
    
    Args:
        messages: List of message dicts for the conversation
        settings: LLM configuration
        tools: Optional list of tool schemas for function calling
        
    Returns:
        Parsed LLM response
    """
    url = f"{settings.llm_api_base.rstrip('/')}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }

    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
    }
    
    if tools:
        payload["tools"] = tools

    print(f"Calling LLM at {url}...", file=sys.stderr)

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    data = response.json()
    message = data["choices"][0]["message"]
    
    print(f"Received response from LLM.", file=sys.stderr)

    return message


def execute_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    """Execute a single tool call and return the result.
    
    Args:
        tool_call: Tool call dict from LLM response
        
    Returns:
        Dict with tool name, args, and result
    """
    function = tool_call["function"]
    tool_name = function["name"]
    
    # Parse arguments
    try:
        args = json.loads(function["arguments"])
    except json.JSONDecodeError:
        return {
            "tool": tool_name,
            "args": {},
            "result": "Error: Invalid arguments JSON"
        }
    
    # Get the tool function
    tool_func = TOOL_FUNCTIONS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "args": args,
            "result": f"Error: Unknown tool '{tool_name}'"
        }
    
    # Execute the tool
    print(f"Executing tool: {tool_name}({args})", file=sys.stderr)
    
    try:
        result = tool_func(**args)
    except Exception as e:
        result = f"Error executing tool: {e}"
    
    return {
        "tool": tool_name,
        "args": args,
        "result": result
    }


def extract_source_from_answer(answer: str) -> str:
    """Extract source reference from the LLM's answer.
    
    Looks for patterns like:
    - wiki/file.md#section
    - (wiki/file.md#section)
    - [source: wiki/file.md#section]
    
    Args:
        answer: The LLM's text answer
        
    Returns:
        Source reference string, or empty string if not found
    """
    import re
    
    # Pattern to match wiki file references with optional section anchor
    pattern = r"wiki/[\w\-/]+\.md(?:#[\w\-]+)?"
    
    matches = re.findall(pattern, answer)
    if matches:
        return matches[0]
    
    return ""


def run_agentic_loop(
    question: str,
    settings: AgentSettings,
    max_iterations: int = 10,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Run the agentic loop to answer a question.
    
    Args:
        question: User's question
        settings: LLM configuration
        max_iterations: Maximum number of tool calls
        
    Returns:
        Tuple of (answer, source, tool_calls)
    """
    # Initialize message history
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    tool_calls_log: list[dict[str, Any]] = []
    
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---", file=sys.stderr)
        
        # Call LLM with tools
        message = call_llm(messages, settings, tools=TOOLS)
        
        # Check if LLM wants to call tools
        if "tool_calls" in message and message["tool_calls"]:
            # Add assistant message with tool calls to history
            messages.append({
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": message["tool_calls"],
            })
            
            # Execute each tool call
            for tool_call in message["tool_calls"]:
                tool_result = execute_tool_call(tool_call)
                tool_calls_log.append(tool_result)
                
                # Add tool result to message history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_result["result"],
                })
            
            # Continue loop - LLM will process tool results
            continue
        
        # No tool calls - LLM provided final answer
        answer = message.get("content", "")
        print(f"\nFinal answer: {answer[:100]}...", file=sys.stderr)
        
        # Extract source from answer
        source = extract_source_from_answer(answer)
        
        return answer, source, tool_calls_log
    
    # Reached max iterations
    print(f"\nReached maximum iterations ({max_iterations})", file=sys.stderr)
    
    # Return best available answer
    if tool_calls_log:
        last_result = tool_calls_log[-1]["result"]
        answer = f"Reached maximum tool calls. Last result: {last_result[:200]}"
        source = ""
    else:
        answer = "Unable to answer - exceeded maximum tool calls"
        source = ""
    
    return answer, source, tool_calls_log


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        return 1

    question = sys.argv[1]

    try:
        settings = AgentSettings()
    except Exception as e:
        print(f"Error loading settings: {e}", file=sys.stderr)
        return 1

    try:
        answer, source, tool_calls = run_agentic_loop(question, settings)
    except httpx.HTTPError as e:
        print(f"HTTP error calling LLM: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error running agentic loop: {e}", file=sys.stderr)
        return 1

    result: dict[str, Any] = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }

    print(json.dumps(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
