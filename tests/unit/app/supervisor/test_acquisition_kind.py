"""The acquisition kind: a request of its own lane, coalesced like a run, executed in-process by the worker.

DESIGN O-5 A: the supervisor admits one acquisition request beside the one pipeline request, so a grab
never waits behind a whole run. An equal job queued joins; a running one absorbs nothing. The worker
calls the engine's services with the job's follow (fakes here), never a CLI step, and takes no
``pipeline.lock``.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.errors import AppForbidden, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor import worker
from personalscraper.app.supervisor.acquisition_execution import AcquisitionEngine, AcquisitionUnavailable
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import (
    AcquisitionJob,
    JobKind,
    Lane,
    RequestState,
    RunKind,
    RunOptions,
    RunRequest,
    RunTrigger,
    Settlement,
    WaitReason,
)
from personalscraper.app.supervisor.service import RunService
from personalscraper.app.supervisor.supervisor import Supervisor
from personalscraper.conf.models.config import Config
from personalscraper.core.event_bus import EventBus
from personalscraper.lock import is_lock_held
from tests.unit.app.supervisor.fakes import FakeWorkerLauncher

_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)
_ADMIN = Actor.system(_NO_CEILING, account_id=AccountId("account-admin"), name="admin")
_GRAB_7 = AcquisitionJob(JobKind.GRAB, followed_id=7)


def _ordinary(*rights: Right, ceiling: InstanceCeiling = _NO_CEILING) -> Actor:
    """An ordinary-role actor holding some rights.

    Args:
        *rights: The rights its role carries.
        ceiling: The instance's ceiling.

    Returns:
        The actor.
    """
    return Actor(
        account_id=AccountId("account-a"),
        name="a",
        role_id=RoleId("role-a"),
        role_kind=RoleKind.ORDINARY,
        role_rights=frozenset(rights),
        ceiling=ceiling,
    )


class _Clock:
    """A clock the test moves.

    Attributes:
        now: The epoch it reads.
    """

    def __init__(self) -> None:
        """Start at epoch 1000."""
        self.now = 1000.0

    def __call__(self) -> float:
        """Read it.

        Returns:
            The epoch.
        """
        return self.now


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
def runs(store: AppStore, test_config: Config, clock: _Clock) -> RunService:
    """The run service over the test's store.

    Args:
        store: The store.
        test_config: The synthetic configuration.
        clock: The clock.

    Returns:
        The service.
    """
    return RunService(store=store, data_dir=test_config.paths.data_dir, clock=clock)


@pytest.fixture
def launcher() -> FakeWorkerLauncher:
    """A launcher that starts nothing.

    Returns:
        The fake.
    """
    return FakeWorkerLauncher()


@pytest.fixture
def supervisor(
    store: AppStore, test_config: Config, runs: RunService, launcher: FakeWorkerLauncher, clock: _Clock
) -> Supervisor:
    """A supervisor over the test's store, with no watcher.

    Args:
        store: The store.
        test_config: The synthetic configuration.
        runs: The run service.
        launcher: The fake launcher.
        clock: The clock.

    Returns:
        The supervisor.
    """
    return Supervisor(
        store=store,
        runs=runs,
        system_actor=lambda: _ADMIN,
        event_bus=EventBus(),
        config=test_config,
        launcher=launcher,
        clock=clock,
        pid=100,
        host="host-a",
        pid_alive=lambda _pid: True,
    )


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


class TestTheJob:
    """What an acquisition job is, and what it is not."""

    def test_a_job_round_trips_through_its_canonical_text(self) -> None:
        """The request stores the job as text and reads the same job back."""
        job = AcquisitionJob(JobKind.GRAB, followed_id=7, limit=3, release="Show.S01E01.1080p")
        request = RunRequest.ask(RunKind.ACQUISITION, RunTrigger.WEB, job, AccountId("a"), 1.0)

        assert request.job == job
        assert (
            request.options_json
            == RunRequest.ask(RunKind.ACQUISITION, RunTrigger.CLI, job, AccountId("b"), 2.0).options_json
        )

    def test_a_whole_pass_has_no_follow(self) -> None:
        """A scheduled pass names no follow (DESIGN O-15 B)."""
        assert AcquisitionJob(JobKind.SEARCH).followed_id is None

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"kind": JobKind.PRIME},
            {"kind": JobKind.DETECT, "limit": 2},
            {"kind": JobKind.GRAB, "limit": 0},
            {"kind": JobKind.SEARCH, "followed_id": 1, "release": "x"},
            {"kind": JobKind.GRAB, "release": "x"},
        ],
    )
    def test_a_job_no_pass_can_run_is_refused(self, kwargs: dict[str, object]) -> None:
        """A prime with no follow, a limit on a detect or below 1, a release off a one-follow grab."""
        with pytest.raises(ValueError):
            AcquisitionJob(**kwargs)  # type: ignore[arg-type]

    def test_options_and_job_are_not_interchangeable(self) -> None:
        """A request of one kind refuses the other's payload, and reads only its own."""
        with pytest.raises(ValueError):
            RunRequest.ask(RunKind.ACQUISITION, RunTrigger.WEB, RunOptions(), AccountId("a"), 1.0)
        with pytest.raises(ValueError):
            RunRequest.ask(RunKind.PIPELINE, RunTrigger.WEB, _GRAB_7, AccountId("a"), 1.0)

    def test_the_lane_of_each_kind(self) -> None:
        """The runs and the rescrapes share the pipeline lane; the passes have the other."""
        assert RunKind.PIPELINE.lane is RunKind.RESCRAPE.lane is Lane.PIPELINE
        assert RunKind.ACQUISITION.lane is Lane.ACQUISITION
        assert Lane.ACQUISITION.kinds == (RunKind.ACQUISITION,)


class TestCoalescing:
    """An equal job joins a queued one; a running one absorbs nothing."""

    def test_two_equal_grabs_are_one_request(self, store: AppStore, runs: RunService) -> None:
        """The second ask answers with the first one's uid, joined; one row exists."""
        first = runs.ask_acquisition(_ADMIN, _GRAB_7)
        second = runs.ask_acquisition(_ADMIN, _GRAB_7, trigger=RunTrigger.CLI)

        assert (first.joined, first.state) == (False, "queued")
        assert (second.joined, second.uid) == (True, first.uid)
        assert len(store.runs.queued(Lane.ACQUISITION)) == 1

    def test_jobs_that_differ_are_two_requests(self, store: AppStore, runs: RunService) -> None:
        """Another follow, another pass, a limit or a release is another ask."""
        for job in (
            _GRAB_7,
            AcquisitionJob(JobKind.GRAB, followed_id=8),
            AcquisitionJob(JobKind.GRAB, followed_id=7, limit=2),
            AcquisitionJob(JobKind.GRAB, followed_id=7, release="a"),
            AcquisitionJob(JobKind.SEARCH, followed_id=7),
            AcquisitionJob(JobKind.GRAB),
        ):
            assert not runs.ask_acquisition(_ADMIN, job).joined

        assert len(store.runs.queued(Lane.ACQUISITION)) == 6

    def test_a_running_grab_does_not_absorb_a_new_ask(self, store: AppStore, runs: RunService, clock: _Clock) -> None:
        """What a running pass works on was read when it began: a new ask queues behind it."""
        running = runs.ask_acquisition(_ADMIN, _GRAB_7)
        request = store.runs.get(running.uid)
        assert request is not None
        request.admit(4000, clock())
        store.runs.save(request)

        again = runs.ask_acquisition(_ADMIN, _GRAB_7)

        assert (again.joined, again.state) == (False, "queued")
        assert again.uid != running.uid

    def test_an_acquisition_ask_joins_no_run(self, store: AppStore, runs: RunService) -> None:
        """A pipeline run and an acquisition pass never answer each other."""
        run = runs.ask_run(_ADMIN, trigger=RunTrigger.WEB, options=RunOptions())
        grab = runs.ask_acquisition(_ADMIN, AcquisitionJob(JobKind.DETECT))

        assert not grab.joined
        assert grab.uid != run.uid

    def test_the_view_keeps_the_pipeline_lane_apart(self, runs: RunService) -> None:
        """``running`` and ``queued`` are the pipeline lane's, what the watcher reads; the passes are beside them."""
        run = runs.ask_run(_ADMIN, trigger=RunTrigger.WEB, options=RunOptions())
        grab = runs.ask_acquisition(_ADMIN, _GRAB_7)

        view = runs.queue_view()

        assert [r.uid for r in view.queued] == [run.uid]
        assert [r.uid for r in view.acquisition_queued] == [grab.uid]
        assert view.running is None
        assert view.acquisition_running is None


class TestAuthorisation:
    """The ask needs the rights of the pass's operation, and nothing is written before."""

    def test_a_pilot_may_grab_and_search_but_not_detect(self, store: AppStore, runs: RunService) -> None:
        """``grabForFollow`` and ``searchForFollow`` open on pilot rights; ``runDetection`` asks the pipeline's."""
        pilot = _ordinary(Right.ACQUISITION_PILOT_OWN)

        assert runs.ask_acquisition(pilot, _GRAB_7).state == "queued"
        assert runs.ask_acquisition(pilot, AcquisitionJob(JobKind.SEARCH, followed_id=7)).state == "queued"
        with pytest.raises(AppForbidden) as refused:
            runs.ask_acquisition(pilot, AcquisitionJob(JobKind.DETECT))

        assert refused.value.code is RefusalCode.RIGHT_MISSING
        assert len(store.runs.queued(Lane.ACQUISITION)) == 2

    def test_a_requester_may_prime_the_follow_it_made(self, runs: RunService) -> None:
        """A prime is asked under the rights of the use case that made the follow take work."""
        requester = _ordinary(Right.ACQUISITION_REQUEST)

        assert runs.ask_acquisition(requester, AcquisitionJob(JobKind.PRIME, followed_id=7)).state == "queued"

    def test_an_actor_with_no_right_is_refused_before_any_write(self, store: AppStore, runs: RunService) -> None:
        """No right, no row."""
        with pytest.raises(AppForbidden) as refused:
            runs.ask_acquisition(_ordinary(), _GRAB_7)

        assert refused.value.code is RefusalCode.RIGHT_MISSING
        assert store.runs.queued() == ()

    def test_a_read_only_instance_refuses_every_ask(self, store: AppStore, runs: RunService) -> None:
        """The read-only ceiling refuses the write, for an Admin too."""
        read_only = Actor.system(
            InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True), account_id=AccountId("account-admin"), name="admin"
        )

        with pytest.raises(AppForbidden) as refused:
            runs.ask_acquisition(read_only, _GRAB_7)

        assert refused.value.code is RefusalCode.INSTANCE_READ_ONLY
        assert store.runs.queued() == ()


class TestLanes:
    """The supervisor admits one request per lane."""

    def test_an_acquisition_request_is_admitted_while_a_pipeline_request_runs(
        self, store: AppStore, runs: RunService, supervisor: Supervisor, launcher: FakeWorkerLauncher
    ) -> None:
        """O-5 A: the grab starts beside the run, not behind it."""
        run = runs.ask_run(_ADMIN, trigger=RunTrigger.WEB, options=RunOptions())
        supervisor.tick_admission()
        grab = runs.ask_acquisition(_ADMIN, _GRAB_7)

        supervisor.tick_admission()

        assert launcher.started == [run.uid, grab.uid]
        assert _state(store, run.uid)[0] is RequestState.RUNNING
        assert _state(store, grab.uid) == (RequestState.RUNNING, None, None)

    def test_one_acquisition_request_runs_at_a_time(
        self, store: AppStore, runs: RunService, supervisor: Supervisor, launcher: FakeWorkerLauncher
    ) -> None:
        """A second pass waits behind the first, in its own lane."""
        first = runs.ask_acquisition(_ADMIN, _GRAB_7)
        second = runs.ask_acquisition(_ADMIN, AcquisitionJob(JobKind.SEARCH))

        supervisor.tick_admission()

        assert launcher.started == [first.uid]
        assert _state(store, second.uid) == (RequestState.QUEUED, None, WaitReason.BEHIND_RUN)

    def test_a_running_grab_does_not_hold_the_pipeline_lane(
        self, store: AppStore, runs: RunService, supervisor: Supervisor, launcher: FakeWorkerLauncher
    ) -> None:
        """A run asked while a grab runs starts at once."""
        grab = runs.ask_acquisition(_ADMIN, _GRAB_7)
        supervisor.tick_admission()
        run = runs.ask_run(_ADMIN, trigger=RunTrigger.WEB, options=RunOptions())

        supervisor.tick_admission()

        assert launcher.started == [grab.uid, run.uid]

    def test_the_pipeline_lane_blocks_do_not_reach_the_acquisition_lane(
        self,
        store: AppStore,
        test_config: Config,
        runs: RunService,
        supervisor: Supervisor,
        launcher: FakeWorkerLauncher,
    ) -> None:
        """``pipeline.pause`` and a held ``pipeline.lock`` hold the run, not the grab."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "pipeline.pause").write_text("")
        (data_dir / "pipeline.lock").write_text(str(os.getpid()))
        run = runs.ask_run(_ADMIN, trigger=RunTrigger.WEB, options=RunOptions())
        grab = runs.ask_acquisition(_ADMIN, _GRAB_7)

        supervisor.tick_admission()

        assert launcher.started == [grab.uid]
        assert _state(store, run.uid)[2] is WaitReason.PAUSED

    def test_a_vanished_acquisition_worker_is_settled_never_run_again(
        self, store: AppStore, runs: RunService, supervisor: Supervisor, launcher: FakeWorkerLauncher
    ) -> None:
        """A worker gone before its first beat lost no lock (it takes none): it is ``interrupted``, not requeued."""
        grab = runs.ask_acquisition(_ADMIN, _GRAB_7)
        supervisor.tick_admission()
        supervisor._pid_alive = lambda _pid: False  # the worker's process is gone, and it was not our child

        supervisor.tick_admission()

        assert _state(store, grab.uid) == (RequestState.SETTLED, Settlement.INTERRUPTED, None)


class _Fake:
    """An engine service that records the calls it is handed.

    Attributes:
        calls: ``(name, keyword arguments)`` of each call, in order.
    """

    def __init__(self, calls: list[tuple[str, dict[str, object]]]) -> None:
        """Share the call log.

        Args:
            calls: The log every fake of the engine appends to.
        """
        self.calls = calls

    def run(self, **kwargs: object) -> object:
        """Record a detect or grab call: the ones with a ``series`` are detects.

        Args:
            **kwargs: The call's keywords.

        Returns:
            Nothing of interest.
        """
        self.calls.append(("detect" if "series" in kwargs else "grab", kwargs))
        return object()

    def run_search(self, **kwargs: object) -> object:
        """Record a search call.

        Args:
            **kwargs: The call's keywords.

        Returns:
            Nothing of interest.
        """
        self.calls.append(("search", kwargs))
        return object()


def _engine(calls: list[tuple[str, dict[str, object]]]) -> AcquisitionEngine:
    """An engine of fakes sharing one call log.

    Args:
        calls: The log.

    Returns:
        The engine.
    """
    fake = _Fake(calls)
    return AcquisitionEngine(detect=fake, search=fake, grab=fake)


def _running(store: AppStore, job: AcquisitionJob) -> RunRequest:
    """Store an acquisition request and admit it, as the supervisor would.

    Args:
        store: The store.
        job: The job.

    Returns:
        The running request.
    """
    request = RunRequest.ask(RunKind.ACQUISITION, RunTrigger.WEB, job, AccountId("account-a"), 100.0)
    store.runs.insert(request)
    request.admit(os.getpid(), 100.0)
    store.runs.save(request)
    return request


def _run_worker(
    store: AppStore, config: Config, uid: RunUid, engine: AcquisitionEngine | AcquisitionUnavailable
) -> int:
    """Run the worker on *uid* with the acquisition body over a fake engine.

    Args:
        store: The store.
        config: The configuration.
        uid: The request.
        engine: The engine to open, or the failure opening it raises.

    Returns:
        The worker's exit code.
    """

    @contextmanager
    def opener(*_: object) -> Iterator[AcquisitionEngine]:
        """Open the fake engine.

        Yields:
            The engine.

        Raises:
            AcquisitionUnavailable: When the test planted one.
        """
        if isinstance(engine, AcquisitionUnavailable):
            raise engine
        yield engine

    return worker.run_request(
        uid,
        config=config,
        settings=None,  # type: ignore[arg-type] — the fakes never read it
        store=store,
        bodies=worker.Bodies(
            pipeline=lambda *_: pytest.fail("a pipeline body ran"),
            rescrape=lambda *_: pytest.fail("a rescrape body ran"),
            acquisition=worker.acquisition_body(opener),
        ),
    )


class TestWorker:
    """The worker runs the job in-process through the engine's services."""

    def test_a_grab_calls_the_engine_with_the_jobs_follow_and_never_a_cli_step(
        self, store: AppStore, test_config: Config
    ) -> None:
        """The grab service gets the follow, the limit and the request's uid; no process is spawned."""
        request = _running(store, AcquisitionJob(JobKind.GRAB, followed_id=7, limit=3))
        calls: list[tuple[str, dict[str, object]]] = []

        with patch.object(subprocess, "Popen", side_effect=AssertionError("a CLI step was spawned")) as popen:
            code = _run_worker(store, test_config, request.uid, _engine(calls))

        assert code == 0
        assert calls == [("grab", {"limit": 3, "followed_id": 7, "run_uid": request.uid})]
        popen.assert_not_called()

    def test_a_search_of_the_whole_queue_names_no_follow(self, store: AppStore, test_config: Config) -> None:
        """A scheduled pass carries no follow: the service gets ``None``."""
        request = _running(store, AcquisitionJob(JobKind.SEARCH))
        calls: list[tuple[str, dict[str, object]]] = []

        code = _run_worker(store, test_config, request.uid, _engine(calls))

        assert code == 0
        assert calls == [("search", {"limit": None, "followed_id": None})]

    def test_a_detect_filters_on_the_follow_as_the_command_does(self, store: AppStore, test_config: Config) -> None:
        """``follow detect --series`` takes the follow's id as text; the pass is live."""
        request = _running(store, AcquisitionJob(JobKind.DETECT, followed_id=7))
        calls: list[tuple[str, dict[str, object]]] = []

        code = _run_worker(store, test_config, request.uid, _engine(calls))

        assert code == 0
        [(name, kwargs)] = calls
        assert name == "detect"
        assert kwargs["series"] == "7"
        assert kwargs["dry_run"] is False
        assert isinstance(kwargs["today"], date)
        assert isinstance(kwargs["now"], int)

    def test_a_prime_runs_detect_search_grab_of_its_follow_in_order(self, store: AppStore, test_config: Config) -> None:
        """The amorce of one follow: the v0 runner's three steps, in the process."""
        request = _running(store, AcquisitionJob(JobKind.PRIME, followed_id=7))
        calls: list[tuple[str, dict[str, object]]] = []

        code = _run_worker(store, test_config, request.uid, _engine(calls))

        assert code == 0
        assert [name for name, _ in calls] == ["detect", "search", "grab"]
        assert calls[0][1]["series"] == "7"
        assert calls[1][1]["followed_id"] == 7
        assert calls[2][1]["followed_id"] == 7

    def test_it_takes_no_pipeline_lock_and_leaves_a_foreign_one_alone(
        self, store: AppStore, test_config: Config
    ) -> None:
        """A run holds ``pipeline.lock``; the grab beside it neither loses the race nor touches the file."""
        request = _running(store, _GRAB_7)
        lock = test_config.paths.data_dir / "pipeline.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()))
        calls: list[tuple[str, dict[str, object]]] = []

        code = _run_worker(store, test_config, request.uid, _engine(calls))

        assert code == 0
        assert [name for name, _ in calls] == ["grab"]
        assert is_lock_held(lock)
        assert lock.read_text() == str(os.getpid())

    def test_a_named_release_is_never_replaced_by_the_engines_pick(self, store: AppStore, test_config: Config) -> None:
        """The engine cannot take a named release yet: nothing runs, the request fails."""
        request = _running(store, AcquisitionJob(JobKind.GRAB, followed_id=7, release="Show.S01E01.1080p"))
        calls: list[tuple[str, dict[str, object]]] = []

        code = _run_worker(store, test_config, request.uid, _engine(calls))

        assert code == worker.FAILED_EXIT
        assert calls == []

    def test_an_engine_that_cannot_open_fails_the_request(self, store: AppStore, test_config: Config) -> None:
        """No torrent client, no store: exit 1, as the command's ``Exit(1)``."""
        request = _running(store, _GRAB_7)

        code = _run_worker(store, test_config, request.uid, AcquisitionUnavailable("no torrent client"))

        assert code == worker.FAILED_EXIT

    def test_a_pass_that_raises_fails_the_request(self, store: AppStore, test_config: Config) -> None:
        """An exception out of the service is an exit 1, never an uncaught crash."""
        request = _running(store, _GRAB_7)

        class _Boom:
            """A grab service that raises."""

            def run(self, **_: object) -> object:
                """Raise.

                Raises:
                    RuntimeError: Always.
                """
                raise RuntimeError("tracker down")

        code = _run_worker(store, test_config, request.uid, AcquisitionEngine(grab=_Boom()))

        assert code == worker.FAILED_EXIT

    def test_a_job_that_needs_a_service_the_engine_lacks_fails(self, store: AppStore, test_config: Config) -> None:
        """A grab on an engine with no grab service is an exit 1, not a silent success."""
        request = _running(store, _GRAB_7)

        code = _run_worker(store, test_config, request.uid, AcquisitionEngine())

        assert code == worker.FAILED_EXIT


class _Context:
    """The part of the CLI boundary's application context the engine opener reads.

    Attributes:
        acquire: The acquisition context, or ``None``.
        provider_registry: The metadata registry.
        event_bus: The bus.
    """

    def __init__(self, acquire: object | None) -> None:
        """Hold the acquisition context.

        Args:
            acquire: What ``context.acquire`` answers.
        """
        self.acquire = acquire
        self.provider_registry = object()
        self.event_bus = EventBus()


class _Acquire:
    """The part of the acquisition context the engine opener reads.

    Attributes:
        store: The acquire store, or ``None``.
        ownership: The ownership checker.
        grab: The grab core, or ``None`` without a torrent client.
    """

    def __init__(self, *, grab: object | None) -> None:
        """Build with or without a grab core.

        Args:
            grab: The grab core, or ``None``.
        """
        self.store = object()
        self.ownership = object()
        self.grab = grab


class _GrabCore:
    """A grab core holding the one service that both searches and grabs."""

    service = _Fake([])


class TestOpenEngine:
    """The default opener fills the engine from the CLI boundary, a torrent client only for a grab."""

    @staticmethod
    def _boundary(context: _Context, clients: list[bool]) -> object:
        """A stand-in for ``per_step_boundary`` that records whether a client was asked.

        Args:
            context: The context it yields.
            clients: Receives each ``build_torrent_client`` it is called with.

        Returns:
            The stand-in.
        """

        @contextmanager
        def boundary(_config: object, _settings: object, *, build_torrent_client: bool = False) -> Iterator[_Context]:
            """Open the fake boundary.

            Args:
                _config: Unused.
                _settings: Unused.
                build_torrent_client: Whether a client was asked.

            Yields:
                The context.
            """
            clients.append(build_torrent_client)
            yield context

        return boundary

    def test_a_grab_connects_the_client_and_uses_the_grab_core(self, test_config: Config) -> None:
        """A grab (and a prime) opens the boundary with a client and runs the grab core's service."""
        clients: list[bool] = []
        context = _Context(_Acquire(grab=_GrabCore()))
        with (
            patch("personalscraper.cli_helpers.per_step_boundary", self._boundary(context, clients)),
            worker.open_engine(test_config, None, _GRAB_7) as engine,  # type: ignore[arg-type]
        ):
            assert engine.grab is _GrabCore.service
            assert engine.search is None
            assert engine.detect is None
        assert clients == [True]

    def test_a_prime_gets_all_three_passes(self, test_config: Config) -> None:
        """The amorce of one follow detects, searches and grabs: the engine holds the three services."""
        from personalscraper.acquire.detect import DetectService

        clients: list[bool] = []
        context = _Context(_Acquire(grab=_GrabCore()))
        with (
            patch("personalscraper.cli_helpers.per_step_boundary", self._boundary(context, clients)),
            worker.open_engine(test_config, None, AcquisitionJob(JobKind.PRIME, followed_id=7)) as engine,  # type: ignore[arg-type]
        ):
            assert isinstance(engine.detect, DetectService)
            assert engine.search is _GrabCore.service
            assert engine.grab is _GrabCore.service
        assert clients == [True]

    def test_a_grab_without_a_client_is_unavailable(self, test_config: Config) -> None:
        """No grab core (no torrent client): the pass cannot run."""
        clients: list[bool] = []
        context = _Context(_Acquire(grab=None))
        with (
            patch("personalscraper.cli_helpers.per_step_boundary", self._boundary(context, clients)),
            pytest.raises(AcquisitionUnavailable),
            worker.open_engine(test_config, None, _GRAB_7),  # type: ignore[arg-type]
        ):
            pass

    def test_a_search_builds_its_own_service_and_asks_no_client(self, test_config: Config) -> None:
        """The search pass never contacts the torrent client: it is built as the command builds it."""
        clients: list[bool] = []
        context = _Context(_Acquire(grab=None))
        built = _Fake([])
        with (
            patch("personalscraper.cli_helpers.per_step_boundary", self._boundary(context, clients)),
            patch("personalscraper.acquire.build_search_service", return_value=built) as build,
            worker.open_engine(test_config, None, AcquisitionJob(JobKind.SEARCH)) as engine,  # type: ignore[arg-type]
        ):
            assert engine.search is built
            assert engine.grab is None
        assert clients == [False]
        build.assert_called_once()

    def test_a_detect_builds_the_detect_service_and_asks_no_client(self, test_config: Config) -> None:
        """The detect pass runs the real :class:`DetectService` over the boundary's store."""
        from personalscraper.acquire.detect import DetectService

        clients: list[bool] = []
        context = _Context(_Acquire(grab=None))
        with (
            patch("personalscraper.cli_helpers.per_step_boundary", self._boundary(context, clients)),
            worker.open_engine(test_config, None, AcquisitionJob(JobKind.DETECT)) as engine,  # type: ignore[arg-type]
        ):
            assert isinstance(engine.detect, DetectService)
            assert engine.search is None
            assert engine.grab is None
        assert clients == [False]

    def test_no_acquisition_context_is_unavailable(self, test_config: Config) -> None:
        """A boundary with no acquire store: nothing to run."""
        clients: list[bool] = []
        with (
            patch("personalscraper.cli_helpers.per_step_boundary", self._boundary(_Context(None), clients)),
            pytest.raises(AcquisitionUnavailable),
            worker.open_engine(test_config, None, AcquisitionJob(JobKind.DETECT)),  # type: ignore[arg-type]
        ):
            pass

    def test_the_default_bodies_run_acquisition_through_this_opener(self) -> None:
        """``Bodies()`` carries an acquisition body: a request of that kind is never run by the pipeline body."""
        assert worker.Bodies().acquisition is not worker.Bodies().pipeline
