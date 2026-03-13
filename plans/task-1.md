# Task 1 Plan: Call an LLM from Code

## LLM Provider and Model

- **Provider**: Qwen Code API (running on remote VM)
- **Model**: `qwen3-coder-plus`
- **API Endpoint**: OpenAI-compatible chat completions API at `http://<vm-ip>:<port>/v1`

## Architecture

The agent will be a simple CLI program with the following flow:

```
Command-line argument → Parse question → Call LLM API → Parse response → Output JSON
```

### Components

1. **Environment Configuration**
   - Read `.env.agent.secret` for `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL`
   - Use `pydantic-settings` (already in project dependencies) for configuration management

2. **LLM Client**
   - Use `httpx` (already in project dependencies) to make async HTTP requests
   - Call the OpenAI-compatible `/chat/completions` endpoint
   - Send the user question as a single user message

3. **Response Processing**
   - Parse the LLM response to extract the answer text
   - Format output as JSON: `{"answer": "...", "tool_calls": []}`
   - `tool_calls` is empty for this task (will be populated in Task 2)

4. **Output Handling**
   - Valid JSON to stdout (single line)
   - All debug/progress output to stderr
   - Exit code 0 on success

### Error Handling

- Timeout: 60 seconds for API request
- Network errors: Catch and report to stderr, exit with non-zero code
- Invalid response: Handle gracefully with error message to stderr

## Testing Strategy

Create one regression test that:
1. Runs `agent.py` as a subprocess with a test question
2. Parses the stdout as JSON
3. Verifies `answer` field exists and is non-empty
4. Verifies `tool_calls` field exists and is an empty array

## Files to Create

1. `plans/task-1.md` - This plan
2. `.env.agent.secret` - LLM configuration (copy from `.env.agent.example`)
3. `agent.py` - Main CLI program
4. `AGENT.md` - Documentation
5. `backend/tests/unit/test_agent.py` - Regression test
