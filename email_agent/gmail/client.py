"""Gmail API client with quota awareness and retry logic.

Provides read, label, and draft operations with three retry strategies:
- call_gmail_with_retry: transient errors (GmailApiError), exponential backoff + jitter
- call_gmail_quota_retry: rate limit errors (QuotaExceededError), fixed 60s backoff
- Health check: no retry, validates connectivity

See PLAN.md §8 for Gmail API integration details.
See PLAN.md §7 for retry strategy specification.
"""

from __future__ import annotations

import base64
import json
import logging
from email.message import EmailMessage
from typing import Any, NoReturn

import structlog
import tenacity
from googleapiclient.errors import HttpError
from tenacity import (
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    wait_fixed,
)

from email_agent.exceptions.base import (
    GmailApiError,
    QuotaExceededError,
)

logger = structlog.get_logger(__name__)

# HTTP status codes
_RATE_LIMIT_CODE = 429


def _is_transient_gmail_error(exc: BaseException) -> bool:
    """Return True for retryable Gmail API errors (not quota).

    Matches GmailApiError or HttpError that is a 5xx server error,
    but NOT QuotaExceededError (HTTP 429).
    """
    if isinstance(exc, QuotaExceededError):
        return False
    if isinstance(exc, GmailApiError):
        return True
    if isinstance(exc, HttpError):
        return bool(500 <= exc.resp.status < 600)
    return False


call_gmail_with_retry = tenacity.retry(
    retry=retry_if_exception(_is_transient_gmail_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


call_gmail_quota_retry = tenacity.retry(
    retry=retry_if_exception_type(QuotaExceededError),
    stop=stop_after_attempt(3),
    wait=wait_fixed(60),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class GmailClient:
    """Gmail API client with quota awareness and retry logic.

    Provides read, label, and draft operations. All HTTP errors from
    the Gmail API are converted to custom exception types.

    Args:
        service: Authenticated Gmail API service object from GmailAuth.
    """

    def __init__(self, service: Any) -> None:
        self._service = service

    def list_unread_emails(self, after_timestamp: str | None = None) -> list[str]:
        """List unread email message IDs from INBOX.

        Args:
            after_timestamp: RFC 3339 timestamp to filter emails after.
                None means no time filter.

        Returns:
            List of message ID strings.
        """
        query = "is:unread"
        if after_timestamp:
            query = f"is:unread after:{after_timestamp}"

        results: dict[str, Any] = (
            self._service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=100,
            )
            .execute()
        )

        messages: list[dict[str, str]] = results.get("messages", [])
        return [msg["id"] for msg in messages]

    def get_email(self, message_id: str) -> dict[str, Any]:
        """Fetch full email message by ID.

        Args:
            message_id: Gmail message ID.

        Returns:
            Full message dict with payload, headers, threadId, etc.

        Raises:
            GmailApiError: If the API call fails.
        """
        try:
            message: dict[str, Any] = (
                self._service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute()
            )
            return message
        except HttpError as exc:  # pragma: no cover - _handle_http_error always raises
            self._handle_http_error(exc)

    def apply_label(self, message_id: str, label_name: str) -> None:
        """Apply a Gmail label to a message.

        Args:
            message_id: Gmail message ID.
            label_name: Label name to apply.

        Raises:
            LabelError: If label operation fails.
        """
        try:
            self._service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_name]},
            ).execute()
        except HttpError as exc:
            self._handle_http_error(exc)

    def create_draft(
        self,
        message_id: str,
        reply_text: str,
        thread_id: str,
        to_address: str,
        subject: str,
    ) -> str:
        """Create a draft reply in the same thread.

        Args:
            message_id: Original message ID (used for In-Reply-To header).
            reply_text: Plain text body of the draft reply.
            thread_id: Thread ID for the draft.
            to_address: Recipient email address.
            subject: Email subject line.

        Returns:
            Draft ID string.

        Raises:
            GmailApiError: If draft creation fails.
        """
        message = EmailMessage()
        message["To"] = to_address
        message["Subject"] = subject
        message["In-Reply-To"] = message_id
        message["References"] = message_id
        message.set_content(reply_text)
        raw_bytes = message.as_bytes()

        try:
            draft: dict[str, Any] = (
                self._service.users()
                .drafts()
                .create(
                    userId="me",
                    body={
                        "message": {
                            "raw": base64.urlsafe_b64encode(raw_bytes).decode("ascii"),
                            "threadId": thread_id,
                        }
                    },
                )
                .execute()
            )
            return str(draft["id"])
        except HttpError as exc:
            self._handle_http_error(exc)

    def get_drafts_in_thread(self, thread_id: str) -> list[str]:
        """Check for existing drafts in a thread (for deduplication).

        Args:
            thread_id: Gmail thread ID.

        Returns:
            List of draft IDs in this thread.
        """
        try:
            results: dict[str, Any] = (
                self._service.users()
                .drafts()
                .list(
                    userId="me",
                    q=f"thread:{thread_id}",
                )
                .execute()
            )
            drafts: list[dict[str, Any]] = results.get("drafts", [])
            return [d["id"] for d in drafts]
        except HttpError as exc:
            self._handle_http_error(exc)
            raise  # Unreachable: _handle_http_error always raises

    def health_check(self) -> bool:
        """Check Gmail API connectivity.

        Returns True if the API is reachable, False otherwise.
        This method does NOT use retry - it makes a single attempt.

        Returns:
            True if Gmail API responds, False otherwise.
        """
        try:
            self._service.users().getProfile(userId="me").execute()
            return True
        except Exception:
            return False

    def _handle_http_error(self, exc: HttpError) -> NoReturn:
        """Convert HttpError to appropriate custom exception.

        Parses JSON error body to detect rateLimitExceeded for
        QuotaExceededError. All other HTTP errors become GmailApiError.

        Args:
            exc: HttpError from googleapiclient.

        Raises:
            QuotaExceededError: For HTTP 429 rate limit errors.
            GmailApiError: For all other HTTP errors.
        """
        if exc.resp.status == _RATE_LIMIT_CODE:
            reason = self._extract_error_reason(exc)
            logger.warning(
                "Gmail API rate limit exceeded",
                status=exc.resp.status,
                reason=reason,
            )
            msg = f"Gmail API rate limit exceeded: {reason}"
            raise QuotaExceededError(msg) from exc

        msg = f"Gmail API error {exc.resp.status}: {exc.uri} — {exc.error_details}"
        raise GmailApiError(msg) from exc

    def _extract_error_reason(self, exc: HttpError) -> str:
        """Extract reason string from HTTP 429 error body.

        Looks for 'reason' field in JSON error body, e.g.:
        {"error": {"errors": [{"reason": "rateLimitExceeded"}]}}

        Args:
            exc: HttpError with 429 status.

        Returns:
            Reason string or "unknown" if not found.
        """
        try:
            error_body = json.loads(exc.content.decode("utf-8"))
            errors = error_body.get("error", {}).get("errors", [])
            if errors:
                return str(errors[0].get("reason", "unknown"))
        except Exception:
            pass
        return "unknown"
