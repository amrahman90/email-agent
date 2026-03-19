"""Email Agent configuration module.

This module provides typed configuration management using pydantic-settings.
Configuration is loaded from config.yaml with environment variable overrides.

Configuration Sections:
    - gmail: Gmail API settings (credentials, token paths)
    - ollama: Ollama LLM settings (base_url, model, timeout)
    - agent: Agent behavior settings (categories, thresholds, polling)

See docs/configuration.md for full configuration reference.
"""

from email_agent.config.settings import (
    AgentSettings,
    GmailSettings,
    OllamaSettings,
    Settings,
)

__all__ = [
    "AgentSettings",
    "GmailSettings",
    "OllamaSettings",
    "Settings",
]
