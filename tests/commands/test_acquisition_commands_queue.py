"""``follow detect``, ``search`` and ``grab`` under a live supervisor lease: they ask through the queue.

With a live lease the command runs no pass in its own process: it asks one acquisition request through
the in-process service, follows the request the service answered to its settlement and exits with its
code; the worker writes the ``pipeline_run`` row. With no live lease the direct path is unchanged
(``test_grab.py``, ``test_search_command.py`` and ``test_follow_detect.py`` hold it), and ``--dry-run``,
which writes nothing, keeps it whatever the lease.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from personalscraper.acquire.domain import FollowedSeries
from personalscraper.acquire.store import build_acquire_store
from personalscraper.app.errors import RefusalCode
from personalscraper.app.store.store import AppStore, build_app_store
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import (
    AcquisitionJob,
    JobKind,
    Lane,
    RunKind,
    RunRequest,
    RunTrigger,
    Settlement,
)
from personalscraper.cli import app
from personalscraper.conf.environment import StoreName, store_path
from personalscraper.conf.models.config import Config
from personalscraper.core.identity import MediaRef
from personalscraper.i18n import t, t_code
from personalscraper.pipeline_history import PipelineRunWriter

runner = CliRunner()

_SLEEP = "personalscraper.commands.run_follow.time.sleep"
_UID_ENV = "PERSONALSCRAPER_RUN_UID"
_BOUNDARIES = (
    "personalscraper.commands.grab.per_step_boundary",
    "personalscraper.commands.search.per_step_boundary",
    "personalscraper.commands.follow.per_step_boundary",
)

#: Each command, the job it asks and the ``pipeline_run`` command its pass is recorded under.
_COMMANDS = [
    pytest.param(["grab"], JobKind.GRAB, id="grab"),
    pytest.param(["search"], JobKind.SEARCH, id="search"),
    pytest.param(["follow", "detect"], JobKind.DETECT, id="follow-detect"),
]


@pytest.fixture(autouse=True)
def _no_external_uid(monkeypatch: pytest.MonkeyPatch) -> None:
    """No caller promised a run uid, and no instance role restricts the ask.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.delenv(_UID_ENV, raising=False)
    monkeypatch.delenv("PM2_HOME", raising=False)


@pytest.fixture
def store(test_config: Config) -> Iterator[AppStore]:
    """The environment's ``app.db`` with a live supervisor lease.

    Args:
        test_config: The synthetic configuration.

    Yields:
        The store.
    """
    app_store = build_app_store(test_config)
    claimed = app_store.lease.claim(os.getpid(), "host", time.time(), 3600.0, lambda _pid: True)
    assert claimed is not None
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def library_db(test_config: Config) -> Path:
    """The path of the indexer database, which holds the ``pipeline_run`` table once a writer ensured it.

    Args:
        test_config: The synthetic configuration.

    Returns:
        Its path.
    """
    db_path = test_config.indexer.db_path
    assert db_path is not None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # A first write brings the file to the current schema.
    PipelineRunWriter(db_path).insert("seed-row", trigger="cli", dry_run=False, pid=1, if_absent=True)
    return db_path


@pytest.fixture(autouse=True)
def no_direct_pass() -> Iterator[list[str]]:
    """Every command's boundary, replaced by one that records that the direct path was taken, and stops there.

    Yields:
        The boundaries entered, by their patch target.
    """
    entered: list[str] = []

    def _boundary_of(target: str) -> Callable[..., object]:
        """A boundary that records *target* and refuses to open.

        Args:
            target: The patched name.

        Returns:
            The stand-in.
        """

        @contextmanager
        def boundary(*_args: object, **_kwargs: object) -> Iterator[None]:
            """Record the entry and stop the command.

            Yields:
                Never: it raises first.

            Raises:
                _DirectPath: Always.
            """
            entered.append(target)
            raise _DirectPath
            yield None

        return boundary

    patches = [patch(target, _boundary_of(target)) for target in _BOUNDARIES]
    for started in patches:
        started.start()
    try:
        yield entered
    finally:
        for started in patches:
            started.stop()


class _DirectPath(Exception):
    """The command opened its own boundary: it runs its pass in this process."""


def _requests(config: Config) -> list[RunRequest]:
    """Every request stored, oldest first.

    Args:
        config: The synthetic configuration.

    Returns:
        The requests.
    """
    app_db = store_path(config.paths.data_dir, StoreName.APP)
    with sqlite3.connect(str(app_db)) as conn:
        uids = [row[0] for row in conn.execute("SELECT uid FROM run_request ORDER BY asked_at, rowid")]
    reader = build_app_store(config)
    try:
        found = [reader.runs.get(RunUid(uid)) for uid in uids]
    finally:
        reader.close()
    return [request for request in found if request is not None]


def _settle_all(store: AppStore, *settlements: Settlement) -> Callable[[float], None]:
    """A ``time.sleep`` that, at each wait, runs and settles the oldest queued acquisition request.

    Args:
        store: The store.
        *settlements: How each request ends, in the queue's order; the last one repeats.

    Returns:
        The replacement for ``time.sleep``.
    """
    remaining = list(settlements)

    def _sleep(_seconds: float) -> None:
        """Settle the oldest queued request.

        Args:
            _seconds: The wait asked for, ignored.
        """
        queued = store.runs.queued(Lane.ACQUISITION)
        if not queued:
            return
        request = queued[0]
        request.admit(4242, 2_000.0)
        assert store.runs.save(request)
        request.settle(remaining.pop(0) if len(remaining) > 1 else remaining[0], 3_000.0)
        assert store.runs.save(request)

    return _sleep


def _rows(db_path: Path) -> list[tuple[str, str | None, str | None, str | None]]:
    """The ``pipeline_run`` rows written besides the seed one.

    Args:
        db_path: The indexer database.

    Returns:
        ``(run_uid, command, outcome, steps_json)`` of each.
    """
    with sqlite3.connect(str(db_path)) as conn:
        return conn.execute(
            "SELECT run_uid, command, outcome, steps_json FROM pipeline_run WHERE run_uid != 'seed-row' ORDER BY id"
        ).fetchall()


def _follow(config: Config, title: str, tvdb_id: int, *, active: bool = True) -> int:
    """Store a follow in ``acquire.db``.

    Args:
        config: The synthetic configuration.
        title: Its title.
        tvdb_id: Its provider id.
        active: Whether it is at work.

    Returns:
        Its ``followed_id``.
    """
    acquire = build_acquire_store(config.acquire)
    try:
        return acquire.follow.add(
            FollowedSeries(media_ref=MediaRef(tvdb_id=tvdb_id), title=title, added_at=1_000_000, active=active)
        )
    finally:
        acquire.close()


def _line(result_output: str) -> str:
    """The output with its wrapping undone.

    Args:
        result_output: The command's output.

    Returns:
        One line.
    """
    return " ".join(result_output.split())


class TestLiveLeaseAsks:
    """A live lease: one request in the queue, no pass in this process."""

    @pytest.mark.parametrize(("argv", "kind"), _COMMANDS)
    def test_asks_one_acquisition_request_and_runs_no_pass(
        self,
        argv: list[str],
        kind: JobKind,
        test_config: Config,
        store: AppStore,
        library_db: Path,
        no_direct_pass: list[str],
    ) -> None:
        """One request: kind ``acquisition``, the command's job, trigger ``cli``; exit 0 once it succeeds."""
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS)):
            result = runner.invoke(app, argv)

        assert result.exit_code == 0, result.output
        assert no_direct_pass == []
        [request] = _requests(test_config)
        assert request.kind is RunKind.ACQUISITION
        assert request.job == AcquisitionJob(kind)
        assert request.trigger is RunTrigger.CLI
        assert t("cli_core.run.queued", uid=request.uid, position=1) in _line(result.output)

    @pytest.mark.parametrize(("argv", "kind"), _COMMANDS)
    def test_writes_no_row_of_its_own(self, argv: list[str], kind: JobKind, store: AppStore, library_db: Path) -> None:
        """The worker's row is the only one of the pass: the queued command adds none."""
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS)):
            result = runner.invoke(app, argv)

        assert result.exit_code == 0, result.output
        assert _rows(library_db) == []

    @pytest.mark.parametrize(("argv", "kind"), _COMMANDS[:2])
    def test_carries_the_follow_and_the_limit(
        self, argv: list[str], kind: JobKind, test_config: Config, store: AppStore, library_db: Path
    ) -> None:
        """``--followed-id`` and ``--limit`` are the job's."""
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS)):
            result = runner.invoke(app, [*argv, "--followed-id", "7", "--limit", "3"])

        assert result.exit_code == 0, result.output
        [request] = _requests(test_config)
        assert request.job == AcquisitionJob(kind, followed_id=7, limit=3)

    def test_a_second_grab_while_one_is_queued_joins_it(
        self, test_config: Config, store: AppStore, library_db: Path
    ) -> None:
        """An equal job waiting answers the ask: still one request, the joined uid followed."""
        waiting = RunRequest.ask(
            RunKind.ACQUISITION, RunTrigger.WEB, AcquisitionJob(JobKind.GRAB), "account-x", 1_000.0, RunUid("waiting")
        )
        store.runs.insert(waiting)
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS)):
            result = runner.invoke(app, ["grab"])

        assert result.exit_code == 0, result.output
        assert [request.uid for request in _requests(test_config)] == ["waiting"]
        assert t("cli_core.run.joined", uid="waiting") in _line(result.output)

    @pytest.mark.parametrize(
        ("settlement", "code"),
        [(Settlement.ERROR, 1), (Settlement.KILLED, 130), (Settlement.INTERRUPTED, 1)],
    )
    def test_exits_with_the_passes_code(
        self,
        settlement: Settlement,
        code: int,
        test_config: Config,
        store: AppStore,
        library_db: Path,
        no_direct_pass: list[str],
    ) -> None:
        """The command's exit code is the settled request's."""
        with patch(_SLEEP, _settle_all(store, settlement)):
            result = runner.invoke(app, ["search"])

        assert result.exit_code == code, result.output
        assert no_direct_pass == []
        assert [request.settlement for request in _requests(test_config)] == [settlement]

    @pytest.mark.parametrize(("argv", "kind"), _COMMANDS[:2])
    @pytest.mark.parametrize("limit", ["0", "-2"])
    def test_a_limit_below_one_is_refused_and_nothing_is_asked(
        self, argv: list[str], kind: JobKind, limit: str, test_config: Config, store: AppStore, library_db: Path
    ) -> None:
        """No job takes a cap below 1: the command says so and exits 2."""
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS)):
            result = runner.invoke(app, [*argv, "--limit", limit])

        assert result.exit_code == 2, result.output
        assert t("cli_acquisition.queue.limit_too_low") in _line(result.output)
        assert _requests(test_config) == []

    def test_a_read_only_instance_refuses_and_nothing_is_asked(
        self,
        test_config: Config,
        store: AppStore,
        library_db: Path,
        no_direct_pass: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The read-only clone refuses the system actor, as it does for ``run``."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        result = runner.invoke(app, ["grab"])

        assert result.exit_code == 1, result.output
        assert t_code("cli_refusals", RefusalCode.INSTANCE_READ_ONLY) in _line(result.output)
        assert _requests(test_config) == []
        assert no_direct_pass == []


class TestSeries:
    """``follow detect --series`` is resolved to its follow rows before it is asked."""

    def test_a_title_substring_asks_the_detect_of_that_follow(
        self, test_config: Config, store: AppStore, library_db: Path
    ) -> None:
        """The title filter, case-insensitive, names one follow: its id is the job's."""
        _follow(test_config, "Other Show", 1)
        wanted = _follow(test_config, "The Long Voyage", 2)
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS)):
            result = runner.invoke(app, ["follow", "detect", "--series", "long voy"])

        assert result.exit_code == 0, result.output
        [request] = _requests(test_config)
        assert request.job == AcquisitionJob(JobKind.DETECT, followed_id=wanted)

    def test_an_integer_is_a_followed_id(self, test_config: Config, store: AppStore, library_db: Path) -> None:
        """A number names the follow by its row, never by its title."""
        first = _follow(test_config, "Show 2", 1)
        _follow(test_config, "Other", 2)
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS)):
            result = runner.invoke(app, ["follow", "detect", "--series", str(first)])

        assert result.exit_code == 0, result.output
        [request] = _requests(test_config)
        assert request.job == AcquisitionJob(JobKind.DETECT, followed_id=first)

    def test_several_matches_ask_one_detect_each_and_exit_on_the_first_failure(
        self, test_config: Config, store: AppStore, library_db: Path
    ) -> None:
        """The direct path processes every match: one request per follow, the first non-zero code returned."""
        ids = [_follow(test_config, f"Voyage {n}", n) for n in (1, 2, 3)]
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS, Settlement.KILLED, Settlement.ERROR)):
            result = runner.invoke(app, ["follow", "detect", "--series", "voyage"])

        assert result.exit_code == 130, result.output
        assert [request.job.followed_id for request in _requests(test_config)] == ids

    def test_a_one_off_request_is_matched_too(self, test_config: Config, store: AppStore, library_db: Path) -> None:
        """A one-off request is polled by the detect pass: ``--series`` reaches it as the direct path does."""
        followed_id = _follow(test_config, "One Off", 5)
        with sqlite3.connect(str(test_config.acquire.db_path)) as conn:
            conn.execute("UPDATE followed_series SET scope = 'request' WHERE id = ?", (followed_id,))
        with patch(_SLEEP, _settle_all(store, Settlement.SUCCESS)):
            result = runner.invoke(app, ["follow", "detect", "--series", "one off"])

        assert result.exit_code == 0, result.output
        [request] = _requests(test_config)
        assert request.job.followed_id == followed_id

    @pytest.mark.parametrize(
        ("followed", "key"),
        [
            pytest.param(True, "cli_acquisition.follow.detect.no_match", id="no-match"),
            pytest.param(False, "cli_acquisition.follow.detect.no_active", id="no-active"),
        ],
    )
    def test_nothing_matched_says_so_asks_nothing_and_records_the_run(
        self,
        followed: bool,
        key: str,
        test_config: Config,
        store: AppStore,
        library_db: Path,
        no_direct_pass: list[str],
    ) -> None:
        """No follow to ask for: the direct path's line, exit 0 and its success row."""
        if followed:
            _follow(test_config, "Other Show", 1)
        result = runner.invoke(app, ["follow", "detect", "--series", "voyage"])

        assert result.exit_code == 0, result.output
        assert t(key) in _line(result.output)
        assert _requests(test_config) == []
        assert no_direct_pass == []
        assert [(command, outcome) for _, command, outcome, _ in _rows(library_db)] == [("follow-detect", "success")]

    def test_ctrl_c_detaches_from_every_request(self, test_config: Config, store: AppStore, library_db: Path) -> None:
        """Ctrl-C leaves all the asked requests to the supervisor and names each; exit 0."""
        for n in (1, 2):
            _follow(test_config, f"Voyage {n}", n)

        def _interrupt(_seconds: float) -> None:
            """Press Ctrl-C at the first wait.

            Args:
                _seconds: The wait asked for, ignored.

            Raises:
                KeyboardInterrupt: Always.
            """
            raise KeyboardInterrupt

        with patch(_SLEEP, _interrupt):
            result = runner.invoke(app, ["follow", "detect", "--series", "voyage"])

        assert result.exit_code == 0, result.output
        asked = _requests(test_config)
        assert len(asked) == 2
        for request in asked:
            assert t("cli_core.run.detached", uid=request.uid) in _line(result.output)


class TestExternalRunUid:
    """A spawner that promised a run uid owns that row: the command copies the worker's counts onto it."""

    @pytest.mark.parametrize(("argv", "kind"), _COMMANDS)
    def test_asks_under_a_fresh_uid_and_copies_the_workers_counts(
        self,
        argv: list[str],
        kind: JobKind,
        test_config: Config,
        store: AppStore,
        library_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The request never takes the promised uid; the external row gets the pass's counts."""
        monkeypatch.setenv(_UID_ENV, "external-uid")
        writer = PipelineRunWriter(library_db)
        writer.insert("external-uid", trigger="web", dry_run=False, pid=1, kind="maintenance", command="prime")
        settle = _settle_all(store, Settlement.SUCCESS)

        def _worker_then_settle(seconds: float) -> None:
            """Write the worker's row of the queued request, then settle it.

            Args:
                seconds: The wait asked for.
            """
            [queued] = store.runs.queued(Lane.ACQUISITION)
            writer.insert(queued.uid, trigger="cli", dry_run=False, pid=2, kind="maintenance", command="pass")
            writer.update_step(queued.uid, "pass", 1.0, 2.0, "success", counts={"skipped": 4})
            writer.finalize(queued.uid, "success")
            settle(seconds)

        with patch(_SLEEP, _worker_then_settle):
            result = runner.invoke(app, argv)

        assert result.exit_code == 0, result.output
        [request] = _requests(test_config)
        assert request.uid != "external-uid"
        external = next(row for row in _rows(library_db) if row[0] == "external-uid")
        assert external[2] == "running"  # its owner finalizes it
        assert [step["counts"] for step in json.loads(external[3] or "[]")] == [{"skipped": 4}]


class TestNoQueue:
    """When the queue is not the path."""

    @pytest.mark.parametrize(("argv", "kind"), _COMMANDS)
    def test_with_no_lease_the_direct_path_runs(
        self, argv: list[str], kind: JobKind, no_direct_pass: list[str], library_db: Path
    ) -> None:
        """No supervisor ever ran here: the command opens its own boundary."""
        result = runner.invoke(app, argv)

        assert isinstance(result.exception, _DirectPath), result.output
        assert len(no_direct_pass) == 1

    @pytest.mark.parametrize(("argv", "kind"), _COMMANDS)
    def test_dry_run_keeps_the_direct_path_under_a_live_lease(
        self,
        argv: list[str],
        kind: JobKind,
        test_config: Config,
        store: AppStore,
        library_db: Path,
        no_direct_pass: list[str],
    ) -> None:
        """A preview writes nothing, so it is never queued."""
        result = runner.invoke(app, [*argv, "--dry-run"])

        assert isinstance(result.exception, _DirectPath), result.output
        assert len(no_direct_pass) == 1
        assert _requests(test_config) == []

    @pytest.mark.parametrize(("argv", "kind"), _COMMANDS)
    def test_an_unreadable_app_db_refuses_and_runs_nothing(
        self, argv: list[str], kind: JobKind, test_config: Config, no_direct_pass: list[str], library_db: Path
    ) -> None:
        """The lease alone authorises a pass: an unreadable store is exit 1, the file left in place."""
        app_db = store_path(test_config.paths.data_dir, StoreName.APP)
        app_db.parent.mkdir(parents=True, exist_ok=True)
        garbage = b"not a database, " * 64
        app_db.write_bytes(garbage)

        result = runner.invoke(app, argv)

        assert result.exit_code == 1, result.output
        assert t("cli_core.run.supervisor_state_unreadable") in _line(result.output)
        assert no_direct_pass == []
        assert app_db.read_bytes() == garbage
        assert _rows(library_db) == []
