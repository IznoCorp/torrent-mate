"""Unit tests for the worker: one request, by the uid in its environment, under ``pipeline.lock``.

The bodies are stubs: no pipeline phase and no rescrape runs. A lost race for ``pipeline.lock``
exits 3 and writes no ``pipeline_run`` row; the heartbeat beats while the body runs; the lock is
released whatever the body did.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor import worker
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.launcher import RUN_UID_ENV
from personalscraper.app.supervisor.model import RunKind, RunOptions, RunRequest, RunTrigger
from personalscraper.conf.models.config import Config
from personalscraper.core.identity import ItemId
from personalscraper.lock import is_lock_held


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
def library(test_config: Config) -> Path:
    """Migrate the synthetic config's library store, where ``pipeline_run`` lives.

    Args:
        test_config: The synthetic configuration.

    Returns:
        The library store's path.
    """
    from personalscraper.core.event_bus import EventBus
    from personalscraper.indexer import migrations
    from personalscraper.indexer.db import apply_migrations, open_db

    db_path = Path(test_config.indexer.db_path)  # type: ignore[arg-type] — resolved by the config
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_db(db_path, event_bus=EventBus())
    apply_migrations(conn, Path(migrations.__file__).parent)
    conn.commit()
    conn.close()
    return db_path


def _running(store: AppStore, kind: RunKind = RunKind.PIPELINE, options: RunOptions | None = None) -> RunRequest:
    """Store a request and admit it, as the supervisor would.

    Args:
        store: The store.
        kind: The request's kind.
        options: Its options.

    Returns:
        The running request.
    """
    request = RunRequest.ask(kind, RunTrigger.WEB, options or RunOptions(), AccountId("account-a"), 100.0)
    store.runs.insert(request)
    request.admit(os.getpid(), 100.0)
    store.runs.save(request)
    return request


def _pipeline_rows(db_path: Path) -> list[tuple[object, ...]]:
    """The ``pipeline_run`` rows of the library store.

    Args:
        db_path: The library store.

    Returns:
        The rows' ``run_uid, kind, command, outcome``.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("SELECT run_uid, kind, command, outcome FROM pipeline_run").fetchall()
    finally:
        conn.close()


class TestLock:
    """The worker takes ``pipeline.lock`` exactly as ``run`` does."""

    def test_a_lost_lock_exits_3_and_writes_no_pipeline_run_row(
        self, store: AppStore, test_config: Config, library: Path
    ) -> None:
        """A live holder of ``pipeline.lock`` makes the worker exit 3; no body runs, no row is written."""
        request = _running(store)
        lock = test_config.paths.data_dir / "pipeline.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()))
        ran: list[RunUid] = []

        code = worker.run_request(
            request.uid,
            config=test_config,
            settings=None,  # type: ignore[arg-type] — the stub body never reads it
            store=store,
            bodies=worker.Bodies(pipeline=lambda *_: ran.append(request.uid) or 0, rescrape=lambda *_: 0),
        )

        assert code == worker.LOST_LOCK_EXIT
        assert code == 3
        assert ran == []
        assert _pipeline_rows(library) == []
        assert lock.read_text() == str(os.getpid()), "the foreign holder's lock was touched"

    def test_the_lock_is_held_while_the_body_runs_and_released_after(
        self, store: AppStore, test_config: Config
    ) -> None:
        """The body runs under ``pipeline.lock``, and its exit code is the worker's."""
        request = _running(store)
        lock = test_config.paths.data_dir / "pipeline.lock"
        seen: list[bool] = []

        def body(*_: object) -> int:
            seen.append(is_lock_held(lock))
            return 2

        code = worker.run_request(
            request.uid,
            config=test_config,
            settings=None,  # type: ignore[arg-type]
            store=store,
            bodies=worker.Bodies(pipeline=body, rescrape=lambda *_: 0),
        )

        assert code == 2
        assert seen == [True]
        assert not lock.exists()

    def test_a_body_that_raises_exits_1_and_releases_the_lock(self, store: AppStore, test_config: Config) -> None:
        """An exception out of the body is an error (exit 1), never a lock left behind."""
        request = _running(store)

        def body(*_: object) -> int:
            raise RuntimeError("boom")

        code = worker.run_request(
            request.uid,
            config=test_config,
            settings=None,  # type: ignore[arg-type]
            store=store,
            bodies=worker.Bodies(pipeline=body, rescrape=lambda *_: 0),
        )

        assert code == 1
        assert not (test_config.paths.data_dir / "pipeline.lock").exists()

    def test_a_rescrape_runs_the_rescrape_body_with_its_item(self, store: AppStore, test_config: Config) -> None:
        """A rescrape request runs the rescrape body, handed the request (its item)."""
        request = _running(store, RunKind.RESCRAPE, RunOptions(item_id=ItemId(42)))
        items: list[object] = []

        def rescrape(_config: object, _settings: object, asked: RunRequest) -> int:
            items.append(asked.options.item_id)
            return 0

        code = worker.run_request(
            request.uid,
            config=test_config,
            settings=None,  # type: ignore[arg-type]
            store=store,
            bodies=worker.Bodies(pipeline=lambda *_: 1, rescrape=rescrape),
        )

        assert code == 0
        assert items == [42]

    def test_an_unknown_uid_exits_1_without_the_lock(self, store: AppStore, test_config: Config) -> None:
        """A uid with no request runs nothing and never takes the lock."""
        code = worker.run_request(
            RunUid("f" * 32),
            config=test_config,
            settings=None,  # type: ignore[arg-type]
            store=store,
            bodies=worker.Bodies(pipeline=lambda *_: 0, rescrape=lambda *_: 0),
        )

        assert code == 1
        assert not (test_config.paths.data_dir / "pipeline.lock").exists()


class TestHeartbeat:
    """The worker shows a sign of life while its body runs; the body knows nothing of it."""

    def test_the_heartbeat_is_written_while_the_body_runs(self, store: AppStore, test_config: Config) -> None:
        """With a short interval, the body sees its request's heartbeat move forward."""
        request = _running(store)
        beaten = threading.Event()
        ticks = iter(float(n) for n in range(1000, 2000))

        def body(*_: object) -> int:
            beaten.wait(timeout=5)
            return 0

        def clock() -> float:
            value = next(ticks)
            beaten.set()
            return value

        worker.run_request(
            request.uid,
            config=test_config,
            settings=None,  # type: ignore[arg-type]
            store=store,
            bodies=worker.Bodies(pipeline=body, rescrape=lambda *_: 0),
            heartbeat_interval_s=0.01,
            clock=clock,
        )

        stored = store.runs.get(request.uid)
        assert stored is not None and stored.heartbeat_at is not None
        assert stored.heartbeat_at >= 1000.0


class TestMain:
    """The entry point: the uid comes from the environment, nowhere else."""

    def test_the_uid_is_read_from_the_environment(
        self, store: AppStore, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``main`` runs the request named by ``PERSONALSCRAPER_RUN_UID`` and returns its body's code."""
        request = _running(store)
        monkeypatch.setenv(RUN_UID_ENV, request.uid)
        seen: list[RunUid] = []

        def run_request(uid: RunUid, **_: object) -> int:
            seen.append(uid)
            return 0

        with (
            patch("personalscraper.app.supervisor.worker.load_config", return_value=test_config),
            patch("personalscraper.app.supervisor.worker.get_settings"),
            patch("personalscraper.app.supervisor.worker.configure_logging"),
            patch("personalscraper.app.supervisor.worker.build_app_store", return_value=store),
            patch("personalscraper.app.supervisor.worker.run_request", side_effect=run_request),
        ):
            code = worker.main()

        assert code == 0
        assert seen == [request.uid]

    def test_no_uid_in_the_environment_exits_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A worker started without its uid runs nothing."""
        monkeypatch.delenv(RUN_UID_ENV, raising=False)
        with patch("personalscraper.app.supervisor.worker.load_config") as load:
            assert worker.main() == 1
        load.assert_not_called()


class TestRescrapeRow:
    """A rescrape's ``pipeline_run`` row is the worker's own, under the request's uid."""

    def test_the_row_is_recorded_under_the_request_uid_and_finalized(self, test_config: Config, library: Path) -> None:
        """The row factory inserts a maintenance row under the uid and closes it ``success``."""
        uid = RunUid("b" * 32)
        factory = worker.request_run_row(uid)
        with factory(test_config, "library-rescrape-item") as recorder:
            assert recorder is not None
            recorder.record_counts({"rescraped": 1})

        assert _pipeline_rows(library) == [(uid, "maintenance", "library-rescrape-item", "success")]

    def test_a_failure_inside_finalizes_the_row_error(self, test_config: Config, library: Path) -> None:
        """An exception leaving the row's block records it ``error`` and goes on."""
        uid = RunUid("c" * 32)
        factory = worker.request_run_row(uid)
        with pytest.raises(RuntimeError), factory(test_config, "library-rescrape-item"):
            raise RuntimeError("1")

        assert _pipeline_rows(library) == [(uid, "maintenance", "library-rescrape-item", "error")]
