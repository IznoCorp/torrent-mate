"""Regression tests for ``_eligible()`` strict allowlist (sub-phase 6.1).

Verifies the three no-circuit eligibility categories:

1. **Documented no-circuit providers** (IMDb / RottenTomatoes façades) — allowed.
2. **Test fakes** (classes with ``_registry_test_fake: ClassVar[bool] = True``) — allowed.
3. **Unknown real provider without circuit** — rejected with a warning.

Plus one regression test (Phase 26.1 / C1) that exercises a real CircuitBreaker.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

from personalscraper.api.metadata.registry._factory import _eligible
from personalscraper.core.circuit import CircuitBreaker, CircuitState


def test_eligible_unknown_provider_no_circuit_rejected(caplog):
    """Real provider without .circuit AND not in allowlist → excluded, logs WARNING."""

    class _UnknownProvider:
        provider_name: ClassVar[str] = "unknown_provider"
        # no .circuit attribute, not in allowlist

    with caplog.at_level("WARNING", logger="personalscraper.api.metadata.registry._factory"):
        result = _eligible(_UnknownProvider())

    assert result is False
    assert any("registry_provider_no_circuit" in r.message for r in caplog.records)


def test_eligible_imdb_facade_no_circuit_allowed():
    """IMDb façade (no circuit, shared with OMDb) → eligible per allowlist."""

    class _ImdbFacade:
        provider_name: ClassVar[str] = "imdb"

    assert _eligible(_ImdbFacade()) is True


def test_eligible_fake_class_no_circuit_allowed():
    """Test fake class (_registry_test_fake marker, no circuit) → eligible."""

    class FakeProvider:
        provider_name: ClassVar[str] = "fake_test"
        _registry_test_fake: ClassVar[bool] = True  # explicit opt-in marker

    assert _eligible(FakeProvider()) is True


def test_eligible_real_circuit_open_rejected() -> None:
    """Regression for C1: _eligible must reject a real CircuitBreaker in OPEN state.

    Before the fix, _eligible did ``state != "OPEN"`` (string comparison), which
    always returned True for the enum value ``CircuitState.OPEN`` (whose value is
    the lowercase string ``"open"``). This test instantiates a real CircuitBreaker,
    drives it to OPEN, and verifies _eligible returns False.
    """
    from requests.exceptions import ConnectionError as RequestsConnectionError

    breaker = CircuitBreaker(
        name="test_provider",
        failure_threshold=1,
        cooldown_seconds=60.0,
        event_bus=SimpleNamespace(emit=lambda e: None),
    )
    # Trip the breaker: one failure with threshold=1 opens the circuit.
    breaker.record_failure(RequestsConnectionError("simulated outage"))
    assert breaker.state is CircuitState.OPEN, f"breaker did not open: {breaker.state}"

    class _RealCircuitProvider:
        provider_name = "test_provider"

        def __init__(self, c: CircuitBreaker) -> None:
            self.circuit = c

    p = _RealCircuitProvider(breaker)
    assert _eligible(p) is False, "regression: _eligible accepted OPEN real CircuitBreaker"
