"""Draft reply model for generated email responses.

Dataclass representing a draft reply created in Gmail. Produced by
processor/draft.py and consumed by workflows/pipeline.py for creating
Gmail drafts via GmailClient.create_draft().

See PLAN.md §5 Phase 2: Draft for deduplication and threading details.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DraftReply:
    """A generated draft reply to be created in Gmail.

    Created by processor/draft.py when an email passes the importance
    threshold gate. Consumed by workflows/pipeline.py which calls
    GmailClient.create_draft() to persist it.

    Threading: reply is created in the same thread as the original email
    using the In-Reply-To / References headers.

    Attributes:
        email_id: Gmail message ID of the original email being replied to.
        thread_id: Gmail thread ID for the reply placement.
        reply_text: Generated plain-text reply body.
        subject: Reply subject line (Re: prefix applied if not already present).
        to_address: Recipient email address (From header of original email).
    """

    email_id: str
    thread_id: str
    reply_text: str
    subject: str
    to_address: str

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if not self.email_id:
            raise ValueError("email_id cannot be empty")
        if not self.thread_id:
            raise ValueError("thread_id cannot be empty")
        if not self.reply_text:
            raise ValueError("reply_text cannot be empty")
        if not self.subject:
            raise ValueError("subject cannot be empty")
        if not self.to_address:
            raise ValueError("to_address cannot be empty")
