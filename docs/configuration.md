# Configuration Reference

Complete reference for `config.yaml`.

## Full Example

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
    - "Social"
    - "Promotions"
    - "Spam"
  important_senders:
    - "boss@company.com"
    - "hr@company.com"
    - "@family.com"
  importance_threshold: "medium"
  max_emails_per_batch: 50
  email_age_limit_days: 7
  draft_reply_max_length: 500
  polling_interval: 60
```

## Sections

### `gmail`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `credentials_path` | string | `credentials/credentials.json` | OAuth2 credentials file |
| `token_path` | string | `credentials/token.json` | OAuth2 token storage |

### `ollama`

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `base_url` | string | `http://localhost:11434` | Valid URL | Ollama API endpoint |
| `model` | string | `llama3.2:1b` | Non-empty | Model to use |
| `timeout` | int | 120 | 10-300 seconds | Request timeout |

### `agent`

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `categories` | list[str] | required | 1-20 unique | Email categories (Gmail labels) |
| `important_senders` | list[str] | required | Non-empty | Emails/domains that always get draft replies |
| `importance_threshold` | string | `medium` | low/medium/high | Minimum importance level (gates draft creation) |
| `max_emails_per_batch` | int | 50 | 1-100 | Max emails per polling cycle |
| `email_age_limit_days` | int | 7 | 0-365 | ⚠️ Only process emails newer than this (0=no limit - processes ALL historical emails) |
| `draft_reply_max_length` | int | 500 | 50-2000 words | Max words in draft reply |
| `polling_interval` | int | 60 | 10-3600 seconds | Seconds between polls |

## Validation Rules

All fields are validated at startup. Invalid config causes immediate exit with clear error messages.

### Categories

- Must be unique (case-insensitive)
- Max 20 categories
- Emoji/unicode are normalized

### Important Senders

- Email addresses: `user@example.com`
- Domains: `@example.com` (matches all from domain)
- Case-insensitive matching
- Uses `email.utils.parseaddr()` to safely extract email addresses (avoids display-name injection)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `EMAIL_AGENT_CONFIG` | Path to config file (default: `config.yaml`) |
| `EMAIL_AGENT_VERBOSE` | Set to `1` for DEBUG logging |

## Fail-Fast Behavior

| Error | Behavior |
|-------|----------|
| Missing `credentials.json` | Exit with error |
| Invalid YAML | Exit with parse error |
| Validation failure | Exit with field errors |
| Ollama unreachable | Exit with connection error |
