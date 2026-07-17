"""Unit tests for the DETECT service layer (ACQUIRE-03 — grab parity).

Drives :class:`~personalscraper.acquire.detect.DetectService` directly against a
REAL :class:`ConcreteAcquireStore` + a REAL :class:`EventBus`, mirroring how the
grab tests drive ``AcquisitionService``. The resurrection cadence-cutoff gate
gets its own coverage here (it used to be buried in the CLI command).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.detect import DetectOutcome, DetectService, DetectStatus
from personalscraper.acquire.domain import AiredEpisode, FollowedSeries, WantedItem
from personalscraper.acquire.events import FilmAcquired, WantedEnqueued
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig, CadenceConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef


class _StubOwnership:
    """Ownership stub: owns exactly the media_refs it was given."""

    def __init__(self, owned: set[MediaRef]) -> None:
        self._owned = owned

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        return media_ref in self._owned


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _config() -> SimpleNamespace:
    """A minimal config exposing only ``acquire.cadence`` (all the service reads)."""
    return SimpleNamespace(acquire=SimpleNamespace(cadence=CadenceConfig()))


def _service(store: ConcreteAcquireStore, ownership: _StubOwnership, bus: EventBus) -> DetectService:
    """Build a DetectService with a MagicMock registry (poll_aired is patched)."""
    return DetectService(store=store, ownership=ownership, registry=MagicMock(), event_bus=bus, config=_config())


def test_detect_service_no_active_status(store: ConcreteAcquireStore) -> None:
    """An empty active set → status NO_ACTIVE, no actions."""
    result = _service(store, _StubOwnership(set()), EventBus()).run(
        series=None, dry_run=False, today=date(2024, 1, 1), now=1
    )
    assert result.status is DetectStatus.NO_ACTIVE
    assert result.actions == []


def test_detect_service_no_match_status(store: ConcreteAcquireStore) -> None:
    """A --series filter with no match → status NO_MATCH."""
    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=99), title="Silo", added_at=1))
    result = _service(store, _StubOwnership(set()), EventBus()).run(
        series="Nonexistent", dry_run=False, today=date(2024, 1, 1), now=1
    )
    assert result.status is DetectStatus.NO_MATCH


def test_detect_service_movie_enqueue_grab_parity(store: ConcreteAcquireStore) -> None:
    """An unowned movie follow → OK result with one ENQUEUED action + a real wanted row."""
    ref = MediaRef(tmdb_id=1184918)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Le Robot sauvage", added_at=1, kind="movie"))
    bus = EventBus()
    emitted: list[WantedEnqueued] = []
    bus.subscribe(WantedEnqueued, emitted.append)

    with patch("personalscraper.acquire.detect.poll_aired", return_value=[]):
        result = _service(store, _StubOwnership(set()), bus).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=100
        )

    assert result.status is DetectStatus.OK
    assert [a.outcome for a in result.actions] == [DetectOutcome.ENQUEUED]
    assert result.summary.enqueued == 1
    assert result.summary.detected == 1
    row = store.wanted.find(followed_id=fid, kind="movie", season=None, episode=None)
    assert row is not None and row.status == "pending"
    assert len(emitted) == 1 and emitted[0].kind == "movie"


def test_detect_service_movie_owned_retires_and_emits(store: ConcreteAcquireStore) -> None:
    """An OWNED movie follow → FILM_ACQUIRED action, follow retired, FilmAcquired emitted."""
    ref = MediaRef(tmdb_id=1184918)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Le Robot sauvage", added_at=1, kind="movie"))
    wid = store.wanted.add(WantedItem(media_ref=ref, kind="movie", status="pending", enqueued_at=1, followed_id=fid))
    store.wanted.mark_grabbed(wid, "abcd1234")
    bus = EventBus()
    films: list[FilmAcquired] = []
    bus.subscribe(FilmAcquired, films.append)

    with patch("personalscraper.acquire.detect.poll_aired", return_value=[]):
        result = _service(store, _StubOwnership({ref}), bus).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=100
        )

    assert [a.outcome for a in result.actions] == [DetectOutcome.FILM_ACQUIRED]
    assert result.summary.skipped_owned == 1
    follow = store.follow.get(fid)
    assert follow is not None and follow.active is False
    assert len(films) == 1 and films[0].followed_id == fid


def test_detect_service_resurrects_abandoned_within_cutoff(store: ConcreteAcquireStore) -> None:
    """An abandoned aired-unowned episode within cutoff → RESURRECTED (cadence gate)."""
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Silo", added_at=1))
    wid = store.wanted.add(
        WantedItem(
            media_ref=ref,
            kind="episode",
            status="pending",
            enqueued_at=int(time.time()) - 3600,
            followed_id=fid,
            season=3,
            episode=4,
        )
    )
    store.wanted.set_status(wid, "abandoned")
    ep = AiredEpisode(media_ref=ref, season=3, episode=4, air_date=date(2024, 1, 1), title="Ep")

    with patch("personalscraper.acquire.detect.poll_aired", return_value=[ep]):
        result = _service(store, _StubOwnership(set()), EventBus()).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=int(time.time())
        )

    assert [a.outcome for a in result.actions] == [DetectOutcome.RESURRECTED]
    assert result.summary.resurrected == 1
    assert store.wanted.get(wid).status == "pending"  # type: ignore[union-attr]


def test_detect_service_past_cutoff_stays_abandoned(store: ConcreteAcquireStore) -> None:
    """An abandoned row past its cadence cutoff → SKIPPED_DUP (no flip-flop)."""
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Silo", added_at=1))
    wid = store.wanted.add(
        WantedItem(
            media_ref=ref, kind="episode", status="pending", enqueued_at=1_000_000, followed_id=fid, season=3, episode=4
        )
    )
    store.wanted.set_status(wid, "abandoned")
    ep = AiredEpisode(media_ref=ref, season=3, episode=4, air_date=date(2024, 1, 1), title="Ep")

    with patch("personalscraper.acquire.detect.poll_aired", return_value=[ep]):
        result = _service(store, _StubOwnership(set()), EventBus()).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=int(time.time())
        )

    assert [a.outcome for a in result.actions] == [DetectOutcome.SKIPPED_DUP]
    assert result.summary.skipped_dup == 1
    assert store.wanted.get(wid).status == "abandoned"  # type: ignore[union-attr]
