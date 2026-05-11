"""Tests for ``event_to_dict`` — pure-payload JSON-safe encoder.

Locks Sub-phase 1.5 of the event-bus feature: every encoding rule from
DESIGN §JSON serialization contract, plus the ``Event.to_dict`` delegation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from uuid import UUID

import pytest

from personalscraper.core.event_bus import Event, event_to_dict

# ---------------------------------------------------------------------------
# Test-only Event subclasses (kept here so they live outside the production
# registry by Invariant 9 — Event.__init_subclass__ will be added in 1.6).
# ---------------------------------------------------------------------------


class _Mode(Enum):
    """Sample enum for value-encoding tests."""

    LIVE = "live"
    DRY = "dry"


@dataclass(frozen=True)
class _Inner:
    """Nested dataclass with primitive fields."""

    a: int
    b: str


class _WithDateAndId(Event):
    """Inherits Event default fields (timestamp, event_id, source, correlation_id)."""


@dataclass(frozen=True)
class _WithPath(Event):
    """Event subclass adding a Path field."""

    path: Path = Path("/tmp/sample.mp4")


@dataclass(frozen=True)
class _WithEnum(Event):
    """Event subclass adding an Enum field."""

    mode: _Mode = _Mode.LIVE


@dataclass(frozen=True)
class _WithNested(Event):
    """Event subclass with a nested dataclass field."""

    inner: _Inner = field(default_factory=lambda: _Inner(a=1, b="x"))


@dataclass(frozen=True)
class _WithList(Event):
    """Event subclass with a list-of-dataclass field."""

    items: list[_Inner] = field(default_factory=lambda: [_Inner(1, "a"), _Inner(2, "b")])


@dataclass(frozen=True)
class _WithPrimitives(Event):
    """Event subclass with the basic JSON-safe primitives + None."""

    n: int = 7
    f: float = 1.5
    s: str = "hello"
    b: bool = True
    nullable: str | None = None


@dataclass(frozen=True)
class _WithBadKeyDict(Event):
    """Event subclass whose dict has a non-JSON-safe key (tuple)."""

    details: dict = field(default_factory=lambda: {(1, 2): "tuple-key"})


@dataclass(frozen=True)
class _WithUnsupported(Event):
    """Event subclass with a deliberately unsupported value type."""

    blob: object = field(default_factory=object)


# ---------------------------------------------------------------------------
# Encoder tests
# ---------------------------------------------------------------------------


def test_to_dict_encodes_datetime_as_iso_8601() -> None:
    """``timestamp`` is encoded as a UTC ISO 8601 string with offset suffix."""
    event = _WithDateAndId()
    data = event_to_dict(event)
    assert isinstance(data["timestamp"], str)
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$",
        data["timestamp"],
    )


def test_to_dict_encodes_uuid_as_str() -> None:
    """``event_id`` becomes a canonical UUID string."""
    event = _WithDateAndId()
    data = event_to_dict(event)
    assert isinstance(data["event_id"], str)
    # Round-trip through UUID() to validate format.
    UUID(data["event_id"])


def test_to_dict_encodes_path_as_str() -> None:
    """A ``Path`` field is encoded as its string form."""
    event = _WithPath(path=Path("/var/data/movie.mkv"))
    data = event_to_dict(event)
    assert data["path"] == "/var/data/movie.mkv"
    assert isinstance(data["path"], str)


def test_to_dict_encodes_enum_as_value() -> None:
    """An ``Enum`` field is encoded as ``enum.value`` (not its name)."""
    event = _WithEnum(mode=_Mode.DRY)
    data = event_to_dict(event)
    assert data["mode"] == "dry"


def test_to_dict_encodes_nested_dataclass() -> None:
    """A nested dataclass is recursively encoded as a dict of its field values."""
    event = _WithNested(inner=_Inner(a=42, b="answer"))
    data = event_to_dict(event)
    assert data["inner"] == {"a": 42, "b": "answer"}


def test_to_dict_encodes_list_of_dataclasses() -> None:
    """A list of dataclasses becomes a list of dicts (recursive encoding)."""
    event = _WithList()
    data = event_to_dict(event)
    assert data["items"] == [
        {"a": 1, "b": "a"},
        {"a": 2, "b": "b"},
    ]


def test_to_dict_encodes_none_int_str_bool_unchanged() -> None:
    """JSON-native primitives pass through unchanged."""
    event = _WithPrimitives(n=10, f=2.5, s="literal", b=False, nullable=None)
    data = event_to_dict(event)
    assert data["n"] == 10
    assert data["f"] == 2.5
    assert data["s"] == "literal"
    assert data["b"] is False
    assert data["nullable"] is None


def test_to_dict_dict_with_non_safe_key_raises() -> None:
    """A dict whose keys are not str/int/float/bool/None raises ``TypeError``."""
    event = _WithBadKeyDict()
    with pytest.raises(TypeError):
        event_to_dict(event)


def test_to_dict_unsupported_type_raises_typeerror() -> None:
    """An unsupported value type raises a clear ``TypeError`` (fail-loud)."""
    event = _WithUnsupported(blob=object())
    with pytest.raises(TypeError, match="Cannot encode"):
        event_to_dict(event)


def test_event_to_dict_method_delegates_to_module_level() -> None:
    """``Event.to_dict()`` is a thin alias for ``event_to_dict(self)``."""
    event = _WithDateAndId()
    assert event.to_dict() == event_to_dict(event)


def test_to_dict_encodes_tuple_as_list() -> None:
    """Tuples are encoded as lists (JSON has no tuple type)."""

    @dataclass(frozen=True)
    class _WithTuple(Event):
        coords: tuple[int, int, int] = (1, 2, 3)

    event = _WithTuple()
    data = event_to_dict(event)
    assert data["coords"] == [1, 2, 3]
    assert isinstance(data["coords"], list)


def test_to_dict_encodes_nested_dict_with_str_keys() -> None:
    """A nested dict with string keys round-trips field-by-field."""

    @dataclass(frozen=True)
    class _WithStrDict(Event):
        details: dict = field(default_factory=lambda: {"k1": 1, "k2": "v"})

    event = _WithStrDict()
    data = event_to_dict(event)
    assert data["details"] == {"k1": 1, "k2": "v"}
