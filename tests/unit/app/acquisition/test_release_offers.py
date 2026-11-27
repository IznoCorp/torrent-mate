"""``ReleaseReads.offers`` and ``release_handle``: the picker's candidates, each with the handle it is chosen by.

``readReleases`` answers each candidate with an ``id`` the grab names it by (never its name), and, with
no key, the candidates of every item the reader may see (what the quality profile counts against). The
keyed read's own rules (own-scoping, the governing row, the numbering) are pinned in
``test_release_reads.py``; these cases hold what the route adds on top.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition.releases import ReleaseReads, release_handle
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from tests.unit.app.acquisition.test_release_reads import (
    ALICE,
    BOB,
    FILM,
    OWNER,
    SHOW,
    _actor,
    _candidate,
    _follow,
    _wanted,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a migrated store on a temp acquire.db and close it afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        The store.
    """
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def test_a_handle_is_stable_for_the_same_candidate_of_the_same_row() -> None:
    """Asked twice, the same candidate has the same handle: a pick made on one read names it on the next."""
    candidate = _candidate(1, "Show.S02E05.1080p", season=2, episode=5)

    assert release_handle(7, candidate) == release_handle(7, replace(candidate))


def test_a_handle_names_its_row_before_its_digest() -> None:
    """The grab finds the wanted row from the handle alone: ``<wantedId>:<digest>``."""
    wanted_id, _, digest = release_handle(42, _candidate(1, "Show.S02E05")).partition(":")

    assert wanted_id == "42"
    assert digest != ""


def test_a_handle_differs_by_row_and_by_candidate() -> None:
    """Two rows offering one release, or one row offering two, never share a handle."""
    first = _candidate(1, "Show.S02E05.1080p")
    second = _candidate(2, "Show.S02E05.720p")

    assert len({release_handle(1, first), release_handle(2, first), release_handle(1, second)}) == 3


def test_a_replaced_set_does_not_keep_the_handle_of_a_release_that_left_it() -> None:
    """The handle follows the release, not its rank: a release that is gone has no handle to be chosen by."""
    kept = _candidate(1, "Show.S02E05.1080p")
    moved_up = replace(kept, rank=2)
    gone = _candidate(1, "Show.S02E05.2160p")

    assert release_handle(1, kept) == release_handle(1, moved_up)
    assert release_handle(1, kept) != release_handle(1, gone)


def test_a_keyed_offer_carries_its_row_and_the_handle_of_its_candidate(store: ConcreteAcquireStore) -> None:
    """Each offer is a candidate in rank order with the wanted row it came from."""
    follow = _follow(store, MediaRef(tvdb_id=81189))
    wanted = _wanted(store, follow, season=2, episode=5)
    first, second = _candidate(1, "Show.S02E05.1080p", season=2, episode=5), _candidate(2, "Show.S02E05.720p")
    store.candidates.replace(wanted, [second, first])

    offers = ReleaseReads(store, owner=OWNER).offers(_actor(ALICE), SHOW, 2, 5)

    assert [(o.wanted_id, o.candidate.title, o.handle) for o in offers] == [
        (wanted, "Show.S02E05.1080p", release_handle(wanted, first)),
        (wanted, "Show.S02E05.720p", release_handle(wanted, second)),
    ]


def test_no_key_offers_the_candidates_of_every_item_the_reader_may_see(store: ConcreteAcquireStore) -> None:
    """With no key, every readable follow's open rows answer: the profile counts against all of them."""
    show = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    film = _follow(store, MediaRef(tmdb_id=603), asked_by=ALICE)
    store.candidates.replace(_wanted(store, show, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    store.candidates.replace(_wanted(store, film, kind="movie"), [_candidate(1, "The.Matrix.1999")])

    offers = ReleaseReads(store, owner=OWNER).offers(_actor(ALICE), None, None, None)

    assert sorted(o.candidate.title for o in offers) == ["Show.S02E05", "The.Matrix.1999"]


def test_no_key_leaves_out_what_the_reader_may_not_see(store: ConcreteAcquireStore) -> None:
    """Another member's follow is filtered out of the whole as it is out of one read; see.others lifts it."""
    theirs = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    mine = _follow(store, MediaRef(tvdb_id=70000), asked_by=BOB)
    store.candidates.replace(_wanted(store, theirs, season=1, episode=1), [_candidate(1, "Alice.S01E01")])
    store.candidates.replace(_wanted(store, mine, season=1, episode=1), [_candidate(1, "Bob.S01E01")])
    reads = ReleaseReads(store, owner=OWNER)

    assert [o.candidate.title for o in reads.offers(_actor(BOB, Right.ACQUISITION_PILOT_OWN), None, None, None)] == [
        "Bob.S01E01"
    ]
    assert sorted(
        o.candidate.title for o in reads.offers(_actor(BOB, Right.ACQUISITION_SEE_OTHERS), None, None, None)
    ) == ["Alice.S01E01", "Bob.S01E01"]


def test_no_key_leaves_out_closed_rows_and_removed_follows(store: ConcreteAcquireStore) -> None:
    """A done row and a removed follow are history: their stale sets are not counted."""
    live = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    removed = _follow(store, MediaRef(tvdb_id=70000), asked_by=ALICE)
    store.candidates.replace(_wanted(store, live, season=2, episode=5), [_candidate(1, "Live")])
    store.candidates.replace(_wanted(store, live, season=2, episode=6, status="done"), [_candidate(1, "Done")])
    store.candidates.replace(_wanted(store, removed, season=1, episode=1), [_candidate(1, "Removed")])
    store.requesters.save_follow(removed, [], removed_at=500, min_resolution=None, active=False)

    offers = ReleaseReads(store, owner=OWNER).offers(_actor(ALICE), None, None, None)

    assert [o.candidate.title for o in offers] == ["Live"]


def test_no_key_keeps_the_latest_open_row_of_each_coordinate_only(store: ConcreteAcquireStore) -> None:
    """Two open rows at one episode (a re-follow left one): the later row's set speaks, as in a keyed read."""
    follow = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    older = _wanted(store, follow, season=2, episode=5, status="searching")
    newer = _wanted(store, follow, season=2, episode=5, status="available")
    store.candidates.replace(older, [_candidate(1, "Older")])
    store.candidates.replace(newer, [_candidate(1, "Newer")])

    offers = ReleaseReads(store, owner=OWNER).offers(_actor(ALICE), None, None, None)

    assert [o.candidate.title for o in offers] == ["Newer"]


def test_no_key_with_a_season_narrows_to_that_season(store: ConcreteAcquireStore) -> None:
    """A season (and an episode) asked with no key keeps the rows at those coordinates."""
    follow = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "S02E05")])
    store.candidates.replace(_wanted(store, follow, season=3, episode=1), [_candidate(1, "S03E01")])
    reads = ReleaseReads(store, owner=OWNER)

    assert [o.candidate.title for o in reads.offers(_actor(ALICE), None, 3, None)] == ["S03E01"]
    assert [o.candidate.title for o in reads.offers(_actor(ALICE), None, 2, 5)] == ["S02E05"]


def test_a_keyed_film_offer_names_the_film_row(store: ConcreteAcquireStore) -> None:
    """A film is asked with neither season nor episode and offers its single row's set."""
    follow = _follow(store, MediaRef(tmdb_id=603), asked_by=ALICE)
    wanted = _wanted(store, follow, kind="movie")
    store.candidates.replace(wanted, [_candidate(1, "The.Matrix.1999.1080p")])

    (offer,) = ReleaseReads(store, owner=OWNER).offers(_actor(ALICE), FILM, None, None)

    assert (offer.wanted_id, offer.candidate.season, offer.candidate.episode) == (wanted, None, None)
