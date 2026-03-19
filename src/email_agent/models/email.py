"""Email data models.

Provides dataclasses for representing Gmail emails and their metadata
used throughout the email-agent pipeline.

See PLAN.md §8 for email threading (In-Reply-To) details.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EmailMetadata:
    """Immutable metadata extracted from Gmail message headers.

    Attributes:
        message_id: Gmail unique message ID (internal).
        thread_id: Gmail thread ID for conversation grouping.
        subject: Email subject line.
        sender: Sender email address (From header).
        recipient: Recipient email address (To header).
        date: Unix timestamp (epoch seconds) from internalDate.
    """

    message_id: str
    thread_id: str
    subject: str
    sender: str
    recipient: str
    date: int


@dataclass(slots=True)
class Email:
    """Full email representation used in the processing pipeline.

    Contains the stripped plain-text body (HTML already removed by pipeline),
    along with extracted metadata. Used by triage, importance assessment,
    and draft generation.

    Attributes:
        email_id: Gmail message ID (alias for message_id, used in pipeline).
        metadata: Parsed headers and identifiers.
        body: Stripped plain-text body (HTML removed by BeautifulSoup in pipeline).
        snippet: Short preview from Gmail (already available without stripping).
        headers: Raw header dict for debugging (not used in normal flow).
    """

    email_id: str
    metadata: EmailMetadata
    body: str = ""
    snippet: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    # Convenience aliases for pipeline ergonomics
    @property
    def message_id(self) -> str:
        """Alias for email_id (Gmail terminology)."""
        return self.email_id

    @property
    def thread_id(self) -> str:
        """Alias for metadata.thread_id."""
        return self.metadata.thread_id

    @property
    def subject(self) -> str:
        """Alias for metadata.subject."""
        return self.metadata.subject

    @property
    def sender(self) -> str:
        """Alias for metadata.sender."""
        return self.metadata.sender

    @property
    def date(self) -> int:
        """Alias for metadata.date (Unix timestamp)."""
        return self.metadata.date

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if not self.email_id:
            raise ValueError("email_id cannot be empty")
        if not self.metadata:
            raise ValueError("metadata cannot be None")
