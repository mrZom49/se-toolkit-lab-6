#!/usr/bin/env python3
import httpx
import json

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            }
        }
    }
]

# Test with tools
response = httpx.post(
    'http://10.93.24.232:42005/v1/chat/completions',
    json={
        'model': 'qwen3-coder-plus',
        'messages': [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': 'List files in wiki directory'}
        ],
        'temperature': 0.1,
        'tools': TOOLS
    },
    headers={'Authorization': 'Bearer my-secret-qwen-key'},
    timeout=30.0
)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
