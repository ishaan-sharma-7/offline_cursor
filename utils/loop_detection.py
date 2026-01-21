"""Loop detection utilities to prevent repetitive actions."""
from typing import Dict, List


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
    Detect if the agent is stuck in a loop.

    Args:
        action_history: List of recent action signatures
        error_history: List of recent error messages

    Returns:
        Correction message if looping detected, empty string otherwise
    """
    if len(action_history) < 3:
        return ""

    # Check for same error twice in a row
    if len(error_history) >= 2:
        if error_history[-1] == error_history[-2]:
            return "STOP. Same error twice in a row. Read the error message carefully - it tells you the exact line number to fix."

    recent = action_history[-6:]

    # Check for same action 3 times
    if len(recent) >= 3 and recent[-1] == recent[-2] == recent[-3]:
        return f"STOP. You've done the same action 3 times: {recent[-1]}. Move on to the next step."

    # Check for alternating 2-action loop
    if len(recent) >= 4:
        if recent[-1] == recent[-3] and recent[-2] == recent[-4]:
            return f"STOP. You're in a loop: {recent[-2]} -> {recent[-1]} -> repeat. Break the cycle and continue with the actual task."

    # Check for 3-action repeating cycle
    if len(recent) >= 6:
        if recent[-1] == recent[-4] and recent[-2] == recent[-5] and recent[-3] == recent[-6]:
            return f"STOP. You're repeating a 3-step cycle. The task files are created - move on or report completion."

    # Check for write/delete cycle
    writes = [a for a in recent if a.startswith("write:")]
    deletes = [a for a in recent if a.startswith("delete:")]
    if len(writes) >= 2 and len(deletes) >= 1:
        return "STOP. Do not delete files you just created. Continue building the project."

    # Check for repeated "file not found" errors
    if len(error_history) >= 2:
        recent_errors = error_history[-3:]
        not_found_errors = [e for e in recent_errors if "not found" in e.lower()]
        if len(not_found_errors) >= 2:
            return "STOP. You keep looking for a file that doesn't exist at that path. Use list_files('.') to see where the file actually is - it may be in the current directory, not the project subfolder."

    return ""
