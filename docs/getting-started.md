# Getting Started

Get up and running with Email Agent in 5 minutes.

## Prerequisites

- Python 3.13+
- [Ollama](https://ollama.com) installed with `llama3.2:1b` model
- Gmail account with Gmail API access

## Quick Setup

### 1. Install Dependencies

```bash
cd email-agent
uv sync
```

### 2. Run Interactive Setup

```bash
python -m email_agent setup
```

This will:
- Guide you through Gmail OAuth setup
- Create initial `config.yaml`
- Verify Ollama connection

### 3. Edit Configuration

Open `config.yaml` and customize:

```yaml
agent:
  categories:
    - "Work"
    - "Personal"
    - "Finance"
  important_senders:
    - "boss@company.com"
    - "@family.com"
```

### 4. Run the Agent

```bash
python -m email_agent
```

## Running Modes

| Mode | Command | Description |
|------|---------|-------------|
| Continuous | `python -m email_agent` | Polls every 60 seconds |
| Once | `python -m email_agent --once` | Process emails, then exit |
| Dry Run | `python -m email_agent --dry-run` | Simulate without changes |
| Verbose | `python -m email_agent --verbose` | DEBUG logging |

## Next Steps

- [Full Installation Guide](installation.md) - Detailed setup
- [Configuration Reference](configuration.md) - All config options
- [Usage Guide](usage.md) - All CLI commands
