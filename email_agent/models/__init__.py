"""Email data models.

Re-exports all model classes for convenient importing throughout the codebase:
    - Email, EmailMetadata from email.py
    - TriageDecision, TriageAction from triage.py
    - DraftReply from draft.py
    - ImportanceLevel from importance.py

Usage:
    from email_agent.models import Email, TriageDecision, DraftReply

See PLAN.md §4 (Project Structure) for model inventory.
"""

from email_agent.models.draft import DraftReply
from email_agent.models.email import Email, EmailMetadata
from email_agent.models.importance import ImportanceLevel
from email_agent.models.triage import TriageAction, TriageDecision

__all__ = [
    "DraftReply",
    "Email",
    "EmailMetadata",
    "ImportanceLevel",
    "TriageAction",
    "TriageDecision",
]
