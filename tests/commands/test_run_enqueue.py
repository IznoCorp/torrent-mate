"""``personalscraper run`` under a live supervisor lease: it enqueues the run and follows it.

With a live lease the command starts nothing in its own process: it asks the run through the
in-process service, follows the request the service answered (not necessarily the uid it brought),
prints each step as it closes and exits with the run's code. With no live lease the direct path is
unchanged (``test_pipeline_run_app_context.py`` and its neighbours hold it).
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.app.errors import RefusalCode
from personalscraper.app.store.store import AppStore, build_app_store
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import (
    RequestState,
    RunKind,
    RunOptions,
    RunRequest,
    RunTrigger,
    Settlement,
)
from personalscraper.cli import app
from personalscraper.commands.run_follow import _read_only
from personalscraper.conf.environment import StoreName, store_path
from personalscraper.conf.models.config import Config
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.i18n import t, t_code
from personalscraper.pipeline_history import PipelineRunWriter

runner = CliRunner()

_SLEEP = "personalscraper.commands.run_follow.time.sleep"
_UID_ENV = "PERSONALSCRAPER_RUN_UID"
_BUILD_SERVICES = "personalscraper.commands.run_follow.build_app_services"
_EXECUTE_RUN = "personalscraper.commands.pipeline.execute_run"
_PIPELINE_RUN_DDL = """
CREATE TABLE pipeline_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_uid TEXT UNIQUE NOT NULL, trigger TEXT NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 0, started_at REAL NOT NULL, ended_at REAL, outcome TEXT,
    steps_json TEXT, error TEXT, pid INTEGER, kind TEXT NOT NULL DEFAULT 'pipeline',
    command TEXT NULL, options_json TEXT NULL, output_tail TEXT NULL
)
"""


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
    """The indexer database, holding the ``pipeline_run`` table.

    Args:
        test_config: The synthetic configuration.

    Returns:
        Its path.
    """
    db_path = test_config.indexer.db_path
    assert db_path is not None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.executescript(_PIPELINE_RUN_DDL)
    conn.close()
    return db_path


@pytest.fixture
def pipeline_run() -> Iterator[MagicMock]:
    """``Pipeline.run`` and the lock, patched so a call in this process is caught.

    Yields:
        The ``Pipeline.run`` mock.
    """
    with (
        patch("personalscraper.pipeline.Pipeline.run") as mock_run,
        patch("personalscraper.cli_helpers.acquire_pipeline_lock") as mock_lock,
    ):
        yield mock_run
        mock_lock.assert_not_called()


def _admit(store: AppStore, uid: str) -> None:
    """Move a request to running, as the supervisor does.

    Args:
        store: The store.
        uid: The request.
    """
    request = store.runs.get(RunUid(uid))
    assert request is not None
    request.admit(4242, 2_000.0)
    assert store.runs.save(request)


def _settle(store: AppStore, uid: str, settlement: Settlement) -> None:
    """Settle a running request.

    Args:
        store: The store.
        uid: The request.
        settlement: How it ended.
    """
    request = store.runs.get(RunUid(uid))
    assert request is not None
    request.settle(settlement, 3_000.0)
    assert store.runs.save(request)


def _release(store: AppStore) -> None:
    """Delete the lease, as a supervisor's clean stop does.

    Args:
        store: The store.
    """
    assert store.lease.release(os.getpid(), "host")


def _forget(test_config: Config, uid: str) -> None:
    """Delete a request's row, as if another hand removed it.

    Args:
        test_config: The synthetic configuration.
        uid: The request.
    """
    with sqlite3.connect(str(store_path(test_config.paths.data_dir, StoreName.APP)), isolation_level=None) as conn:
        conn.execute("DELETE FROM run_request WHERE uid = ?", (uid,))


def _script(*moves: Callable[[], None]) -> Callable[[float], None]:
    """A ``time.sleep`` that plays one move per poll, then does nothing.

    Args:
        *moves: What happens during each wait, in order.

    Returns:
        The replacement for ``time.sleep``.
    """
    remaining = list(moves)

    def _sleep(_seconds: float) -> None:
        """Play the next move.

        Args:
            _seconds: The wait asked for, ignored.
        """
        if remaining:
            remaining.pop(0)()

    return _sleep


def _queue_one(store: AppStore, uid: str, *, state: RequestState = RequestState.QUEUED) -> RunRequest:
    """Store a request as another client asked it.

    Args:
        store: The store.
        uid: Its key.
        state: ``queued`` or ``running``.

    Returns:
        The request.
    """
    request = RunRequest.ask(RunKind.PIPELINE, RunTrigger.WEB, RunOptions(), "account-x", 1_000.0, RunUid(uid))
    store.runs.insert(request)
    if state is RequestState.RUNNING:
        _admit(store, uid)
    return request


def _row(db_path: Path, uid: str, steps: tuple[str, ...] = (), outcome: str | None = None) -> None:
    """Write a run's ``pipeline_run`` row as the worker's pipeline does.

    Args:
        db_path: The indexer database.
        uid: The run's uid.
        steps: The step names closed so far, each ``success``.
        outcome: The row's final outcome, or ``None`` while it runs.
    """
    writer = PipelineRunWriter(db_path)
    writer.insert(uid, trigger="cli", dry_run=False, pid=4242, if_absent=True)
    for index, name in enumerate(steps):
        writer.update_step(uid, name, 10.0 + index, 11.0 + index, "success")
    if outcome is not None:
        writer.finalize(uid, outcome)


class TestLiveLeaseEnqueues:
    """A live lease: nothing runs in this process."""

    def test_asks_one_request_under_the_env_uid_and_runs_nothing(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One request is stored under the env uid, its trigger ``cli``; ``Pipeline.run`` is never called."""
        monkeypatch.setenv(_UID_ENV, "promised-uid")
        with patch(
            _SLEEP,
            _script(lambda: _admit(store, "promised-uid"), lambda: _settle(store, "promised-uid", Settlement.SUCCESS)),
        ):
            result = runner.invoke(app, ["run", "--dry-run"])

        assert result.exit_code == 0, result.output
        pipeline_run.assert_not_called()
        stored = store.runs.get(RunUid("promised-uid"))
        assert stored is not None
        assert stored.trigger is RunTrigger.CLI
        assert stored.options.dry_run is True
        assert "promised-uid" in result.output

    def test_trigger_reason_is_the_requests_trigger(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--trigger-reason scrape-resolve`` is stored as that trigger, not widened to ``cli``."""
        monkeypatch.setenv(_UID_ENV, "resolve-uid")
        with patch(
            _SLEEP,
            _script(lambda: _admit(store, "resolve-uid"), lambda: _settle(store, "resolve-uid", Settlement.SUCCESS)),
        ):
            result = runner.invoke(app, ["run", "--trigger-reason", "scrape-resolve"])

        assert result.exit_code == 0, result.output
        stored = store.runs.get(RunUid("resolve-uid"))
        assert stored is not None
        assert stored.trigger is RunTrigger.SCRAPE_RESOLVE

    def test_follows_the_answered_uid_when_the_ask_joined(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A uid-less ask joins the waiting equal request; the follower follows THAT uid and mirrors its end."""
        monkeypatch.delenv(_UID_ENV, raising=False)
        _queue_one(store, "waiting-uid")
        with patch(
            _SLEEP,
            _script(lambda: _admit(store, "waiting-uid"), lambda: _settle(store, "waiting-uid", Settlement.ERROR)),
        ):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 1, result.output
        assert "waiting-uid" in result.output
        assert len(store.runs.queued()) == 0
        pipeline_run.assert_not_called()

    def test_a_promised_uid_already_settled_exits_on_its_settlement_at_once(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The service answers ``idle`` for a settled promised uid: no wait, the exit code of its settlement."""
        monkeypatch.setenv(_UID_ENV, "done-uid")
        _queue_one(store, "done-uid", state=RequestState.RUNNING)
        _settle(store, "done-uid", Settlement.KILLED)
        sleeps: list[float] = []
        with patch(_SLEEP, sleeps.append):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 130, result.output
        assert sleeps == []

    def test_prints_each_step_as_it_closes_and_the_end(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A step is printed once, when ``steps_json`` holds it; the end line follows the settlement."""
        monkeypatch.setenv(_UID_ENV, "steps-uid")

        def _first() -> None:
            _admit(store, "steps-uid")
            _row(library_db, "steps-uid", ("ingest",))

        def _second() -> None:
            _row(library_db, "steps-uid", ("sort",))

        def _end() -> None:
            _row(library_db, "steps-uid", outcome="success")
            _settle(store, "steps-uid", Settlement.SUCCESS)

        with patch(_SLEEP, _script(_first, _second, _end)):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 0, result.output
        out = result.output
        assert out.count(t("cli_core.run.step_done", step="ingest", status="success")) == 1
        assert out.count(t("cli_core.run.step_done", step="sort", status="success")) == 1
        assert out.index("ingest") < out.index("sort")
        assert t("cli_core.run.finished", uid="steps-uid", settlement="success") in out

    def test_a_vanished_request_ends_abandoned(
        self,
        store: AppStore,
        library_db: Path,
        pipeline_run: MagicMock,
        test_config: Config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A request whose row disappears while followed ends on the abandoned line, exit 1."""
        monkeypatch.setenv(_UID_ENV, "gone-uid")
        with patch(_SLEEP, _script(lambda: _forget(test_config, "gone-uid"))):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 1, result.output
        assert t("cli_core.run.finished", uid="gone-uid", settlement="abandoned") in result.output

    def test_the_following_line_is_printed_only_when_following(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A followed run says it is followed; a detached one does not."""
        monkeypatch.setenv(_UID_ENV, "followed-uid")
        with patch(
            _SLEEP,
            _script(lambda: _admit(store, "followed-uid"), lambda: _settle(store, "followed-uid", Settlement.SUCCESS)),
        ):
            followed = runner.invoke(app, ["run"])
        monkeypatch.setenv(_UID_ENV, "left-uid")
        with patch(_SLEEP, lambda _seconds: None):
            detached = runner.invoke(app, ["run", "--detach"])

        assert followed.exit_code == 0, followed.output
        assert t("cli_core.run.following", uid="followed-uid") in followed.output
        assert detached.exit_code == 0, detached.output
        assert t("cli_core.run.queued", uid="left-uid", position=1) in detached.output
        assert t("cli_core.run.following", uid="left-uid") not in detached.output


class TestLeaseLost:
    """The supervisor goes away while a request is followed: the follower stops instead of waiting for ever."""

    @pytest.mark.timeout(20)
    def test_a_queued_request_stays_queued_and_the_exit_is_non_zero(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A clean stop releases the lease: the follower says the run stays queued and exits 1."""
        monkeypatch.setenv(_UID_ENV, "stays-uid")
        with patch(_SLEEP, _script(lambda: _release(store))):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 1, result.output
        assert t("cli_core.run.lease_lost_queued", uid="stays-uid") in " ".join(result.output.split())
        stored = store.runs.get(RunUid("stays-uid"))
        assert stored is not None and stored.state is RequestState.QUEUED

    @pytest.mark.timeout(20)
    def test_a_running_request_is_reported_interrupted(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The lease lapses while the run runs: the follower says it was interrupted and exits 1."""
        monkeypatch.setenv(_UID_ENV, "cut-uid")
        with patch(_SLEEP, _script(lambda: _admit(store, "cut-uid"), lambda: _release(store))):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 1, result.output
        assert t("cli_core.run.lease_lost_running", uid="cut-uid") in " ".join(result.output.split())

    @pytest.mark.timeout(20)
    def test_a_settlement_seen_with_the_lease_gone_still_wins(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A supervisor that settles then stops: the follower reports the settlement, not a lost lease."""
        monkeypatch.setenv(_UID_ENV, "last-uid")

        def _settle_and_stop() -> None:
            _settle(store, "last-uid", Settlement.SUCCESS)
            _release(store)

        with patch(_SLEEP, _script(lambda: _admit(store, "last-uid"), _settle_and_stop)):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 0, result.output
        assert t("cli_core.run.finished", uid="last-uid", settlement="success") in result.output


class TestRefused:
    """The instance refuses the ask."""

    def test_a_read_only_instance_refuses_and_exits_non_zero(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The read-only ceiling refuses the system actor: the refusal text, exit 1, nothing stored."""
        monkeypatch.setenv(_UID_ENV, "refused-uid")
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        result = runner.invoke(app, ["run"])

        assert result.exit_code == 1, result.output
        assert t_code("cli_refusals", RefusalCode.INSTANCE_FORBIDDEN_WRITE) in " ".join(result.output.split())
        assert store.runs.get(RunUid("refused-uid")) is None
        pipeline_run.assert_not_called()


class TestExitCodes:
    """The exit code mirrors the settlement."""

    @pytest.mark.parametrize(
        ("settlement", "code"),
        [
            (Settlement.SUCCESS, 0),
            (Settlement.ERROR, 1),
            (Settlement.KILLED, 130),
            (Settlement.INTERRUPTED, 1),
            (Settlement.ABANDONED, 1),
        ],
    )
    def test_settlement_maps_to_its_code(
        self,
        store: AppStore,
        library_db: Path,
        pipeline_run: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        settlement: Settlement,
        code: int,
    ) -> None:
        """Each settlement exits with its own code."""
        monkeypatch.setenv(_UID_ENV, "code-uid")
        with patch(_SLEEP, _script(lambda: _admit(store, "code-uid"), lambda: _settle(store, "code-uid", settlement))):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == code, result.output

    def test_error_with_a_trailer_abort_row_exits_2(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An ``error`` settlement whose ``pipeline_run`` row closed ``trailers`` in error is the trailer abort: 2."""
        monkeypatch.setenv(_UID_ENV, "abort-uid")

        def _end() -> None:
            writer = PipelineRunWriter(library_db)
            writer.insert("abort-uid", trigger="cli", dry_run=False, pid=4242, if_absent=True)
            writer.update_step("abort-uid", "trailers", 10.0, 11.0, "error")
            writer.finalize("abort-uid", "error")
            _settle(store, "abort-uid", Settlement.ERROR)

        with patch(_SLEEP, _script(lambda: _admit(store, "abort-uid"), _end)):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 2, result.output

    def test_trailer_error_with_continue_flag_is_a_plain_error(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With ``--continue-on-trailer-error`` a failed trailers step does not abort: the run's error is 1."""
        monkeypatch.setenv(_UID_ENV, "cont-uid")

        def _end() -> None:
            writer = PipelineRunWriter(library_db)
            writer.insert("cont-uid", trigger="cli", dry_run=False, pid=4242, if_absent=True)
            writer.update_step("cont-uid", "trailers", 10.0, 11.0, "error")
            writer.finalize("cont-uid", "error")
            _settle(store, "cont-uid", Settlement.ERROR)

        with patch(_SLEEP, _script(lambda: _admit(store, "cont-uid"), _end)):
            result = runner.invoke(app, ["run", "--continue-on-trailer-error"])

        assert result.exit_code == 1, result.output

    def test_trailer_error_with_continue_in_config_is_a_plain_error(
        self,
        store: AppStore,
        library_db: Path,
        pipeline_run: MagicMock,
        test_config: Config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``trailers.pipeline.continue_on_error`` in the config carries on as the flag does: 1, as the direct path."""
        monkeypatch.setenv(_UID_ENV, "conf-uid")
        monkeypatch.setattr(test_config.trailers.pipeline, "continue_on_error", True)

        def _end() -> None:
            writer = PipelineRunWriter(library_db)
            writer.insert("conf-uid", trigger="cli", dry_run=False, pid=4242, if_absent=True)
            writer.update_step("conf-uid", "trailers", 10.0, 11.0, "error")
            writer.finalize("conf-uid", "error")
            _settle(store, "conf-uid", Settlement.ERROR)

        with patch(_SLEEP, _script(lambda: _admit(store, "conf-uid"), _end)):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 1, result.output


class TestDetachAndInterrupt:
    """The follower may leave; the request stays."""

    def test_detach_returns_zero_at_once(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--detach`` enqueues, prints the detached line and never polls."""
        monkeypatch.setenv(_UID_ENV, "detach-uid")
        sleeps: list[float] = []
        with patch(_SLEEP, sleeps.append):
            result = runner.invoke(app, ["run", "--detach"])

        assert result.exit_code == 0, result.output
        assert sleeps == []
        assert t("cli_core.run.detached", uid="detach-uid") in result.output
        stored = store.runs.get(RunUid("detach-uid"))
        assert stored is not None and stored.state is RequestState.QUEUED

    def test_ctrl_c_detaches_and_leaves_the_request(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``KeyboardInterrupt`` while following prints the detached line and leaves the request untouched."""
        monkeypatch.setenv(_UID_ENV, "ctrlc-uid")

        def _interrupt() -> None:
            raise KeyboardInterrupt

        with patch(_SLEEP, _script(lambda: _admit(store, "ctrlc-uid"), _interrupt)):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 0, result.output
        assert t("cli_core.run.detached", uid="ctrlc-uid") in result.output
        stored = store.runs.get(RunUid("ctrlc-uid"))
        assert stored is not None
        assert stored.state is RequestState.RUNNING
        assert stored.settlement is None


class TestInteractiveRefused:
    """``--interactive`` needs the direct path."""

    def test_refused_with_a_live_lease_and_nothing_is_asked(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The refusal line is printed, the exit is 1 and no request is stored."""
        monkeypatch.setenv(_UID_ENV, "inter-uid")
        result = runner.invoke(app, ["run", "--interactive"])

        assert result.exit_code == 1, result.output
        assert t("cli_core.run.interactive_needs_direct") in " ".join(result.output.split())
        assert store.runs.get(RunUid("inter-uid")) is None
        pipeline_run.assert_not_called()

    def test_refused_before_the_services_are_built(
        self, store: AppStore, library_db: Path, pipeline_run: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The refusal needs only the lease: building the services is never reached."""
        monkeypatch.delenv(_UID_ENV, raising=False)
        with patch(_BUILD_SERVICES, side_effect=RuntimeError("services must not be built")) as built:
            result = runner.invoke(app, ["run", "--interactive"])

        assert result.exit_code == 1, result.output
        assert t("cli_core.run.interactive_needs_direct") in " ".join(result.output.split())
        built.assert_not_called()


class TestNoLiveLease:
    """No live lease: today's direct path."""

    def test_an_expired_lease_takes_the_direct_path(self, test_config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
        """A lapsed lease authorises nobody: the run executes in this process and asks nothing."""
        monkeypatch.setenv(_UID_ENV, "direct-uid")
        app_store = build_app_store(test_config)
        try:
            assert app_store.lease.claim(os.getpid(), "host", time.time() - 7200, 60.0, lambda _pid: True) is not None
            with patch("personalscraper.commands.pipeline.execute_run", return_value=0) as executed:
                result = runner.invoke(app, ["run"])
            assert result.exit_code == 0, result.output
            executed.assert_called_once()
            assert app_store.runs.get(RunUid("direct-uid")) is None
        finally:
            app_store.close()

    def test_no_app_db_takes_the_direct_path_without_creating_one(
        self, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no ``app.db`` at all the direct path runs and does not create the file."""
        monkeypatch.delenv(_UID_ENV, raising=False)
        with patch("personalscraper.commands.pipeline.execute_run", return_value=0) as executed:
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 0, result.output
        executed.assert_called_once()
        assert not store_path(test_config.paths.data_dir, StoreName.APP).exists()

    def test_an_app_db_without_a_lease_never_builds_the_services(
        self, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The lease is read on its own: with none, the services are never built and the run goes direct."""
        monkeypatch.delenv(_UID_ENV, raising=False)
        app_store = build_app_store(test_config)
        try:
            assert app_store.lease.read() is None
        finally:
            app_store.close()
        assert store_path(test_config.paths.data_dir, StoreName.APP).exists()
        with (
            patch(_BUILD_SERVICES, side_effect=RuntimeError("services must not be built")) as built,
            patch(_EXECUTE_RUN, return_value=0) as executed,
        ):
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 0, result.output
        executed.assert_called_once()
        built.assert_not_called()

    def test_an_unreadable_app_db_takes_the_direct_path(
        self, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A store that cannot be read while deciding is « no live lease »: the run still goes direct."""
        monkeypatch.delenv(_UID_ENV, raising=False)
        app_db = store_path(test_config.paths.data_dir, StoreName.APP)
        app_db.parent.mkdir(parents=True, exist_ok=True)
        app_db.write_bytes(b"not a database, " * 64)
        with patch(_EXECUTE_RUN, return_value=0) as executed:
            result = runner.invoke(app, ["run"])

        assert result.exit_code == 0, result.output
        executed.assert_called_once()

    def test_detach_says_it_needs_a_supervisor_and_the_run_goes_on(
        self, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--detach`` with no supervisor is not silently dropped: a notice, then the run here."""
        monkeypatch.delenv(_UID_ENV, raising=False)
        with patch(_EXECUTE_RUN, return_value=0) as executed:
            result = runner.invoke(app, ["run", "--detach"])

        assert result.exit_code == 0, result.output
        assert t("cli_core.run.detach_needs_supervisor") in " ".join(result.output.split())
        executed.assert_called_once()


class TestReadOnlyRow:
    """The follower reads the run's row without being able to write it."""

    def test_the_indexer_connection_refuses_a_write(self, library_db: Path) -> None:
        """The connection is opened read-only: a write raises."""
        with _read_only(library_db) as conn, pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE intruder (a INTEGER)")
