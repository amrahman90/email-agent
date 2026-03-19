# Changelog

All notable changes to this project.

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

## Technical Decisions

| Feature | Decision |
|---------|----------|
| Config Format | YAML + pydantic-settings |
| LLM Structured Output | Function calling |
| Processing | Sequential |
| Orchestration | workflows/pipeline.py |
| Exception Handling | Custom hierarchy |
| Retry | tenacity |

## Known Limitations

- Polling only (no Gmail Watch)
- Gmail only (no Outlook/IMAP)
- Single Ollama model
- Sequential processing (no concurrency)
