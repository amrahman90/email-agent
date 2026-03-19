# Usage Guide

Command-line interface and running modes.

## CLI Commands

### Run Agent (Continuous)

```bash
python -m email_agent [--config <path>]
```

Starts polling loop. Runs until interrupted (Ctrl+C).

### Run Once

```bash
python -m email_agent --once [--config <path>]
```

Process existing unread emails, then exit.

### Dry Run

```bash
python -m email_agent --dry-run [--config <path>]
```

Simulate processing without:
- Creating Gmail labels
- Applying labels to emails
- Creating draft replies

LLM still called for triage decisions (to test classification accuracy).

### Verbose Mode

```bash
python -m email_agent --verbose [--config <path>]
```

Enables DEBUG logging. Shows:
- LLM prompts and responses (truncated)
- Triage decisions
- API call metadata

⚠️ **Warning**: Raw email content may contain PII. Use with caution.

### Combine Options

```bash
python -m email_agent --once --verbose
```

## Interactive Setup

```bash
python -m email_agent setup
```

Runs first-run wizard:
1. Gmail OAuth flow
2. Ollama health check
3. Config generation
4. Label creation

## Reset State

```bash
python -m email_agent --clear-state
```

Resets processed email tracking. Next run will re-evaluate all unread emails.
Confirmation prompt before resetting.

## Windows Script

On Windows, you can use the PowerShell runner script:

```powershell
.\scripts\run_windows.ps1
```

This script:
1. Activates the virtual environment (if using venv)
2. Runs `python -m email_agent`
3. Captures output to `email-agent.log`

## Processing Flow

```
1. Poll Gmail for unread emails
2. For each email:
   a. Triage (categorize + decide action)
   b. Apply business rules
   c. Apply Gmail label
3. For REPLY emails:
   a. Generate draft reply
   b. Create draft in same thread
4. Log summary statistics
```

## Output Log Format

JSON structured logs to `email-agent.log`:

```json
{
  "event": "phase_summary",
  "phase": "triage",
  "total": 10,
  "IGNORE": 5,
  "REPLY": 3,
  "SUSPICIOUS": 2
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Config error |
| 2 | Gmail auth error |
| 3 | Ollama error |
| 4 | Unexpected error |

## Keyboard Interrupt

Press `Ctrl+C` to gracefully stop. Current email processing completes before exit.
