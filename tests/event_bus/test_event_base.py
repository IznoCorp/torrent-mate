"""Tests for the ``Event`` base dataclass and ``current_correlation_id``.

Locks Sub-phase 1.1 of the event-bus feature: frozen dataclass, auto-derived
``source``, UTC-aware ``timestamp``, unique ``event_id``, ContextVar capture.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from personalscraper.core.event_bus import UTC, Event, current_correlation_id


class _Foo(Event):
    """Test-only subclass; lives outside the production registry by Invariant 9."""


class _Bar(Event):
    """Second test-only subclass to assert distinct sources."""


def test_event_default_source_is_module_dot_class() -> None:
    """``source`` auto-derives to ``f"{module}.{ClassName}"`` when empty."""
    event = _Foo()
    assert event.source == f"{_Foo.__module__}._Foo"


def test_event_explicit_source_is_respected() -> None:
    """An explicit ``source`` argument wins over the auto-derived value."""
    event = _Foo(source="custom-source")
    assert event.source == "custom-source"


def test_event_timestamp_is_utc_aware() -> None:
    """``timestamp`` is timezone-aware and tagged UTC."""
    event = _Foo()
    assert event.timestamp.tzinfo is not None
    # Both ``datetime.UTC`` (3.11+) and ``timezone.utc`` are accepted; same offset.
    assert event.timestamp.utcoffset() == timezone.utc.utcoffset(None)
    # Stronger: the canonical UTC sentinel matches the module-level alias.
    assert event.timestamp.tzinfo is UTC


def test_event_event_id_is_unique_per_instance() -> None:
    """Each event gets its own ``event_id`` UUID."""
    a = _Foo()
    b = _Foo()
    assert isinstance(a.event_id, UUID)
    assert isinstance(b.event_id, UUID)
    assert a.event_id != b.event_id


def test_event_correlation_id_default_is_none_outside_bound_region() -> None:
    """Without binding the ContextVar, ``correlation_id`` is ``None``."""
    # Defensive: ensure no leakage from prior tests in this module.
    assert current_correlation_id.get() is None
    event = _Foo()
    assert event.correlation_id is None


def test_event_correlation_id_captured_inside_bound_region() -> None:
    """Inside a bound ContextVar region, the value is captured at construction."""
    token = current_correlation_id.set("abc")
    try:
        event = _Foo()
        assert event.correlation_id == "abc"
    finally:
        current_correlation_id.reset(token)
    # After reset, new events again get None.
    assert current_correlation_id.get() is None
    after = _Bar()
    assert after.correlation_id is None


def test_event_correlation_id_explicit_overrides_contextvar() -> None:
    """An explicit ``correlation_id`` argument wins over the ContextVar value."""
    token = current_correlation_id.set("from-context")
    try:
        event = _Foo(correlation_id="explicit")
        assert event.correlation_id == "explicit"
    finally:
        current_correlation_id.reset(token)


def test_event_is_frozen_no_attribute_assignment_after_construction() -> None:
    """``Event`` is a frozen dataclass — direct field assignment raises."""
    event = _Foo()
    # FrozenInstanceError inherits from AttributeError; catching the broader
    # base is robust across CPython versions.
    try:
        event.source = "mutated"  # type: ignore[misc]
    except (AttributeError, TypeError):
        pass
    else:  # pragma: no cover - signals a regression in frozen behavior
        raise AssertionError("Event must be frozen — assignment should raise")


def test_event_timestamp_default_is_recent() -> None:
    """``timestamp`` default factory uses ``datetime.now(UTC)`` — no future drift."""
    before = datetime.now(UTC)
    event = _Foo()
    after = datetime.now(UTC)
    assert before <= event.timestamp <= after


def test_event_id_str_form_matches_uuid_canonical_pattern() -> None:
    """Sanity: the UUID prints in the canonical 8-4-4-4-12 hex form."""
    event = _Foo()
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    assert re.match(pattern, str(event.event_id))
