"""``FollowRepository``: a follow and its requesters read and written on a real acquire store (K3 P3).

The repository loads the aggregate by its acquisition key (P1's lookup, a duplicate raising) and
saves its requesters with the projection of DESIGN § 2.4 — ``min_resolution`` and ``active`` on the
``followed_series`` row — in one transaction, answering whether ``active`` went from false to true.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import FollowedSeries
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.acquisition.follow_repository import FollowAmbiguous, FollowRepository
from personalscraper.app.acquisition.model import (
    AcquisitionKey,
    Follow,
    InForce,
    QualityFloor,
    Scope,
    Via,
)
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

ALICE = AccountId("account-alice")
BOB = AccountId("account-bob")
SHOW = AcquisitionKey.parse("tvdb:81189")
NOTHING = InForce(floor=None, paused=False)


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


def _add_show(store: ConcreteAcquireStore, *, profile: str | None = None, active: bool = True) -> int:
    """Follow the show of :data:`SHOW` and return its rowid.

    Args:
        store: The store.
        profile: The row's ``quality_profile_json``.
        active: The row's ``active`` flag.

    Returns:
        The rowid.
    """
    return store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=81189), title="Show", added_at=100, quality_profile_json=profile, active=active
        )
    )


def _loaded(repository: FollowRepository, key: AcquisitionKey = SHOW) -> Follow:
    """Load a follow that must exist.

    Args:
        repository: The repository.
        key: The follow's key.

    Returns:
        The follow.
    """
    follow = repository.get(key)
    assert follow is not None
    return follow


def test_get_an_unknown_key_is_none(store: ConcreteAcquireStore) -> None:
    """No row holds the key: no follow."""
    assert FollowRepository(store).get(SHOW) is None


def test_get_a_follow_with_no_requester(store: ConcreteAcquireStore) -> None:
    """A follow written before the model has its row's id, its key, its scope and no requester."""
    rowid = _add_show(store)
    follow = _loaded(FollowRepository(store))
    assert (follow.id, follow.key, follow.scope, follow.requesters, follow.removed_at) == (
        rowid,
        SHOW,
        Scope.FOLLOW,
        (),
        None,
    )


def test_get_names_the_medium_by_its_own_rule(store: ConcreteAcquireStore) -> None:
    """A film found by its IMDb id is named TMDB first, from the row's ids."""
    store.follow.add(
        FollowedSeries(media_ref=MediaRef(tmdb_id=603, imdb_id="tt0133093"), title="Film", added_at=100, kind="movie")
    )
    assert _loaded(FollowRepository(store), AcquisitionKey.parse("imdb:tt0133093")).key.wire == "tmdb:603"


def test_save_then_get(store: ConcreteAcquireStore) -> None:
    """Requesters saved are read back, in the order they asked."""
    _add_show(store)
    repository = FollowRepository(store)
    follow = _loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200).with_requester(BOB, Via.REQUEST, now=300)
    follow = follow.with_setting(BOB, floor=QualityFloor.P1080, paused=True)
    repository.save(follow, NOTHING)
    assert _loaded(repository).requesters == follow.requesters


def test_a_second_ask_keeps_since_through_save_and_get(store: ConcreteAcquireStore) -> None:
    """An account asking again keeps its first ask's ``since`` once saved and read back."""
    _add_show(store)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200), NOTHING)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=900), NOTHING)
    (alice,) = _loaded(repository).requesters
    assert alice.since == 200


def test_a_requester_who_left_is_deleted(store: ConcreteAcquireStore) -> None:
    """Saving a follow one requester left removes its row."""
    _add_show(store)
    repository = FollowRepository(store)
    both = _loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200).with_requester(BOB, Via.FOLLOW, now=300)
    repository.save(both, NOTHING)
    repository.save(_loaded(repository).without_requester(ALICE, now=400), NOTHING)
    assert [one.account_id for one in _loaded(repository).requesters] == [BOB]


def test_the_projection_writes_the_floor_keeping_the_other_profile_keys(store: ConcreteAcquireStore) -> None:
    """``min_resolution`` takes the floor in force; the profile's other keys stay."""
    profile = json.dumps({"min_resolution": None, "required_audio": ["VF"], "exclude_3d": False})
    rowid = _add_show(store, profile=profile)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200), InForce(QualityFloor.P2160, False))
    row = store.follow.get(rowid)
    assert row is not None
    assert json.loads(row.quality_profile_json or "") == {
        "min_resolution": 2160,
        "required_audio": ["VF"],
        "exclude_3d": False,
    }


def test_the_projection_clears_the_floor(store: ConcreteAcquireStore) -> None:
    """No floor in force writes ``min_resolution`` null."""
    rowid = _add_show(store, profile=json.dumps({"min_resolution": 1080}))
    repository = FollowRepository(store)
    repository.save(_loaded(repository), NOTHING)
    row = store.follow.get(rowid)
    assert row is not None
    assert json.loads(row.quality_profile_json or "") == {"min_resolution": None}


def test_the_projection_leaves_a_null_profile_null_with_no_floor(store: ConcreteAcquireStore) -> None:
    """A row with no profile and no floor in force keeps its NULL profile (the permissive default)."""
    rowid = _add_show(store)
    repository = FollowRepository(store)
    repository.save(_loaded(repository), NOTHING)
    row = store.follow.get(rowid)
    assert row is not None
    assert row.quality_profile_json is None


def test_the_projection_writes_active_from_the_pause(store: ConcreteAcquireStore) -> None:
    """A follow paused in force is written inactive, then active once the pause is lifted."""
    rowid = _add_show(store)
    repository = FollowRepository(store)
    follow = _loaded(repository)
    repository.save(follow, InForce(None, paused=True))
    assert store.follow.get(rowid).active is False  # type: ignore[union-attr]
    repository.save(follow, NOTHING)
    assert store.follow.get(rowid).active is True  # type: ignore[union-attr]


def test_a_removed_follow_is_written_removed_and_inactive(store: ConcreteAcquireStore) -> None:
    """The last requester leaving writes ``removed_at`` and ``active = 0``, its rows gone."""
    rowid = _add_show(store)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200), NOTHING)
    repository.save(_loaded(repository).without_requester(ALICE, now=500), NOTHING)
    row = store.follow.get(rowid)
    assert row is not None
    assert (row.removed_at, row.active) == (500, False)
    assert store.requesters.list_for(rowid) == []


def test_save_answers_true_only_when_active_goes_from_false_to_true(store: ConcreteAcquireStore) -> None:
    """The prime rule: only a follow starting to take work answers true."""
    _add_show(store)
    repository = FollowRepository(store)
    follow = _loaded(repository)
    assert repository.save(follow, NOTHING) is False  # true → true
    assert repository.save(follow, InForce(None, paused=True)) is False  # true → false
    assert repository.save(follow, InForce(None, paused=True)) is False  # false → false
    assert repository.save(follow, NOTHING) is True  # false → true


def test_a_revived_follow_answers_true(store: ConcreteAcquireStore) -> None:
    """A removed follow asked for again starts taking work: the save answers true."""
    _add_show(store)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200), NOTHING)
    repository.save(_loaded(repository).without_requester(ALICE, now=300), NOTHING)
    revived = _loaded(repository).with_requester(BOB, Via.FOLLOW, now=400)
    assert repository.save(revived, NOTHING) is True
    assert _loaded(repository).removed_at is None


def test_saving_a_follow_whose_row_is_gone_raises(store: ConcreteAcquireStore) -> None:
    """A follow deleted under the aggregate cannot be saved."""
    _add_show(store)
    repository = FollowRepository(store)
    follow = _loaded(repository)
    store.follow.delete(follow.id)
    with pytest.raises(LookupError):
        repository.save(follow, NOTHING)


def test_an_ambiguous_key_raises(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """Two rows holding the key's id are a duplicate: the lookup refuses to choose."""
    _add_show(store)
    conn = sqlite3.connect(tmp_path / "acquire.db")
    try:
        with conn:
            conn.execute(
                "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) VALUES (?, ?, 1, 1, ?)",
                (json.dumps({"tvdb_id": 81189, "tmdb_id": 1396, "imdb_id": None}), "Show again", "show"),
            )
    finally:
        conn.close()
    with pytest.raises(FollowAmbiguous):
        FollowRepository(store).get(SHOW)
