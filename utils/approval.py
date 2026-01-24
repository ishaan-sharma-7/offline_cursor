"""Human-in-the-loop approval system for the coding agent."""
from enum import Enum
from typing import Dict, Any, Tuple
from .config import get_config
from .display import YOU_COLOR, ASSISTANT_COLOR, ERROR_COLOR, SUCCESS_COLOR, RESET_COLOR
from .forbidden import validate_command, validate_path


class ToolRisk(Enum):
    """Risk levels for tools."""
    SAFE = "safe"              # Read-only, no side effects
    MODERATE = "moderate"      # File modifications
    HIGH = "high"              # Command execution, deletions


# Tool risk categorization
TOOL_RISK_LEVELS: Dict[str, ToolRisk] = {
    # Safe - read-only operations
    "read_file": ToolRisk.SAFE,
    "list_files": ToolRisk.SAFE,
    "view_file": ToolRisk.SAFE,
    "search_in_files": ToolRisk.SAFE,
    "check_installed": ToolRisk.SAFE,
    "list_environment": ToolRisk.SAFE,
    # Moderate - file modifications
    "write_file": ToolRisk.MODERATE,
    "insert_lines": ToolRisk.MODERATE,
    "replace_lines": ToolRisk.MODERATE,
    "delete_lines": ToolRisk.MODERATE,
    # High - command execution and deletions
    "run_command": ToolRisk.HIGH,
    "delete": ToolRisk.HIGH,
}


def get_tool_risk(tool_name: str) -> ToolRisk:
    """Get the risk level for a tool."""
    return TOOL_RISK_LEVELS.get(tool_name, ToolRisk.HIGH)


def format_tool_preview(name: str, args: Dict[str, Any]) -> str:
    """Format a tool call for preview display."""
    if name == "write_file":
        path = args.get("path", "unknown")
        content = args.get("content", "")
        lines = content.count('\n') + 1 if content else 0
        preview = content[:200] + "..." if len(content) > 200 else content
        return f"Write to '{path}' ({lines} lines):\n{preview}"

    elif name == "run_command":
        cmd = args.get("command", "")
        wd = args.get("working_dir", ".")
        return f"Execute command in '{wd}':\n  $ {cmd}"

    elif name == "delete":
        path = args.get("path", "unknown")
        return f"Delete: {path}"

    elif name == "insert_lines":
        path = args.get("path", "unknown")
        line = args.get("line", 1)
        content = args.get("content", "")
        return f"Insert at line {line} in '{path}':\n{content[:100]}"

    elif name == "replace_lines":
        path = args.get("path", "unknown")
        start = args.get("start", 1)
        end = args.get("end", 1)
        content = args.get("content", "")
        return f"Replace lines {start}-{end} in '{path}':\n{content[:100]}"

    elif name == "delete_lines":
        path = args.get("path", "unknown")
        start = args.get("start", 1)
        end = args.get("end", 1)
        return f"Delete lines {start}-{end} in '{path}'"

    else:
        return f"{name}({args})"


def request_approval(name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Request user approval for a tool execution.

    Returns:
        Tuple of (approved: bool, feedback: str)
        - If approved, feedback is empty
        - If rejected, feedback contains user's reason/instruction
    """
    config = get_config()
    risk = get_tool_risk(name)

    # Forbidden actions validation (auto-block before approval)
    if name == "run_command":
        is_safe, error_msg = validate_command(
            args.get("command", ""),
            override_enabled=config.enable_forbidden_overrides
        )
        if not is_safe:
            return False, f"FORBIDDEN: {error_msg}"

    # Path validation (context-aware: read vs write)
    if name in ("write_file", "delete", "insert_lines", "replace_lines", "delete_lines"):
        path = args.get("path", "") or args.get("filename", "")
        is_safe, error_msg = validate_path(
            path,
            operation='write',
            override_enabled=config.enable_forbidden_overrides
        )
        if not is_safe:
            return False, f"FORBIDDEN: {error_msg}"

    # Read operations are allowed even on system paths (for debugging)
    if name in ("read_file", "view_file"):
        path = args.get("path", "") or args.get("filename", "")
        is_safe, error_msg = validate_path(
            path,
            operation='read',
            override_enabled=config.enable_forbidden_overrides
        )
        if not is_safe:
            return False, f"FORBIDDEN: {error_msg}"

    # Safe tools always execute
    if risk == ToolRisk.SAFE:
        return True, ""

    # Auto mode executes everything
    if config.is_auto_mode():
        return True, ""

    # Show approval prompt
    risk_color = ERROR_COLOR if risk == ToolRisk.HIGH else ASSISTANT_COLOR
    risk_label = "HIGH RISK" if risk == ToolRisk.HIGH else "MODERATE"

    print(f"\n{risk_color}{'='*60}{RESET_COLOR}")
    print(f"{risk_color}[{risk_label}] Agent wants to execute:{RESET_COLOR}")
    print(f"{risk_color}{'='*60}{RESET_COLOR}")
    print(format_tool_preview(name, args))
    print(f"{risk_color}{'='*60}{RESET_COLOR}")
    print(f"{YOU_COLOR}Options:{RESET_COLOR}")
    print(f"  {SUCCESS_COLOR}y{RESET_COLOR} / {SUCCESS_COLOR}yes{RESET_COLOR}  - Approve this action")
    print(f"  {ERROR_COLOR}n{RESET_COLOR} / {ERROR_COLOR}no{RESET_COLOR}   - Reject this action")
    print(f"  {ASSISTANT_COLOR}a{RESET_COLOR} / {ASSISTANT_COLOR}auto{RESET_COLOR} - Approve and enable auto-mode for session")
    print(f"  {YOU_COLOR}Or type feedback to guide the agent{RESET_COLOR}")
    print()

    try:
        response = input(f"{YOU_COLOR}Approve? {RESET_COLOR}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{ERROR_COLOR}Interrupted - rejecting action{RESET_COLOR}")
        return False, "User cancelled the operation"

    if response in ('y', 'yes', ''):
        return True, ""

    if response in ('a', 'auto'):
        config.set_auto_mode(True)
        print(f"{SUCCESS_COLOR}Auto-mode enabled for this session{RESET_COLOR}")
        return True, ""

    if response in ('n', 'no'):
        return False, "User rejected the action. Try a different approach."

    # Treat any other input as feedback
    return False, f"User feedback: {response}"
