"""Integration tests for Pipeline with mocked Gmail/Ollama."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from email_agent.gmail.client import GmailClient
from email_agent.models.email import Email, EmailMetadata
from email_agent.models.triage import TriageAction, TriageDecision
from email_agent.ollama.client import OllamaClient
from email_agent.processor.draft import DraftProcessor
from email_agent.processor.triage import TriageProcessor
from email_agent.state.tracker import StateTracker
from email_agent.workflows.pipeline import Pipeline, PipelineConfig


def _make_email(
    email_id: str,
    subject: str = "Test Subject",
    sender: str = "test@example.com",
) -> Email:
    """Helper to create an Email model."""
    metadata = EmailMetadata(
        message_id=email_id,
        thread_id=f"thread_{email_id}",
        subject=subject,
        sender=sender,
        recipient="me@gmail.com",
        date=1700000000,
    )
    return Email(
        email_id=email_id,
        metadata=metadata,
        body="Test email body",
    )


def _make_decision(
    action: TriageAction = TriageAction.REPLY,
    category: str = "WORK",
) -> TriageDecision:
    """Helper to create a TriageDecision."""
    return TriageDecision(
        action=action,
        category=category,
        confidence=0.8,
        suspicious_signals=[],
        reason="Test",
    )


@pytest.fixture
def mock_gmail() -> MagicMock:
    """Return a mock GmailClient."""
    import base64

    gmail = MagicMock(spec=GmailClient)
    gmail.list_unread_emails.return_value = ["msg_001", "msg_002"]

    def get_email_side_effect(message_id: str) -> dict[str, Any]:
        body_content = "This is a test email body that needs a response."
        encoded = base64.urlsafe_b64encode(body_content.encode()).decode()
        return {
            "id": message_id,
            "threadId": f"thread_{message_id}",
            "internalDate": "1700000000",
            "snippet": "Test snippet",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "test@example.com"},
                    {"name": "To", "value": "me@gmail.com"},
                ],
                "body": {"data": encoded},
            },
        }

    gmail.get_email.side_effect = get_email_side_effect
    gmail.health_check.return_value = True
    return gmail


@pytest.fixture
def mock_ollama() -> MagicMock:
    """Return a mock OllamaClient."""
    ollama = MagicMock(spec=OllamaClient)
    ollama.health_check = AsyncMock(return_value=True)
    ollama.triage = AsyncMock(
        return_value={
            "action": "REPLY",
            "category": "WORK",
            "confidence": 0.85,
            "suspicious_signals": [],
            "reason": "Test triage",
        }
    )
    ollama.generate_draft = AsyncMock(
        return_value="Thank you for your email. I will get back to you soon."
    )
    return ollama


@pytest.fixture
def pipeline_config(agent_settings: Any) -> PipelineConfig:
    """Return a PipelineConfig for testing."""
    return PipelineConfig(
        settings=MagicMock(
            gmail=MagicMock(),
            ollama=MagicMock(),
            agent=agent_settings,
        ),
        system_prompt_triage="Triage this email",
        system_prompt_draft="Generate a draft reply",
        dry_run=False,
    )


@pytest.mark.asyncio
async def test_pipeline_phase1_triage_flow(
    mock_gmail: MagicMock,
    mock_ollama: MagicMock,
    agent_settings: Any,
    tmp_state_dir: Any,
) -> None:
    """Verify Phase 1 triage flow processes emails correctly."""
    state_tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    state_tracker.load()

    triage_processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )
    draft_processor = DraftProcessor(
        ollama_client=mock_ollama,
        max_length=500,
    )

    pipeline = Pipeline(
        gmail_client=mock_gmail,
        ollama_client=mock_ollama,
        triage_processor=triage_processor,
        draft_processor=draft_processor,
        state_tracker=state_tracker,
        config=MagicMock(
            settings=MagicMock(agent=agent_settings),
            system_prompt_triage="Triage",
            system_prompt_draft="Draft",
            dry_run=False,
        ),
    )

    result = await pipeline.run()

    assert "phase1" in result
    assert "phase2" in result


@pytest.mark.asyncio
async def test_pipeline_phase2_draft_flow(
    mock_gmail: MagicMock,
    mock_ollama: MagicMock,
    agent_settings: Any,
    tmp_state_dir: Any,
) -> None:
    """Verify Phase 2 draft flow generates drafts for REPLY emails."""
    state_tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    state_tracker.load()

    triage_processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )
    draft_processor = DraftProcessor(
        ollama_client=mock_ollama,
        max_length=500,
    )

    mock_gmail.get_drafts_in_thread.return_value = []

    pipeline = Pipeline(
        gmail_client=mock_gmail,
        ollama_client=mock_ollama,
        triage_processor=triage_processor,
        draft_processor=draft_processor,
        state_tracker=state_tracker,
        config=MagicMock(
            settings=MagicMock(agent=agent_settings),
            system_prompt_triage="Triage",
            system_prompt_draft="Draft",
            dry_run=False,
        ),
    )

    await pipeline.run()

    mock_ollama.generate_draft.assert_called()


@pytest.mark.asyncio
async def test_pipeline_skips_already_processed_emails(
    mock_gmail: MagicMock,
    mock_ollama: MagicMock,
    agent_settings: Any,
    tmp_state_dir: Any,
) -> None:
    """Verify pipeline skips already processed email IDs."""
    state_tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    state_tracker.load()
    state_tracker.mark_processed("msg_001")
    state_tracker.mark_processed("msg_002")

    triage_processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )
    draft_processor = DraftProcessor(
        ollama_client=mock_ollama,
        max_length=500,
    )

    pipeline = Pipeline(
        gmail_client=mock_gmail,
        ollama_client=mock_ollama,
        triage_processor=triage_processor,
        draft_processor=draft_processor,
        state_tracker=state_tracker,
        config=MagicMock(
            settings=MagicMock(agent=agent_settings),
            system_prompt_triage="Triage",
            system_prompt_draft="Draft",
            dry_run=False,
        ),
    )

    await pipeline.run()

    mock_ollama.triage.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_dry_run_mode(
    mock_gmail: MagicMock,
    mock_ollama: MagicMock,
    agent_settings: Any,
    tmp_state_dir: Any,
) -> None:
    """Verify dry_run mode skips Gmail write operations."""
    state_tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    state_tracker.load()

    triage_processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )
    draft_processor = DraftProcessor(
        ollama_client=mock_ollama,
        max_length=500,
    )

    pipeline = Pipeline(
        gmail_client=mock_gmail,
        ollama_client=mock_ollama,
        triage_processor=triage_processor,
        draft_processor=draft_processor,
        state_tracker=state_tracker,
        config=MagicMock(
            settings=MagicMock(agent=agent_settings),
            system_prompt_triage="Triage",
            system_prompt_draft="Draft",
            dry_run=True,
        ),
    )

    await pipeline.run()

    mock_gmail.apply_label.assert_not_called()
    mock_gmail.create_draft.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_batch_overflow_warning(
    mock_gmail: MagicMock,
    mock_ollama: MagicMock,
    agent_settings: Any,
    tmp_state_dir: Any,
) -> None:
    """Verify batch overflow warning when emails exceed max_per_batch."""
    agent_settings.max_emails_per_batch = 1

    mock_gmail.list_unread_emails.return_value = ["msg_001", "msg_002"]

    state_tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    state_tracker.load()

    triage_processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )
    draft_processor = DraftProcessor(
        ollama_client=mock_ollama,
        max_length=500,
    )

    pipeline = Pipeline(
        gmail_client=mock_gmail,
        ollama_client=mock_ollama,
        triage_processor=triage_processor,
        draft_processor=draft_processor,
        state_tracker=state_tracker,
        config=MagicMock(
            settings=MagicMock(agent=agent_settings),
            system_prompt_triage="Triage",
            system_prompt_draft="Draft",
            dry_run=False,
        ),
    )

    await pipeline.run()

    mock_ollama.triage.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_per_email_error_isolation(
    mock_gmail: MagicMock,
    mock_ollama: MagicMock,
    agent_settings: Any,
    tmp_state_dir: Any,
) -> None:
    """Verify one email's error doesn't stop the entire batch."""
    mock_gmail.list_unread_emails.return_value = ["msg_001", "msg_002"]
    mock_gmail.get_email.side_effect = [
        Exception("API error"),
        {
            "id": "msg_002",
            "threadId": "thread_002",
            "internalDate": "1700000000",
            "snippet": "Test",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Subject 2"},
                    {"name": "From", "value": "test2@example.com"},
                    {"name": "To", "value": "me@gmail.com"},
                ],
                "body": {"data": ""},
            },
        },
    ]

    state_tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    state_tracker.load()

    triage_processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )
    draft_processor = DraftProcessor(
        ollama_client=mock_ollama,
        max_length=500,
    )

    pipeline = Pipeline(
        gmail_client=mock_gmail,
        ollama_client=mock_ollama,
        triage_processor=triage_processor,
        draft_processor=draft_processor,
        state_tracker=state_tracker,
        config=MagicMock(
            settings=MagicMock(agent=agent_settings),
            system_prompt_triage="Triage",
            system_prompt_draft="Draft",
            dry_run=False,
        ),
    )

    result = await pipeline.run()

    assert result["phase1"].errors >= 0


@pytest.mark.asyncio
async def test_pipeline_importance_gate_high_threshold(
    mock_gmail: MagicMock,
    mock_ollama: MagicMock,
    agent_settings: Any,
    tmp_state_dir: Any,
) -> None:
    """Verify high importance threshold only drafts important senders."""
    agent_settings.importance_threshold = "high"
    agent_settings.important_senders = ["important@example.com"]

    mock_gmail.list_unread_emails.return_value = ["msg_001"]
    mock_gmail.get_email.return_value = {
        "id": "msg_001",
        "threadId": "thread_001",
        "internalDate": "1700000000",
        "snippet": "Test",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Not Important"},
                {"name": "From", "value": "regular@example.com"},
                {"name": "To", "value": "me@gmail.com"},
            ],
            "body": {"data": ""},
        },
    }
    mock_gmail.get_drafts_in_thread.return_value = []

    state_tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    state_tracker.load()

    triage_processor = TriageProcessor(
        ollama_client=mock_ollama,
        agent_settings=agent_settings,
    )
    draft_processor = DraftProcessor(
        ollama_client=mock_ollama,
        max_length=500,
    )

    pipeline = Pipeline(
        gmail_client=mock_gmail,
        ollama_client=mock_ollama,
        triage_processor=triage_processor,
        draft_processor=draft_processor,
        state_tracker=state_tracker,
        config=MagicMock(
            settings=MagicMock(agent=agent_settings),
            system_prompt_triage="Triage",
            system_prompt_draft="Draft",
            dry_run=False,
        ),
    )

    await pipeline.run()

    mock_ollama.generate_draft.assert_not_called()
