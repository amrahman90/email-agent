"""Polling trigger for continuous email monitoring.

Provides a background polling loop that runs the pipeline at configurable
intervals. Uses threading primitives for safe concurrent operation.

Polling Concurrency Guard (PLAN.md §9):
    Uses threading.Lock to ensure only one poll cycle runs at a time.
    If a poll cycle takes longer than polling_interval, the next cycle
    waits for the current one to complete before proceeding.

Graceful Shutdown (PLAN.md §13):
    threading.Event is used to signal graceful shutdown.
    On SIGINT/SIGTERM, the event is set and the polling loop exits
    cleanly after the current cycle completes.

See PLAN.md §9 for polling concurrency guard specification.
See PLAN.md §13 for graceful shutdown specification.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from email_agent.config.settings import Settings

logger = structlog.get_logger(__name__)


class PollingTrigger:
    """Background polling loop for email processing.

    Runs the pipeline at configurable intervals with:
        - threading.Lock to ensure single poll cycle at a time
        - threading.Event for graceful shutdown (SIGINT/SIGTERM)
        - Interval configuration from settings

    Args:
        settings: Application settings with polling_interval.
        pipeline_coro: Async callable that runs one full pipeline cycle.
            Called with no arguments: await pipeline_coro()

    Example:
        async def run_pipeline():
            pipeline = Pipeline(...)
            await pipeline.run()

        trigger = PollingTrigger(settings, run_pipeline)
        trigger.start()
        # ... later ...
        trigger.stop()
    """

    def __init__(
        self,
        settings: Settings,
        pipeline_coro: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        self._settings = settings
        self._pipeline_coro = pipeline_coro
        self._interval = settings.agent.polling_interval

        # Concurrency guard: ensures only one poll cycle runs at a time
        self._lock = threading.Lock()

        # Shutdown signal: set by SIGINT/SIGTERM handler
        self._shutdown_event = threading.Event()

        # Background thread for the polling loop
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the polling loop in a background thread.

        Non-blocking: returns immediately. The loop runs in a dedicated thread.
        """
        if self._thread is not None:
            logger.warning("PollingTrigger already started")
            return

        self._shutdown_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="PollingTrigger",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "PollingTrigger started",
            interval_seconds=self._interval,
        )

    def stop(self) -> None:
        """Signal the polling loop to stop and wait for it to finish.

        Blocking: waits for the current poll cycle to complete before returning.
        """
        logger.info("PollingTrigger stopping")
        self._shutdown_event.set()

        if self._thread is not None:
            self._thread.join(timeout=120)
            self._thread = None

        logger.info("PollingTrigger stopped")

    def _run_loop(self) -> None:
        """Run the polling loop in a background thread.

        Uses its own event loop (asyncio.new_event_loop) since the
        background thread cannot share the main thread's event loop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while not self._shutdown_event.is_set():
                # Use lock to ensure single poll cycle at a time
                with self._lock:
                    if self._shutdown_event.is_set():
                        break

                    logger.debug("Poll cycle starting")
                    start_time = time.monotonic()

                    try:
                        # Run one pipeline cycle
                        task = self._pipeline_coro()
                        loop.run_until_complete(task)
                    except Exception as exc:
                        logger.error(
                            "Poll cycle failed with exception",
                            error=str(exc),
                            error_type=type(exc).__name__,
                        )

                    elapsed = time.monotonic() - start_time
                    logger.debug(
                        "Poll cycle complete",
                        elapsed_seconds=round(elapsed, 2),
                    )

                # Check shutdown before sleeping
                if self._shutdown_event.is_set():
                    break

                # Sleep with interruptible wait
                self._shutdown_event.wait(timeout=self._interval)

        finally:
            loop.close()

        logger.info("PollingTrigger loop exited")

    def set_shutdown_event(self, event: threading.Event) -> None:
        """Set an external shutdown event to coordinate with main thread.

        Allows the main thread to share a single shutdown event for both
        the polling trigger and the main entry point.

        Args:
            event: threading.Event to use for shutdown signaling.
        """
        self._shutdown_event = event
