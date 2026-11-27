"""What the worker keeps around an acquisition pass: what the commands did around the engine call.

The queued path must lose nothing of the direct one: the pass's ``pipeline_run`` row with its counts
(under the request's uid, so a supervisor adopting the worker settles it from there), the ownership
reconcile before a search, the reconcile then the reswitch before a grab, and the Telegram and Redis
subscribers. Each test falls when its behaviour is removed.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from personalscraper.acquire.detect import DetectResult, DetectStatus, DetectSummary
from personalscraper.acquire.reconcile import ReconcileSummary
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor import worker
from personalscraper.app.supervisor.acquisition_execution import AcquisitionEngine
from personalscraper.app.supervisor.model import (
    AcquisitionJob,
    JobKind,
    RequestState,
    RunTrigger,
    Settlement,
)
from personalscraper.app.supervisor.service import RunService
from personalscraper.app.supervisor.supervisor import Supervisor
from personalscraper.conf.models.config import Config
from personalscraper.core.event_bus import EventBus
from tests.fixtures.torrent_scope import SCOPE, SCOPED_TORRENT_CONFIG
from tests.unit.app.supervisor import test_acquisition_kind as kind
from tests.unit.app.supervisor.fakes import FakeWorkerLauncher
from tests.unit.app.supervisor.test_acquisition_kind import (
    _ADMIN,
    _Acquire,
    _Context,
    _Fake,
    _GrabCore,
    _run_worker,
    _running,
)

#: Each job and the ``pipeline_run`` command its pass is recorded under (v0's names).
_JOBS = [
    pytest.param(AcquisitionJob(JobKind.DETECT), "follow-detect", ["follow-detect"], id="detect"),
    pytest.param(AcquisitionJob(JobKind.SEARCH), "search", ["search"], id="search"),
    pytest.param(AcquisitionJob(JobKind.GRAB), "grab", ["grab"], id="grab"),
    pytest.param(
        AcquisitionJob(JobKind.PRIME, followed_id=7), "prime", ["follow-detect", "search", "grab"], id="prime"
    ),
]


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


def _row(config: Config, uid: str) -> dict[str, Any]:
    """The ``pipeline_run`` row of a request.

    Args:
        config: The configuration.
        uid: The request's uid.

    Returns:
        The row, its ``steps_json`` parsed as ``steps``.
    """
    with sqlite3.connect(str(config.indexer.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        found = conn.execute("SELECT * FROM pipeline_run WHERE run_uid = ?", (uid,)).fetchone()
    assert found is not None, "the worker wrote no row"
    row = dict(found)
    row["steps"] = json.loads(row["steps_json"] or "[]")
    return row


def _hooked(order: list[str], fake: _Fake, **extra: Any) -> AcquisitionEngine:
    """An engine whose passes and surroundings all append to one log.

    Args:
        order: The log.
        fake: The fake serving every pass; its calls go to *order* too.
        **extra: Engine fields to override.

    Returns:
        The engine.
    """

    def _before_search() -> ReconcileSummary:
        """Record the reconcile before a search.

        Returns:
            What it settled.
        """
        order.append("before_search")
        return ReconcileSummary(closed_owned=3, fell_back_to_episodes=1)

    def _before_grab() -> ReconcileSummary:
        """Record the reconcile and reswitch before a grab.

        Returns:
            What the reconcile settled.
        """
        order.append("before_grab")
        return ReconcileSummary(closed_owned=2, requeued_missing=4, confirmed_grabbed=5, fell_back_to_episodes=6)

    @contextmanager
    def _listeners() -> Iterator[None]:
        """Record when the grab's subscribers listen.

        Yields:
            Once.
        """
        order.append("listeners_on")
        try:
            yield
        finally:
            order.append("listeners_off")

    fields: dict[str, Any] = {
        "detect": fake,
        "search": fake,
        "grab": fake,
        "before_search": _before_search,
        "before_grab": _before_grab,
        "grab_listeners": _listeners,
    }
    fields.update(extra)
    return AcquisitionEngine(**fields)


class _Logging(_Fake):
    """An engine fake that writes the name of each pass into the shared order log."""

    def __init__(self, order: list[str]) -> None:
        """Log into *order*.

        Args:
            order: The log.
        """
        super().__init__([])
        self.order = order

    def run(self, **kwargs: object) -> Any:
        """Record a detect or grab pass.

        Args:
            **kwargs: The call's keywords.

        Returns:
            The scripted answer.
        """
        self.order.append("detect" if "series" in kwargs else "grab")
        return super().run(**kwargs)

    def run_search(self, **kwargs: object) -> Any:
        """Record a search pass.

        Args:
            **kwargs: The call's keywords.

        Returns:
            The scripted answer.
        """
        self.order.append("search")
        return super().run_search(**kwargs)


class TestTheRow:
    """The worker's row is the pass's ``pipeline_run`` row, as the command's was."""

    @pytest.mark.parametrize(("job", "command", "steps"), _JOBS)
    def test_a_pass_writes_its_row_under_the_requests_uid(
        self, job: AcquisitionJob, command: str, steps: list[str], store: AppStore, test_config: Config
    ) -> None:
        """Kind ``maintenance``, v0's command name, the request's trigger, success, one counts entry per pass."""
        request = _running(store, job)

        assert _run_worker(store, test_config, request.uid, _hooked([], _Fake([]))) == 0

        row = _row(test_config, request.uid)
        assert (row["kind"], row["command"], row["trigger"], row["outcome"]) == (
            "maintenance",
            command,
            RunTrigger.WEB.value,
            "success",
        )
        assert [step["name"] for step in row["steps"]] == steps

    def test_a_commands_request_is_recorded_as_the_commands(self, store: AppStore, test_config: Config) -> None:
        """A pass the CLI asked reads ``cli`` on its row, not the row factory's default ``web``."""
        request = _running(store, AcquisitionJob(JobKind.GRAB), trigger=RunTrigger.CLI)

        assert _run_worker(store, test_config, request.uid, _hooked([], _Fake([]))) == 0

        assert _row(test_config, request.uid)["trigger"] == RunTrigger.CLI.value

    def test_the_counts_of_each_pass_are_the_commands(self, store: AppStore, test_config: Config) -> None:
        """Detect, search and grab carry the numbers their commands recorded, the reconcile's included."""
        fake = _Fake([])
        request = _running(store, AcquisitionJob(JobKind.PRIME, followed_id=7))

        _run_worker(store, test_config, request.uid, _hooked([], fake))

        detect, search, grab = (step["counts"] for step in _row(test_config, request.uid)["steps"])
        assert detect == {
            "detected": 2,
            "enqueued": 2,
            "skipped_owned": 0,
            "skipped_dup": 0,
            "skipped_covered": 0,
            "resurrected": 0,
            "closed_owned": 0,
        }
        assert search == {
            "available": 1,
            "waiting": 0,
            "unverified": 0,
            "abandoned": 0,
            "skipped": 0,
            "absorbed": 0,
            "closed_owned": 3,
            "fell_back_to_episodes": 1,
        }
        assert grab == {
            "grabbed": 1,
            "retried": 0,
            "abandoned": 0,
            "skipped": 0,
            "absorbed": 0,
            "closed_owned": 2,
            "requeued_missing": 4,
            "confirmed_grabbed": 5,
            "fell_back_to_episodes": 6,
        }

    def test_a_detect_that_polled_nothing_records_no_counts(self, store: AppStore, test_config: Config) -> None:
        """``no_active`` / ``no_match`` is a success row with no numbers, as the command's was."""
        fake = _Fake([])
        fake.detected = DetectResult(DetectStatus.NO_ACTIVE, [], DetectSummary())
        request = _running(store, AcquisitionJob(JobKind.DETECT))

        _run_worker(store, test_config, request.uid, _hooked([], fake))

        row = _row(test_config, request.uid)
        assert (row["outcome"], row["steps"]) == ("success", [])

    def test_a_pass_that_exits_non_zero_closes_its_row_in_error(self, store: AppStore, test_config: Config) -> None:
        """A follow the detect cannot find ends the request in error, and its row says so."""
        fake = _Fake([])
        fake.detected = DetectResult(DetectStatus.NO_MATCH, [], DetectSummary())
        request = _running(store, AcquisitionJob(JobKind.DETECT, followed_id=7))

        assert _run_worker(store, test_config, request.uid, _hooked([], fake)) == worker.FAILED_EXIT

        assert _row(test_config, request.uid)["outcome"] == "error"

    def test_a_pass_that_raises_closes_its_row_in_error(self, store: AppStore, test_config: Config) -> None:
        """An exception from the engine is the row's error."""

        def _boom() -> ReconcileSummary:
            """Fail.

            Raises:
                RuntimeError: Always.
            """
            raise RuntimeError("tracker exploded")

        request = _running(store, AcquisitionJob(JobKind.SEARCH))

        code = _run_worker(store, test_config, request.uid, _hooked([], _Fake([]), before_search=_boom))

        assert code == worker.FAILED_EXIT
        row = _row(test_config, request.uid)
        assert (row["outcome"], row["error"]) == ("error", "tracker exploded")

    def test_an_adopted_worker_is_settled_from_its_row(self, store: AppStore, test_config: Config) -> None:
        """A supervisor that finds the finished worker gone settles ``success`` from the row, not ``interrupted``."""
        request = _running(store, AcquisitionJob(JobKind.GRAB))
        assert _run_worker(store, test_config, request.uid, _hooked([], _Fake([]))) == 0
        runs = RunService(store=store, data_dir=test_config.paths.data_dir)
        adopter = Supervisor(
            store=store,
            runs=runs,
            system_actor=lambda: _ADMIN,
            event_bus=EventBus(),
            config=test_config,
            launcher=FakeWorkerLauncher(),
            pid=100,
            host="host-a",
            pid_alive=lambda _pid: False,
        )

        adopter.tick_admission()

        settled = store.runs.get(request.uid)
        assert settled is not None
        assert (settled.state, settled.settlement) == (RequestState.SETTLED, Settlement.SUCCESS)


class TestTheSurroundings:
    """What ran around the engine call in the commands runs around it in the worker."""

    def test_a_search_is_reconciled_first_and_hears_no_grab_listener(
        self, store: AppStore, test_config: Config
    ) -> None:
        """The ownership reconcile precedes the search; the grab's subscribers do not listen."""
        order: list[str] = []
        request = _running(store, AcquisitionJob(JobKind.SEARCH))

        _run_worker(store, test_config, request.uid, _hooked(order, _Logging(order)))

        assert order == ["before_search", "search"]

    def test_a_grab_is_reconciled_and_reswitched_first_under_its_listeners(
        self, store: AppStore, test_config: Config
    ) -> None:
        """The subscribers listen before the reconcile, which emits download events, and until the grab ends."""
        order: list[str] = []
        request = _running(store, AcquisitionJob(JobKind.GRAB))

        _run_worker(store, test_config, request.uid, _hooked(order, _Logging(order)))

        assert order == ["listeners_on", "before_grab", "grab", "listeners_off"]

    def test_a_primes_listeners_hear_its_grab_alone(self, store: AppStore, test_config: Config) -> None:
        """As v0's three processes: only the grab's sent Telegram."""
        order: list[str] = []
        request = _running(store, AcquisitionJob(JobKind.PRIME, followed_id=7))

        _run_worker(store, test_config, request.uid, _hooked(order, _Logging(order)))

        assert order == [
            "detect",
            "before_search",
            "search",
            "listeners_on",
            "before_grab",
            "grab",
            "listeners_off",
        ]


class _Closing:
    """A subscriber or publisher that records its closing.

    Attributes:
        log: Where it records.
        name: Its name in the log.
    """

    def __init__(self, log: list[str], name: str) -> None:
        """Record into *log*.

        Args:
            log: The log.
            name: The name.
        """
        self.log = log
        self.name = name

    def close(self) -> None:
        """Record the closing."""
        self.log.append(f"{self.name}_closed")


#: What each stand-in was handed: its positional and keyword arguments, by recorded name.
_Handed = dict[str, tuple[tuple[object, ...], dict[str, object]]]


@contextmanager
def _opened(
    test_config: Config,
    job: AcquisitionJob,
    order: list[str],
    *,
    context: _Context | None = None,
    settings: object | None = None,
    handed: _Handed | None = None,
    telegram_configured: bool = True,
) -> Iterator[AcquisitionEngine]:
    """The default opener over a fake CLI boundary, its surroundings replaced by recorders.

    Args:
        test_config: The configuration.
        job: The job.
        order: Where the surroundings record.
        context: The boundary's context; a fresh one when ``None``.
        settings: The settings the opener is given.
        handed: Receives what each stand-in is handed, when a test reads it.
        telegram_configured: Whether the Telegram builder answers a subscriber.

    Yields:
        The engine.
    """

    def _recorder(name: str, answer: object) -> Any:
        """A stand-in that records its call.

        Args:
            name: The name recorded.
            answer: What it returns.

        Returns:
            The stand-in.
        """

        def _call(*args: object, **kwargs: object) -> object:
            """Record and answer.

            Args:
                *args: The call's positional arguments.
                **kwargs: The call's keywords.

            Returns:
                The scripted answer.
            """
            order.append(name)
            if handed is not None:
                handed[name] = (args, kwargs)
            return answer

        return _call

    context = context if context is not None else _Context(_Acquire(grab=_GrabCore()))
    subscriber = _Closing(order, "telegram") if telegram_configured else None
    surroundings = "personalscraper.commands.acquisition_surroundings"
    reconciled = ReconcileSummary(closed_owned=1)
    with (
        patch("personalscraper.cli_helpers.per_step_boundary", kind.TestOpenEngine._boundary(context, [])),
        patch("personalscraper.acquire.build_search_service", lambda *_: _Fake([])),
        patch(f"{surroundings}.reconcile_before_search", _recorder("reconcile_before_search", reconciled)),
        patch(f"{surroundings}.reconcile_before_run", _recorder("reconcile_before_run", reconciled)),
        patch(f"{surroundings}.reswitch_before_run", _recorder("reswitch_before_run", None)),
        patch(f"{surroundings}.build_acq_telegram_subscriber", _recorder("telegram_built", subscriber)),
        patch(
            "personalscraper.subscribers.redis_stream.build_redis_publisher",
            _recorder("redis_built", _Closing(order, "redis")),
        ),
        worker.open_engine(test_config, settings, job) as engine,  # type: ignore[arg-type]
    ):
        yield engine


def _assert_same(actual: tuple[object, ...], *expected: object) -> None:
    """Assert that *actual* holds the very objects expected, in order: an equal stand-in is not the same wiring.

    Args:
        actual: What a stand-in was handed.
        *expected: The objects it must be.
    """
    assert len(actual) == len(expected), actual
    for got, wanted in zip(actual, expected, strict=True):
        assert got is wanted, f"handed {got!r}, expected {wanted!r}"


class TestOpenEngineSurroundings:
    """The default opener wires the commands' own surroundings."""

    def test_the_search_reconcile_is_the_commands(self, test_config: Config) -> None:
        """``before_search`` is the search command's ownership sweep."""
        order: list[str] = []
        with _opened(test_config, AcquisitionJob(JobKind.SEARCH), order) as engine:
            assert engine.before_search() == ReconcileSummary(closed_owned=1)

        assert order == ["redis_built", "reconcile_before_search", "redis_closed"]

    def test_the_grab_reconciles_then_reswitches(self, test_config: Config) -> None:
        """``before_grab`` is the grab command's reconcile, then its reswitch, and answers the reconcile."""
        order: list[str] = []
        with _opened(test_config, AcquisitionJob(JobKind.GRAB), order) as engine:
            assert engine.before_grab() == ReconcileSummary(closed_owned=1)

        assert order == ["redis_built", "reconcile_before_run", "reswitch_before_run", "redis_closed"]

    def test_the_grab_listeners_are_telegram_closed_after(self, test_config: Config) -> None:
        """The subscriber is built when the grab's listeners open and closed when they end, even on a failure."""
        order: list[str] = []
        with _opened(test_config, AcquisitionJob(JobKind.GRAB), order) as engine:
            with pytest.raises(RuntimeError), engine.grab_listeners():
                order.append("grabbing")
                raise RuntimeError("grab failed")

        assert order == ["redis_built", "telegram_built", "grabbing", "telegram_closed", "redis_closed"]

    def test_the_redis_publisher_is_closed_when_the_pass_raises(self, test_config: Config) -> None:
        """The publisher streams every event of the pass and is closed whatever happens."""
        order: list[str] = []
        with pytest.raises(RuntimeError), _opened(test_config, AcquisitionJob(JobKind.DETECT), order):
            raise RuntimeError("detect failed")

        assert order == ["redis_built", "redis_closed"]

    def test_a_grab_without_telegram_listens_to_nothing_and_ends_cleanly(self, test_config: Config) -> None:
        """No subscriber is built where Telegram is not configured: the grab runs and nothing is closed for it."""
        order: list[str] = []
        with _opened(test_config, AcquisitionJob(JobKind.GRAB), order, telegram_configured=False) as engine:
            with engine.grab_listeners():
                order.append("grabbing")

        assert order == ["redis_built", "telegram_built", "grabbing", "redis_closed"]

    def test_the_search_reconcile_and_the_publisher_are_on_the_passs_bus(self, test_config: Config) -> None:
        """On another bus the publisher would stream nothing and the sweep's events would be lost."""
        context = _Context(_Acquire(grab=_GrabCore()))
        handed: _Handed = {}
        with _opened(test_config, AcquisitionJob(JobKind.SEARCH), [], context=context, handed=handed) as engine:
            engine.before_search()

        _assert_same(handed["redis_built"][0], context.event_bus, test_config.web)
        _assert_same(handed["reconcile_before_search"][0][:2], context.acquire, context.event_bus)

    def test_the_grabs_reconcile_and_reswitch_are_on_the_passs_bus(self, test_config: Config) -> None:
        """The download and reswitch events of a grab reach the subscribers of its own bus."""
        context = _Context(_Acquire(grab=_GrabCore()))
        handed: _Handed = {}
        with _opened(test_config, AcquisitionJob(JobKind.GRAB), [], context=context, handed=handed) as engine:
            engine.before_grab()

        for name in ("reconcile_before_run", "reswitch_before_run"):
            _assert_same(handed[name][0][:2], context.acquire, context.event_bus)

    def test_telegram_listens_on_the_passs_bus_with_the_workers_settings(self, test_config: Config) -> None:
        """The subscriber is built from the worker's configuration and settings, on the bus the grab emits on."""
        context = _Context(_Acquire(grab=_GrabCore()))
        settings = object()
        handed: _Handed = {}
        with _opened(
            test_config, AcquisitionJob(JobKind.GRAB), [], context=context, settings=settings, handed=handed
        ) as engine:
            with engine.grab_listeners():
                pass

        _assert_same(handed["telegram_built"][0], test_config, settings, context.event_bus)

    def test_the_grab_reconciles_and_reswitches_under_the_instances_torrent_scope(self, test_config: Config) -> None:
        """In a shared client, an unscoped reswitch could delete another instance's torrent."""
        scoped = test_config.model_copy(update={"torrent": SCOPED_TORRENT_CONFIG})
        handed: _Handed = {}
        with _opened(scoped, AcquisitionJob(JobKind.GRAB), [], handed=handed) as engine:
            engine.before_grab()

        for name in ("reconcile_before_run", "reswitch_before_run"):
            assert handed[name][1] == {"scope": SCOPE}, name
