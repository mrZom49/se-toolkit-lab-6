#!/usr/bin/env python3
"""CLI agent that answers questions using an LLM.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": []}
"""

import json
import sys
from typing import Any

import httpx
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """LLM configuration from .env.agent.secret."""

    llm_api_key: str
    llm_api_base: str
    llm_model: str

    class Config:
        env_file = ".env.agent.secret"
        env_file_encoding = "utf-8"


def call_lllm(question: str, settings: AgentSettings) -> str:
    """Call the LLM API and return the answer."""
    url = f"{settings.llm_api_base.rstrip('/')}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Answer questions concisely and accurately."},
            {"role": "user", "content": question},
        ],
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    data = response.json()
    answer = data["choices"][0]["message"]["content"]

    print(f"Received answer from LLM.", file=sys.stderr)

    return answer


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        return 1

    question = sys.argv[1]

    try:
        settings = AgentSettings()
    except Exception as e:
        print(f"Error loading settings: {e}", file=sys.stderr)
        return 1

    try:
        answer = call_lllm(question, settings)
    except httpx.HTTPError as e:
        print(f"HTTP error calling LLM: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error calling LLM: {e}", file=sys.stderr)
        return 1

    result: dict[str, Any] = {
        "answer": answer,
        "tool_calls": [],
    }

    print(json.dumps(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
