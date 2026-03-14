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
    """LLM and API configuration from environment files."""

    llm_api_key: str
    llm_api_base: str
    llm_model: str
    lms_api_key: str = ""  # Backend API key from .env.docker.secret
    agent_api_base_url: str = "http://localhost:42002"  # Base URL for query_api

    class Config:
        env_file = ".env.agent.secret"
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra env vars from other files


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
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API to fetch live data or check system behavior. Use this for questions about item counts, scores, analytics, or system status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/scores')"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

# System prompt for the agent - uses JSON-based tool calling for models that don't support function calling
SYSTEM_PROMPT = """You are a helpful system assistant. You answer questions by using available tools.

You have access to these tools:
1. list_files: List files in a directory. Use this FIRST to discover wiki or source files.
   - Parameter: path (string) - e.g., "wiki"
2. read_file: Read contents of a file. Use this to get detailed information from files.
   - Parameter: path (string) - e.g., "wiki/git-workflow.md"
3. query_api: Call the backend API. Use this for live data like item counts, scores, analytics.
   - Parameters: method (GET/POST/PUT/DELETE), path (string) - e.g., "GET", "/items/"

To use a tool, respond with ONLY a JSON object like this:
{"tool": "tool_name", "args": {"param1": "value1"}}

Examples:
- {"tool": "list_files", "args": {"path": "wiki"}}
- {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}}
- {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}}

When you have found the answer, respond with:
{"answer": "Your answer here", "source": "wiki/file.md#section"}

Process:
1. Use list_files to find relevant files
2. Use read_file to read file contents
3. Answer based on what you read, including the source

Rules:
- Always use tools before answering
- Include source references
- Be concise
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


def query_api(method: str, path: str, body: str | None = None, settings: AgentSettings | None = None) -> str:
    """Call the backend API with authentication.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API endpoint path (e.g., '/items/', '/analytics/scores')
        body: Optional JSON request body for POST/PUT requests
        settings: Agent settings for API configuration

    Returns:
        JSON string with status_code and body, or error message
    """
    if settings is None:
        try:
            settings = AgentSettings()
        except Exception as e:
            return f"Error loading settings: {e}"

    try:
        # Build URL
        base_url = settings.agent_api_base_url.rstrip('/')
        url = f"{base_url}{path}"

        # Build headers
        headers = {
            "Content-Type": "application/json",
        }

        # Add authentication if LMS_API_KEY is available
        if settings.lms_api_key:
            headers["X-API-Key"] = settings.lms_api_key

        # Build request
        print(f"Calling API: {method} {url}", file=sys.stderr)

        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, content=body or "{}")
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, content=body or "{}")
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return f"Error: Unsupported HTTP method: {method}"

        # Build response
        result = {
            "status_code": response.status_code,
            "body": response.text,
        }

        return json.dumps(result)

    except httpx.HTTPError as e:
        return f"Error: HTTP error: {e}"
    except Exception as e:
        return f"Error calling API: {e}"


# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files,
    "query_api": query_api,
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
        payload["tool_choice"] = "auto"  # Let LLM decide when to use tools

    print(f"Calling LLM at {url}...", file=sys.stderr)

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    data = response.json()
    message = data["choices"][0]["message"]
    
    print(f"Received response from LLM.", file=sys.stderr)

    return message


def execute_tool_call(tool_call: dict[str, Any], settings: AgentSettings | None = None) -> dict[str, Any]:
    """Execute a single tool call and return the result.

    Args:
        tool_call: Tool call dict from LLM response
        settings: Agent settings for tools that need configuration

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
        # Pass settings for tools that need it (like query_api)
        if tool_name == "query_api" and settings:
            result = tool_func(**args, settings=settings)
        else:
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
    - backend/app/file.py
    - GET /api/endpoint
    - (wiki/file.md#section)
    - [source: wiki/file.md#section]

    Args:
        answer: The LLM's text answer

    Returns:
        Source reference string, or empty string if not found
    """
    import re

    # Pattern to match wiki file references with optional section anchor
    wiki_pattern = r"wiki/[\w\-/]+\.md(?:#[\w\-]+)?"

    # Pattern to match backend source files
    backend_pattern = r"backend/[\w\-/]+\.py"

    # Pattern to match API endpoints (e.g., "GET /items/" or "POST /analytics/scores")
    api_pattern = r"(?:GET|POST|PUT|DELETE|PATCH)\s+/[\w\-/]+"

    # Try wiki pattern first
    matches = re.findall(wiki_pattern, answer, re.IGNORECASE)
    if matches:
        return matches[0]

    # Try backend pattern
    matches = re.findall(backend_pattern, answer, re.IGNORECASE)
    if matches:
        return matches[0]

    # Try API pattern
    matches = re.findall(api_pattern, answer, re.IGNORECASE)
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

        # Call LLM (without tools parameter - using JSON-based prompting)
        message = call_llm(messages, settings, tools=None)

        # Get response content
        content = message.get("content", "")
        print(f"LLM response: {content[:200]}...", file=sys.stderr)

        # Try to parse as JSON for tool calls
        try:
            import json
            parsed = json.loads(content.strip())
            
            # Check if it's a tool call
            if "tool" in parsed and "args" in parsed:
                tool_name = parsed["tool"]
                args = parsed["args"]
                
                # Execute the tool
                tool_func = TOOL_FUNCTIONS.get(tool_name)
                if tool_func:
                    print(f"Executing tool: {tool_name}({args})", file=sys.stderr)
                    if tool_name == "query_api":
                        result = tool_func(**args, settings=settings)
                    else:
                        result = tool_func(**args)
                    
                    tool_calls_log.append({
                        "tool": tool_name,
                        "args": args,
                        "result": result,
                    })
                    
                    # Add result to message history
                    messages.append({
                        "role": "assistant",
                        "content": content,
                    })
                    messages.append({
                        "role": "user",
                        "content": f"Tool result: {result}",
                    })
                    continue
                else:
                    messages.append({
                        "role": "user",
                        "content": f"Error: Unknown tool '{tool_name}'",
                    })
                    continue
                    
            # Check if it's a final answer
            elif "answer" in parsed:
                answer = parsed["answer"]
                source = parsed.get("source", "")
                print(f"\nFinal answer: {answer[:100]}...", file=sys.stderr)
                return answer, source, tool_calls_log
                
        except json.JSONDecodeError:
            # Not JSON - treat as final answer
            pass
        
        # Check for source patterns in text answer
        answer = content
        source = extract_source_from_answer(answer)
        print(f"\nFinal answer: {answer[:100]}...", file=sys.stderr)
        return answer, source, tool_calls_log

    # Reached max iterations
    print(f"\nReached maximum iterations ({max_iterations})", file=sys.stderr)
    
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
