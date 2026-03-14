# Agent Architecture

## Overview

This agent is a CLI program that answers questions by calling an LLM API with **tools** and an **agentic loop**. It can read files from the project wiki, list directories, and provide answers with source references.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Command-line    │ ──> │ Environment  │ ──> │ LLM + Tools  │ ──> │ Agentic      │
│ argument        │     │ config       │     │ (function    │     │ Loop         │
│ (question)      │     │ (.env.agent) │     │ calling)     │     │              │
└─────────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                        │
                                                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Agentic Loop                                   │
│                                                                             │
│  1. Send question + tool schemas to LLM                                     │
│  2. If LLM returns tool_calls:                                              │
│     - Execute each tool                                                     │
│     - Append results as "tool" role messages                                │
│     - Go back to step 1                                                     │
│  3. If LLM returns text answer:                                             │
│     - Extract answer and source                                             │
│     - Output JSON and exit                                                  │
│  4. Stop after 10 iterations (safety limit)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                                                        │
                                                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JSON Response                                      │
│  {"answer": "...", "source": "wiki/file.md#section", "tool_calls": [...]}   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Configuration (`AgentSettings`)

- Reads from `.env.agent.secret` using `pydantic-settings`
- Configuration values:
  - `LLM_API_KEY` - API key for authentication
  - `LLM_API_BASE` - Base URL of the LLM API endpoint
  - `LLM_MODEL` - Model name to use (default: `qwen3-coder-plus`)

### 2. Tools

Two tools are available for the LLM to call:

#### `read_file`

Reads contents of a file from the project repository.

- **Parameters:** `path` (string) - Relative path from project root
- **Returns:** File contents as a string, or error message
- **Security:** Validates path is within project directory

#### `list_files`

Lists files and directories at a given path.

- **Parameters:** `path` (string) - Relative directory path
- **Returns:** Newline-separated list of entries, or error message
- **Security:** Validates path is within project directory

### 3. Tool Schemas

Tools are defined as OpenAI-compatible function schemas:

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
                        "description": "Relative path to the file"
                    }
                },
                "required": ["path"]
            }
        }
    },
    # ... list_files schema
]
```

### 4. Agentic Loop (`run_agentic_loop`)

The core loop that enables the agent to iteratively use tools:

1. **Initialize** message history with system prompt and user question
2. **Call LLM** with messages and tool schemas
3. **Check response:**
   - If `tool_calls` present:
     - Execute each tool via `execute_tool_call`
     - Append results as `role: "tool"` messages
     - Increment counter and loop back to step 2
   - If text answer (no tool calls):
     - Extract answer and source
     - Return result and exit
4. **Safety limit:** Stop after 10 tool calls maximum

### 5. Path Security (`validate_path`)

Prevents access to files outside the project directory:

```python
def validate_path(path: str) -> Path:
    full_path = (PROJECT_ROOT / path).resolve()
    
    # Security check: must be within project
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        raise ValueError("Access denied: path outside project directory")
    
    return full_path
```

### 6. System Prompt

The system prompt instructs the LLM to:

- Use `list_files` to discover relevant wiki files
- Use `read_file` to find specific information
- Always include a source reference (e.g., `wiki/git-workflow.md#resolving-merge-conflicts`)
- Stop calling tools once the answer is found

### 7. Output Formatting

- Outputs a single JSON line to stdout
- Format: `{"answer": "...", "source": "...", "tool_calls": [...]}`
- `source` - Wiki file reference with optional section anchor
- `tool_calls` - Array of all tool invocations with args and results
- All debug/progress output goes to stderr

## LLM Provider

- **Provider:** Qwen Code API
- **Model:** `qwen3-coder-plus`
- **Endpoint:** OpenAI-compatible API running on remote VM

## Usage

```bash
# Basic usage
uv run agent.py "How do you resolve a merge conflict?"

# Example output
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

## Environment Setup

1. Copy the example environment file:
   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Edit `.env.agent.secret` and fill in:
   - `LLM_API_KEY` - Your Qwen API key
   - `LLM_API_BASE` - Your VM's API endpoint
   - `LLM_MODEL` - Model name (default: `qwen3-coder-plus`)

## Error Handling

- Missing arguments: Shows usage message to stderr, exits with code 1
- Configuration errors: Reports error to stderr, exits with code 1
- HTTP errors: Reports error to stderr, exits with code 1
- File not found: Returns error message, LLM can try another file
- Path security violation: Returns error, does not access file
- Max iterations exceeded: Returns best available answer

## Testing

Run the regression tests:

```bash
uv run pytest backend/tests/unit/test_agent.py -v
```

## Message Flow Example

```
User: "How do you resolve a merge conflict?"

→ LLM (with tools): decides to list wiki files
  Assistant: tool_calls: list_files(path="wiki")
→ Tool result: "git-workflow.md\n..."

→ LLM (with history): decides to read git-workflow.md
  Assistant: tool_calls: read_file(path="wiki/git-workflow.md")
→ Tool result: "# Git Workflow\n\n## Resolving Merge Conflicts\n..."

→ LLM (with history): has enough info, provides answer
  Assistant: "Edit the conflicting file... [source: wiki/git-workflow.md#resolving-merge-conflicts]"
```

## Future Extensions (Task 3)

- Additional tools for interacting with the backend API
- More sophisticated source extraction
- Better handling of section anchors in wiki files
