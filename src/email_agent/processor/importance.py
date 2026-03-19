"""Importance assessment for email draft creation gating.

Determines whether an email is important enough to receive a draft reply
based on sender reputation, subject keywords, and LLM confidence.

The importance level returned gates Phase 2 draft creation:
    - low:  All REPLY-action emails get drafts
    - medium: REPLY-action emails + important_senders get drafts
    - high: Only important_senders get drafts

Called by processor/triage.py during the triage phase to assess
importance alongside the LLM triage decision.

See PLAN.md §5 (Importance Threshold Gate) for usage details.
"""

from __future__ import annotations

import structlog

from email_agent.models.email import Email
from email_agent.models.importance import ImportanceLevel

logger = structlog.get_logger(__name__)

# Keywords indicating potentially important or urgent emails
IMPORTANT_KEYWORDS: list[str] = [
    "urgent",
    "asap",
    "important",
    "critical",
    "deadline",
    "action required",
    "please respond",
    "follow up",
    "time sensitive",
]

# Keywords suggesting low importance or automated notifications
LOW_IMPORTANCE_KEYWORDS: list[str] = [
    "newsletter",
    "unsubscribe",
    "notification",
    "update",
    "digest",
    "automated",
    "no reply",
    "do not reply",
]


def _sender_matches_important(sender: str, important_senders: list[str]) -> bool:
    """Check if sender matches any important_sender pattern.

    Supports both exact email addresses and domain wildcards (@domain.com).
    Matching is case-insensitive.

    Args:
        sender: Sender email address.
        important_senders: List of exact emails or domain wildcards.

    Returns:
        True if sender matches any important_sender pattern.
    """
    sender_lower = sender.lower()
    for pattern in important_senders:
        pattern_lower = pattern.lower()
        if pattern_lower.startswith("@"):
            # Domain wildcard: match any email from that domain
            domain = pattern_lower[1:]
            if sender_lower.endswith(domain):
                return True
        elif sender_lower == pattern_lower:
            # Exact email match
            return True
    return False


def _has_important_subject(subject: str) -> bool:
    """Check if subject contains important/urgent keywords.

    Case-insensitive matching.

    Args:
        subject: Email subject line.

    Returns:
        True if any important keyword is found.
    """
    subject_lower = subject.lower()
    return any(kw in subject_lower for kw in IMPORTANT_KEYWORDS)


def _has_low_importance_subject(subject: str) -> bool:
    """Check if subject contains low-importance keywords.

    Case-insensitive matching.

    Args:
        subject: Email subject line.

    Returns:
        True if any low-importance keyword is found.
    """
    subject_lower = subject.lower()
    return any(kw in subject_lower for kw in LOW_IMPORTANCE_KEYWORDS)


def assess_importance(
    email: Email,
    important_senders: list[str],
    llm_confidence: float | None = None,
) -> ImportanceLevel:
    """Assess the importance level of an email.

    Combines three signals:
        1. Sender reputation (exact email or domain match against important_senders)
        2. Subject keywords (urgent vs. newsletter patterns)
        3. LLM confidence from triage decision

    Args:
        email: The email to assess.
        important_senders: Configured list of important sender patterns.
        llm_confidence: Optional LLM confidence score [0.0, 1.0] from triage.

    Returns:
        ImportanceLevel: low, medium, or high.
    """
    sender = email.sender
    subject = email.subject

    # Signal 1: Sender reputation
    sender_is_important = _sender_matches_important(sender, important_senders)

    # Signal 2: Subject keywords
    subject_is_important = _has_important_subject(subject)
    subject_is_low = _has_low_importance_subject(subject)

    # Signal 3: LLM confidence
    confidence_is_high = llm_confidence is not None and llm_confidence >= 0.8
    confidence_is_low = llm_confidence is not None and llm_confidence < 0.5

    # Scoring logic
    score = 0

    if sender_is_important:
        score += 3  # Strong positive signal
    if subject_is_important:
        score += 1
    if subject_is_low:
        score -= 2
    if confidence_is_high:
        score += 1
    if confidence_is_low:
        score -= 1

    # Classify based on composite score
    if score >= 3:
        return ImportanceLevel.HIGH
    elif score >= 1:
        return ImportanceLevel.MEDIUM
    else:
        return ImportanceLevel.LOW
