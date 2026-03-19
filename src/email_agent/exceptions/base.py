"""Exception hierarchy for email-agent.

All custom exceptions inherit from EmailAgentError to enable
catch-all error handling at the top level.

See PLAN.md §7 for the authoritative specification.
"""

from __future__ import annotations


class EmailAgentError(Exception):
    """Base exception for all email-agent errors."""

    pass


class GmailAuthError(EmailAgentError):
    """Raised when Gmail OAuth2 authentication fails."""

    pass


class GmailApiError(EmailAgentError):
    """Raised when Gmail API request fails (non-rate-limit errors)."""

    pass


class QuotaExceededError(GmailApiError):
    """Gmail API rate limit exceeded (HTTP 429).

    Requires longer backoff than standard GmailApiError retries.
    Note: isinstance(QuotaExceededError, GmailApiError) returns True,
    so retry functions must use lambda to exclude it from GmailApiError
    retries. See PLAN.md §7 retry strategy.
    """

    pass


class OllamaConnectionError(EmailAgentError):
    """Raised when connection to Ollama fails."""

    pass


class OllamaTimeoutError(EmailAgentError):
    """Raised when Ollama request times out."""

    pass


class TriageError(EmailAgentError):
    """Raised when email triage processing fails."""

    pass


class DraftError(EmailAgentError):
    """Raised when draft reply creation fails."""

    pass


class LabelError(EmailAgentError):
    """Raised when Gmail label operations fail."""

    pass
