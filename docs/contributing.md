# Contributing

Development guide for Email Agent.

## Setting Up Development Environment

### 1. Clone Repository

```bash
git clone <repo-url>
cd email-agent
```

### 2. Install Dependencies

```bash
uv sync --extra dev
```

### 3. Install Pre-commit

```bash
uv run pre-commit install
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/my-feature
```

### 2. Make Changes

Format code with Ruff (required):
- `ruff check src/` — lint
- `ruff format src/` — format

Follow code style:
- Use type hints
- Add docstrings
- Follow existing patterns

### 3. Run Tests

```bash
pytest
```

### 4. Run Linting

```bash
uv run ruff check src/
uv run ruff format src/
```

### 5. Commit

Pre-commit hooks run automatically:
- Ruff linting
- No `.send(` calls allowed

## Code Style

### Type Hints

Required for all functions:

```python
def process_email(email_id: str, config: Settings) -> TriageDecision:
    ...
```

### Docstrings

Follow Google style:

```python
def triage_email(email: Email) -> TriageDecision:
    """Triage an email using LLM and business rules.
    
    Args:
        email: The email to triage.
        
    Returns:
        TriageDecision with action, category, and confidence.
    """
    ...
```

### Error Handling

- Use custom exceptions
- Log with structlog
- Don't expose internals in errors

## Project Structure

See [PLAN.md §4 Project Structure](PLAN.md#4-project-structure) for the complete module inventory.

## Testing

### Write Tests

- Unit tests for each module
- Integration tests for workflows
- Mock external APIs

### Test Commands

```bash
# All tests
pytest

# With coverage
pytest --cov=src/email_agent

# Specific file
pytest tests/test_triage.py -v
```

## Pull Request Process

1. Fork repository
2. Create feature branch
3. Make changes with tests
4. Ensure linting passes
5. Submit pull request

## Reporting Issues

Include:
- Python version
- Ollama version
- Full error trace
- `config.yaml` (remove sensitive data)
- Steps to reproduce
