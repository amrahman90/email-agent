"""Pydantic settings for email-agent configuration.

Validates configuration from config.yaml with environment variable overrides.
Supports nested settings for Gmail, Ollama, and Agent configuration.

See docs/configuration.md for full configuration reference.
See PLAN.md §12 for authoritative specification.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import structlog
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

LOGGER = structlog.get_logger()


class GmailSettings(BaseSettings):
    """Gmail API configuration settings."""

    credentials_path: Path = Field(default=Path("credentials/credentials.json"))
    token_path: Path = Field(default=Path("credentials/token.json"))


class OllamaSettings(BaseSettings):
    """Ollama LLM configuration settings."""

    base_url: str = Field(default="http://localhost:11434")
    model: str = Field(default="llama3.2:1b")
    timeout: int = Field(default=120, ge=10, le=300)


class AgentSettings(BaseSettings):
    """Agent behavior configuration settings."""

    categories: list[str] = Field(..., min_length=1, max_length=20)
    important_senders: list[str] = Field(..., min_length=1)
    importance_threshold: Literal["low", "medium", "high"] = Field(default="medium")
    max_emails_per_batch: int = Field(default=50, ge=1, le=100)
    email_age_limit_days: int = Field(default=7, ge=0, le=365)
    draft_reply_max_length: int = Field(default=500, ge=50, le=2000)
    polling_interval: int = Field(default=60, ge=10, le=3600)

    @field_validator("categories")
    @classmethod
    def validate_categories_unique(cls, v: list[str]) -> list[str]:
        """Ensure categories are unique case-insensitively."""
        seen: set[str] = set()
        result: list[str] = []
        for cat in v:
            normalized = cat.lower().strip()
            if normalized in seen:
                raise ValueError(f"Duplicate category (case-insensitive): {cat!r}")
            seen.add(normalized)
            result.append(cat.strip())
        return result

    @field_validator("important_senders")
    @classmethod
    def validate_important_senders(cls, v: list[str]) -> list[str]:
        """Validate sender patterns (full emails or domain wildcards)."""
        result: list[str] = []
        for sender in v:
            stripped = sender.strip()
            if not stripped:
                raise ValueError("Empty sender in important_senders")
            if stripped.startswith("@"):
                if not re.match(r"^@[a-zA-Z0-9.-]+$", stripped):
                    raise ValueError(f"Invalid domain wildcard: {stripped!r}")
            elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", stripped):
                raise ValueError(f"Invalid email address: {stripped!r}")
            result.append(stripped)
        return result

    def warn_if_no_age_limit(self) -> None:
        """Emit WARNING if email_age_limit_days is 0."""
        if self.email_age_limit_days == 0:
            LOGGER.warning(
                "email_age_limit_days=0: Processing ALL unread emails with no age limit. "
                "This may take a very long time on first run."
            )


class Settings(BaseSettings):
    """Top-level configuration container.

    Loads from config.yaml with environment variable overrides.
    Environment variables use EMAIL_AGENT_ prefix and _ nested delimiter.
    """

    gmail: GmailSettings = Field(default_factory=lambda: GmailSettings())
    ollama: OllamaSettings = Field(default_factory=lambda: OllamaSettings())
    agent: AgentSettings = Field(default_factory=lambda: AgentSettings())  # type: ignore[call-arg]
