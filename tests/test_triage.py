"""Tests for TriageProcessor and business rules."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from email_agent.models.email import Email, EmailMetadata
from email_agent.models.triage import TriageAction, TriageDecision
from email_agent.ollama.client import OllamaClient
from email_agent.processor.triage import (
    TriageProcessor,
    _apply_low_confidence_downgrade,
    _apply_phishing_override,
    _apply_travel_override,
)


def _make_email(email_id: str, subject: str, sender: str, body: str = "") -> Email:
    """Helper to create an Email model."""
    metadata = EmailMetadata(
        message_id=email_id,
        thread_id="thread_001",
        subject=subject,
        sender=sender,
        recipient="me@gmail.com",
        date=1700000000,
    )
    return Email(
        email_id=email_id,
        metadata=metadata,
        body=body,
    )


def _make_decision(
    action: TriageAction = TriageAction.REPLY,
    category: str = "WORK",
    confidence: float = 0.8,
    suspicious_signals: list[str] | None = None,
) -> TriageDecision:
    """Helper to create a TriageDecision."""
    return TriageDecision(
        action=action,
        category=category,
        confidence=confidence,
        suspicious_signals=suspicious_signals or [],
        reason="Test decision",
    )


def test_phishing_override_applied_for_urgent_subject_with_suspicious_links() -> None:
    """Verify phishing override for urgent subject with shortened URLs."""
    email = _make_email(
        email_id="msg_001",
        subject="URGENT: Password Reset Required",
        sender="fake@bank.com",
        body="Click here to verify your account. https://bit.ly/fake-link",
    )
    decision = _make_decision(action=TriageAction.REPLY)

    result = _apply_phishing_override(decision, email)

    assert result.action == TriageAction.SUSPICIOUS
    assert result.category == "SECURITY_ADMIN"
    assert "shortened_url" in result.suspicious_signals
    assert result.confidence == 1.0


def test_phishing_override_not_applied_for_normal_email() -> None:
    """Verify phishing override not applied to normal email."""
    email = _make_email(
        email_id="msg_001",
        subject="Meeting Tomorrow",
        sender="colleague@example.com",
        body="Let's meet at 2pm to discuss the project.",
    )
    decision = _make_decision(action=TriageAction.REPLY)

    result = _apply_phishing_override(decision, email)

    assert result is decision


def test_travel_override_applied_for_travel_confirmation_without_reply_request() -> None:
    """Verify travel override for confirmation without reply request."""
    email = _make_email(
        email_id="msg_001",
        subject="Flight Confirmation AA1234",
        sender="travel@airlines.com",
        body="Your flight confirmation is confirmed. Hotel reservation details attached. This is an automated message.",
    )
    decision = _make_decision(action=TriageAction.REPLY)

    result = _apply_travel_override(decision, email)

    assert result.action == TriageAction.IGNORE
    assert "travel itinerary" in result.reason.lower()


def test_travel_override_not_applied_when_reply_requested() -> None:
    """Verify travel override not applied when reply is requested."""
    email = _make_email(
        email_id="msg_001",
        subject="Flight Confirmation AA1234",
        sender="travel@airlines.com",
        body="Please confirm your meal preference. Reply to this email.",
    )
    decision = _make_decision(action=TriageAction.REPLY)

    result = _apply_travel_override(decision, email)

    assert result is decision


def test_low_confidence_downgrade_applied_for_suspicious_with_low_confidence() -> None:
    """Verify low-confidence SUSPICIOUS is downgraded to IGNORE."""
    decision = _make_decision(
        action=TriageAction.SUSPICIOUS,
        confidence=0.3,
        suspicious_signals=["some_signal"],
    )

    result = _apply_low_confidence_downgrade(decision, "msg_001")

    assert result.action == TriageAction.IGNORE
    assert "low-confidence suspicious" in result.reason.lower()


def test_low_confidence_downgrade_not_applied_for_high_confidence() -> None:
    """Verify low-confidence downgrade not applied for high confidence."""
    decision = _make_decision(
        action=TriageAction.SUSPICIOUS,
        confidence=0.8,
        suspicious_signals=["signal1", "signal2"],
    )

    result = _apply_low_confidence_downgrade(decision, "msg_001")

    assert result is decision


@pytest.mark.asyncio
async def test_category_unknown_uses_uncategorized(
    agent_settings: Any,
    mocker: MockerFixture,
) -> None:
    """Verify unknown category in run_triage is replaced with UNCATEGORIZED."""
    unknown_category_response = {
        "action": "REPLY",
        "category": "NOT_A_REAL_CATEGORY_XYZ",
        "confidence": 0.85,
        "reason": "This is a test",
    }

    mock_ollama = AsyncMock(spec=OllamaClient)
    mock_ollama.triage.return_value = unknown_category_response

    processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )

    email = _make_email(
        email_id="msg_001",
        subject="Meeting Tomorrow",
        sender="colleague@example.com",
        body="Let's meet at 2pm.",
    )

    result = await processor.run_triage(email, system_prompt="Triage this email")

    # Unknown category should be replaced with UNCATEGORIZED
    assert result.category == "UNCATEGORIZED"
    assert result.action == TriageAction.REPLY


@pytest.mark.asyncio
async def test_triage_processor_run_triage(
    agent_settings: Any,
    mock_ollama_response: dict[str, Any],
    mocker: MockerFixture,
) -> None:
    """Verify run_triage calls Ollama and applies business rules."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    mock_ollama.triage.return_value = mock_ollama_response

    processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )

    email = _make_email(
        email_id="msg_001",
        subject="Meeting Tomorrow",
        sender="colleague@example.com",
        body="Let's meet at 2pm.",
    )

    result = await processor.run_triage(email, system_prompt="Triage this email")

    assert result.action.value == mock_ollama_response["action"]
    assert result.category == mock_ollama_response["category"]
    mock_ollama.triage.assert_called_once()


def test_phishing_override_with_phishing_subject() -> None:
    """Verify phishing override detects phishing subject keywords."""
    email = _make_email(
        email_id="msg_001",
        subject="Security Alert: Account Suspended",
        sender="boss@company.com",
        body="Please review the attached document.",
    )
    decision = _make_decision(action=TriageAction.REPLY)

    result = _apply_phishing_override(decision, email)

    assert result.action == TriageAction.SUSPICIOUS
    assert "phishing_subject_keyword" in result.suspicious_signals


def test_phishing_override_with_suspicious_links_only() -> None:
    """Verify phishing override triggers on shortened URLs alone."""
    email = _make_email(
        email_id="msg_001",
        subject="Meeting Tomorrow",
        sender="colleague@example.com",
        body="Check this out: https://bit.ly/abc123",
    )
    decision = _make_decision(action=TriageAction.REPLY)

    result = _apply_phishing_override(decision, email)

    assert result.action == TriageAction.SUSPICIOUS
    assert "shortened_url" in result.suspicious_signals


def test_low_confidence_downgrade_not_applied_for_ignore_action() -> None:
    """Verify low-confidence downgrade not applied to IGNORE action."""
    decision = _make_decision(
        action=TriageAction.IGNORE,
        confidence=0.3,
        suspicious_signals=[],
    )

    result = _apply_low_confidence_downgrade(decision, "test_email_001")

    assert result is decision


def test_low_confidence_downgrade_not_applied_for_reply_action() -> None:
    """Verify low-confidence downgrade not applied to REPLY action."""
    decision = _make_decision(
        action=TriageAction.REPLY,
        confidence=0.3,
        suspicious_signals=[],
    )

    result = _apply_low_confidence_downgrade(decision, "test_email_002")

    assert result is decision


def test_travel_override_not_applied_for_non_reply() -> None:
    """Verify travel override not applied to non-REPLY actions."""
    email = _make_email(
        email_id="msg_001",
        subject="Flight Confirmation AA1234",
        sender="travel@airlines.com",
        body="Your flight is confirmed. No reply needed.",
    )
    decision = _make_decision(action=TriageAction.IGNORE)

    result = _apply_travel_override(decision, email)

    assert result is decision
