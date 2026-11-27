"""``FollowCompleteness``: a follow's aired catalogue against the library, season by season (K3 P7).

v1's twin of v0's completeness: the detect-written aired cache, the library's ownership and the
follow's ``wanted`` rows, each episode's state from the single derivation. A season's tallies count
the aired episodes held, in motion and in all, the announced ones apart. A film has no seasons; a
follow with no cached catalogue reads ``unknown``; an unreadable source is ignorance, never a 500.
Reads are filtered by membership: a follow the actor may not read is not found.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.acquire._aired_store import _AiredSubStore
from personalscraper.acquire._wanted_store import _WantedSubStore
from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.errors import AppNotFound, RefusalCode
from personalscraper.core.identity import MediaRef
from tests.unit.app.acquisition.follow_world import ALICE, BOB, DAVE, NOW, FollowWorld, actor

SHOW = AcquisitionKey.parse("tvdb:81189")
FILM = AcquisitionKey.parse("tmdb:603")


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
    """Alice follows :data:`SHOW`, its catalogue cached: season 1 aired 1–3, season 2 aired 1, 2 announced.

    Args:
        world: The world.

    Returns:
        The follow's row.
    """
    world.follows.create(actor(ALICE), SHOW, title="Breaking Bad", kind="show", year=2008)
    (row,) = world.store.follow.find_all_by_ref(SHOW.ref(), kind="show")
    assert row.id is not None
    world.aired(
        row.id,
        [(1, 1, "2026-01-01"), (1, 2, "2026-01-08"), (1, 3, "2026-01-15"), (2, 1, "2026-11-01"), (2, 2, "2026-12-24")],
    )
    return row.id


def test_each_season_tallies_aired_owned_in_motion_and_announced(world: FollowWorld) -> None:
    """S1: e1 held, e2 grabbed, e3 never searched; S2: e1 available, e2 announced — newest season first."""
    row = _followed(world)
    world.ownership.pairs = {(1, 1)}
    world.episode(row, 1, 2, "grabbed")
    world.episode(row, 2, 1, "available")

    read = world.completeness.read(actor(ALICE), SHOW)

    assert (read.key, read.title, read.kind, read.source) == (SHOW.wire, "Breaking Bad", "show", "cache")
    assert read.catalog_refreshed_at == float(NOW - 100)
    second, first = read.seasons
    assert (first.season, first.owned, first.queued, first.total, first.announced) == (1, 1, 1, 3, 0)
    assert [one.state for one in first.episodes] == ["in_library", "acquiring", "unverified"]
    assert (second.season, second.owned, second.queued, second.total, second.announced) == (2, 0, 1, 1, 1)
    assert [one.state for one in second.episodes] == ["to_grab", "announced"]
    assert second.episodes[1].air_date == "2026-12-24"


def test_the_completeness_names_the_follows_row(world: FollowWorld) -> None:
    """The contract's ``followedId`` is an integer: the follow's row, whatever key it is asked by."""
    row = _followed(world)

    assert world.completeness.read(actor(ALICE), SHOW).follow_id == row


def test_episodes_a_season_row_absorbed_read_its_season(world: FollowWorld) -> None:
    """A season asked absorbs its pending episode, which reads its season's facts: found, so ``to_grab``.

    The episodes with no row of their own are not the season's to speak for: never searched.
    """
    row = _followed(world)
    world.episode(row, 1, 1, "pending")
    world.seasons.ask(actor(ALICE), SHOW, 1)
    (season,) = world.store.wanted.list_for_followed(row, kind="season")
    assert season.id is not None
    world.store.wanted.set_status(season.id, "available")

    read = world.completeness.read(actor(ALICE), SHOW)

    first = read.seasons[-1]
    assert [one.state for one in first.episodes] == ["to_grab", "unverified", "unverified"]
    assert first.queued == 1


def test_a_film_has_no_seasons(world: FollowWorld) -> None:
    """A film reads its facts and no season; with no catalogue its source is ``unknown``."""
    world.follows.create(actor(ALICE), FILM, title="The Matrix", kind="movie", year=1999)

    read = world.completeness.read(actor(ALICE), FILM)

    assert (read.kind, read.seasons, read.source, read.catalog_refreshed_at) == ("movie", (), "unknown", None)


def test_a_show_with_no_cached_catalogue_reads_unknown(world: FollowWorld) -> None:
    """Never detected: no season, source ``unknown`` — never « up to date » on zero knowledge."""
    world.follows.create(actor(ALICE), SHOW, title="Breaking Bad", kind="show", year=2008)

    read = world.completeness.read(actor(ALICE), SHOW)

    assert (read.seasons, read.source) == ((), "unknown")


def test_an_unreadable_cache_is_ignorance(world: FollowWorld) -> None:
    """The aired cache failing reads as no catalogue, never an error."""
    _followed(world)

    with patch.object(_AiredSubStore, "list_for_followed", side_effect=RuntimeError("corrupt")):
        read = world.completeness.read(actor(ALICE), SHOW)

    assert (read.seasons, read.source) == ((), "unknown")


def test_an_unreadable_queue_reads_never_searched(world: FollowWorld) -> None:
    """The wanted rows failing: every aired episode not held reads ``unverified``, the catalogue still shown."""
    row = _followed(world)
    world.episode(row, 1, 2, "grabbed")

    with patch.object(_WantedSubStore, "list_for_followed", side_effect=RuntimeError("corrupt")):
        read = world.completeness.read(actor(ALICE), SHOW)

    assert [one.state for one in read.seasons[-1].episodes] == ["unverified"] * 3


def test_a_follow_the_actor_may_not_read_is_not_found(world: FollowWorld) -> None:
    """Bob asked nothing and does not see the others': ``acquisition.not_found``; Dave sees every follow."""
    _followed(world)

    with pytest.raises(AppNotFound) as refused:
        world.completeness.read(actor(BOB), SHOW)

    assert refused.value.code is RefusalCode.ACQUISITION_NOT_FOUND
    assert world.completeness.read(actor(DAVE), SHOW).key == SHOW.wire


def test_a_removed_follow_is_not_found(world: FollowWorld) -> None:
    """A follow its last requester left has no completeness to read, even for who sees every follow."""
    _followed(world)
    world.follows.remove(actor(ALICE), SHOW)

    with pytest.raises(AppNotFound):
        world.completeness.read(actor(DAVE), SHOW)


def test_a_legacy_follow_reads_as_the_owners(world: FollowWorld) -> None:
    """A follow with no requester row is the owner's: only ``see.others`` reads it."""
    world.legacy_follow(MediaRef(tvdb_id=2), title="Legacy")
    key = AcquisitionKey.parse("tvdb:2")

    with pytest.raises(AppNotFound):
        world.completeness.read(actor(ALICE), key)
    assert world.completeness.read(actor(DAVE), key).title == "Legacy"
