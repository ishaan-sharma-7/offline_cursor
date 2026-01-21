"""File operation tools for the coding agent."""
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict


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
