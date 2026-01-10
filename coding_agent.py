import inspect
import json
import os

import ollama
from pathlib import Path
from typing import Any, Dict, List, Tuple


SYSTEM_PROMPT = """
You are an autonomous coding agent. Your job is to use the available tools to build, modify, and test code until it works correctly.

AVAILABLE TOOLS:
{tool_list_repr}

TOOL CALLING FORMAT:
Every tool call must be on a single line in this exact format:
tool: TOOL_NAME({{"arg1": "value1", "arg2": "value2"}})

Requirements:
- Valid JSON with double quotes only
- Use \\n for line breaks in strings
- No markdown, no explanations, just the tool call
- One tool call per line

HANDLING LARGE CODE:
The edit_file tool has JSON limitations. For files over 20 lines:

Method 1 - Incremental creation:
tool: edit_file({{"path": "file.py", "old_str": "", "new_str": "import os"}})
tool: edit_file({{"path": "file.py", "old_str": "import os", "new_str": "import os\\nimport sys"}})
tool: edit_file({{"path": "file.py", "old_str": "import sys", "new_str": "import sys\\n\\ndef main():\\n    pass"}})

Method 2 - Delete and recreate:
tool: delete({{"path": "file.py"}})
tool: edit_file({{"path": "file.py", "old_str": "", "new_str": "short_content_here"}})

Method 3 - View then edit:
tool: view_file({{"filename": "file.py"}})
tool: edit_file({{"path": "file.py", "old_str": "exact_line_to_replace", "new_str": "replacement"}})

When you get JSON parse errors, immediately switch to Method 1 or Method 2.

STANDARD WORKFLOW:
1. Create directory structure with run_command mkdir -p
2. Create files using edit_file (keep initial content minimal)
3. Add functionality incrementally with additional edit_file calls
4. Install dependencies with run_command using pip3/python3 on macOS
5. Test by running the code with run_command
6. Read error messages from stdout/stderr
7. Fix errors with targeted edit_file calls
8. Repeat steps 5-7 until tests pass

COMMON PATTERNS:

Starting a new project:
tool: run_command({{"command": "mkdir -p projectname/src projectname/tests"}})
tool: edit_file({{"path": "projectname/src/main.py", "old_str": "", "new_str": "def main():\\n    pass"}})
tool: run_command({{"command": "pip3 install -r projectname/requirements.txt"}})

Modifying existing code:
tool: view_file({{"filename": "src/app.py", "start_line": 10, "end_line": 30}})
tool: edit_file({{"path": "src/app.py", "old_str": "old_function_def", "new_str": "new_function_def"}})

Debugging:
tool: run_command({{"command": "python3 test.py"}})
[read stderr output]
tool: view_file({{"filename": "test.py", "start_line": 15, "end_line": 25}})
tool: edit_file({{"path": "test.py", "old_str": "buggy_line", "new_str": "fixed_line"}})
tool: run_command({{"command": "python3 test.py"}})

PLATFORM SPECIFICS:
- macOS: Use python3 and pip3, not python and pip
- Windows: Use python and pip
- Always check command output (returncode, stdout, stderr)
- Timeout is 30 seconds for run_command

ERROR RECOVERY:
If edit_file returns "old_str not found":
- Use view_file to see actual content
- Copy exact string including whitespace
- Try again with correct old_str

If JSON parse error occurs:
- File is too large for single edit
- Switch to incremental edits or delete+recreate
- Do not output the tool call as plain text
- Do not explain what went wrong
- Just use a different approach

If run_command returns non-zero exit code:
- Read stderr for error message
- Identify the issue (missing import, syntax error, etc)
- Fix with edit_file
- Run again

RESPONSE BEHAVIOR:
When user requests something:
- Do not explain the approach
- Do not write "Here's how to do it"
- Do not output code in markdown blocks
- Immediately start calling tools

After tool execution completes:
- You may provide a brief status update
- Keep it under 2 sentences
- Focus on what was accomplished or what's next

CRITICAL RULES:
1. Never output a tool call as plain text for the user to read
2. Never use markdown code blocks for code
3. Never explain steps before doing them
4. If a tool fails, try a different approach immediately
5. Keep working until the code runs without errors
6. Use view_file before editing unfamiliar code
7. Test everything with run_command

EXAMPLES:

User: "Create a Flask app with one route"
Response:
tool: run_command({{"command": "mkdir -p flask_app"}})
tool: edit_file({{"path": "flask_app/app.py", "old_str": "", "new_str": "from flask import Flask"}})
tool: edit_file({{"path": "flask_app/app.py", "old_str": "from flask import Flask", "new_str": "from flask import Flask\\n\\napp = Flask(__name__)"}})
tool: edit_file({{"path": "flask_app/app.py", "old_str": "app = Flask(__name__)", "new_str": "app = Flask(__name__)\\n\\n@app.route('/')\\ndef home():\\n    return 'Hello'"}})
tool: run_command({{"command": "pip3 install flask"}})
tool: run_command({{"command": "cd flask_app && python3 app.py"}})

User: "Fix the bug in calculator.py"
Response:
tool: view_file({{"filename": "calculator.py"}})
tool: run_command({{"command": "python3 calculator.py"}})
[observe error]
tool: edit_file({{"path": "calculator.py", "old_str": "result = a / b", "new_str": "result = a / b if b != 0 else None"}})
tool: run_command({{"command": "python3 calculator.py"}})

Your goal is to deliver working code. Use tools efficiently, handle errors automatically, and iterate until success.
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
    """Read the complete contents of a file"""
    full_path = resolve_abs_path(filename)
    with open(str(full_path), "r") as f:
        content = f.read()
    return {"file_path": str(full_path), "content": content}

def list_files_tool(path: str) -> Dict[str, Any]:
    """List all files and directories in the specified path"""
    full_path = resolve_abs_path(path)
    all_files = []
    for item in full_path.iterdir():
        all_files.append({
            "filename": item.name,
            "type": "file" if item.is_file() else "dir"
        })
    return {"path": str(full_path), "files": all_files}

def edit_file_tool(path: str, old_str: str, new_str: str) -> Dict[str, Any]:
    """Create a new file or edit an existing file. Use old_str="" to create new files. For edits, old_str must match exactly."""
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

def run_command_tool(command: str, working_dir: str = ".") -> Dict[str, Any]:
    """Execute a shell command (bash, python3, pip3, etc.) and return stdout/stderr. Use this to run code, install packages, test programs."""
    import subprocess
    full_path = resolve_abs_path(working_dir)
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(full_path),
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "working_dir": str(full_path)
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "error": "Command timed out after 30 seconds"}
    except Exception as e:
        return {"command": command, "error": str(e)}

def view_file_tool(filename: str, start_line: int = None, end_line: int = None) -> Dict[str, Any]:
    """View a file with line numbers. Optionally specify start_line and end_line to view specific sections."""
    full_path = resolve_abs_path(filename)
    
    # Check if file exists
    if not full_path.exists():
        return {
            "error": f"File not found: {full_path}",
            "file_path": str(full_path)
        }
    
    content = full_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    if start_line is not None and end_line is not None:
        selected_lines = lines[start_line-1:end_line]
        view = "\n".join(f"{i+start_line}: {line}" for i, line in enumerate(selected_lines))
    elif start_line is not None:
        selected_lines = lines[start_line-1:]
        view = "\n".join(f"{i+start_line}: {line}" for i, line in enumerate(selected_lines))
    else:
        view = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))
    
    return {
        "file_path": str(full_path),
        "content": view,
        "total_lines": len(lines),
        "showing_lines": f"{start_line or 1}-{end_line or len(lines)}"
    }

def search_in_files_tool(pattern: str, path: str = ".", file_pattern: str = "*.py") -> Dict[str, Any]:
    """Search for a regex pattern across multiple files. Useful for finding imports, function definitions, TODOs, etc."""
    import re
    full_path = resolve_abs_path(path)
    matches = []
    
    try:
        for file in full_path.rglob(file_pattern):
            if file.is_file():
                try:
                    content = file.read_text(encoding="utf-8")
                    for i, line in enumerate(content.splitlines(), 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            matches.append({
                                "file": str(file.relative_to(full_path)),
                                "line": i,
                                "content": line.strip()
                            })
                except:
                    continue
    except Exception as e:
        return {"error": str(e)}
    
    return {
        "pattern": pattern,
        "path": str(full_path),
        "file_pattern": file_pattern,
        "matches": matches,
        "total_matches": len(matches)
    }

def delete_tool(path: str) -> Dict[str, Any]:
    """Delete a file or directory. Use carefully - this cannot be undone."""
    import shutil
    full_path = resolve_abs_path(path)
    
    if not full_path.exists():
        return {
            "path": str(full_path),
            "action": "not_found",
            "error": "File or directory does not exist"
        }
    
    try:
        if full_path.is_file():
            full_path.unlink()
            return {"path": str(full_path), "action": "deleted_file"}
        elif full_path.is_dir():
            shutil.rmtree(full_path)
            return {"path": str(full_path), "action": "deleted_directory"}
    except Exception as e:
        return {"path": str(full_path), "action": "error", "error": str(e)}

TOOL_REGISTRY = {
    "read_file": read_file_tool,
    "list_files": list_files_tool,
    "edit_file": edit_file_tool, 
    "run_command": run_command_tool,
    "view_file": view_file_tool,
    "search_in_files": search_in_files_tool,
    "delete": delete_tool,
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
            
            json_str = rest[:-1].strip()
            
            # Try to parse JSON with better error handling
            try:
                args = json.loads(json_str)
            except json.JSONDecodeError as e:
                # Try to fix common issues
                # Sometimes the model puts extra quotes or escapes wrong
                if json_str.startswith('"') and json_str.endswith('"'):
                    json_str = json_str[1:-1]
                    args = json.loads(json_str)
                else:
                    raise e
                    
            invocations.append((name, args))
        except json.JSONDecodeError as e:
            print(f"  ⚠ JSON parse error: {str(e)[:100]}")
            print(f"  ⚠ Attempted to parse: {line[:200]}...")
            continue
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
                elif name == "run_command":
                    resp = tool(args.get("command", ""), args.get("working_dir", "."))
                    print(f"  ✓ Ran command: {resp.get('command')}")
                    if resp.get('stdout'):
                        print(f"    stdout: {resp['stdout'][:200]}")
                    if resp.get('stderr'):
                        print(f"    stderr: {resp['stderr'][:200]}")
                    if resp.get('error'):
                        print(f"    error: {resp['error']}")
                    print(f"    return code: {resp.get('returncode', 'N/A')}")
                elif name == "view_file":
                    resp = tool(
                        args.get("filename"), 
                        args.get("start_line"), 
                        args.get("end_line")
                    )
                    if resp.get('error'):  # ADD THIS CHECK
                        print(f"  ✗ Error: {resp['error']}")
                    else:
                        print(f"  ✓ Viewed file: {resp['file_path']} (lines {resp['showing_lines']})")
                elif name == "search_in_files":
                    resp = tool(
                        args.get("pattern"),
                        args.get("path", "."),
                        args.get("file_pattern", "*.py")
                    )
                    if resp.get('error'):
                        print(f"  ✗ Search error: {resp['error']}")
                    else:
                        print(f"  ✓ Found {resp['total_matches']} matches for '{resp['pattern']}'")
                        # Show first few matches
                        for match in resp['matches'][:5]:
                            print(f"    {match['file']}:{match['line']} - {match['content'][:80]}")
                        if resp['total_matches'] > 5:
                            print(f"    ... and {resp['total_matches'] - 5} more matches")
                elif name == "delete":  # ADD THIS BLOCK
                    resp = tool(args.get("path"))
                    if resp.get('error'):
                        print(f"  ✗ Delete error: {resp['error']}")
                    else:
                        print(f"  ✓ Deleted: {resp['path']} ({resp['action']})")

                conversation.append({
                    "role": "user",
                    "content": f"tool_result({json.dumps(resp)})"
                })

                if resp.get("action") == "no_change_needed":
                    print(f"  → No changes needed")
            
            # After tools execute, continue the loop to get next response

if __name__ == "__main__":
    run_coding_agent_loop()
