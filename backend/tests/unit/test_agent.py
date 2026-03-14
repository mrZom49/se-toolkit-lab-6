"""Regression tests for agent.py CLI."""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str, project_root: Path) -> subprocess.CompletedProcess:
    """Run the agent with a question and return the result.

    Args:
        question: The question to ask the agent
        project_root: The project root directory

    Returns:
        CompletedProcess with stdout, stderr, and returncode
    """
    agent_path = project_root / "agent.py"

    # Run with uv run from shell, not as Python module
    return subprocess.run(
        ["uv", "run", str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=project_root,
    )


def test_agent_outputs_valid_json_with_required_fields() -> None:
    """Test that agent.py outputs valid JSON with answer and tool_calls fields.

    This test runs the agent as a subprocess with a simple question,
    parses the stdout as JSON, and verifies the required fields are present.
    """
    project_root = Path(__file__).parent.parent.parent.parent

    question = "What is 2 + 2?"

    result = run_agent(question, project_root)

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = result.stdout.strip()
    assert output, "Agent produced no output"

    data = json.loads(output)

    assert "answer" in data, "Missing 'answer' field in output"
    assert isinstance(data["answer"], str), "'answer' must be a string"
    assert len(data["answer"]) > 0, "'answer' must not be empty"

    assert "tool_calls" in data, "Missing 'tool_calls' field in output"
    assert isinstance(data["tool_calls"], list), "'tool_calls' must be an array"
    assert len(data["tool_calls"]) == 0, "'tool_calls' must be empty for Task 1"


def test_agent_uses_read_file_tool_for_wiki_question() -> None:
    """Test that agent uses read_file tool when answering wiki questions.

    This test runs the agent with a question about git merge conflicts,
    which should require reading the wiki/git-workflow.md file.
    Verifies that read_file is in tool_calls and source references the wiki.
    """
    project_root = Path(__file__).parent.parent.parent.parent

    question = "How do you resolve a merge conflict?"

    result = run_agent(question, project_root)

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = result.stdout.strip()
    assert output, "Agent produced no output"

    data = json.loads(output)

    # Verify tool_calls contains read_file
    assert len(data["tool_calls"]) > 0, "Expected tool_calls to be non-empty"
    
    tool_names = [call.get("tool") for call in data["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Verify source field references wiki/git-workflow.md
    assert "source" in data, "Missing 'source' field in output"
    assert isinstance(data["source"], str), "'source' must be a string"
    assert "wiki/git-workflow.md" in data["source"], \
        f"Expected source to reference wiki/git-workflow.md, got: {data['source']}"

    # Verify answer is present
    assert "answer" in data, "Missing 'answer' field in output"
    assert isinstance(data["answer"], str), "'answer' must be a string"
    assert len(data["answer"]) > 0, "'answer' must not be empty"


def test_agent_uses_list_files_tool_for_directory_question() -> None:
    """Test that agent uses list_files tool when asked about directory contents.

    This test runs the agent with a question about files in the wiki,
    which should require listing the wiki directory.
    Verifies that list_files is in tool_calls.
    """
    project_root = Path(__file__).parent.parent.parent.parent

    question = "What files are in the wiki?"

    result = run_agent(question, project_root)

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = result.stdout.strip()
    assert output, "Agent produced no output"

    data = json.loads(output)

    # Verify tool_calls contains list_files
    assert len(data["tool_calls"]) > 0, "Expected tool_calls to be non-empty"
    
    tool_names = [call.get("tool") for call in data["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"

    # Verify answer is present
    assert "answer" in data, "Missing 'answer' field in output"
    assert isinstance(data["answer"], str), "'answer' must be a string"
    assert len(data["answer"]) > 0, "'answer' must not be empty"
