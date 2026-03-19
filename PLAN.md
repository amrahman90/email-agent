# Email Agent - Project Plan

**Version:** 2.0
**Date:** 2026-03-19
**Status:** Ready for Implementation

> **Note:** User-facing documentation has been moved to `docs/`. See:
> - [Setup Guide](docs/getting-started.md)
> - [Configuration Reference](docs/configuration.md)
> - [Architecture](docs/architecture.md)
> - [Troubleshooting](docs/troubleshooting.md)

---

## 1. Project Overview

**Project Name:** Email Agent
**Type:** Desktop/Local AI Agent
**Core Functionality:** Reads Gmail unread emails, categorizes them into user-defined labels using Ollama LLM, and creates draft replies for important emails.
**Target Users:** Individual users who want automated email organization with AI assistance.

### Key Principle
**NEVER send emails automatically** - All drafts must be reviewed and sent manually by the user.

---

## 2. Technical Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.13+ |
| Package Manager | uv |
| Email Provider | Gmail (Google Gmail API) |
| LLM Provider | Ollama (local, llama3.2:1b) |
| Config Format | YAML (with pydantic-settings validation) |
| Authentication | OAuth 2.0 (Gmail) |
| Logging | structlog (structured JSON logs) |
| Linting | Ruff (code quality) + pre-commit pygrep hook (no-send enforcement) |
| Retry Logic | tenacity (exponential backoff + jitter) |

---

## 3. Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              Email Agent                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Gmail API  │◄──►│   Ollama     │◄──►│   Config     │                   │
│  │   Client     │    │   Client     │    │   Manager    │                   │
│  └──────┬───────┘    └──────────────┘    └──────────────┘                   │
│         │                                                                  │
│         ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                    Email Processor                            │          │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │          │
│  │  │   Triage   │  │  Assess    │  │ Create Draft Reply     │  │          │
│  │  │   Stage    │  │ Importance │  │ (if important)         │  │          │
│  │  └─────┬──────┘  └──────┬─────┘  └────────────────────────┘  │          │
│  │        │               │                                     │          │
│  │        └───────────────┼─────────────────────────────────────┘          │
│  │                        ▼                                               │
│  │  ┌──────────────────────────────────────────────────────────────┐        │
│  │  │         Business Rules Override Layer                       │        │
│  │  │  (Post-LLM deterministic corrections)                       │        │
│  │  │  - Phishing keyword detection                               │        │
│  │  │  - Travel itinerary patterns                                │        │
│  │  │  - Low-confidence downgrades                                │        │
│  │  └──────────────────────────────────────────────────────────────┘        │
│  └──────────────────────────────────────────────────────────────┘          │
│         │                                                                  │
│         ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                    Workflow Pipeline                          │          │
│  │              (Two-phase: Triage → Draft)                     │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                    Trigger Module                            │          │
│  │              (Polling loop with interval)                   │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Project Structure

```
email-agent/
├── PLAN.md                    # This document (technical reference)
├── docs/                      # User & developer documentation
│   ├── README.md              # Documentation index
│   ├── getting-started.md     # Quick start guide
│   ├── installation.md        # Detailed installation steps
│   ├── configuration.md       # config.yaml reference
│   ├── usage.md               # CLI commands and modes
│   ├── troubleshooting.md     # Common issues and solutions
│   ├── security.md            # Security best practices
│   ├── architecture.md        # System architecture overview
│   ├── gmail-setup.md         # Gmail API OAuth setup
│   ├── ollama-setup.md        # Ollama installation + model
│   ├── testing.md             # Testing guide
│   ├── changelog.md           # Version history
│   └── contributing.md         # Development guide
├── config.yaml                # User configuration (categories, senders, etc.)
├── pyproject.toml             # Python project configuration
├── .env.example               # Environment variable template
├── .pre-commit-config.yaml   # Pre-commit hooks (no-send enforcement)
│
├── state/                     # Runtime: auto-created on first run
│   └── processed_emails.json  # Populated at runtime (gitignored)
│
├── .github/
│   └── workflows/
│       └── ci.yml            # CI: ruff check + tests
│
├── src/
│   └── email_agent/
│       ├── __init__.py
│       ├── __main__.py          # Entry point: python -m email_agent
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py    # Pydantic-settings for config.yaml validation
│       │   └── loader.py      # YAML config loading helpers
│       │
│       ├── state/
│       │   ├── __init__.py
│       │   └── tracker.py     # Track processed email IDs (prevent duplicates)
│       │
│       ├── gmail/
│       │   ├── __init__.py
│       │   ├── client.py      # Gmail API client (read, label, draft)
│       │   ├── auth.py        # OAuth2 authentication flow
│       │   └── labels.py      # Label management with normalization
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── email.py       # Email, EmailMetadata dataclasses
│       │   ├── triage.py      # TriageDecision pydantic model
│       │   └── draft.py       # DraftReply dataclass
│       │
│       ├── ollama/
│       │   ├── __init__.py
│       │   ├── client.py      # Ollama API client with function calling
│       │   └── circuit_breaker.py  # Circuit breaker state machine
│       │
│       ├── processor/
│       │   ├── __init__.py
│       │   ├── triage.py      # Email triage (LLM + business rules), calls importance.py
│       │   ├── importance.py  # Importance assessment (called by triage.py)
│       │   └── draft.py       # Draft reply generation
│       │
│       ├── workflows/
│       │   ├── __init__.py
│       │   └── pipeline.py    # Two-phase pipeline orchestration (MAIN ORCHESTRATOR)
│       │
│       ├── trigger/
│       │   ├── __init__.py
│       │   └── polling.py     # Polling loop with interval management
│       │
│       ├── service/
│       │   ├── __init__.py
│       │   └── agent.py       # Dependency injection container (NOT main orchestrator)
│       │
│       └── exceptions/
│           ├── __init__.py
│           └── base.py        # EmailAgentError base + subclasses
│
├── scripts/
│   ├── stress_test.py         # Generate test emails for testing
│   ├── first_run.py           # Called by `python -m email_agent setup` (NOT standalone)
│   └── run_windows.ps1        # Windows runner script
│
├── credentials/
│   └── .gitkeep               # Placeholder (credentials go here, NOT in git)
│
└── tests/
    ├── __init__.py
    ├── conftest.py            # Pytest fixtures
    ├── test_settings.py       # Config validation tests
    ├── test_gmail_client.py   # Gmail client tests
    ├── test_ollama_client.py  # Ollama client tests
    ├── test_circuit_breaker.py # Circuit breaker state machine tests
    ├── test_state_tracker.py  # State tracking + TTL cleanup tests
    ├── test_triage.py         # Triage + business rules tests
    ├── test_importance.py     # Importance assessment tests
    ├── test_pipeline.py       # Integration tests (mocked)
    └── test_exceptions.py     # Exception hierarchy tests
```

---

## 5. Two-Phase Pipeline

### Phase 1: Triage

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. FETCH    → List unread emails from INBOX                      │
│ 2. STATE    → Check if already processed (skip if yes)          │
│ 3. STRIP    → Strip HTML (BeautifulSoup, html.parser);          │
│              → If plain text missing and HTML→empty, skip       │
│ 4. TRIAGE   → For each email:                                   │
│              - Call Ollama with function calling                 │
│              - Apply business rules override                     │
│              - Apply Gmail label                                 │
│ 5. SUMMARY  → Log triage results                               │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2: Draft

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. FILTER   → Get emails with action=REPLY                      │
│ 2. DEDUP    → Check for existing drafts in same thread          │
│ 3. IMPORTANCE → Check importance_threshold                      │
│              → Skip if below threshold                          │
│ 4. DRAFT    → For each REPLY email (not deduplicated):          │
│              - Call Ollama with draft prompt                    │
│              - Create Gmail draft (same thread)                 │
│ 5. SUMMARY  → Log draft creation results                       │
└─────────────────────────────────────────────────────────────────┘
```

### Importance Threshold Gate

Only emails meeting `importance_threshold` get draft replies:
- `low`: All REPLY emails get drafts
- `medium`: REPLY + important_senders get drafts
- `high`: Only important_senders get drafts

### Draft Deduplication

Before creating a draft, check if one already exists in the same thread.
If exists, skip draft creation and log as "duplicate_skipped".

### Batch Overflow Warning

If `len(emails) > max_emails_per_batch`, log a warning:
```python
if len(emails) > max_emails_per_batch:
    LOGGER.warning(
        "Email batch capped at %d (total: %d). Next poll will catch remaining.",
        max_emails_per_batch, len(emails)
    )
```

### Per-Email Error Isolation

```python
for email in emails:
    try:
        decision = run_triage(triage_agent, email)
    except Exception as exc:
        LOGGER.warning("Triage failed for %s, defaulting to IGNORE: %s", email_id, exc)
        decision = TriageDecision(action="IGNORE", category="UNCATEGORIZED", ...)

    decision = apply_business_rules(decision, email)

    try:
        apply_label(email_id, decision.category)
    except Exception as exc:
        LOGGER.warning("Label failed for %s: %s", email_id, exc)
```

---

## 6. Ollama Function Calling

### Triage Tool Definition

```python
{
    "name": "triage_email",
    "description": "Classify an email and decide action",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["IGNORE", "REPLY", "SUSPICIOUS"],
                "description": "What to do with this email"
            },
            "category": {
                "type": "string",
                "enum": config.agent.categories,  # Injected at runtime from config.yaml
                "description": "Email category from configured categories list"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence in classification"
            },
            "suspicious_signals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Risk indicators if SUSPICIOUS"
            },
            "reason": {
                "type": "string",
                "description": "Brief explanation"
            }
        },
        "required": ["action", "category", "confidence", "reason"]
    }
}
```

### Business Rules Override Layer

After LLM triage decision, apply deterministic corrections:

**Phishing Override:**
```python
if has_urgent_language(email) or has_suspicious_links(email):
    return "SUSPICIOUS", "SECURITY_ADMIN", f"Override: phishing detected. {reason}"
```

**Travel Itinerary Override:**
```python
if matches_travel_pattern(email):
    if not has_reply_request(email):
        action = "IGNORE"
```

**Low-Confidence Downgrade:**
```python
if action == "SUSPICIOUS" and confidence < 0.5 and len(suspicious_signals) < 2:
    action = "IGNORE"  # Never promote to REPLY - too risky
```

---

## 7. Exception Hierarchy

All custom exceptions inherit from `EmailAgentError`:

```python
class EmailAgentError(Exception):
    pass

class GmailAuthError(EmailAgentError):
    pass

class GmailApiError(EmailAgentError):
    pass

class QuotaExceededError(GmailApiError):
    """Gmail API rate limit exceeded (HTTP 429). Requires longer backoff."""
    pass

class OllamaConnectionError(EmailAgentError):
    pass

class OllamaTimeout(EmailAgentError):
    pass

class TriageError(EmailAgentError):
    pass

class DraftError(EmailAgentError):
    pass

class LabelError(EmailAgentError):
    pass
```

### Retry Strategy (Tenacity)

```python
# Standard retry for Ollama transient errors (timeouts)
TRANSIENT_EXCEPTIONS = (OllamaTimeout,)

@retry(
    retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
)
def call_ollama_with_retry(prompt: str) -> dict:
    ...
```

```python
# Retry for Gmail transient errors (5xx, timeouts)
# NOTE: QuotaExceededError excluded because it is a subclass of GmailApiError;
# tenacity uses isinstance() internally, so if GmailApiError appeared in the
# retry tuple, isinstance(QuotaExceededError, GmailApiError) would also match.
# Quota errors are handled separately below.
@retry(
    retry=retry_if_exception(
        lambda e: isinstance(e, GmailApiError)
                  and not isinstance(e, QuotaExceededError)
    ),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
)
def call_gmail_with_retry(*args, **kwargs):
    ...
```

```python
# Separate retry for Gmail quota errors (HTTP 429)
# Uses longer fixed backoff to honor Gmail's quota reset window.
@retry(
    retry=retry_if_exception_type(QuotaExceededError),
    stop=stop_after_attempt(3),
    wait=wait_fixed(60),
)
def call_gmail_quota_retry(*args, **kwargs):
    ...
```

| Scenario | Retry Strategy |
|----------|----------------|
| Ollama timeout | Retry 3x, exponential backoff + jitter (max 10s) |
| Gmail API transient error | Retry 3x, exponential backoff + jitter |
| Gmail API rate limit (429) | Retry 3x, fixed 60s backoff (quota reset window) |
| Invalid OAuth token | Fail fast, exit with error |
| Email parse failure | Skip email, log error, continue |
| Invalid LLM response | Retry 1x, then skip with warning |

---

## 8. Gmail API Integration

### Required OAuth2 Scopes

```
- https://www.googleapis.com/auth/gmail.readonly
- https://www.googleapis.com/auth/gmail.labels
- https://www.googleapis.com/auth/gmail.compose
```

### Email Operations

| Operation | API Method | Notes |
|-----------|------------|-------|
| List new emails | `users.messages.list()` | Filter: `is:unread after:{timestamp}` |
| Get email content | `users.messages.get()` | Full message with payload |
| Apply label | `users.messages.modify()` | Add Gmail label |
| Create draft | `users.drafts.create()` | Draft only, NEVER send |

### Email Threading (In-Reply-To)

```python
original = gmail.get_email(message_id)
message_id_header = original.get("messageIdHeader", "")
subject = original.get("subject", "")
reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

message = EmailMessage()
message["To"] = original["from"]
message["Subject"] = reply_subject
if message_id_header:
    message["In-Reply-To"] = message_id_header
    parent_references = original.get("referencesHeader", "")
    message["References"] = f"{parent_references} {message_id_header}".strip()
message.set_content(reply_text)

gmail.create_draft(raw=message.as_bytes(), thread_id=original["threadId"])
```

### Label Normalization

```python
import unicodedata

def normalize_label_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    cleaned = "".join(
        c for c in normalized
        if c.isalnum() or c in {" ", "&", "/", "-", "_"}
    ).lower()
    return " ".join(cleaned.split())
```

**Consistency**: Both config categories AND Gmail label lookups use `normalize_label_name()`.
This ensures "Finance/Tax" in config matches the normalized Gmail label.

---

## 9. Decisions Finalized

| Decision | Choice |
|----------|--------|
| Config Format | `config.yaml` (YAML + pydantic-settings) |
| Trigger System | Polling only (V1), Watch in V2 |
| Trigger Module | Separate `trigger/polling.py` |
| HTML Handling | Plain text first → HTML stripped via BeautifulSoup → empty string |
| Label Format | Direct names (e.g., "Work") |
| Draft Location | Same thread as original email |
| Mark as Read | No (user decides) |
| Concurrency | Sequential processing |
| Logging | structlog (structured JSON), INFO default, daily rotation (TimedRotatingFileHandler, backupCount=7) |
| "Never Send" | Enforced by pre-commit hook + CI ruff check |
| LLM Structured Output | Function calling (Ollama native) |
| Business Rules | Post-LLM deterministic overrides |
| Pipeline | Two-phase (Triage → Draft) |
| Orchestration | `workflows/pipeline.py` is main orchestrator |
| Exception Hierarchy | Custom exceptions in `exceptions/` module |
| Retry Library | tenacity with @retry decorator |

---

### Polling Concurrency Guard

`trigger/polling.py` uses a `threading.Lock` to ensure only one poll cycle runs at a time.
If a poll cycle takes longer than `polling_interval`, next cycle waits for completion.

```python
class PollingTrigger:
    def __init__(self):
        self._lock = threading.Lock()

    def run_cycle(self):
        with self._lock:
            # Full poll cycle here
            ...
```

### Gmail Quota Awareness

On HTTP 429 response from Gmail API:
1. Parse JSON body for `reason == "rateLimitExceeded"` or `"userRateLimitExceeded"`
2. Log WARNING with quota info
3. Use longer backoff: minimum 60s for quota errors (not exponential from 1s)
4. Fail after 3 retries

Example 429 response body:
```json
{"error": {"errors": [{"reason": "rateLimitExceeded"}], ...}}
```

### Ollama Circuit Breaker

Prevents cascade failures when Ollama is unavailable. Wraps retry logic in `ollama/client.py`.

**Parameters:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `failure_threshold` | 5 | Consecutive failures before opening circuit |
| `open_duration` | 60 seconds | Wait before testing recovery |
| `half_open_max_calls` | 1 | Test calls allowed in half-open state |

**State Machine:**

```
CLOSED ──[5 consecutive failures]──→ OPEN ──[60s elapsed]──→ HALF-OPEN
  ↑                                          ↑                      │
  │                                          └────[1 failure]────────┘
  └────────────────[1 success in half-open]────────────────────────┘
```

**Behavior:**
- CLOSED: Normal operation, failures increment counter, success resets to 0
- OPEN: Skip all Ollama calls for 60s, emails default to IGNORE, log WARNING
- HALF-OPEN: Allow 1 test call, success → CLOSED, failure → OPEN again
- Health check at startup always runs (unaffected by circuit state)

**Implementation:** `src/email_agent/ollama/circuit_breaker.py`

---

## 10. Acceptance Criteria

- [ ] Agent reads unread emails from Gmail INBOX
- [ ] Emails are categorized using Ollama function calling
- [ ] Business rules override layer applies deterministic corrections
- [ ] Gmail labels are created/used correctly (direct naming with normalization)
- [ ] Ollama is called for triage decisions with dynamic category enum from config
- [ ] Important emails get a draft reply created in same thread
- [ ] **NO email is ever sent automatically** (enforced by pre-commit hook + CI)
- [ ] Config is loaded from `config.yaml` with pydantic-settings validation
- [ ] Agent can run continuously or in single-batch mode
- [ ] Dry-run mode works without applying labels/drafts
- [ ] Ollama health check runs at startup
- [ ] Per-email errors are isolated (don't stop entire batch)
- [ ] Two-phase pipeline: Triage → Draft (sequential)
- [ ] Summary logging with action counts at end of each phase
- [ ] Custom exception hierarchy with proper chaining
- [ ] Retry logic uses tenacity with exponential backoff
- [ ] Polling loop runs in separate `trigger/` module
- [ ] Circuit breaker prevents cascade Ollama failures
- [ ] Graceful shutdown completes current operation before exit
- [ ] State tracking persists across runs with TTL cleanup
- [ ] Draft deduplication prevents duplicate drafts in same thread
- [ ] HTML emails are stripped before processing
- [ ] Batch overflow triggers warning log
- [ ] `--clear-state` CLI flag resets processed emails
- [ ] email_age_limit_days=0 emits startup warning
- [ ] Unit tests cover core functionality
- [ ] Code compiles and runs without errors
- [ ] Stress test script generates test emails
- [ ] First-run setup wizard guides user through configuration
- [ ] Complete documentation in `docs/` folder
- [ ] Exit codes: 0=success, 1=config error, 2=Gmail auth error, 3=Ollama error, 4=unexpected (see [docs/usage.md](docs/usage.md#exit-codes))

---

## 11. Future Enhancements (Out of Scope for V1)

- [ ] Gmail Watch API with Pub/Sub for real-time notifications (V2)
- [ ] Support for multiple email providers (Outlook, IMAP)
- [ ] Email summarization before categorization
- [ ] Scheduled summary reports
- [ ] Interactive reply editing in web UI
- [ ] Learning from user corrections
- [ ] Multiple Ollama models
- [ ] Web UI for monitoring and control

---

## 12. Project Configuration

### pyproject.toml

```toml
[project]
name = "email-agent"
version = "0.0.1"
requires-python = ">=3.13"
dependencies = [
    "google-api-python-client>=2.100.0",
    "google-auth-oauthlib>=1.2.0",
    "ollama>=0.5.0",
    "pydantic-settings>=2.0.0",
    "structlog>=24.0.0",
    "tenacity>=8.0.0",
    "beautifulsoup4>=4.12.0",
    "pyyaml>=6.0.0",
]

[project.scripts]
email-agent = "email_agent.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.optional-dependencies]
dev = [
    "pre-commit>=3.0.0",
    "ruff>=0.1.0",
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N"]
```

### "Never Send" Enforcement

Automated enforcement via pre-commit hook + CI:

**.pre-commit-config.yaml** (create in project root):
```yaml
repos:
  - repo: local
    hooks:
      - id: no-send
        name: Forbid .send( calls
        language: pygrep
        entry: '\.send\('
        files: '^src/'
```

**CI Workflow** (`.github/workflows/ci.yml`):
```yaml
- run: ruff check src/
```

### .env.example

```bash
# Path to config file
EMAIL_AGENT_CONFIG=config.yaml

# Enable verbose (DEBUG) logging
EMAIL_AGENT_VERBOSE=1

# Override polling interval (seconds)
EMAIL_AGENT_POLL_INTERVAL=
```

---

## 13. Graceful Shutdown

The agent handles `SIGINT` (Ctrl+C) and `SIGTERM` gracefully:

1. **Signal received** → Set `threading.Event` shutdown flag
2. **Current email** → Completes processing (per-email isolation)
3. **Pipeline phase** → Finishes current phase summary
4. **Exit** → Log final stats, exit with code 0

```python
import signal
import threading

shutdown_event = threading.Event()

def signal_handler(signum, frame):
    LOGGER.info("Shutdown signal received, finishing current operation...")
    shutdown_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

---

## 14. State Tracking

Track processed email IDs to prevent duplicate processing across runs:

**Storage:** `state/processed_emails.json` (simple, no SQLite needed)

**Format:**
```json
{
  "processed": ["msg_id_1", "msg_id_2"],
  "last_processed": "2026-03-19T10:30:00Z"
}
```

**Behavior:**
- On startup: Load processed IDs into memory set
- Before triage: Check if email ID in processed set → skip if yes
- After successful triage: Add email ID to processed set
- On shutdown: Persist processed set to JSON

**Cleanup Policy:**
- On startup: Prune IDs older than `(email_age_limit_days + 7)` days
- Max stored IDs: 10,000 (oldest pruned first if exceeded)
- Corruption handling: If JSON parse fails, log WARNING and start fresh

**CLI Flag:** `--clear-state` to reset processed emails and start fresh.
Confirmation prompt before resetting.

**email_age_limit_days=0 Warning:**
If `email_age_limit_days == 0` at startup:
```python
LOGGER.warning(
    "email_age_limit_days=0: Processing ALL unread emails with no age limit. "
    "This may take a very long time on first run."
)
```

---

## 15. Verbose Logging Restrictions

When `--verbose` is enabled:
- ✅ Log: LLM prompts (truncated), triage decisions, action counts
- ✅ Log: API call metadata (count, timing)
- ❌ Never log: Raw email bodies, full email content
- ❌ Never log: Email addresses in debug output (redact with `***`)
- ❌ Never log: OAuth tokens, API keys, or credentials
- ❌ Never log: Full email IDs in debug traces (use truncated hashes)

---

## 16. Documentation Structure

This document (PLAN.md) is the **single source of truth** for all technical decisions, architecture, and project structure. Other documents serve specific purposes:

| Document | Purpose |
|----------|---------|
| `PLAN.md` | **Technical reference** — architecture, decisions, API contracts, exception hierarchy, pipeline design |
| `build.md` | **Execution todo** — implementation checklist organized by phase, references PLAN.md for details |
| `docs/*.md` | **User-facing documentation** — getting started, configuration, troubleshooting, security |

### Synchronization Rules

- **build.md** references PLAN.md §X for technical details (no duplication)
- **docs/architecture.md** references PLAN.md §5 (pipeline) and §7 (exceptions/retry) — no duplication
- **docs/configuration.md** is standalone (config reference)
- **docs/usage.md** is standalone (CLI usage)
- Any conflict: PLAN.md is authoritative

---

(End of file)
