"""Tests for Pydantic settings validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from email_agent.config.settings import AgentSettings, GmailSettings, OllamaSettings


def test_gmail_settings_defaults() -> None:
    """Verify GmailSettings default values."""
    settings = GmailSettings()
    assert settings.credentials_path == Path("credentials/credentials.json")
    assert settings.token_path == Path("credentials/token.json")


def test_ollama_settings_defaults() -> None:
    """Verify OllamaSettings default values."""
    settings = OllamaSettings()
    assert settings.base_url == "http://localhost:11434"
    assert settings.model == "llama3.2:1b"
    assert settings.timeout == 120


def test_agent_settings_categories_unique() -> None:
    """Reject duplicate categories case-insensitively."""
    with pytest.raises(ValidationError) as exc_info:
        AgentSettings(
            categories=["Work", "PERSONAL", "work"],
            important_senders=["test@example.com"],
        )
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "Duplicate category" in str(errors[0]["msg"])


def test_agent_settings_important_senders_invalid_email() -> None:
    """Reject invalid email formats in important_senders."""
    with pytest.raises(ValidationError) as exc_info:
        AgentSettings(
            categories=["WORK"],
            important_senders=["not-an-email"],
        )
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "Invalid email address" in str(errors[0]["msg"])


def test_agent_settings_important_senders_domain_wildcard() -> None:
    """Accept valid domain wildcards in important_senders."""
    settings = AgentSettings(
        categories=["WORK"],
        important_senders=["@company.com", "user@partner.org"],
    )
    assert "@company.com" in settings.important_senders
    assert "user@partner.org" in settings.important_senders


def test_agent_settings_email_age_limit_zero() -> None:
    """Allow email_age_limit_days=0 (no age filtering)."""
    settings = AgentSettings(
        categories=["WORK"],
        important_senders=["test@example.com"],
        email_age_limit_days=0,
    )
    assert settings.email_age_limit_days == 0


def test_agent_settings_importance_threshold_validation() -> None:
    """Validate importance_threshold accepts valid values."""
    for threshold in ["low", "medium", "high"]:
        settings = AgentSettings(
            categories=["WORK"],
            important_senders=["test@example.com"],
            importance_threshold=threshold,
        )
        assert settings.importance_threshold == threshold

    with pytest.raises(ValidationError):
        AgentSettings(
            categories=["WORK"],
            important_senders=["test@example.com"],
            importance_threshold="invalid",
        )


def test_agent_settings_polling_interval_bounds() -> None:
    """Validate polling_interval bounds (10-3600 seconds)."""
    settings_min = AgentSettings(
        categories=["WORK"],
        important_senders=["test@example.com"],
        polling_interval=10,
    )
    assert settings_min.polling_interval == 10

    settings_max = AgentSettings(
        categories=["WORK"],
        important_senders=["test@example.com"],
        polling_interval=3600,
    )
    assert settings_max.polling_interval == 3600

    with pytest.raises(ValidationError):
        AgentSettings(
            categories=["WORK"],
            important_senders=["test@example.com"],
            polling_interval=5,
        )

    with pytest.raises(ValidationError):
        AgentSettings(
            categories=["WORK"],
            important_senders=["test@example.com"],
            polling_interval=4000,
        )


def test_agent_settings_categories_case_normalized() -> None:
    """Verify categories are stripped but case is preserved."""
    settings = AgentSettings(
        categories=["  Work  ", "Personal  "],
        important_senders=["test@example.com"],
    )
    assert "Work" in settings.categories
    assert "Personal" in settings.categories


def test_agent_settings_important_senders_empty_rejected() -> None:
    """Reject empty important_senders list."""
    with pytest.raises(ValidationError) as exc_info:
        AgentSettings(
            categories=["WORK"],
            important_senders=[],
        )
    errors = exc_info.value.errors()
    assert len(errors) == 1


def test_agent_settings_categories_empty_rejected() -> None:
    """Reject empty categories list."""
    with pytest.raises(ValidationError) as exc_info:
        AgentSettings(
            categories=[],
            important_senders=["test@example.com"],
        )
    errors = exc_info.value.errors()
    assert len(errors) == 1
