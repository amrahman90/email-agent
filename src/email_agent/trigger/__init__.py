"""Trigger module for email-agent.

Provides polling loop implementation for continuous email monitoring.

PollingTrigger:
    - Runs at configurable intervals (default: 60 seconds)
    - Uses threading.Lock to ensure single poll cycle at a time
    - Concurrency-aware: next poll waits for current to complete

The trigger module is separate from the pipeline to enable
clean separation of concerns. The main entry point coordinates
the trigger and pipeline.

See PLAN.md §9 for polling concurrency guard specification.
See PLAN.md §4 for Phase 4 module inventory.
"""

from email_agent.trigger.polling import PollingTrigger

__all__ = [
    "PollingTrigger",
]
