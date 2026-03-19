"""Draft reply generation processor.

Generates draft replies for emails that pass the importance threshold gate.
Called by workflows/pipeline.py during Phase 2 (Draft) for each email
with action=REPLY that meets the importance threshold.

See PLAN.md §5 Phase 2: Draft for the full pipeline flow.
See PLAN.md §8 for email threading (In-Reply-To / References) details.
"""

from __future__ import annotations

import structlog

from email_agent.exceptions.base import DraftError
from email_agent.models.draft import DraftReply
from email_agent.models.email import Email
from email_agent.models.triage import TriageDecision
from email_agent.ollama.client import OllamaClient

logger = structlog.get_logger(__name__)


def _build_reply_subject(original_subject: str) -> str:
    """Build a reply subject line with Re: prefix if not already present.

    Args:
        original_subject: The original email subject line.

    Returns:
        Subject with Re: prefix if needed.
    """
    stripped = original_subject.strip()
    if stripped.lower().startswith("re:"):
        # Normalize to "Re: " with correct capitalization
        return f"Re: {stripped[3:].strip()}"
    return f"Re: {stripped}"


class DraftProcessor:
    """Draft reply generator using Ollama LLM.

    Generates plain-text draft replies for emails that pass the importance
    threshold gate. Produces DraftReply objects consumed by the pipeline
    for Gmail draft creation.

    Args:
        ollama_client: Ollama API client for draft generation.
        max_length: Maximum characters for generated draft replies.
    """

    def __init__(
        self,
        ollama_client: OllamaClient,
        max_length: int,
    ) -> None:
        self._ollama = ollama_client
        self._max_length = max_length

    async def generate_draft(
        self,
        email: Email,
        triage_decision: TriageDecision,
        system_prompt: str,
    ) -> DraftReply:
        """Generate a draft reply for a triaged email.

        Calls Ollama to generate a draft reply based on the original email
        content and triage decision category.

        Args:
            email: The original email being replied to.
            triage_decision: The triage decision (provides category context).
            system_prompt: System prompt for the Ollama draft generation model.

        Returns:
            DraftReply with all fields populated for Gmail draft creation.

        Raises:
            DraftError: If draft generation fails.
        """
        email_id = email.email_id
        logger.debug(
            "Generating draft reply",
            email_id=email_id,
            category=triage_decision.category,
        )

        try:
            reply_text = await self._ollama.generate_draft(
                email_body=email.body,
                email_subject=email.subject,
                email_from=email.sender,
                system_prompt=system_prompt,
                max_length=self._max_length,
            )
        except Exception as exc:
            raise DraftError(
                f"Draft generation failed for {email_id}",
            ) from exc

        if not reply_text or not reply_text.strip():
            raise DraftError(f"Empty draft generated for {email_id}")

        # Build reply subject
        reply_subject = _build_reply_subject(email.subject)

        logger.debug(
            "Draft generated successfully",
            email_id=email_id,
            reply_subject=reply_subject,
            reply_length=len(reply_text),
        )

        return DraftReply(
            email_id=email_id,
            thread_id=email.thread_id,
            reply_text=reply_text.strip(),
            subject=reply_subject,
            to_address=email.sender,
        )
