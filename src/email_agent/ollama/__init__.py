"""Ollama LLM integration module.

Provides Ollama API client with function calling support for email triage
and draft generation.

Key Classes:
    - OllamaClient: API client with retry and circuit breaker
    - CircuitBreaker: State machine to prevent cascade failures

Circuit Breaker Parameters:
    - failure_threshold: 5 consecutive failures → OPEN
    - open_duration: 60 seconds before HALF-OPEN
    - half_open_max_calls: 1 test call allowed in HALF-OPEN

Retry Strategy:
    - OllamaTimeoutError: 3 retries, exponential backoff + jitter (max 10s)
    - See PLAN.md §7 for full retry strategy table

See PLAN.md §7 for exception hierarchy and retry strategy.
"""

from email_agent.ollama.circuit_breaker import CircuitBreaker, CircuitState
from email_agent.ollama.client import OllamaClient

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "OllamaClient",
]
