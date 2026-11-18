"""Unit tests for the queue and lease repositories over ``app.db``, and the ``007_supervisor.sql`` migration.

The migration applies on a fresh store and on one left at ``006``; the queue reads FIFO and writes
every field of a request back; the lease is claimed once, refused while live, and taken over once it
has expired or its holder is gone.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.store.store import _MIGRATIONS_DIR, AppStore
from personalscraper.app.supervisor.lease_repository import LeaseRepository
from personalscraper.app.supervisor.model import (
    RequestState,
    RunKind,
    RunOptions,
    RunRequest,
    RunTrigger,
    Settlement,
    WaitReason,
)
from personalscraper.app.supervisor.queue_repository import QueueRepository
from personalscraper.core.identity import ItemId
from personalscraper.core.sqlite import apply_migrations, open_db

ASKER = AccountId("account-a")
NOW = 1_000.0


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


def _ask(
    options: RunOptions | None = None,
    *,
    kind: RunKind = RunKind.PIPELINE,
    now: float = NOW,
) -> RunRequest:
    """Ask a run at *now*.

    Args:
        options: What the run is asked to do; the defaults when omitted.
        kind: The kind of run.
        now: The epoch of the ask.

    Returns:
        The queued request.
    """
    return RunRequest.ask(kind, RunTrigger.WEB, options or RunOptions(), ASKER, now)


def _no_pid_alive(pid: int) -> bool:
    """A process-liveness probe that finds nobody alive.

    Args:
        pid: A process id.

    Returns:
        Always ``False``.
    """
    return False


def _every_pid_alive(pid: int) -> bool:
    """A process-liveness probe that finds everybody alive.

    Args:
        pid: A process id.

    Returns:
        Always ``True``.
    """
    return True


class TestMigration:
    """``007_supervisor.sql`` adds the two tables and nothing else."""

    def test_a_fresh_store_has_the_queue_and_the_lease(self, store: AppStore) -> None:
        """A fresh store has the queue and the lease."""
        assert store.runs.get("0" * 32) is None
        assert store.lease.read() is None

    def test_a_store_left_at_006_migrates_and_keeps_its_rows(self, tmp_path: Path) -> None:
        """A store left at 006 migrates and keeps its rows."""
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        for script in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            if int(script.stem.split("_")[0]) <= 6:
                shutil.copy(script, scripts / script.name)
        db_path = tmp_path / "data" / "app.db"
        db_path.parent.mkdir()
        conn = open_db(db_path)
        try:
            apply_migrations(conn, scripts)
            conn.execute("INSERT INTO app_setting (key, value) VALUES ('k', 'v')")
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
        finally:
            conn.close()

        migrated = AppStore(db_path)
        try:
            assert migrated.settings.setting("k") == "v"
            migrated.runs.insert(_ask())
            assert migrated.lease.read() is None
            conn = sqlite3.connect(db_path)
            try:
                assert conn.execute("PRAGMA user_version").fetchone()[0] == 10
            finally:
                conn.close()
        finally:
            migrated.close()

    def test_the_base_refuses_a_state_the_model_does_not_know(self, store: AppStore) -> None:
        """The base refuses a state the model does not know."""
        store.runs.insert(_ask())
        conn = store._ensure_open()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE run_request SET state = 'paused'")

    def test_the_base_keeps_one_lease_row_at_most(self, store: AppStore) -> None:
        """The base keeps one lease row at most."""
        conn = store._ensure_open()
        conn.execute("INSERT INTO run_lease VALUES (1, 1, 'h', 1.0, 1.0, 2.0)")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO run_lease VALUES (2, 2, 'h', 1.0, 1.0, 2.0)")


class TestQueue:
    """The queue of asked runs."""

    def test_insert_then_get_returns_an_equal_request(self, store: AppStore) -> None:
        """Insert then get returns an equal request."""
        request = _ask(RunOptions(skip_trailers=True))
        store.runs.insert(request)
        assert store.runs.get(request.uid) == request

    def test_get_of_an_unknown_uid_is_none(self, store: AppStore) -> None:
        """Get of an unknown uid is none."""
        assert store.runs.get("f" * 32) is None

    def test_first_queued_is_the_oldest_ask(self, store: AppStore) -> None:
        """First queued is the oldest ask."""
        late = _ask(RunOptions(dry_run=True), now=NOW + 10)
        early = _ask(now=NOW)
        middle = _ask(RunOptions(skip_trailers=True), now=NOW + 5)
        for request in (late, early, middle):
            store.runs.insert(request)
        assert store.runs.first_queued() == early

    def test_first_queued_keeps_insertion_order_on_a_tie(self, store: AppStore) -> None:
        """First queued keeps insertion order on a tie."""
        first = _ask(RunOptions(dry_run=True))
        second = _ask(RunOptions(skip_trailers=True))
        store.runs.insert(first)
        store.runs.insert(second)
        assert store.runs.first_queued() == first

    def test_first_queued_skips_what_is_running_or_settled(self, store: AppStore) -> None:
        """First queued skips what is running or settled."""
        running = _ask(now=NOW)
        running.admit(4242, NOW)
        settled = _ask(RunOptions(dry_run=True), now=NOW + 1)
        settled.admit(4243, NOW + 1)
        settled.settle(Settlement.SUCCESS, NOW + 2)
        waiting = _ask(RunOptions(skip_trailers=True), now=NOW + 3)
        for request in (running, settled, waiting):
            store.runs.insert(request)
        assert store.runs.first_queued() == waiting

    def test_first_queued_of_an_empty_queue_is_none(self, store: AppStore) -> None:
        """First queued of an empty queue is none."""
        assert store.runs.first_queued() is None

    def test_running_lists_the_running_requests_oldest_first(self, store: AppStore) -> None:
        """Running lists the running requests oldest first."""
        later = _ask(RunOptions(dry_run=True), now=NOW + 1)
        earlier = _ask(now=NOW)
        queued = _ask(RunOptions(skip_trailers=True), now=NOW + 2)
        later.admit(1, NOW + 1)
        earlier.admit(2, NOW)
        for request in (later, earlier, queued):
            store.runs.insert(request)
        assert store.runs.running() == [earlier, later]

    def test_save_writes_every_transition_back(self, store: AppStore) -> None:
        """Save writes every transition back."""
        request = _ask()
        store.runs.insert(request)
        request.admit(4242, NOW + 1)
        store.runs.save(request)
        assert store.runs.get(request.uid) == request
        request.back_to_queue(WaitReason.PIPELINE_LOCK_HELD)
        store.runs.save(request)
        assert store.runs.get(request.uid) == request
        request.admit(4343, NOW + 2)
        request.settle(Settlement.INTERRUPTED, NOW + 3)
        store.runs.save(request)
        saved = store.runs.get(request.uid)
        assert saved == request
        assert saved is not None
        assert saved.state is RequestState.SETTLED
        assert saved.settlement is Settlement.INTERRUPTED

    def test_save_of_an_unknown_request_raises(self, store: AppStore) -> None:
        """Save of an unknown request raises."""
        with pytest.raises(LookupError):
            store.runs.save(_ask())

    def test_queued_like_finds_a_queued_pipeline_run_of_equal_options(self, store: AppStore) -> None:
        """Queued like finds a queued pipeline run of equal options."""
        queued = _ask(RunOptions(dry_run=True))
        store.runs.insert(queued)
        store.runs.insert(_ask(RunOptions(skip_trailers=True), now=NOW + 1))
        found = store.runs.queued_like(RunKind.PIPELINE, queued.options_json, None)
        assert found == queued

    def test_queued_like_ignores_other_options_kinds_and_states(self, store: AppStore) -> None:
        """Queued like ignores other options kinds and states."""
        running = _ask(RunOptions(dry_run=True))
        running.admit(1, NOW)
        store.runs.insert(running)
        store.runs.insert(_ask(RunOptions(item_id=ItemId(3)), kind=RunKind.RESCRAPE, now=NOW + 1))
        assert store.runs.queued_like(RunKind.PIPELINE, running.options_json, None) is None
        assert store.runs.queued_like(RunKind.PIPELINE, _ask().options_json, None) is None

    def test_queued_like_finds_a_queued_rescrape_by_item(self, store: AppStore) -> None:
        """Queued like finds a queued rescrape by item."""
        queued = _ask(RunOptions(item_id=ItemId(3)), kind=RunKind.RESCRAPE)
        store.runs.insert(queued)
        store.runs.insert(_ask(RunOptions(item_id=ItemId(4)), kind=RunKind.RESCRAPE, now=NOW + 1))
        asked = _ask(RunOptions(item_id=ItemId(3), dry_run=True), kind=RunKind.RESCRAPE)
        assert store.runs.queued_like(RunKind.RESCRAPE, asked.options_json, ItemId(3)) == queued
        assert store.runs.queued_like(RunKind.RESCRAPE, asked.options_json, ItemId(5)) is None

    def test_queued_lists_every_queued_request_in_fifo_order(self, store: AppStore) -> None:
        """Queued lists every queued request, oldest ask first, and nothing else."""
        late = _ask(RunOptions(dry_run=True), now=NOW + 10)
        early = _ask(now=NOW)
        middle = _ask(RunOptions(skip_trailers=True), now=NOW + 5)
        running = _ask(RunOptions(no_post_maintenance=True), now=NOW + 1)
        running.admit(1, NOW + 1)
        settled = _ask(RunOptions(continue_on_trailer_error=True), now=NOW + 2)
        settled.admit(2, NOW + 2)
        settled.settle(Settlement.SUCCESS, NOW + 3)
        for request in (late, early, middle, running, settled):
            store.runs.insert(request)
        assert store.runs.queued() == (early, middle, late)

    def test_queued_keeps_insertion_order_on_a_tie(self, store: AppStore) -> None:
        """Queued breaks an equal ``asked_at`` by insertion order."""
        first = _ask(RunOptions(dry_run=True))
        second = _ask(RunOptions(skip_trailers=True))
        store.runs.insert(first)
        store.runs.insert(second)
        assert store.runs.queued() == (first, second)

    def test_queued_of_an_empty_queue_is_empty(self, store: AppStore) -> None:
        """Queued of an empty queue is an empty tuple."""
        assert store.runs.queued() == ()

    def test_touch_heartbeat_moves_a_running_requests_heartbeat(self, store: AppStore) -> None:
        """A heartbeat on a running request is written and says so."""
        request = _ask()
        request.admit(4242, NOW)
        store.runs.insert(request)
        assert store.runs.touch_heartbeat(request.uid, NOW + 30) is True
        saved = store.runs.get(request.uid)
        assert saved is not None
        assert saved.heartbeat_at == NOW + 30

    def test_touch_heartbeat_of_a_settled_request_changes_nothing(self, store: AppStore) -> None:
        """A heartbeat on a settled request writes nothing and says so."""
        request = _ask()
        request.admit(4242, NOW)
        request.settle(Settlement.SUCCESS, NOW + 1)
        store.runs.insert(request)
        assert store.runs.touch_heartbeat(request.uid, NOW + 30) is False
        assert store.runs.get(request.uid) == request

    def test_touch_heartbeat_of_a_queued_or_unknown_request_is_false(self, store: AppStore) -> None:
        """A heartbeat on a queued or an unknown request writes nothing."""
        queued = _ask()
        store.runs.insert(queued)
        assert store.runs.touch_heartbeat(queued.uid, NOW + 30) is False
        assert store.runs.touch_heartbeat("f" * 32, NOW + 30) is False
        assert store.runs.get(queued.uid) == queued

    def test_a_stale_save_does_not_resurrect_a_settled_request(self, store: AppStore) -> None:
        """A save over a row whose state moved meanwhile writes nothing and returns ``False``."""
        request = _ask()
        request.admit(4242, NOW)
        store.runs.insert(request)
        stale_copy = store.runs.get(request.uid)
        assert stale_copy is not None
        request.settle(Settlement.KILLED, NOW + 5)
        assert store.runs.save(request) is True
        stale_copy.back_to_queue(WaitReason.PIPELINE_LOCK_HELD)
        assert store.runs.save(stale_copy) is False
        saved = store.runs.get(request.uid)
        assert saved is not None
        assert saved.state is RequestState.SETTLED
        assert saved.settlement is Settlement.KILLED

    def test_a_save_returns_true_and_a_second_move_saves_from_the_new_state(self, store: AppStore) -> None:
        """After a successful save the request is read in its new state: the next move saves too."""
        request = _ask()
        store.runs.insert(request)
        request.admit(4242, NOW + 1)
        assert store.runs.save(request) is True
        request.settle(Settlement.SUCCESS, NOW + 2)
        assert store.runs.save(request) is True

    def test_queued_like_of_a_pipeline_ignores_the_options_of_a_rescrape_and_matches_its_own(
        self, store: AppStore
    ) -> None:
        """A pipeline ask joins only a queued pipeline run of its own options."""
        store.runs.insert(_ask(RunOptions(dry_run=True), now=NOW))
        wanted = _ask(RunOptions(skip_trailers=True), now=NOW + 1)
        store.runs.insert(wanted)
        assert store.runs.queued_like(RunKind.PIPELINE, wanted.options_json, None) == wanted

    def test_queued_like_of_a_rescrape_without_an_item_matches_nothing(self, store: AppStore) -> None:
        """A rescrape with no item never joins: not even a queued rescrape of the same options."""
        store.runs.insert(_ask(kind=RunKind.RESCRAPE))
        asked = _ask(kind=RunKind.RESCRAPE)
        assert store.runs.queued_like(RunKind.RESCRAPE, asked.options_json, None) is None

    def test_first_queued_and_queued_order_an_out_of_order_insert(self, store: AppStore) -> None:
        """The order is the query's, not the insertion's nor the index's: the oldest ask comes first."""
        store._ensure_open().execute("DROP INDEX run_request_state_asked")  # the planner must not order for us
        newer = _ask(RunOptions(dry_run=True), now=NOW + 10)
        older = _ask(now=NOW)
        store.runs.insert(newer)
        store.runs.insert(older)
        assert store.runs.first_queued() == older
        assert store.runs.queued() == (older, newer)
        later = _ask(RunOptions(skip_trailers=True), now=NOW + 20)
        later.admit(1, NOW + 20)
        earlier = _ask(RunOptions(no_post_maintenance=True), now=NOW + 15)
        earlier.admit(2, NOW + 15)
        store.runs.insert(later)
        store.runs.insert(earlier)
        assert store.runs.running() == [earlier, later]


class TestLease:
    """The supervisor's lease."""

    def test_claim_of_an_empty_lease_takes_it(self, store: AppStore) -> None:
        """Claim of an empty lease takes it."""
        lease = store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert lease is not None
        assert (lease.holder_pid, lease.holder_host) == (4242, "iznoserver")
        assert (lease.taken_at, lease.renewed_at, lease.expires_at) == (NOW, NOW, NOW + 60)
        assert store.lease.read() == lease

    def test_claim_is_refused_while_the_lease_is_live(self, store: AppStore) -> None:
        """Claim is refused while the lease is live."""
        held = store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert store.lease.claim(5151, "iznoserver", NOW + 30, 60, _every_pid_alive) is None
        assert store.lease.read() == held

    def test_claim_succeeds_once_the_lease_has_expired(self, store: AppStore) -> None:
        """Claim succeeds once the lease has expired."""
        store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        taken = store.lease.claim(5151, "iznoserver", NOW + 60, 60, _every_pid_alive)
        assert taken is not None
        assert taken.holder_pid == 5151
        assert (taken.taken_at, taken.expires_at) == (NOW + 60, NOW + 120)
        assert store.lease.read() == taken

    def test_claim_succeeds_while_live_when_the_holder_is_gone(self, store: AppStore) -> None:
        """Claim succeeds while live when the holder is gone."""
        store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        taken = store.lease.claim(5151, "iznoserver", NOW + 5, 60, _no_pid_alive)
        assert taken is not None
        assert taken.holder_pid == 5151

    def test_renew_extends_the_holders_lease(self, store: AppStore) -> None:
        """Renew extends the holders lease."""
        store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert store.lease.renew(4242, "iznoserver", NOW + 30, 60) is True
        lease = store.lease.read()
        assert lease is not None
        assert (lease.taken_at, lease.renewed_at, lease.expires_at) == (NOW, NOW + 30, NOW + 90)

    def test_renew_is_refused_to_another_pid(self, store: AppStore) -> None:
        """Renew is refused to another pid."""
        store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert store.lease.renew(5151, "iznoserver", NOW + 30, 60) is False
        lease = store.lease.read()
        assert lease is not None
        assert lease.expires_at == NOW + 60

    def test_renew_without_a_lease_is_refused(self, store: AppStore) -> None:
        """Renew without a lease is refused."""
        assert store.lease.renew(4242, "iznoserver", NOW, 60) is False

    def test_release_deletes_the_holders_lease(self, store: AppStore) -> None:
        """Release deletes the holders lease."""
        store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert store.lease.release(4242, "iznoserver") is True
        assert store.lease.read() is None

    def test_release_by_another_pid_keeps_the_lease(self, store: AppStore) -> None:
        """Release by another pid keeps the lease."""
        held = store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert store.lease.release(5151, "iznoserver") is False
        assert store.lease.read() == held

    def test_a_released_lease_is_claimable_at_once(self, store: AppStore) -> None:
        """A released lease is claimable at once."""
        store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        store.lease.release(4242, "iznoserver")
        assert store.lease.claim(5151, "iznoserver", NOW + 1, 60, _every_pid_alive) is not None

    def test_a_live_lease_of_a_gone_holder_on_another_host_is_not_taken_over(self, store: AppStore) -> None:
        """The dead-holder takeover is for this host's lease: another host's holds until it expires."""
        held = store.lease.claim(4242, "other-host", NOW, 60, _every_pid_alive)
        assert store.lease.claim(5151, "iznoserver", NOW + 5, 60, _no_pid_alive) is None
        assert store.lease.read() == held

    def test_another_hosts_lease_is_claimable_on_expiry(self, store: AppStore) -> None:
        """Another host's lease is claimed once it has expired."""
        store.lease.claim(4242, "other-host", NOW, 60, _every_pid_alive)
        taken = store.lease.claim(5151, "iznoserver", NOW + 60, 60, _every_pid_alive)
        assert taken is not None
        assert (taken.holder_pid, taken.holder_host) == (5151, "iznoserver")

    def test_renew_is_refused_to_the_same_pid_on_another_host(self, store: AppStore) -> None:
        """Renew matches the holder's pid AND host."""
        store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert store.lease.renew(4242, "other-host", NOW + 30, 60) is False
        lease = store.lease.read()
        assert lease is not None
        assert lease.expires_at == NOW + 60

    def test_release_by_the_same_pid_on_another_host_keeps_the_lease(self, store: AppStore) -> None:
        """Release matches the holder's pid AND host."""
        held = store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert store.lease.release(4242, "other-host") is False
        assert store.lease.read() == held

    def test_claim_lives_for_the_ttl_it_is_given(self, store: AppStore) -> None:
        """A claim expires at ``now + ttl``, whatever the default ttl is."""
        lease = store.lease.claim(4242, "iznoserver", NOW, 7, _every_pid_alive)
        assert lease is not None
        assert lease.expires_at == NOW + 7
        assert store.lease.read() == lease

    def test_renew_extends_for_the_ttl_it_is_given(self, store: AppStore) -> None:
        """A renewal expires at ``now + ttl``, whatever the default ttl is."""
        store.lease.claim(4242, "iznoserver", NOW, 60, _every_pid_alive)
        assert store.lease.renew(4242, "iznoserver", NOW + 10, 7) is True
        lease = store.lease.read()
        assert lease is not None
        assert lease.expires_at == NOW + 17


def test_the_store_exposes_one_repository_per_aggregate(store: AppStore) -> None:
    """The store exposes one repository per aggregate."""
    assert isinstance(store.runs, QueueRepository)
    assert isinstance(store.lease, LeaseRepository)
    assert store.runs is store.runs
    assert store.lease is store.lease
