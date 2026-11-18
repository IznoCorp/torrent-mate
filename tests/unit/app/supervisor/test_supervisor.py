"""Unit tests for the ``Supervisor``: the lease, admission, settlement, adoption and the absorbed watcher.

One tick at a time, over a ``tmp_path`` ``app.db``: the launcher is a fake (no process starts), the
watcher half is a fake (no torrent client), the clock is the test's.
"""

from __future__ import annotations

import dataclasses
import errno
import os
import sqlite3
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.watcher import WatcherDecision, WatcherInput, WatcherOutput, WatcherState
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.errors import AppForbidden
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor import supervisor as supervisor_module
from personalscraper.app.supervisor.events import RunAdmitted, RunQueued, RunSettled
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.launcher import ProcessWorkerLauncher, WorkerLauncher
from personalscraper.app.supervisor.model import (
    LEASE_TTL_S,
    STALE_AFTER_S,
    RequestState,
    RunOptions,
    RunRequest,
    RunTrigger,
    Settlement,
    WaitReason,
)
from personalscraper.app.supervisor.service import RunService
from personalscraper.app.supervisor.supervisor import Supervisor, pid_alive
from personalscraper.conf.models.config import Config
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.indexer.library_view import IndexUnavailable
from personalscraper.pipeline_history import PipelineRunWriter
from tests.conftest import LoggedEvents
from tests.fixtures.torrent_scope import SCOPED_TORRENT_CONFIG, UNSCOPED_TORRENT_CONFIG
from tests.unit.app.supervisor.fakes import FakeWatcherHalf, FakeWorkerLauncher

_HOST = "host-a"
_ADMIN = Actor.system(
    InstanceCeiling(forbidden=frozenset(), read_only=False), account_id=AccountId("account-admin"), name="admin"
)
_DRY = RunOptions(dry_run=True)


class _Clock:
    """A clock the test moves.

    Attributes:
        now: The epoch it reads.
    """

    def __init__(self, now: float = 1000.0) -> None:
        """Start at *now*.

        Args:
            now: The first epoch.
        """
        self.now = now

    def __call__(self) -> float:
        """Read it.

        Returns:
            The epoch.
        """
        return self.now


class _ScriptedWatcherService:
    """A decision engine returning the decisions the test queues; it records the inputs it saw.

    Attributes:
        decisions: The decisions to return, in order (IDLE once exhausted).
        seen: The inputs evaluated.
    """

    def __init__(self, *decisions: WatcherOutput) -> None:
        """Queue *decisions*.

        Args:
            *decisions: The outputs to return.
        """
        self.decisions = list(decisions)
        self.seen: list[WatcherInput] = []

    def evaluate(self, inp: WatcherInput, state: WatcherState) -> WatcherOutput:
        """Return the next queued decision.

        Args:
            inp: The input.
            state: The state.

        Returns:
            The decision, carrying *state* when none is queued.
        """
        self.seen.append(inp)
        if self.decisions:
            return self.decisions.pop(0)
        return WatcherOutput(decision=WatcherDecision.IDLE, new_state=state)


def _fire(reason: str = "completion") -> WatcherOutput:
    """A FIRE_RUN decision.

    Args:
        reason: Why the run fires.

    Returns:
        The decision.
    """
    return WatcherOutput(decision=WatcherDecision.FIRE_RUN, new_state=WatcherState(), run_reason=reason)


def _input(now: float = 1000.0, *, sentinel: bool = False) -> WatcherInput:
    """A quiet watcher input.

    Args:
        now: The cycle's epoch.
        sentinel: Whether the manual sentinel is present.

    Returns:
        The input, the pipeline lock reported free.
    """
    return WatcherInput(
        completed_hashes=frozenset(),
        ingested_hashes=frozenset(),
        triage_skipped_hashes=frozenset(),
        sentinel_present=sentinel,
        pipeline_lock_held=False,
        now=now,
        downloading_count=0,
    )


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


@pytest.fixture
def clock() -> _Clock:
    """The test's clock.

    Returns:
        A clock at epoch 1000.
    """
    return _Clock()


@pytest.fixture
def launcher() -> FakeWorkerLauncher:
    """A launcher that starts nothing.

    Returns:
        The fake.
    """
    return FakeWorkerLauncher()


@pytest.fixture
def watching(test_config: Config) -> Config:
    """The synthetic configuration with the watcher enabled.

    Args:
        test_config: The synthetic configuration.

    Returns:
        A copy with ``watch.enabled``.
    """
    return test_config.model_copy(update={"watch": test_config.watch.model_copy(update={"enabled": True})})


def _supervisor(
    store: AppStore,
    config: Config,
    launcher: FakeWorkerLauncher,
    clock: _Clock,
    *,
    pid: int = 100,
    watcher: FakeWatcherHalf | None = None,
    watcher_service: _ScriptedWatcherService | None = None,
    bus: EventBus | None = None,
    alive: bool = True,
    pid_alive: Callable[[int], bool] | None = None,
    worker_launcher: WorkerLauncher | None = None,
) -> Supervisor:
    """Build a supervisor over the test's store, fakes and clock.

    Args:
        store: The store.
        config: The configuration.
        launcher: The fake launcher.
        clock: The clock.
        pid: Its process id.
        watcher: The fake watcher half, or ``None`` (no torrent client).
        watcher_service: The decision engine, or ``None`` for the real one.
        bus: The event bus.
        alive: What the liveness probe answers for any process id.
        pid_alive: The liveness probe, when it must answer per process id (wins over *alive*).
        worker_launcher: A launcher to use instead of *launcher* (a real one over planted children).

    Returns:
        The supervisor.
    """
    return Supervisor(
        store=store,
        runs=_service(store, config, clock),
        system_actor=lambda: _ADMIN,
        event_bus=bus if bus is not None else EventBus(),
        config=config,
        launcher=worker_launcher if worker_launcher is not None else launcher,
        watcher=watcher,
        watcher_service=watcher_service,
        clock=clock,
        pid=pid,
        host=_HOST,
        pid_alive=pid_alive if pid_alive is not None else (lambda _pid: alive),
    )


def _service(store: AppStore, config: Config, clock: _Clock) -> RunService:
    """The run service over the test's store.

    Args:
        store: The store.
        config: The configuration.
        clock: The clock.

    Returns:
        The service.
    """
    return RunService(store=store, data_dir=config.paths.data_dir, clock=clock)


def _ask(store: AppStore, config: Config, clock: _Clock, options: RunOptions | None = None) -> RunUid:
    """Ask a pipeline run from the web.

    Args:
        store: The store.
        config: The configuration.
        clock: The clock.
        options: The run's options.

    Returns:
        The request's uid.
    """
    return _service(store, config, clock).ask_run(_ADMIN, trigger=RunTrigger.WEB, options=options or RunOptions()).uid


def _state(store: AppStore, uid: RunUid) -> tuple[RequestState, Settlement | None, WaitReason | None]:
    """Read a request's state, settlement and wait reason.

    Args:
        store: The store.
        uid: The request.

    Returns:
        The triple.
    """
    request = store.runs.get(uid)
    assert request is not None
    return request.state, request.settlement, request.wait_reason


def _library(config: Config) -> Path:
    """Migrate the configuration's library store, where ``pipeline_run`` lives.

    Args:
        config: The configuration.

    Returns:
        The library store's path.
    """
    from personalscraper.indexer import migrations
    from personalscraper.indexer.db import apply_migrations, open_db

    db_path = Path(config.indexer.db_path)  # type: ignore[arg-type] — resolved by the config
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_db(db_path, event_bus=EventBus())
    apply_migrations(conn, Path(migrations.__file__).parent)
    conn.commit()
    conn.close()
    return db_path


class TestLease:
    """One supervisor at a time holds the authority to start a run."""

    def test_a_second_supervisor_idles_under_a_live_lease_and_claims_after_expiry(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """B finds A's live lease: it starts nothing; once A stops renewing and the lease lapses, B claims it."""
        first = _supervisor(store, test_config, launcher, clock, pid=100)
        second = _supervisor(store, test_config, launcher, clock, pid=200)
        first.tick_admission()
        uid = _ask(store, test_config, clock)

        with logged_events() as events:
            second.tick_admission()

        assert not second.holds_lease
        assert launcher.started == []
        assert "supervisor.lease_held" in [event["event"] for event in events]

        clock.now += LEASE_TTL_S + 1
        second.tick_admission()

        assert second.holds_lease
        assert launcher.started == [uid]
        lease = store.lease.read()
        assert lease is not None and lease.holder_pid == 200

    def test_the_holder_renews_its_lease_every_tick(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """A tick pushes the expiry a TTL past the tick."""
        supervisor = _supervisor(store, test_config, launcher, clock)
        supervisor.tick_admission()
        clock.now += 30
        supervisor.tick_admission()

        lease = store.lease.read()
        assert lease is not None and lease.expires_at == clock.now + LEASE_TTL_S

    def test_a_holder_that_lost_its_lease_starts_nothing(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """When another took the lease over, the renewal fails, it is logged, and the old holder admits nothing."""
        first = _supervisor(store, test_config, launcher, clock, pid=100)
        first.tick_admission()
        clock.now += LEASE_TTL_S + 1
        _supervisor(store, test_config, launcher, clock, pid=200).tick_admission()
        _ask(store, test_config, clock, _DRY)
        launcher.started.clear()

        with logged_events() as events:
            first.tick_admission()

        assert not first.holds_lease
        assert launcher.started == []
        assert "supervisor.lease_renew_failed" in [event["event"] for event in events]

    def test_a_clean_stop_releases_the_lease(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """``stop`` deletes the lease at once, so the next supervisor need not wait out the TTL."""
        supervisor = _supervisor(store, test_config, launcher, clock)
        supervisor.tick_admission()
        supervisor.stop()

        assert store.lease.read() is None
        assert not supervisor.holds_lease


class TestPidAlive:
    """The liveness probe handed to ``Lease.claimable``."""

    def test_a_process_of_another_user_is_alive(self) -> None:
        """``PermissionError`` from ``os.kill(pid, 0)``: the pid is held by someone else's live process."""
        with patch("personalscraper.app.supervisor.supervisor.os.kill", side_effect=PermissionError(errno.EPERM, "")):
            assert pid_alive(4242) is True

    def test_a_vanished_process_is_gone(self) -> None:
        """``ProcessLookupError``: nothing runs under that pid."""
        with patch("personalscraper.app.supervisor.supervisor.os.kill", side_effect=ProcessLookupError()):
            assert pid_alive(4242) is False

    def test_this_process_is_alive(self) -> None:
        """The probe on our own pid answers alive."""
        assert pid_alive(os.getpid()) is True


class TestAdmission:
    """The head of the queue is started when nothing runs and nothing holds the lock."""

    def test_fifo_one_at_a_time(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """The oldest ask starts first; the next waits ``behind_run`` until the first settles."""
        supervisor = _supervisor(store, test_config, launcher, clock)
        first = _ask(store, test_config, clock)
        clock.now += 1
        second = _ask(store, test_config, clock, _DRY)

        supervisor.tick_admission()

        assert launcher.started == [first]
        assert _state(store, first)[0] is RequestState.RUNNING
        assert _state(store, second) == (RequestState.QUEUED, None, WaitReason.BEHIND_RUN)

        supervisor.tick_admission()
        assert launcher.started == [first], "a second request started while one runs"

        launcher.exit(first, 0)
        supervisor.tick_admission()

        assert _state(store, first)[:2] == (RequestState.SETTLED, Settlement.SUCCESS)
        assert launcher.started == [first, second]

    def test_a_held_pipeline_lock_keeps_the_head_queued(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """A live foreign holder of ``pipeline.lock``: the head stays queued with ``pipeline_lock_held``."""
        lock = test_config.paths.data_dir / "pipeline.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()))
        uid = _ask(store, test_config, clock)

        _supervisor(store, test_config, launcher, clock).tick_admission()

        assert launcher.started == []
        assert _state(store, uid) == (RequestState.QUEUED, None, WaitReason.PIPELINE_LOCK_HELD)

    def test_a_live_scrape_resolve_lock_keeps_the_head_queued(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """A resolve holding its item lock would make the worker back off: the head waits instead."""
        resolves = test_config.paths.data_dir / "locks" / "scrape"
        resolves.mkdir(parents=True, exist_ok=True)
        (resolves / "item.lock").write_text(str(os.getpid()))
        uid = _ask(store, test_config, clock)

        _supervisor(store, test_config, launcher, clock).tick_admission()

        assert launcher.started == []
        assert _state(store, uid) == (RequestState.QUEUED, None, WaitReason.PIPELINE_LOCK_HELD)

    def test_a_pause_keeps_the_head_queued(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """``pipeline.pause`` present: the head stays queued with ``paused``."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        (test_config.paths.data_dir / "pipeline.pause").write_text("")
        uid = _ask(store, test_config, clock)

        _supervisor(store, test_config, launcher, clock).tick_admission()

        assert launcher.started == []
        assert _state(store, uid) == (RequestState.QUEUED, None, WaitReason.PAUSED)

    def test_a_failed_start_settles_the_request_abandoned(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """No worker can ever run (ENOENT): the request is settled ``abandoned``, logged, and the next one may start."""
        uid = _ask(store, test_config, clock)
        launcher.fail_with = OSError(errno.ENOENT, "no interpreter")
        supervisor = _supervisor(store, test_config, launcher, clock)

        with logged_events() as events:
            supervisor.tick_admission()

        assert _state(store, uid)[:2] == (RequestState.SETTLED, Settlement.ABANDONED)
        assert "supervisor.worker_start_failed" in [event["event"] for event in events]

        launcher.fail_with = None
        clock.now += 1
        nxt = _ask(store, test_config, clock)
        supervisor.tick_admission()
        assert launcher.started == [nxt]


class TestSettlement:
    """How a worker's end settles its request."""

    @pytest.mark.parametrize(
        ("code", "settlement"),
        [(0, Settlement.SUCCESS), (1, Settlement.ERROR), (2, Settlement.ERROR), (-15, Settlement.KILLED)],
    )
    def test_the_exit_code_settles_the_request(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        code: int,
        settlement: Settlement,
    ) -> None:
        """0 success, 1 and 2 error, killed by SIGTERM (−15) killed."""
        uid = _ask(store, test_config, clock)
        supervisor = _supervisor(store, test_config, launcher, clock)
        supervisor.tick_admission()
        launcher.exit(uid, code)
        supervisor.tick_admission()

        assert _state(store, uid)[:2] == (RequestState.SETTLED, settlement)

    def test_exit_3_puts_the_request_back_in_the_queue(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """The worker lost ``pipeline.lock``: the request is queued again (``pipeline_lock_held``), then retried."""
        uid = _ask(store, test_config, clock)
        supervisor = _supervisor(store, test_config, launcher, clock)
        supervisor.tick_admission()
        launcher.exit(uid, 3)
        lock = test_config.paths.data_dir / "pipeline.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()))

        with logged_events() as events:
            supervisor.tick_admission()

        assert _state(store, uid) == (RequestState.QUEUED, None, WaitReason.PIPELINE_LOCK_HELD)
        assert "supervisor.worker_lost_lock" in [event["event"] for event in events]

        lock.unlink()
        supervisor.tick_admission()
        assert launcher.started == [uid, uid]
        assert _state(store, uid)[0] is RequestState.RUNNING

    @pytest.mark.parametrize(
        ("outcome", "settlement"),
        [
            ("success", Settlement.SUCCESS),
            ("error", Settlement.ERROR),
            ("killed", Settlement.KILLED),
            ("running", Settlement.INTERRUPTED),
            (None, Settlement.INTERRUPTED),
        ],
    )
    def test_a_stale_heartbeat_settles_from_the_pipeline_run_row_else_interrupted(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        outcome: str | None,
        settlement: Settlement,
    ) -> None:
        """An adopted worker silent for three heartbeats: its run row's outcome, else ``interrupted``."""
        library = _library(test_config)
        uid = _ask(store, test_config, clock)
        _supervisor(store, test_config, launcher, clock, pid=100).tick_admission()
        if outcome is not None:
            writer = PipelineRunWriter(library)
            writer.insert(uid, trigger="web", dry_run=False, pid=4000)
            if outcome != "running":
                writer.finalize(uid, outcome)

        clock.now += LEASE_TTL_S + STALE_AFTER_S + 1
        restarted = _supervisor(store, test_config, FakeWorkerLauncher(first_pid=9000), clock, pid=300)
        restarted.tick_admission()

        assert _state(store, uid)[:2] == (RequestState.SETTLED, settlement)

    def test_the_heartbeat_keeps_an_adopted_request_running(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """A restart adopts a running request whose heartbeat is fresh: no second start, still running."""
        uid = _ask(store, test_config, clock)
        _supervisor(store, test_config, launcher, clock, pid=100).tick_admission()
        clock.now += LEASE_TTL_S + 1
        store.runs.touch_heartbeat(uid, clock.now)
        fresh = FakeWorkerLauncher(first_pid=9000)

        with logged_events() as events:
            _supervisor(store, test_config, fresh, clock, pid=300).tick_admission()

        assert fresh.started == []
        assert _state(store, uid)[0] is RequestState.RUNNING
        adopted = [event for event in events if event["event"] == "supervisor.adopted"]
        assert [event["uid"] for event in adopted] == [uid]


class TestEvents:
    """The supervisor's events reach the bus, in order."""

    def test_queued_admitted_settled_in_order(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """A request is announced once when first seen (``joined=False``), then admitted, then settled."""
        bus = EventBus()
        seen: list[Event] = []
        bus.subscribe(Event, seen.append)
        supervisor = _supervisor(store, test_config, launcher, clock, bus=bus)
        uid = _ask(store, test_config, clock)

        supervisor.tick_admission()
        supervisor.tick_admission()
        launcher.exit(uid, 0)
        supervisor.tick_admission()

        ours = [event for event in seen if isinstance(event, (RunQueued, RunAdmitted, RunSettled))]
        assert [type(event) for event in ours] == [RunQueued, RunAdmitted, RunSettled]
        queued, admitted, settled = ours
        assert isinstance(queued, RunQueued) and queued.uid == uid and queued.joined is False
        assert queued.trigger is RunTrigger.WEB
        assert isinstance(admitted, RunAdmitted) and admitted.uid == uid
        assert isinstance(settled, RunSettled) and settled.settlement is Settlement.SUCCESS


class TestWatcherHalf:
    """The absorbed watcher asks runs through the service instead of spawning them."""

    def test_fire_run_asks_a_run_with_the_decision_reason(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """FIRE_RUN becomes one queued request, triggered by the decision's reason, default options."""
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input()]
        supervisor = _supervisor(
            store, watching, launcher, clock, watcher=watcher, watcher_service=_ScriptedWatcherService(_fire())
        )
        supervisor.tick_admission()
        supervisor.tick_watcher()

        queued = store.runs.queued()
        assert len(queued) == 1
        assert queued[0].trigger is RunTrigger.COMPLETION
        assert queued[0].options == RunOptions()
        assert queued[0].asked_by == _ADMIN.account_id

    def test_fire_run_twice_is_one_request_joined(
        self,
        store: AppStore,
        watching: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """Two FIRE_RUN while the first ask still waits: one request, the second ask joined."""
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input(), _input()]
        supervisor = _supervisor(
            store,
            watching,
            launcher,
            clock,
            watcher=watcher,
            watcher_service=_ScriptedWatcherService(_fire(), _fire("safety_net")),
        )
        supervisor.tick_admission()

        with logged_events() as events:
            supervisor.tick_watcher()
            supervisor.tick_watcher()

        assert len(store.runs.queued()) == 1
        assert "app.runs.joined" in [event["event"] for event in events]

    def test_the_input_reports_the_queue_busy_instead_of_the_lock(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """``pipeline_lock_held`` is « a request is queued or running », whatever the lock file says."""
        lock = watching.paths.data_dir / "pipeline.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()))
        watcher = FakeWatcherHalf()
        watcher.inputs = [dataclasses.replace(_input(), pipeline_lock_held=True), _input()]
        engine = _ScriptedWatcherService()
        supervisor = _supervisor(store, watching, launcher, clock, watcher=watcher, watcher_service=engine)
        supervisor.tick_admission()

        supervisor.tick_watcher()
        _ask(store, watching, clock)
        supervisor.tick_watcher()

        assert [inp.pipeline_lock_held for inp in engine.seen] == [False, True]

    def test_a_disabled_watcher_asks_nothing_and_admission_still_runs(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """``watch.enabled = false``: no poll, no automatic ask; a web ask is still started."""
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input()]
        supervisor = _supervisor(
            store, test_config, launcher, clock, watcher=watcher, watcher_service=_ScriptedWatcherService(_fire())
        )
        supervisor.tick_admission()
        supervisor.tick_watcher()

        assert watcher.polls == 0
        assert store.runs.queued() == ()

        uid = _ask(store, test_config, clock)
        supervisor.tick_admission()
        assert launcher.started == [uid]

    @pytest.mark.parametrize(
        ("torrent_config", "queued"),
        [(SCOPED_TORRENT_CONFIG, 0), (UNSCOPED_TORRENT_CONFIG, 1)],
        ids=["scoped", "unscoped"],
    )
    def test_the_default_engine_is_scoped_by_the_config(
        self,
        store: AppStore,
        watching: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        torrent_config: object,
        queued: int,
    ) -> None:
        """The real engine is built scoped on a scoped config: a boot with no recorded run asks nothing there only."""
        config = watching.model_copy(update={"torrent": torrent_config})
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input()]
        supervisor = _supervisor(store, config, launcher, clock, watcher=watcher)
        supervisor.tick_admission()
        supervisor.tick_watcher()

        assert len(store.runs.queued()) == queued

    def test_no_torrent_client_asks_nothing(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """Without a watcher half (no client), the watcher tick is idle."""
        supervisor = _supervisor(store, watching, launcher, clock, watcher_service=_ScriptedWatcherService(_fire()))
        supervisor.tick_admission()
        supervisor.tick_watcher()

        assert store.runs.queued() == ()

    def test_a_paused_watcher_asks_nothing(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """``watcher.paused`` present: no poll, no automatic ask."""
        watching.paths.data_dir.mkdir(parents=True, exist_ok=True)
        (watching.paths.data_dir / "watcher.paused").write_text("")
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input()]
        supervisor = _supervisor(
            store, watching, launcher, clock, watcher=watcher, watcher_service=_ScriptedWatcherService(_fire())
        )
        supervisor.tick_admission()
        supervisor.tick_watcher()

        assert watcher.polls == 0
        assert store.runs.queued() == ()

    def test_the_watcher_waits_for_the_lease(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """A supervisor without the lease asks nothing (its peer's watcher is the one that runs)."""
        _supervisor(store, watching, launcher, clock, pid=100).tick_admission()
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input()]
        idle = _supervisor(
            store, watching, launcher, clock, pid=200, watcher=watcher, watcher_service=_ScriptedWatcherService(_fire())
        )
        idle.tick_admission()
        idle.tick_watcher()

        assert watcher.polls == 0
        assert store.runs.queued() == ()

    def test_a_manual_fire_consumes_the_sentinel(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """An operator poke (``manual``) eats ``watch.trigger``; an automatic reason never does."""
        sentinel = watching.paths.data_dir / "watch.trigger"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("")
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input(sentinel=True), _input(sentinel=True)]
        supervisor = _supervisor(
            store,
            watching,
            launcher,
            clock,
            watcher=watcher,
            watcher_service=_ScriptedWatcherService(_fire("completion"), _fire("manual")),
        )
        supervisor.tick_admission()

        supervisor.tick_watcher()
        assert sentinel.exists()
        supervisor.tick_watcher()
        assert not sentinel.exists()

    def test_cross_seed_and_pending_run_go_through_the_port(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """FIRE_CROSS_SEED hands the hashes to the port; every polled cycle publishes the pending run."""
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input()]
        decision = WatcherOutput(
            decision=WatcherDecision.FIRE_CROSS_SEED, new_state=WatcherState(), cross_seed_hashes=["h1", "h2"]
        )
        supervisor = _supervisor(
            store, watching, launcher, clock, watcher=watcher, watcher_service=_ScriptedWatcherService(decision)
        )
        supervisor.tick_admission()
        supervisor.tick_watcher()

        assert watcher.cross_seeded == [["h1", "h2"]]
        assert watcher.pending == [(None, 0, 1000.0)]
        assert store.runs.queued() == ()

    def test_a_successful_run_is_recorded_for_the_safety_net(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """A pipeline run settled ``success`` is the watcher's last successful run (stored and in its state)."""
        watcher = FakeWatcherHalf(restored_at=10.0)
        engine = _ScriptedWatcherService()
        supervisor = _supervisor(store, watching, launcher, clock, watcher=watcher, watcher_service=engine)
        uid = _ask(store, watching, clock)
        supervisor.tick_admission()
        clock.now = 1500.0
        launcher.exit(uid, 0)
        supervisor.tick_admission()

        assert watcher.successes == [1500.0]
        watcher.inputs = [_input(1501.0)]
        supervisor.tick_watcher()
        assert supervisor.watcher_state.last_successful_run_at == 1500.0

    def test_the_last_successful_run_is_restored(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """The watcher's state starts from the stored last successful run."""
        supervisor = _supervisor(store, watching, launcher, clock, watcher=FakeWatcherHalf(restored_at=42.0))

        assert supervisor.watcher_state.last_successful_run_at == 42.0


class _Crash(BaseException):
    """The supervisor process dying mid-tick (SIGKILL): nothing after the raise runs."""


def _admitted_by_first_supervisor(
    store: AppStore, config: Config, launcher: FakeWorkerLauncher, clock: _Clock
) -> RunUid:
    """Ask a run and have a first supervisor (pid 100) admit it under worker pid 4000.

    Args:
        store: The store.
        config: The configuration.
        launcher: The first supervisor's launcher.
        clock: The clock.

    Returns:
        The running request's uid.
    """
    uid = _ask(store, config, clock)
    _supervisor(store, config, launcher, clock, pid=100).tick_admission()
    assert launcher.pid_of(uid) == 4000
    return uid


class TestAdmissionOrder:
    """The admission is durable before the worker exists, so a crash never leaves a worker on a queued request."""

    def test_the_request_is_saved_running_before_its_worker_starts(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """At the moment of ``Popen`` the stored request is already ``running``; its pid is recorded after."""
        uid = _ask(store, test_config, clock)
        seen: list[RequestState] = []
        launcher.on_start = lambda started: seen.append(_state(store, started)[0])

        _supervisor(store, test_config, launcher, clock).tick_admission()

        assert seen == [RequestState.RUNNING]
        request = store.runs.get(uid)
        assert request is not None and request.worker_pid == launcher.pid_of(uid)

    def test_a_crash_between_the_admission_and_the_pid_record_never_starts_the_request_twice(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """The supervisor dies after ``Popen``, before the pid is saved: the restart adopts it, then ``interrupted``."""
        uid = _ask(store, test_config, clock)
        real_save = store.runs.save

        def crash_on_pid_record(request: RunRequest) -> bool:
            if request.state is RequestState.RUNNING and request.worker_pid is not None:
                raise _Crash
            return real_save(request)

        with patch.object(store.runs, "save", side_effect=crash_on_pid_record), pytest.raises(_Crash):
            _supervisor(store, test_config, launcher, clock, pid=100).tick_admission()

        assert launcher.started == [uid]
        assert _state(store, uid)[0] is RequestState.RUNNING

        fresh = FakeWorkerLauncher(first_pid=9000)
        clock.now += LEASE_TTL_S + 1
        restarted = _supervisor(store, test_config, fresh, clock, pid=300)
        restarted.tick_admission()
        assert fresh.started == [], "the admitted request was started a second time"
        assert _state(store, uid)[0] is RequestState.RUNNING

        clock.now += STALE_AFTER_S
        restarted.tick_admission()
        assert _state(store, uid)[:2] == (RequestState.SETTLED, Settlement.INTERRUPTED)
        assert fresh.started == []

    def test_an_admission_lost_to_another_writer_starts_nothing(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """The compare-and-set of the admission writes nothing: no worker is started, it is logged."""
        _ask(store, test_config, clock)
        real_save = store.runs.save

        def lose_the_admission(request: RunRequest) -> bool:
            if request.state is RequestState.RUNNING:
                return False
            return real_save(request)

        with patch.object(store.runs, "save", side_effect=lose_the_admission), logged_events() as events:
            _supervisor(store, test_config, launcher, clock).tick_admission()

        assert launcher.started == []
        assert "supervisor.admit_lost" in [event["event"] for event in events]


class TestStartFailures:
    """A start that fails abandons the request at once on a permanent cause, retries a transient one."""

    def test_a_failure_that_is_not_an_os_error_abandons_at_once(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """Any exception from the launcher settles the head ``abandoned``; the queue is not blocked behind it."""
        uid = _ask(store, test_config, clock)
        launcher.fail_with = RuntimeError("bad argv")

        _supervisor(store, test_config, launcher, clock).tick_admission()

        assert _state(store, uid)[:2] == (RequestState.SETTLED, Settlement.ABANDONED)
        request = store.runs.get(uid)
        assert request is not None and (request.worker_pid, request.admitted_at) == (None, None)

    def test_a_transient_errno_keeps_the_head_queued_and_retries(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """EMFILE twice, then the system recovers: the head waited ``worker_start_failed``, then it starts."""
        uid = _ask(store, test_config, clock)
        launcher.fail_with = OSError(errno.EMFILE, "too many open files")
        launcher.fail_times = 2
        supervisor = _supervisor(store, test_config, launcher, clock)

        supervisor.tick_admission()
        state, settlement, reason = _state(store, uid)
        assert (state, settlement) == (RequestState.QUEUED, None)
        assert reason is WaitReason("worker_start_failed")
        supervisor.tick_admission()
        supervisor.tick_admission()

        assert launcher.started == [uid]
        assert _state(store, uid)[0] is RequestState.RUNNING

    def test_a_transient_errno_that_never_recovers_abandons_after_a_bounded_count(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """EAGAIN at every attempt: queued until the last allowed attempt, then ``abandoned``; the next may start."""
        uid = _ask(store, test_config, clock)
        launcher.fail_with = OSError(errno.EAGAIN, "no fork")
        supervisor = _supervisor(store, test_config, launcher, clock)
        attempts = supervisor_module.MAX_WORKER_START_ATTEMPTS

        for _ in range(attempts - 1):
            supervisor.tick_admission()
            assert _state(store, uid)[0] is RequestState.QUEUED
        supervisor.tick_admission()

        assert _state(store, uid)[:2] == (RequestState.SETTLED, Settlement.ABANDONED)
        launcher.fail_with = None
        clock.now += 1
        nxt = _ask(store, test_config, clock)
        supervisor.tick_admission()
        assert launcher.started == [nxt]


class TestAdoptedWorker:
    """A worker of a previous supervisor is judged by its pid as soon as it is gone, not only by its heartbeat."""

    def test_an_adopted_worker_that_lost_the_lock_is_put_back_in_the_queue(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """Gone, no ``pipeline_run`` row, heartbeat never beaten: it exited 3, so its request is queued again."""
        _library(test_config)
        uid = _admitted_by_first_supervisor(store, test_config, launcher, clock)
        lock = test_config.paths.data_dir / "pipeline.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()))
        fresh = FakeWorkerLauncher(first_pid=9000)
        clock.now += LEASE_TTL_S + 1

        with logged_events() as events:
            _supervisor(store, test_config, fresh, clock, pid=300, pid_alive=lambda pid: pid != 4000).tick_admission()

        assert _state(store, uid) == (RequestState.QUEUED, None, WaitReason.PIPELINE_LOCK_HELD)
        assert "supervisor.worker_lost_lock" in [event["event"] for event in events]
        assert fresh.started == []

    def test_a_dead_adopted_worker_is_settled_from_its_row_at_once(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """Gone with a fresh heartbeat: settled from its row on the first tick, without the stale wait."""
        library = _library(test_config)
        uid = _admitted_by_first_supervisor(store, test_config, launcher, clock)
        writer = PipelineRunWriter(library)
        writer.insert(uid, trigger="web", dry_run=False, pid=4000)
        writer.finalize(uid, "success")
        clock.now += LEASE_TTL_S + 1
        store.runs.touch_heartbeat(uid, clock.now)

        restarted = _supervisor(store, test_config, FakeWorkerLauncher(first_pid=9000), clock, pid=300, alive=False)
        restarted.tick_admission()

        assert _state(store, uid)[:2] == (RequestState.SETTLED, Settlement.SUCCESS)

    def test_a_dead_adopted_worker_that_had_beaten_and_left_no_row_is_interrupted(
        self, store: AppStore, test_config: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """Its heartbeat moved, so it held the lock and ran: no requeue, ``interrupted``."""
        _library(test_config)
        uid = _admitted_by_first_supervisor(store, test_config, launcher, clock)
        clock.now += LEASE_TTL_S + 1
        store.runs.touch_heartbeat(uid, clock.now)
        fresh = FakeWorkerLauncher(first_pid=9000)

        _supervisor(store, test_config, fresh, clock, pid=300, alive=False).tick_admission()

        assert _state(store, uid)[:2] == (RequestState.SETTLED, Settlement.INTERRUPTED)
        assert fresh.started == []

    def test_an_unreadable_run_row_is_retried_next_tick(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """A locked ``library.db`` answers « unknown »: the request stays running, and settles once readable."""
        library = _library(test_config)
        uid = _admitted_by_first_supervisor(store, test_config, launcher, clock)
        writer = PipelineRunWriter(library)
        writer.insert(uid, trigger="web", dry_run=False, pid=4000)
        writer.finalize(uid, "success")
        clock.now += LEASE_TTL_S + STALE_AFTER_S + 1
        restarted = _supervisor(store, test_config, FakeWorkerLauncher(first_pid=9000), clock, pid=300)

        locked = IndexUnavailable("database is locked")
        with (
            patch.object(PipelineRunWriter, "outcome", side_effect=locked),
            logged_events() as events,
        ):
            restarted.tick_admission()

        assert _state(store, uid)[0] is RequestState.RUNNING
        assert "supervisor.run_row_unreadable" in [event["event"] for event in events]
        restarted.tick_admission()
        assert _state(store, uid)[:2] == (RequestState.SETTLED, Settlement.SUCCESS)

    def test_a_run_row_that_stays_unreadable_settles_interrupted_after_a_bounded_count(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """A store that never reads again: running for the allowed reads, then ``interrupted``, and the queue moves."""
        _library(test_config)
        uid = _admitted_by_first_supervisor(store, test_config, launcher, clock)
        clock.now += LEASE_TTL_S + STALE_AFTER_S + 1
        fresh = FakeWorkerLauncher(first_pid=9000)
        restarted = _supervisor(store, test_config, fresh, clock, pid=300)
        reads = getattr(supervisor_module, "MAX_UNREADABLE_ROW_READS", 30)

        with (
            patch.object(PipelineRunWriter, "outcome", side_effect=IndexUnavailable("file is not a database")),
            logged_events() as events,
        ):
            for _ in range(reads - 1):
                restarted.tick_admission()
                assert _state(store, uid)[0] is RequestState.RUNNING
            nxt = _ask(store, test_config, clock, _DRY)
            restarted.tick_admission()

        assert _state(store, uid)[:2] == (RequestState.SETTLED, Settlement.INTERRUPTED)
        assert "supervisor.run_row_unreadable_settled" in [event["event"] for event in events]
        assert fresh.started == [nxt]


class TestExitCodeKept:
    """A child's exit code survives a failed save: it is forgotten only once its request left ``running``."""

    def test_a_save_that_raises_keeps_the_exit_code_for_the_next_tick(
        self, store: AppStore, test_config: Config, clock: _Clock
    ) -> None:
        """Exit 3, the requeue's save raises: the next tick still reads 3 and requeues; then the child is reaped."""
        uid = _ask(store, test_config, clock)
        request = store.runs.get(uid)
        assert request is not None
        request.admit(4000, clock.now)
        assert store.runs.save(request)
        real = ProcessWorkerLauncher()
        child = MagicMock(pid=4000)
        child.poll.return_value = 3
        real._children[4000] = child
        lock = test_config.paths.data_dir / "pipeline.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()))
        supervisor = _supervisor(store, test_config, FakeWorkerLauncher(), clock, worker_launcher=real)
        real_save = store.runs.save
        failed: list[RunUid] = []

        def fail_once(saved: RunRequest) -> bool:
            if not failed:
                failed.append(saved.uid)
                raise sqlite3.OperationalError("database is locked")
            return real_save(saved)

        with patch.object(store.runs, "save", side_effect=fail_once), pytest.raises(sqlite3.OperationalError):
            supervisor.tick_admission()
        supervisor.tick_admission()

        assert _state(store, uid) == (RequestState.QUEUED, None, WaitReason.PIPELINE_LOCK_HELD)
        assert 4000 not in real._children


class TestWatcherAskLost:
    """A FIRE_RUN that was not taken leaves the watcher's state as it was before the decision."""

    def test_a_refused_fire_run_leaves_the_state_unchanged(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """The ask is refused (a read-only instance): the debounce window and backoff are not advanced."""
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input()]
        supervisor = _supervisor(
            store, watching, launcher, clock, watcher=watcher, watcher_service=_ScriptedWatcherService(_fire())
        )
        supervisor.tick_admission()
        before = WatcherState(debounce_until=5.0, backoff_multiplier=2, debounce_origin="completion")
        supervisor.watcher_state = dataclasses.replace(before)

        with patch.object(RunService, "ask_run", side_effect=AppForbidden("read-only instance")):
            supervisor.tick_watcher()

        assert supervisor.watcher_state == before
        assert store.runs.queued() == ()

    def test_a_raising_ask_leaves_the_state_unchanged(
        self, store: AppStore, watching: Config, launcher: FakeWorkerLauncher, clock: _Clock
    ) -> None:
        """Any exception from the ask restores the state too, and still reaches the loop's guard."""
        watcher = FakeWatcherHalf()
        watcher.inputs = [_input()]
        supervisor = _supervisor(
            store, watching, launcher, clock, watcher=watcher, watcher_service=_ScriptedWatcherService(_fire())
        )
        supervisor.tick_admission()
        before = WatcherState(debounce_until=5.0, backoff_multiplier=2, debounce_origin="completion")
        supervisor.watcher_state = dataclasses.replace(before)

        with patch.object(RunService, "ask_run", side_effect=RuntimeError("store down")), pytest.raises(RuntimeError):
            supervisor.tick_watcher()

        assert supervisor.watcher_state == before


class _SlowPollWatcher(FakeWatcherHalf):
    """A watcher half whose poll outlasts the lease's TTL (a slow torrent client), then polls nothing."""

    def __init__(self, store: AppStore, clock: _Clock) -> None:
        """Bind the poll to the store and clock it reads.

        Args:
            store: The store holding the lease.
            clock: The clock the poll moves.
        """
        super().__init__()
        self._store = store
        self._clock = clock

    def poll(self) -> WatcherInput | None:
        """Move the clock past the TTL, then wait (bounded, real time) for the lease to be renewed meanwhile.

        Returns:
            ``None``: the cycle is skipped.
        """
        self.polls += 1
        self._clock.now += LEASE_TTL_S + 10
        renewed = threading.Event()
        for _ in range(200):
            lease = self._store.lease.read()
            if lease is not None and lease.expires_at > self._clock.now:
                renewed.set()
                break
            renewed.wait(0.01)
        return None


class TestLeaseDuringTheWatcher:
    """The lease is kept while a watcher tick runs longer than its TTL."""

    def test_a_poll_longer_than_the_ttl_keeps_the_lease(
        self,
        store: AppStore,
        watching: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """While the poll runs past the TTL, the lease is renewed: a second supervisor cannot claim it."""
        monkeypatch.setattr(supervisor_module, "LEASE_KEEP_INTERVAL_S", 0.01, raising=False)
        supervisor = _supervisor(
            store,
            watching,
            launcher,
            clock,
            pid=100,
            watcher=_SlowPollWatcher(store, clock),
            watcher_service=_ScriptedWatcherService(),
        )
        supervisor.tick_admission()

        supervisor.tick_watcher()

        second = _supervisor(store, watching, launcher, clock, pid=200)
        second.tick_admission()
        assert not second.holds_lease
        lease = store.lease.read()
        assert lease is not None and lease.holder_pid == 100
        assert not [thread for thread in threading.enumerate() if thread.name == "supervisor-lease-keeper"]


class TestFailingTicks:
    """A tick that keeps failing stops the loop, so PM2 restarts the process instead of a silent wedge."""

    def test_consecutive_failures_stop_the_loop_non_zero(
        self,
        store: AppStore,
        test_config: Config,
        launcher: FakeWorkerLauncher,
        clock: _Clock,
        logged_events: LoggedEvents,
    ) -> None:
        """N admission ticks failing in a row: an error event, and ``run`` raises (the command exits 1)."""
        supervisor = _supervisor(store, test_config, launcher, clock)
        limit = getattr(supervisor_module, "MAX_CONSECUTIVE_TICK_FAILURES", 30)
        calls = iter(range(3 * limit))

        def wedged() -> None:
            raise ValueError("unparsable run_request row")

        supervisor.tick_admission = wedged  # type: ignore[method-assign]
        with logged_events() as events, pytest.raises(RuntimeError) as raised:
            supervisor.run(lambda: next(calls, None) is None, sleep=lambda _s: None)

        assert type(raised.value).__name__ == "SupervisorWedged"
        assert "supervisor.ticks_failing" in [event["event"] for event in events]

    def test_a_success_resets_the_count(self, store: AppStore, test_config: Config, clock: _Clock) -> None:
        """N−1 failures, a success, N−1 failures: the loop goes on until it is asked to stop."""
        supervisor = _supervisor(store, test_config, FakeWorkerLauncher(), clock)
        limit = getattr(supervisor_module, "MAX_CONSECUTIVE_TICK_FAILURES", 30)
        outcomes = [False] * (limit - 1) + [True] + [False] * (limit - 1)
        ran: list[bool] = []

        def flaky() -> None:
            ok = outcomes[len(ran)]
            ran.append(ok)
            if not ok:
                raise ValueError("transient")

        supervisor.tick_admission = flaky  # type: ignore[method-assign]
        supervisor.run(lambda: len(ran) == len(outcomes), sleep=lambda _s: None)

        assert len(ran) == len(outcomes)
