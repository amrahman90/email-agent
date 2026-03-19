"""Email Agent - AI-powered email triage and draft reply agent.

A desktop AI agent that reads Gmail unread emails, categorizes them using
Ollama LLM (with function calling), and creates draft replies for important
emails.

Key Features:
- Gmail integration via Google API
- Ollama LLM with function calling for email triage
- Two-phase pipeline: Triage → Draft
- Business rules override layer for deterministic corrections
- Circuit breaker to prevent cascade failures
- Structured logging with structlog
- Graceful shutdown support

Usage:
    python -m email_agent [--once] [--dry-run] [--verbose]

See PLAN.md for technical reference and docs/ for user documentation.
"""

__version__ = "0.0.1"
__all__ = [
    "__version__",
]
