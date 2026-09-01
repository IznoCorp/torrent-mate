"""Tests for the B.3 wanted ↔ library ↔ client reconciliation.

Regression suite for the frozen-`grabbed` bug: 14 production rows (Silo S3E1,
American Dad S22E5-11, FROM S4E8-10, Rick & Morty S9E5-6, Le Robot sauvage)
sat at ``grabbed`` forever because nothing ever compared them back to the
library or to the torrent client. Each rule of :func:`reconcile_wanted` gets a
red-on-old case against a REAL temp store.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import SeasonFellBackToEpisodes
from personalscraper.acquire.reconcile import reconcile_wanted
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef


class _StubOwnership:
    """Ownership stub: owns exactly the (season, episode) pairs it was given."""

    def __init__(self, owned_pairs: set[tuple[int | None, int | None]]) -> None:
        self._owned = owned_pairs

    def owns(self, media_ref: MediaRef, *, kind: str, season: int | None = None, episode: int | None = None) -> bool:
        return (season, episode) in self._owned


class _ExplodingOwnership:
    """Ownership stub that raises — reconcile must fail soft per row."""

    def owns(self, media_ref: MediaRef, *, kind: str, season: int | None = None, episode: int | None = None) -> bool:
        raise RuntimeError("library.db is locked")


# Subscriber-less sink: reconcile REQUIRES a bus (event_bus contract); these
# tests assert row transitions, not download events (covered in
# test_reconcile_download_events.py).
_BUS = EventBus()


def _items(*hashes: str, progress: float = 0.5) -> dict[str, TorrentItem]:
    """Client items for *hashes* — presence in the client is what matters here."""
    return {
        h: TorrentItem(hash=h, name=f"release-{h}", size_bytes=1024, progress=progress, state="downloading")
        for h in hashes
    }


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    yield s
    s.close()


def _grabbed(store: ConcreteAcquireStore, *, season: int, episode: int, info_hash: str) -> int:
    """Insert one grabbed episode row and return its id."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            season=season,
            episode=episode,
        )
    )
    store.wanted.mark_grabbed(wanted_id, info_hash)
    return wanted_id


def test_owned_grabbed_row_closes_done(store: ConcreteAcquireStore) -> None:
    """A grabbed row whose episode the library owns closes ``done`` (the Silo case)."""
    wanted_id = _grabbed(store, season=3, episode=1, info_hash="f92c7b09")

    summary = reconcile_wanted(store, _StubOwnership({(3, 1)}), client_items=_items("f92c7b09"), event_bus=_BUS)

    assert summary.closed_owned == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_vanished_torrent_unowned_requeues_pending(store: ConcreteAcquireStore) -> None:
    """Grabbed + hash absent from the client + unowned → back to pending, hash cleared."""
    wanted_id = _grabbed(store, season=3, episode=2, info_hash="deadbeef")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items={}, event_bus=_BUS)

    assert summary.requeued_missing == 1
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "pending"
    assert row.grabbed_hash is None


def test_torrent_still_in_client_stays_grabbed(store: ConcreteAcquireStore) -> None:
    """Grabbed + hash still known to the client + unowned → left in flight."""
    wanted_id = _grabbed(store, season=3, episode=3, info_hash="cafebabe")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items=_items("cafebabe"), event_bus=_BUS)

    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_client_unavailable_never_requeues(store: ConcreteAcquireStore) -> None:
    """client_hashes=None (client outage) → the requeue half is skipped (fail-soft)."""
    wanted_id = _grabbed(store, season=3, episode=4, info_hash="deadbeef")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items=None, event_bus=_BUS)

    assert summary.requeued_missing == 0
    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_ownership_error_fails_soft_per_row(store: ConcreteAcquireStore) -> None:
    """An ownership exception leaves the row untouched — never aborts the sweep."""
    wanted_id = _grabbed(store, season=3, episode=5, info_hash="0badf00d")

    summary = reconcile_wanted(store, _ExplodingOwnership(), client_items=_items("0badf00d"), event_bus=_BUS)

    assert summary.checked == 1
    assert summary.closed_owned == 0
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_reconcile_is_idempotent(store: ConcreteAcquireStore) -> None:
    """A second pass finds nothing to do (guarded SQL transitions)."""
    _grabbed(store, season=3, episode=6, info_hash="f92c7b09")
    ownership = _StubOwnership({(3, 6)})

    first = reconcile_wanted(store, ownership, client_items=_items("f92c7b09"), event_bus=_BUS)
    second = reconcile_wanted(store, ownership, client_items=_items("f92c7b09"), event_bus=_BUS)

    assert first.closed_owned == 1
    assert second.checked == 0
    assert second.closed_owned == 0


def test_owned_movie_row_closes_done(store: ConcreteAcquireStore) -> None:
    """The movie shape (Le Robot sauvage): grabbed + owned movie → done."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tmdb_id=1184918),
            kind="movie",
            status="pending",
            enqueued_at=1_750_000_000,
        )
    )
    store.wanted.mark_grabbed(wanted_id, "4bdfb777")

    summary = reconcile_wanted(store, _StubOwnership({(None, None)}), client_items=_items("4bdfb777"), event_bus=_BUS)

    assert summary.closed_owned == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_owned_pending_row_closes_done(store: ConcreteAcquireStore) -> None:
    """A pending row whose episode the library owns closes ``done`` — never re-searched.

    The resurrected-then-indexed shape (prod, HotD S03E03): an episode row was
    resurrected to pending while its file sat unindexed on disk; once the index
    healed, the pending row had to close instead of triggering a duplicate grab
    at the next cron.
    """
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=371572),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            season=3,
            episode=3,
        )
    )

    summary = reconcile_wanted(store, _StubOwnership({(3, 3)}), client_items={}, event_bus=_BUS)

    assert summary.closed_owned == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_unowned_pending_row_stays_pending(store: ConcreteAcquireStore) -> None:
    """An unowned pending row is left queued (no hash logic applies to it)."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=371572),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            season=3,
            episode=4,
        )
    )

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items={}, event_bus=_BUS)

    assert summary.closed_owned == 0
    assert summary.requeued_missing == 0
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "pending"


class _OwnsAllOwnership:
    """Ownership stub that owns every work (movie + episode)."""

    def owns(self, media_ref: MediaRef, *, kind: str, season: int | None = None, episode: int | None = None) -> bool:
        return True


def test_closed_movie_followed_ids_surfaces_only_transitioned_movies(store: ConcreteAcquireStore) -> None:
    """Reconcile surfaces the followed_id of movie rows it closes — for D2-A retirement.

    ACQUIRE-02: the post-dispatch reconcile subscriber reads this to retire the
    follow + emit FilmAcquired. Only ``kind == "movie"`` rows carrying a
    followed_id appear; episodes never do (a series continues).
    """
    followed_id = store.follow.add(
        FollowedSeries(media_ref=MediaRef(tmdb_id=555), title="Ferrari", added_at=1_750_000_000, kind="movie")
    )
    movie_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tmdb_id=555),
            kind="movie",
            status="pending",
            enqueued_at=1_750_000_000,
            followed_id=followed_id,
        )
    )
    store.wanted.mark_grabbed(movie_id, "aa11bb22")
    episode_id = _grabbed(store, season=3, episode=1, info_hash="cc33dd44")

    summary = reconcile_wanted(store, _OwnsAllOwnership(), client_items=_items("aa11bb22", "cc33dd44"), event_bus=_BUS)

    assert summary.closed_owned == 2  # both rows close
    assert summary.closed_movie_followed_ids == (followed_id,)  # only the movie, and only its follow
    assert store.wanted.get(episode_id).status == "done"  # type: ignore[union-attr]


def test_closed_movie_followed_ids_empty_when_nothing_transitions(store: ConcreteAcquireStore) -> None:
    """No owned rows → the movie-followed-id tuple is empty (idempotent second pass)."""
    _grabbed(store, season=1, episode=1, info_hash="ee55ff66")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items=_items("ee55ff66"), event_bus=_BUS)

    assert summary.closed_movie_followed_ids == ()


# ---------------------------------------------------------------------------
# PR #320 review cycle 1 — the §11(d) crash window must stay reachable (F-B2)
# ---------------------------------------------------------------------------


def _crash_window(store: ConcreteAcquireStore, *, season: int, episode: int, info_hash: str) -> int:
    """Insert a row in the §11(d) crash window: hash persisted, status 'searching'.

    ``mark_grabbed`` wrote the info-hash, then the process died before the next
    status write, leaving the row at 'searching'.
    """
    wanted_id = _grabbed(store, season=season, episode=episode, info_hash=info_hash)
    store.wanted.set_status(wanted_id, "searching")
    return wanted_id


def test_owned_crash_window_row_closes_done(store: ConcreteAcquireStore) -> None:
    """A 'searching' row holding a hash closes when the library owns the episode.

    ``reclaim_stale_searching`` refuses to revert this row (re-grabbing an
    already-added torrent would be worse), so reconciliation is the ONLY thing
    that can close it — which means the sweep has to WALK the 'searching'
    status. It used to walk only grabbed + pending, so the row was frozen with
    nobody able to touch it.
    """
    wanted_id = _crash_window(store, season=3, episode=7, info_hash="c0ffee01")

    summary = reconcile_wanted(store, _StubOwnership({(3, 7)}), client_items=_items("c0ffee01"), event_bus=_BUS)

    assert summary.closed_owned == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_vanished_crash_window_row_requeues_pending(store: ConcreteAcquireStore) -> None:
    """A 'searching' row whose torrent vanished and is unowned goes back to pending.

    The vanished-torrent branch keys on the HASH, not on ``status == 'grabbed'``
    — the hash is what says « a torrent was added for this row », and it
    outlives the status.
    """
    wanted_id = _crash_window(store, season=3, episode=8, info_hash="c0ffee02")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items={}, event_bus=_BUS)

    assert summary.requeued_missing == 1
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "pending"
    assert row.grabbed_hash is None


def test_crash_window_row_still_in_client_is_confirmed_grabbed(store: ConcreteAcquireStore) -> None:
    """The torrent IS in the client → the intent is confirmed, not left hanging (M9/D2).

    Was: « stays searching, counted in flight ». That left the row in a state no
    pass could close — ``reclaim_stale_searching`` refuses a hash-carrying row,
    so it sat at 'searching' until (and unless) the library happened to own it,
    with no seed obligation protecting the torrent meanwhile. The intent-hash
    recovery promotes it instead: the add landed, only the status write was lost.
    """
    wanted_id = _crash_window(store, season=3, episode=9, info_hash="c0ffee03")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items=_items("c0ffee03"), event_bus=_BUS)

    assert summary.confirmed_grabbed == 1
    assert summary.still_in_flight == 0
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"
    assert row.grabbed_hash == "c0ffee03"


def test_grabbed_row_still_in_client_stays_in_flight(store: ConcreteAcquireStore) -> None:
    """A row already CONFIRMED 'grabbed' whose torrent lives is simply in flight.

    The confirmation branch is scoped to 'searching' intent rows; a grabbed row
    with a live torrent must keep its status and be counted, exactly as before.
    """
    wanted_id = _grabbed(store, season=3, episode=10, info_hash="c0ffee0a")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items=_items("c0ffee0a"), event_bus=_BUS)

    assert summary.still_in_flight == 1
    assert summary.confirmed_grabbed == 0
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_legacy_pending_row_with_a_stale_hash_is_requeued(store: ConcreteAcquireStore) -> None:
    """Rows the OLD blind recovery left at 'pending' + hash are repaired, not stranded.

    The pre-fix get-then-set recovery forced hash-carrying rows to 'pending'.
    The grab pass then skipped them forever on its hash guard, and the requeue
    was guarded on ``status='grabbed'`` so nothing cleared the stale hash. The
    OPEN-status guard repairs them on the next sweep.
    """
    wanted_id = _grabbed(store, season=4, episode=1, info_hash="c0ffee04")
    store.wanted.set_status(wanted_id, "pending")  # the legacy shape

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items={}, event_bus=_BUS)

    assert summary.requeued_missing == 1
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "pending"
    assert row.grabbed_hash is None


def test_unowned_hashless_pending_row_is_never_requeued(store: ConcreteAcquireStore) -> None:
    """A plain queued row (no hash) is untouched — the hash key must not over-reach."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            season=5,
            episode=1,
        )
    )

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items={}, event_bus=_BUS)

    assert summary.requeued_missing == 0
    assert summary.still_in_flight == 0
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "pending"


def test_owned_available_row_closes_done(store: ConcreteAcquireStore) -> None:
    """Regression (PR #320 review cycle 2, M3): an owned « À récupérer » row closes.

    The sweep walked grabbed + searching + pending only, so a row a search had
    marked ``available`` for media the library ALREADY owns survived every
    reconciliation — a standing order to re-download something already on disk.
    Ownership outranks the queue in every state.
    """
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            season=6,
            episode=1,
        )
    )
    store.wanted.record_search_outcome(wanted_id, "available", 4)
    store.wanted.set_status(wanted_id, "available")

    summary = reconcile_wanted(store, _StubOwnership({(6, 1)}), client_items={}, event_bus=_BUS)

    assert summary.closed_owned == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_unowned_available_row_stays_available(store: ConcreteAcquireStore) -> None:
    """An unowned « À récupérer » row is left for the grab pass — never requeued."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            season=6,
            episode=2,
        )
    )
    store.wanted.record_search_outcome(wanted_id, "available", 4)
    store.wanted.set_status(wanted_id, "available")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items={}, event_bus=_BUS)

    assert summary.closed_owned == 0
    assert summary.requeued_missing == 0
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "available", (
        f"a hash-less available row must stay takeable; got {row.status!r}"
    )


def test_owned_movie_available_row_surfaces_its_follow(store: ConcreteAcquireStore) -> None:
    """A followed FILM whose media landed while « À récupérer » is retired too."""
    followed_id = store.follow.add(
        FollowedSeries(media_ref=MediaRef(tmdb_id=777), title="Le Robot sauvage", added_at=1, kind="movie")
    )
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tmdb_id=777),
            kind="movie",
            status="pending",
            enqueued_at=1_750_000_000,
            followed_id=followed_id,
        )
    )
    store.wanted.set_status(wanted_id, "available")

    summary = reconcile_wanted(store, _OwnsAllOwnership(), client_items={}, event_bus=_BUS)

    assert summary.closed_owned == 1
    assert summary.closed_movie_followed_ids == (followed_id,)


def test_season_row_without_followed_id_is_never_closed(store: ConcreteAcquireStore) -> None:
    """A season row with no ``followed_id`` has no catalog → no ownership answer.

    The season-ownership derivation reads the follow's aired catalog; without a
    ``followed_id`` there is nothing to read, so the blind-spot guard answers
    « not owned » — even when the stub claims (season, None) as owned.
    """
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="season",
            status="pending",
            enqueued_at=1_750_000_000,
            season=3,
            episode=None,
        )
    )

    reconcile_wanted(store, _StubOwnership({(3, None)}), client_items={}, event_bus=_BUS)

    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "pending"  # untouched — not closed to done


# ---------------------------------------------------------------------------
# Review F6 (season-grab) — season rows walk the reconciliation sweep
# ---------------------------------------------------------------------------


def _followed_show(store: ConcreteAcquireStore) -> int:
    """Insert a followed show and return its id."""
    return store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=403245),
            title="Silo",
            added_at=1_750_000_000,
            kind="show",
        )
    )


def _season_row(
    store: ConcreteAcquireStore,
    *,
    followed_id: int,
    season: int,
    info_hash: str | None = None,
) -> int:
    """Insert one season wanted row (optionally grabbed) and return its id."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="season",
            status="pending",
            enqueued_at=1_750_000_000,
            followed_id=followed_id,
            season=season,
            episode=None,
        )
    )
    if info_hash is not None:
        store.wanted.mark_grabbed(wanted_id, info_hash)
    return wanted_id


def test_grabbed_season_all_aired_owned_closes_done(store: ConcreteAcquireStore) -> None:
    """A grabbed season whose aired episodes are ALL owned closes ``done``.

    Review F6: the wholesale kind=="season" skip meant nothing could ever close
    a grabbed season row — it read « en cours » forever even after the whole
    season pack was dispatched to the library.
    """
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e01")

    summary = reconcile_wanted(store, _StubOwnership({(3, 1), (3, 2)}), client_items=_items("5ea50e01"), event_bus=_BUS)

    assert summary.checked == 1
    assert summary.closed_owned == 1
    assert summary.closed_movie_followed_ids == ()  # seasons are shows — no retirement
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_grabbed_season_partially_owned_stays_in_flight(store: ConcreteAcquireStore) -> None:
    """Half the season owned + torrent still in the client → left in flight."""
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e02")

    summary = reconcile_wanted(store, _StubOwnership({(3, 1)}), client_items=_items("5ea50e02"), event_bus=_BUS)

    assert summary.closed_owned == 0
    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_grabbed_season_vanished_torrent_requeues_pending(store: ConcreteAcquireStore) -> None:
    """Season torrent vanished from the client + season not fully owned → requeued.

    Review F6: the skip also starved the vanished-torrent path — a dead season
    grab was never sent back to ``pending``, so the season was never retried.
    """
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e03")

    summary = reconcile_wanted(store, _StubOwnership({(3, 1)}), client_items={}, event_bus=_BUS)

    assert summary.requeued_missing == 1
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "pending"
    assert row.grabbed_hash is None


def test_searching_season_with_hash_in_client_is_confirmed(store: ConcreteAcquireStore) -> None:
    """A §11(d) crash-window SEASON row (searching + hash in client) is confirmed."""
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e04")
    store.wanted.set_status(wanted_id, "searching")

    summary = reconcile_wanted(store, _StubOwnership(set()), client_items=_items("5ea50e04"), event_bus=_BUS)

    assert summary.confirmed_grabbed == 1
    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "grabbed"
    assert row.grabbed_hash == "5ea50e04"


def test_season_with_empty_aired_catalog_is_never_closed(store: ConcreteAcquireStore) -> None:
    """Blind-spot guard: an empty aired catalog can NEVER close a season row.

    Even an owns-everything checker must not close the row — an empty catalog
    is absence of knowledge, not a statement that the season is complete.
    """
    followed_id = _followed_show(store)  # no aired catalog written
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e05")

    summary = reconcile_wanted(store, _OwnsAllOwnership(), client_items=_items("5ea50e05"), event_bus=_BUS)

    assert summary.closed_owned == 0
    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


# ---------------------------------------------------------------------------
# A landed-but-incomplete season pack — the « Les Groos » shape
# ---------------------------------------------------------------------------
#
# wanted 184 (Les Groos S01) sat at ``grabbed`` from 2026-08-28 to 2026-09-01
# reading « En vol » while its media had been on the disk the whole time. The
# pack (``Les.Groos.2026.S01…LOLOPC``) carried 12 of the 13 episodes TVDB
# declares aired, so ``_season_fully_owned`` answered False forever, and the
# torrent was still seeding under its c411 obligation, so neither the requeue
# nor the confirm path applied. A grabbed season has no cutoff and no cadence —
# the search pass walks ``pending`` and the grab pass ``available`` — which left
# the row with NO exit at all, and the missing episode was never searched for.


def _dispatched_journey(
    store: ConcreteAcquireStore,
    *,
    info_hash: str,
    followed_id: int,
    season: int,
    now: int = 1_750_000_000,
) -> None:
    """Record a journey that reached the library for *info_hash*."""
    store.provenance.upsert_grab(
        info_hash,
        followed_id=followed_id,
        media_ref=MediaRef(tvdb_id=403245),
        kind="season",
        grabbed_at=now,
        season=season,
    )
    store.provenance.set_ingest(info_hash, ingest_path="/staging/097-TEMP/pack", ingested_at=now + 60)
    store.provenance.set_dispatch(info_hash, dispatch_path="/disk/series/Silo", dispatched_at=now + 120)


def _capture(bus: EventBus, event_type: type) -> list:
    """Subscribe a sink to *bus* and return the list it fills."""
    seen: list = []
    bus.subscribe(event_type, seen.append)
    return seen


def test_landed_season_pack_missing_an_episode_falls_back_to_episodes(
    store: ConcreteAcquireStore,
) -> None:
    """A dispatched season pack that did not carry every aired episode is FINISHED.

    The season attempt got everything that release will ever give: the row must
    leave « en vol » for the terminal ``fallback_episodes``, and the episode the
    pack did not carry must be re-enqueued so it is searched for on its own.
    """
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08"), (3, 3, None, "2026-01-15")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e10")
    _dispatched_journey(store, info_hash="5ea50e10", followed_id=followed_id, season=3)

    summary = reconcile_wanted(
        store,
        _StubOwnership({(3, 1), (3, 2)}),
        client_items=_items("5ea50e10", progress=1.0),
        event_bus=_BUS,
    )

    assert summary.still_in_flight == 0
    assert summary.fell_back_to_episodes == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "fallback_episodes"


def test_the_fallback_re_enqueues_ONLY_the_episodes_the_pack_did_not_carry(
    store: ConcreteAcquireStore,
) -> None:
    """The owned episodes get no row — only the missing one is queued again."""
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08"), (3, 3, None, "2026-01-15")],
        now=1_750_000_000,
    )
    _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e11")
    _dispatched_journey(store, info_hash="5ea50e11", followed_id=followed_id, season=3)

    reconcile_wanted(
        store,
        _StubOwnership({(3, 1), (3, 2)}),
        client_items=_items("5ea50e11", progress=1.0),
        event_bus=_BUS,
    )

    queued = [(row.season, row.episode) for row in store.wanted.list_pending() if row.kind == "episode"]
    assert queued == [(3, 3)]


def test_the_fallback_announces_itself(store: ConcreteAcquireStore) -> None:
    """§8 — the transition is a visible event, never a silent status flip."""
    bus = EventBus()
    seen = _capture(bus, SeasonFellBackToEpisodes)
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e12")
    _dispatched_journey(store, info_hash="5ea50e12", followed_id=followed_id, season=3)

    reconcile_wanted(
        store,
        _StubOwnership({(3, 1)}),
        client_items=_items("5ea50e12", progress=1.0),
        event_bus=bus,
    )

    assert len(seen) == 1
    assert seen[0].season_wanted_id == wanted_id
    assert seen[0].season == 3
    assert seen[0].reenqueued_count == 1


def test_a_season_still_in_the_pipeline_is_left_alone(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING: only a journey that REACHED the library ends the attempt.

    Ingested-not-yet-dispatched means the pipeline is still working on it —
    declaring the season finished there would re-enqueue episodes the very next
    dispatch is about to shelve.
    """
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e13")
    store.provenance.upsert_grab(
        "5ea50e13",
        followed_id=followed_id,
        media_ref=MediaRef(tvdb_id=403245),
        kind="season",
        grabbed_at=1_750_000_000,
        season=3,
    )
    store.provenance.set_ingest("5ea50e13", ingest_path="/staging/097-TEMP/pack", ingested_at=1_750_000_060)

    summary = reconcile_wanted(
        store,
        _StubOwnership({(3, 1)}),
        client_items=_items("5ea50e13", progress=1.0),
        event_bus=_BUS,
    )

    assert summary.fell_back_to_episodes == 0
    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_a_landed_season_with_no_journey_at_all_is_left_alone(store: ConcreteAcquireStore) -> None:
    """A missing provenance row is absence of knowledge — never a licence to close."""
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e14")

    summary = reconcile_wanted(
        store,
        _StubOwnership({(3, 1)}),
        client_items=_items("5ea50e14", progress=1.0),
        event_bus=_BUS,
    )

    assert summary.fell_back_to_episodes == 0
    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_a_landed_season_with_an_empty_catalog_is_left_alone(store: ConcreteAcquireStore) -> None:
    """Blind-spot guard, second end: no catalog means no « missing » list to act on."""
    followed_id = _followed_show(store)  # no aired catalog written
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e15")
    _dispatched_journey(store, info_hash="5ea50e15", followed_id=followed_id, season=3)

    summary = reconcile_wanted(
        store,
        _StubOwnership(set()),
        client_items=_items("5ea50e15", progress=1.0),
        event_bus=_BUS,
    )

    assert summary.fell_back_to_episodes == 0
    assert summary.still_in_flight == 1
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "grabbed"


def test_a_fully_owned_landed_season_still_closes_done(store: ConcreteAcquireStore) -> None:
    """Ownership outranks the fallback: a complete pack closes, it does not fall back."""
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e16")
    _dispatched_journey(store, info_hash="5ea50e16", followed_id=followed_id, season=3)

    summary = reconcile_wanted(
        store,
        _StubOwnership({(3, 1), (3, 2)}),
        client_items=_items("5ea50e16", progress=1.0),
        event_bus=_BUS,
    )

    assert summary.closed_owned == 1
    assert summary.fell_back_to_episodes == 0
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_the_fallback_never_duplicates_an_episode_row_that_is_already_open(
    store: ConcreteAcquireStore,
) -> None:
    """A live episode row is reused as-is — a duplicate would double-search and double-grab."""
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            followed_id=followed_id,
            season=3,
            episode=2,
        )
    )
    season_wanted_id = _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e17")
    _dispatched_journey(store, info_hash="5ea50e17", followed_id=followed_id, season=3)

    summary = reconcile_wanted(
        store,
        _StubOwnership({(3, 1)}),
        client_items=_items("5ea50e17", progress=1.0),
        event_bus=_BUS,
    )

    assert summary.fell_back_to_episodes == 1
    row = store.wanted.get(season_wanted_id)
    assert row is not None and row.status == "fallback_episodes"
    queued = [(row.season, row.episode) for row in store.wanted.list_pending() if row.kind == "episode"]
    assert queued == [(3, 2)]


def test_the_landed_season_leaves_the_sweep_for_good(store: ConcreteAcquireStore) -> None:
    """Idempotence: a second pass finds a terminal row and queues nothing more."""
    followed_id = _followed_show(store)
    store.aired.replace_for_followed(
        followed_id,
        [(3, 1, None, "2026-01-01"), (3, 2, None, "2026-01-08")],
        now=1_750_000_000,
    )
    _season_row(store, followed_id=followed_id, season=3, info_hash="5ea50e18")
    _dispatched_journey(store, info_hash="5ea50e18", followed_id=followed_id, season=3)
    ownership = _StubOwnership({(3, 1)})
    items = _items("5ea50e18", progress=1.0)

    reconcile_wanted(store, ownership, client_items=items, event_bus=_BUS)
    second = reconcile_wanted(store, ownership, client_items=items, event_bus=_BUS)

    assert second.fell_back_to_episodes == 0
    queued = [(row.season, row.episode) for row in store.wanted.list_pending() if row.kind == "episode"]
    assert queued == [(3, 2)]
