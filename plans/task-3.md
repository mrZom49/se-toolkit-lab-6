# Plan: Task 3 — The System Agent

## New tool: `query_api`
- Parameters: `method` (GET/POST/PUT/DELETE), `path` (endpoint), `body` (optional JSON)
- Returns: JSON with `status_code` and `body`
- Authentication: `Authorization: Bearer {LMS_API_KEY}` header
- Base URL from `AGENT_API_BASE_URL` env var (default: `http://localhost:42002`)

## System prompt updates
- Tell the LLM when to use `query_api` vs `read_file`:
  - Data questions (counts, scores, analytics) → `query_api`
  - Code/architecture questions → `read_file`
  - Wiki/documentation → `read_file` + `list_files`
  - Bug diagnosis → `query_api` to reproduce, then `read_file` to find the bug

## Environment variables
All config from env vars, not hardcoded. The autochecker injects its own values.

## Benchmark strategy
- Run `run_eval.py` after implementation
- Fix one question at a time
- Iterate on system prompt based on failures
