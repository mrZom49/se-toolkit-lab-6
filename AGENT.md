# Agent Architecture

## Overview

This agent is a CLI program that answers questions by calling an LLM API with **tools** and an **agentic loop**. It can read files from the project wiki, list directories, query the backend API, and provide answers with source references.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Command-line    │ ──> │ Environment  │ ──> │ LLM + Tools  │ ──> │ Agentic      │
│ argument        │     │ config       │     │ (function    │     │ Loop         │
│ (question)      │     │ (.env files) │     │ calling)     │     │              │
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
│  {"answer": "...", "source": "...", "tool_calls": [...]}                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Configuration (`AgentSettings`)

- Reads from `.env.agent.secret` and `.env.docker.secret` using `pydantic-settings`
- Configuration values:
  - `LLM_API_KEY` - API key for LLM provider authentication
  - `LLM_API_BASE` - Base URL of the LLM API endpoint
  - `LLM_MODEL` - Model name to use (default: `qwen3-coder-plus`)
  - `LMS_API_KEY` - Backend API key for `query_api` authentication (from `.env.docker.secret`)
  - `AGENT_API_BASE_URL` - Base URL for backend API (default: `http://localhost:42002`)

### 2. Tools

Three tools are available for the LLM to call:

#### `read_file`

Reads contents of a file from the project repository.

- **Parameters:** `path` (string) - Relative path from project root
- **Returns:** File contents as a string, or error message
- **Security:** Validates path is within project directory
- **Use cases:** Wiki documentation, source code inspection

#### `list_files`

Lists files and directories at a given path.

- **Parameters:** `path` (string) - Relative directory path
- **Returns:** Newline-separated list of entries, or error message
- **Security:** Validates path is within project directory
- **Use cases:** Discovering wiki files, finding source files

#### `query_api` (Task 3)

Calls the backend API to fetch live data or check system behavior.

- **Parameters:**
  - `method` (string) - HTTP method (GET, POST, PUT, DELETE)
  - `path` (string) - API endpoint path (e.g., `/items/`, `/analytics/scores`)
  - `body` (string, optional) - JSON request body for POST/PUT requests
- **Returns:** JSON string with `status_code` and `body`
- **Authentication:** Uses `X-API-Key` header with `LMS_API_KEY`
- **Use cases:** Item counts, score queries, analytics, system status

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
                        "description": "Relative directory path to list"
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
            "description": "Call the backend API to fetch live data or check system behavior",
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

The system prompt instructs the LLM to choose the right tool for each question type:

```
You are a helpful system assistant. You answer questions by using available tools.

Available tools:
- list_files: List files in a directory (use for discovering wiki or source files)
- read_file: Read contents of a file (use for wiki documentation or source code)
- query_api: Call the backend API (use for live data like item counts, scores, analytics)

Instructions:
1. For wiki/documentation questions: use list_files to discover, then read_file to find answers
2. For system fact questions (framework, ports, status codes): read source code files like backend/app/main.py
3. For data questions (how many items, scores, rates): use query_api with appropriate endpoints
4. Always include a source reference when applicable (e.g., "wiki/file.md#section" or "backend/app/file.py")
5. For API queries, the source can be the endpoint path (e.g., "GET /items/")
6. Be concise and accurate
7. Stop calling tools once you have found the answer
```

### 7. Output Formatting

- Outputs a single JSON line to stdout
- Format: `{"answer": "...", "source": "...", "tool_calls": [...]}`
- `answer` - The LLM's answer text
- `source` - Source reference (wiki file, backend file, or API endpoint)
- `tool_calls` - Array of all tool invocations with args and results
- All debug/progress output goes to stderr

### 8. Source Extraction (`extract_source_from_answer`)

Extracts source references from the LLM's answer using regex patterns:

- Wiki files: `wiki/file.md#section`
- Backend files: `backend/app/file.py`
- API endpoints: `GET /items/`

## LLM Provider

- **Provider:** Qwen Code API
- **Model:** `qwen3-coder-plus`
- **Endpoint:** OpenAI-compatible API running on remote VM

## Usage

```bash
# Basic usage
uv run agent.py "How do you resolve a merge conflict?"

# Query backend data
uv run agent.py "How many items are in the database?"

# Check system facts
uv run agent.py "What framework does the backend use?"
```

### Example Output

```json
{
  "answer": "There are 120 items in the database.",
  "source": "GET /items/",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

## Environment Setup

1. Copy the example environment files:
   ```bash
   cp .env.agent.example .env.agent.secret
   cp .env.docker.example .env.docker.secret
   ```

2. Edit `.env.agent.secret` and fill in:
   - `LLM_API_KEY` - Your Qwen API key
   - `LLM_API_BASE` - Your VM's API endpoint
   - `LLM_MODEL` - Model name (default: `qwen3-coder-plus`)

3. Edit `.env.docker.secret` and ensure:
   - `LMS_API_KEY` - Backend API key for authentication

## Error Handling

- Missing arguments: Shows usage message to stderr, exits with code 1
- Configuration errors: Reports error to stderr, exits with code 1
- HTTP errors (LLM or API): Reports error to stderr, exits with code 1
- File not found: Returns error message, LLM can try another file
- Path security violation: Returns error, does not access file
- Max iterations exceeded: Returns best available answer

## Testing

Run the regression tests:

```bash
uv run pytest backend/tests/unit/test_agent.py -v
```

Tests include:
- JSON output validation
- Wiki question handling (uses `read_file`)
- Directory listing (uses `list_files`)
- Framework question (uses `read_file` on backend source)
- Item count question (uses `query_api`)

## Message Flow Example

### Wiki Question
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

### API Question
```
User: "How many items are in the database?"

→ LLM (with tools): decides to query API
  Assistant: tool_calls: query_api(method="GET", path="/items/")
→ Tool result: {"status_code": 200, "body": "[...]"}

→ LLM (with history): counts items from response
  Assistant: "There are 120 items in the database. [source: GET /items/]"
```

## Lessons Learned (Task 3)

Building the System Agent taught several important lessons about agentic systems:

1. **Tool descriptions matter**: The LLM needs clear, specific descriptions of when to use each tool. Initially, the `query_api` description was too vague, and the LLM would try to use `read_file` for data questions. Adding explicit guidance like "use for live data like item counts, scores, analytics" helped significantly.

2. **Authentication separation**: Keeping `LMS_API_KEY` (backend auth) separate from `LLM_API_KEY` (LLM provider auth) is critical for security. The agent reads from two different `.env` files, which required updating `AgentSettings` to allow extra environment variables.

3. **Source extraction flexibility**: The original source extraction only matched wiki files. For Task 3, we extended it to also match backend source files (`backend/app/*.py`) and API endpoints (`GET /items/`), making the agent's answers more traceable.

4. **Error handling in tools**: The `query_api` tool must gracefully handle connection errors, authentication failures, and invalid endpoints. Returning structured error messages lets the LLM understand what went wrong and potentially try a different approach.

5. **Environment variable flexibility**: The autochecker runs the agent with different credentials and backend URLs. Hardcoding values would fail evaluation. Reading all configuration from environment variables ensures the agent works in any deployment.

6. **Iterative benchmarking**: Running `run_eval.py` and iterating on failures is essential. The benchmark tests real questions across all classes (wiki lookup, system facts, data queries, bug diagnosis, reasoning). Each failure reveals a gap in tool descriptions or system prompt guidance.

## Final Evaluation Score

*To be filled after running the benchmark*

```bash
uv run run_eval.py
```

## Future Extensions

- Multi-step reasoning: Chain multiple tool calls to answer complex questions
- Caching: Cache API responses to reduce redundant calls
- Better section extraction: Parse markdown headers for more precise source anchors
- Additional tools: Add tools for running tests, checking logs, or analyzing errors
