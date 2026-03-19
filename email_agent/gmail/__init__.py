"""Gmail API integration module.

Provides Gmail API client with OAuth2 authentication, label management,
and email operations (read, label, draft).

OAuth2 Scopes:
    - https://www.googleapis.com/auth/gmail.readonly
    - https://www.googleapis.com/auth/gmail.labels
    - https://www.googleapis.com/auth/gmail.compose

Key Classes:
    - GmailClient: Main API client with quota awareness
    - GmailAuth: OAuth2 authentication flow

Key Features:
    - Quota awareness: detects HTTP 429 rate limit errors
    - Retry logic: tenacity-based retry for transient errors
    - Label normalization: NFKD unicode normalization

See PLAN.md §8 for Gmail API integration details.
"""

from email_agent.gmail.auth import GmailAuth
from email_agent.gmail.client import GmailClient

__all__ = [
    "GmailAuth",
    "GmailClient",
]
