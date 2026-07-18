"""config package — schema, loader, and default config."""
from config.config_schema import AgentConfig, ModelConfig, ProjectPathsConfig, AgentBehaviorConfig, UIContextConfig
from config.config_loader import ConfigLoader

__all__ = [
    "AgentConfig",
    "ModelConfig",
    "ProjectPathsConfig",
    "AgentBehaviorConfig",
    "UIContextConfig",
    "ConfigLoader",
]
