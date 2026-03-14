# Task 2 Plan: The Documentation Agent

## Overview

This task extends the Task 1 CLI agent with two tools (`read_file`, `list_files`) and an agentic loop. The agent can now navigate the wiki, read files, and provide answers with source references.

## Tool Definitions

### 1. `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message if the file doesn't exist or access is denied.

**Security:** 
- Resolve path to absolute path
- Verify the resolved path is within the project directory
- Reject paths that would escape the project (e.g., `../.env`)

### 2. `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated list of file/directory names.

**Security:**
- Same path validation as `read_file`
- Only list directories within the project

## Tool Schemas for LLM

Tools will be defined as OpenAI-compatible function schemas:

```python
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
```

## Agentic Loop Implementation

The loop will:

1. **Initialize** message history with system prompt and user question
2. **Call LLM** with messages + tool schemas
3. **Check response:**
   - If `tool_calls` present:
     - Execute each tool function
     - Append tool results as `role: "tool"` messages
     - Increment tool call counter
     - Loop back to step 2
   - If text answer (no tool calls):
     - Extract answer and source from response
     - Output JSON and exit
4. **Safety limit:** Stop after 10 tool calls maximum

### Message Flow Example

```
User: "How do you resolve a merge conflict?"

→ LLM (with tools): decides to list wiki files
← Assistant: tool_calls: list_files(path="wiki")
→ Tool result: "git-workflow.md\n..."

→ LLM (with history): decides to read git-workflow.md
← Assistant: tool_calls: read_file(path="wiki/git-workflow.md")
→ Tool result: "# Git Workflow\n\n## Resolving Merge Conflicts\n..."

→ LLM (with history): has enough info, provides answer
← Assistant: "Edit the conflicting file... [source: wiki/git-workflow.md#resolving-merge-conflicts]"
```

## System Prompt Strategy

The system prompt will instruct the LLM to:

1. Use `list_files` to discover relevant wiki files
2. Use `read_file` to find specific information
3. Always include a source reference in the format `wiki/filename.md#section-anchor`
4. Be concise and accurate
5. Stop calling tools once the answer is found

Example system prompt:
```
You are a helpful documentation assistant. You answer questions by reading files from the project wiki.

Available tools:
- list_files: List files in a directory
- read_file: Read contents of a file

Instructions:
1. First use list_files to discover relevant wiki files
2. Then use read_file to find the specific information you need
3. Always include a source reference in your answer (e.g., "wiki/git-workflow.md#resolving-merge-conflicts")
4. Be concise and accurate
5. Stop calling tools once you have found the answer
```

## Path Security Implementation

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

def validate_path(path: str) -> Path:
    """Validate and resolve a relative path to within the project."""
    # Resolve to absolute path
    full_path = (PROJECT_ROOT / path).resolve()
    
    # Security check: must be within project
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        raise ValueError(f"Access denied: path outside project directory")
    
    return full_path
```

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

## Files to Modify/Create

1. `plans/task-2.md` - This plan
2. `agent.py` - Add tools and agentic loop
3. `AGENT.md` - Update documentation with tools and loop
4. `backend/tests/unit/test_agent.py` - Add 2 tool-calling tests

## Testing Strategy

Two regression tests:

1. **Test read_file usage:**
   - Question: "How do you resolve a merge conflict?"
   - Verify: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Test list_files usage:**
   - Question: "What files are in the wiki?"
   - Verify: `list_files` in tool_calls

## Error Handling

- File not found: Return error message, LLM can try another file
- Path security violation: Return error, do not access file
- LLM exceeds 10 tool calls: Stop and return best available answer
- HTTP errors: Report to stderr, exit with non-zero code
