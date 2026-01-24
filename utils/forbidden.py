"""Forbidden actions validation system.

This module provides intelligent validation for dangerous commands and system file access.
It automatically blocks forbidden operations before they reach the approval prompt, with
educational error messages and context-aware validation.
"""

import re
from pathlib import Path
from typing import Tuple

# Safe command allowlist (checked before forbidden patterns)
ALLOWED_COMMAND_PATTERNS = [
    r'^pip\s+(install|uninstall|list|show|freeze)',
    r'^pip3\s+(install|uninstall|list|show|freeze)',
    r'^npm\s+(install|uninstall|update|run|test|start|build)',
    r'^yarn\s+(install|add|remove|run|test|build)',
    r'^pnpm\s+(install|add|remove|run|test)',
    r'^python\s+',
    r'^python3\s+',
    r'^node\s+',
    r'^git\s+',
    r'^cargo\s+(build|run|test|install)',
    r'^go\s+(run|build|test|get)',
    r'^rustc\s+',
    r'^javac\s+',
    r'^java\s+',
    r'^gcc\s+',
    r'^g\+\+\s+',
    r'^make\s+',
    r'^cmake\s+',
    r'^docker\s+(run|build|exec|ps|logs|compose)',
    r'^kubectl\s+',
]

# Forbidden command patterns with educational metadata
FORBIDDEN_COMMAND_PATTERNS = {
    # Destructive filesystem commands
    r'\brm\s+-rf\s+/(?!tmp|var/tmp)': {
        'reason': 'This would recursively delete system files starting from root directory',
        'alternative': 'Use "rm -rf ./target_folder" to delete specific directories in your workspace',
    },
    r'\brm\s+-rf\s+\*': {
        'reason': 'This would delete all files in the current directory and subdirectories',
        'alternative': 'Specify exact files or folders to delete, e.g., "rm -rf build/" or "rm temp_file.txt"',
    },
    r'\bdd\s+if=': {
        'reason': 'The dd command can overwrite entire disks and cause permanent data loss',
        'alternative': 'Use standard file copy commands like "cp" for file operations',
    },
    r'\bmkfs\.': {
        'reason': 'This formats filesystems and will erase all data on the target device',
        'alternative': 'Filesystem formatting should be done manually with extreme caution',
    },
    r'\bformat\s+': {
        'reason': 'This formats drives and will erase all data',
        'alternative': 'Formatting should be done manually outside of automated tools',
    },

    # Privilege escalation
    r'\bsudo\b': {
        'reason': 'Running commands with sudo grants root privileges and can compromise system security',
        'alternative': 'Run the agent without sudo, or execute privileged commands manually',
    },
    r'\bsu\s+': {
        'reason': 'Switching users can grant elevated privileges',
        'alternative': 'Execute user-switching commands manually when needed',
    },
    r'\bchmod\s+777': {
        'reason': 'chmod 777 makes files world-writable, creating serious security vulnerabilities',
        'alternative': 'Use proper permissions like "chmod 755" for executables or "chmod 644" for files',
    },

    # Remote code execution
    r'(curl|wget)\s+.*\|\s*(bash|sh|zsh|fish)': {
        'reason': 'Piping downloaded content directly to a shell interpreter can execute malicious code',
        'alternative': 'Download the script first, review it, then execute: "curl url -o script.sh && bash script.sh"',
    },
    r'wget\s+(-O-|--output-document=-)': {
        'reason': 'wget -O- outputs to stdout, often used to pipe to shell interpreters',
        'alternative': 'Download the file first: "wget -O script.sh url", review it, then execute if safe',
    },

    # System manipulation
    r'\bsetuid\b': {
        'reason': 'Setting SUID bits can create privilege escalation vulnerabilities',
        'alternative': 'SUID modifications should be done manually with full understanding of security implications',
    },
    r'\bsysctl\s+': {
        'reason': 'sysctl modifies kernel parameters and can destabilize the system',
        'alternative': 'Kernel parameter changes should be made manually with proper understanding',
    },
    r'\biptables\s+': {
        'reason': 'Modifying firewall rules can expose your system to network attacks',
        'alternative': 'Firewall configuration should be done manually with careful planning',
    },
    r'\breboot\b': {
        'reason': 'Rebooting would interrupt all running processes and the agent session',
        'alternative': 'Reboot manually when ready, outside of the agent session',
    },
    r'\bshutdown\b': {
        'reason': 'Shutting down would terminate all processes',
        'alternative': 'Shutdown manually when ready',
    },
    r'\binit\s+[016]': {
        'reason': 'Changing init runlevels can halt or reboot the system',
        'alternative': 'System state changes should be done manually',
    },

    # Kernel/hardware access
    r'\bmodprobe\s+': {
        'reason': 'Loading kernel modules requires root access and can compromise system security',
        'alternative': 'Kernel module management should be done manually with proper understanding',
    },
    r'\binsmod\s+': {
        'reason': 'Inserting kernel modules can compromise system stability and security',
        'alternative': 'Use modprobe manually if you need to load kernel modules',
    },
    r'\brmmod\s+': {
        'reason': 'Removing kernel modules can crash the system',
        'alternative': 'Kernel module management should be done manually',
    },
}

# Read-only commands that are safe even on system paths
READ_ONLY_COMMANDS = [
    r'^cat\s+',
    r'^less\s+',
    r'^more\s+',
    r'^head\s+',
    r'^tail\s+',
    r'^grep\s+',
    r'^find\s+',
    r'^ls\s+',
    r'^stat\s+',
    r'^file\s+',
    r'^strings\s+',
    r'^hexdump\s+',
    r'^od\s+',
]

# Write operations that should be blocked on system paths
WRITE_OPERATIONS = ['write_file', 'delete', 'insert_lines', 'replace_lines', 'delete_lines']

# Forbidden path patterns (for write operations)
FORBIDDEN_PATH_PATTERNS = {
    # Linux/Unix system directories
    r'^/etc/': 'System configuration directory - modifications can break your system',
    r'^/sys/': 'Kernel/device interface - should not be modified',
    r'^/proc/': 'Process information pseudo-filesystem - read-only by design',
    r'^/boot/': 'Boot loader files - modifications can prevent system boot',
    r'^/dev/': 'Device files - direct access can damage hardware or data',
    r'^/root/': "Root user's home directory - should not be accessed",
    r'^/var/log/': 'System logs - should not be modified to preserve audit trail',
    r'^/usr/bin/': 'System binaries - modifications can break system commands',
    r'^/usr/sbin/': 'System administration binaries - critical system files',
    r'^/bin/': 'Essential command binaries - system will break if modified',
    r'^/sbin/': 'System binaries - critical for system operation',

    # macOS system directories
    r'^/Library/System': 'macOS system directory - protected by System Integrity Protection',
    r'^/System/': 'macOS system files - modifications can break macOS',
    r'^/private/etc/': 'macOS system configuration - modifications can break system',
    r'^/private/var/': 'macOS system variable data - should not be modified',

    # Windows system directories
    r'^C:\\Windows\\': 'Windows system directory - modifications can break Windows',
    r'^C:\\Program Files\\': 'Installed programs - should be modified through installers',
    r'^C:\\Program Files \(x86\)\\': 'Installed 32-bit programs - use proper installers',
    r'^C:\\ProgramData\\': 'Shared application data - should not be directly modified',
}


def is_allowed_command(command: str) -> bool:
    """Check if command matches safe allowlist patterns.

    Args:
        command: The shell command to check

    Returns:
        True if command is in the allowlist, False otherwise
    """
    for pattern in ALLOWED_COMMAND_PATTERNS:
        if re.match(pattern, command.strip(), re.IGNORECASE):
            return True
    return False


def is_read_only_command(command: str) -> bool:
    """Check if command is read-only (safe to execute on system paths).

    Args:
        command: The shell command to check

    Returns:
        True if command is read-only, False otherwise
    """
    for pattern in READ_ONLY_COMMANDS:
        if re.match(pattern, command.strip(), re.IGNORECASE):
            return True
    return False


def validate_command(command: str, override_enabled: bool = False) -> Tuple[bool, str]:
    """Validate a shell command against forbidden patterns.

    Args:
        command: The shell command to validate
        override_enabled: If True, allows overriding with user confirmation

    Returns:
        Tuple of (is_safe, error_message)
        - is_safe: True if command is safe, False if forbidden
        - error_message: Empty string if safe, educational error if forbidden
    """
    if not command or not command.strip():
        return True, ""

    # First, check if command is in the allowlist
    if is_allowed_command(command):
        return True, ""

    # Check against forbidden patterns
    for pattern, metadata in FORBIDDEN_COMMAND_PATTERNS.items():
        if re.search(pattern, command, re.IGNORECASE):
            error_msg = f"BLOCKED: {metadata['reason']}\n"
            error_msg += f"💡 Suggestion: {metadata['alternative']}"
            if override_enabled:
                error_msg += "\n⚠️  Use --override-forbidden flag to bypass (requires confirmation)"
            return False, error_msg

    # Check for suspicious command chaining
    if any(sep in command for sep in ['&&', '||', ';']):
        # Split by these separators (but not pipes, which are handled separately)
        parts = re.split(r'[;&]+', command)
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Skip if this part is allowlisted
            if is_allowed_command(part):
                continue

            for pattern, metadata in FORBIDDEN_COMMAND_PATTERNS.items():
                if re.search(pattern, part, re.IGNORECASE):
                    error_msg = f"BLOCKED: Chained command contains dangerous operation.\n"
                    error_msg += f"Issue: {metadata['reason']}\n"
                    error_msg += f"💡 Suggestion: {metadata['alternative']}"
                    return False, error_msg

    return True, ""


def validate_path(path: str, operation: str = 'write', override_enabled: bool = False) -> Tuple[bool, str]:
    """Validate a file path against forbidden directories.

    Args:
        path: The file path to validate
        operation: The operation type ('read' or 'write')
        override_enabled: If True, allows overriding with user confirmation

    Returns:
        Tuple of (is_safe, error_message)
        - is_safe: True if path is safe, False if forbidden
        - error_message: Empty string if safe, educational error if forbidden
    """
    if not path or not path.strip():
        return True, ""

    # Read operations on system paths are allowed (for debugging)
    if operation == 'read':
        return True, ""

    # Import resolve_abs_path from tools module
    from .tools import resolve_abs_path

    # Resolve to absolute path
    try:
        abs_path = str(resolve_abs_path(path))
    except Exception as e:
        return False, f"Invalid path: {e}"

    # Check against forbidden patterns (only for write operations)
    for pattern, reason in FORBIDDEN_PATH_PATTERNS.items():
        if re.match(pattern, abs_path, re.IGNORECASE):
            error_msg = f"BLOCKED: Cannot write to system directory.\n"
            error_msg += f"Path: {abs_path}\n"
            error_msg += f"Reason: {reason}\n"
            error_msg += f"💡 Suggestion: Work within your project directory or home folder"
            if override_enabled:
                error_msg += "\n⚠️  Use --override-forbidden flag to bypass (requires confirmation)"
            return False, error_msg

    # Additional safety: Check if path escapes working directory
    cwd = str(Path.cwd())
    home = str(Path.home())

    # Path is safe if it's within:
    # 1. Current working directory
    # 2. User's home directory
    # 3. Temporary directories (/tmp, /var/tmp)
    if not (abs_path.startswith(cwd) or abs_path.startswith(home)):
        if not abs_path.startswith('/tmp/') and not abs_path.startswith('/var/tmp/'):
            error_msg = f"BLOCKED: Path outside safe workspace.\n"
            error_msg += f"Path: {abs_path}\n"
            error_msg += f"Reason: Write operations should be contained within your project or home directory\n"
            error_msg += f"💡 Suggestion: Use paths within {cwd} or {home}"
            return False, error_msg

    return True, ""
