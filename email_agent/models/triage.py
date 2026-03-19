"""Triage decision model for email classification results.

Pydantic model representing the output of LLM triage + business rules
override. Returned by processor/triage.py for use by workflows/pipeline.py.

See PLAN.md §6 for the business rules override layer specification.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class TriageAction(StrEnum):
    """Triage action enum — deterministic set, not user-configurable."""

    IGNORE = "IGNORE"
    REPLY = "REPLY"
    SUSPICIOUS = "SUSPICIOUS"


class TriageDecision(BaseModel):
    """Result of email triage including LLM decision and business rules override.

    Attributes:
        action: What to do with the email (IGNORE/REPLY/SUSPICIOUS).
        category: Configured category label from config.agent.categories.
        confidence: LLM confidence score [0.0, 1.0].
        suspicious_signals: List of risk indicators when action is SUSPICIOUS.
        reason: Human-readable explanation of the triage decision.
    """

    action: TriageAction
    category: str = Field(..., min_length=1, max_length=200)
    confidence: float = Field(..., ge=0.0, le=1.0)
    suspicious_signals: list[str] = Field(default_factory=list)
    reason: str = Field(..., min_length=1, max_length=1000)

    @model_validator(mode="before")
    @classmethod
    def _validate_action_enum(cls, data: Any) -> Any:
        """Coerce action string to TriageAction enum value.

        Handles raw LLM output where action might be a plain str.
        """
        if isinstance(data, dict):
            action_value = data.get("action")
            if isinstance(action_value, str):
                # Normalize to uppercase for enum matching
                data["action"] = action_value.upper()
            # Ensure suspicious_signals is a list
            if not data.get("suspicious_signals"):
                data["suspicious_signals"] = []
        return data

    model_config = {
        "str_strip_whitespace": True,
        "use_enum_values": False,  # Keep enum objects (not string values)
    }
