# Phase 1 — Event contract: schema_version + registry events

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> or `superpowers:executing-plans` to implement this phase step-by-step.

**Goal:** Unify the event substrate — add `schema_version` to the `Event` base and bring
the 5 registry events onto the `Event` contract so they are auto-registered, envelope-round-trippable,
and delivered to base-`Event` subscribers.

**Architecture:** Minimal, additive changes to `core/event_bus.py` and
`api/metadata/registry/_events.py`. The 5 event classes get `kw_only=True` and subclass `Event`.
A new eager-import line in `events/__init__.py` triggers auto-registration. Two architecture tests
lock in the invariants.

**Tech Stack:** Python dataclasses (`frozen=True, kw_only=True`), pytest, `rg` (ripgrep with `-t py`).

---

## Gate (pre-conditions from previous phase)

_Phase 1 has no predecessor. Pre-conditions: branch `feat/arch-cleanup-2` is checked out and
`make check` is green on HEAD._

```bash
git branch --show-current   # must print: feat/arch-cleanup-2
make check                  # must exit 0
```

---

## Files

| Action | Path                                                              |
| ------ | ----------------------------------------------------------------- |
| Modify | `personalscraper/core/event_bus.py`                               |
| Modify | `personalscraper/api/metadata/registry/_events.py`                |
| Modify | `personalscraper/api/metadata/registry/__init__.py`               |
| Modify | `personalscraper/events/__init__.py`                              |
| Create | `tests/architecture/test_event_schema_version.py`                 |
| Create | `tests/architecture/test_registry_events_contract.py`             |
| Update | `tests/event_bus/test_pipeline_events.py` (catalog count 18 → 23) |

---

## Sub-phase 1.1 — Add `schema_version` to the `Event` base

### Task 1: Write the failing test

- [ ] **Step 1.1.1: Write `tests/architecture/test_event_schema_version.py`**

```python
"""Architecture test: Event base carries schema_version (arch-cleanup-2 Phase 1).

Invariants:
- Event has a schema_version field with default 1.
- Any concrete subclass instance carries schema_version == 1.
- event_to_envelope serializes the field inside "data".
- event_from_envelope round-trips it correctly.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from personalscraper.core.event_bus import (
    Event,
    event_from_envelope,
    event_to_envelope,
)


@dataclass(frozen=True, kw_only=True)
class _SampleEvent(Event):
    """Minimal test-only Event subclass for schema_version assertions."""

    label: str = "test"


def test_event_base_has_schema_version_attribute() -> None:
    """Event class has a schema_version field."""
    assert hasattr(Event, "schema_version"), "Event is missing schema_version field"


def test_event_instance_schema_version_default_is_1() -> None:
    """Freshly constructed Event subclass has schema_version == 1."""
    ev = _SampleEvent()
    assert ev.schema_version == 1


def test_envelope_data_carries_schema_version() -> None:
    """event_to_envelope includes schema_version inside the 'data' dict."""
    ev = _SampleEvent()
    envelope = event_to_envelope(ev)
    assert "schema_version" in envelope["data"], (
        f"envelope['data'] keys: {list(envelope['data'].keys())}"
    )
    assert envelope["data"]["schema_version"] == 1


def test_round_trip_preserves_schema_version() -> None:
    """event_from_envelope reconstructs schema_version == 1."""
    ev = _SampleEvent(label="round-trip")
    reconstructed = event_from_envelope(event_to_envelope(ev))
    assert reconstructed.schema_version == 1  # type: ignore[union-attr]
```

- [ ] **Step 1.1.2: Run the test — expect 4 failures**

```bash
python -m pytest tests/architecture/test_event_schema_version.py -v
# EXPECT: 4 FAILED — AttributeError / AssertionError: Event is missing schema_version
```

### Task 2: Implement `schema_version` on `Event`

- [ ] **Step 1.1.3: Add `schema_version: int = 1` to the `Event` dataclass in `core/event_bus.py`**

Locate the `Event` class (around line 204). Add the field after `correlation_id`:

```python
@dataclass(frozen=True, kw_only=True)
class Event:
    # ... existing docstring unchanged ...
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: str | None = field(
        default_factory=lambda: current_correlation_id.get(),
    )
    schema_version: int = 1
```

- [ ] **Step 1.1.4: Run the test — expect 4 passing**

```bash
python -m pytest tests/architecture/test_event_schema_version.py -v
# EXPECT: 4 passed
```

- [ ] **Step 1.1.5: Smoke-import and quick sanity**

```bash
python -c "from personalscraper.core.event_bus import Event; assert hasattr(Event, 'schema_version'); print('ok')"
# EXPECT: ok
```

- [ ] **Step 1.1.6: Commit**

```bash
git add personalscraper/core/event_bus.py tests/architecture/test_event_schema_version.py
git commit -m "feat(arch-cleanup-2): add schema_version field to Event base (default=1)"
```

---

## Sub-phase 1.2 — Rebase 5 registry events onto `Event`

### Task 3: Write the failing registry contract test

- [ ] **Step 1.2.1: Write `tests/architecture/test_registry_events_contract.py`**

```python
"""Architecture test: registry events conform to the Event contract (arch-cleanup-2 Phase 1).

Invariants:
- All 5 classes in api/metadata/registry/_events.py subclass Event.
- All 5 are in _EVENT_CLASS_REGISTRY after importing personalscraper.events.
- All 5 round-trip through event_to_envelope / event_from_envelope.
- Public import path from registry package is preserved.
"""

from __future__ import annotations

import pytest

# Trigger auto-registration of all production events including registry events.
import personalscraper.events  # noqa: F401


from personalscraper.api.metadata.registry import _events as reg_events
from personalscraper.core.event_bus import (
    Event,
    _EVENT_CLASS_REGISTRY,
    event_from_envelope,
    event_to_envelope,
)

_REGISTRY_EVENT_NAMES = [
    "ProviderFallbackTriggered",
    "ProviderExhaustedEvent",
    "LockedCapabilityUnresolved",
    "RegistryFanOutCompleted",
    "RegistryBootValidated",
]


@pytest.mark.parametrize("name", _REGISTRY_EVENT_NAMES)
def test_registry_event_subclasses_event(name: str) -> None:
    """Each registry event class is an Event subclass."""
    cls = getattr(reg_events, name)
    assert issubclass(cls, Event), f"{name} does not subclass Event"


@pytest.mark.parametrize("name", _REGISTRY_EVENT_NAMES)
def test_registry_event_in_catalog(name: str) -> None:
    """Each registry event is registered in _EVENT_CLASS_REGISTRY."""
    assert name in _EVENT_CLASS_REGISTRY, (
        f"{name} missing from _EVENT_CLASS_REGISTRY. "
        f"Registered: {sorted(_EVENT_CLASS_REGISTRY)}"
    )


def test_provider_fallback_triggered_round_trips() -> None:
    """ProviderFallbackTriggered survives envelope round-trip."""
    ev = reg_events.ProviderFallbackTriggered(
        capability="MetadataClient",
        from_provider="tmdb",
        to_provider="tvdb",
        reason="network",
        exc_type="requests.Timeout",
        item={"title": "Test", "year": 2024},
    )
    reconstructed = event_from_envelope(event_to_envelope(ev))
    assert reconstructed == ev


def test_registry_boot_validated_round_trips() -> None:
    """RegistryBootValidated survives envelope round-trip."""
    ev = reg_events.RegistryBootValidated(
        providers=("tmdb", "tvdb"),
        capabilities={"MetadataClient": ("tmdb", "tvdb")},
    )
    reconstructed = event_from_envelope(event_to_envelope(ev))
    assert reconstructed == ev


def test_public_import_path_preserved() -> None:
    """Registry events are importable from the registry package public surface."""
    from personalscraper.api.metadata.registry import (  # noqa: F401
        ProviderFallbackTriggered,
        RegistryBootValidated,
    )
```

- [ ] **Step 1.2.2: Run the test — expect failures**

```bash
python -m pytest tests/architecture/test_registry_events_contract.py -v
# EXPECT: FAILED — registry events do not subclass Event yet
```

### Task 4: Rebase the 5 registry events onto `Event`

- [ ] **Step 1.2.3: Rewrite `personalscraper/api/metadata/registry/_events.py`**

The key changes: add `from personalscraper.core.event_bus import Event`, change each
`@dataclass(frozen=True)` to `@dataclass(frozen=True, kw_only=True)`, and add `(Event)`
as base class. Payload fields are unchanged.

```python
"""EventBus event dataclasses for the provider registry (DESIGN §7.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from personalscraper.core.event_bus import Event

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import AttemptOutcome, ProviderMatch


@dataclass(frozen=True, kw_only=True)
class ProviderFallbackTriggered(Event):
    """Emitted when a chain moves from one provider to the next.

    Attributes:
        capability: The capability being chained (Protocol name).
        from_provider: Name of the provider that failed.
        to_provider: Name of the provider being tried next.
        reason: Why the fallback occurred — closed enum:
            ``circuit_open`` (provider tripped),
            ``network`` (ApiError / requests / OSError),
            ``empty_result`` (provider returned None / empty payload),
            ``other`` (unclassified Exception).
        exc_type: Exception type name if an error caused the fallback.
        item: Dict with item context (title, year, media_type, etc.).
    """

    capability: str
    from_provider: str
    to_provider: str
    reason: Literal["circuit_open", "network", "empty_result", "other"]
    exc_type: str | None
    item: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class ProviderExhaustedEvent(Event):
    """Emitted when all providers in a chain failed for an item.

    Attributes:
        capability: The capability being chained (Protocol name).
        attempted: Per-provider outcomes for the exhausted chain, stored
            as a ``tuple`` so the frozen-dataclass invariant is honoured.
        item: Dict with item context (title, year, media_type, etc.).
    """

    capability: str
    attempted: tuple[AttemptOutcome, ...]
    item: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class LockedCapabilityUnresolved(Event):
    """Emitted when ``locked()`` cannot bind a provider via IDCrossRef.

    Attributes:
        capability: The locked capability being resolved (Protocol name).
        match: The ``ProviderMatch`` that could not be resolved.
        chain_tried: Tuple of providers tried for IDCrossRef translation.
    """

    capability: str
    match: ProviderMatch
    chain_tried: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class RegistryFanOutCompleted(Event):
    """Always emitted after ``fan_out`` returns (even on full success).

    Attributes:
        capability: The capability that was fanned out (Protocol name).
        attempted: Per-provider outcomes for the fan-out, stored as a
            ``tuple`` so the frozen-dataclass invariant is honoured.
        eligible: Number of providers that survived eligibility filtering.
    """

    capability: str
    attempted: tuple[AttemptOutcome, ...]
    eligible: int


@dataclass(frozen=True, kw_only=True)
class RegistryBootValidated(Event):
    """Emitted when boot completed successfully.

    Attributes:
        providers: Sorted tuple of registered provider names.
        capabilities: Map of capability name → tuple of provider names.
    """

    providers: tuple[str, ...]
    capabilities: dict[str, tuple[str, ...]]
```

- [ ] **Step 1.2.4: Add eager-import of `registry._events` to `personalscraper/events/__init__.py`**

After the last existing eager-import line (currently `from personalscraper.trailers import events
as _trailers_events`), add:

```python
from personalscraper.api.metadata.registry import _events as _registry_events  # noqa: F401
```

Also add the 5 public names to `__all__`:

```python
from personalscraper.api.metadata.registry._events import (
    LockedCapabilityUnresolved,
    ProviderExhaustedEvent,
    ProviderFallbackTriggered,
    RegistryBootValidated,
    RegistryFanOutCompleted,
)
```

And append them to `__all__`:

```python
__all__ = [
    # ... existing entries ...
    "LockedCapabilityUnresolved",
    "ProviderExhaustedEvent",
    "ProviderFallbackTriggered",
    "RegistryBootValidated",
    "RegistryFanOutCompleted",
]
```

- [ ] **Step 1.2.5: Drop the `type: ignore[arg-type]` in `registry/__init__.py` at line ~706**

Find the emit line:

```bash
grep -n "type: ignore\[arg-type\]" personalscraper/api/metadata/registry/__init__.py
```

Remove the `# type: ignore[arg-type]` comment from that line — the argument is now
a real `Event` subclass and mypy no longer needs the suppression.

- [ ] **Step 1.2.6: Run the contract test — expect passing**

```bash
python -m pytest tests/architecture/test_registry_events_contract.py -v
# EXPECT: all passed
```

- [ ] **Step 1.2.7: Residual grep — positional construction of the 5 events**

The `kw_only=True` flip means any positional construction (e.g.
`ProviderFallbackTriggered("cap", "from", ...)`) now raises `TypeError`.
Scan both `personalscraper/` and `tests/`:

```bash
rg -t py "ProviderFallbackTriggered\|ProviderExhaustedEvent\|LockedCapabilityUnresolved\|RegistryFanOutCompleted\|RegistryBootValidated" personalscraper/ tests/
```

For every match, verify the construction uses keyword arguments. If any positional
construction is found, rewrite it to keyword form. Add a regression test for each
breakage found (see Step 1.2.8 template).

- [ ] **Step 1.2.8: Regression test template (apply if positional-construction breakage found)**

For each positional-construction breakage, add a test in the nearest existing test module:

```python
def test_<EventName>_constructed_with_kwargs() -> None:
    """Regression: kw_only flip — positional construction must raise TypeError."""
    import pytest
    with pytest.raises(TypeError):
        # Replace with the actual positional call that was broken
        ProviderFallbackTriggered("cap", "from", "to", "network", None, {})
```

- [ ] **Step 1.2.9: Update the catalog-size invariant in `tests/event_bus/test_pipeline_events.py`**

Find the test `test_production_event_catalog_size` (around line 110). Update:

```python
# Before:
assert len(_EVENT_CLASS_REGISTRY) == 18, (
    f"Expected 18 v1 events, found {len(_EVENT_CLASS_REGISTRY)}: {sorted(_EVENT_CLASS_REGISTRY)}"
)

# After (also add eager-import for registry._events if not already present via personalscraper.events):
import personalscraper.events  # noqa: F401 — eager-import side effect (already present)
# Add registry events import if needed:
import personalscraper.api.metadata.registry._events  # noqa: F401

assert len(_EVENT_CLASS_REGISTRY) == 23, (
    f"Expected 23 events (18 original + 5 registry), "
    f"found {len(_EVENT_CLASS_REGISTRY)}: {sorted(_EVENT_CLASS_REGISTRY)}"
)
```

Also update the docstring count narrative to mention the +5 registry events.

- [ ] **Step 1.2.10: Run the full test suite**

```bash
make test
# EXPECT: all passed, 0 errors
```

- [ ] **Step 1.2.11: Commit**

```bash
git add personalscraper/api/metadata/registry/_events.py \
        personalscraper/api/metadata/registry/__init__.py \
        personalscraper/events/__init__.py \
        tests/architecture/test_registry_events_contract.py \
        tests/event_bus/test_pipeline_events.py
git commit -m "feat(arch-cleanup-2): rebase 5 registry events onto Event contract; register in catalog"
```

---

## Phase Gate

```bash
make lint && make test && make check
# EXPECT: exit 0 for all three

python -c "import personalscraper.events; print('ok')"
# EXPECT: ok

rg -t py 'type: ignore\[arg-type\]' personalscraper/api/metadata/registry/__init__.py
# EXPECT: no output (exit 1 — rg exits 1 when no matches found)

python3 scripts/check-module-size.py
# EXPECT: exit 0; only two WARN lines (scraper/movie_service.py, library/scanner.py)
```

---

## Acceptance Criteria (Phase 1 subset)

```bash
# ACC-02 — Event base carries schema_version
python -c "from personalscraper.core.event_bus import Event; assert hasattr(Event, 'schema_version'); print('ok')"
# EXPECT: exit 0; stdout: ok

# ACC-03 — all 5 registry events are real Events
python -c "
import personalscraper.events
from personalscraper.core.event_bus import Event
from personalscraper.api.metadata.registry import _events as e
names = ['ProviderFallbackTriggered','ProviderExhaustedEvent','LockedCapabilityUnresolved','RegistryFanOutCompleted','RegistryBootValidated']
assert all(issubclass(getattr(e, n), Event) for n in names)
print('ok')
"
# EXPECT: exit 0; stdout: ok

# ACC-04 — registry events are catalog-registered
python -c "
import personalscraper.events
from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
assert 'ProviderFallbackTriggered' in _EVENT_CLASS_REGISTRY
print('ok')
"
# EXPECT: exit 0; stdout: ok

# ACC-05 — the emit type:ignore is gone
rg -t py 'type: ignore\[arg-type\]' personalscraper/api/metadata/registry/__init__.py
# EXPECT: no output, exit 1

# ACC-06 — registry events public import path preserved
python -c "from personalscraper.api.metadata.registry import ProviderFallbackTriggered, RegistryBootValidated; print('ok')"
# EXPECT: exit 0; stdout: ok

# ACC-13 — architecture contract tests pass
python -m pytest tests/architecture/test_registry_events_contract.py tests/architecture/test_event_schema_version.py -q
# EXPECT: exit 0; "passed" in output

# ACC-17 — smoke import
python -c "import personalscraper; print('ok')"
# EXPECT: exit 0; stdout: ok
```
