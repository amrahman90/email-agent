"""Importance level enum for email importance assessment.

Controls which emails receive draft reply generation based on
importance_threshold configuration.

See PLAN.md §5 (Importance Threshold Gate) for usage details.
"""

from __future__ import annotations

from enum import StrEnum


class ImportanceLevel(StrEnum):
    """Email importance level for draft creation gating.

    Determines which emails get draft replies based on importance_threshold:
        - low:  All REPLY-action emails get drafts
        - medium: REPLY-action emails + important_senders get drafts
        - high: Only important_senders get drafts

    See PLAN.md §5 (Importance Threshold Gate).
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
