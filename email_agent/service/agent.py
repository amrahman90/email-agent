"""Dependency injection container for email-agent services.

AgentContainer builds and holds all service instances:
    - GmailAuth + GmailClient for Gmail API
    - CircuitBreaker + OllamaClient for Ollama LLM
    - TriageProcessor + DraftProcessor for business logic
    - StateTracker for state persistence

Provides a cleanup method for async resource teardown.

This is NOT the main orchestrator — that role belongs to workflows/pipeline.py.
This container only manages instance creation and lifecycle.

See PLAN.md §9 for dependency injection specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from email_agent.config.settings import Settings
from email_agent.gmail.auth import GmailAuth
from email_agent.gmail.client import GmailClient
from email_agent.ollama.circuit_breaker import CircuitBreaker
from email_agent.ollama.client import OllamaClient
from email_agent.processor.draft import DraftProcessor
from email_agent.processor.triage import TriageProcessor
from email_agent.state.tracker import StateTracker
from email_agent.workflows.pipeline import Pipeline, PipelineConfig

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class PipelineRunResult:
    """Result of a single pipeline run."""

    phase1: dict[str, Any]
    phase2: dict[str, Any]


class AgentContainer:
    """Dependency injection container for email-agent.

    Builds and holds all service instances. Call cleanup() to
    properly teardown async resources (httpx client).

    Args:
        settings: Application settings.

    Example:
        container = AgentContainer(settings)
        await container.initialize()

        # Use container.pipeline to run the agent
        results = await container.pipeline.run()

        # Cleanup when done
        await container.cleanup()
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        # Lazily created services
        self._gmail_auth: GmailAuth | None = None
        self._gmail_client: GmailClient | None = None
        self._circuit_breaker: CircuitBreaker | None = None
        self._ollama_client: OllamaClient | None = None
        self._triage_processor: TriageProcessor | None = None
        self._draft_processor: DraftProcessor | None = None
        self._state_tracker: StateTracker | None = None
        self._pipeline: Pipeline | None = None

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all services (OAuth2, build clients, etc.).

        Must be called before using the pipeline. Safe to call multiple times
        (subsequent calls are no-ops).

        Raises:
            GmailAuthError: If OAuth2 authentication fails.
            OllamaConnectionError: If Ollama health check fails.
        """
        if self._initialized:
            return

        logger.info("Initializing AgentContainer")

        # Gmail authentication and client
        self._gmail_auth = GmailAuth(self._settings.gmail)
        credentials = self._gmail_auth.get_credentials()
        gmail_service = self._gmail_auth.build_service(credentials)
        self._gmail_client = GmailClient(gmail_service)

        # Ollama circuit breaker and client
        self._circuit_breaker = CircuitBreaker()
        self._ollama_client = OllamaClient(
            settings=self._settings.ollama,
            circuit_breaker=self._circuit_breaker,
        )

        # Processors
        self._triage_processor = TriageProcessor(
            ollama_client=self._ollama_client,
            agent_settings=self._settings.agent,
        )
        self._draft_processor = DraftProcessor(
            ollama_client=self._ollama_client,
            max_length=self._settings.agent.draft_reply_max_length,
        )

        # State tracker — load, prune, enforce limits, but don't use
        # context manager (we manage save explicitly in cleanup())
        state_dir = Path("state")
        tracker = StateTracker(
            state_dir=state_dir,
            email_age_limit_days=self._settings.agent.email_age_limit_days,
        )
        tracker.load()
        tracker.prune()
        tracker.enforce_max_ids()
        self._state_tracker = tracker

        # Pipeline config — system prompts come from config loader (Phase 5)
        # For now, use minimal prompts; Phase 5 will inject real prompts
        triage_prompt = "You are an email triage assistant."
        draft_prompt = "You are an email drafting assistant."

        self._pipeline = Pipeline(
            gmail_client=self._gmail_client,
            ollama_client=self._ollama_client,
            triage_processor=self._triage_processor,
            draft_processor=self._draft_processor,
            state_tracker=tracker,
            config=PipelineConfig(
                settings=self._settings,
                system_prompt_triage=triage_prompt,
                system_prompt_draft=draft_prompt,
                dry_run=False,
            ),
        )

        self._initialized = True
        logger.info("AgentContainer initialized")

    @property
    def pipeline(self) -> Pipeline:
        """Return the initialized pipeline.

        Returns:
            The Pipeline instance.

        Raises:
            RuntimeError: If initialize() has not been called.
        """
        if not self._initialized or self._pipeline is None:
            raise RuntimeError("AgentContainer not initialized. Call initialize() first.")
        return self._pipeline

    @property
    def gmail_client(self) -> GmailClient:
        """Return the Gmail client.

        Returns:
            The GmailClient instance.
        """
        if self._gmail_client is None:
            raise RuntimeError("AgentContainer not initialized.")
        return self._gmail_client

    @property
    def ollama_client(self) -> OllamaClient:
        """Return the Ollama client.

        Returns:
            The OllamaClient instance.
        """
        if self._ollama_client is None:
            raise RuntimeError("AgentContainer not initialized.")
        return self._ollama_client

    @property
    def state_tracker(self) -> StateTracker:
        """Return the state tracker.

        Returns:
            The StateTracker instance.
        """
        if self._state_tracker is None:
            raise RuntimeError("AgentContainer not initialized.")
        return self._state_tracker

    async def cleanup(self) -> None:
        """Clean up async resources (httpx client connections).

        Call this when shutting down the agent.
        Safe to call multiple times.
        """
        logger.info("AgentContainer cleanup")

        if self._ollama_client is not None:
            await self._ollama_client.close()

        if self._state_tracker is not None:
            self._state_tracker.save()

        logger.info("AgentContainer cleanup complete")

    async def run_once(self) -> PipelineRunResult:
        """Run a single pipeline cycle.

        Convenience method that initializes (if needed) and runs
        one complete pipeline cycle.

        Returns:
            PipelineRunResult with phase summaries from the pipeline run.
        """
        if not self._initialized:
            await self.initialize()

        results = await self.pipeline.run()
        return PipelineRunResult(
            phase1=results["phase1"].to_log_fields(),
            phase2=results["phase2"].to_log_fields(),
        )
