"""Test suite for email-agent.

Tests are organized by module:
    - test_settings.py: Config validation tests
    - test_gmail_client.py: Gmail API client tests
    - test_ollama_client.py: Ollama API client tests
    - test_circuit_breaker.py: Circuit breaker state machine tests
    - test_state_tracker.py: State tracking + TTL cleanup tests
    - test_triage.py: Triage + business rules tests
    - test_importance.py: Importance assessment tests
    - test_pipeline.py: Integration tests (mocked)
    - test_exceptions.py: Exception hierarchy tests

Fixtures are defined in conftest.py.

See docs/testing.md for testing guide.
"""
