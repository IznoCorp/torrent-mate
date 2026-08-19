"""Tests for the five-state truth facts (web/acquisition/truth.py — acq-states).

The named production cases pin the derivation:
- Silo: everything aired is owned, one phantom grabbed row → ``up_to_date`` card
  (``acquiring_count`` 0), never « en cours d'acquisition ».
- House of the Dragon: an aired episode neither owned nor open in the queue →
  ``unverified`` (no open row = no verdict = no knowledge), never « à jour ».

Translated from the P0-B.2 four-bucket model (inflight/queued/missing) to the
five-state counts: each test keeps its original intent, only the vocabulary and
the honest-ignorance rules changed.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition.truth import FollowTruth, compute_follow_truth, compute_movie_truth
from personalscraper.web.models.acquisition import FollowedSeriesItem, MediaRefResponse, MovieFacts


class _StubChecker:
    """Ownership checker stub exposing a fixed owned-pairs set."""

    def __init__(self, pairs: set[tuple[int, int]]) -> None:
        self._pairs = pairs

    def owned_pairs(self, media_ref: MediaRef) -> set[tuple[int, int]]:
        return self._pairs


class _MovieChecker:
    """Ownership checker stub exposing a fixed ``owns`` verdict for a film."""

    def __init__(self, *, owned: bool) -> None:
        self._owned = owned

    def owns(self, media_ref: MediaRef, *, kind: str) -> bool:
        assert kind == "movie"
        return self._owned


@pytest.fixture
def acquire_conn(tmp_path: Path):
    """Yield a read connection to a migrated temp acquire.db with one follow."""
    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    # Touch a sub-store so the schema exists.
    store.wanted.list_pending()
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    conn.execute(
        "INSERT INTO followed_series (id, media_ref_json, title, active, added_at, kind) "
        "VALUES (1, '{\"tvdb_id\": 403245}', 'Silo', 1, 1750000000, 'show')"
    )
    conn.commit()
    yield conn
    conn.close()
    store.close()


def _seed_aired(conn: sqlite3.Connection, pairs: list[tuple[int, int]]) -> None:
    """Insert aired-catalog rows for followed_id=1."""
    conn.executemany(
        "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) "
        "VALUES (1, ?, ?, NULL, '2026-01-01', 1750000000)",
        pairs,
    )
    conn.commit()


def _seed_wanted(
    conn: sqlite3.Connection,
    season: int,
    episode: int,
    status: str,
    *,
    outcome: str | None = None,
    found: int | None = None,
) -> None:
    """Insert one episode wanted row for followed_id=1, with its search verdict.

    Args:
        conn: Open connection to the temp acquire.db.
        season: Season number.
        episode: Episode number.
        status: The wanted row status.
        outcome: ``last_search_outcome`` (``None`` = never searched).
        found: ``last_search_found`` (``None`` = the search did not conclude).
    """
    conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, status, enqueued_at, "
        "last_search_outcome, last_search_found) "
        "VALUES (1, '{\"tvdb_id\": 403245}', 'episode', ?, ?, ?, 1750000000, ?, ?)",
        (season, episode, status, outcome, found),
    )
    conn.commit()


REF = MediaRef(tvdb_id=403245)


def test_no_catalog_yields_none_facts(acquire_conn: sqlite3.Connection) -> None:
    """No cached catalog → all-None facts (caller degrades to raw counters)."""
    truth = compute_follow_truth(acquire_conn, _StubChecker(set()), followed_id=1, media_ref=REF)
    assert truth == FollowTruth()


def test_silo_shape_phantom_grabbed_is_not_inflight(acquire_conn: sqlite3.Connection) -> None:
    """All aired episodes owned + one grabbed row → nothing in acquisition.

    The Silo bug: the card said « En cours d'acquisition » from a raw
    ``grabbed`` counter while every episode chip was green. A grabbed row whose
    episode the library owns is a phantom, not an acquisition.
    """
    _seed_aired(acquire_conn, [(3, 1), (3, 2)])
    _seed_wanted(acquire_conn, 3, 1, "grabbed")
    truth = compute_follow_truth(acquire_conn, _StubChecker({(3, 1), (3, 2)}), followed_id=1, media_ref=REF)

    assert truth.aired_count == 2
    assert truth.owned_count == 2
    assert truth.acquiring_count == 0
    assert truth.to_grab_count == 0
    assert truth.pending_count == 0
    assert truth.unverified_count == 0

    # And the derived card status is « à jour », never « en cours ».
    item = _item(truth, wanted_grabbed=1)
    assert item.status == "up_to_date"


def test_hotd_shape_unqueued_missing_episode(acquire_conn: sqlite3.Connection) -> None:
    """An aired episode neither owned nor open in the queue → unverified.

    Translated from the P0-B.2 ``missing`` bucket: an episode with no OPEN
    wanted row carries no search verdict, so the honest reading is « on ne sait
    pas » (``unverified``) — the card must never read « à jour » here, which is
    the invariant this test has always defended.
    """
    _seed_aired(acquire_conn, [(3, 3), (3, 4)])
    # E3 owned; E4 has an abandoned row (not an open one) → no verdict to read.
    _seed_wanted(acquire_conn, 3, 4, "abandoned")
    truth = compute_follow_truth(acquire_conn, _StubChecker({(3, 3)}), followed_id=1, media_ref=REF)

    assert truth.unverified_count == 1
    assert _item(truth, wanted_grabbed=0).status == "unverified"


def test_real_inflight_and_queue_counts(acquire_conn: sqlite3.Connection) -> None:
    """Unowned aired episodes split between grabbed and an unsearched pending row.

    Translated: the ``pending`` row was never searched (no verdict columns), so
    it counts as ``unverified`` rather than the former ``queued`` bucket — but
    the card still reads « en cours d'acquisition », since ``acquiring``
    outranks ``unverified``.
    """
    _seed_aired(acquire_conn, [(1, 1), (1, 2), (1, 3)])
    _seed_wanted(acquire_conn, 1, 2, "grabbed")
    _seed_wanted(acquire_conn, 1, 3, "pending")
    truth = compute_follow_truth(acquire_conn, _StubChecker({(1, 1)}), followed_id=1, media_ref=REF)

    assert truth.owned_count == 1
    assert truth.acquiring_count == 1
    assert truth.unverified_count == 1
    assert truth.to_grab_count == 0
    assert truth.pending_count == 0
    assert _item(truth, wanted_grabbed=1).status == "acquiring"


def test_searched_pending_row_splits_to_grab_and_pending(acquire_conn: sqlite3.Connection) -> None:
    """The last search verdict decides between « à récupérer » and « en attente ».

    New in the five-state model: two identical ``pending`` rows read differently
    once their verdicts differ — one found a takeable candidate, the other
    concluded there was none. The card shows the actionable one.
    """
    _seed_aired(acquire_conn, [(2, 1), (2, 2)])
    _seed_wanted(acquire_conn, 2, 1, "pending", outcome="all_filtered", found=0)
    _seed_wanted(acquire_conn, 2, 2, "pending", outcome="available", found=2)
    truth = compute_follow_truth(acquire_conn, _StubChecker(set()), followed_id=1, media_ref=REF)

    assert truth.pending_count == 1
    assert truth.to_grab_count == 1
    assert truth.unverified_count == 0
    assert _item(truth, wanted_grabbed=0).status == "to_grab"


def test_inconclusive_verdict_never_reads_pending(acquire_conn: sqlite3.Connection) -> None:
    """A tracker outage is « non vérifié », never « en attente » (panne ≠ absence)."""
    _seed_aired(acquire_conn, [(4, 1)])
    _seed_wanted(acquire_conn, 4, 1, "pending", outcome="trackers_unavailable", found=None)
    truth = compute_follow_truth(acquire_conn, _StubChecker(set()), followed_id=1, media_ref=REF)

    assert truth.unverified_count == 1
    assert truth.pending_count == 0
    assert _item(truth, wanted_grabbed=0).status == "unverified"


def test_absorbed_episodes_read_acquiring_not_unverified(acquire_conn: sqlite3.Connection) -> None:
    """Review F7: a season being grabbed keeps the card at « en acquisition ».

    Every live episode wanted of the season was absorbed by an open season row
    (R5). The absorbed rows used to be silenced (open-statuses-only selection),
    dropping every episode to « never searched » → the card degraded to
    « Non vérifié » while a season grab was actively in flight.
    """
    _seed_aired(acquire_conn, [(5, 1), (5, 2)])
    _seed_wanted(acquire_conn, 5, 1, "absorbed")
    _seed_wanted(acquire_conn, 5, 2, "absorbed")
    # The open season row carrying the acquisition (kind='season', episode NULL).
    acquire_conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, status, enqueued_at) "
        "VALUES (1, '{\"tvdb_id\": 403245}', 'season', 5, NULL, 'grabbed', 1750000000)"
    )
    acquire_conn.commit()

    truth = compute_follow_truth(acquire_conn, _StubChecker(set()), followed_id=1, media_ref=REF)

    assert truth.acquiring_count == 2  # absorbed episodes are IN MOTION
    assert truth.unverified_count == 0
    assert _item(truth, wanted_grabbed=0).status == "acquiring"


def _item(truth: FollowTruth, *, wanted_grabbed: int) -> FollowedSeriesItem:
    """Build a FollowedSeriesItem carrying the truth facts (status is computed)."""
    return FollowedSeriesItem(
        id=1,
        title="Silo",
        media_ref=MediaRefResponse(tvdb_id=403245),
        active=True,
        kind="show",
        added_at=1750000000.0,
        wanted_pending=0,
        wanted_grabbed=wanted_grabbed,
        aired_count=truth.aired_count,
        owned_count=truth.owned_count,
        to_grab_count=truth.to_grab_count,
        acquiring_count=truth.acquiring_count,
        pending_count=truth.pending_count,
        unverified_count=truth.unverified_count,
    )


# ── D2-B: film status keyed on ownership (disk presence), not the raw counter ──

_MOVIE_REF = MediaRef(tmdb_id=100001)


def _seed_movie_follow(conn: sqlite3.Connection) -> None:
    """Insert the kind='movie' follow (id=2) the film cases hang off."""
    conn.execute(
        "INSERT INTO followed_series (id, media_ref_json, title, active, added_at, kind) "
        "VALUES (2, '{\"tmdb_id\": 100001}', 'Ferrari', 1, 1750000000, 'movie')"
    )
    conn.commit()


def _seed_movie_wanted(
    conn: sqlite3.Connection,
    status: str,
    *,
    outcome: str | None = None,
    found: int | None = None,
) -> None:
    """Insert one movie wanted row for followed_id=2 with its search verdict."""
    conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, status, enqueued_at, "
        "last_search_outcome, last_search_found) "
        "VALUES (2, '{\"tmdb_id\": 100001}', 'movie', ?, 1750000000, ?, ?)",
        (status, outcome, found),
    )
    conn.commit()


def _movie_item(facts: MovieFacts, *, wanted_grabbed: int, wanted_pending: int) -> FollowedSeriesItem:
    """Build a kind='movie' FollowedSeriesItem carrying the film's unit facts."""
    return FollowedSeriesItem(
        id=2,
        title="Ferrari",
        media_ref=MediaRefResponse(tmdb_id=100001),
        active=True,
        kind="movie",
        added_at=1750000000.0,
        wanted_pending=wanted_pending,
        wanted_grabbed=wanted_grabbed,
        movie_facts=facts,
    )


def test_movie_owned_beats_phantom_grabbed_counter(acquire_conn: sqlite3.Connection) -> None:
    """A film ON DISK reads ``up_to_date`` even with a stale ``grabbed`` row.

    Red-on-old: the movie branch derived status purely from ``wanted_grabbed``,
    so a phantom grabbed row pinned an already-owned film at « en cours
    d'acquisition ». Ownership (disk presence) wins.
    """
    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "grabbed")
    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=True), followed_id=2, media_ref=_MOVIE_REF)
    assert facts.owned is True
    assert facts.wanted_status == "grabbed"
    assert _movie_item(facts, wanted_grabbed=1, wanted_pending=0).status == "up_to_date"


def test_movie_absent_with_grabbed_is_acquiring(acquire_conn: sqlite3.Connection) -> None:
    """A film NOT on disk with a grabbed row → ``acquiring``."""
    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "grabbed")
    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=False), followed_id=2, media_ref=_MOVIE_REF)
    assert facts.owned is False
    assert _movie_item(facts, wanted_grabbed=1, wanted_pending=0).status == "acquiring"


def test_movie_absent_available_row_is_to_grab(acquire_conn: sqlite3.Connection) -> None:
    """A film NOT on disk whose search found a takeable candidate → ``to_grab``.

    Translated from the old « pending → pending » case: a queued row now reads
    from its verdict, and an ``available`` row is exactly the actionable state
    the old model could not express.
    """
    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "available", outcome="available", found=3)
    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=False), followed_id=2, media_ref=_MOVIE_REF)
    assert facts.wanted_status == "available"
    assert _movie_item(facts, wanted_grabbed=0, wanted_pending=1).status == "to_grab"


def test_movie_absent_searched_nothing_takeable_is_pending(acquire_conn: sqlite3.Connection) -> None:
    """A film NOT on disk, searched, nothing takeable → ``pending``."""
    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "pending", outcome="no_candidates", found=0)
    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=False), followed_id=2, media_ref=_MOVIE_REF)
    assert _movie_item(facts, wanted_grabbed=0, wanted_pending=1).status == "pending"


def test_movie_absent_no_open_row_is_unverified(acquire_conn: sqlite3.Connection) -> None:
    """A film NOT on disk with no wanted row at all → honest ``unverified``.

    Old code read ``up_to_date`` here (no grabbed, no pending) — claiming a film
    the library does not hold is « à jour ». Translated from ``incomplete``: with
    no row there is no verdict either, so the honest reading is « on ne sait pas ».
    """
    _seed_movie_follow(acquire_conn)
    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=False), followed_id=2, media_ref=_MOVIE_REF)
    assert facts == MovieFacts(owned=False)
    assert _movie_item(facts, wanted_grabbed=0, wanted_pending=0).status == "unverified"


def test_movie_open_row_wins_over_closed_leftover(acquire_conn: sqlite3.Connection) -> None:
    """A re-followed film reads its OPEN row, not the abandoned leftover."""
    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "abandoned", outcome="no_candidates", found=0)
    _seed_movie_wanted(acquire_conn, "grabbed")
    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=False), followed_id=2, media_ref=_MOVIE_REF)
    assert facts.wanted_status == "grabbed"
    assert _movie_item(facts, wanted_grabbed=1, wanted_pending=0).status == "acquiring"


# ---------------------------------------------------------------------------
# D3 — one selection rule everywhere: a closed row is history, films included
# ---------------------------------------------------------------------------


def test_movie_whose_only_row_is_abandoned_is_unverified(acquire_conn: sqlite3.Connection) -> None:
    """A film whose ONLY row is ``abandoned`` reads ``unverified``, not « En attente ».

    Red-on-old (VISIBLE CHANGE, arbitrated by D3): the movie selector used to
    fall back to « the most recent row of ANY status » when no open row existed,
    so a closed row's stale verdict (``no_candidates``, found=0) still answered
    for the card and the film read « En attente » — a queue state for an item
    that is no longer in the queue. Episodes never behaved that way
    (``select_wanted_facts`` drops closed rows); films now use the same rule.
    """
    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "abandoned", outcome="no_candidates", found=0)

    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=False), followed_id=2, media_ref=_MOVIE_REF)

    assert facts == MovieFacts(owned=False), "a closed row must not speak for the card"
    assert _movie_item(facts, wanted_grabbed=0, wanted_pending=0).status == "unverified"


def test_movie_whose_only_row_is_done_is_unverified_when_unowned(acquire_conn: sqlite3.Connection) -> None:
    """Same rule for a ``done`` leftover: history cannot claim the card.

    An unowned film with a ``done`` row is a contradiction (the file left the
    library, or the closure was wrong). The honest reading is « we do not know »
    — never the stale verdict of a finished acquisition.
    """
    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "done", outcome="grabbed", found=1)

    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=False), followed_id=2, media_ref=_MOVIE_REF)

    assert facts == MovieFacts(owned=False)
    assert _movie_item(facts, wanted_grabbed=0, wanted_pending=0).status == "unverified"


def test_owned_film_with_only_a_closed_row_still_reads_up_to_date(acquire_conn: sqlite3.Connection) -> None:
    """Dropping the closed row never hides OWNERSHIP: the disk still wins.

    The rule change removes a stale VERDICT, not the library fact — a film on
    disk whose row was closed reads « À jour » exactly as before.
    """
    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "done", outcome="grabbed", found=1)

    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=True), followed_id=2, media_ref=_MOVIE_REF)

    assert facts.owned is True
    assert facts.wanted_status is None
    assert _movie_item(facts, wanted_grabbed=0, wanted_pending=0).status == "up_to_date"


def test_movie_selection_matches_the_episode_selector(acquire_conn: sqlite3.Connection) -> None:
    """The film card and the episode matrix agree on WHICH row governs.

    Same rows in, same governing facts out — the property D3 buys: one rule
    everywhere, so the two surfaces can no longer disagree.
    """
    from personalscraper.web.acquisition.states import select_wanted_facts

    _seed_movie_follow(acquire_conn)
    _seed_movie_wanted(acquire_conn, "abandoned", outcome="no_candidates", found=0)
    _seed_movie_wanted(acquire_conn, "pending", outcome="trackers_unavailable", found=None)
    _seed_movie_wanted(acquire_conn, "done", outcome="grabbed", found=1)

    rows = acquire_conn.execute(
        "SELECT id, status, last_search_outcome, last_search_found FROM wanted WHERE followed_id = 2"
    ).fetchall()
    expected = select_wanted_facts([tuple(r) for r in rows])  # type: ignore[misc]

    facts = compute_movie_truth(acquire_conn, _MovieChecker(owned=False), followed_id=2, media_ref=_MOVIE_REF)

    assert (facts.wanted_status, facts.last_search_outcome, facts.last_search_found) == expected


# ---------------------------------------------------------------------------
# episode-states D2 / ACC-03 — announced futures never reach the card counts
# ---------------------------------------------------------------------------


def _seed_aired_dated(conn: sqlite3.Connection, pairs: list[tuple[int, int, str]]) -> None:
    """Insert aired-catalog rows carrying an explicit ``air_date`` per episode."""
    conn.executemany(
        "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) "
        "VALUES (1, ?, ?, NULL, ?, 1750000000)",
        pairs,
    )
    conn.commit()


def test_future_episode_is_excluded_from_the_card_counts(acquire_conn: sqlite3.Connection) -> None:
    """ACC-03: a cached FUTURE episode never degrades the card — the show stays « À jour ».

    Two aired episodes (both owned) plus a future one. The future is cached (the
    matrix will show it as ``announced``) but must NOT be counted here: with it in
    the aired set it would derive to ``unverified`` (no wanted row, unowned)
    and pull the card off « À jour ». The aired-only query drops it.
    """
    from datetime import date

    today = date(2024, 6, 15)
    _seed_aired_dated(
        acquire_conn,
        [
            (1, 1, "2024-06-01"),  # aired, owned
            (1, 2, "2024-06-10"),  # aired, owned
            (1, 3, "2025-01-01"),  # FUTURE — announced
        ],
    )

    truth = compute_follow_truth(
        acquire_conn, _StubChecker({(1, 1), (1, 2)}), followed_id=1, media_ref=REF, today=today
    )

    assert truth.aired_count == 2, "only the two AIRED episodes are counted"
    assert truth.owned_count == 2
    assert truth.unverified_count == 0, "the future must not fall into unverified and degrade the card"

    # And the aggregated card status stays « À jour ».
    item = FollowedSeriesItem(
        id=1,
        title="Severance",
        media_ref=MediaRefResponse(tvdb_id=403245),
        active=True,
        kind="show",
        added_at=1750000000.0,
        wanted_pending=0,
        wanted_grabbed=0,
        aired_count=truth.aired_count,
        owned_count=truth.owned_count,
        to_grab_count=truth.to_grab_count,
        acquiring_count=truth.acquiring_count,
        pending_count=truth.pending_count,
        unverified_count=truth.unverified_count,
    )
    assert item.status == "up_to_date"


def test_only_future_episodes_read_unverified(acquire_conn: sqlite3.Connection) -> None:
    """A series whose ONLY cached episodes are future has no aired catalog → unverified.

    Honest: there is nothing aired to be « up to date » on yet, so the card
    reads « we don't know » — never « À jour » on the strength of a future.
    """
    from datetime import date

    _seed_aired_dated(acquire_conn, [(1, 1, "2025-01-01"), (1, 2, "2025-02-01")])

    truth = compute_follow_truth(
        acquire_conn, _StubChecker(set()), followed_id=1, media_ref=REF, today=date(2024, 6, 15)
    )

    assert truth == FollowTruth(), "only-future cache is no aired catalog → all-None sentinel"


# ── acq-escalade / incident 2026-08-04 — l'épisode absorbé suit SA saison ──


def _seed_season_and_absorb(
    conn: sqlite3.Connection,
    season: int,
    episodes: list[int],
    *,
    season_status: str,
    outcome: str | None = None,
    found: int | None = None,
) -> None:
    """Create a season wanted and absorb *episodes* onto it, as R5 does."""
    cur = conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, status, enqueued_at, "
        "last_search_outcome, last_search_found) "
        "VALUES (1, '{\"tvdb_id\": 403245}', 'season', ?, NULL, ?, 1750000000, ?, ?)",
        (season, season_status, outcome, found),
    )
    season_id = cur.lastrowid
    for ep in episodes:
        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, status, enqueued_at, "
            "absorbed_by) VALUES (1, '{\"tvdb_id\": 403245}', 'episode', ?, ?, 'absorbed', 1750000000, ?)",
            (season, ep, season_id),
        )
    conn.commit()


def test_absorbed_episodes_count_as_acquiring_while_the_season_is_grabbed(
    acquire_conn: sqlite3.Connection,
) -> None:
    """A season actually downloading ⇒ its absorbed episodes ARE in acquisition."""
    _seed_aired(acquire_conn, [(15, 21), (15, 22)])
    _seed_season_and_absorb(acquire_conn, 15, [21, 22], season_status="grabbed", outcome="grabbed", found=4)

    truth = compute_follow_truth(acquire_conn, _StubChecker(set()), followed_id=1, media_ref=REF)

    assert truth.acquiring_count == 2


def test_absorbed_episodes_stop_claiming_acquisition_once_the_season_is_requeued(
    acquire_conn: sqlite3.Connection,
) -> None:
    """REGRESSION 2026-08-04 — the reswitch requeued the season; nothing is in flight.

    The operator saw « source bloquée, bascule vers une autre release » and then no
    change at all: the four absorbed American Dad episodes kept reading « En cours
    d'acquisition » because the card never looked at the season row. A requeued
    season means « on cherche à nouveau », not « en cours » (§2).
    """
    _seed_aired(acquire_conn, [(15, 21), (15, 22)])
    _seed_season_and_absorb(acquire_conn, 15, [21, 22], season_status="pending", outcome=None, found=None)

    truth = compute_follow_truth(acquire_conn, _StubChecker(set()), followed_id=1, media_ref=REF)

    assert truth.acquiring_count == 0, "nothing is downloading — the card must not say it is"
    assert truth.unverified_count == 2, "a requeued season has concluded nothing yet"


def _seed_dated(conn: sqlite3.Connection, rows: list[tuple[int, int, str]]) -> None:
    """Insert catalog rows carrying an explicit air date.

    Args:
        conn: Open connection to the temp acquire.db.
        rows: ``(season, episode, air_date)`` triples.
    """
    conn.executemany(
        "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) "
        "VALUES (1, ?, ?, NULL, ?, 1750000000)",
        rows,
    )
    conn.commit()


class TestAnnouncedCount:
    """The futures are counted — and only ever tell « À jour » from « Terminé »."""

    def test_futures_are_counted_but_enter_no_bucket(self, acquire_conn: sqlite3.Connection) -> None:
        """Two aired owned, three announced: the card is caught up AND knows it is not over."""
        _seed_dated(
            acquire_conn,
            [
                (1, 1, "2026-01-01"),
                (1, 2, "2026-01-08"),
                (1, 3, "2027-01-01"),
                (1, 4, "2027-01-08"),
                (1, 5, "2027-01-15"),
            ],
        )

        truth = compute_follow_truth(
            acquire_conn,
            _StubChecker({(1, 1), (1, 2)}),
            followed_id=1,
            media_ref=REF,
            today=date(2026, 6, 1),
        )

        assert truth.aired_count == 2, "a future must never inflate the aired count"
        assert truth.owned_count == 2
        assert truth.unverified_count == 0, "a future must never land in a bucket"
        assert truth.announced_count == 3

    def test_no_future_leaves_the_count_at_zero(self, acquire_conn: sqlite3.Connection) -> None:
        """Nothing ahead → 0, which is a fact, not an absence of one."""
        _seed_dated(acquire_conn, [(1, 1, "2026-01-01"), (1, 2, "2026-01-08")])

        truth = compute_follow_truth(
            acquire_conn,
            _StubChecker({(1, 1), (1, 2)}),
            followed_id=1,
            media_ref=REF,
            today=date(2026, 6, 1),
        )

        assert truth.announced_count == 0

    def test_dateless_legacy_rows_are_aired_not_announced(self, acquire_conn: sqlite3.Connection) -> None:
        """A cache written before air dates existed reads as aired, as it always has."""
        _seed_aired(acquire_conn, [(1, 1), (1, 2)])
        acquire_conn.execute("UPDATE aired_episode SET air_date = '' WHERE followed_id = 1")
        acquire_conn.commit()

        truth = compute_follow_truth(
            acquire_conn,
            _StubChecker({(1, 1), (1, 2)}),
            followed_id=1,
            media_ref=REF,
            today=date(2026, 6, 1),
        )

        assert truth.aired_count == 2
        assert truth.announced_count == 0

    def test_a_catalogue_of_only_futures_is_still_no_knowledge(self, acquire_conn: sqlite3.Connection) -> None:
        """Announced-only → the all-None sentinel: there is nothing to be up to date ON.

        The sentinel wins over the announced count: a series with no aired
        episode reads ``unverified``, and must not carry a stray count that
        would suggest we know something about its library state.
        """
        _seed_dated(acquire_conn, [(1, 1, "2027-01-01"), (1, 2, "2027-01-08")])

        truth = compute_follow_truth(
            acquire_conn,
            _StubChecker(set()),
            followed_id=1,
            media_ref=REF,
            today=date(2026, 6, 1),
        )

        assert truth == FollowTruth()
