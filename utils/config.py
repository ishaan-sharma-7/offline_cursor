"""Configuration management for the coding agent."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from .streaming import StreamMode


class ApprovalMode(Enum):
    """Approval modes for agent actions."""
    MANUAL = "manual"      # Require approval for risky operations
    AUTO = "auto"          # Execute all operations automatically


@dataclass
class AgentConfig:
    """Runtime configuration for the coding agent."""
    approval_mode: ApprovalMode = ApprovalMode.MANUAL
    enable_forbidden_overrides: bool = False  # Allow overriding forbidden actions with confirmation

    # Streaming feature
    stream_mode: StreamMode = StreamMode.THOUGHTS

    def is_auto_mode(self) -> bool:
        """Check if running in auto mode."""
        return self.approval_mode == ApprovalMode.AUTO

    def set_auto_mode(self, enabled: bool) -> None:
        """Toggle auto mode."""
        self.approval_mode = ApprovalMode.AUTO if enabled else ApprovalMode.MANUAL


# Global config instance
_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config


def init_config(
    auto_mode: bool = False,
    override_forbidden: bool = False,
    stream_mode: str = "silent"
) -> AgentConfig:
    """Initialize config with CLI arguments."""
    global _config

    # Map stream mode string to enum
    stream_mode_enum = {
        "silent": StreamMode.SILENT,
        "thoughts": StreamMode.THOUGHTS,
        "full": StreamMode.FULL
    }.get(stream_mode.lower(), StreamMode.SILENT)

    _config = AgentConfig(
        approval_mode=ApprovalMode.AUTO if auto_mode else ApprovalMode.MANUAL,
        enable_forbidden_overrides=override_forbidden,
        stream_mode=stream_mode_enum
    )
    return _config
