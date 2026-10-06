"""The worker: one asked run or rescrape, in a process of its own (``python -m``).

The supervisor starts it detached, with the request's uid in ``PERSONALSCRAPER_RUN_UID`` and nothing
in its argv. It takes ``pipeline.lock`` exactly as ``personalscraper run`` does, so a run stays
excluded from every foreign holder of the lock and v0's readers of the file see the worker's pid.
A lost race exits :data:`LOST_LOCK_EXIT` before anything is written (no ``pipeline_run`` row): the
supervisor puts the request back in the queue.

Under the lock it runs today's body, unchanged: a pipeline run (:func:`execute_run`, the
``--no-console`` semantics) or the rescrape of one item (:func:`rescrape_item`). A heartbeat thread
writes the request's ``heartbeat_at`` meanwhile; the body knows nothing of it. The worker only
exits: settling the request from its exit code is the supervisor's job.

The uid is also the ``pipeline_run`` row's: the pipeline reads it from the same variable, and a
rescrape records its maintenance row under it (:func:`request_run_row`), so a supervisor that
adopts a silent worker can settle it from that row.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Final

from personalscraper.app.store.store import AppStore, build_app_store
from personalscraper.app.supervisor.execution import RunRecorder, RunRowFactory, execute_run, rescrape_item
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.launcher import LOST_LOCK_EXIT, RUN_UID_ENV
from personalscraper.app.supervisor.model import HEARTBEAT_INTERVAL_S, RequestState, RunKind, RunRequest, RunTrigger
from personalscraper.conf.loader import load_config
from personalscraper.config import get_settings
from personalscraper.lock import acquire_pipeline_lock, release_lock, scrape_locks_dir_for
from personalscraper.logger import configure_logging, get_logger
from personalscraper.pipeline_history import PipelineRunWriter

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings

log = get_logger("app.supervisor.worker")

#: The exit code of a worker that could not run its request (no uid, no request, a request that is
#: not running, a body that raised).
FAILED_EXIT: Final = 1

#: A body: runs one request under the lock and returns its exit code.
Body = Callable[["Config", "Settings", RunRequest], int]

#: The ``pipeline_run`` command a rescrape is recorded under, as the CLI command always was.
RESCRAPE_COMMAND: Final = "library-rescrape-item"


def _run_pipeline(config: Config, settings: Settings, request: RunRequest) -> int:
    """Run today's pipeline body for *request*, printing nothing (the ``--no-console`` semantics).

    Args:
        config: Loaded configuration.
        settings: Loaded settings.
        request: The request; its options are the run's flags.

    Returns:
        The run's exit code.
    """
    # A plain CLI run carries no trigger reason (its row reads ``cli``); every other trigger is one.
    trigger = "" if request.trigger is RunTrigger.CLI else request.trigger.value
    return execute_run(config, settings, request.options, trigger=trigger, console=None, verbose=False, no_console=True)


def _run_rescrape(config: Config, settings: Settings, request: RunRequest) -> int:
    """Run today's rescrape body for *request*'s item, its row recorded under the request's uid.

    Args:
        config: Loaded configuration.
        settings: Loaded settings.
        request: The request; its options carry the item.

    Returns:
        The rescrape's exit code; 1 when the request names no item or the index is missing.
    """
    from rich.console import Console  # noqa: PLC0415

    from personalscraper.cli_helpers import per_step_boundary  # noqa: PLC0415

    item_id = request.options.item_id
    db_path = config.indexer.db_path
    if item_id is None or db_path is None or not Path(db_path).exists():
        log.error("worker.rescrape_unrunnable", uid=request.uid, item_id=item_id)
        return FAILED_EXIT
    return rescrape_item(
        config,
        settings,
        item_id,
        console=Console(),
        run_row=request_run_row(request.uid, trigger=request.trigger),
        step_boundary=per_step_boundary,
    )


@dataclass(frozen=True)
class Bodies:
    """What the worker runs for each kind of request; today's bodies by default.

    Attributes:
        pipeline: Runs a pipeline request.
        rescrape: Runs an item rescrape request.
    """

    pipeline: Body = field(default=_run_pipeline)
    rescrape: Body = field(default=_run_rescrape)


class _RequestRunRecorder:
    """Writes a rescrape's numeric result on its ``pipeline_run`` row (fail-soft, like the writer)."""

    def __init__(self, writer: PipelineRunWriter, uid: RunUid, command: str) -> None:
        """Bind the recorder to the row.

        Args:
            writer: The library store's run writer.
            uid: The row's uid (the request's).
            command: The command the row is recorded under.
        """
        self._writer = writer
        self._uid = uid
        self._command = command
        self._started_at = time.time()

    def record_counts(self, counts: dict[str, int]) -> None:
        """Append the result as one ``steps_json`` entry.

        Args:
            counts: The counters to record.
        """
        self._writer.update_step(self._uid, self._command, self._started_at, time.time(), "success", counts=counts)


def request_run_row(uid: RunUid, *, trigger: RunTrigger = RunTrigger.WEB) -> RunRowFactory:
    """The ``pipeline_run`` row factory of a rescrape run by the worker: its row, under the request's uid.

    The CLI's row factory cannot serve here: with ``PERSONALSCRAPER_RUN_UID`` set it believes a web
    runner reserved and finalizes the row, and writes neither. The worker has no such runner, so it
    owns the row: inserted ``maintenance`` under the uid, finalized ``success``, or ``error`` when an
    exception leaves the block (the rescrape raises one on failure precisely so).

    Args:
        uid: The request's uid, the row's.
        trigger: The request's trigger, the row's.

    Returns:
        A factory with the shape ``rescrape_item`` expects.
    """

    @contextmanager
    def run_row(config: Config, command: str) -> Iterator[RunRecorder | None]:
        """Open the row of *command* under the request's uid; finalize it on exit.

        Args:
            config: Loaded configuration (``indexer.db_path`` hosts the row).
            command: The command the row is recorded under.

        Yields:
            The recorder; ``None`` when the configuration names no library store.

        Raises:
            BaseException: Whatever the block raised, after the row is finalized ``error``.
        """
        db_path = config.indexer.db_path
        if db_path is None:
            yield None
            return
        writer = PipelineRunWriter(Path(db_path))
        writer.insert(
            uid,
            trigger=trigger.value,
            dry_run=False,
            pid=os.getpid(),
            kind="maintenance",
            command=command,
            if_absent=True,
        )
        try:
            yield _RequestRunRecorder(writer, uid, command)
        except BaseException as exc:
            writer.finalize(uid, "error", error=str(exc) or type(exc).__name__)
            raise
        writer.finalize(uid, "success")

    return run_row


class _Heartbeat:
    """A daemon thread writing the request's ``heartbeat_at`` every interval while the body runs."""

    def __init__(self, store: AppStore, uid: RunUid, interval_s: float, clock: Callable[[], float]) -> None:
        """Prepare the thread; nothing runs until the block is entered.

        Args:
            store: The environment's ``app.db``.
            uid: The request.
            interval_s: Seconds between two heartbeats.
            clock: The epoch clock.
        """
        self._store = store
        self._uid = uid
        self._interval_s = interval_s
        self._clock = clock
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._beat, name="worker-heartbeat", daemon=True)

    def _beat(self) -> None:
        """Write a heartbeat each interval until stopped; a failed write is logged, never fatal."""
        while not self._stopped.wait(self._interval_s):
            try:
                self._store.runs.touch_heartbeat(self._uid, self._clock())
            except Exception:  # noqa: BLE001 — a missed beat must never stop the run it reports on
                log.warning("worker.heartbeat_failed", uid=self._uid, exc_info=True)

    def __enter__(self) -> None:
        """Start beating."""
        self._thread.start()

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        """Stop beating and wait for the thread.

        Args:
            exc_type: The exception type leaving the block, if any.
            exc: The exception, if any.
            tb: Its traceback, if any.
        """
        self._stopped.set()
        self._thread.join()


def run_request(
    uid: RunUid,
    *,
    config: Config,
    settings: Settings,
    store: AppStore,
    bodies: Bodies | None = None,
    heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S,
    clock: Callable[[], float] = time.time,
) -> int:
    """Run request *uid* under ``pipeline.lock``, beating its heartbeat, and return the exit code.

    Args:
        uid: The request.
        config: Loaded configuration.
        settings: Loaded settings.
        store: The environment's ``app.db``.
        bodies: What runs each kind; today's bodies when ``None``.
        heartbeat_interval_s: Seconds between two heartbeats.
        clock: The epoch clock of the heartbeats.

    Returns:
        The body's exit code; :data:`LOST_LOCK_EXIT` when ``pipeline.lock`` is held (nothing ran);
        :data:`FAILED_EXIT` when the request is unknown, not ``running`` (the supervisor saves
        the admission before it starts the worker, so any other state means it did not admit
        this run), or the body raised.
    """
    bodies = bodies if bodies is not None else Bodies()
    request = store.runs.get(uid)
    if request is None:
        log.error("worker.request_unknown", uid=uid)
        return FAILED_EXIT
    if request.state is not RequestState.RUNNING:
        log.error("worker.request_not_running", uid=uid, state=request.state)
        return FAILED_EXIT
    data_dir = config.paths.data_dir
    lock_file = data_dir / "pipeline.lock"
    if not acquire_pipeline_lock(lock_file, scrape_locks_dir_for(data_dir)):
        log.warning("worker.lost_lock", uid=uid)
        return LOST_LOCK_EXIT
    body = bodies.pipeline if request.kind is RunKind.PIPELINE else bodies.rescrape
    log.info("worker.started", uid=uid, kind=request.kind, pid=os.getpid())
    try:
        with _Heartbeat(store, uid, heartbeat_interval_s, clock):
            try:
                code = body(config, settings, request)
            except Exception:
                log.exception("worker.failed", uid=uid, kind=request.kind)
                code = FAILED_EXIT
    finally:
        release_lock(lock_file)
    log.info("worker.ended", uid=uid, kind=request.kind, code=code)
    return code


def main() -> int:
    """Run the request named by ``PERSONALSCRAPER_RUN_UID``; the entry point of ``python -m``.

    Returns:
        The exit code (see :func:`run_request`); :data:`FAILED_EXIT` with no uid or no configuration.
    """
    raw_uid = os.environ.get(RUN_UID_ENV)
    if not raw_uid:
        log.error("worker.uid_missing", variable=RUN_UID_ENV)
        return FAILED_EXIT
    uid = RunUid(raw_uid)
    configure_logging()
    try:
        config = load_config()
        settings = get_settings()
    except Exception:
        log.exception("worker.config_load_failed", uid=uid)
        return FAILED_EXIT
    store = build_app_store(config)
    try:
        return run_request(uid, config=config, settings=settings, store=store)
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
