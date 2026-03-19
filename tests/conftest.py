"""Shared pytest fixtures for email-agent tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from email_agent.config.settings import (
    AgentSettings,
    GmailSettings,
    OllamaSettings,
    Settings,
)
from email_agent.gmail.client import GmailClient
from email_agent.models.email import Email, EmailMetadata
from email_agent.ollama.circuit_breaker import CircuitBreaker


@pytest.fixture
def sample_email() -> dict[str, Any]:
    """Return a typical email data dict for testing."""
    return {
        "id": "msg_001",
        "threadId": "thread_001",
        "subject": "Meeting Tomorrow",
        "from": "colleague@example.com",
        "to": "me@gmail.com",
        "date": "1700000000",
        "snippet": "Hi, let's meet tomorrow at 2pm to discuss the project.",
        "body_plain": "Hi,\n\nLet's meet tomorrow at 2pm to discuss the project.\n\nBest,\nJohn",
    }


@pytest.fixture
def sample_email_model() -> Email:
    """Return a sample Email model instance."""
    metadata = EmailMetadata(
        message_id="msg_001",
        thread_id="thread_001",
        subject="Meeting Tomorrow",
        sender="colleague@example.com",
        recipient="me@gmail.com",
        date=1700000000,
    )
    return Email(
        email_id="msg_001",
        metadata=metadata,
        body="Hi,\n\nLet's meet tomorrow at 2pm to discuss the project.\n\nBest,\nJohn",
        snippet="Hi, let's meet tomorrow at 2pm to discuss the project.",
    )


@pytest.fixture
def mock_gmail_service() -> MagicMock:
    """Return a mock Gmail API service object."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_gmail_client(mock_gmail_service: MagicMock) -> GmailClient:
    """Return a GmailClient with a mocked service."""
    return GmailClient(service=mock_gmail_service)


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Return a mock httpx response object."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"message": {"content": "test response"}}
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def mock_ollama_response() -> dict[str, Any]:
    """Return a mock Ollama triage response dict."""
    return {
        "action": "REPLY",
        "category": "WORK",
        "confidence": 0.85,
        "suspicious_signals": [],
        "reason": "This email requires a response about the project meeting.",
    }


@pytest.fixture
def mock_ollama_draft_response() -> dict[str, Any]:
    """Return a mock Ollama draft generation response dict."""
    return {
        "message": {
            "content": "Sure, let's meet at 2pm tomorrow. I'll bring the project documentation.",
        }
    }


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for state tracker tests."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """Return a fresh CircuitBreaker instance."""
    return CircuitBreaker(failure_threshold=5, open_duration=60.0, half_open_max_calls=1)


@pytest.fixture
def ollama_settings() -> OllamaSettings:
    """Return default Ollama settings for testing."""
    return OllamaSettings(
        base_url="http://localhost:11434",
        model="llama3.2:1b",
        timeout=120,
    )


@pytest.fixture
def agent_settings() -> AgentSettings:
    """Return default Agent settings for testing."""
    return AgentSettings(
        categories=["WORK", "PERSONAL", "NEWSLETTER", "PROMOTION"],
        important_senders=["boss@company.com", "@critical.com"],
        importance_threshold="medium",
        max_emails_per_batch=50,
        email_age_limit_days=7,
        draft_reply_max_length=500,
        polling_interval=60,
    )


@pytest.fixture
def gmail_settings() -> GmailSettings:
    """Return default Gmail settings for testing."""
    return GmailSettings(
        credentials_path=Path("credentials/credentials.json"),
        token_path=Path("credentials/token.json"),
    )


@pytest.fixture
def settings(
    gmail_settings: GmailSettings,
    ollama_settings: OllamaSettings,
    agent_settings: AgentSettings,
) -> Settings:
    """Return full Settings for testing."""
    return Settings(
        gmail=gmail_settings,
        ollama=ollama_settings,
        agent=agent_settings,
    )


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def load_email_fixture(fixtures_dir: Path):
    """Return a helper to load an email fixture by name."""

    def _load(name: str) -> dict[str, Any]:
        fixture_path = fixtures_dir / f"{name}.json"
        with open(fixture_path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    return _load
