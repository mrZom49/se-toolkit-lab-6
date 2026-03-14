# Plan: Task 1 — Call an LLM from Code

## Provider and model
- **Provider:** OpenRouter (free, no credit card)
- **Model:** `meta-llama/llama-4-scout:free` (best free option with tool calling support)
- **API format:** OpenAI-compatible chat completions

## Agent structure
- Single file `agent.py` in project root
- Read config from `.env.agent.secret` via `dotenv`
- Accept question as CLI argument (`sys.argv[1]`)
- Send to LLM via `httpx` (already in deps) or `requests`
- Output JSON `{"answer": "...", "tool_calls": []}` to stdout
- All debug output to stderr

## Key decisions
- Use `openai` SDK if available, otherwise raw HTTP
- 60-second timeout on LLM call
- Exit code 0 on success, non-zero on failure
