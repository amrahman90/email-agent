"""Ollama circuit breaker state machine.

Prevents cascade failures when Ollama is unavailable. Wraps Ollama calls
in a three-state machine (CLOSED → OPEN → HALF-OPEN → CLOSED).

Parameters:
    - failure_threshold: 5 consecutive failures → OPEN
    - open_duration: 60 seconds before HALF-OPEN
    - half_open_max_calls: 1 test call allowed in HALF-OPEN

State Machine:
    CLOSED ──[5 consecutive failures]──→ OPEN ──[60s elapsed]──→ HALF-OPEN
      ↑                                          ↑                      │
      │                                          └────[1 failure]───────┘
      └────────────────[1 success in half-open]────────────────────────┘

Behavior:
    - CLOSED: Normal operation; failures increment counter, success resets to 0
    - OPEN: Skip all Ollama calls for 60s; emails default to IGNORE; log WARNING
    - HALF-OPEN: Allow 1 test call; success → CLOSED; failure → OPEN again
    - Health check at startup always runs (unaffected by circuit state)

See PLAN.md §9 for full circuit breaker specification.
"""

from __future__ import annotations

import threading
import time
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker state machine for Ollama calls.

    Thread-safe state machine that prevents cascade failures by
    temporarily stopping calls to a failing service.

    Args:
        failure_threshold: Consecutive failures before opening circuit.
        open_duration: Seconds to wait before testing recovery.
        half_open_max_calls: Test calls allowed in half-open state.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        open_duration: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._open_duration = open_duration
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count_in_half_open = 0
        self._opened_at: float | None = None
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        """Return current circuit state, checking for time-based transitions."""
        with self._lock:
            if (
                self._state == CircuitState.OPEN
                and self._opened_at is not None
                and (time.monotonic() - self._opened_at) >= self._open_duration
            ):
                logger.info(
                    "Circuit breaker transitioning OPEN → HALF-OPEN (open_duration elapsed)",
                    open_duration=self._open_duration,
                )
                self._state = CircuitState.HALF_OPEN
                self._success_count_in_half_open = 0
            return self._state

    @property
    def failure_count(self) -> int:
        """Return current consecutive failure count (CLOSED state only)."""
        with self._lock:
            return self._failure_count

    def record_success(self) -> None:
        """Record a successful call.

        In CLOSED state: resets failure counter.
        In HALF_OPEN state: if success_count reaches half_open_max_calls,
            transitions to CLOSED.
        In OPEN state: no effect.
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                self._failure_count = 0
                logger.debug("Circuit breaker: success recorded, failure_count reset")

            elif self._state == CircuitState.HALF_OPEN:
                self._success_count_in_half_open += 1
                if self._success_count_in_half_open >= self._half_open_max_calls:
                    logger.info(
                        "Circuit breaker transitioning HALF-OPEN → CLOSED "
                        "(half_open_max_calls reached)",
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count_in_half_open = 0

    def record_failure(self) -> None:
        """Record a failed call.

        In CLOSED state: increments failure counter; if threshold reached,
            transitions to OPEN.
        In HALF_OPEN state: immediately transitions back to OPEN.
        In OPEN state: no effect.
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                self._failure_count += 1
                logger.warning(
                    "Circuit breaker: failure recorded",
                    failure_count=self._failure_count,
                    failure_threshold=self._failure_threshold,
                )
                if self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = time.monotonic()
                    logger.error(
                        "Circuit breaker OPEN (failure_threshold reached)",
                        failure_threshold=self._failure_threshold,
                        open_duration=self._open_duration,
                    )

            elif self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "Circuit breaker transitioning HALF-OPEN → OPEN (test call failed)",
                )
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                self._success_count_in_half_open = 0

    def allow_request(self) -> bool:
        """Return True if a request should be allowed through.

        Always allows health checks (they pass state=None in call).
        In OPEN state: returns False if open_duration not yet elapsed.
        In HALF_OPEN state: allows up to half_open_max_calls.
        In CLOSED state: always allows.
        """
        current_state = self.state
        if current_state == CircuitState.CLOSED:
            return True
        if current_state == CircuitState.OPEN:
            return False
        # HALF_OPEN
        with self._lock:
            return self._success_count_in_half_open < self._half_open_max_calls

    def is_open(self) -> bool:
        """Return True if circuit is OPEN (calls are being blocked)."""
        return self.state == CircuitState.OPEN

    def is_half_open(self) -> bool:
        """Return True if circuit is HALF-OPEN (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state with zero failures.

        Used primarily for testing or forced re-initialization.
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count_in_half_open = 0
            self._opened_at = None
            logger.info("Circuit breaker reset to CLOSED")
