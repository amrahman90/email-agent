# Email Agent

**Desktop AI agent that reads Gmail unread emails, categorizes them using Ollama LLM, and creates draft replies for important emails.**

> **Core principle:** Emails are never sent automatically. All drafts are created for human review.

## Features

- **Smart Triage** — Classifies emails into user-defined categories (Work, Personal, Finance, etc.) using Ollama function calling
- **Importance Assessment** — Scores emails and creates draft replies for important ones
- **Business Rules** — Phishing detection, travel itinerary handling, low-confidence downgrades
- **Draft Deduplication** — Prevents duplicate drafts in the same thread
- **Circuit Breaker** — Protects against cascade failures when Ollama is unavailable
- **Graceful Shutdown** — Completes current operation on SIGINT/SIGTERM
- **Dry-Run Mode** — Simulate without applying labels or creating drafts
- **Verbose Logging** — Structured JSON logs with configurable verbosity

## Prerequisites

- Python 3.13+
- [Ollama](https://ollama.com) with `llama3.2:1b` model
- Gmail account with [Gmail API access](docs/gmail-setup.md)

## Quick Start

```bash
# Install dependencies
cd email-agent
uv sync

# Run interactive setup (creates config.yaml, authenticates Gmail)
python -m email_agent setup

# Start the agent (continuous polling)
python -m email_agent

# Or run once and exit
python -m email_agent --once
```

## Installation

See [docs/installation.md](docs/installation.md) for detailed installation steps including:
- Ollama setup and model installation
- Gmail API OAuth configuration
- First-run setup wizard

## Configuration

Copy `config.yaml.example` to `config.yaml`:

```yaml
gmail:
  credentials_path: "credentials/credentials.json"
  token_path: "credentials/token.json"

ollama:
  base_url: "http://localhost:11434"
  model: "llama3.2:1b"
  timeout: 120

agent:
  categories:
    - "Work"
    - "Personal"
    - "Finance"
  important_senders:
    - "boss@company.com"
  importance_threshold: "medium"   # low | medium | high
  max_emails_per_batch: 50
  email_age_limit_days: 7
  polling_interval: 60
```

See [docs/configuration.md](docs/configuration.md) for full reference.

## Usage

| Command | Description |
|---------|-------------|
| `python -m email_agent` | Continuous mode (polls every 60s) |
| `python -m email_agent --once` | Process emails once, then exit |
| `python -m email_agent --dry-run` | Simulate without applying changes |
| `python -m email_agent --verbose` | DEBUG logging |
| `python -m email_agent --clear-state` | Reset processed email state |
| `python -m email_agent setup` | Run interactive setup wizard |
| `python -m email_agent health` | Check Gmail/Ollama connectivity |

See [docs/usage.md](docs/usage.md) for all CLI options and exit codes.

## Project Structure

```
email-agent/
├── src/email_agent/           # Source code
│   ├── config/                 # Settings and YAML loading
│   ├── gmail/                  # Gmail API client
│   ├── models/                 # Data models (Email, TriageDecision, DraftReply)
│   ├── ollama/                 # Ollama client + circuit breaker
│   ├── processor/              # Triage, importance, draft generation
│   ├── workflows/              # Two-phase pipeline orchestrator
│   ├── trigger/                # Polling loop
│   └── exceptions/             # Custom exception hierarchy
├── scripts/                    # Utility scripts (setup, stress test)
├── tests/                      # 103 passing tests
├── docs/                       # User & developer documentation
├── config.yaml.example         # Configuration template
├── .env.example                # Environment variables template
└── pyproject.toml              # Project configuration
```

## Architecture

Email Agent uses a two-phase pipeline:

1. **Triage Phase** — Fetches unread emails, runs Ollama function calling to classify, applies business rule overrides, labels emails
2. **Draft Phase** — Filters REPLY-actioned emails, checks importance threshold, creates draft replies in same thread

See [docs/architecture.md](docs/architecture.md) for full architecture details.

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run python -m ruff check

# Type check
uv run python -m mypy

# Install pre-commit hooks
uv run pre-commit install
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | 5-minute quick start |
| [Installation](docs/installation.md) | Detailed installation |
| [Configuration](docs/configuration.md) | config.yaml reference |
| [Usage](docs/usage.md) | CLI commands |
| [Gmail Setup](docs/gmail-setup.md) | Gmail API OAuth setup |
| [Ollama Setup](docs/ollama-setup.md) | Ollama installation |
| [Troubleshooting](docs/troubleshooting.md) | Common issues |
| [Architecture](docs/architecture.md) | System design |
| [Testing](docs/testing.md) | Testing guide |
| [Security](docs/security.md) | Security best practices |

## License

MIT
