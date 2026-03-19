"""Tests for OllamaClient."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pytest_mock import MockerFixture

from email_agent.exceptions.base import OllamaConnectionError, OllamaTimeoutError
from email_agent.ollama.circuit_breaker import CircuitBreaker
from email_agent.ollama.client import OllamaClient


@pytest.fixture
def ollama_client(
    ollama_settings: Any,
    circuit_breaker: CircuitBreaker,
) -> OllamaClient:
    """Return an OllamaClient for testing."""
    return OllamaClient(settings=ollama_settings, circuit_breaker=circuit_breaker)


@pytest.mark.asyncio
async def test_health_check_returns_true_on_success(
    ollama_client: OllamaClient, mocker: MockerFixture
) -> None:
    """Verify health_check returns True when Ollama responds."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    mocker.patch.object(
        ollama_client, "_get_client", new_callable=AsyncMock, return_value=mock_client
    )

    result = await ollama_client.health_check()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_returns_false_on_connection_error(
    ollama_client: OllamaClient, mocker: MockerFixture
) -> None:
    """Verify health_check returns False on connection error."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")

    mocker.patch.object(
        ollama_client, "_get_client", new_callable=AsyncMock, return_value=mock_client
    )

    result = await ollama_client.health_check()

    assert result is False


@pytest.mark.asyncio
async def test_triage_returns_decision_dict(
    ollama_client: OllamaClient, mock_ollama_response: dict[str, Any], mocker: MockerFixture
) -> None:
    """Verify triage returns parsed decision dict."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {
            "tool_calls": [
                {
                    "function": {
                        "arguments": '{"action": "REPLY", "category": "WORK", "confidence": 0.85, "suspicious_signals": [], "reason": "Test"}',
                    }
                }
            ]
        }
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mocker.patch.object(
        ollama_client, "_get_client", new_callable=AsyncMock, return_value=mock_client
    )

    result = await ollama_client.triage(
        email_body="Test email body",
        email_subject="Test Subject",
        email_from="test@example.com",
        categories=["WORK", "PERSONAL"],
        system_prompt="Test prompt",
    )

    assert result["action"] == "REPLY"
    assert result["category"] == "WORK"


@pytest.mark.asyncio
async def test_triage_raises_connection_error_when_circuit_open(
    ollama_client: OllamaClient,
) -> None:
    """Verify triage raises OllamaConnectionError when circuit is open."""
    for _ in range(5):
        ollama_client._cb.record_failure()

    assert ollama_client._cb.is_open() is True

    with pytest.raises(OllamaConnectionError) as exc_info:
        await ollama_client.triage(
            email_body="Test body",
            email_subject="Test Subject",
            email_from="test@example.com",
            categories=["WORK"],
            system_prompt="Test prompt",
        )

    assert "Circuit breaker is OPEN" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_draft_returns_text(
    ollama_client: OllamaClient, mocker: MockerFixture
) -> None:
    """Verify generate_draft returns generated text."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {
            "content": "Thank you for your email. I will get back to you soon.",
        }
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mocker.patch.object(
        ollama_client, "_get_client", new_callable=AsyncMock, return_value=mock_client
    )

    result = await ollama_client.generate_draft(
        email_body="Test body",
        email_subject="Test Subject",
        email_from="test@example.com",
        system_prompt="Test prompt",
        max_length=500,
    )

    assert "Thank you" in result


@pytest.mark.asyncio
async def test_generate_draft_raises_connection_error_when_circuit_open(
    ollama_client: OllamaClient,
) -> None:
    """Verify generate_draft raises OllamaConnectionError when circuit is open."""
    for _ in range(5):
        ollama_client._cb.record_failure()

    assert ollama_client._cb.is_open() is True

    with pytest.raises(OllamaConnectionError) as exc_info:
        await ollama_client.generate_draft(
            email_body="Test body",
            email_subject="Test Subject",
            email_from="test@example.com",
            system_prompt="Test prompt",
            max_length=500,
        )

    assert "Circuit breaker is OPEN" in str(exc_info.value)


def test_parse_response_extracts_tool_call_arguments(
    ollama_client: OllamaClient,
) -> None:
    """Verify _parse_response extracts tool call arguments."""
    data = {
        "message": {
            "tool_calls": [
                {
                    "function": {
                        "arguments": '{"action": "IGNORE", "category": "NEWSLETTER", "confidence": 0.9, "suspicious_signals": [], "reason": "Newsletter"}',
                    }
                }
            ]
        }
    }

    result = ollama_client._parse_response(data)

    assert result["action"] == "IGNORE"
    assert result["category"] == "NEWSLETTER"


def test_parse_response_fallback_to_content(
    ollama_client: OllamaClient,
) -> None:
    """Verify _parse_response falls back to content when no tool_calls."""
    data = {
        "message": {
            "content": "This is plain text response without tool calls.",
        }
    }

    result = ollama_client._parse_response(data)

    assert result == "This is plain text response without tool calls."


def test_parse_response_fallback_for_invalid_json_arguments(
    ollama_client: OllamaClient,
) -> None:
    """Verify _parse_response handles invalid JSON in arguments."""
    data = {
        "message": {
            "tool_calls": [
                {
                    "function": {
                        "arguments": "not valid json",
                    }
                }
            ]
        }
    }

    result = ollama_client._parse_response(data)

    assert result["content"] == "not valid json"


@pytest.mark.asyncio
async def test_triage_timeout_raises_ollama_timeout(
    ollama_client: OllamaClient, mocker: MockerFixture
) -> None:
    """Verify triage raises OllamaTimeoutError on timeout."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("Request timed out")

    mocker.patch.object(
        ollama_client, "_get_client", new_callable=AsyncMock, return_value=mock_client
    )

    with pytest.raises(OllamaTimeoutError) as exc_info:
        await ollama_client.triage(
            email_body="Test body",
            email_subject="Test Subject",
            email_from="test@example.com",
            categories=["WORK"],
            system_prompt="Test prompt",
        )

    assert "timed out" in str(exc_info.value).lower()
