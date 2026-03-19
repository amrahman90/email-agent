"""Service module for email-agent.

Provides dependency injection container for managing service instances.

AgentContainer:
    - Dependency injection container
    - Manages lifecycle of Gmail, Ollama, and processor instances
    - NOT the main orchestrator (that's workflows/pipeline.py)

This module follows the Dependency Injection pattern to:
    - Make services easy to test with mocks
    - Centralize instance creation
    - Enable clean separation of concerns

See PLAN.md §4 for project structure and §9 for DI specification.
See PLAN.md §4 for Phase 4 module inventory.
"""

from email_agent.service.agent import AgentContainer

__all__ = [
    "AgentContainer",
]
