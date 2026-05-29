"""Architecture test: Event base carries schema_version (arch-cleanup-2 Phase 1).

Invariants:
- Event has a schema_version field with default 1.
- Any concrete subclass instance carries schema_version == 1.
- event_to_envelope serializes the field inside "data".
- event_from_envelope round-trips it correctly.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from personalscraper.core.event_bus import (
    _EVENT_CLASS_REGISTRY,
    Event,
    event_from_envelope,
    event_to_envelope,
)


@dataclass(frozen=True, kw_only=True)
class _SampleEvent(Event):
    """Minimal test-only Event subclass for schema_version assertions."""

    label: str = "test"


@pytest.fixture
def _registry_cleanup() -> Iterator[None]:
    """Snapshot + restore the registry around a test that registers a stub.

    ``_SampleEvent`` lives in a ``tests.*`` module so ``__init_subclass__``
    deliberately keeps it out of ``_EVENT_CLASS_REGISTRY`` (test-module
    exclusion invariant). The round-trip test below temporarily registers it
    so ``event_from_envelope`` can reconstruct it, then restores the snapshot
    to avoid polluting the production catalog.
    """
    snapshot = dict(_EVENT_CLASS_REGISTRY)
    yield
    _EVENT_CLASS_REGISTRY.clear()
    _EVENT_CLASS_REGISTRY.update(snapshot)


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
    assert "schema_version" in envelope["data"], f"envelope['data'] keys: {list(envelope['data'].keys())}"
    assert envelope["data"]["schema_version"] == 1


def test_round_trip_preserves_schema_version(_registry_cleanup: None) -> None:
    """event_from_envelope reconstructs schema_version == 1."""
    _EVENT_CLASS_REGISTRY[_SampleEvent.__name__] = _SampleEvent
    ev = _SampleEvent(label="round-trip")
    reconstructed = event_from_envelope(event_to_envelope(ev))
    assert reconstructed.schema_version == 1
