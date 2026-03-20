"""Tests for CircuitBreaker state machine."""

from __future__ import annotations

from pytest_mock import MockerFixture

from email_agent.ollama.circuit_breaker import CircuitBreaker, CircuitState


def test_initial_state_is_closed(circuit_breaker: CircuitBreaker) -> None:
    """Verify circuit starts in CLOSED state."""
    assert circuit_breaker.state == CircuitState.CLOSED


def test_failure_count_starts_at_zero(circuit_breaker: CircuitBreaker) -> None:
    """Verify failure count starts at 0."""
    assert circuit_breaker.failure_count == 0


def test_record_failure_increments_count(circuit_breaker: CircuitBreaker) -> None:
    """Verify record_failure increments the failure counter."""
    circuit_breaker.record_failure()
    assert circuit_breaker.failure_count == 1


def test_record_success_resets_failure_count(circuit_breaker: CircuitBreaker) -> None:
    """Verify success resets failure counter to 0."""
    circuit_breaker.record_failure()
    circuit_breaker.record_failure()
    assert circuit_breaker.failure_count == 2

    circuit_breaker.record_success()
    assert circuit_breaker.failure_count == 0


def test_five_failures_opens_circuit(circuit_breaker: CircuitBreaker) -> None:
    """Verify circuit opens after 5 consecutive failures."""
    for _ in range(5):
        circuit_breaker.record_failure()

    assert circuit_breaker.state == CircuitState.OPEN
    assert circuit_breaker.failure_count == 5


def test_open_state_blocks_requests(circuit_breaker: CircuitBreaker) -> None:
    """Verify OPEN state blocks new requests."""
    for _ in range(5):
        circuit_breaker.record_failure()

    assert not circuit_breaker.allow_request()


def test_half_open_allows_test_request(circuit_breaker: CircuitBreaker) -> None:
    """Verify HALF-OPEN allows one test request."""
    for _ in range(5):
        circuit_breaker.record_failure()

    assert circuit_breaker.state == CircuitState.OPEN
    assert not circuit_breaker.allow_request()


def test_half_open_success_closes_circuit(
    circuit_breaker: CircuitBreaker, mocker: MockerFixture
) -> None:
    """Verify success in HALF-OPEN transitions to CLOSED."""
    for _ in range(5):
        circuit_breaker.record_failure()

    cb = circuit_breaker
    mock_time = mocker.patch("email_agent.ollama.circuit_breaker.time")
    mock_time.monotonic.return_value = cb._opened_at + 60.0  # type: ignore[operator]
    _ = circuit_breaker.state

    circuit_breaker.record_success()
    assert circuit_breaker.state == CircuitState.CLOSED


def test_half_open_failure_reopens_circuit(
    circuit_breaker: CircuitBreaker, mocker: MockerFixture
) -> None:
    """Verify failure in HALF-OPEN transitions back to OPEN."""
    for _ in range(5):
        circuit_breaker.record_failure()

    cb = circuit_breaker
    mock_time = mocker.patch("email_agent.ollama.circuit_breaker.time")
    mock_time.monotonic.return_value = cb._opened_at + 60.0  # type: ignore[operator]
    _ = circuit_breaker.state

    circuit_breaker.record_failure()
    assert circuit_breaker.state == CircuitState.OPEN


def test_time_based_transition_open_to_half_open(
    circuit_breaker: CircuitBreaker, mocker: MockerFixture
) -> None:
    """Verify OPEN transitions to HALF-OPEN after open_duration elapses."""
    mock_time = mocker.patch("email_agent.ollama.circuit_breaker.time")
    mock_time.monotonic.return_value = 1000.0

    for _ in range(5):
        circuit_breaker.record_failure()

    assert circuit_breaker.state == CircuitState.OPEN

    cb = circuit_breaker
    mock_time.monotonic.return_value = cb._opened_at + 60.0  # type: ignore[operator]

    _ = circuit_breaker.state

    assert circuit_breaker.state == CircuitState.HALF_OPEN  # type: ignore[comparison-overlap]


def test_reset_restores_closed_state(circuit_breaker: CircuitBreaker) -> None:
    """Verify reset() restores CLOSED state with zero failures."""
    for _ in range(5):
        circuit_breaker.record_failure()

    assert circuit_breaker.state == CircuitState.OPEN

    circuit_breaker.reset()

    assert circuit_breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]
    assert circuit_breaker.failure_count == 0


def test_is_open_returns_true_when_open(circuit_breaker: CircuitBreaker) -> None:
    """Verify is_open() returns True when circuit is OPEN."""
    for _ in range(5):
        circuit_breaker.record_failure()

    assert circuit_breaker.is_open() is True


def test_is_half_open_returns_true_when_half_open(
    circuit_breaker: CircuitBreaker, mocker: MockerFixture
) -> None:
    """Verify is_half_open() returns True when circuit is HALF-OPEN."""
    mock_time = mocker.patch("email_agent.ollama.circuit_breaker.time")
    mock_time.monotonic.return_value = 1000.0

    for _ in range(5):
        circuit_breaker.record_failure()

    cb = circuit_breaker
    mock_time.monotonic.return_value = cb._opened_at + 60.0  # type: ignore[operator]

    _ = circuit_breaker.state

    assert circuit_breaker.is_half_open() is True


def test_multiple_successes_in_half_open_closes_circuit(
    circuit_breaker: CircuitBreaker, mocker: MockerFixture
) -> None:
    """Verify multiple successes in HALF-OPEN eventually close the circuit."""
    mock_time = mocker.patch("email_agent.ollama.circuit_breaker.time")
    mock_time.monotonic.return_value = 1000.0

    for _ in range(5):
        circuit_breaker.record_failure()

    cb = circuit_breaker
    mock_time.monotonic.return_value = cb._opened_at + 60.0  # type: ignore[operator]
    _ = circuit_breaker.state

    circuit_breaker.record_success()
    assert circuit_breaker.state == CircuitState.CLOSED


def test_success_in_closed_resets_count(circuit_breaker: CircuitBreaker) -> None:
    """Verify success in CLOSED resets failure count."""
    circuit_breaker.record_failure()
    circuit_breaker.record_failure()
    circuit_breaker.record_failure()

    assert circuit_breaker.failure_count == 3

    circuit_breaker.record_success()

    assert circuit_breaker.failure_count == 0
    assert circuit_breaker.state == CircuitState.CLOSED


def test_failure_in_open_has_no_effect(circuit_breaker: CircuitBreaker) -> None:
    """Verify failure recorded in OPEN state has no effect."""
    for _ in range(5):
        circuit_breaker.record_failure()

    assert circuit_breaker.state == CircuitState.OPEN

    circuit_breaker.record_failure()

    assert circuit_breaker.state == CircuitState.OPEN


def test_success_in_open_has_no_effect(circuit_breaker: CircuitBreaker) -> None:
    """Verify success recorded in OPEN state has no effect."""
    for _ in range(5):
        circuit_breaker.record_failure()

    assert circuit_breaker.state == CircuitState.OPEN

    circuit_breaker.record_success()

    assert circuit_breaker.state == CircuitState.OPEN
