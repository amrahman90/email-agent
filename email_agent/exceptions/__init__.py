"""Exception hierarchy for email-agent.

All custom exceptions inherit from EmailAgentError to enable
catch-all error handling at the top level.

Exception Hierarchy:
    EmailAgentError
    ├── GmailAuthError
    ├── GmailApiError
    │   └── QuotaExceededError
    ├── OllamaConnectionError
    ├── OllamaTimeoutError
    ├── TriageError
    ├── DraftError
    └── LabelError

See PLAN.md §7 for the authoritative specification.
"""

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

__all__ = [
    "DraftError",
    "EmailAgentError",
    "GmailApiError",
    "GmailAuthError",
    "LabelError",
    "OllamaConnectionError",
    "OllamaTimeoutError",
    "QuotaExceededError",
    "TriageError",
]
