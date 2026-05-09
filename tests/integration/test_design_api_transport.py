"""Design-contract tests for the api-unify transport layer.

Marker convention enforced by ``scripts/update_feature_map.py``:

- ``Design:`` line points at a heading anchor in the design or reference doc.
- ``Contract:`` line states the observable behavior pinned by the test.

Pin points for the ``api/transport/`` package (DESIGN §3.3-§3.7):

- §3.3 transport policy is frozen and composes auth/retry/circuit/rate-limit.
- §3.4 ApiKeyAuth attaches the key to the configured location.
- §3.5 circuit breaker opens after the configured number of final failures.
- §3.7 HttpTransport retries idempotent ``GET`` until success or exhaustion.
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from typing import Any

import pytest
import responses

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api.transport._auth import ApiKeyAuth, NoAuth
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


class TestPolicyContract:
    """Transport-policy invariants — DESIGN §3.3."""

    def test_policy_is_frozen(self) -> None:
        """``TransportPolicy`` is frozen — mutation must raise.

        Design: docs/archive/features/api-unify/DESIGN.md#33-apitransport_policypy--transport-contract
        Contract: ``TransportPolicy`` is immutable. Reassigning any field
        on an existing instance raises ``FrozenInstanceError`` so accidental
        in-flight mutation cannot drift a long-lived transport's behavior.
        """
        policy = _make_policy()
        with pytest.raises(FrozenInstanceError):
            policy.timeout_seconds = 99.0  # type: ignore[misc]


class TestAuthContract:
    """Auth strategies — DESIGN §3.4."""

    @responses.activate
    def test_api_key_auth_attaches_key_to_query(self) -> None:
        """``ApiKeyAuth(location='query')`` adds the key to every request URL.

        Design: docs/archive/features/api-unify/DESIGN.md#34-apitransport_authpy
        Contract: When the policy carries ``ApiKeyAuth(location='query')``,
        every outbound request URL contains the configured key as a query
        parameter — observable on the recorded request.
        """
        responses.add(responses.GET, re.compile(rf"{BASE}/test"), json={"ok": True})

        transport = HttpTransport(_make_policy(auth=ApiKeyAuth("test-key", location="query")))
        transport.get("/test")
        transport.close()

        request_url = responses.calls[0].request.url or ""
        assert "api_key=test-key" in request_url


class TestCircuitBreakerContract:
    """Circuit breaker — DESIGN §3.5."""

    @responses.activate
    def test_circuit_opens_after_threshold_final_failures(self) -> None:
        """Circuit transitions to OPEN after ``failure_threshold`` final failures.

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

        # The transport wraps a 5xx into ``ApiError`` (provider-level error
        # contract from personalscraper.api._contracts). Pin the precise
        # type so a refactor that swallows the wrap or starts raising a
        # different class surfaces here rather than being masked by a
        # broad ``Exception`` catch.
        with pytest.raises(ApiError):
            transport.get("/down")
        with pytest.raises(ApiError):
            transport.get("/down")

        with pytest.raises(CircuitOpenError, match="Circuit breaker OPEN"):
            transport.get("/down")

        transport.close()


class TestHttpTransportContract:
    """HttpTransport — DESIGN §3.7."""

    @responses.activate
    def test_get_retries_until_success(self) -> None:
        """``GET`` retries on transient 5xx until success.

        Design: docs/archive/features/api-unify/DESIGN.md#37-apitransport_httppy--httptransport
        Contract: HttpTransport.get() honours the policy's retry budget for
        idempotent verbs. After two 503 responses followed by a 200 response,
        the call returns the success body and three HTTP requests are
        recorded — no exception escapes.
        """
        url = f"{BASE}/flaky"
        responses.add(responses.GET, url, json={"error": "boom"}, status=503)
        responses.add(responses.GET, url, json={"error": "boom"}, status=503)
        responses.add(responses.GET, url, json={"ok": True}, status=200)

        retry = RetryPolicy(max_attempts=3, initial_wait=0.001, max_wait=0.01)
        transport = HttpTransport(_make_policy(retry=retry))
        result = transport.get("/flaky")
        transport.close()

        assert isinstance(result, dict)
        assert result["ok"] is True
        assert len(responses.calls) == 3
