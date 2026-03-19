"""LLM triage with business rules override layer.

Combines Ollama LLM function calling with deterministic business rules
that override the LLM decision in specific, well-defined scenarios.

Business Rules Override Layer (post-LLM deterministic corrections):
    1. Phishing override: Detects urgent language + suspicious links → SUSPICIOUS
    2. Travel itinerary override: Detects travel confirmations with no reply request → IGNORE
    3. Low-confidence downgrade: Low-confidence SUSPICIOUS without strong signals → IGNORE

Also assesses importance via processor/importance.py for draft gating.

See PLAN.md §6 for full business rules specification.
See PLAN.md §5 for importance threshold gate details.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from email_agent.exceptions.base import TriageError
from email_agent.models.email import Email
from email_agent.models.importance import ImportanceLevel
from email_agent.models.triage import TriageAction, TriageDecision
from email_agent.ollama.client import OllamaClient
from email_agent.processor.importance import assess_importance

if TYPE_CHECKING:
    from email_agent.config.settings import AgentSettings

logger = structlog.get_logger(__name__)

# Phishing detection patterns
_PHISHING_SUBJECT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"password\s*reset", re.IGNORECASE),
    re.compile(r"account\s*(will\s*)?(be\s*)?(closed?|suspended|locked)", re.IGNORECASE),
    re.compile(r"verify\s*(your)?\s*(account|identity|information)", re.IGNORECASE),
    re.compile(r"unusual\s*(sign[ -]?in|activity|login)", re.IGNORECASE),
    re.compile(r"confirm\s*(your)?\s*(identity|account|information)", re.IGNORECASE),
    re.compile(r"security\s*(alert|warning|notice|notification)", re.IGNORECASE),
    re.compile(r"urgent\s*action\s*required", re.IGNORECASE),
]

_PHISHING_BODY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"https?://[^\s]*?(bit\.ly|tinyurl|t\.co|goo\.gl|is\.gd|buff\.ly)[^\s]*", re.IGNORECASE
    ),
    re.compile(r"click\s*(here|on|the\s*(link|button|url))\s*(to|and|for)", re.IGNORECASE),
    re.compile(
        r"enter\s*(your\s*)?(password|credential|login|account)\s*(now|immediately|urgent)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(verify|confirm|update)\s*(your\s*)?(account|information|details)\s*(within|before|now)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(compromised?|unauthorized|fraud|scam)\b", re.IGNORECASE),
]

# Travel itinerary patterns
_TRAVEL_KEYWORDS: list[str] = [
    "flight confirmation",
    "hotel reservation",
    "booking confirmation",
    "trip details",
    "travel itinerary",
    "flight number",
    "boarding pass",
    "car rental",
    "rental car",
]

_TRAVEL_REPLY_REQUEST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"please\s+confirm|please\s+reply|rsvp|will\s+you\s+attend", re.IGNORECASE),
    re.compile(r"respond\s+(by|to|if)|let\s+us\s+know\s+(if|by)", re.IGNORECASE),
]


def _has_phishing_subject(subject: str) -> bool:
    """Check if subject contains phishing indicators."""
    return any(p.search(subject) for p in _PHISHING_SUBJECT_PATTERNS)


def _has_phishing_body(body: str) -> bool:
    """Check if body contains phishing indicators."""
    if not body:
        return False
    return sum(1 for p in _PHISHING_BODY_PATTERNS if p.search(body)) >= 2


def _has_suspicious_links(body: str) -> bool:
    """Check if body contains shortened or suspicious URLs."""
    if not body:
        return False
    return bool(
        re.search(
            r"https?://[^\s]*?(bit\.ly|tinyurl|t\.co|goo\.gl|is\.gd|buff\.ly)[^\s]*",
            body,
            re.IGNORECASE,
        )
    )


def _matches_travel_pattern(subject: str, body: str) -> bool:
    """Check if email matches a travel itinerary pattern."""
    combined = f"{subject} {body}".lower()
    return sum(1 for kw in _TRAVEL_KEYWORDS if kw in combined) >= 2


def _has_reply_request(subject: str, body: str) -> bool:
    """Check if email explicitly requests a reply or response."""
    combined = f"{subject} {body}"
    return any(p.search(combined) for p in _TRAVEL_REPLY_REQUEST_PATTERNS)


def _apply_phishing_override(
    decision: TriageDecision,
    email: Email,
) -> TriageDecision:
    """Apply phishing detection override.

    If email shows phishing indicators, override to SUSPICIOUS with
    phishing signals regardless of the LLM decision.
    """
    is_phishing_subject = _has_phishing_subject(email.subject)
    is_phishing_body = _has_phishing_body(email.body)
    has_suspicious_links = _has_suspicious_links(email.body)

    if is_phishing_subject or is_phishing_body or has_suspicious_links:
        signals = []
        if is_phishing_subject:
            signals.append("phishing_subject_keyword")
        if is_phishing_body:
            signals.append("phishing_body_content")
        if has_suspicious_links:
            signals.append("shortened_url")

        logger.warning(
            "Phishing override applied",
            email_id=email.email_id,
            phishing_subject=is_phishing_subject,
            phishing_body=is_phishing_body,
            suspicious_links=has_suspicious_links,
        )

        return TriageDecision(
            action=TriageAction.SUSPICIOUS,
            category="SECURITY_ADMIN",
            confidence=1.0,
            suspicious_signals=signals,
            reason=f"Override: phishing detected. {decision.reason}",
        )

    return decision


def _apply_travel_override(
    decision: TriageDecision,
    email: Email,
) -> TriageDecision:
    """Apply travel itinerary override.

    If email matches a travel pattern without a reply request,
    downgrade to IGNORE (automated notification, no action needed).
    """
    if decision.action != TriageAction.REPLY:
        return decision

    is_travel = _matches_travel_pattern(email.subject, email.body)
    has_request = _has_reply_request(email.subject, email.body)

    if is_travel and not has_request:
        logger.info(
            "Travel itinerary override applied",
            email_id=email.email_id,
        )
        return TriageDecision(
            action=TriageAction.IGNORE,
            category=decision.category,
            confidence=decision.confidence,
            suspicious_signals=[],
            reason=f"Override: travel itinerary (no reply requested). {decision.reason}",
        )

    return decision


def _apply_low_confidence_downgrade(
    decision: TriageDecision,
    email_id: str,
) -> TriageDecision:
    """Apply low-confidence downgrade for SUSPICIOUS decisions.

    If a SUSPICIOUS decision has low confidence and few signals,
    downgrade to IGNORE. Never promote to REPLY — too risky.

    Args:
        decision: The current triage decision.
        email_id: Email ID for logging.
    """
    if decision.action != TriageAction.SUSPICIOUS:
        return decision

    if decision.confidence < 0.5 and len(decision.suspicious_signals) < 2:
        logger.info(
            "Low-confidence SUSPICIOUS downgraded to IGNORE",
            email_id=email_id,
            confidence=decision.confidence,
            signals_count=len(decision.suspicious_signals),
        )
        return TriageDecision(
            action=TriageAction.IGNORE,
            category=decision.category,
            confidence=decision.confidence,
            suspicious_signals=decision.suspicious_signals,
            reason=f"Override: low-confidence suspicious downgraded. {decision.reason}",
        )

    return decision


class TriageProcessor:
    """Email triage processor combining LLM classification with business rules.

    Orchestrates the full triage flow:
        1. Call Ollama for LLM classification (via OllamaClient.triage)
        2. Validate and parse LLM response into TriageDecision
        3. Apply business rules override layer (phishing, travel, low-confidence)
        4. Assess importance for draft gating

    Args:
        ollama_client: Ollama API client for LLM calls.
        agent_settings: Agent configuration (categories, important_senders, etc.).
    """

    def __init__(
        self,
        ollama_client: OllamaClient,
        agent_settings: AgentSettings,
    ) -> None:
        self._ollama = ollama_client
        self._settings = agent_settings

    async def run_triage(
        self,
        email: Email,
        system_prompt: str,
    ) -> TriageDecision:
        """Run full triage pipeline on a single email.

        1. Strip HTML (already done by pipeline, body is plain text)
        2. Call Ollama LLM for classification
        3. Apply business rules override layer
        4. Assess importance for draft gating

        Args:
            email: The email to triage (body already stripped of HTML).
            system_prompt: System prompt for the Ollama triage model.

        Returns:
            TriageDecision with action, category, confidence, signals, and reason.

        Raises:
            TriageError: If LLM call fails or response is unparseable.
        """
        email_id = email.email_id
        logger.debug("Starting triage", email_id=email_id)

        # Step 1: Call LLM
        try:
            raw_result = await self._ollama.triage(
                email_body=email.body,
                email_subject=email.subject,
                email_from=email.sender,
                categories=self._settings.categories,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            raise TriageError(
                f"LLM triage failed for {email_id}",
            ) from exc

        # Step 2: Validate LLM response into TriageDecision
        try:
            decision = TriageDecision.model_validate(raw_result)
        except Exception as exc:
            raise TriageError(
                f"Invalid triage response for {email_id}: {exc}",
            ) from exc

        # Step 3: Validate category is in config (defensive)
        if decision.category not in self._settings.categories:
            logger.warning(
                "LLM returned unknown category, using UNCATEGORIZED",
                email_id=email_id,
                returned_category=decision.category,
                allowed_categories=self._settings.categories,
            )
            # Create new decision with valid category (preserve action/reason)
            decision = TriageDecision(
                action=decision.action,
                category="UNCATEGORIZED",
                confidence=decision.confidence,
                suspicious_signals=decision.suspicious_signals,
                reason=decision.reason,
            )

        # Step 4: Apply business rules override layer
        decision = _apply_phishing_override(decision, email)
        decision = _apply_travel_override(decision, email)
        decision = _apply_low_confidence_downgrade(decision, email_id)

        logger.debug(
            "Triage complete",
            email_id=email_id,
            action=decision.action.value,
            category=decision.category,
            confidence=decision.confidence,
        )

        return decision

    def assess_importance_for_triage(
        self,
        email: Email,
        triage_decision: TriageDecision,
    ) -> ImportanceLevel:
        """Assess importance level for an email after triage.

        Called by the pipeline to determine if a REPLY decision
        should result in draft creation, based on importance_threshold.

        Args:
            email: The triaged email.
            triage_decision: The triage decision from run_triage.

        Returns:
            ImportanceLevel for draft gating in Phase 2.
        """
        return assess_importance(
            email=email,
            important_senders=self._settings.important_senders,
            llm_confidence=triage_decision.confidence,
        )
