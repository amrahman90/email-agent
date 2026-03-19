"""YAML configuration loading helpers.

Loads and validates configuration from config.yaml files.
Provides error handling for YAML parsing and validation failures.

See docs/configuration.md for configuration reference.
"""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml

from email_agent.config.settings import Settings

LOGGER = structlog.get_logger()


class ConfigError(Exception):
    """Raised for YAML parse errors or validation failures."""

    pass


def config_exists(config_path: Path | str | None = None) -> bool:
    """Check if config file exists.

    Args:
        config_path: Path to config file. If None, uses "config.yaml".

    Returns:
        True if config file exists, False otherwise.
    """
    if config_path is None:
        config_path = Path("config.yaml")
    elif isinstance(config_path, str):
        config_path = Path(config_path)

    return config_path.exists()


def load_config(config_path: Path | str | None = None) -> Settings:
    """Load and validate configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses "config.yaml".

    Returns:
        Validated Settings instance.

    Raises:
        ConfigError: If YAML parse fails or validation errors occur.
    """
    if config_path is None:
        config_path = Path("config.yaml")
    elif isinstance(config_path, str):
        config_path = Path(config_path)

    LOGGER.info("Loading configuration", path=str(config_path))

    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ConfigError(f"Configuration file not found: {config_path}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read configuration file: {e}") from e

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in configuration file: {e}") from e

    if not isinstance(data, dict):
        raise ConfigError("Configuration file must contain a YAML dictionary at root")

    try:
        settings = Settings.model_validate(data)
    except Exception as e:
        raise ConfigError(f"Configuration validation failed: {e}") from e

    LOGGER.info(
        "Configuration loaded successfully",
        categories=settings.agent.categories,
        model=settings.ollama.model,
    )

    return settings
