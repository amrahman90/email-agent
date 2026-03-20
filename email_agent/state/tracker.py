"""State tracking for processed email IDs.

Tracks processed email IDs to prevent duplicate processing across runs.
State is persisted to state/processed_emails.json.

Cleanup Policy:
    - TTL: IDs older than (email_age_limit_days + 7) days are pruned
    - Max IDs: 10,000 (oldest pruned first if exceeded)
    - Corruption: Log WARNING and start fresh if parse fails

See PLAN.md §14 for full specification.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

LOGGER = structlog.get_logger()

STATE_FILE = "processed_emails.json"
MAX_IDS = 10_000
TTL_GRACE_DAYS = 7


class StateError(Exception):
    """Raised when state operations fail."""

    pass


@dataclass(slots=True)
class ProcessedState:
    """Represents the processed emails state."""

    # Use dict as ordered set (insertion order preserved in Python 3.7+)
    processed: dict[str, None] = field(default_factory=dict)
    last_processed: str | None = None

    def to_dict(self) -> dict[str, list[str] | str | None]:
        """Convert state to dictionary for JSON serialization.

        Note:
            processed IDs are stored in insertion order (oldest first) to
            preserve chronological ordering for enforce_max_ids() pruning.
            The JSON is not sorted alphabetically, which reduces human
            readability but maintains correct pruning semantics after load().
        """
        return {
            "processed": list(self.processed.keys()),
            "last_processed": self.last_processed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ProcessedState:
        """Create state from dictionary loaded from JSON.

        Note:
            processed IDs are expected in insertion order (oldest first).
            This preserves chronological ordering for enforce_max_ids().
        """
        processed_data = data.get("processed", [])
        if not isinstance(processed_data, list):
            processed_data = []
        last_processed_raw = data.get("last_processed")
        last_processed: str | None = None
        if isinstance(last_processed_raw, str):
            last_processed = last_processed_raw
        # Use dict.fromkeys() to preserve insertion order from JSON list
        return cls(
            processed=dict.fromkeys(str(x) for x in processed_data),
            last_processed=last_processed,
        )


class _DirectoryContext:
    """Context manager for loading state from a directory."""

    def __init__(self, tracker: StateTracker) -> None:
        self._tracker = tracker

    def __enter__(self) -> StateTracker:
        return self._tracker

    def __exit__(self, *args: object) -> None:
        self._tracker.save()


class StateTracker:
    """Track processed email IDs with persistence and cleanup.

    Args:
        state_dir: Directory where state file is stored.
        email_age_limit_days: Maximum age of emails to process.
            0 means no limit (no pruning based on age).
    """

    def __init__(self, state_dir: Path, email_age_limit_days: int) -> None:
        self._state_dir = state_dir
        self._email_age_limit_days = email_age_limit_days
        self._state: ProcessedState = ProcessedState()
        self._state_file = state_dir / STATE_FILE

    def load(self) -> None:
        """Load state from state_dir / processed_emails.json."""
        if not self._state_file.exists():
            LOGGER.info("State file not found, starting fresh", path=str(self._state_file))
            self._state = ProcessedState()
            return

        try:
            raw = self._state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._state = ProcessedState.from_dict(data)
            LOGGER.info(
                "State loaded",
                processed_count=len(self._state.processed),
                path=str(self._state_file),
            )
        except json.JSONDecodeError as e:
            LOGGER.warning(
                "State file corrupted, starting fresh",
                path=str(self._state_file),
                error=str(e),
            )
            self._state = ProcessedState()

    def save(self) -> None:
        """Persist state to JSON file.

        Uses atomic write (write to temp, then rename) to prevent corruption.
        """
        self._state_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self._state_file.with_suffix(".tmp")
        try:
            temp_path.write_text(
                json.dumps(self._state.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temp_path.replace(self._state_file)
            LOGGER.debug("State saved", path=str(self._state_file))
        except OSError as e:
            raise StateError(f"Failed to save state: {e}") from e

    def is_processed(self, email_id: str) -> bool:
        """Check if email ID has already been processed."""
        return email_id in self._state.processed

    def mark_processed(self, email_id: str) -> None:
        """Mark email ID as processed and update timestamp."""
        self._state.processed[email_id] = None
        self._state.last_processed = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def clear(self) -> None:
        """Reset state to empty."""
        self._state = ProcessedState()
        LOGGER.info("State cleared")

    def prune(self) -> int:
        """Prune stale email IDs based on last_processed timestamp.

        Removes IDs when last_processed is older than
        (email_age_limit_days + TTL_GRACE_DAYS). If email_age_limit_days
        is 0, no age-based pruning occurs.

        Design Decision:
            Age is determined by last_processed — the timestamp of the most
            recently processed email. All IDs share this timestamp because
            mark_processed() only updates the timestamp, not per-ID times.
            This means age-based pruning is all-or-nothing: either ALL IDs
            pass the cutoff and survive, or ALL are pruned when the last run
            is too old. This is a deliberate trade-off to avoid the overhead
            of storing per-ID timestamps while still preventing unbounded state
            growth for users who run infrequently.

        Returns:
            Number of IDs removed.
        """
        if self._email_age_limit_days == 0:
            return 0

        if self._state.last_processed is None:
            return 0

        try:
            last_processed_dt = dt.datetime.fromisoformat(
                self._state.last_processed.replace("Z", "+00:00")
            )
        except ValueError:
            return 0

        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(  # noqa: UP017
            days=self._email_age_limit_days + TTL_GRACE_DAYS,
        )

        original_count = len(self._state.processed)

        # If last_processed is older than cutoff, prune all non-empty IDs
        if last_processed_dt < cutoff:
            self._state.processed = {
                email_id: None
                for email_id in self._state.processed
                if email_id != "" and len(email_id) > 0
            }
        else:
            # Even if not past cutoff, remove empty/malformed IDs
            self._state.processed = {
                email_id: None
                for email_id in self._state.processed
                if email_id != "" and len(email_id) > 0
            }

        removed = original_count - len(self._state.processed)

        if removed > 0:
            LOGGER.info(
                "Pruned stale email IDs",
                removed=removed,
                remaining=len(self._state.processed),
                cutoff_days=self._email_age_limit_days + TTL_GRACE_DAYS,
            )

        return removed

    def enforce_max_ids(self) -> int:
        """If > 10,000 IDs, prune oldest until under limit.

        Removes the oldest IDs (earliest in insertion order) to stay
        within the MAX_IDS limit.

        Returns:
            Number of IDs removed.
        """
        if len(self._state.processed) <= MAX_IDS:
            return 0

        removed = len(self._state.processed) - MAX_IDS
        # dict preserves insertion order in Python 3.7+; take the last MAX_IDS
        # (most recently added), discarding the first `removed` (oldest).
        processed_list = list(self._state.processed)
        self._state.processed = dict.fromkeys(processed_list[removed:])

        LOGGER.info(
            "Enforced max ID limit",
            removed=removed,
            remaining=len(self._state.processed),
            max_ids=MAX_IDS,
        )

        return removed

    @classmethod
    def from_directory(
        cls,
        state_dir: Path,
        email_age_limit_days: int,
    ) -> _DirectoryContext:
        """Context manager to load state, run cleanup, and save on exit.

        Args:
            state_dir: Directory where state file is stored.
            email_age_limit_days: Maximum age of emails to process.

        Returns:
            Context manager that yields a configured StateTracker instance.
        """
        tracker = cls(state_dir, email_age_limit_days)
        tracker.load()
        tracker.prune()
        tracker.enforce_max_ids()
        return _DirectoryContext(tracker)
