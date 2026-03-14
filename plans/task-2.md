# Plan: Task 2 — The Documentation Agent

## Tool schemas
- `read_file(path)` — reads a file, returns contents. Rejects `../` traversal.
- `list_files(path)` — lists directory entries. Rejects traversal.

Both registered as OpenAI function-calling schemas in the LLM request.

## Agentic loop
1. Send question + tool schemas to LLM
2. If LLM returns tool_calls → execute each, append results as tool messages, loop
3. If LLM returns text → extract answer and source, output JSON
4. Max 10 iterations

## Path security
- Resolve paths relative to PROJECT_ROOT
- Check resolved path starts with PROJECT_ROOT string
- Reject anything that escapes

## Source extraction
- The LLM should include a source reference in its answer
- The system prompt instructs it to reference `wiki/filename.md#section-anchor`
