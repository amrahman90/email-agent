"""State tracking module for email-agent.

Tracks processed email IDs to prevent duplicate processing across runs.
State is persisted to state/processed_emails.json.

State Format:
    {
        "processed": ["msg_id_1", "msg_id_2"],
        "last_processed": "2026-03-19T10:30:00Z"
    }

Cleanup Policy:
    - TTL: IDs older than (email_age_limit_days + 7) days are pruned
    - Max IDs: 10,000 (oldest pruned first if exceeded)
    - Corruption: Log WARNING and start fresh if parse fails

See PLAN.md §14 for full specification.
"""

from email_agent.state.tracker import StateTracker

__all__ = ["StateTracker"]
