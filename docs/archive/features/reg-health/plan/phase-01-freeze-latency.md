# Phase 1 — S6.0 contract freeze + latency field

## Gate

```bash
make check
```

Must be fully green (lint, test, module-size, typed-api guardrails). Additionally,
the new characterization freeze test must pass:

```bash
pytest tests/api/metadata/registry/test_status_contract_frozen.py -v
```

Expected: all assertions pass (field set, CircuitState values, JSON round-trip).

## Objectives

1. Add `last_latency_ms: float | None` to `ProviderStatus` — an **additive** field
   that is safe under the freeze contract (DESIGN §3.2).
2. Instrument the circuit-breaker `record_success` / `record_failure` boundary in
   the HTTP transport to record wall-clock latency on the circuit object, so that
   `ProviderRegistry.status()` can read it back.
3. Update `ProviderRegistry.status()` to populate `last_latency_ms` from the
   circuit's new attribute.
4. Create a **characterization freeze test** that pins the public contract the
   web surface binds to: exact `ProviderStatus` field set, exact `CircuitState`
   values, and JSON round-trip shape (DESIGN §3.1).

## Files to create

- `tests/api/metadata/registry/test_status_contract_frozen.py`

## Files to modify

- `personalscraper/api/metadata/registry/__init__.py`
  - `ProviderStatus` dataclass (line ~146-166): add `last_latency_ms: float | None`
  - `ProviderRegistry.status()` (line ~605-626): add `last_latency_ms` to the
    `ProviderStatus(...)` constructor call, reading it from
    `getattr(circuit, "last_latency_ms", None)`.

- `personalscraper/core/circuit.py`
  - `CircuitBreaker.__init__` (line ~115-151): add `self._last_latency_ms: float | None = None`.
  - `CircuitBreaker.record_success` (line ~204-226): add `self._last_latency_ms: float | None`
    attribute gettable by the registry status() method. The field is set by the
    transport wrapper, not here — the transport owns the timing measurement
    (it wraps the actual HTTP call and records the delta).
  - `CircuitBreaker.record_failure` (line ~228-285): likewise, the transport sets
    `_last_latency_ms` before or after calling `record_failure`. No change
    inside `record_failure` itself — the transport sets the attribute.

- `personalscraper/api/transport/_http.py`
  - `_do_request` method (line ~285-306): wrap the `_attempt()` call with
    `time.monotonic()` before and after, record the delta on the circuit
    object as `circuit._last_latency_ms = (end - start) * 1000.0`
    **before** calling `record_success` / `record_failure`, so regardless
    of outcome the latency is visible.

### Exact code changes

#### 1. `ProviderStatus` — add field (registry/**init**.py:146-166)

Add `last_latency_ms: float | None` after `last_failure_at: datetime | None`:

```python
@dataclass(frozen=True)
class ProviderStatus:
    provider_name: RegistryProviderName
    circuit_state: CircuitState
    failure_count_recent: int
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_latency_ms: float | None
```

#### 2. `ProviderRegistry.status()` — populate new field (registry/**init**.py:619-625)

Add the latency kwarg to the `ProviderStatus(...)` constructor:

```python
result[name] = ProviderStatus(
    provider_name=RegistryProviderName(name),
    circuit_state=state_value,
    failure_count_recent=(getattr(circuit, "failure_count_recent", 0) if circuit else 0),
    last_success_at=(getattr(circuit, "last_success_at", None) if circuit else None),
    last_failure_at=(getattr(circuit, "last_failure_at", None) if circuit else None),
    last_latency_ms=(getattr(circuit, "_last_latency_ms", None) if circuit else None),
)
```

#### 3. CircuitBreaker init — add attribute (circuit.py:~146)

```python
self._last_latency_ms: float | None = None
```

#### 4. Transport instrumentation (_http.py:~298-306)

```python
import time as _time_mod

start = _time_mod.monotonic()
try:
    result = _attempt()
except (ApiError, requests.RequestException) as exc:
    elapsed_ms = (_time_mod.monotonic() - start) * 1000.0
    circuit._last_latency_ms = elapsed_ms
    if not self._policy.circuit.count_retries:
        circuit.record_failure(exc)
    raise

elapsed_ms = (_time_mod.monotonic() - start) * 1000.0
circuit._last_latency_ms = elapsed_ms
circuit.record_success()
return result
```

## Characterization freeze test

Create `tests/api/metadata/registry/test_status_contract_frozen.py`:

```python
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
import json
from datetime import datetime, timezone

from personalscraper.api.metadata.registry import ProviderStatus, RegistryProviderName
from personalscraper.core.circuit import CircuitState


def test_providerstatus_fields_exact_set():
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


def test_circuitstate_values_closed_set():
    """CircuitState values must be exactly {closed, open, half_open}."""
    values = {m.value for m in CircuitState}
    assert values == {"closed", "open", "half_open"}, f"CircuitState drift: {values}"


def test_providerstatus_json_roundtrip():
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
    assert d["circuit_state"] == "closed"  # Enum .value, not the enum object
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


def test_circuitstate_enum_identity_preserved():
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
```

## Gotchas

- **CircuitState.state self-mutation on read**: reading `CircuitBreaker.state`
  auto-transitions `OPEN → HALF_OPEN` after cooldown (emits `CircuitBreakerHalfOpened`).
  The `status()` method reads `.state` — this side effect is already present and
  is DESIGN_CONFORM. The REST route (Phase 2) will also hit this path. Do NOT
  try to suppress the transition — it is how the half-open probe works.

- **Additive-only**: the freeze test is a guard, not runtime code. It makes
  "additive-only" a checkable invariant. A new field requires extending the
  test in the same commit; a removed/renamed field or CircuitState value fails
  the test (breaking change).

- **`time.monotonic()` for latency**: use `time.monotonic()` (not `time.time()`)
  for the wall-clock delta around the provider call — it is immune to clock
  adjustments. The stored `last_latency_ms` is a float in milliseconds.

- **`_last_latency_ms` is internal**: the attribute on `CircuitBreaker` is
  prefixed `_` because it is set by the transport layer, not by the breaker
  itself. The registry `status()` method reads it via `getattr`. This is
  intentional — the breaker owns circuit logic, not timing.

- **No `last_success_at` / `last_failure_at` on CircuitBreaker**: those fields
  are already read via `getattr(circuit, "last_success_at", None)` in `status()`
  with safe defaults. Phase 1 does NOT add them to `CircuitBreaker` — they are
  pre-existing on a per-transport subclass/wrapper. The characterization test
  covers them on `ProviderStatus` (the public face), not on the breaker internals.
