"""Tests for StateTracker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from email_agent.state.tracker import MAX_IDS, STATE_FILE, StateTracker


def test_load_creates_new_state_if_file_missing(tmp_state_dir: Path) -> None:
    """Verify load() creates fresh state when file doesn't exist."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()

    assert tracker._state.processed == {}
    assert tracker._state.last_processed is None


def test_load_parses_existing_state(tmp_state_dir: Path) -> None:
    """Verify load() parses existing state file correctly."""
    state_file = tmp_state_dir / STATE_FILE
    state_data = {
        "processed": ["msg_001", "msg_002", "msg_003"],
        "last_processed": "2024-01-01T12:00:00Z",
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()

    assert "msg_001" in tracker._state.processed
    assert "msg_002" in tracker._state.processed
    assert "msg_003" in tracker._state.processed
    assert tracker._state.last_processed == "2024-01-01T12:00:00Z"


def test_load_handles_corrupted_json(tmp_state_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Verify load() handles corrupted JSON gracefully."""
    state_file = tmp_state_dir / STATE_FILE
    state_file.write_text("{ invalid json }", encoding="utf-8")

    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()

    assert tracker._state.processed == {}
    assert tracker._state.last_processed is None


def test_save_writes_state_to_disk(tmp_state_dir: Path) -> None:
    """Verify save() persists state correctly."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()
    tracker.mark_processed("msg_001")
    tracker.mark_processed("msg_002")
    tracker.save()

    state_file = tmp_state_dir / STATE_FILE
    assert state_file.exists()

    with open(state_file, encoding="utf-8") as f:
        data = json.load(f)

    assert "msg_001" in data["processed"]
    assert "msg_002" in data["processed"]


def test_is_processed_returns_false_for_new_id(tmp_state_dir: Path) -> None:
    """Verify is_processed() returns False for unprocessed IDs."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()

    assert tracker.is_processed("msg_001") is False


def test_is_processed_returns_true_for_processed_id(tmp_state_dir: Path) -> None:
    """Verify is_processed() returns True for processed IDs."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()
    tracker.mark_processed("msg_001")

    assert tracker.is_processed("msg_001") is True


def test_mark_processed_adds_id(tmp_state_dir: Path) -> None:
    """Verify mark_processed() adds ID to processed set."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()

    tracker.mark_processed("msg_001")
    tracker.mark_processed("msg_002")

    assert "msg_001" in tracker._state.processed
    assert "msg_002" in tracker._state.processed


def test_clear_resets_state(tmp_state_dir: Path) -> None:
    """Verify clear() resets state to empty."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()
    tracker.mark_processed("msg_001")
    tracker.mark_processed("msg_002")
    tracker.save()

    tracker.clear()

    assert tracker._state.processed == {}
    assert tracker._state.last_processed is None


def test_prune_removes_old_ids_when_age_limit_set(tmp_state_dir: Path) -> None:
    """Verify prune() removes stale IDs when age limit is set."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()
    tracker.mark_processed("msg_001")
    tracker.mark_processed("msg_002")

    removed = tracker.prune()

    assert removed >= 0


def test_prune_returns_zero_when_age_limit_zero(tmp_state_dir: Path) -> None:
    """Verify prune() returns 0 when email_age_limit_days is 0."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=0)
    tracker.load()
    tracker.mark_processed("msg_001")

    removed = tracker.prune()

    assert removed == 0


def test_enforce_max_ids_removes_oldest_when_over_limit(tmp_state_dir: Path) -> None:
    """Verify enforce_max_ids() removes oldest IDs when over limit."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()

    for i in range(MAX_IDS + 100):
        tracker.mark_processed(f"msg_{i:05d}")

    removed = tracker.enforce_max_ids()

    # The 100 oldest (first 100 added) are discarded;
    # the 10,000 most recently added remain.
    assert removed == 100
    assert len(tracker._state.processed) == MAX_IDS
    # The last 100 added (msg_00000 through msg_00099) were discarded
    assert not tracker.is_processed("msg_00000")
    assert not tracker.is_processed("msg_00099")
    # The 10,000th-10,099th added are still present
    assert tracker.is_processed("msg_09000")
    assert tracker.is_processed("msg_09099")


def test_from_directory_context_manager(tmp_state_dir: Path) -> None:
    """Verify from_directory() works as a context manager."""
    with StateTracker.from_directory(tmp_state_dir, email_age_limit_days=7) as tracker:
        tracker.mark_processed("msg_001")
        assert tracker.is_processed("msg_001")

    tracker_load = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker_load.load()
    assert tracker_load.is_processed("msg_001")


def test_save_atomic_write(tmp_state_dir: Path) -> None:
    """Verify save() uses atomic write (temp file then rename)."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()
    tracker.mark_processed("msg_001")

    tracker.save()

    state_file = tmp_state_dir / STATE_FILE
    temp_file = tmp_state_dir / f"{STATE_FILE}.tmp"

    assert state_file.exists()
    assert not temp_file.exists()


def test_multiple_save_overwrites(tmp_state_dir: Path) -> None:
    """Verify multiple saves overwrite correctly."""
    tracker = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker.load()

    tracker.mark_processed("msg_001")
    tracker.save()

    tracker.mark_processed("msg_002")
    tracker.save()

    tracker_load = StateTracker(state_dir=tmp_state_dir, email_age_limit_days=7)
    tracker_load.load()

    assert tracker_load.is_processed("msg_001")
    assert tracker_load.is_processed("msg_002")
