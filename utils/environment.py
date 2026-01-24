"""Environment detection utilities for pre-installed libraries and tools.

This module provides functionality to detect installed packages, libraries, and tools
to help the agent make informed decisions before attempting installations.
"""

import subprocess
import sys
from typing import Dict, List, Optional, Set
from pathlib import Path


# Global cache for environment detection (persists for session)
_package_cache: Dict[str, Set[str]] = {}


def get_python_packages() -> Set[str]:
    """Get list of installed Python packages.

    Returns:
        Set of package names (lowercase) installed in current Python environment
    """
    cache_key = 'python_packages'

    # Return cached result if available
    if cache_key in _package_cache:
        return _package_cache[cache_key]

    packages = set()

    try:
        # Method 1: Try using pip list (fastest)
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--format=freeze'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if '==' in line:
                    package_name = line.split('==')[0].strip().lower()
                    packages.add(package_name)
    except Exception:
        # Method 2: Fallback to checking importable modules
        try:
            import pkg_resources
            for dist in pkg_resources.working_set:
                packages.add(dist.project_name.lower())
        except Exception:
            pass

    # Cache the result
    _package_cache[cache_key] = packages
    return packages


def get_npm_packages() -> Set[str]:
    """Get list of globally installed npm packages.

    Returns:
        Set of package names installed globally via npm
    """
    cache_key = 'npm_packages'

    # Return cached result if available
    if cache_key in _package_cache:
        return _package_cache[cache_key]

    packages = set()

    try:
        result = subprocess.run(
            ['npm', 'list', '-g', '--depth=0', '--json'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            if 'dependencies' in data:
                packages = set(data['dependencies'].keys())
    except Exception:
        # Fallback: try parsing text output
        try:
            result = subprocess.run(
                ['npm', 'list', '-g', '--depth=0'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '@' in line and not line.strip().startswith('npm'):
                        # Extract package name from lines like "├── package@version"
                        parts = line.split('@')
                        if len(parts) >= 2:
                            pkg = parts[0].strip().replace('├──', '').replace('└──', '').strip()
                            if pkg:
                                packages.add(pkg)
        except Exception:
            pass

    # Cache the result
    _package_cache[cache_key] = packages
    return packages


def check_command_available(command: str) -> bool:
    """Check if a command/binary is available in PATH.

    Args:
        command: Command name to check (e.g., 'python', 'node', 'git')

    Returns:
        True if command is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['which', command] if sys.platform != 'win32' else ['where', command],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def get_language_runtimes() -> Dict[str, Optional[str]]:
    """Get available language runtimes and their versions.

    Returns:
        Dictionary mapping runtime names to version strings (or None if not installed)
    """
    cache_key = 'language_runtimes'

    # Check cache first
    if cache_key in _package_cache:
        return _package_cache[cache_key]  # type: ignore

    runtimes = {}

    # Define commands to check and their version flags
    checks = {
        'python': ['python3', '--version'],
        'python2': ['python2', '--version'],
        'node': ['node', '--version'],
        'npm': ['npm', '--version'],
        'java': ['java', '-version'],
        'javac': ['javac', '-version'],
        'ruby': ['ruby', '--version'],
        'go': ['go', 'version'],
        'rust': ['rustc', '--version'],
        'cargo': ['cargo', '--version'],
        'gcc': ['gcc', '--version'],
        'g++': ['g++', '--version'],
        'make': ['make', '--version'],
        'git': ['git', '--version'],
        'docker': ['docker', '--version'],
    }

    for name, cmd in checks.items():
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                # Extract version from output (first line usually contains version)
                version_line = (result.stdout or result.stderr).split('\n')[0]
                runtimes[name] = version_line.strip()
            else:
                runtimes[name] = None
        except Exception:
            runtimes[name] = None

    # Cache the result
    _package_cache[cache_key] = runtimes  # type: ignore
    return runtimes


def check_package_installed(package_type: str, package_name: str) -> Dict[str, any]:
    """Check if a specific package is installed.

    Args:
        package_type: Type of package ('python', 'npm', or 'command')
        package_name: Name of the package to check

    Returns:
        Dictionary with 'installed' boolean and optional 'version' or 'info'
    """
    package_name_lower = package_name.lower()

    if package_type == 'python':
        python_packages = get_python_packages()
        installed = package_name_lower in python_packages

        if installed:
            # Try to get version
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'show', package_name],
                    capture_output=True,
                    text=True,
                    timeout=2
                )

                if result.returncode == 0:
                    version = None
                    for line in result.stdout.split('\n'):
                        if line.startswith('Version:'):
                            version = line.split(':', 1)[1].strip()
                            break

                    return {
                        'installed': True,
                        'version': version,
                        'package_type': 'python',
                        'package_name': package_name
                    }
            except Exception:
                pass

        return {
            'installed': installed,
            'package_type': 'python',
            'package_name': package_name
        }

    elif package_type == 'npm':
        npm_packages = get_npm_packages()
        installed = package_name in npm_packages

        return {
            'installed': installed,
            'package_type': 'npm',
            'package_name': package_name
        }

    elif package_type == 'command':
        available = check_command_available(package_name)

        return {
            'installed': available,
            'package_type': 'command',
            'package_name': package_name
        }

    else:
        return {
            'error': f"Unknown package type: {package_type}",
            'installed': False
        }


def get_environment_summary() -> Dict[str, any]:
    """Get a comprehensive summary of the current environment.

    Returns:
        Dictionary with environment information including:
        - Available runtimes and versions
        - Installed Python packages count
        - Installed npm packages count
        - Platform information
    """
    python_packages = get_python_packages()
    npm_packages = get_npm_packages()
    runtimes = get_language_runtimes()

    # Filter to only installed runtimes
    available_runtimes = {k: v for k, v in runtimes.items() if v is not None}

    return {
        'platform': sys.platform,
        'python_version': sys.version.split()[0],
        'python_executable': sys.executable,
        'available_runtimes': available_runtimes,
        'python_packages_count': len(python_packages),
        'npm_packages_count': len(npm_packages),
        'working_directory': str(Path.cwd()),
    }


def clear_cache():
    """Clear the package cache (useful for testing or after installing new packages)."""
    global _package_cache
    _package_cache.clear()
