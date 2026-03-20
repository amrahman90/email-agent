# Changelog

All notable changes to this project.

## [Unreleased] - 2026-03-20

## [0.0.1] - 2026-03-20

### Fixed

#### CI Pipeline
- **Root cause: `.gitignore` exclusion** — `state/` pattern was matching `email_agent/state/` Python package, excluding it from git. Fixed by changing to `/state/` (root-level only).
- **Root cause: Missing mypy dependency** — `mypy` was only in `.pre-commit-config.yaml` hooks, not as a dev dependency. Added `mypy>=1.13.0` to `pyproject.toml`.
- **Root cause: Missing editable install in CI** — Test job didn't install the package before running pytest. Added `uv pip install -e . --no-build` to CI test job.
- **Root cause: Broken pre-commit mypy hook** — `pre-commit/mirrors-mypy` doesn't work with `uv run`. Replaced with a `local` hook using `uv run mypy`.
- **Path configuration** — Updated all CI and pre-commit paths from `src/` to `email_agent/` after project restructure.
- **Removed diagnostic debugging step** — Cleaned up the CI test job by removing the "Diagnose package installation" debug step that was added during investigation.

#### Test Suite
- **Circuit breaker time-mocking tests** (`test_is_half_open_returns_true_when_half_open`, `test_half_open_success_closes_circuit`, `test_half_open_failure_reopens_circuit`, `test_multiple_successes_in_half_open_closes_circuit`) — All had the same bug: `mocker.patch()` was applied **after** the `record_failure()` loop, causing `_opened_at` to capture a `MagicMock` object instead of a float. Fixed by moving `mock_time = mocker.patch(...)` and `mock_time.monotonic.return_value = 1000.0` **before** the failure-recording loop.
- **Removed 2 unused `# type: ignore[comparison-overlap]` comments** from `test_circuit_breaker.py` (lines 77 and 172) — mypy confirmed these were no longer needed after the time-mocking fix.
- **Retained necessary `# type: ignore` comments** across `test_circuit_breaker.py`, `test_settings.py`, `scripts/first_run.py`, and `scripts/stress_test.py` — these suppress legitimate mypy errors from typed interfaces used with untyped test values or dynamic API responses.

### Changed

- **CI lint job** — Now runs `uv run mypy email_agent/` (type check only), separate from pre-commit which runs full `uv run mypy email_agent/ tests/ scripts/`.
- **Pre-commit configuration** — Updated `files` pattern from `^src/` to `^email_agent/` to match project structure.
- **Project structure** — Package is now at `email_agent/` (project root), not `src/email_agent/`.

### Technical Decisions

| Feature | Decision |
|---------|----------|
| Config Format | YAML + pydantic-settings |
| LLM Structured Output | Function calling |
| Processing | Sequential |
| Orchestration | workflows/pipeline.py |
| Exception Handling | Custom hierarchy |
| Retry | tenacity |
| Package Layout | Flat (email_agent/ at project root) |

## [Unreleased] - 2026-03-19

### Planned Features

- Gmail API integration (read, label, draft)
- Ollama integration with function calling
- Two-phase pipeline (Triage → Draft)
- Business rules override layer
- Polling trigger system
- Configuration via `config.yaml` with pydantic-settings
- Custom exception hierarchy
- Retry logic with tenacity
- Structured logging with structlog
- Ruff linting with "no send" rule
- Comprehensive test suite
- Documentation in `docs/`
- Email categorization using LLM
- Automatic label application
- Draft reply generation
- Per-email error isolation
- Label normalization (emoji/unicode)
- State tracking to prevent duplicate processing
- Graceful shutdown
- HTML email stripping (BeautifulSoup)

### Security

- Never send emails automatically
- All AI processing local
- OAuth2 for Gmail
- No credentials in git

## Known Limitations

- Polling only (no Gmail Watch)
- Gmail only (no Outlook/IMAP)
- Single Ollama model
- Sequential processing (no concurrency)
