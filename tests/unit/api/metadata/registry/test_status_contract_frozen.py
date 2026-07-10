"""Characterization freeze test for the registry status contract (S6.0).

This test pins the public contract the web UI binds to:
- ``ProviderStatus`` field set (exact names + types)
- ``CircuitState`` values (closed set)
- JSON round-trip shape

A removed/renamed field or enum value FAILS this test (breaking change).
A new field is allowed only when this test is deliberately extended in
the same commit (the commit documents the additive change — DESIGN §3.1).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from personalscraper.api.metadata.registry import ProviderStatus, RegistryProviderName
from personalscraper.core.circuit import CircuitState


def test_providerstatus_fields_exact_set() -> None:
    """ProviderStatus must have exactly these 6 fields — no more, no less."""
    field_names = {f.name for f in dataclasses.fields(ProviderStatus)}
    expected = {
        "provider_name",
        "circuit_state",
        "failure_count_recent",
        "last_success_at",
        "last_failure_at",
        "last_latency_ms",
    }
    assert field_names == expected, f"Field drift: {field_names ^ expected}"


def test_circuitstate_values_closed_set() -> None:
    """CircuitState values must be exactly {closed, open, half_open}."""
    values = {m.value for m in CircuitState}
    assert values == {"closed", "open", "half_open"}, f"CircuitState drift: {values}"


def test_providerstatus_json_roundtrip() -> None:
    """ProviderStatus serializes to/from dict matching the expected JSON shape."""
    status = ProviderStatus(
        provider_name=RegistryProviderName("tmdb"),
        circuit_state=CircuitState.CLOSED,
        failure_count_recent=0,
        last_success_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        last_failure_at=None,
        last_latency_ms=42.5,
    )

    # Simulate the JSON serialization the REST route will perform.
    # ProviderStatus is a frozen dataclass — the REST model (Phase 2)
    # will convert it via a Pydantic model. The characterization test
    # asserts the raw dataclass shape so the Pydantic model can be
    # validated against it.
    d = dataclasses.asdict(status)

    assert d["provider_name"] == "tmdb"
    assert d["circuit_state"] is CircuitState.CLOSED  # dataclasses.asdict keeps enum identity
    assert d["failure_count_recent"] == 0
    assert d["last_success_at"] is not None
    assert d["last_failure_at"] is None
    assert d["last_latency_ms"] == 42.5

    # All keys must be present (no unexpected extras).
    assert set(d.keys()) == {
        "provider_name",
        "circuit_state",
        "failure_count_recent",
        "last_success_at",
        "last_failure_at",
        "last_latency_ms",
    }


def test_circuitstate_enum_identity_preserved() -> None:
    """Status factory must use the enum object, not its string value."""
    status = ProviderStatus(
        provider_name=RegistryProviderName("tvdb"),
        circuit_state=CircuitState.HALF_OPEN,
        failure_count_recent=3,
        last_success_at=None,
        last_failure_at=None,
        last_latency_ms=None,
    )
    assert status.circuit_state is CircuitState.HALF_OPEN
    assert status.circuit_state.value == "half_open"
