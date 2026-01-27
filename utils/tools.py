"""File operation tools for the coding agent."""
import difflib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


def resolve_abs_path(path_str: str) -> Path:
    """Resolve a path string to an absolute Path object."""
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def read_file_tool(filename: str) -> Dict[str, Any]:
    """Read the complete contents of a file."""
    full_path = resolve_abs_path(filename)
    with open(str(full_path), "r") as f:
        content = f.read()
    return {"file_path": str(full_path), "content": content}


def list_files_tool(path: str = ".") -> Dict[str, Any]:
    """List all files and directories in the specified path."""
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


def check_installed_tool(package_type: str, package_name: str) -> Dict[str, Any]:
    """Check if a package/library is installed.

    Args:
        package_type: Type of package to check ('python', 'npm', or 'command')
        package_name: Name of the package/command to check

    Returns:
        Dictionary with installation status and version info if available

    Examples:
        check_installed('python', 'requests')  # Check if requests is installed
        check_installed('npm', 'express')      # Check if express is installed globally
        check_installed('command', 'git')      # Check if git command is available
    """
    from .environment import check_package_installed

    try:
        result = check_package_installed(package_type, package_name)
        return result
    except Exception as e:
        return {
            "package_type": package_type,
            "package_name": package_name,
            "installed": False,
            "error": str(e)
        }


def list_environment_tool() -> Dict[str, Any]:
    """Get summary of current environment including installed runtimes and packages.

    Returns:
        Dictionary with environment information:
        - Platform and Python version
        - Available language runtimes (python, node, java, etc.)
        - Count of installed Python and npm packages
        - Working directory

    Use this to understand what tools and libraries are available before attempting installations.
    """
    from .environment import get_environment_summary

    try:
        summary = get_environment_summary()
        return {
            "action": "environment_summary",
            **summary
        }
    except Exception as e:
        return {
            "action": "error",
            "error": str(e)
        }


def find_occurrences(content: str, search: str) -> List[Tuple[int, int]]:
    """
    Find all occurrences of search string in content.

    Args:
        content: The full text content to search in
        search: The exact string to find

    Returns:
        List of (start_pos, end_pos) tuples indicating position of each match.
    """
    occurrences = []
    start = 0

    while True:
        pos = content.find(search, start)
        if pos == -1:
            break
        occurrences.append((pos, pos + len(search)))
        start = pos + 1  # Move forward to find overlapping matches

    return occurrences


def count_changed_lines(diff: str) -> int:
    """
    Count number of changed lines in unified diff.

    Counts lines starting with + or - (excluding file headers +++ and ---).

    Args:
        diff: Unified diff string

    Returns:
        Number of lines that were added or removed
    """
    changed = 0
    for line in diff.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            changed += 1
        elif line.startswith('-') and not line.startswith('---'):
            changed += 1
    return changed


def apply_diff_tool(path: str, search_content: str, replace_content: str) -> Dict[str, Any]:
    """
    Apply a diff by finding and replacing exact text with context validation.

    This tool is safer than line-based editing because it validates that the exact
    text you want to change exists before making modifications. It prevents errors
    from stale line numbers or unexpected file changes.

    Args:
        path: File path (resolved to absolute)
        search_content: Exact text to find (must match exactly including whitespace)
        replace_content: Text to replace with

    Returns:
        Dictionary with:
        - action: "applied" | "error"
        - path: absolute path
        - lines_changed: number of lines modified
        - diff_preview: unified diff showing change
        - error: error message if failed (optional)

    Examples:
        # Fix a bug in a function
        apply_diff(
            path="script.py",
            search_content="def add(a, b):\\n    return a - b",
            replace_content="def add(a, b):\\n    return a + b"
        )

        # Update a variable
        apply_diff(
            path="config.py",
            search_content="DEBUG = False",
            replace_content="DEBUG = True"
        )
    """
    full_path = resolve_abs_path(path)

    # 1. Validate file exists
    if not full_path.exists():
        return {
            "path": str(full_path),
            "action": "error",
            "error": "File does not exist.\n\nSuggestion: Use write_file to create it first."
        }

    try:
        # 2. Read original content
        original_content = full_path.read_text(encoding="utf-8")

        # 3. Find search_content occurrences
        occurrences = find_occurrences(original_content, search_content)

        if len(occurrences) == 0:
            search_preview = search_content[:200] + ("..." if len(search_content) > 200 else "")
            return {
                "path": str(full_path),
                "action": "error",
                "error": (
                    f"Search content not found in file.\n\n"
                    f"Searched for:\n---\n{search_preview}\n---\n\n"
                    f"Suggestion: Use view_file to verify current content, then copy exact text."
                )
            }

        if len(occurrences) > 1:
            # Calculate approximate line numbers for each occurrence
            lines_found = []
            for start_pos, _ in occurrences:
                line_num = original_content[:start_pos].count('\n') + 1
                lines_found.append(str(line_num))

            lines_str = ", ".join(lines_found)
            return {
                "path": str(full_path),
                "action": "error",
                "error": (
                    f"Search content appears {len(occurrences)} times in file.\n\n"
                    f"Found at approximate lines: {lines_str}\n\n"
                    f"Suggestion: Include more surrounding context (like function signature or "
                    f"preceding lines) to make the match unique."
                )
            }

        # 4. Apply the replacement (exactly one match)
        start_pos, end_pos = occurrences[0]
        new_content = (
            original_content[:start_pos] +
            replace_content +
            original_content[end_pos:]
        )

        # 5. Generate unified diff preview
        original_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{full_path.name}",
            tofile=f"b/{full_path.name}",
            lineterm=''
        ))
        diff_preview = '\n'.join(diff_lines)

        # 6. Calculate changes
        lines_changed = count_changed_lines(diff_preview)

        # 7. Write new content
        full_path.write_text(new_content, encoding="utf-8")

        return {
            "path": str(full_path),
            "action": "applied",
            "lines_changed": lines_changed,
            "original_line_count": len(original_lines),
            "new_line_count": len(new_lines),
            "diff_preview": diff_preview[:1000]  # Limit size for display
        }

    except Exception as e:
        return {
            "path": str(full_path),
            "action": "error",
            "error": f"Failed to apply diff: {str(e)}"
        }


def format_python_file(path: Path) -> Dict[str, Any]:
    """
    Auto-format Python file using black and isort.

    Returns:
        Dictionary with formatting results and diff preview
    """
    if not path.exists() or path.suffix != '.py':
        return {"formatted": False, "reason": "Not a Python file or doesn't exist"}

    try:
        # Read original content
        original_content = path.read_text(encoding="utf-8")

        # Run black (formatting)
        subprocess.run(
            ["black", "-q", str(path)],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Run isort (import sorting)
        subprocess.run(
            ["isort", "-q", str(path)],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Read formatted content
        formatted_content = path.read_text(encoding="utf-8")

        # Generate diff if changes were made
        if original_content != formatted_content:
            original_lines = original_content.splitlines(keepends=True)
            formatted_lines = formatted_content.splitlines(keepends=True)

            diff_lines = list(difflib.unified_diff(
                original_lines,
                formatted_lines,
                fromfile=f"a/{path.name}",
                tofile=f"b/{path.name}",
                lineterm=''
            ))
            diff_preview = '\n'.join(diff_lines[:20])  # First 20 lines
            lines_changed = count_changed_lines('\n'.join(diff_lines))

            return {
                "formatted": True,
                "changes_made": True,
                "lines_changed": lines_changed,
                "diff_preview": diff_preview
            }
        else:
            return {"formatted": True, "changes_made": False}

    except subprocess.TimeoutExpired:
        return {"formatted": False, "error": "Formatting timed out"}
    except FileNotFoundError:
        return {"formatted": False, "error": "black or isort not installed"}
    except Exception as e:
        return {"formatted": False, "error": str(e)}


def task_complete_tool(summary: str) -> Dict[str, Any]:
    """Signal that the current task is complete. Call this when you have finished the user's request.

    Args:
        summary: Brief description of what was accomplished

    Returns:
        Confirmation that task completion was recorded

    Example:
        task_complete({"summary": "Created hello_world.py and ran it successfully"})
    """
    return {
        "action": "task_complete",
        "summary": summary,
        "status": "completed"
    }

