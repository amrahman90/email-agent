"""Email processing modules.

Re-exports all processor classes for convenient importing:
    - TriageProcessor from triage.py
    - DraftProcessor from draft.py

Usage:
    from email_agent.processor import TriageProcessor, DraftProcessor

See PLAN.md §4 (Project Structure) for processor inventory.
See PLAN.md §5 for two-phase pipeline (Triage → Draft) flow.
"""

from email_agent.processor.draft import DraftProcessor
from email_agent.processor.triage import TriageProcessor

__all__ = [
    "DraftProcessor",
    "TriageProcessor",
]
