import inspect
import json
import ast
import re
import ollama
from pathlib import Path
from typing import Any, Dict, List, Tuple, Set
import hashlib


SYSTEM_PROMPT = """You are Qwen, a coding agent. Call tools to complete tasks.

TOOLS:
{tool_list_repr}

FORMAT:
tool: tool_name({{'key': 'value'}})

CRITICAL RULES:
1. Do NOT explain what you will do. Just call the tool.
2. Do NOT say "I will now..." or "Let me...". Just call the tool.
3. Only ONE tool call per response.
4. For newlines in content, use \\n (backslash-n), not actual line breaks.

CORRECT example:
tool: write_file({{'path': 'app.py', 'content': 'import os\\nimport sys\\n\\ndef main():\\n    print("hello")\\n\\nif __name__ == "__main__":\\n    main()'}})

WRONG - Do not do this:
"I will create a file called app.py with the following content..."
(This is wrong because you explained instead of calling the tool)

WORKFLOW:
1. Create files: write_file
2. Edit files: view_file first, then replace_lines/insert_lines/delete_lines
3. Run code: run_command
4. If errors: view_file, fix with replace_lines, run again

RULES:
- Line numbers start at 1
- Always view_file before editing
- Do not delete files you just created unless asked
- Do not create "test" files - work on the actual task files

FILE PATH WARNING:
When Python code creates files (like reports), they are written relative to WHERE YOU RUN THE COMMAND, not where the script lives.
Example: If you run `python myproject/demo.py` and demo.py writes to "report.txt", the file appears in the CURRENT directory, not in myproject/.
Solution: In your generated code, use explicit paths like "myproject/report.txt" or use __file__ to get the script's directory.

If view_file says "not found", use list_files to check both the current directory AND the project directory."""

YOU_COLOR = "\033[94m"
ASSISTANT_COLOR = "\033[93m"
ERROR_COLOR = "\033[91m"
SUCCESS_COLOR = "\033[92m"
RESET_COLOR = "\033[0m"


def resolve_abs_path(path_str: str) -> Path:
    """Resolve a path string to an absolute Path object"""
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


def list_files_tool(path: str = ".") -> Dict[str, Any]:
    """List all files and directories in the specified path"""
    full_path = resolve_abs_path(path)
    all_files = []
    for item in full_path.iterdir():
        all_files.append({
            "filename": item.name,
            "type": "file" if item.is_file() else "dir"
        })
    return {"path": str(full_path), "files": all_files}


def write_file_tool(path: str, content: str) -> Dict[str, Any]:
    """Create a new file or overwrite existing. Use \\n for newlines."""
    full_path = resolve_abs_path(path)
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        line_count = len(content.splitlines())
        char_count = len(content)
        return {
            "path": str(full_path),
            "action": "written",
            "lines": line_count,
            "chars": char_count
        }
    except Exception as e:
        return {"path": str(full_path), "action": "error", "error": str(e)}


def insert_lines_tool(path: str, line: int, content: str) -> Dict[str, Any]:
    """Insert lines BEFORE the specified line number (1-indexed)."""
    full_path = resolve_abs_path(path)
    if not full_path.exists():
        return {"path": str(full_path), "action": "error", "error": "File does not exist. Use write_file first."}
    try:
        original = full_path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        if lines and not lines[-1].endswith('\n'):
            lines[-1] += '\n'
        new_lines = [l + '\n' if not l.endswith('\n') else l for l in content.splitlines()]
        insert_pos = line - 1
        if insert_pos < 0:
            insert_pos = 0
        if insert_pos > len(lines):
            insert_pos = len(lines)
        lines[insert_pos:insert_pos] = new_lines
        full_path.write_text(''.join(lines), encoding="utf-8")
        return {
            "path": str(full_path),
            "action": "inserted",
            "at_line": line,
            "inserted_lines": len(new_lines),
            "total_lines": len(lines)
        }
    except Exception as e:
        return {"path": str(full_path), "action": "error", "error": str(e)}


def replace_lines_tool(path: str, start: int, end: int, content: str) -> Dict[str, Any]:
    """Replace lines start-end (inclusive, 1-indexed) with new content."""
    full_path = resolve_abs_path(path)
    if not full_path.exists():
        return {"path": str(full_path), "action": "error", "error": "File does not exist."}
    try:
        original = full_path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        if start < 1 or end < 1:
            return {"path": str(full_path), "action": "error", "error": "Line numbers must be >= 1"}
        if start > end:
            return {"path": str(full_path), "action": "error", "error": f"start ({start}) must be <= end ({end})"}
        start_idx = start - 1
        end_idx = end
        if content:
            new_lines = [l + '\n' if not l.endswith('\n') else l for l in content.splitlines()]
        else:
            new_lines = []
        lines[start_idx:end_idx] = new_lines
        full_path.write_text(''.join(lines), encoding="utf-8")
        return {
            "path": str(full_path),
            "action": "replaced",
            "replaced_lines": f"{start}-{end}",
            "new_line_count": len(new_lines),
            "total_lines": len(lines)
        }
    except Exception as e:
        return {"path": str(full_path), "action": "error", "error": str(e)}


def delete_lines_tool(path: str, start: int, end: int) -> Dict[str, Any]:
    """Delete lines start-end (inclusive, 1-indexed)."""
    full_path = resolve_abs_path(path)
    if not full_path.exists():
        return {"path": str(full_path), "action": "error", "error": "File does not exist"}
    try:
        original = full_path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        if start < 1 or end < 1:
            return {"path": str(full_path), "action": "error", "error": "Line numbers must be >= 1"}
        if start > end:
            return {"path": str(full_path), "action": "error", "error": f"start ({start}) must be <= end ({end})"}
        start_idx = start - 1
        end_idx = end
        deleted_count = end_idx - start_idx
        del lines[start_idx:end_idx]
        full_path.write_text(''.join(lines), encoding="utf-8")
        return {
            "path": str(full_path),
            "action": "deleted",
            "deleted_lines": f"{start}-{end}",
            "deleted_count": deleted_count,
            "remaining_lines": len(lines)
        }
    except Exception as e:
        return {"path": str(full_path), "action": "error", "error": str(e)}


def run_command_tool(command: str, working_dir: str = ".") -> Dict[str, Any]:
    """Execute a shell command and return stdout/stderr."""
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
    """View a file with line numbers."""
    full_path = resolve_abs_path(filename)
    if not full_path.exists():
        return {"error": f"File not found: {full_path}", "file_path": str(full_path)}
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
    """Search for a regex pattern across files."""
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
    """Delete a file or directory."""
    import shutil
    full_path = resolve_abs_path(path)
    if not full_path.exists():
        return {"path": str(full_path), "action": "not_found", "error": "Does not exist"}
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
    "write_file": write_file_tool,
    "insert_lines": insert_lines_tool,
    "replace_lines": replace_lines_tool,
    "delete_lines": delete_lines_tool,
    "run_command": run_command_tool,
    "view_file": view_file_tool,
    "search_in_files": search_in_files_tool,
    "delete": delete_tool,
}

def get_tool_str_representation(tool_name: str) -> str:
    tool = TOOL_REGISTRY[tool_name]
    sig = str(inspect.signature(tool))
    doc = tool.__doc__.strip() if tool.__doc__ else "No description"
    return f"{tool_name}{sig}\n  {doc}"


def get_full_system_prompt():
    tool_str_repr = "\n\n".join(
        f"• {get_tool_str_representation(name)}"
        for name in TOOL_REGISTRY
    )
    return SYSTEM_PROMPT.format(tool_list_repr=tool_str_repr)

def normalize_multiline_strings(text: str) -> str:
    """
    Replace literal newlines inside string literals with \\n.
    This fixes the most common parse failure.
    """
    result = []
    in_string = False
    string_char = None
    i = 0

    while i < len(text):
        char = text[i]

        if char == '\\' and i + 1 < len(text):
            result.append(char)
            result.append(text[i + 1])
            i += 2
            continue

        if char in ('"', "'"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
            result.append(char)
        elif char == '\n':
            if in_string:
                result.append('\\n')
            else:
                result.append(char)
        else:
            result.append(char)
        i += 1

    return ''.join(result)

def extract_tool_invocations(text: str) -> Tuple[List[Tuple[str, Dict[str, Any]]], str]:
    """
    Parse tool calls. Returns (invocations, error_message).
    error_message is empty string if successful, otherwise describes the problem.
    """
    clean_text = text.replace("```python", "").replace("```json", "").replace("```", "").strip()

    clean_text = normalize_multiline_strings(clean_text)

    match = re.search(r"tool:\s*(\w+)\s*\(", clean_text)
    if not match:
        match = re.search(r"^(\w+)\s*\(\s*\{", clean_text, re.MULTILINE)
        if not match:
            for tool_name in TOOL_REGISTRY:
                if tool_name in text.lower():
                    return [], f"You mentioned '{tool_name}' but didn't call it. Call it now: tool: {tool_name}({{...}})"
            return [], ""

    tool_name = match.group(1)
    if tool_name not in TOOL_REGISTRY:
        return [], f"Unknown tool: {tool_name}"

    start_idx = match.end() - 1

    balance = 0
    in_string = False
    string_char = None
    escape_next = False
    end_idx = -1

    for i in range(start_idx, len(clean_text)):
        char = clean_text[i]

        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue

        if char in ('"', "'"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None

        if not in_string:
            if char == '(':
                balance += 1
            elif char == ')':
                balance -= 1
                if balance == 0:
                    end_idx = i
                    break

    if end_idx == -1:
        return [], f"Incomplete tool call for '{tool_name}' - missing closing parenthesis. Try a shorter content string."

    args_str = clean_text[start_idx + 1:end_idx]
    dict_start = args_str.find('{')
    dict_end = args_str.rfind('}')

    if dict_start == -1 or dict_end == -1:
        return [], f"No arguments dict found for '{tool_name}'. Use: tool: {tool_name}({{\"key\": \"value\"}})"

    json_str = args_str[dict_start:dict_end + 1]

    args = None
    parse_error = None

    try:
        args = ast.literal_eval(json_str)
    except Exception as e:
        parse_error = str(e)

    if args is None:
        try:
            args = json.loads(json_str)
            parse_error = None
        except Exception as e:
            if parse_error is None:
                parse_error = str(e)

    if args is None:
        try:
            fixed = json_str.replace("'", '"')
            args = json.loads(fixed)
            parse_error = None
        except:
            pass

    if args is None:
        return [], f"Could not parse arguments for '{tool_name}': {parse_error}. Use double quotes and \\n for newlines."

    return [(tool_name, args)], ""


def execute_llm_call(conversation: List[Dict[str, str]]):
    response = ollama.chat(
        model="qwen2.5-coder:14b",
        messages=conversation,
        options={
            "temperature": 0.0,
            "num_predict": 4096,
            "num_ctx": 8192,
            "stop": ["User:", "\n\nYou (type"],
        }
    )
    return response['message']['content']


def execute_tool(name: str, args: Dict) -> Dict:
    tool = TOOL_REGISTRY[name]
    try:
        if name == "read_file":
            return tool(args.get("filename", ""))
        elif name == "list_files":
            return tool(args.get("path", "."))
        elif name == "write_file":
            return tool(args.get("path", ""), args.get("content", ""))
        elif name == "insert_lines":
            return tool(args.get("path", ""), args.get("line", 1), args.get("content", ""))
        elif name == "replace_lines":
            return tool(args.get("path", ""), args.get("start", 1), args.get("end", 1), args.get("content", ""))
        elif name == "delete_lines":
            return tool(args.get("path", ""), args.get("start", 1), args.get("end", 1))
        elif name == "run_command":
            return tool(args.get("command", ""), args.get("working_dir", "."))
        elif name == "view_file":
            return tool(args.get("filename", ""), args.get("start_line"), args.get("end_line"))
        elif name == "search_in_files":
            return tool(args.get("pattern", ""), args.get("path", "."), args.get("file_pattern", "*.py"))
        elif name == "delete":
            return tool(args.get("path", ""))
        else:
            return {"error": f"No handler for tool: {name}"}
    except Exception as e:
        return {"error": str(e)}


def show_tool_result(name: str, result: Dict) -> str:
    """Display tool result in a clean format. Returns hint message if applicable."""
    hint = ""

    if result.get("error"):
        print(f"  {ERROR_COLOR}✗ Error: {result['error']}{RESET_COLOR}")
        if "not found" in str(result.get("error", "")).lower() or "File not found" in str(result.get("error", "")):
            hint = "File not found. Use list_files('.') to check the current directory - the file may have been created there instead of in the project folder."
        return hint

    if name == "run_command":
        rc = result.get('returncode', 0)
        status = f"{SUCCESS_COLOR}✓{RESET_COLOR}" if rc == 0 else f"{ERROR_COLOR}✗{RESET_COLOR}"
        print(f"  {status} Command: {result.get('command', 'N/A')} (exit {rc})")
        stdout = result.get('stdout', '').strip()
        stderr = result.get('stderr', '').strip()
        if stdout:
            print(f"    out: {stdout[:400]}")
        if stderr:
            print(f"    err: {stderr[:400]}")
        if not stdout and not stderr:
            print(f"    (no output)")
    elif name == "write_file":
        print(f"  {SUCCESS_COLOR}✓ Wrote {result['lines']} lines to {result['path']}{RESET_COLOR}")
    elif name == "insert_lines":
        print(f"  {SUCCESS_COLOR}✓ Inserted {result['inserted_lines']} lines at line {result['at_line']}{RESET_COLOR}")
    elif name == "replace_lines":
        print(f"  {SUCCESS_COLOR}✓ Replaced lines {result['replaced_lines']}{RESET_COLOR}")
    elif name == "delete_lines":
        print(f"  {SUCCESS_COLOR}✓ Deleted lines {result['deleted_lines']}{RESET_COLOR}")
    elif name == "view_file":
        print(f"  {SUCCESS_COLOR}✓ Viewing lines {result['showing_lines']}{RESET_COLOR}")
    elif name == "list_files":
        print(f"  {SUCCESS_COLOR}✓ Listed {len(result.get('files', []))} items{RESET_COLOR}")
    else:
        print(f"  {SUCCESS_COLOR}✓ {name} completed{RESET_COLOR}")

    return hint


def get_multiline_input():
    print(f"{YOU_COLOR}You (type 'SUBMIT' on a new line to send):{RESET_COLOR}")
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'SUBMIT':
                break
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            return None
    return "\n".join(lines).strip()

def get_action_signature(name: str, args: Dict) -> str:
    """Create a signature for an action to detect repetitive behavior."""
    if name == "write_file":
        return f"write:{args.get('path', '')}"
    elif name == "run_command":
        return f"run:{args.get('command', '')[:50]}"
    elif name == "delete":
        return f"delete:{args.get('path', '')}"
    elif name == "view_file":
        return f"view:{args.get('filename', '')}"
    else:
        return f"{name}:{str(args)[:30]}"


def detect_loop(action_history: List[str], error_history: List[str]) -> str:
    """
    Detect if we're in a loop. Returns a correction message if looping, empty string otherwise.
    error_history tracks recent errors to detect "trying same failing thing repeatedly"
    """
    if len(action_history) < 4:
        return ""

    recent = action_history[-6:]

    if len(recent) >= 3 and recent[-1] == recent[-2] == recent[-3]:
        return f"STOP. You've done the same action 3 times: {recent[-1]}. Move on to the next step."

    if len(recent) >= 4:
        if recent[-1] == recent[-3] and recent[-2] == recent[-4]:
            return f"STOP. You're in a loop: {recent[-2]} -> {recent[-1]} -> repeat. Break the cycle and continue with the actual task."

    if len(recent) >= 6:
        if recent[-1] == recent[-4] and recent[-2] == recent[-5] and recent[-3] == recent[-6]:
            return f"STOP. You're repeating a 3-step cycle. The task files are created - move on or report completion."

    writes = [a for a in recent if a.startswith("write:")]
    deletes = [a for a in recent if a.startswith("delete:")]
    if len(writes) >= 2 and len(deletes) >= 1:
        return "STOP. Do not delete files you just created. Continue building the project."

    if len(error_history) >= 2:
        recent_errors = error_history[-3:]
        not_found_errors = [e for e in recent_errors if "not found" in e.lower()]
        if len(not_found_errors) >= 2:
            return "STOP. You keep looking for a file that doesn't exist at that path. Use list_files('.') to see where the file actually is - it may be in the current directory, not the project subfolder."

    return ""


def run_coding_agent_loop():
    conversation = [{"role": "system", "content": get_full_system_prompt()}]
    MAX_STEPS = 50

    created_files: Set[str] = set()
    action_history: List[str] = []

    print(f"{SUCCESS_COLOR}Coding Agent Ready. Type your request, then 'SUBMIT' to send.{RESET_COLOR}")
    print(f"Press Ctrl+C to exit.\n")

    while True:
        user_input = get_multiline_input()

        if user_input is None:
            print("\nExiting...")
            break
        if not user_input:
            continue

        conversation.append({"role": "user", "content": user_input})
        action_history.clear()
        error_history: List[str] = []
        consecutive_no_tool = 0

        for step in range(1, MAX_STEPS + 1):
            print(f"\n{ASSISTANT_COLOR}[Step {step}/{MAX_STEPS}]{RESET_COLOR}")

            response = execute_llm_call(conversation)
            tool_invocations, parse_error = extract_tool_invocations(response)

            if not tool_invocations:
                consecutive_no_tool += 1

                response_lower = response.lower()
                done_signals = ['task complete', 'finished creating', 'all files created', 'project is ready', 'done.']
                if any(sig in response_lower for sig in done_signals):
                    print(f"{SUCCESS_COLOR}Agent reports completion:{RESET_COLOR} {response[:200]}")
                    if created_files:
                        print(f"{SUCCESS_COLOR}Files created: {', '.join(created_files)}{RESET_COLOR}")
                    break

                if parse_error:
                    print(f"  {ERROR_COLOR}⚠️ Parse error: {parse_error}{RESET_COLOR}")
                    conversation.append({"role": "assistant", "content": response})
                    conversation.append({"role": "user", "content": f"ERROR: {parse_error}"})
                    continue

                print(f"  {ERROR_COLOR}⚠️ No tool call in response{RESET_COLOR}")
                print(f"    Preview: {response[:150]}...")

                if consecutive_no_tool >= 2:
                    nudge = "STOP EXPLAINING. You must call a tool NOW. Example: tool: write_file({\"path\": \"file.py\", \"content\": \"code\"})"
                    conversation.append({"role": "assistant", "content": response})
                    conversation.append({"role": "user", "content": nudge})
                    consecutive_no_tool = 0
                else:
                    conversation.append({"role": "assistant", "content": response})
                    conversation.append({"role": "user", "content": "Call the tool now. Do not explain."})
                continue

            consecutive_no_tool = 0

            name, args = tool_invocations[0]
            action_sig = get_action_signature(name, args)
            action_history.append(action_sig)

            print(f"  Calling: {name}")

            loop_msg = detect_loop(action_history, error_history)
            if loop_msg:
                print(f"  {ERROR_COLOR}⚠️ Loop detected{RESET_COLOR}")
                conversation.append({"role": "assistant", "content": response})
                conversation.append({"role": "user", "content": loop_msg})
                action_history.clear()
                error_history.clear()
                continue

            conversation.append({"role": "assistant", "content": response})

            result = execute_tool(name, args)
            hint = show_tool_result(name, result)

            if result.get("error"):
                error_history.append(str(result.get("error", "")))
                if len(error_history) > 5:
                    error_history.pop(0)

            if name == "write_file" and result.get("action") == "written":
                created_files.add(args.get("path", ""))

            result_str = json.dumps(result)
            if len(result_str) > 3000:
                result_str = result_str[:3000] + "...(truncated)"

            if hint:
                conversation.append({"role": "user", "content": f"Result: {result_str}\n\nHINT: {hint}"})
            else:
                conversation.append({"role": "user", "content": f"Result: {result_str}"})

        if step >= MAX_STEPS:
            print(f"\n{ERROR_COLOR}⚠️ Hit {MAX_STEPS} step limit{RESET_COLOR}")

        if len(conversation) > 40:
            summary = f"[Previous work: Created files: {', '.join(created_files) if created_files else 'none yet'}]"
            conversation = [conversation[0], {"role": "user", "content": summary}] + conversation[-25:]


if __name__ == "__main__":
    run_coding_agent_loop()
