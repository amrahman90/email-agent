"""Two-phase pipeline orchestrator for email processing.

This Pipeline is the MAIN ORCHESTRATOR per PLAN.md §9.
It coordinates:
    1. Fetching unread emails from Gmail
    2. Running Phase 1: Triage for each email
    3. Running Phase 2: Draft generation for important emails
    4. Logging summary statistics

Two-Phase Design (PLAN.md §5):
    Phase 1 (Triage):   Fetch unread → Check state → Strip HTML → Triage → Apply label
    Phase 2 (Draft):    Filter REPLY → Dedup → Importance gate → Generate draft → Create Gmail draft

Per-Email Error Isolation:
    Errors in Phase 1 or Phase 2 for a single email are isolated and logged.
    A failure for one email does NOT stop the batch.

See PLAN.md §5 for full pipeline specification.
See PLAN.md §9 for orchestration decisions.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from bs4 import BeautifulSoup

from email_agent.exceptions.base import LabelError
from email_agent.gmail.client import GmailClient
from email_agent.models.email import Email, EmailMetadata
from email_agent.models.importance import ImportanceLevel
from email_agent.models.triage import TriageAction, TriageDecision
from email_agent.ollama.client import OllamaClient
from email_agent.processor.draft import DraftProcessor
from email_agent.processor.importance import _sender_matches_important
from email_agent.processor.triage import TriageProcessor
from email_agent.state.tracker import StateTracker

if TYPE_CHECKING:
    from email_agent.config.settings import Settings

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class PipelineConfig:
    """Configuration for pipeline execution.

    Attributes:
        settings: Application settings (categories, thresholds, etc.).
        system_prompt_triage: System prompt for triage LLM calls.
        system_prompt_draft: System prompt for draft generation LLM calls.
        dry_run: If True, skip Gmail label/draft operations.
    """

    settings: Settings
    system_prompt_triage: str
    system_prompt_draft: str
    dry_run: bool = False


@dataclass(slots=True)
class PhaseSummary:
    """Summary statistics for a pipeline phase."""

    phase: str
    total: int = 0
    actions: dict[str, int] | None = None
    errors: int = 0

    def to_log_fields(self) -> dict[str, Any]:
        """Return fields for structured logging."""
        fields: dict[str, Any] = {
            "phase": self.phase,
            "total": self.total,
            "errors": self.errors,
        }
        if self.actions:
            fields["actions"] = self.actions
        return fields


@dataclass(slots=True)
class _EmailWithDecision:
    """Holds an email and its Phase 1 triage decision."""

    email: Email
    decision: TriageDecision
    had_error: bool = False


class Pipeline:
    """Two-phase email processing pipeline.

    Phase 1 (Triage):
        1. Fetch unread email IDs from Gmail
        2. Check state tracker for already-processed emails
        3. For each unprocessed email:
            a. Fetch full email from Gmail
            b. Strip HTML to get plain text body
            c. Run triage (LLM + business rules)
            d. Apply Gmail label (unless dry_run)
            e. Mark as processed in state tracker
        4. Log phase summary

    Phase 2 (Draft):
        1. Filter emails with action=REPLY from Phase 1
        2. For each REPLY email:
            a. Check importance threshold
            b. Check for existing drafts in same thread (dedup)
            c. Generate draft reply via LLM
            d. Create Gmail draft (unless dry_run)
        3. Log phase summary

    Args:
        gmail_client: Gmail API client.
        ollama_client: Ollama API client.
        triage_processor: Triage processor (LLM + business rules).
        draft_processor: Draft processor (LLM draft generation).
        state_tracker: State tracker for processed email IDs.
        config: Pipeline configuration.
    """

    def __init__(
        self,
        gmail_client: GmailClient,
        ollama_client: OllamaClient,
        triage_processor: TriageProcessor,
        draft_processor: DraftProcessor,
        state_tracker: StateTracker,
        config: PipelineConfig,
    ) -> None:
        self._gmail = gmail_client
        self._ollama = ollama_client
        self._triage = triage_processor
        self._draft = draft_processor
        self._state = state_tracker
        self._config = config

    async def run(self) -> dict[str, PhaseSummary]:
        """Run the full two-phase pipeline.

        Returns:
            Dict with "phase1" and "phase2" PhaseSummary objects.
        """
        logger.info("Pipeline starting")

        # Phase 1: Triage
        phase1_summary, phase1_results = await self._run_phase1()

        # Phase 2: Draft
        phase2_summary = await self._run_phase2(phase1_summary, phase1_results)

        logger.info(
            "Pipeline complete",
            phase1=phase1_summary.to_log_fields(),
            phase2=phase2_summary.to_log_fields(),
        )

        return {
            "phase1": phase1_summary,
            "phase2": phase2_summary,
        }

    # -------------------------------------------------------------------------
    # Phase 1: Triage
    # -------------------------------------------------------------------------

    async def _run_phase1(
        self,
    ) -> tuple[PhaseSummary, list[_EmailWithDecision]]:
        """Execute Phase 1: Triage.

        Fetches unread emails, runs triage for each, and applies labels.

        Returns:
            Tuple of (PhaseSummary, list of email+decision pairs for Phase 2).
        """
        summary = PhaseSummary(phase="phase1_triage")

        # Step 1: Fetch unread email IDs
        message_ids = self._gmail.list_unread_emails()
        if not message_ids:
            logger.info("No unread emails found")
            return summary, []

        summary.total = len(message_ids)

        # Batch overflow warning
        max_batch = self._config.settings.agent.max_emails_per_batch
        if len(message_ids) > max_batch:
            logger.warning(
                "Email batch capped at %d (total: %d). Next poll will catch remaining.",
                max_batch,
                len(message_ids),
            )
            message_ids = message_ids[:max_batch]

        # Filter out already-processed emails
        unprocessed: list[str] = []
        for msg_id in message_ids:
            if not self._state.is_processed(msg_id):
                unprocessed.append(msg_id)

        if not unprocessed:
            logger.info("All emails already processed", total=len(message_ids))
            return summary, []

        logger.info(
            "Processing emails",
            total=len(message_ids),
            unprocessed=len(unprocessed),
            already_processed=len(message_ids) - len(unprocessed),
        )

        # Step 2-5: Process each email with per-email error isolation
        triage_results: list[_EmailWithDecision] = []
        action_counts: dict[str, int] = {}
        errors = 0

        for msg_id in unprocessed:
            result = await self._process_email_triage(msg_id)
            triage_results.append(result)

            action_key = result.decision.action.value
            action_counts[action_key] = action_counts.get(action_key, 0) + 1

            if result.had_error:
                errors += 1

        summary.actions = action_counts
        summary.errors = errors

        logger.info(
            "Phase 1 (Triage) complete",
            **summary.to_log_fields(),
        )

        return summary, triage_results

    async def _process_email_triage(self, message_id: str) -> _EmailWithDecision:
        """Process a single email through Phase 1 triage.

        Per-email error isolation: any failure defaults to IGNORE.

        Args:
            message_id: Gmail message ID.

        Returns:
            _EmailWithDecision for this email.
        """
        try:
            # Fetch full email
            raw_email = self._gmail.get_email(message_id)

            # Parse into Email model
            email = self._parse_email(message_id, raw_email)

            # Strip HTML to get plain text body
            body = self._strip_html(email.body) if email.body else ""

            # If body is empty after stripping, skip (don't triage empty emails)
            if not body.strip():
                logger.debug(
                    "Email body empty after HTML strip, skipping",
                    email_id=message_id,
                )
                decision = TriageDecision(
                    action=TriageAction.IGNORE,
                    category="UNCATEGORIZED",
                    confidence=1.0,
                    suspicious_signals=[],
                    reason="Empty body after HTML strip",
                )
                return _EmailWithDecision(email=email, decision=decision)

            # Update email body with stripped version
            email = Email(
                email_id=email.email_id,
                metadata=email.metadata,
                body=body,
                snippet=email.snippet,
                headers=email.headers,
            )

            # Run triage (LLM + business rules)
            decision = await self._triage.run_triage(
                email=email,
                system_prompt=self._config.system_prompt_triage,
            )

            # Apply Gmail label (unless dry_run)
            if not self._config.dry_run:
                await self._apply_label_safe(message_id, decision)

            # Mark as processed in state tracker
            self._state.mark_processed(message_id)

            return _EmailWithDecision(email=email, decision=decision)

        except Exception as exc:
            logger.warning(
                "Triage failed for email, defaulting to IGNORE",
                email_id=message_id,
                error=str(exc),
            )
            # We need a minimal Email for Phase 2 to work with
            # Return a placeholder that Phase 2 will skip due to IGNORE action
            minimal_metadata = EmailMetadata(
                message_id=message_id,
                thread_id="",
                subject="",
                sender="",
                recipient="",
                date=0,
            )
            minimal_email = Email(
                email_id=message_id,
                metadata=minimal_metadata,
            )
            # Default to IGNORE on any failure (per-email isolation)
            decision = TriageDecision(
                action=TriageAction.IGNORE,
                category="UNCATEGORIZED",
                confidence=0.0,
                suspicious_signals=[],
                reason=f"Triage error: {exc}",
            )
            return _EmailWithDecision(email=minimal_email, decision=decision, had_error=True)

    async def _apply_label_safe(
        self,
        message_id: str,
        decision: TriageDecision,
    ) -> None:
        """Apply Gmail label with error handling.

        Errors are logged but do not propagate.

        Args:
            message_id: Gmail message ID.
            decision: TriageDecision with category.
        """
        try:
            label_name = decision.category
            self._gmail.apply_label(message_id, label_name)
        except LabelError as exc:
            logger.warning(
                "Label failed for email",
                email_id=message_id,
                label=decision.category,
                error=str(exc),
            )

    # -------------------------------------------------------------------------
    # Phase 2: Draft
    # -------------------------------------------------------------------------

    async def _run_phase2(
        self,
        phase1_summary: PhaseSummary,
        phase1_results: list[_EmailWithDecision],
    ) -> PhaseSummary:
        """Execute Phase 2: Draft generation.

        For each REPLY email from Phase 1:
            1. Check importance threshold
            2. Check for existing drafts in same thread (dedup)
            3. Generate draft reply
            4. Create Gmail draft (unless dry_run)

        Args:
            phase1_summary: Summary from Phase 1.
            phase1_results: List of email+decision pairs from Phase 1.

        Returns:
            PhaseSummary with draft creation counts.
        """
        summary = PhaseSummary(phase="phase2_draft")
        summary.total = phase1_summary.total

        if not phase1_results:
            return summary

        # Filter for REPLY action only
        reply_emails = [r for r in phase1_results if r.decision.action == TriageAction.REPLY]

        if not reply_emails:
            logger.info("No REPLY emails from Phase 1, skipping draft generation")
            summary.actions = {"no_reply": phase1_summary.total}
            return summary

        logger.info(
            "Phase 2 (Draft) starting",
            reply_emails=len(reply_emails),
        )

        # Track outcomes
        draft_created = 0
        duplicate_skipped = 0
        below_threshold = 0
        draft_errors = 0

        # Importance threshold gate
        threshold = self._config.settings.agent.importance_threshold

        for item in reply_emails:
            email = item.email
            decision = item.decision

            try:
                # Step 1: Importance gate
                importance = self._triage.assess_importance_for_triage(
                    email=email,
                    triage_decision=decision,
                )

                if not self._passes_importance_gate(importance, threshold, email):
                    below_threshold += 1
                    logger.debug(
                        "Email below importance threshold, skipping draft",
                        email_id=email.email_id,
                        importance=importance.value,
                        threshold=threshold,
                    )
                    continue

                # Step 2: Draft deduplication — check existing drafts in thread
                if not self._config.dry_run:
                    existing_drafts = self._gmail.get_drafts_in_thread(email.thread_id)
                    if existing_drafts:
                        duplicate_skipped += 1
                        logger.info(
                            "Draft already exists in thread, skipping",
                            email_id=email.email_id,
                            thread_id=email.thread_id,
                        )
                        continue
                else:
                    # In dry_run, simulate the check
                    logger.debug(
                        "Dry-run: would check for existing drafts",
                        email_id=email.email_id,
                    )

                # Step 3: Generate draft reply
                draft_reply = await self._draft.generate_draft(
                    email=email,
                    triage_decision=decision,
                    system_prompt=self._config.system_prompt_draft,
                )

                # Step 4: Create Gmail draft (unless dry_run)
                if not self._config.dry_run:
                    self._gmail.create_draft(
                        message_id=email.email_id,
                        reply_text=draft_reply.reply_text,
                        thread_id=email.thread_id,
                        to_address=draft_reply.to_address,
                        subject=draft_reply.subject,
                    )
                    draft_created += 1
                    logger.debug(
                        "Draft created",
                        email_id=email.email_id,
                        thread_id=email.thread_id,
                    )
                else:
                    draft_created += 1
                    logger.debug(
                        "Dry-run: would create draft",
                        email_id=email.email_id,
                    )

            except Exception as exc:
                draft_errors += 1
                logger.warning(
                    "Draft generation failed for email",
                    email_id=email.email_id,
                    error=str(exc),
                )

        # Build action summary
        summary.actions = {
            "drafts_created": draft_created,
            "duplicate_skipped": duplicate_skipped,
            "below_threshold": below_threshold,
            "errors": draft_errors,
        }

        logger.info(
            "Phase 2 (Draft) complete",
            **summary.to_log_fields(),
        )

        return summary

    def _passes_importance_gate(
        self,
        importance: ImportanceLevel,
        threshold: str,
        email: Email,
    ) -> bool:
        """Check if email importance passes the configured threshold gate.

        Importance Threshold Gate (PLAN.md §5):
            - low:  All REPLY emails get drafts
            - medium: REPLY + important_senders get drafts
            - high: Only important_senders get drafts

        Args:
            importance: Assessed importance level.
            threshold: Configured importance_threshold.
            email: The email being evaluated.

        Returns:
            True if the email should receive a draft.
        """
        if threshold == "low":
            return True

        if threshold == "medium":
            # medium: allow all REPLY (importance assessment already done)
            return True

        if threshold == "high":
            # high: only important senders get drafts
            important_senders = self._config.settings.agent.important_senders
            return _sender_matches_important(email.sender, important_senders)

        return False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _parse_email(self, message_id: str, raw: dict[str, Any]) -> Email:
        """Parse a raw Gmail message dict into an Email model.

        Args:
            message_id: Gmail message ID.
            raw: Raw message dict from Gmail API.

        Returns:
            Parsed Email object.
        """
        payload = raw.get("payload", {})
        headers = self._extract_headers(payload)
        metadata = EmailMetadata(
            message_id=message_id,
            thread_id=raw.get("threadId", ""),
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            recipient=headers.get("To", ""),
            date=int(raw.get("internalDate", "0")),
        )

        # Extract body (plain text preferred, fallback to HTML)
        body = self._extract_body(payload)

        # Extract snippet
        snippet = raw.get("snippet", "")

        return Email(
            email_id=message_id,
            metadata=metadata,
            body=body,
            snippet=snippet,
            headers=headers,
        )

    def _extract_headers(self, payload: dict[str, Any]) -> dict[str, str]:
        """Extract headers from Gmail message payload.

        Args:
            payload: Message payload dict.

        Returns:
            Dict of header name -> value.
        """
        result: dict[str, str] = {}
        for header in payload.get("headers", []):
            name = header.get("name", "")
            value = header.get("value", "")
            if name:
                result[name] = value
        return result

    def _extract_body(self, payload: dict[str, Any]) -> str:
        """Extract plain text body from Gmail message payload.

        Prefers text/plain part. Falls back to text/html part.
        Returns empty string if neither is available.

        Args:
            payload: Message payload dict.

        Returns:
            Extracted body string (may be empty).
        """
        # Try text/plain first
        body = self._get_part_text(payload, "text/plain")
        if body:
            return body

        # Fall back to text/html
        body = self._get_part_text(payload, "text/html")
        return body if body else ""

    def _get_part_text(self, payload: dict[str, Any], mime_type: str) -> str:
        """Recursively search for a MIME part of the given type.

        Args:
            payload: Message payload dict.
            mime_type: Desired MIME type (e.g., "text/plain").

        Returns:
            Decoded body string or empty string if not found.
        """
        mime = payload.get("mimeType", "")
        if mime == mime_type:
            data = payload.get("body", {}).get("data", "")
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                except Exception:
                    return ""

        # Recurse into parts
        for part in payload.get("parts", []):
            text = self._get_part_text(part, mime_type)
            if text:
                return text

        return ""

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags from a string, leaving plain text.

        Args:
            html: HTML string.

        Returns:
            Plain text with HTML tags removed.
        """
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator=" ", strip=True)
