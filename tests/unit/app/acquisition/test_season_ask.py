"""``SeasonAsk``: a whole season asked by medium, of a follow or as a one-off request (K3 P7, DESIGN § 2.7).

A followed show gets a season row ``trigger='manual'`` absorbing its live episodes, and one ``prime``;
an owned show nobody follows gets a request row (scope ``request``, the caller its requester ``via
request``), never listed among the follows; neither is ``acquisition.not_found``. An open season row
answers ``reused``. ``absorbedCount`` counts the season's aired episodes the library does not hold.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.acquire._wanted_store import _WantedSubStore
from personalscraper.acquire.catalogue import CatalogueStore
from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.acquisition.seasons import HeldShow, IndexedShows
from personalscraper.app.errors import AppBadRequest, AppForbidden, AppNotFound, RefusalCode
from personalscraper.app.library.completeness import CatalogueView
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import LibraryIndex
from personalscraper.indexer.ownership import IndexerOwnershipChecker
from tests.unit.app.acquisition.follow_world import ALICE, BOB, DAVE, MEMBER, OWNER, FollowWorld, actor
from tests.unit.app.library.world import FixtureIndex, catalogued

SHOW = AcquisitionKey.parse("tvdb:81189")
OWNED = AcquisitionKey.parse("tvdb:4242")


@pytest.fixture
def world(tmp_path: Path) -> Iterator[FollowWorld]:
    """A world with an empty acquire store, the seeded roster and an empty queue.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The world.
    """
    built = FollowWorld(tmp_path)
    try:
        yield built
    finally:
        built.close()


def _followed(world: FollowWorld) -> int:
    """Alice follows :data:`SHOW`; its prime is settled away so the queue is empty.

    Args:
        world: The world.

    Returns:
        The follow's row.
    """
    world.follows.create(actor(ALICE), SHOW, title="Breaking Bad", kind="show", year=2008)
    (row,) = world.store.follow.find_all_by_ref(SHOW.ref(), kind="show")
    assert row.id is not None
    world.settle_all()
    return row.id


def _hold_owned(world: FollowWorld) -> None:
    """The library holds :data:`OWNED`: season 1 aired 1–3, episode 1 held.

    Args:
        world: The world.
    """
    world.shows.shows["tvdb:4242"] = HeldShow(
        title="Owned Show",
        year=2020,
        ref=MediaRef(tvdb_id=4242, tmdb_id=99),
        aired=frozenset({(1, 1), (1, 2), (1, 3), (2, 1)}),
        owned=frozenset({(1, 1)}),
    )


def test_a_followed_shows_season_is_written_manual_absorbs_and_is_primed(world: FollowWorld) -> None:
    """Season row ``trigger='manual'``; a pending episode absorbed, a grabbed one only pointed; one prime."""
    row = _followed(world)
    pending = world.episode(row, 1, 1, "pending")
    grabbed = world.episode(row, 1, 2, "grabbed")
    other = world.episode(row, 2, 1, "pending")

    asked = world.seasons.ask(actor(ALICE), SHOW, 1)

    (season,) = world.store.wanted.list_for_followed(row, kind="season")
    assert (season.season, season.trigger, season.status) == (1, "manual", "pending")
    assert world.store.wanted.get(pending).status == "absorbed"  # type: ignore[union-attr]
    kept = world.store.wanted.get(grabbed)
    assert kept is not None and (kept.status, kept.absorbed_by) == ("grabbed", season.id)
    assert world.store.wanted.get(other).status == "pending"  # type: ignore[union-attr]
    assert world.primes() == [row]
    assert (asked.reused, asked.queued) == (False, True)
    assert asked.run_uid is not None


def test_an_owned_unfollowed_show_gets_a_request_row_never_listed(world: FollowWorld) -> None:
    """The library owns it, nobody follows it: a request row, the caller ``via request``, no follow listed."""
    _hold_owned(world)

    asked = world.seasons.ask(actor(ALICE), OWNED, 1)

    (found,) = world.store.follow.find_all_by_ref(OWNED.ref(), kind="show")
    assert found.id is not None
    row = world.row(found.id)
    assert (row.scope, row.removed_at, row.title, row.year) == ("request", None, "Owned Show", 2020)
    assert row.media_ref == MediaRef(tvdb_id=4242, tmdb_id=99)
    assert world.requesters(row.id) == {ALICE: ("request", None, False)}
    assert world.follows.read_follows(actor(DAVE)) == []
    assert world.primes() == [row.id]
    assert asked.absorbed_count == 2


def test_neither_followed_nor_owned_is_not_found(world: FollowWorld) -> None:
    """No follow, no request, nothing the library owns: ``acquisition.not_found``, nothing written."""
    with pytest.raises(AppNotFound) as refused:
        world.seasons.ask(actor(ALICE), SHOW, 1)

    assert refused.value.code is RefusalCode.ACQUISITION_NOT_FOUND
    assert world.store.follow.list_all() == []


def test_an_open_season_is_reused(world: FollowWorld) -> None:
    """A second ask of a season still open: ``reused``, nothing written, no prime."""
    row = _followed(world)
    world.seasons.ask(actor(ALICE), SHOW, 1)
    world.settle_all()

    again = world.seasons.ask(actor(ALICE), SHOW, 1)

    assert (again.reused, again.queued, again.run_uid) == (True, False, None)
    assert len(world.store.wanted.list_for_followed(row, kind="season")) == 1
    assert world.primes() == []


def test_absorbed_count_counts_aired_episodes_not_owned(world: FollowWorld) -> None:
    """B-380: the season's aired episodes the library lacks — not the rows absorbed, not the announced."""
    row = _followed(world)
    world.aired(row, [(1, 1, "2026-01-01"), (1, 2, "2026-01-08"), (1, 3, "2026-01-15"), (1, 4, "2026-12-31")])
    world.ownership.pairs = {(1, 1)}

    asked = world.seasons.ask(actor(ALICE), SHOW, 1)

    assert asked.absorbed_count == 2


def test_a_follow_not_the_actors_is_refused(world: FollowWorld) -> None:
    """A season of someone else's follow, without ``pilot.any``: ``acquisition.not_requester``."""
    _followed(world)

    with pytest.raises(AppForbidden) as refused:
        world.seasons.ask(actor(BOB), SHOW, 1)

    assert refused.value.code is RefusalCode.ACQUISITION_NOT_REQUESTER


def test_a_season_below_one_is_refused(world: FollowWorld) -> None:
    """Season 0: ``request.invalid`` naming ``season``."""
    with pytest.raises(AppBadRequest) as refused:
        world.seasons.ask(actor(ALICE), SHOW, 0)

    assert refused.value.params == {"fields": ["season"]}


def _hold_show(world: FollowWorld) -> None:
    """The library holds :data:`SHOW` too, so a removed follow of it may be asked as a request.

    Args:
        world: The world.
    """
    world.shows.shows["tvdb:81189"] = HeldShow(
        title="Breaking Bad", year=2008, ref=MediaRef(tvdb_id=81189), aired=None, owned=frozenset()
    )


def test_a_legacy_follows_owner_gets_its_season_primed(world: FollowWorld) -> None:
    """A follow with no requester row is the owner's: its season ask writes the owner's row, and is primed.

    The owner here pilots its own acquisitions only (no ``pilot.any``): the supervisor authorises
    the prime against the follow's requester rows, so the owner's ask must be one of them.
    """
    row = world.legacy_follow(SHOW.ref(), title="Breaking Bad")
    owner = actor(OWNER, role=MEMBER)

    asked = world.seasons.ask(owner, SHOW, 1)

    assert (asked.reused, asked.queued) == (False, True)
    assert world.primes() == [row]
    assert set(world.requesters(row)) == {OWNER}


def test_a_request_whose_season_write_fails_leaves_nothing(world: FollowWorld) -> None:
    """The request row, its requester and the season commit together: the season failing undoes the request."""
    _hold_owned(world)

    with (
        patch.object(_WantedSubStore, "add", side_effect=RuntimeError("disk full")),
        pytest.raises(RuntimeError),
    ):
        world.seasons.ask(actor(ALICE), OWNED, 1)

    assert world.store.follow.list_all() == []
    assert world.primes() == []


def test_a_followed_season_whose_absorb_fails_leaves_no_season_row(world: FollowWorld) -> None:
    """The season row and its absorptions commit together: never a pending season its episodes ignore."""
    row = _followed(world)
    pending = world.episode(row, 1, 1, "pending")

    with (
        patch.object(_WantedSubStore, "absorb_episodes", side_effect=RuntimeError("disk full")),
        pytest.raises(RuntimeError),
    ):
        world.seasons.ask(actor(ALICE), SHOW, 1)

    assert world.store.wanted.list_for_followed(row, kind="season") == []
    assert world.status(pending) == "pending"


def test_a_removed_follow_asked_one_season_gives_up_its_other_seasons(world: FollowWorld) -> None:
    """Revived as a request of season 2: season 1's open rows are abandoned, its grabbed one left to run."""
    _hold_show(world)
    row = _followed(world)
    first_season = world.season_row(row, 1)
    first_episode = world.episode(row, 1, 5, "available")
    first_grabbed = world.episode(row, 1, 6, "grabbed")
    second_episode = world.episode(row, 2, 1, "pending")
    world.follows.remove(actor(ALICE), SHOW)

    asked = world.seasons.ask(actor(BOB), SHOW, 2)

    assert world.row(row).scope == "request"
    assert world.row(row).active is True
    assert world.requesters(row) == {BOB: ("request", None, False)}
    assert (world.status(first_season), world.status(first_episode)) == ("abandoned", "abandoned")
    assert world.status(first_grabbed) == "grabbed"
    assert world.status(second_episode) == "absorbed"
    assert (asked.reused, asked.queued) == (False, True)


def test_a_removed_follow_whose_season_is_still_open_is_reused_and_primed(world: FollowWorld) -> None:
    """The kept season row answers ``reused``; the ask turned the row back on, so it is primed all the same."""
    _hold_show(world)
    row = _followed(world)
    world.season_row(row, 2)
    world.follows.remove(actor(ALICE), SHOW)
    world.settle_all()

    asked = world.seasons.ask(actor(BOB), SHOW, 2)

    assert (asked.reused, asked.queued) == (True, True)
    assert asked.run_uid is not None
    assert world.primes() == [row]
    assert len(world.store.wanted.list_for_followed(row, kind="season")) == 1


def test_the_library_index_answers_a_held_show(tmp_path: Path) -> None:
    """``IndexedShows`` over a real ``library.db`` and catalogue: the show, its ids, aired and owned pairs."""
    index = FixtureIndex(tmp_path / "library.db")
    item = index.item("Owned Show", kind="show", year=2020, tvdb="4242")
    index.episodes(item, 1, [1])
    index.conn.close()
    catalogue = CatalogueStore(tmp_path / "acquire.db")
    catalogued(catalogue, "tvdb", "4242", {1: [date(2026, 1, 1), date(2026, 1, 8), date(2027, 1, 1)]})
    shows = IndexedShows(
        index=LibraryIndex(index.path),
        view=CatalogueView(catalogue=catalogue, ownership=IndexerOwnershipChecker(index.path)),
        today=lambda: date(2026, 11, 23),
    )

    held = shows.held_show(MediaRef(tvdb_id=4242))

    assert held is not None
    assert (held.title, held.year, held.ref.tvdb_id) == ("Owned Show", 2020, 4242)
    assert held.aired == frozenset({(1, 1), (1, 2)})
    assert held.owned == frozenset({(1, 1)})
    assert shows.held_show(MediaRef(tvdb_id=9999)) is None
