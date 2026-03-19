# Testing Guide

How to test Email Agent.

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_triage.py

# Run with coverage
pytest --cov=src/email_agent

# Run verbose
pytest -v
```

## Test Structure

```
tests/
├── conftest.py            # Pytest fixtures
├── fixtures/              # Sample email JSON files
├── test_settings.py       # Config validation
├── test_gmail_client.py   # Gmail client
├── test_ollama_client.py  # Ollama client
├── test_circuit_breaker.py # Circuit breaker state machine
├── test_state_tracker.py  # State tracking + TTL cleanup
├── test_triage.py         # Triage + business rules
├── test_importance.py     # Importance assessment
├── test_pipeline.py       # Integration tests
└── test_exceptions.py     # Exception hierarchy
```

## Fixtures

### `sample_email`

Mock email payload:

```python
@pytest.fixture
def sample_email():
    return {
        "id": "123",
        "threadId": "abc",
        "subject": "Test Email",
        "from": "sender@example.com",
        "body": "Email body text",
    }
```

### `mock_gmail_client`

Mocked Gmail client for integration tests.

### `mock_ollama_response`

Mock Ollama responses for testing LLM integration.

## Writing Tests

### Unit Test Example

```python
def test_label_normalization():
    from email_agent.gmail.labels import normalize_label_name

    assert normalize_label_name("Work") == "work"
    assert normalize_label_name("🔥 Work") == "work"
```

### Integration Test Example

```python
def test_pipeline_with_mocked_apis(mock_gmail_client, mock_ollama):
    from email_agent.workflows.pipeline import Pipeline

    pipeline = Pipeline(gmail=mock_gmail_client, ollama=mock_ollama)
    results = pipeline.run_triage_phase(emails)

    assert len(results) > 0
```

## Mocking

### Mock Ollama

```python
@pytest.fixture
def mock_ollama(mocker):
    return mocker.patch("email_agent.ollama.client.OllamaClient.call")
```

### Mock Gmail

```python
@pytest.fixture
def mock_gmail(mocker):
    return mocker.patch("email_agent.gmail.client.GmailClient")
```

## Test Data

Create `tests/fixtures/` directory with sample email JSON files for testing.

## Coverage

Run with coverage:

```bash
pytest --cov=src/email_agent --cov-report=html
```

View HTML report at `htmlcov/index.html`.

## Stress Testing

Generate test emails:

```bash
python scripts/stress_test.py
```
