# Agent Architecture

## Overview

This agent is a CLI program that answers questions by calling an LLM API. It forms the foundation for the more advanced agent with tools and agentic loop that will be built in Tasks 2-3.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Command-line    │ ──> │ Environment  │ ──> │ LLM API      │ ──> │ JSON         │
│ argument        │     │ config       │     │ (Qwen Code)  │     │ response     │
│ (question)      │     │ (.env.agent) │     │              │     │ to stdout    │
└─────────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

## Components

### 1. Configuration (`AgentSettings`)

- Reads from `.env.agent.secret` using `pydantic-settings`
- Configuration values:
  - `LLM_API_KEY` - API key for authentication
  - `LLM_API_BASE` - Base URL of the LLM API endpoint
  - `LLM_MODEL` - Model name to use (default: `qwen3-coder-plus`)

### 2. LLM Client (`call_lllm`)

- Uses `httpx` for HTTP requests
- Calls the OpenAI-compatible `/chat/completions` endpoint
- Sends a system message and the user's question
- 60-second timeout for responses
- Returns the answer text from the LLM response

### 3. Output Formatting

- Outputs a single JSON line to stdout
- Format: `{"answer": "...", "tool_calls": []}`
- `tool_calls` is empty in Task 1 (will be populated in Task 2)
- All debug/progress output goes to stderr

## LLM Provider

- **Provider**: Qwen Code API
- **Model**: `qwen3-coder-plus`
- **Endpoint**: OpenAI-compatible API running on remote VM
- **Benefits**: 1000 free requests/day, works from Russia, no credit card required

## Usage

```bash
# Basic usage
uv run agent.py "What does REST stand for?"

# Example output
{"answer": "Representational State Transfer.", "tool_calls": []}
```

## Environment Setup

1. Copy the example environment file:
   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Edit `.env.agent.secret` and fill in:
   - `LLM_API_KEY` - Your Qwen API key
   - `LLM_API_BASE` - Your VM's API endpoint (e.g., `http://192.168.1.100:42005/v1`)
   - `LLM_MODEL` - Model name (default: `qwen3-coder-plus`)

## Error Handling

- Missing arguments: Shows usage message to stderr, exits with code 1
- Configuration errors: Reports error to stderr, exits with code 1
- HTTP errors: Reports error to stderr, exits with code 1
- General errors: Reports error to stderr, exits with code 1
- Success: Outputs JSON to stdout, exits with code 0

## Testing

Run the regression test:

```bash
uv run pytest backend/tests/unit/test_agent.py -v
```

## Future Extensions (Tasks 2-3)

- **Task 2**: Add tool support - populate `tool_calls` array with tool invocations
- **Task 3**: Add agentic loop - iteratively call tools until the task is complete
