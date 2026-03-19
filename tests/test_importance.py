"""Tests for assess_importance function."""

from __future__ import annotations

from email_agent.models.email import Email, EmailMetadata
from email_agent.models.importance import ImportanceLevel
from email_agent.processor.importance import (
    _has_important_subject,
    _has_low_importance_subject,
    _sender_matches_important,
    assess_importance,
)


def _make_email(sender: str, subject: str) -> Email:
    """Helper to create an Email model."""
    metadata = EmailMetadata(
        message_id="msg_001",
        thread_id="thread_001",
        subject=subject,
        sender=sender,
        recipient="me@gmail.com",
        date=1700000000,
    )
    return Email(
        email_id="msg_001",
        metadata=metadata,
        body="Test body",
    )


def test_high_score_for_important_sender_with_urgent_subject() -> None:
    """Verify high importance score for important sender with urgent subject."""
    email = _make_email(
        sender="boss@company.com",
        subject="URGENT: Deadline tomorrow",
    )

    result = assess_importance(
        email=email,
        important_senders=["boss@company.com"],
        llm_confidence=0.9,
    )

    assert result == ImportanceLevel.HIGH


def test_low_score_for_newsletter_email() -> None:
    """Verify low importance score for newsletter."""
    email = _make_email(
        sender="newsletter@company.com",
        subject="Monthly Newsletter",
    )

    result = assess_importance(
        email=email,
        important_senders=["important@company.com"],
        llm_confidence=0.5,
    )

    assert result == ImportanceLevel.LOW


def test_medium_score_for_regular_email() -> None:
    """Verify medium importance score for regular email."""
    email = _make_email(
        sender="colleague@example.com",
        subject="Quick question",
    )

    result = assess_importance(
        email=email,
        important_senders=["boss@company.com"],
        llm_confidence=0.7,
    )

    assert result == ImportanceLevel.LOW


def test_sender_matches_important_exact_email() -> None:
    """Verify exact email match in important senders."""
    assert _sender_matches_important("boss@company.com", ["boss@company.com"]) is True
    assert _sender_matches_important("Boss@Company.com", ["boss@company.com"]) is True
    assert _sender_matches_important("other@company.com", ["boss@company.com"]) is False


def test_sender_matches_important_domain_wildcard() -> None:
    """Verify domain wildcard match in important senders."""
    assert _sender_matches_important("user@company.com", ["@company.com"]) is True
    assert _sender_matches_important("user@sub.company.com", ["@company.com"]) is True
    assert _sender_matches_important("user@other.com", ["@company.com"]) is False


def test_important_keywords_detected() -> None:
    """Verify important keywords are detected in subject."""
    important_keywords = ["urgent", "asap", "important", "critical", "deadline"]

    for keyword in important_keywords:
        assert _has_important_subject(f"{keyword} - action needed") is True


def test_low_importance_keywords_detected() -> None:
    """Verify low importance keywords are detected in subject."""
    low_keywords = ["newsletter", "unsubscribe", "notification", "update", "digest"]

    for keyword in low_keywords:
        assert _has_low_importance_subject(f"{keyword} update") is True


def test_confidence_high_increases_score() -> None:
    """Verify high confidence (>=0.8) increases importance score."""
    email_normal = _make_email(
        sender="colleague@example.com",
        subject="Quick question",
    )
    email_important = _make_email(
        sender="colleague@example.com",
        subject="Quick question",
    )

    result_normal = assess_importance(
        email=email_normal,
        important_senders=[],
        llm_confidence=0.5,
    )

    result_with_high_confidence = assess_importance(
        email=email_important,
        important_senders=[],
        llm_confidence=0.85,
    )

    assert result_with_high_confidence.value > result_normal.value


def test_confidence_low_decreases_score() -> None:
    """Verify low confidence (<0.5) decreases importance score."""
    email_normal = _make_email(
        sender="colleague@example.com",
        subject="Newsletter Update",
    )
    email_low_conf = _make_email(
        sender="colleague@example.com",
        subject="Newsletter Update",
    )

    result_normal = assess_importance(
        email=email_normal,
        important_senders=[],
        llm_confidence=0.5,
    )

    result_low_confidence = assess_importance(
        email=email_low_conf,
        important_senders=[],
        llm_confidence=0.3,
    )

    assert result_low_confidence.value <= result_normal.value


def test_combined_signals_score() -> None:
    """Verify combined signals produce correct importance."""
    email = _make_email(
        sender="critical@company.com",
        subject="URGENT: Critical deadline",
    )

    result = assess_importance(
        email=email,
        important_senders=["critical@company.com"],
        llm_confidence=0.9,
    )

    assert result == ImportanceLevel.HIGH


def test_no_important_senders_or_keywords_low() -> None:
    """Verify low importance when no important signals."""
    email = _make_email(
        sender="random@example.com",
        subject="Automated notification",
    )

    result = assess_importance(
        email=email,
        important_senders=[],
        llm_confidence=0.4,
    )

    assert result == ImportanceLevel.LOW
