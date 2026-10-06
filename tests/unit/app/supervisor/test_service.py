"""Unit tests for ``RunService``: the in-process enqueue of a run or an item rescrape.

An ask is authorised before any row is written; an equal ask waiting in the queue is joined, never
refused; a supplied uid is kept; a rescrape joins a request already running; the queue view reads
the waiting requests in order.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.actor import SYSTEM_ROLE_ID, Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.errors import AppForbidden, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import (
    RequestState,
    RunKind,
    RunOptions,
    RunRequest,
    RunTrigger,
)
from personalscraper.app.supervisor.service import RunAsked, RunService
from personalscraper.core.identity import ItemId
from tests.conftest import LoggedEvents

_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)
_READ_ONLY = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)
_ITEM = ItemId("item-1")
_OTHER_ITEM = ItemId("item-2")


def _ordinary(rights: frozenset[Right], ceiling: InstanceCeiling = _NO_CEILING) -> Actor:
    """An ordinary-role actor holding some rights.

    Args:
        rights: The rights its role carries.
        ceiling: The instance's ceiling.

    Returns:
        The actor.
    """
    return Actor(
        account_id=AccountId("account-a"),
        name="a",
        role_id=RoleId("role-a"),
        role_kind=RoleKind.ORDINARY,
        role_rights=rights,
        ceiling=ceiling,
    )


def _admin(ceiling: InstanceCeiling = _NO_CEILING) -> Actor:
    """An Admin actor.

    Args:
        ceiling: The instance's ceiling.

    Returns:
        The actor.
    """
    return Actor.system(ceiling, account_id=AccountId("account-admin"), name="admin")


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` on ``tmp_path``.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    try:
        yield app_store
    finally:
        app_store.close()


class _Clock:
    """A settable clock.

    Attributes:
        now: The epoch it answers.
    """

    def __init__(self) -> None:
        """Start at a fixed epoch."""
        self.now = 1_000.0

    def __call__(self) -> float:
        """Answer the current epoch.

        Returns:
            :attr:`now`.
        """
        return self.now


@pytest.fixture
def clock() -> _Clock:
    """The service's clock.

    Returns:
        The clock.
    """
    return _Clock()


@pytest.fixture
def service(store: AppStore, tmp_path: Path, clock: _Clock) -> RunService:
    """The service over the store.

    Args:
        store: The store.
        tmp_path: The test's temporary directory.
        clock: The clock.

    Returns:
        The service.
    """
    return RunService(store=store, data_dir=tmp_path, clock=clock)


def _rows(store: AppStore) -> int:
    """How many requests the queue holds, whatever their state.

    Args:
        store: The store.

    Returns:
        The count.
    """
    return len(store.runs.queued()) + len(store.runs.running())


class TestAuthorisation:
    """The ask is refused before anything is written."""

    def test_an_actor_without_pipeline_control_is_refused_before_any_row(
        self, service: RunService, store: AppStore
    ) -> None:
        """No ``pipeline.control``: ``right.missing``, and the queue stays empty."""
        with pytest.raises(AppForbidden) as refusal:
            service.ask_run(_ordinary(frozenset()), trigger=RunTrigger.WEB, options=RunOptions())

        assert refusal.value.code == RefusalCode.RIGHT_MISSING
        assert _rows(store) == 0

    def test_an_actor_without_the_rescrape_right_is_refused_before_any_row(
        self, service: RunService, store: AppStore
    ) -> None:
        """A rescrape asks ``library.rescrape``, not the pipeline's right."""
        with pytest.raises(AppForbidden) as refusal:
            service.ask_rescrape(_ordinary(frozenset({Right.PIPELINE_CONTROL})), item_id=_ITEM)

        assert refusal.value.code == RefusalCode.RIGHT_MISSING
        assert _rows(store) == 0

    def test_a_read_only_ceiling_refuses_an_admin(self, service: RunService, store: AppStore) -> None:
        """The ceiling binds Admin too: nothing is written."""
        with pytest.raises(AppForbidden) as refusal:
            service.ask_run(_admin(_READ_ONLY), trigger=RunTrigger.CLI, options=RunOptions())

        assert refusal.value.code == RefusalCode.INSTANCE_FORBIDDEN_WRITE
        assert _rows(store) == 0


class TestAskRun:
    """A pipeline run is queued, or joins the equal one waiting."""

    def test_the_first_ask_queues_a_new_request(self, service: RunService, store: AppStore, clock: _Clock) -> None:
        """A new uid, ``queued``, not joined; the request is stored as asked."""
        asked = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions(dry_run=True))

        assert asked.state == "queued"
        assert asked.joined is False
        stored = store.runs.get(asked.uid)
        assert stored is not None
        assert (stored.kind, stored.trigger, stored.asked_by, stored.asked_at) == (
            RunKind.PIPELINE,
            RunTrigger.WEB,
            AccountId("account-admin"),
            clock.now,
        )
        assert stored.options == RunOptions(dry_run=True)

    def test_two_equal_asks_answer_one_uid_the_second_joined(self, service: RunService, store: AppStore) -> None:
        """The second ask joins the first: same uid, ``queued``, one row."""
        first = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())
        second = service.ask_run(_admin(), trigger=RunTrigger.CLI, options=RunOptions())

        assert second == RunAsked(uid=first.uid, state="queued", joined=True)
        assert _rows(store) == 1

    def test_an_ask_with_other_options_is_queued_beside(self, service: RunService, store: AppStore) -> None:
        """Options differ: a second request, never a refusal."""
        first = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())
        second = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions(dry_run=True))

        assert second.uid != first.uid
        assert second.joined is False
        assert _rows(store) == 2

    def test_a_running_request_does_not_absorb_a_new_ask(self, service: RunService, store: AppStore) -> None:
        """New arrivals may have come: an ask equal to a RUNNING pipeline is queued."""
        running = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())
        request = store.runs.get(running.uid)
        assert request is not None
        request.admit(4242, 1_001.0)
        assert store.runs.save(request)

        again = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())

        assert again.uid != running.uid
        assert (again.state, again.joined) == ("queued", False)

    def test_a_supplied_uid_is_kept(self, service: RunService, store: AppStore) -> None:
        """A caller that already promised a uid gets it back, and it keys the row."""
        uid = RunUid("a" * 32)

        asked = service.ask_run(_admin(), trigger=RunTrigger.CLI, options=RunOptions(), uid=uid)

        assert asked.uid == uid
        assert store.runs.get(uid) is not None

    def test_a_supplied_uid_does_not_replace_the_joined_one(self, service: RunService, store: AppStore) -> None:
        """An equal ask joins the waiting request even when it brings its own uid: the waiting uid answers."""
        first = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())

        second = service.ask_run(_admin(), trigger=RunTrigger.CLI, options=RunOptions(), uid=RunUid("b" * 32))

        assert second.uid == first.uid
        assert second.joined is True
        assert store.runs.get(RunUid("b" * 32)) is None

    def test_asks_are_logged(self, service: RunService, logged_events: LoggedEvents) -> None:
        """``app.runs.asked`` for a new request, ``app.runs.joined`` for a joined one."""
        with logged_events() as events:
            service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())
            service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())

        assert [event["event"] for event in events if event["event"].startswith("app.runs.")] == [
            "app.runs.asked",
            "app.runs.joined",
        ]


class TestAskRescrape:
    """A rescrape joins a waiting or running request of the same item."""

    def test_a_rescrape_is_queued_for_its_item(self, service: RunService, store: AppStore) -> None:
        """A new request of kind rescrape carrying the item."""
        asked = service.ask_rescrape(_admin(), item_id=_ITEM)

        assert (asked.state, asked.joined) == ("queued", False)
        stored = store.runs.get(asked.uid)
        assert stored is not None
        assert stored.kind is RunKind.RESCRAPE
        assert stored.trigger is RunTrigger.WEB
        assert stored.options.item_id == _ITEM

    def test_a_second_rescrape_of_the_item_joins_the_queued_one(self, service: RunService, store: AppStore) -> None:
        """Same item, still queued: same uid, ``queued``."""
        first = service.ask_rescrape(_admin(), item_id=_ITEM)
        second = service.ask_rescrape(_admin(), item_id=_ITEM)

        assert second == RunAsked(uid=first.uid, state="queued", joined=True)
        assert _rows(store) == 1

    def test_a_rescrape_of_another_item_is_queued_beside(self, service: RunService, store: AppStore) -> None:
        """Another item does not join."""
        first = service.ask_rescrape(_admin(), item_id=_ITEM)
        second = service.ask_rescrape(_admin(), item_id=_OTHER_ITEM)

        assert second.uid != first.uid
        assert _rows(store) == 2

    def test_a_rescrape_joins_the_running_request_of_its_item_and_answers_running(
        self, service: RunService, store: AppStore
    ) -> None:
        """The joined request runs: the answer is ``running``, joined."""
        first = service.ask_rescrape(_admin(), item_id=_ITEM)
        request = store.runs.get(first.uid)
        assert request is not None
        request.admit(4242, 1_001.0)
        assert store.runs.save(request)

        second = service.ask_rescrape(_admin(), item_id=_ITEM)

        assert second == RunAsked(uid=first.uid, state="running", joined=True)
        assert _rows(store) == 1

    def test_a_rescrape_never_joins_a_pipeline_run(self, service: RunService) -> None:
        """Kinds differ: a pipeline run waiting does not answer a rescrape."""
        run = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())

        rescrape = service.ask_rescrape(_admin(), item_id=_ITEM)

        assert rescrape.uid != run.uid


class TestReads:
    """``queue_view`` and ``request``."""

    def test_the_queue_view_lists_the_queued_in_order_and_the_running(
        self, service: RunService, store: AppStore, clock: _Clock
    ) -> None:
        """The running request apart, the queued oldest first; no lease, so none live."""
        head = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())
        clock.now += 1
        second = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions(dry_run=True))
        clock.now += 1
        third = service.ask_rescrape(_admin(), item_id=_ITEM)
        running = store.runs.get(head.uid)
        assert running is not None
        running.admit(4242, clock.now)
        assert store.runs.save(running)

        view = service.queue_view()

        assert view.running is not None
        assert view.running.uid == head.uid
        assert [request.uid for request in view.queued] == [second.uid, third.uid]
        assert view.lease_live is False

    def test_the_queue_view_of_an_empty_queue(self, service: RunService) -> None:
        """Nothing runs, nothing waits."""
        view = service.queue_view()

        assert (view.running, view.queued, view.lease_live) == (None, (), False)

    def test_the_lease_is_live_while_it_has_not_expired(
        self, service: RunService, store: AppStore, clock: _Clock
    ) -> None:
        """A claimed lease read before its expiry is live, after it is not."""
        assert store.lease.claim(4242, "host", clock.now, 60.0, lambda pid: True)

        assert service.queue_view().lease_live is True
        clock.now += 61.0
        assert service.queue_view().lease_live is False

    def test_the_queue_view_is_read_while_another_connection_holds_the_writer_lock(
        self, service: RunService, store: AppStore, tmp_path: Path
    ) -> None:
        """A pure read never waits for the writer lock (the supervisor's writes): it reads the committed state."""
        asked = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())
        writer = sqlite3.connect(tmp_path / "app.db", isolation_level=None)
        try:
            writer.execute("BEGIN IMMEDIATE")

            view = service.queue_view()
        finally:
            writer.close()

        assert [request.uid for request in view.queued] == [asked.uid]

    def test_request_reads_one_by_uid(self, service: RunService) -> None:
        """A known uid answers its request, an unknown one ``None``."""
        asked = service.ask_run(_admin(), trigger=RunTrigger.WEB, options=RunOptions())

        found = service.request(asked.uid)

        assert isinstance(found, RunRequest)
        assert found.state is RequestState.QUEUED
        assert service.request(RunUid("c" * 32)) is None


def test_the_system_role_id_is_the_admin_role() -> None:
    """Guard of the fixture: the helper builds an Admin, whose rights list is empty."""
    assert _admin().role_id == SYSTEM_ROLE_ID
