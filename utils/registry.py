"""Tool registry and execution logic."""
import inspect
from typing import Dict
from .tools import (
    read_file_tool,
    list_files_tool,
    write_file_tool,
    insert_lines_tool,
    replace_lines_tool,
    delete_lines_tool,
    run_command_tool,
    view_file_tool,
    search_in_files_tool,
    delete_tool,
)


# Registry of all available tools
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
    """Get string representation of a tool for the system prompt."""
    tool = TOOL_REGISTRY[tool_name]
    sig = str(inspect.signature(tool))
    doc = tool.__doc__.strip() if tool.__doc__ else "No description"
    return f"{tool_name}{sig}\n  {doc}"


def execute_tool(name: str, args: Dict) -> Dict:
    """Execute a tool with the given arguments."""
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
