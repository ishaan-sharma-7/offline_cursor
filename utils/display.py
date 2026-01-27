"""Display and UI utilities for the coding agent."""
from typing import Dict

# ANSI color codes for terminal output
YOU_COLOR = "\033[94m"
ASSISTANT_COLOR = "\033[93m"
ERROR_COLOR = "\033[91m"
SUCCESS_COLOR = "\033[92m"
RESET_COLOR = "\033[0m"


def show_tool_result(name: str, result: Dict) -> str:
    """
    Display tool result in a clean format.

    Returns:
        hint message if applicable (e.g., file not found suggestions), empty string otherwise
    """
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
    elif name == "apply_diff":
        if result.get("action") == "applied":
            print(f"  {SUCCESS_COLOR}✓ Applied diff to {result['path']}{RESET_COLOR}")
            print(f"    Changed {result.get('lines_changed', 0)} lines")
            if result.get('diff_preview'):
                print(f"    Preview:")
                # Show first 10 lines of diff
                diff_lines = result['diff_preview'].split('\n')[:10]
                for line in diff_lines:
                    print(f"      {line}")
                if len(result['diff_preview'].split('\n')) > 10:
                    print(f"      ... (truncated)")
    elif name == "view_file":
        print(f"  {SUCCESS_COLOR}✓ Viewing lines {result['showing_lines']}{RESET_COLOR}")
    elif name == "list_files":
        print(f"  {SUCCESS_COLOR}✓ Listed {len(result.get('files', []))} items{RESET_COLOR}")
    else:
        print(f"  {SUCCESS_COLOR}✓ {name} completed{RESET_COLOR}")

    return hint


def get_multiline_input():
    """Get multi-line input from the user."""
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
