"""CLI entry point for email-agent.

Supports:
    - Normal mode:     python -m email_agent [--config <path>]
    - Once mode:       python -m email_agent --once [--config <path>]
    - Dry-run mode:    python -m email_agent --dry-run [--config <path>]
    - Verbose mode:    python -m email_agent --verbose [--config <path>]
    - Clear state:     python -m email_agent --clear-state [--config <path>]
    - First-run setup: python -m email_agent setup

Exit codes:
    0 = Success
    1 = Config error
    2 = Gmail auth error
    3 = Ollama error
    4 = Unexpected error

See docs/usage.md for full CLI reference.
See PLAN.md §13 for graceful shutdown specification.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from email_agent.config.settings import Settings
    from email_agent.service.agent import AgentContainer
    from email_agent.state.tracker import StateTracker

# ---------------------------------------------------------------------------
# Module-level shutdown event shared across signal handlers and pipeline
# ---------------------------------------------------------------------------

_shutdown_event = threading.Event()

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------


def configure_logging(verbose: bool = False) -> None:
    """Configure structured logging for the application.

    Args:
        verbose: If True, use DEBUG level and human-readable rendering.
                If False, use INFO level and JSON rendering.
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    # Detect if running in a terminal (human-readable output)
    is_terminal = sys.stderr.isatty()

    processors: list[object] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if verbose and is_terminal:
        # Human-readable console output for local debugging
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON output for production / log files
        processors.append(structlog.processors.JSONRenderer())

    wrapper = structlog.make_filtering_bound_logger(log_level)

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=wrapper,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

logger = structlog.get_logger()


def _handle_signal(signum: int, frame: FrameType | None) -> None:
    """Handle SIGINT/SIGTERM for graceful shutdown.

    Sets the shutdown event to signal the pipeline to finish cleanly.
    Per PLAN.md §13: current operation completes before exit.
    """
    signame = signal.Signals(signum).name
    logger.info("Shutdown signal received, finishing current operation...", signal=signame)
    _shutdown_event.set()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

# Parser built once at module level (argparse has no side effects on import)
_parser: argparse.ArgumentParser | None = None


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    global _parser
    if _parser is not None:
        return _parser

    _parser = argparse.ArgumentParser(
        prog="email-agent",
        description="Email Agent — AI-powered Gmail triage and draft creation",
    )
    _parser.add_argument(
        "--config",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to config.yaml (default: ./config.yaml)",
    )
    _parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single batch and exit (continuous polling otherwise)",
    )
    _parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate processing without applying labels or creating drafts",
    )
    _parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging (may contain PII — use with caution)",
    )
    _parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Reset processed email tracking before starting",
    )
    _parser.add_argument(
        "setup",
        nargs="?",
        help="Run interactive first-run setup wizard",
    )

    return _parser


# ---------------------------------------------------------------------------
# State clearing
# ---------------------------------------------------------------------------


def _clear_state_interactive(state_tracker: StateTracker) -> None:
    """Prompt user to confirm state clearing, then reset.

    Args:
        state_tracker: StateTracker instance to reset.
    """
    print()
    print("WARNING: This will reset all processed email tracking.")
    print("All unread emails will be re-evaluated on the next run.")
    print()
    try:
        response = input("Proceed with state reset? [y/N]: ").strip().lower()
    except (EOFError, OSError):
        response = "n"

    if response in ("y", "yes"):
        state_tracker.clear()
        state_tracker.save()
        logger.info("State tracking reset")
        print("State tracking has been reset.")
    else:
        print("State reset cancelled.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _run_continuous(settings: Settings) -> None:
    """Run the polling loop continuously until shutdown.

    This is a synchronous function that blocks the calling thread
    (the signal handler sets _shutdown_event to break the loop).

    Args:
        settings: Application settings (used to extract polling_interval).
    """
    from email_agent.service.agent import AgentContainer
    from email_agent.trigger.polling import PollingTrigger

    polling_interval = settings.agent.polling_interval
    container = AgentContainer(settings)

    # Import here to avoid top-level circular imports
    async def _init_and_run() -> None:
        await container.initialize()
        await container.run_once()
        await container.cleanup()

    async def _pipeline_coro() -> None:
        """No-argument async callable passed to PollingTrigger.

        Creates a task for the init+run+cleanup sequence.
        """
        await _init_and_run()

    trigger = PollingTrigger(
        settings=settings,
        pipeline_coro=_pipeline_coro,
    )
    trigger.set_shutdown_event(_shutdown_event)

    logger.info("Starting continuous polling mode", polling_interval=polling_interval)
    trigger.start()
    trigger.stop()  # Blocks until shutdown event is set and loop exits


async def _run_once(
    container: AgentContainer,
    dry_run: bool,
    config_path: Path | None,
) -> None:
    """Run a single pipeline cycle.

    Args:
        container: Initialized AgentContainer.
        dry_run: If True, run in dry-run mode.
        config_path: Path to config (for logging).
    """
    logger.info("Running single pipeline cycle", dry_run=dry_run, config=config_path)

    # Update dry_run in pipeline config if requested
    if dry_run:
        container.pipeline._config.dry_run = True

    results = await container.run_once()
    logger.info("Single cycle complete", phase1=results.phase1, phase2=results.phase2)


async def _async_main(argv: list[str]) -> int:
    """Async main — runs the agent.

    Returns:
        Exit code (0=success, 1=config error, 2=Gmail auth error, 3=Ollama error, 4=unexpected).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Handle 'setup' subcommand separately
    if args.setup == "setup":
        return _run_setup()

    # -------------------------------------------------------------------
    # Normal / once / dry-run mode
    # -------------------------------------------------------------------

    # Configure logging
    verbose = args.verbose or bool(os.environ.get("EMAIL_AGENT_VERBOSE"))
    configure_logging(verbose=verbose)

    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Load configuration
    from email_agent.config.loader import ConfigError, load_config
    from email_agent.exceptions.base import (
        GmailAuthError,
        OllamaConnectionError,
    )

    config_path = Path(args.config) if args.config else None

    try:
        settings = load_config(config_path)
    except ConfigError as exc:
        logger.error("Configuration error", error=str(exc))
        return 1

    # Emit warning for email_age_limit_days=0
    settings.agent.warn_if_no_age_limit()

    # -------------------------------------------------------------------
    # Run the agent (once or continuous)
    # -------------------------------------------------------------------

    if args.once:
        # Once mode: use container managed here, with explicit cleanup
        from email_agent.service.agent import AgentContainer

        container = AgentContainer(settings)

        try:
            await container.initialize()
        except GmailAuthError as exc:
            logger.error("Gmail authentication failed", error=str(exc))
            return 2
        except OllamaConnectionError as exc:
            logger.error("Ollama connection failed", error=str(exc))
            return 3
        except Exception as exc:
            logger.error("Unexpected initialization error", error=str(exc))
            return 4

        try:
            if args.clear_state:
                _clear_state_interactive(container.state_tracker)

            await _run_once(container, args.dry_run, config_path)

        except Exception as exc:
            logger.error("Unexpected error during execution", error=str(exc))
            return 4

        finally:
            await container.cleanup()

        return 0

    else:
        # Continuous mode: PollingTrigger owns the container lifecycle
        # _run_continuous blocks until shutdown, then returns
        _run_continuous(settings)
        return 0


def _run_setup() -> int:
    """Launch the first-run setup wizard.

    Runs scripts/first_run.py as a subprocess.

    Returns:
        Exit code from the setup wizard.
    """
    setup_script = Path(__file__).parent.parent.parent / "scripts" / "first_run.py"
    logger.info("Launching first-run setup wizard", script=str(setup_script))

    try:
        result = subprocess.run(
            [sys.executable, str(setup_script)],
            check=False,
        )
        return result.returncode
    except FileNotFoundError:
        print(f"ERROR: Setup script not found: {setup_script}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: Failed to run setup wizard: {exc}", file=sys.stderr)
        return 4


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for email-agent.

    Args:
        argv: Command-line arguments (defaults to sys.argv).

    Returns:
        Exit code (0=success, 1=config error, 2=Gmail auth error, 3=Ollama error, 4=unexpected).
    """
    if argv is None:
        argv = sys.argv[1:]

    # Basic no-send enforcement at CLI level: block obviously bad invocations
    # The real enforcement is via pre-commit hook + CI ruff check.
    joined = " ".join(argv).lower()
    if ".send(" in joined:
        print("ERROR: .send() calls are forbidden in email-agent.", file=sys.stderr)
        print("All drafts must be reviewed and sent manually.", file=sys.stderr)
        return 4

    try:
        return asyncio.run(_async_main(argv))
    except KeyboardInterrupt:
        # Already handled by signal handler, just exit cleanly
        return 0
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
