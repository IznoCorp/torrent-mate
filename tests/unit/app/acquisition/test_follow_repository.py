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

from personalscraper.acquire.domain import FollowedSeries, FollowKind, FollowRequester
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.accounts.rights import Right
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
OWNER = AccountId("account-owner")
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


def _asked(store: ConcreteAcquireStore, rowid: int, account: AccountId, since: int = 200) -> None:
    """Store one requester row, so the follow is no longer the owner's implied ask.

    Args:
        store: The store.
        rowid: The follow's row.
        account: The asking account.
        since: When it asked.
    """
    store.requesters.upsert(
        FollowRequester(followed_id=rowid, account_id=account, via="follow", floor=None, paused=False, since=since)
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
    follow = (
        _loaded(repository)
        .with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER)
        .with_requester(BOB, Via.REQUEST, now=300, owner=OWNER)
    )
    follow = follow.with_setting(BOB, floor=QualityFloor.P1080, paused=True, owner=OWNER)
    repository.save(follow, NOTHING)
    assert _loaded(repository).requesters == follow.requesters


def test_a_second_ask_keeps_since_through_save_and_get(store: ConcreteAcquireStore) -> None:
    """An account asking again keeps its first ask's ``since`` once saved and read back."""
    _asked(store, _add_show(store), ALICE)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER), NOTHING)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=900, owner=OWNER), NOTHING)
    (alice,) = _loaded(repository).requesters
    assert alice.since == 200


def test_a_requester_who_left_is_deleted(store: ConcreteAcquireStore) -> None:
    """Saving a follow one requester left removes its row."""
    _asked(store, _add_show(store), ALICE)
    repository = FollowRepository(store)
    both = (
        _loaded(repository)
        .with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER)
        .with_requester(BOB, Via.FOLLOW, now=300, owner=OWNER)
    )
    repository.save(both, NOTHING)
    repository.save(_loaded(repository).without_requester(ALICE, now=400, owner=OWNER), NOTHING)
    assert [one.account_id for one in _loaded(repository).requesters] == [BOB]


def test_the_projection_writes_the_floor_keeping_the_other_profile_keys(store: ConcreteAcquireStore) -> None:
    """``min_resolution`` takes the floor in force; the profile's other keys stay."""
    profile = json.dumps({"min_resolution": None, "required_audio": ["VF"], "exclude_3d": False})
    rowid = _add_show(store, profile=profile)
    repository = FollowRepository(store)
    repository.save(
        _loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER), InForce(QualityFloor.P2160, False)
    )
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
    _asked(store, rowid, ALICE)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER), NOTHING)
    repository.save(_loaded(repository).without_requester(ALICE, now=500, owner=OWNER), NOTHING)
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
    _asked(store, _add_show(store), ALICE)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER), NOTHING)
    repository.save(_loaded(repository).without_requester(ALICE, now=300, owner=OWNER), NOTHING)
    revived = _loaded(repository).with_requester(BOB, Via.FOLLOW, now=400, owner=OWNER)
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


def _row(store: ConcreteAcquireStore, rowid: int) -> FollowedSeries:
    """Read a follow row that must exist.

    Args:
        store: The store.
        rowid: The row's id.

    Returns:
        The row.
    """
    row = store.follow.get(rowid)
    assert row is not None
    return row


def test_a_film_named_tvdb_comes_back_through_get(store: ConcreteAcquireStore) -> None:
    """A film holding only a TVDB id is named ``tvdb:`` and found by that key and its kind."""
    rowid = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=111), title="Film", added_at=100, kind="movie"))
    key = AcquisitionKey.of(MediaRef(tvdb_id=111), "movie")
    assert _loaded_kind(FollowRepository(store), key, "movie").id == rowid


def test_a_bare_tvdb_key_finds_the_film_that_holds_it(store: ConcreteAcquireStore) -> None:
    """A wire key carries no kind: no show answers to ``tvdb:111``, so the film holding that id does."""
    rowid = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=111), title="Film", added_at=100, kind="movie"))

    found = FollowRepository(store).get(AcquisitionKey.parse("tvdb:111"))

    assert found is not None and found.id == rowid


def test_a_bare_tvdb_key_names_the_show_before_a_film(store: ConcreteAcquireStore) -> None:
    """A show and a film both hold ``tvdb:111``: TVDB is the shows' provider, so the show answers."""
    show = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=111), title="Show", added_at=100))
    store.follow.add(
        FollowedSeries(media_ref=MediaRef(tvdb_id=111, tmdb_id=5), title="Film", added_at=100, kind="movie")
    )

    found = FollowRepository(store).get(AcquisitionKey.parse("tvdb:111"))

    assert found is not None and found.id == show


def test_a_bare_tvdb_key_held_by_two_films_is_ambiguous(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """The fallback refuses as a lookup does when two films answer (a duplicate): it never picks one."""
    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=111), title="Film", added_at=100, kind="movie"))
    conn = sqlite3.connect(tmp_path / "acquire.db")
    try:
        with conn:
            conn.execute(
                "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) VALUES (?, ?, 1, 1, ?)",
                (json.dumps({"tvdb_id": 111, "tmdb_id": 5, "imdb_id": None}), "Film again", "movie"),
            )
    finally:
        conn.close()

    with pytest.raises(FollowAmbiguous):
        FollowRepository(store).get(AcquisitionKey.parse("tvdb:111"))


def test_a_tmdb_key_resolves_each_medium_by_its_kind(store: ConcreteAcquireStore) -> None:
    """TMDB numbers films and shows apart: the same id finds the film or the show by the kind given."""
    film = store.follow.add(FollowedSeries(media_ref=MediaRef(tmdb_id=603), title="Film", added_at=100, kind="movie"))
    show = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=81189, tmdb_id=603), title="Show", added_at=100))
    repository = FollowRepository(store)
    key = AcquisitionKey.parse("tmdb:603")
    assert _loaded_kind(repository, key, "movie").id == film
    assert _loaded_kind(repository, key, "show").id == show


def _loaded_kind(repository: FollowRepository, key: AcquisitionKey, kind: FollowKind) -> Follow:
    """Load a follow of a known kind that must exist.

    Args:
        repository: The repository.
        key: The follow's key.
        kind: The medium's kind.

    Returns:
        The follow.
    """
    follow = repository.get(key, kind)
    assert follow is not None
    return follow


def test_a_v0_follow_keeps_its_floor_pause_and_owner_when_another_joins(store: ConcreteAcquireStore) -> None:
    """A paused v0 follow with a 2160 floor: a second account joins, and nothing the owner set is lost."""
    rowid = _add_show(store, profile=json.dumps({"min_resolution": 2160, "exclude_3d": True}), active=False)
    repository = FollowRepository(store)
    joined = _loaded(repository).with_requester(BOB, Via.FOLLOW, now=500, owner=OWNER)
    holds = {OWNER: set(Right), BOB: {Right.ACQUISITION_QUALITY_OWN}}
    assert repository.save(joined, joined.in_force(lambda account, right: right in holds.get(account, set()))) is False
    row = _row(store, rowid)
    assert json.loads(row.quality_profile_json or "")["min_resolution"] == 2160
    assert row.active is False
    owner, bob = _loaded(repository).requesters
    assert (owner.account_id, owner.floor, owner.paused) == (OWNER, QualityFloor.P2160, True)
    assert bob.account_id == BOB


def test_a_v0_follow_saved_untouched_keeps_its_settings(store: ConcreteAcquireStore) -> None:
    """Loading and saving a requester-less follow writes back its own v0 floor and pause."""
    rowid = _add_show(store, profile=json.dumps({"min_resolution": 1080}), active=False)
    repository = FollowRepository(store)
    follow = _loaded(repository)
    assert repository.save(follow, follow.in_force(lambda account, right: False)) is False
    row = _row(store, rowid)
    assert (json.loads(row.quality_profile_json or "")["min_resolution"], row.active) == (1080, False)


def test_a_floor_is_written_onto_a_null_profile(store: ConcreteAcquireStore) -> None:
    """A row with no profile takes the floor in force as its only key."""
    rowid = _add_show(store)
    repository = FollowRepository(store)
    repository.save(
        _loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER), InForce(QualityFloor.P1080, False)
    )
    assert json.loads(_row(store, rowid).quality_profile_json or "") == {"min_resolution": 1080}


def test_a_changed_setting_is_written_over_the_stored_requester(store: ConcreteAcquireStore) -> None:
    """A requester already stored takes its new floor and pause on the next save."""
    _asked(store, _add_show(store), ALICE)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER), NOTHING)
    repository.save(
        _loaded(repository).with_setting(ALICE, floor=QualityFloor.P2160, paused=True, owner=OWNER), NOTHING
    )
    (alice,) = _loaded(repository).requesters
    assert (alice.floor, alice.paused, alice.since) == (QualityFloor.P2160, True, 200)


def test_a_failed_save_writes_nothing(store: ConcreteAcquireStore) -> None:
    """A requester the table refuses rolls the whole save back: requesters and projection as they were."""
    rowid = _add_show(store)
    _asked(store, rowid, ALICE)
    repository = FollowRepository(store)
    repository.save(_loaded(repository).with_requester(ALICE, Via.FOLLOW, now=200, owner=OWNER), NOTHING)
    bob = FollowRequester(followed_id=rowid, account_id=BOB, via="follow", floor=None, paused=False, since=300)
    # ``since`` is NOT NULL: the third write fails, after ALICE's delete and BOB's insert ran.
    broken = FollowRequester(
        followed_id=rowid, account_id="account-carol", via="follow", floor=None, paused=False, since=None
    )  # type: ignore[arg-type]
    with pytest.raises(sqlite3.IntegrityError):
        store.requesters.save_follow(rowid, [bob, broken], removed_at=None, min_resolution=2160, active=False)
    assert [one.account_id for one in store.requesters.list_for(rowid)] == [ALICE]
    row = _row(store, rowid)
    assert (row.quality_profile_json, row.active) == (None, True)
