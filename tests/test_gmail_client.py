"""Tests for GmailClient."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from email_agent.exceptions.base import GmailApiError, QuotaExceededError
from email_agent.gmail.client import GmailClient


@pytest.fixture
def gmail_client(mock_gmail_service: MagicMock) -> GmailClient:
    """Return a GmailClient with mocked service."""
    return GmailClient(service=mock_gmail_service)


def test_list_unread_emails_returns_message_ids(gmail_client: GmailClient) -> None:
    """Verify list_unread_emails returns message ID list."""
    mock_gmail_service = gmail_client._service
    mock_gmail_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg_001"}, {"id": "msg_002"}],
    }

    result = gmail_client.list_unread_emails()

    assert result == ["msg_001", "msg_002"]
    mock_gmail_service.users.return_value.messages.return_value.list.assert_called_once()


def test_get_email_returns_message_dict(gmail_client: GmailClient) -> None:
    """Verify get_email returns full message dict."""
    mock_gmail_service = gmail_client._service
    expected_message = {
        "id": "msg_001",
        "threadId": "thread_001",
        "payload": {},
    }
    mock_gmail_service.users.return_value.messages.return_value.get.return_value.execute.return_value = expected_message

    result = gmail_client.get_email("msg_001")

    assert result == expected_message


def test_apply_label_calls_modify(gmail_client: GmailClient) -> None:
    """Verify apply_label calls modify API."""
    mock_gmail_service = gmail_client._service
    mock_gmail_service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}

    gmail_client.apply_label("msg_001", "WORK")

    mock_gmail_service.users.return_value.messages.return_value.modify.assert_called_once_with(
        userId="me",
        id="msg_001",
        body={"addLabelIds": ["WORK"]},
    )


def test_create_draft_returns_draft_id(gmail_client: GmailClient) -> None:
    """Verify create_draft returns draft ID."""
    mock_gmail_service = gmail_client._service
    mock_gmail_service.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
        "id": "draft_001",
    }

    draft_id = gmail_client.create_draft(
        message_id="msg_001",
        reply_text="Thanks for your email.",
        thread_id="thread_001",
        to_address="sender@example.com",
        subject="Re: Meeting",
    )

    assert draft_id == "draft_001"


def test_get_drafts_in_thread_returns_draft_ids(gmail_client: GmailClient) -> None:
    """Verify get_drafts_in_thread returns draft ID list."""
    mock_gmail_service = gmail_client._service
    mock_gmail_service.users.return_value.drafts.return_value.list.return_value.execute.return_value = {
        "drafts": [{"id": "draft_001"}, {"id": "draft_002"}],
    }

    result = gmail_client.get_drafts_in_thread("thread_001")

    assert result == ["draft_001", "draft_002"]


def test_health_check_returns_true_on_success(gmail_client: GmailClient) -> None:
    """Verify health_check returns True when API responds."""
    mock_gmail_service = gmail_client._service
    mock_gmail_service.users.return_value.getProfile.return_value.execute.return_value = {
        "emailAddress": "me@gmail.com"
    }

    result = gmail_client.health_check()

    assert result is True


def test_health_check_returns_false_on_error(gmail_client: GmailClient) -> None:
    """Verify health_check returns False on error."""
    mock_gmail_service = gmail_client._service
    mock_gmail_service.users.return_value.getProfile.return_value.execute.side_effect = Exception(
        "API error"
    )

    result = gmail_client.health_check()

    assert result is False


def test_quota_exceeded_error_raised_on_429(gmail_client: GmailClient) -> None:
    """Verify QuotaExceededError is raised on HTTP 429."""
    mock_gmail_service = gmail_client._service

    mock_resp = MagicMock()
    mock_resp.status = 429
    mock_resp.uri = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    mock_resp.error_details = "rateLimitExceeded"
    mock_resp.content = b'{"error": {"errors": [{"reason": "rateLimitExceeded"}]}}'

    http_error = HttpError(mock_resp, b"rate limit exceeded")

    mock_gmail_service.users.return_value.messages.return_value.get.return_value.execute.side_effect = http_error

    with pytest.raises(QuotaExceededError) as exc_info:
        gmail_client.get_email("msg_001")

    assert "rate limit exceeded" in str(exc_info.value).lower()


def test_gmail_api_error_raised_on_5xx(gmail_client: GmailClient) -> None:
    """Verify GmailApiError is raised on HTTP 5xx."""
    mock_gmail_service = gmail_client._service

    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.uri = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    mock_resp.error_details = "internal error"

    http_error = HttpError(mock_resp, b"internal error")

    mock_gmail_service.users.return_value.messages.return_value.get.return_value.execute.side_effect = http_error

    with pytest.raises(GmailApiError) as exc_info:
        gmail_client.get_email("msg_001")

    assert "500" in str(exc_info.value)
