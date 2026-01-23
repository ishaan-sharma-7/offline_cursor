"""Configuration management for the coding agent."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ApprovalMode(Enum):
    """Approval modes for agent actions."""
    MANUAL = "manual"      # Require approval for risky operations
    AUTO = "auto"          # Execute all operations automatically


@dataclass
class AgentConfig:
    """Runtime configuration for the coding agent."""
    approval_mode: ApprovalMode = ApprovalMode.MANUAL

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


def init_config(auto_mode: bool = False) -> AgentConfig:
    """Initialize config with CLI arguments."""
    global _config
    _config = AgentConfig(
        approval_mode=ApprovalMode.AUTO if auto_mode else ApprovalMode.MANUAL
    )
    return _config
