"""Ollama API client with function calling, retry logic, and circuit breaker.

Provides LLM-based email triage and draft generation using Ollama's
function calling (tool use) API. Wraps all calls with tenacity retry
and circuit breaker protection.

Retry Strategy:
    - OllamaTimeoutError: 3 retries, exponential backoff + jitter (max 10s)
    - See PLAN.md §7 for full retry strategy table.

Circuit Breaker:
    - Integrated via CircuitBreaker class in circuit_breaker.py
    - Prevents cascade failures when Ollama is unavailable
    - Health check at startup always runs (unaffected by circuit state)

See PLAN.md §6 for Ollama function calling specification.
See PLAN.md §7 for retry and circuit breaker details.
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

import httpx
import structlog
import tenacity
from tenacity import (
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from email_agent.config.settings import OllamaSettings
from email_agent.exceptions.base import (
    OllamaConnectionError,
    OllamaTimeoutError,
)
from email_agent.ollama.circuit_breaker import CircuitBreaker

logger = structlog.get_logger(__name__)

TIMEOUT_MSG = "Request to Ollama timed out"


call_ollama_with_retry = tenacity.retry(
    retry=retry_if_exception_type(OllamaTimeoutError),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class OllamaClient:
    """Ollama API client with function calling and circuit breaker.

    Provides email triage and draft generation via Ollama's tool-use API.
    All LLM calls are protected by the circuit breaker and use tenacity retry.

    Args:
        settings: Ollama configuration (base_url, model, timeout).
        circuit_breaker: Circuit breaker instance for fault protection.
    """

    def __init__(
        self,
        settings: OllamaSettings,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        self._settings = settings
        self._cb = circuit_breaker
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create and return the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.base_url,
                timeout=httpx.Timeout(self._settings.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """Check Ollama API connectivity.

        This method ALWAYS runs regardless of circuit breaker state.
        It is used at startup to verify Ollama is available before
        entering the main loop.

        Returns:
            True if Ollama responds to /api/tags, False otherwise.
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception as exc:
            logger.error("Ollama health check failed", error=str(exc))
            return False

    async def triage(
        self,
        email_body: str,
        email_subject: str,
        email_from: str,
        categories: list[str],
        system_prompt: str,
    ) -> dict[str, Any]:
        """Classify an email using Ollama function calling.

        Calls the Ollama /api/chat endpoint with a triage tool definition.
        The model returns a structured response via tool_calls.

        Args:
            email_body: Stripped plain-text email body.
            email_subject: Email subject line.
            email_from: Sender email address.
            categories: Configured category list (injected into tool enum).
            system_prompt: System prompt for triage instructions.

        Returns:
            Dict with keys: action, category, confidence, suspicious_signals, reason.

        Raises:
            OllamaConnectionError: If circuit is OPEN or call fails.
            OllamaTimeoutError: If request times out (retried by tenacity).
        """
        if not self._cb.allow_request():
            logger.warning(
                "Circuit breaker OPEN: skipping Ollama triage call",
                state=self._cb.state.value,
            )
            raise OllamaConnectionError("Circuit breaker is OPEN; Ollama calls are blocked")

        tool_definition = self._build_triage_tool(categories)
        payload = self._build_triage_payload(
            email_body=email_body,
            email_subject=email_subject,
            email_from=email_from,
            system_prompt=system_prompt,
            tool=tool_definition,
        )

        try:
            result = await self._call_with_circuit_break(payload)
            self._cb.record_success()
            return cast(dict[str, Any], result)
        except Exception:
            self._cb.record_failure()
            raise

    async def generate_draft(
        self,
        email_body: str,
        email_subject: str,
        email_from: str,
        system_prompt: str,
        max_length: int,
    ) -> str:
        """Generate a draft reply using Ollama.

        Args:
            email_body: Stripped plain-text original email body.
            email_subject: Original email subject.
            email_from: Sender email address.
            system_prompt: System prompt for draft generation.
            max_length: Maximum characters for the draft reply.

        Returns:
            Generated draft reply text.

        Raises:
            OllamaConnectionError: If circuit is OPEN or call fails.
            OllamaTimeoutError: If request times out.
        """
        if not self._cb.allow_request():
            logger.warning(
                "Circuit breaker OPEN: skipping Ollama draft call",
                state=self._cb.state.value,
            )
            raise OllamaConnectionError("Circuit breaker is OPEN; Ollama calls are blocked")

        payload = self._build_draft_payload(
            email_body=email_body,
            email_subject=email_subject,
            email_from=email_from,
            system_prompt=system_prompt,
            max_length=max_length,
        )

        try:
            result = await self._call_with_circuit_break(payload)
            self._cb.record_success()
            return cast(str, result)
        except Exception:
            self._cb.record_failure()
            raise

    async def _call_with_circuit_break(self, payload: dict[str, Any]) -> Any:
        """Execute an Ollama API call with circuit breaker protection.

        Wraps the HTTP call in the tenacity retry decorator and records
        success/failure in the circuit breaker.

        Args:
            payload: JSON-serializable request body for Ollama /api/chat.

        Returns:
            Parsed response data from Ollama.

        Raises:
            OllamaTimeoutError: If request times out (retried by tenacity).
            OllamaConnectionError: If HTTP call fails.
        """
        wrapped = call_ollama_with_retry(self._raw_chat)
        return await wrapped(payload)

    async def _raw_chat(self, payload: dict[str, Any]) -> Any:
        """Raw HTTP call to Ollama /api/chat endpoint.

        This method is wrapped by tenacity retry in _call_with_circuit_break.
        It raises OllamaTimeoutError on timeout and OllamaConnectionError on
        connection failures.

        Args:
            payload: Request body for /api/chat.

        Returns:
            Response data from Ollama (tool_calls or content).
        """
        client = await self._get_client()
        try:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(TIMEOUT_MSG) from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaConnectionError(
                f"Ollama returned {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaConnectionError(f"Ollama connection failed: {exc}") from exc

        return self._parse_response(data)

    def _build_triage_tool(self, categories: list[str]) -> dict[str, Any]:
        """Build the triage function calling tool definition.

        Args:
            categories: Dynamic category list from config.

        Returns:
            Ollama tool definition dict.
        """
        return {
            "type": "function",
            "function": {
                "name": "triage_email",
                "description": "Classify an email and decide action",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["IGNORE", "REPLY", "SUSPICIOUS"],
                            "description": "What to do with this email",
                        },
                        "category": {
                            "type": "string",
                            "enum": categories,
                            "description": ("Email category from configured categories list"),
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence in classification",
                        },
                        "suspicious_signals": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Risk indicators if SUSPICIOUS",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation",
                        },
                    },
                    "required": ["action", "category", "confidence", "reason"],
                },
            },
        }

    def _build_triage_payload(
        self,
        email_body: str,
        email_subject: str,
        email_from: str,
        system_prompt: str,
        tool: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the Ollama /api/chat request body for triage.

        Args:
            email_body: Stripped email body.
            email_subject: Email subject.
            email_from: Sender email.
            system_prompt: Triage instructions.
            tool: Tool definition from _build_triage_tool.

        Returns:
            Request body dict for /api/chat.
        """
        truncated_body = email_body[:2000] if email_body else ""
        truncated_subject = email_subject[:500] if email_subject else ""
        return {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"From: {email_from}\n"
                        f"Subject: {truncated_subject}\n\n"
                        f"Body:\n{truncated_body}"
                    ),
                },
            ],
            "tools": [tool],
            "stream": False,
        }

    def _build_draft_payload(
        self,
        email_body: str,
        email_subject: str,
        email_from: str,
        system_prompt: str,
        max_length: int,
    ) -> dict[str, Any]:
        """Build the Ollama /api/chat request body for draft generation.

        Args:
            email_body: Stripped email body.
            email_subject: Email subject.
            email_from: Sender email.
            system_prompt: Draft generation instructions.
            max_length: Maximum draft length in characters.

        Returns:
            Request body dict for /api/chat.
        """
        truncated_body = email_body[:2000] if email_body else ""
        truncated_subject = email_subject[:500] if email_subject else ""
        return {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"From: {email_from}\n"
                        f"Subject: {truncated_subject}\n\n"
                        f"Body:\n{truncated_body}\n\n"
                        f"[Generate a draft reply in {max_length} characters or less]"
                    ),
                },
            ],
            "stream": False,
        }

    def _parse_response(self, data: dict[str, Any]) -> Any:
        """Parse Ollama /api/chat response.

        Extracts tool_call content from model response if available,
        otherwise returns the plain text content.

        Args:
            data: Raw JSON response from /api/chat.

        Returns:
            Tool call arguments dict, or content string, or raw data.
        """
        message = data.get("message", {})
        tool_calls = message.get("tool_calls")
        if tool_calls:
            first_call = tool_calls[0]
            function = first_call.get("function", {})
            arguments_str = function.get("arguments", "{}")

            try:
                return json.loads(arguments_str)
            except json.JSONDecodeError:
                return {"content": arguments_str}
        return message.get("content", "")
