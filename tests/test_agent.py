"""Regression tests for agent.py."""

import json
import subprocess
import sys


def test_agent_returns_valid_json_with_required_fields():
    """Task 1: agent.py outputs JSON with 'answer' and 'tool_calls'."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What does REST stand for?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Agent failed: {result.stderr[:200]}"

    data = json.loads(result.stdout.strip())
    assert "answer" in data, "Missing 'answer' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"
    assert len(data["answer"]) > 0, "Answer is empty"


def test_agent_uses_read_file_for_wiki_question():
    """Task 2: agent uses read_file to answer wiki questions."""
    result = subprocess.run(
        [sys.executable, "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Agent failed: {result.stderr[:200]}"

    data = json.loads(result.stdout.strip())
    tools_used = {tc["tool"] for tc in data.get("tool_calls", [])}
    assert "read_file" in tools_used, f"Expected read_file in tool_calls, got: {tools_used}"
    assert "wiki/" in data.get("source", ""), f"Expected wiki source, got: {data.get('source')}"


def test_agent_uses_list_files_for_directory_question():
    """Task 2: agent uses list_files to list wiki contents."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Agent failed: {result.stderr[:200]}"

    data = json.loads(result.stdout.strip())
    tools_used = {tc["tool"] for tc in data.get("tool_calls", [])}
    assert "list_files" in tools_used, f"Expected list_files in tool_calls, got: {tools_used}"


def test_agent_uses_read_file_for_framework_question():
    """Task 3: agent uses read_file for system architecture questions."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What framework does the backend use?"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Agent failed: {result.stderr[:200]}"

    data = json.loads(result.stdout.strip())
    tools_used = {tc["tool"] for tc in data.get("tool_calls", [])}
    assert "read_file" in tools_used, f"Expected read_file in tool_calls, got: {tools_used}"
    assert "fastapi" in data["answer"].lower(), f"Expected 'fastapi' in answer"


def test_agent_uses_query_api_for_data_question():
    """Task 3: agent uses query_api for data-dependent questions."""
    result = subprocess.run(
        [sys.executable, "agent.py", "How many items are in the database?"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Agent failed: {result.stderr[:200]}"

    data = json.loads(result.stdout.strip())
    tools_used = {tc["tool"] for tc in data.get("tool_calls", [])}
    assert "query_api" in tools_used, f"Expected query_api in tool_calls, got: {tools_used}"
