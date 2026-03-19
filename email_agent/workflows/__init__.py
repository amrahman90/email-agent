"""Workflow orchestration module.

Provides the main two-phase pipeline orchestrator that coordinates
triage and draft generation across all emails.

Main Orchestrator:
    - Pipeline: Two-phase workflow (Triage → Draft)

The Pipeline class is the MAIN ORCHESTRATOR per PLAN.md §9.
It coordinates:
    1. Fetching unread emails from Gmail
    2. Running Phase 1: Triage for each email
    3. Running Phase 2: Draft generation for important emails
    4. Logging summary statistics

See PLAN.md §5 for two-phase pipeline specification.
See PLAN.md §4 for Phase 4 module inventory.
"""

from email_agent.workflows.pipeline import Pipeline

__all__ = [
    "Pipeline",
]
