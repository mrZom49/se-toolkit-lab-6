# Task 3 Plan: The System Agent

## Overview

This task extends the Task 2 documentation agent with a new `query_api` tool that can query the deployed backend API. The agent will now answer three types of questions:
1. **Wiki lookup** - Use `list_files` and `read_file` to find documentation
2. **System facts** - Use `read_file` to check source code (e.g., what framework, ports)
3. **Data queries** - Use `query_api` to fetch live data from the backend

## Tool Definition: `query_api`

### Purpose
Call the deployed backend API to fetch live data or check system behavior.

### Parameters
- `method` (string, required) — HTTP method (GET, POST, PUT, etc.)
- `path` (string, required) — API endpoint path (e.g., `/items/`, `/analytics/scores`)
- `body` (string, optional) — JSON request body for POST/PUT requests

### Returns
JSON string containing:
- `status_code` — HTTP response status code
- `body` — Response body as JSON string

### Authentication
- Read `LMS_API_KEY` from `.env.docker.secret`
- Include in request header: `X-API-Key: <LMS_API_KEY>`

### Base URL
- Read `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
- This points to the Caddy reverse proxy port

## Environment Variables

The agent must read all configuration from environment variables:

| Variable | Purpose | Source | Default |
|----------|---------|--------|---------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` | - |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` | - |
| `LLM_MODEL` | Model name | `.env.agent.secret` | `qwen3-coder-plus` |
| `LMS_API_KEY` | Backend API key for auth | `.env.docker.secret` | - |
| `AGENT_API_BASE_URL` | Base URL for query_api | Optional env var | `http://localhost:42002` |

## Tool Schema for LLM

```python
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
```

## System Prompt Update

The system prompt must guide the LLM to choose the right tool:

```
You are a helpful system assistant. You answer questions by using available tools.

Available tools:
- list_files: List files in a directory (use for discovering wiki or source files)
- read_file: Read contents of a file (use for wiki documentation or source code)
- query_api: Call the backend API (use for live data like item counts, scores, analytics)

Instructions:
1. For wiki/documentation questions: use list_files to discover, then read_file to find answers
2. For system fact questions (framework, ports, status codes): read source code files
3. For data questions (how many items, scores, rates): use query_api with appropriate endpoints
4. Always include a source reference when applicable (e.g., "wiki/file.md#section" or "backend/app/file.py")
5. For API queries, the source can be the endpoint path (e.g., "GET /items/")
6. Stop calling tools once you have found the answer
```

## Implementation Steps

### 1. Update AgentSettings
Add `lms_api_key` and `agent_api_base_url` to the settings class:
```python
class AgentSettings(BaseSettings):
    llm_api_key: str
    llm_api_base: str
    llm_model: str
    lms_api_key: str  # From .env.docker.secret
    agent_api_base_url: str = "http://localhost:42002"  # Optional, has default
```

### 2. Implement `query_api` Function
```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """Call the backend API with authentication."""
    # Build URL from AGENT_API_BASE_URL
    # Add X-API-Key header with LMS_API_KEY
    # Make request and return JSON response
```

### 3. Update Tool Registration
Add `query_api` to `TOOL_FUNCTIONS` map and `TOOLS` schema list.

### 4. Update System Prompt
Modify `SYSTEM_PROMPT` to include guidance on when to use each tool.

### 5. Update Agentic Loop
The loop structure stays the same — just one more tool available.

## Path Security for Source Code

The `read_file` tool should also allow reading backend source files:
- `backend/app/main.py` — FastAPI app entry point
- `backend/app/routers/*.py` — API route definitions
- `backend/app/models/*.py` — Data models

## Testing Strategy

Two new regression tests:

### Test 1: Framework Question
- Question: "What framework does the backend use?"
- Expected: `read_file` in tool_calls, reads `backend/app/main.py` or similar

### Test 2: Data Query Question
- Question: "How many items are in the database?"
- Expected: `query_api` in tool_calls, calls `GET /items/`

## Benchmark Evaluation

Run `uv run run_eval.py` to test against 10 local questions:
- Wiki lookup questions
- System fact questions
- Data query questions
- Bug diagnosis questions
- Reasoning questions

Iterate on:
- Tool descriptions (make clearer for LLM)
- System prompt (better guidance)
- Error handling (handle API errors gracefully)

## Error Handling

- API connection errors: Return error message, LLM can try alternative approach
- Authentication errors: Report to stderr, include in result
- Invalid endpoints: Return 404 response, LLM can try different path
- Timeout: Set reasonable timeout (30s) for API calls

## Files to Modify

1. `plans/task-3.md` — This plan
2. `agent.py` — Add `query_api` tool, update settings, update system prompt
3. `AGENT.md` — Document new architecture and lessons learned
4. `backend/tests/unit/test_agent.py` — Add 2 new regression tests

## Initial Benchmark Score

*To be filled after first run*

## Iteration Log

*To be filled as we debug failing questions*
