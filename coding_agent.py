import inspect
import json
import os

import ollama
from pathlib import Path
from typing import Any, Dict, List, Tuple


SYSTEM_PROMPT = """
You are a coding assistant whose goal it is to help us solve coding tasks. 
You have access to a series of tools you can execute. Here are the tools you can execute:

{tool_list_repr}

CRITICAL TOOL CALLING RULES:
1. When you need to use a tool, output ONLY the tool call line, nothing else
2. Format: tool: TOOL_NAME({{"arg": "value"}})
3. Use compact single-line JSON with double quotes
4. NO markdown code blocks, NO explanations, NO extra text
5. After receiving tool_result(...), you can respond normally or call another tool
6. For file paths, you can use forward slashes to create nested directories (e.g., "mypackage/__init__.py")
7. Use \\n for newlines in code strings

CORRECT EXAMPLES:
tool: edit_file({{"path": "mypackage/__init__.py", "old_str": "", "new_str": ""}})
tool: edit_file({{"path": "test.py", "old_str": "", "new_str": "def hello():\\n    print('hi')"}})
tool: read_file({{"filename": "config.json"}})
tool: list_files({{"path": "."}})
"""

YOU_COLOR = "\u001b[94m"
ASSISTANT_COLOR = "\u001b[93m"
RESET_COLOR = "\u001b[0m"

def resolve_abs_path(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path

def read_file_tool(filename: str) -> Dict[str, Any]:
    full_path = resolve_abs_path(filename)
    print(full_path)
    with open(str(full_path), "r") as f:
        content = f.read()
    return {"file_path": str(full_path), "content": content}

def list_files_tool(path: str) -> Dict[str, Any]:
    full_path = resolve_abs_path(path)
    all_files = []
    for item in full_path.iterdir():
        all_files.append({
            "filename": item.name,
            "type": "file" if item.is_file() else "dir"
        })
    return {"path": str(full_path), "files": all_files}

def edit_file_tool(path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    full_path = resolve_abs_path(path)
    if full_path.exists():
        original = full_path.read_text(encoding="utf-8")
    else:
        original = ""
    
    # Decode escaped newlines and other escape sequences
    old_str = old_str.encode().decode('unicode_escape')
    new_str = new_str.encode().decode('unicode_escape')
    
    if old_str == "":
        if original == new_str:
            return {"path": str(full_path), "action": "no_change_needed"}
        # Create parent directory if it doesn't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(new_str, encoding="utf-8")
        return {"path": str(full_path), "action": "created_or_overwritten"}
    if original.find(old_str) == -1:
        return {"path": str(full_path), "action": "old_str not found"}
    edited = original.replace(old_str, new_str, 1)
    full_path.write_text(edited, encoding="utf-8")
    return {"path": str(full_path), "action": "edited"}


TOOL_REGISTRY = {
    "read_file": read_file_tool,
    "list_files": list_files_tool,
    "edit_file": edit_file_tool, 
}

def get_tool_str_representation(tool_name: str) -> str:
    tool = TOOL_REGISTRY[tool_name]
    return f"""
    Name: {tool_name}
    Description: {tool.__doc__}
    Signature: {inspect.signature(tool)}
    """

def get_full_system_prompt():
    tool_str_repr = ""
    for tool_name in TOOL_REGISTRY:
        tool_str_repr += "TOOL\n===" + get_tool_str_representation(tool_name)
        tool_str_repr += "\n" + "=" * 15 + "\n"
    return SYSTEM_PROMPT.format(tool_list_repr=tool_str_repr)

def extract_tool_invocations(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    invocations = []
    
    # First try to extract from the raw text
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("tool:"):
            continue
        try:
            after = line[len("tool:"):].strip()
            name, rest = after.split("(", 1)
            name = name.strip()
            if not rest.endswith(")"):
                continue
            args = json.loads(rest[:-1].strip())
            invocations.append((name, args))
        except Exception as e:
            print(f"  ⚠ Failed to parse tool call: {e}")
            continue
    
    return invocations

def execute_llm_call(conversation: List[Dict[str, str]]):
    response = ollama.chat(
        model="qwen2.5-coder:14b",
        messages=conversation,
    )
    return response['message']['content']

def run_coding_agent_loop():
    print(get_full_system_prompt())
    conversation = [{"role": "system", "content": get_full_system_prompt()}]

    while True:
        try:
            user_input = input(f"{YOU_COLOR}You:{RESET_COLOR}:")
        except (KeyboardInterrupt, EOFError):
            break

        conversation.append({"role": "user", "content": user_input.strip()})

        while True:
            assistant_response = execute_llm_call(conversation)
            
            # Clean up markdown code blocks if present
            cleaned_response = assistant_response.strip()
            if cleaned_response.startswith("```") and cleaned_response.endswith("```"):
                lines = cleaned_response.split('\n')
                cleaned_response = '\n'.join(lines[1:-1]).strip()
            
            tool_invocations = extract_tool_invocations(cleaned_response)

            if not tool_invocations:
                print(f"{ASSISTANT_COLOR}Assistant:{RESET_COLOR}: {assistant_response}")
                conversation.append({"role": "assistant", "content": assistant_response})
                break

            # Show what tool is being called
            print(f"{ASSISTANT_COLOR}Assistant:{RESET_COLOR}: Calling tools...")
            
            # Store the assistant's message BEFORE tool execution
            conversation.append({"role": "assistant", "content": cleaned_response})
            for name, args in tool_invocations:
                tool = TOOL_REGISTRY[name]
                tool_path = args.get("path") or args.get("filename")
                resp = {}

                if name == "read_file":
                    resp = tool(args.get("filename", "."))
                    print(f"  ✓ Read file: {resp['file_path']}")
                elif name == "list_files":
                    resp = tool(args.get("path", "."))
                    print(f"  ✓ Listed directory: {resp['path']}")
                elif name == "edit_file":
                    resp = tool(tool_path, args.get("old_str", ""), args.get("new_str", ""))
                    print(f"  ✓ Edited file: {resp['path']} - {resp['action']}")

                conversation.append({
                    "role": "user",
                    "content": f"tool_result({json.dumps(resp)})"
                })

                if resp.get("action") == "no_change_needed":
                    print(f"  → No changes needed")
            
            # After tools execute, continue the loop to get next response

if __name__ == "__main__":
    run_coding_agent_loop()
