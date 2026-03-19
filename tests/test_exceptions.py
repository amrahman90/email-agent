"""Tests for exception hierarchy."""

from __future__ import annotations

from email_agent.exceptions.base import (
    DraftError,
    EmailAgentError,
    GmailApiError,
    GmailAuthError,
    LabelError,
    OllamaConnectionError,
    OllamaTimeoutError,
    QuotaExceededError,
    TriageError,
)


def test_email_agent_error_is_base() -> None:
    """Verify EmailAgentError is the base exception."""
    assert issubclass(EmailAgentError, Exception)


def test_gmail_auth_error_inherits() -> None:
    """Verify GmailAuthError inherits from EmailAgentError."""
    assert issubclass(GmailAuthError, EmailAgentError)


def test_gmail_api_error_inherits() -> None:
    """Verify GmailApiError inherits from EmailAgentError."""
    assert issubclass(GmailApiError, EmailAgentError)


def test_quota_exceeded_error_inherits_from_gmail_api_error() -> None:
    """Verify QuotaExceededError inherits from GmailApiError."""
    assert issubclass(QuotaExceededError, GmailApiError)
    assert issubclass(QuotaExceededError, EmailAgentError)


def test_ollama_connection_error_inherits() -> None:
    """Verify OllamaConnectionError inherits from EmailAgentError."""
    assert issubclass(OllamaConnectionError, EmailAgentError)


def test_ollama_timeout_error_inherits() -> None:
    """Verify OllamaTimeoutError inherits from EmailAgentError."""
    assert issubclass(OllamaTimeoutError, EmailAgentError)


def test_triage_error_inherits() -> None:
    """Verify TriageError inherits from EmailAgentError."""
    assert issubclass(TriageError, EmailAgentError)


def test_draft_error_inherits() -> None:
    """Verify DraftError inherits from EmailAgentError."""
    assert issubclass(DraftError, EmailAgentError)


def test_label_error_inherits() -> None:
    """Verify LabelError inherits from EmailAgentError."""
    assert issubclass(LabelError, EmailAgentError)


def test_exception_chaining_preserved() -> None:
    """Verify exception chaining works with __cause__."""
    original = ValueError("original error")
    gmail_error = GmailApiError("api error")
    gmail_error.__cause__ = original

    assert gmail_error.__cause__ is original
    assert isinstance(gmail_error, GmailApiError)
    assert isinstance(gmail_error, EmailAgentError)


def test_quota_exceeded_isinstance_check() -> None:
    """Verify isinstance works correctly for QuotaExceededError."""
    error = QuotaExceededError("rate limit exceeded")

    assert isinstance(error, QuotaExceededError)
    assert isinstance(error, GmailApiError)
    assert isinstance(error, EmailAgentError)
    assert isinstance(error, Exception)
