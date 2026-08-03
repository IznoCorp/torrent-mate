"""Tests for the download lifecycle event classes (seed-caps O4, sub-phase 3.1)."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime

import pytest

import personalscraper.events  # noqa: F401 — eager-import side effect
from personalscraper.acquire.events import (
    DownloadCompleted,
    DownloadProgressed,
    DownloadStarted,
)
from personalscraper.core.event_bus import (
    _EVENT_CLASS_REGISTRY,
    Event,
    event_from_envelope,
    event_to_envelope,
)
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES

DOWNLOAD_EVENT_CLASSES: tuple[type[Event], ...] = (
    DownloadStarted,
    DownloadProgressed,
    DownloadCompleted,
)


@pytest.mark.parametrize("cls", DOWNLOAD_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_download_events_inherit_event_base(cls: type[Event]) -> None:
    """Every download event inherits from Event."""
    assert issubclass(cls, Event)


@pytest.mark.parametrize("cls", DOWNLOAD_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_download_events_are_frozen(cls: type[Event]) -> None:
    """Every download event is a frozen dataclass."""
    assert dataclasses.is_dataclass(cls)
    instance = EVENT_SAMPLE_FACTORIES[cls]()
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.source = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize("cls", DOWNLOAD_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_download_events_auto_registered(cls: type[Event]) -> None:
    """Each download event class name appears in _EVENT_CLASS_REGISTRY."""
    assert _EVENT_CLASS_REGISTRY.get(cls.__name__) is cls


@pytest.mark.parametrize("cls", DOWNLOAD_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_download_events_require_keyword_construction(cls: type[Event]) -> None:
    """Payload fields are kw_only — positional construction raises TypeError."""
    with pytest.raises(TypeError):
        cls("a" * 40)  # type: ignore[call-arg, misc]


def test_download_started_constructs_and_round_trips_values() -> None:
    """DownloadStarted constructs with required kw-only fields and keeps values."""
    event = DownloadStarted(
        info_hash="a" * 40,
        title="Breaking Bad S05E01",
        provider="c411",
        kind="episode",
    )
    assert event.info_hash == "a" * 40
    assert event.title == "Breaking Bad S05E01"
    assert event.provider == "c411"
    assert event.kind == "episode"


def test_download_progressed_constructs_and_round_trips_values() -> None:
    """DownloadProgressed constructs with required kw-only fields and keeps values."""
    event = DownloadProgressed(
        info_hash="b" * 40,
        title="Breaking Bad S05E01",
        progress=0.55,
        threshold_pct=50,
    )
    assert event.info_hash == "b" * 40
    assert event.title == "Breaking Bad S05E01"
    assert event.progress == 0.55
    assert event.threshold_pct == 50


def test_download_completed_constructs_and_round_trips_values() -> None:
    """DownloadCompleted constructs with required kw-only fields and keeps values."""
    event = DownloadCompleted(
        info_hash="c" * 40,
        title="Inception (2010)",
        provider="c411",
        kind="movie",
    )
    assert event.info_hash == "c" * 40
    assert event.title == "Inception (2010)"
    assert event.provider == "c411"
    assert event.kind == "movie"


@pytest.mark.parametrize("cls", DOWNLOAD_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_download_events_auto_derive_source(cls: type[Event]) -> None:
    """``source`` auto-derives to ``{module}.{ClassName}`` when not provided."""
    event = EVENT_SAMPLE_FACTORIES[cls]()
    assert event.source == f"personalscraper.acquire.events.{cls.__name__}"


@pytest.mark.parametrize("cls", DOWNLOAD_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_download_events_auto_derive_timestamp(cls: type[Event]) -> None:
    """``timestamp`` defaults to a UTC-aware construction-time datetime."""
    before = datetime.now(UTC)
    event = EVENT_SAMPLE_FACTORIES[cls]()
    after = datetime.now(UTC)
    assert event.timestamp.tzinfo is not None
    assert before <= event.timestamp <= after


@pytest.mark.parametrize("cls", DOWNLOAD_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_download_events_envelope_roundtrip(cls: type[Event]) -> None:
    """Envelope round-trip preserves equality for every download event."""
    e1 = EVENT_SAMPLE_FACTORIES[cls]()
    envelope = event_to_envelope(e1)
    e2 = event_from_envelope(json.loads(json.dumps(envelope)))
    assert e2 == e1, f"Round-trip failed for {cls.__name__}: {e2!r} != {e1!r}"
