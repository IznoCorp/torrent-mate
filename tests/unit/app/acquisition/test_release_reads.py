"""``ReleaseReads``: the release candidates of one wanted item, own-scoped (K3 P9a, DESIGN § 2.9).

Candidates are seeded through ``store.candidates.replace`` on a real acquire store. The read finds the
follow by its key, the wanted row at the asked season / episode, and answers that row's ranked set.
A follow the actor may not read answers an empty set on a 200 (a filter, never a refusal): the rule
is :meth:`Follow.readable_by` — ``acquisition.see.others``, else membership (§ 2.4).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import (
    FollowedSeries,
    FollowRequester,
    WantedCandidate,
    WantedItem,
    WantedKind,
    WantedStatus,
)
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition.model import AcquisitionKey
from personalscraper.app.acquisition.releases import ReleaseReads
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

ALICE = AccountId("account-alice")
BOB = AccountId("account-bob")
OWNER = AccountId("account-owner")
SHOW = AcquisitionKey.parse("tvdb:81189")
OTHER_SHOW = AcquisitionKey.parse("tvdb:70000")
FILM = AcquisitionKey.parse("tmdb:603")


def _actor(account: AccountId, *rights: Right) -> Actor:
    """Build an ordinary actor holding the given rights.

    Args:
        account: The actor's account.
        *rights: The rights its role carries.

    Returns:
        The actor.
    """
    return Actor(
        account_id=account,
        name="Someone",
        role_id=RoleId("role-member"),
        role_kind=RoleKind.ORDINARY,
        role_rights=frozenset(rights),
        ceiling=InstanceCeiling(forbidden=frozenset(), read_only=False),
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a migrated store on a temp acquire.db and close it afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A :class:`ConcreteAcquireStore` whose schema is applied.
    """
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _follow(store: ConcreteAcquireStore, ref: MediaRef, *, asked_by: AccountId | None = ALICE) -> int:
    """Store a follow of *ref*, asked for by one account.

    Args:
        store: The store.
        ref: The followed medium.
        asked_by: The requester stored, ``None`` for a follow with no requester row.

    Returns:
        The follow's rowid.
    """
    rowid = store.follow.add(FollowedSeries(media_ref=ref, title="Title", added_at=100))
    if asked_by is not None:
        store.requesters.upsert(
            FollowRequester(followed_id=rowid, account_id=asked_by, via="follow", floor=None, paused=False, since=200)
        )
    return rowid


def _wanted(
    store: ConcreteAcquireStore,
    followed_id: int,
    *,
    kind: WantedKind = "episode",
    season: int | None = None,
    episode: int | None = None,
    status: WantedStatus = "pending",
) -> int:
    """Store one wanted row of a follow.

    Args:
        store: The store.
        followed_id: The follow's rowid.
        kind: The row's kind.
        season: The row's season.
        episode: The row's episode.
        status: The row's status.

    Returns:
        The wanted row's id.
    """
    return store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=81189),
            kind=kind,
            status=status,
            enqueued_at=300,
            followed_id=followed_id,
            season=season,
            episode=episode,
        )
    )


def _candidate(rank: int, title: str, *, season: int | None = None, episode: int | None = None) -> WantedCandidate:
    """Build one ranked candidate.

    Args:
        rank: Its rank, 1 the best.
        title: Its release title.
        season: The season it numbers.
        episode: The episode it numbers.

    Returns:
        The candidate.
    """
    return WantedCandidate(
        rank=rank,
        provider="c411",
        title=title,
        info_hash=f"hash{rank}",
        size_bytes=1_000 * rank,
        seeders=50 - rank,
        resolution="1080p",
        source="WEB",
        language="MULTI",
        score=100 - rank,
        season=season,
        episode=episode,
        searched_at=400,
    )


def _titles(
    store: ConcreteAcquireStore, actor: Actor, key: AcquisitionKey, season: int | None, episode: int | None
) -> list[str]:
    """Read the releases and keep their titles, in the order answered.

    Args:
        store: The store.
        actor: The reader.
        key: The follow's key.
        season: The asked season.
        episode: The asked episode.

    Returns:
        The titles of the answered candidates.
    """
    return [c.title for c in ReleaseReads(store, owner=OWNER).read(actor, key, season, episode)]


def test_the_candidates_of_the_episode_asked_are_answered_best_rank_first(store: ConcreteAcquireStore) -> None:
    """The follow's key, its season and its episode name one wanted row: its ranked set comes back."""
    follow = _follow(store, MediaRef(tvdb_id=81189))
    wanted = _wanted(store, follow, season=2, episode=5)
    store.candidates.replace(
        wanted,
        [
            _candidate(2, "Show.S02E05.720p", season=2, episode=5),
            _candidate(1, "Show.S02E05.1080p", season=2, episode=5),
        ],
    )
    assert _titles(store, _actor(ALICE), SHOW, 2, 5) == ["Show.S02E05.1080p", "Show.S02E05.720p"]


def test_the_candidates_keep_their_numbering(store: ConcreteAcquireStore) -> None:
    """Each answered candidate carries the season and episode it was stored with (the picker never parses)."""
    follow = _follow(store, MediaRef(tvdb_id=81189))
    wanted = _wanted(store, follow, season=2, episode=5)
    store.candidates.replace(wanted, [_candidate(1, "Show.S02E05E06.1080p", season=2, episode=5)])
    (found,) = ReleaseReads(store, owner=OWNER).read(_actor(ALICE), SHOW, 2, 5)
    assert (found.season, found.episode, found.info_hash) == (2, 5, "hash1")


def test_another_episode_of_the_follow_is_not_answered(store: ConcreteAcquireStore) -> None:
    """The read is of ONE item: the candidates of S02E06 never answer S02E05."""
    follow = _follow(store, MediaRef(tvdb_id=81189))
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    store.candidates.replace(_wanted(store, follow, season=2, episode=6), [_candidate(1, "Show.S02E06")])
    assert _titles(store, _actor(ALICE), SHOW, 2, 6) == ["Show.S02E06"]


def test_a_season_is_asked_with_no_episode(store: ConcreteAcquireStore) -> None:
    """A season and no episode reads the season wanted row, its packs; the episode rows do not answer it."""
    follow = _follow(store, MediaRef(tvdb_id=81189))
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    store.candidates.replace(
        _wanted(store, follow, kind="season", season=2), [_candidate(1, "Show.S02.COMPLETE", season=2)]
    )
    assert _titles(store, _actor(ALICE), SHOW, 2, None) == ["Show.S02.COMPLETE"]


def test_a_film_is_asked_with_neither(store: ConcreteAcquireStore) -> None:
    """No season and no episode reads the film's wanted row."""
    follow = _follow(store, MediaRef(tmdb_id=603))
    store.candidates.replace(_wanted(store, follow, kind="movie"), [_candidate(1, "The.Matrix.1999.1080p")])
    assert _titles(store, _actor(ALICE), FILM, None, None) == ["The.Matrix.1999.1080p"]


def test_the_candidates_of_another_follow_are_not_answered(store: ConcreteAcquireStore) -> None:
    """The key names the row: a second follow's S02E05 never answers the first's."""
    first = _follow(store, MediaRef(tvdb_id=81189))
    second = _follow(store, MediaRef(tvdb_id=70000))
    store.candidates.replace(_wanted(store, first, season=2, episode=5), [_candidate(1, "First.S02E05")])
    store.candidates.replace(_wanted(store, second, season=2, episode=5), [_candidate(1, "Second.S02E05")])
    assert _titles(store, _actor(ALICE), SHOW, 2, 5) == ["First.S02E05"]
    assert _titles(store, _actor(OWNER, Right.ACQUISITION_SEE_OTHERS), OTHER_SHOW, 2, 5) == ["Second.S02E05"]


def test_the_row_that_governs_is_the_latest_open_one(store: ConcreteAcquireStore) -> None:
    """A closed row is history and speaks for nothing; of two open rows the latest id is the current intent."""
    follow = _follow(store, MediaRef(tvdb_id=81189))
    closed = _wanted(store, follow, season=2, episode=5, status="abandoned")
    older = _wanted(store, follow, season=2, episode=5, status="searching")
    newer = _wanted(store, follow, season=2, episode=5, status="available")
    store.candidates.replace(closed, [_candidate(1, "Closed")])
    store.candidates.replace(older, [_candidate(1, "Older")])
    store.candidates.replace(newer, [_candidate(1, "Newer")])
    assert _titles(store, _actor(ALICE), SHOW, 2, 5) == ["Newer"]


def test_a_row_only_closed_answers_nothing(store: ConcreteAcquireStore) -> None:
    """With no open row at the coordinates the acquisition ended: its stale set is not offered."""
    follow = _follow(store, MediaRef(tvdb_id=81189))
    store.candidates.replace(_wanted(store, follow, season=2, episode=5, status="done"), [_candidate(1, "Done")])
    assert _titles(store, _actor(ALICE), SHOW, 2, 5) == []


def test_no_search_concluded_answers_nothing(store: ConcreteAcquireStore) -> None:
    """A wanted row with no stored set answers an empty list."""
    follow = _follow(store, MediaRef(tvdb_id=81189))
    _wanted(store, follow, season=2, episode=5)
    assert _titles(store, _actor(ALICE), SHOW, 2, 5) == []


def test_an_unknown_key_answers_nothing(store: ConcreteAcquireStore) -> None:
    """No follow holds the key: an empty list, on a 200."""
    assert _titles(store, _actor(ALICE), SHOW, 2, 5) == []


def test_a_requester_reads_its_own_follow(store: ConcreteAcquireStore) -> None:
    """Membership is enough, with no right beyond the door's."""
    follow = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    assert _titles(store, _actor(ALICE, Right.ACQUISITION_PILOT_OWN), SHOW, 2, 5) == ["Show.S02E05"]


def test_a_member_who_did_not_ask_reads_nothing(store: ConcreteAcquireStore) -> None:
    """Someone else's follow is filtered out: an empty list, never a refusal."""
    follow = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    assert _titles(store, _actor(BOB, Right.ACQUISITION_PILOT_OWN), SHOW, 2, 5) == []


def test_see_others_reads_a_follow_it_did_not_ask_for(store: ConcreteAcquireStore) -> None:
    """``acquisition.see.others`` lifts the membership filter."""
    follow = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    assert _titles(store, _actor(BOB, Right.ACQUISITION_SEE_OTHERS), SHOW, 2, 5) == ["Show.S02E05"]


def test_pilot_any_without_see_others_reads_its_own_only(store: ConcreteAcquireStore) -> None:
    """``pilot.any`` is the acts' scope, not the reads' (DESIGN § 2.4): it does not lift the filter."""
    follow = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    assert _titles(store, _actor(BOB, Right.ACQUISITION_PILOT_ANY), SHOW, 2, 5) == []


def test_a_follow_with_no_requester_is_the_owners(store: ConcreteAcquireStore) -> None:
    """A follow written before the model is the owner's ask (ruling 9): the owner reads it, another member does not."""
    follow = _follow(store, MediaRef(tvdb_id=81189), asked_by=None)
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    assert _titles(store, _actor(OWNER), SHOW, 2, 5) == ["Show.S02E05"]
    assert _titles(store, _actor(BOB), SHOW, 2, 5) == []


def test_a_removed_follow_answers_nothing_even_to_see_others(store: ConcreteAcquireStore) -> None:
    """The last requester left: the follow no longer stands, so its set is not offered to anyone."""
    follow = _follow(store, MediaRef(tvdb_id=81189), asked_by=ALICE)
    store.candidates.replace(_wanted(store, follow, season=2, episode=5), [_candidate(1, "Show.S02E05")])
    store.requesters.save_follow(follow, [], removed_at=500, min_resolution=None, active=False)
    assert _titles(store, _actor(BOB, Right.ACQUISITION_SEE_OTHERS), SHOW, 2, 5) == []


def test_an_episode_with_no_season_is_refused(store: ConcreteAcquireStore) -> None:
    """An episode number means nothing without its season: ``request.invalid`` naming ``episode``."""
    with pytest.raises(AppBadRequest) as refused:
        ReleaseReads(store, owner=OWNER).read(_actor(ALICE), SHOW, None, 5)
    assert refused.value.code is RefusalCode.REQUEST_INVALID
    assert refused.value.params == {"fields": ["episode"]}
