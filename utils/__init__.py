"""Utilities package for the coding agent."""

# Import and re-export all utilities
from .display import (
    YOU_COLOR,
    ASSISTANT_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    RESET_COLOR,
    show_tool_result,
    get_multiline_input,
)
from .loop_detection import (
    get_action_signature,
    detect_loop,
)
from .parsing import (
    extract_tool_invocations,
)
from .registry import (
    TOOL_REGISTRY,
    get_tool_str_representation,
    execute_tool,
)
from .config import (
    ApprovalMode,
    AgentConfig,
    get_config,
    init_config,
)
from .approval import (
    ToolRisk,
    get_tool_risk,
    request_approval,
)
from .forbidden import (
    validate_command,
    validate_path,
    FORBIDDEN_COMMAND_PATTERNS,
    FORBIDDEN_PATH_PATTERNS,
)

__all__ = [
    # Display
    'YOU_COLOR',
    'ASSISTANT_COLOR',
    'ERROR_COLOR',
    'SUCCESS_COLOR',
    'RESET_COLOR',
    'show_tool_result',
    'get_multiline_input',
    # Loop detection
    'get_action_signature',
    'detect_loop',
    # Parsing
    'extract_tool_invocations',
    # Registry
    'TOOL_REGISTRY',
    'get_tool_str_representation',
    'execute_tool',
    # Config
    'ApprovalMode',
    'AgentConfig',
    'get_config',
    'init_config',
    # Approval
    'ToolRisk',
    'get_tool_risk',
    'request_approval',
    # Forbidden actions
    'validate_command',
    'validate_path',
    'FORBIDDEN_COMMAND_PATTERNS',
    'FORBIDDEN_PATH_PATTERNS',
]
