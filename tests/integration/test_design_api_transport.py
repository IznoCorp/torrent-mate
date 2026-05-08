"""Design-contract tests for the api-unify transport layer.

Marker convention enforced by ``scripts/update_feature_map.py``:

- ``Design:`` line points at a heading anchor in the design or reference doc.
- ``Contract:`` line states the observable behavior pinned by the test.

Bootstrap test for Phase 4 of the ``test-coverage`` feature: validates the
DESIGN §3.5 ``core/circuit.py`` clause that the breaker opens after the
configured threshold of *final* failures and short-circuits subsequent
requests with ``CircuitOpenError``.
"""

from __future__ import annotations

from typing import Any

import pytest
import responses

from personalscraper.api._contracts import CircuitOpenError
from personalscraper.api.transport._auth import NoAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RetryPolicy,
    TransportPolicy,
)

BASE = "http://test-api.example.com"


def _make_policy(**overrides: Any) -> TransportPolicy:
    """Build a TransportPolicy with sensible bootstrap defaults."""
    kwargs: dict[str, Any] = {
        "provider_name": "TestAPI",
        "base_url": BASE,
        "auth": NoAuth(),
        "retry": RetryPolicy(max_attempts=1, initial_wait=0.001, max_wait=0.01),
        "circuit": CircuitPolicy(failure_threshold=2, cooldown_seconds=0.1, count_retries=False),
    }
    kwargs.update(overrides)
    return TransportPolicy(**kwargs)


class TestCircuitBreakerContract:
    """Design-contract tests for the circuit breaker."""

    @responses.activate
    def test_circuit_opens_after_threshold_final_failures(self) -> None:
        """Circuit transitions to OPEN after `failure_threshold` final failures.

        Design: docs/archive/features/api-unify/DESIGN.md#35-corecircuitpy
        Contract: After ``CircuitPolicy.failure_threshold`` final (post-retry)
        failures the circuit transitions from CLOSED to OPEN. Requests issued
        within the cooldown window short-circuit with ``CircuitOpenError``
        without reaching the underlying transport.
        """
        url = f"{BASE}/down"
        for _ in range(2):
            responses.add(responses.GET, url, json={"error": "down"}, status=500)

        transport = HttpTransport(_make_policy())

        with pytest.raises(Exception):
            transport.get("/down")
        with pytest.raises(Exception):
            transport.get("/down")

        # Circuit is now OPEN — next call short-circuits without hitting the
        # mock server (no extra ``responses.add(...)`` registered).
        with pytest.raises(CircuitOpenError, match="Circuit breaker OPEN"):
            transport.get("/down")

        transport.close()
