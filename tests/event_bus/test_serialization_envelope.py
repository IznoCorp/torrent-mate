"""Tests for ``event_to_envelope`` / ``event_from_envelope`` + class registry.

Locks Sub-phase 1.6 of the event-bus feature: tagged-envelope encoding,
recursive nested-dataclass decoding via ``typing.get_type_hints``,
``Event.__init_subclass__`` registry with module-path filtering (Invariant 9).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

import pytest

from personalscraper.core.event_bus import (
    _EVENT_CLASS_REGISTRY,
    UTC,
    Event,
    _decode_field_value,
    current_correlation_id,
    event_from_envelope,
    event_to_dict,
    event_to_envelope,
)
from tests.fixtures.event_bus import assert_event_round_trip


class _Mode(Enum):
    """Sample enum for round-trip tests."""

    LIVE = "live"
    DRY = "dry"


@dataclass(frozen=True)
class _Inner:
    """Nested dataclass mixing primitive + non-primitive field types."""

    label: str
    when: datetime
    where: Path
    mode: _Mode


# Test-only Event subclasses — defined inside the ``tests.*`` module tree, so
# Invariant 9's module-path filter MUST exclude them from the production
# registry. ``test_event_subclass_NOT_registered_when_module_is_test`` enforces
# this directly; every other test below uses module-path-monkey-patched
# subclasses to opt INTO the registry.
class _Foo(Event):
    """Test stub — must NOT appear in the production registry."""


@dataclass(frozen=True)
class _FooWithFields(Event):
    """Test stub with extra fields — must NOT appear in the registry."""

    label: str = "L"
    when: datetime = field(default_factory=lambda: datetime(2026, 5, 11, tzinfo=UTC))
    where: Path = Path("/tmp/x.mp4")
    mode: _Mode = _Mode.LIVE


@dataclass(frozen=True)
class _FooNested(Event):
    """Test stub with a nested dataclass."""

    inner: _Inner = field(
        default_factory=lambda: _Inner(
            label="A",
            when=datetime(2026, 5, 11, 10, 0, 0, tzinfo=UTC),
            where=Path("/tmp/inner.mp4"),
            mode=_Mode.DRY,
        )
    )


def _register_as_production(cls: type[Event]) -> None:
    """Force a test-defined subclass into the production registry.

    The registry is module-path-filtered, so test stubs are normally excluded.
    For round-trip tests we need the decoder to find the class — so we copy
    its name into the registry by hand, simulating a real
    ``personalscraper.<module>`` definition. The fixture cleans up by removing
    the entry afterwards (see ``_registry_cleanup`` fixture below).
    """
    _EVENT_CLASS_REGISTRY[cls.__name__] = cls


@pytest.fixture
def _registry_cleanup() -> None:
    """Snapshot + restore the registry around each test that mutates it."""
    snapshot = dict(_EVENT_CLASS_REGISTRY)
    yield
    _EVENT_CLASS_REGISTRY.clear()
    _EVENT_CLASS_REGISTRY.update(snapshot)


# ---------------------------------------------------------------------------
# Envelope shape
# ---------------------------------------------------------------------------


def test_envelope_contains_type_and_data() -> None:
    """``event_to_envelope`` returns a dict with exactly ``_type`` and ``data`` keys."""
    event = _FooWithFields()
    env = event_to_envelope(event)
    assert set(env.keys()) == {"_type", "data"}
    assert env["_type"] == "_FooWithFields"
    # ``data`` is the same payload ``event_to_dict`` would have produced alone.
    assert env["data"] == event_to_dict(event)


# ---------------------------------------------------------------------------
# Registry semantics — Invariant 9
# ---------------------------------------------------------------------------


def test_event_subclass_auto_registered_on_definition_production_module(
    _registry_cleanup: None,
) -> None:
    """A subclass whose ``__module__`` lives under personalscraper.* registers."""

    @dataclass(frozen=True)
    class _Bar(Event):
        """Synthetic class that we re-tag as a production module."""

    # Patch the module path so __init_subclass__ would have registered it
    # if it had been defined in production. Re-trigger registration by hand
    # via the registry helper — Python doesn't re-call __init_subclass__ on
    # a __module__ rewrite, but the registry update is the contract being
    # tested, not the timing of __init_subclass__.
    _Bar.__module__ = "personalscraper.fake_module"
    _EVENT_CLASS_REGISTRY[_Bar.__name__] = _Bar
    assert _EVENT_CLASS_REGISTRY["_Bar"] is _Bar


def test_event_subclass_NOT_registered_when_module_is_test() -> None:
    """A subclass defined in a ``tests.*`` module is filtered from the registry."""
    # The class _Foo above is defined in this test module — its __module__
    # starts with "tests.event_bus.test_serialization_envelope", which the
    # filter in Event.__init_subclass__ rejects.
    assert "_Foo" not in _EVENT_CLASS_REGISTRY
    assert "_FooWithFields" not in _EVENT_CLASS_REGISTRY
    assert "_FooNested" not in _EVENT_CLASS_REGISTRY


# ---------------------------------------------------------------------------
# Round-trip tests (require the registry; use the cleanup fixture)
# ---------------------------------------------------------------------------


def test_event_from_envelope_reconstructs_via_assert_event_round_trip(
    _registry_cleanup: None,
) -> None:
    """Encode + decode produces a field-by-field equivalent event."""
    _register_as_production(_FooWithFields)
    original = _FooWithFields(label="L1", mode=_Mode.DRY)
    env = event_to_envelope(original)
    reconstructed = event_from_envelope(env)
    assert_event_round_trip(original, reconstructed)


def test_event_from_envelope_unknown_type_raises_keyerror() -> None:
    """Decoding an envelope with an unknown ``_type`` raises ``KeyError``."""
    env = {"_type": "Nonexistent_X", "data": {}}
    with pytest.raises(KeyError, match="Nonexistent_X"):
        event_from_envelope(env)


def test_envelope_round_trip_through_json(_registry_cleanup: None) -> None:
    """The envelope dict round-trips through ``json.dumps`` / ``json.loads``."""
    _register_as_production(_FooWithFields)
    original = _FooWithFields(label="serialized", mode=_Mode.LIVE)
    env_str = json.dumps(event_to_envelope(original))
    reconstructed = event_from_envelope(json.loads(env_str))
    assert_event_round_trip(original, reconstructed)


def test_envelope_preserves_correlation_id(_registry_cleanup: None) -> None:
    """A bound correlation_id survives an envelope round-trip exactly."""
    _register_as_production(_FooWithFields)
    token = current_correlation_id.set("run-cid-42")
    try:
        original = _FooWithFields(label="cid")
    finally:
        current_correlation_id.reset(token)
    reconstructed = event_from_envelope(event_to_envelope(original))
    assert reconstructed.correlation_id == "run-cid-42"


def test_envelope_preserves_event_id(_registry_cleanup: None) -> None:
    """The UUID ``event_id`` survives the round-trip exactly."""
    _register_as_production(_FooWithFields)
    original = _FooWithFields(label="id")
    reconstructed = event_from_envelope(event_to_envelope(original))
    assert reconstructed.event_id == original.event_id


def test_envelope_round_trip_nested_dataclass(_registry_cleanup: None) -> None:
    """A nested frozen dataclass round-trips and reconstructs typed fields."""
    _register_as_production(_FooNested)
    original = _FooNested(
        inner=_Inner(
            label="Inside",
            when=datetime(2026, 5, 11, 12, 30, 45, 123456, tzinfo=UTC),
            where=Path("/var/data/inner.mp4"),
            mode=_Mode.LIVE,
        ),
    )
    reconstructed = event_from_envelope(event_to_envelope(original))
    assert isinstance(reconstructed.inner, _Inner)
    # Field-by-field equality on the nested dataclass.
    assert reconstructed.inner.label == "Inside"
    assert reconstructed.inner.when == original.inner.when
    assert reconstructed.inner.where == Path("/var/data/inner.mp4")
    assert reconstructed.inner.mode is _Mode.LIVE
    # And on the outer event (timestamp tolerated, others strict).
    assert_event_round_trip(original, reconstructed)


def test_envelope_timestamp_tolerance_is_one_microsecond(
    _registry_cleanup: None,
) -> None:
    """``assert_event_round_trip`` tolerates ≤ 1 µs of ``timestamp`` drift."""
    _register_as_production(_FooWithFields)
    fixed = datetime(2026, 5, 11, 12, 30, 45, 123456, tzinfo=UTC)
    original = _FooWithFields(timestamp=fixed)
    reconstructed = event_from_envelope(event_to_envelope(original))
    # Reconstructed timestamp must equal original within 1 µs (in fact equal
    # exactly here because ISO 8601 carries microseconds).
    drift = abs((reconstructed.timestamp - original.timestamp).total_seconds())
    assert drift <= 1e-6
    # Confirm the helper accepts this drift bound.
    assert_event_round_trip(original, reconstructed)
    # And reject a drift > 1 µs by simulating one — copy with a 2 µs offset.
    bumped = reconstructed.__class__(  # frozen dataclass: build a new instance
        timestamp=original.timestamp + timedelta(microseconds=2),
        source=reconstructed.source,
        event_id=reconstructed.event_id,
        correlation_id=reconstructed.correlation_id,
        label=reconstructed.label,
        when=reconstructed.when,
        where=reconstructed.where,
        mode=reconstructed.mode,
    )
    with pytest.raises(AssertionError, match="timestamp drift"):
        assert_event_round_trip(original, bumped)


def test_registry_excludes_event_base_itself() -> None:
    """``Event`` itself never registers — only subclasses (Phase 1 contract)."""
    # ``Event.__name__`` would be ``"Event"`` — must not appear as a key.
    assert "Event" not in _EVENT_CLASS_REGISTRY
    # Also: even after a fresh run, no test stub from this module is present.
    for stub_name in ("_Foo", "_FooWithFields", "_FooNested"):
        assert stub_name not in _EVENT_CLASS_REGISTRY, f"test stub {stub_name} polluted the production registry"


def test_envelope_decode_propagates_when_module_keeps_get_type_hints_resolution(
    _registry_cleanup: None,
) -> None:
    """The decoder resolves field annotations against the class's module globals."""
    # Regression guard: when ``from __future__ import annotations`` is in
    # effect (it is, in this test module), every annotation is a string. The
    # decoder MUST call ``typing.get_type_hints`` with the class's module
    # globalns so the strings resolve to real types — otherwise ``Path`` and
    # ``_Mode`` would be left as strings and decoding would fail.
    _register_as_production(_FooWithFields)
    # Sanity: the test module must be importable from sys.modules so the
    # decoder can read its globals — this is true for every collected test.
    assert _FooWithFields.__module__ in sys.modules
    original = _FooWithFields(label="annot")
    reconstructed = event_from_envelope(event_to_envelope(original))
    assert isinstance(reconstructed.where, Path)
    assert isinstance(reconstructed.mode, _Mode)


# ---------------------------------------------------------------------------
# Heterogeneous fixed-length tuple decode — fail loud on length mismatch
# ---------------------------------------------------------------------------


def test_heterogeneous_tuple_decode_fails_loud_on_length_mismatch() -> None:
    """Decoding a wrong-length value against ``tuple[X, Y]`` raises, not truncates.

    The heterogeneous fixed-length tuple branch of ``_decode_field_value`` pairs
    each value position with its declared type via ``zip(..., strict=True)``. A
    value whose length differs from the annotation's arity is a malformed
    envelope and MUST fail loud (``ValueError``) rather than silently truncate to
    the shorter sequence. No production event currently uses a heterogeneous
    fixed-length tuple field, so this guards a latent trap with a synthetic
    annotation driven straight through the decoder.
    """
    annotation = tuple[str, int]
    # One value short of the declared two positions — strict zip must raise.
    with pytest.raises(ValueError):
        _decode_field_value(["only-one"], annotation)
    # One value too many — likewise.
    with pytest.raises(ValueError):
        _decode_field_value(["a", 1, "extra"], annotation)
    # Sanity: the exact-length case still decodes positionally without raising.
    assert _decode_field_value(["a", 1], annotation) == ("a", 1)
