# Agent Documentation

## Overview

A CLI agent that answers questions about a Learning Management Service project by using an LLM with tool calling. The agent can read project files, list directories, and query the backend API. It implements an agentic loop where the LLM decides which tools to call, the agent executes them, and feeds results back until the LLM produces a final answer.

## Provider and Model

- **Provider:** OpenRouter
- **Model:** `qwen/qwen3.5-flash-02-23` (cheap, supports tool calling)
- **API format:** OpenAI-compatible chat completions with function calling

## How to run

```bash
uv run agent.py "Your question here"
```

Output is a single JSON line to stdout with `answer`, `source`, and `tool_calls` fields. All debug output goes to stderr.

## Configuration

All configuration is read from environment variables. The `.env.agent.secret` and `.env.docker.secret` files are loaded automatically if present, but the autochecker injects its own values.

| Variable | Purpose |
|----------|---------|
| `LLM_API_KEY` | OpenRouter API key |
| `LLM_API_BASE` | API endpoint URL |
| `LLM_MODEL` | Model identifier |
| `LMS_API_KEY` | Backend API key for `query_api` authentication |
| `AGENT_API_BASE_URL` | Backend base URL (default: `http://localhost:42002`) |

Note: `LLM_API_KEY` authenticates with the LLM provider. `LMS_API_KEY` authenticates with the backend API. These are two distinct keys with different purposes.

## Architecture

The agent follows an agentic loop pattern:

1. Parse question from the first CLI argument
2. Build messages array with system prompt + user question
3. Send messages + tool schemas to the LLM
4. If the LLM responds with tool calls → execute each tool, append results as `tool` role messages, go to step 3
5. If the LLM responds with text (no tool calls) → that is the final answer
6. Maximum 10 tool call iterations to prevent infinite loops

The system prompt instructs the LLM on when to use each tool:
- **Wiki/documentation questions** → `list_files` to discover, `read_file` to find answers
- **Codebase/architecture questions** → `read_file` on source files
- **Data questions** (counts, scores, analytics) → `query_api` to call the backend
- **Bug diagnosis** → `query_api` to reproduce the error, then `read_file` on source code

## Tools

### `read_file(path)`

Reads a file from the project repository. The path is resolved relative to the project root. Path traversal is blocked — any path that resolves outside the project directory returns an error. File contents are truncated at 30,000 characters.

### `list_files(path)`

Lists files and directories at a given path. Returns newline-separated entries with `/` suffix for directories. Hidden files (starting with `.`) are excluded. Path traversal protection is the same as `read_file`.

### `query_api(method, path, body?)`

Sends an HTTP request to the deployed backend API. Authenticates with `LMS_API_KEY` via Bearer token. Returns a JSON string with `status_code` and `body` fields. Supports GET, POST, PUT, DELETE methods.

## Lessons learned

- Free models on OpenRouter can be rate-limited upstream at any time, even with a fresh account. Using a cheap paid model is more reliable.
- Wiki files contain lots of hyperlinks and boilerplate. The file content sent back to the LLM must not be truncated too aggressively, or the LLM will never see the relevant section.
- The LLM tends to re-read the same file in a loop if it cannot find the answer. Adding explicit instructions in the system prompt ("never read the same file twice") helps but is not always obeyed — increasing the content limit is the real fix.
- The `source` field extraction is tricky. The LLM sometimes mentions the source in its answer text but does not set it as a structured field. The current approach uses the last `read_file` path as a fallback.
