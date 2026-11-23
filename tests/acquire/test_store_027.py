"""The sub-stores of migration 027: requesters, candidates, scope/removal readers, trigger.

K3 P2 is inert: only the store reads or writes the new columns. These tests cover the
two new sub-stores (``store.requesters``, ``store.candidates``), the ``followed_series``
readers returning ``scope`` and ``removed_at``, and ``WantedItem.trigger`` written by
``store.wanted.add`` and read back.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import (
    FollowedSeries,
    FollowRequester,
    WantedCandidate,
    WantedItem,
)
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


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


def _follow(store: ConcreteAcquireStore, tvdb_id: int = 81189, title: str = "Show") -> int:
    """Add a follow and return its rowid.

    Args:
        store: The store.
        tvdb_id: The show's TVDB id.
        title: The show's title.

    Returns:
        The rowid of the follow.
    """
    return store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=tvdb_id), title=title, added_at=100))


def _requester(followed_id: int, account_id: str = "acc-1", **overrides: object) -> FollowRequester:
    """Build a requester row, ``via='follow'``, no floor, not paused, unless overridden.

    Args:
        followed_id: The follow asked for.
        account_id: The asking account.
        **overrides: Fields replaced on the default row.

    Returns:
        The :class:`FollowRequester`.
    """
    fields: dict[str, object] = {
        "followed_id": followed_id,
        "account_id": account_id,
        "via": "follow",
        "floor": None,
        "paused": False,
        "since": 300,
    }
    fields.update(overrides)
    return FollowRequester(**fields)  # type: ignore[arg-type]


def _candidate(rank: int, **overrides: object) -> WantedCandidate:
    """Build a candidate row at *rank*.

    Args:
        rank: Its position in the ranked set (1 is the best).
        **overrides: Fields replaced on the default row.

    Returns:
        The :class:`WantedCandidate`.
    """
    fields: dict[str, object] = {
        "rank": rank,
        "provider": "c411",
        "title": f"Show.S01E01.1080p.{rank}",
        "info_hash": f"{rank:040x}",
        "size_bytes": 1_000 * rank,
        "seeders": 10,
        "resolution": "1080p",
        "source": "WEB",
        "language": "MULTI",
        "score": 100 - rank,
        "season": 1,
        "episode": 1,
        "searched_at": 400,
    }
    fields.update(overrides)
    return WantedCandidate(**fields)  # type: ignore[arg-type]


class TestRequesters:
    """``store.requesters``: list_for, upsert, delete, follows_of."""

    def test_a_follow_with_no_requester_lists_none(self, store: ConcreteAcquireStore) -> None:
        """Existing follows have no requester rows (no backfill)."""
        followed_id = _follow(store)
        assert store.requesters.list_for(followed_id) == []

    def test_upsert_then_list_round_trips_every_field(self, store: ConcreteAcquireStore) -> None:
        """An upserted requester reads back as written."""
        followed_id = _follow(store)
        row = _requester(followed_id, "acc-1", via="request", floor=2160, paused=True, since=321)

        store.requesters.upsert(row)

        assert store.requesters.list_for(followed_id) == [row]

    def test_upsert_replaces_the_row_of_the_same_account(self, store: ConcreteAcquireStore) -> None:
        """A second upsert of (follow, account) updates the row, never adds one."""
        followed_id = _follow(store)
        store.requesters.upsert(_requester(followed_id, "acc-1", floor=720))

        store.requesters.upsert(_requester(followed_id, "acc-1", floor=1080, paused=True))

        assert store.requesters.list_for(followed_id) == [_requester(followed_id, "acc-1", floor=1080, paused=True)]

    def test_list_for_orders_by_since_then_account(self, store: ConcreteAcquireStore) -> None:
        """The requesters read oldest ask first, ties by account id, not in the primary key's order.

        The alphabetically first account asked last: the primary key (follow, account) would
        read it first, so only the ``ORDER BY since`` puts it last.
        """
        followed_id = _follow(store)
        store.requesters.upsert(_requester(followed_id, "acc-a", since=500))
        store.requesters.upsert(_requester(followed_id, "acc-c", since=300))
        store.requesters.upsert(_requester(followed_id, "acc-b", since=300))

        accounts = [r.account_id for r in store.requesters.list_for(followed_id)]

        assert accounts == ["acc-b", "acc-c", "acc-a"]

    def test_list_for_is_scoped_to_its_follow(self, store: ConcreteAcquireStore) -> None:
        """Another follow's requesters are not listed."""
        first = _follow(store, 1, "One")
        second = _follow(store, 2, "Two")
        store.requesters.upsert(_requester(first, "acc-1"))
        store.requesters.upsert(_requester(second, "acc-2"))

        assert [r.account_id for r in store.requesters.list_for(first)] == ["acc-1"]

    def test_delete_removes_one_requester_and_says_so(self, store: ConcreteAcquireStore) -> None:
        """Delete drops the (follow, account) row, keeps the others, and returns whether it existed."""
        followed_id = _follow(store)
        store.requesters.upsert(_requester(followed_id, "acc-1"))
        store.requesters.upsert(_requester(followed_id, "acc-2"))

        assert store.requesters.delete(followed_id, "acc-1") is True
        assert store.requesters.delete(followed_id, "acc-1") is False

        assert [r.account_id for r in store.requesters.list_for(followed_id)] == ["acc-2"]

    def test_follows_of_names_the_follows_of_any_listed_account(self, store: ConcreteAcquireStore) -> None:
        """follows_of returns each follow once when any of the accounts asks for it."""
        first = _follow(store, 1, "One")
        second = _follow(store, 2, "Two")
        third = _follow(store, 3, "Three")
        # Written out of id order, and listed accounts out of order too.
        store.requesters.upsert(_requester(third, "acc-3"))
        store.requesters.upsert(_requester(second, "acc-2"))
        store.requesters.upsert(_requester(first, "acc-2"))
        store.requesters.upsert(_requester(first, "acc-1"))

        assert store.requesters.follows_of(["acc-2", "acc-1"]) == [first, second]

    def test_follows_of_nobody_is_empty(self, store: ConcreteAcquireStore) -> None:
        """No account, no follow — and no query with an empty IN list."""
        assert store.requesters.follows_of([]) == []

    def test_requesters_go_with_their_follow(self, store: ConcreteAcquireStore) -> None:
        """Deleting a follow cascades to its requesters (foreign_keys=ON)."""
        followed_id = _follow(store)
        store.requesters.upsert(_requester(followed_id, "acc-1"))

        store.follow.delete(followed_id)

        assert store.requesters.list_for(followed_id) == []
        assert store.requesters.follows_of(["acc-1"]) == []

    def test_a_requester_of_a_missing_follow_is_refused(self, store: ConcreteAcquireStore) -> None:
        """The foreign key is enforced through the sub-store too, and the write rolls back."""
        with pytest.raises(sqlite3.IntegrityError):
            store.requesters.upsert(_requester(999))

    def test_a_bad_floor_is_refused_at_construction(self) -> None:
        """A floor off the ladder never reaches the CHECK: the row refuses it first."""
        with pytest.raises(ValueError, match="floor"):
            _requester(1, floor=480)

    def test_a_bad_via_is_refused_at_construction(self) -> None:
        """A via off the two values never reaches the CHECK: the row refuses it first."""
        with pytest.raises(ValueError, match="via"):
            _requester(1, via="qbittorrent")


class TestReadsOrderExplicitly:
    """The reads whose order the contract states carry an explicit ORDER BY.

    SQLite serves each of these three from the primary key's index today, so no data can
    tell a missing clause from a present one (a mutation removing it passes every
    behavioural test above): the clause is what keeps the order if the key ever changes,
    and the only observable of it is the statement the store sends.
    """

    @staticmethod
    def _sent(store: ConcreteAcquireStore, read: Callable[[], object]) -> str:
        """Run *read* and return the SQL of its SELECT, whitespace collapsed.

        Args:
            store: The store, opened here.
            read: A call on one of its sub-stores that sends one SELECT.

        Returns:
            The text of the SELECT statement the call sent.
        """
        statements: list[str] = []
        store._ensure_open().set_trace_callback(statements.append)  # noqa: SLF001 — the statement is the observable
        try:
            read()
        finally:
            store._ensure_open().set_trace_callback(None)  # noqa: SLF001
        return " ".join(next(sql for sql in statements if sql.lstrip().upper().startswith("SELECT")).split())

    def test_requesters_are_read_by_since_then_account(self, store: ConcreteAcquireStore) -> None:
        """list_for orders by the ask's date, then the account id."""
        assert "ORDER BY since, account_id" in self._sent(store, lambda: store.requesters.list_for(1))

    def test_candidates_are_read_by_rank(self, store: ConcreteAcquireStore) -> None:
        """list_for orders by rank, the best first."""
        assert self._sent(store, lambda: store.candidates.list_for(1)).endswith("ORDER BY rank")

    def test_follows_of_reads_by_id(self, store: ConcreteAcquireStore) -> None:
        """follows_of orders by the follow's id."""
        assert self._sent(store, lambda: store.requesters.follows_of(["acc-1"])).endswith("ORDER BY followed_id")


class TestCandidates:
    """``store.candidates``: replace, list_for."""

    def _wanted(self, store: ConcreteAcquireStore) -> int:
        """Add a follow with one wanted episode and return the wanted rowid.

        Args:
            store: The store.

        Returns:
            The wanted rowid.
        """
        followed_id = _follow(store)
        return store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=81189),
                kind="episode",
                status="pending",
                enqueued_at=200,
                followed_id=followed_id,
                season=1,
                episode=1,
            )
        )

    def test_a_wanted_row_with_no_search_lists_none(self, store: ConcreteAcquireStore) -> None:
        """No concluded search, no candidate."""
        assert store.candidates.list_for(self._wanted(store)) == []

    def test_replace_then_list_round_trips_in_rank_order(self, store: ConcreteAcquireStore) -> None:
        """The candidates read back as written, best rank first, whatever the insertion order."""
        wanted_id = self._wanted(store)
        rows = [
            _candidate(3, info_hash=None, resolution=None, season=None, episode=None),
            _candidate(1),
            _candidate(2),
        ]

        store.candidates.replace(wanted_id, rows)

        assert store.candidates.list_for(wanted_id) == sorted(rows, key=lambda row: row.rank)

    def test_replace_swaps_the_previous_set(self, store: ConcreteAcquireStore) -> None:
        """A new concluded search replaces the previous set wholesale."""
        wanted_id = self._wanted(store)
        store.candidates.replace(wanted_id, [_candidate(1), _candidate(2), _candidate(3)])

        store.candidates.replace(wanted_id, [_candidate(1, title="Fresh")])

        assert [row.title for row in store.candidates.list_for(wanted_id)] == ["Fresh"]

    def test_replace_with_nothing_clears(self, store: ConcreteAcquireStore) -> None:
        """A concluded search that found nothing empties the set."""
        wanted_id = self._wanted(store)
        store.candidates.replace(wanted_id, [_candidate(1)])

        store.candidates.replace(wanted_id, [])

        assert store.candidates.list_for(wanted_id) == []

    def test_a_failed_replace_keeps_the_previous_set(self, store: ConcreteAcquireStore) -> None:
        """The delete and the inserts share one transaction: a duplicate rank rolls both back."""
        wanted_id = self._wanted(store)
        store.candidates.replace(wanted_id, [_candidate(1, title="Kept")])

        with pytest.raises(sqlite3.IntegrityError):
            store.candidates.replace(wanted_id, [_candidate(1), _candidate(1)])

        assert [row.title for row in store.candidates.list_for(wanted_id)] == ["Kept"]

    def test_replace_is_scoped_to_its_wanted_row(self, store: ConcreteAcquireStore) -> None:
        """Replacing one row's set leaves another row's untouched."""
        first = self._wanted(store)
        second = store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=81189),
                kind="episode",
                status="pending",
                enqueued_at=201,
                followed_id=store.follow.find_by_ref(MediaRef(tvdb_id=81189)).id,  # type: ignore[union-attr]
                season=1,
                episode=2,
            )
        )
        store.candidates.replace(first, [_candidate(1, title="First")])
        store.candidates.replace(second, [_candidate(1, title="Second")])

        store.candidates.replace(first, [])

        assert [row.title for row in store.candidates.list_for(second)] == ["Second"]

    def test_candidates_go_with_their_wanted_row(self, store: ConcreteAcquireStore) -> None:
        """Deleting the follow deletes its open wanted rows and, by cascade, their candidates."""
        wanted_id = self._wanted(store)
        store.candidates.replace(wanted_id, [_candidate(1)])
        followed_id = store.follow.find_by_ref(MediaRef(tvdb_id=81189)).id  # type: ignore[union-attr]

        store.follow.delete(followed_id)  # type: ignore[arg-type]

        assert store.candidates.list_for(wanted_id) == []


class TestFollowReadersReturnScopeAndRemoval:
    """Every ``followed_series`` reader carries ``scope`` and ``removed_at``."""

    def test_a_new_follow_reads_scope_follow_not_removed(self, store: ConcreteAcquireStore) -> None:
        """The defaults: scope 'follow', removed_at None, through every reader."""
        followed_id = _follow(store)
        ref = MediaRef(tvdb_id=81189)

        readers = [
            store.follow.get(followed_id),
            store.follow.find_by_ref(ref),
            store.follow.find_all_by_ref(ref)[0],
            store.follow.list_active()[0],
            store.follow.list_all()[0],
        ]

        for follow in readers:
            assert follow is not None
            assert (follow.scope, follow.removed_at) == ("follow", None)

    def test_a_request_scope_and_a_removal_are_read_back(self, store: ConcreteAcquireStore) -> None:
        """A row whose scope and removed_at were written is read with them by every reader."""
        followed_id = _follow(store)
        store._ensure_open().execute(  # noqa: SLF001 — no writer exists yet: P6/P7 add them
            "UPDATE followed_series SET scope = 'request', removed_at = 777 WHERE id = ?", (followed_id,)
        )
        ref = MediaRef(tvdb_id=81189)

        readers = [
            store.follow.get(followed_id),
            store.follow.find_by_ref(ref),
            store.follow.find_all_by_ref(ref)[0],
            store.follow.list_all()[0],
        ]

        for follow in readers:
            assert follow is not None
            assert (follow.scope, follow.removed_at) == ("request", 777)

    def test_a_bad_scope_is_refused_at_construction(self) -> None:
        """FollowedSeries validates its scope as it validates its kind."""
        with pytest.raises(ValueError, match="scope"):
            FollowedSeries(media_ref=MediaRef(tvdb_id=1), title="x", added_at=1, scope="other")  # type: ignore[arg-type]


class TestWantedTrigger:
    """``WantedItem.trigger`` is written by ``add`` and read back."""

    @pytest.mark.parametrize("trigger", ["manual", "automatic", None])
    def test_add_writes_the_trigger_and_get_reads_it(self, store: ConcreteAcquireStore, trigger: str | None) -> None:
        """A trigger (or its absence: unknown) round-trips through add and get."""
        wanted_id = store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=81189),
                kind="season",
                status="pending",
                enqueued_at=200,
                season=1,
                trigger=trigger,  # type: ignore[arg-type]
            )
        )

        item = store.wanted.get(wanted_id)

        assert item is not None
        assert item.trigger == trigger

    def test_the_list_readers_read_it_too(self, store: ConcreteAcquireStore) -> None:
        """list_pending carries the trigger as get does."""
        store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=81189),
                kind="season",
                status="pending",
                enqueued_at=200,
                season=1,
                trigger="manual",
            )
        )

        assert [item.trigger for item in store.wanted.list_pending()] == ["manual"]

    def test_an_item_with_no_trigger_reads_unknown(self) -> None:
        """The default is NULL, an honest « unknown »: v0's frozen season route writes none."""
        item = WantedItem(media_ref=MediaRef(tvdb_id=1), kind="movie", status="pending", enqueued_at=1)
        assert item.trigger is None

    def test_a_bad_trigger_is_refused_at_construction(self) -> None:
        """WantedItem validates its trigger as it validates its kind and status."""
        with pytest.raises(ValueError, match="trigger"):
            WantedItem(
                media_ref=MediaRef(tvdb_id=1),
                kind="movie",
                status="pending",
                enqueued_at=1,
                trigger="cli",  # type: ignore[arg-type]
            )
