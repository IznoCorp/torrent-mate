"""``personalscraper run`` under a live supervisor lease: ask the run, then follow it.

While a supervisor's lease is live nothing but its worker starts a run, so the command asks the
run through the in-process :class:`~personalscraper.app.supervisor.service.RunService` and follows
the request the service answered (a uid-less ask may have joined another request, so the follower
never trusts the uid it brought). It polls the request and the run's ``pipeline_run`` row, prints
each step as it closes and exits with the run's code. With no live lease the command's direct path
runs instead, unchanged.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import typer
from rich.console import Console

from personalscraper.app.composition import build_app_services
from personalscraper.app.errors import AppRefusal, RefusalCode
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import RequestState, RunOptions, RunRequest, RunTrigger, Settlement
from personalscraper.conf.environment import StoreName, store_path
from personalscraper.core.event_bus import EventBus
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.i18n import t, t_code
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.app.services import AppServices
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings

log = get_logger("commands.run_follow")

#: Seconds between two reads of the request and of the run's row.
POLL_INTERVAL_S: Final = 2.0

#: The environment variable a spawning caller (v0's web, the resolve continuation) promises its uid in.
RUN_UID_ENV: Final = "PERSONALSCRAPER_RUN_UID"

#: The exit code of a run the trailers step aborted (``execute_run``'s own).
TRAILER_ABORT_CODE: Final = 2

_EXIT_CODES: Final[dict[Settlement, int]] = {
    Settlement.SUCCESS: 0,
    Settlement.ERROR: 1,
    Settlement.KILLED: 130,
    Settlement.INTERRUPTED: 1,
    Settlement.ABANDONED: 1,
}


def _trigger_of(reason: str) -> RunTrigger:
    """Map a ``--trigger-reason`` to the request's trigger.

    Args:
        reason: The validated option value; empty for a plain CLI run.

    Returns:
        ``RunTrigger.CLI`` for an empty reason, else the trigger of the same code.
    """
    return RunTrigger(reason) if reason else RunTrigger.CLI


def supervised_services(config: Config, settings: Settings) -> AppServices | None:
    """Open the application services when a supervisor's lease is live.

    ``app.db`` is never created for the question: with no file there never was a supervisor.

    Args:
        config: The loaded configuration.
        settings: The loaded settings.

    Returns:
        The services, which the caller closes; ``None`` when no live lease stands (the direct path).
    """
    if not store_path(config.paths.data_dir, StoreName.APP).exists():
        return None
    services = build_app_services(config, settings, event_bus=EventBus())
    try:
        live = services.runs.queue_view().lease_live
    except BaseException:
        services.close()
        raise
    if not live:
        services.close()
        return None
    return services


def enqueue_and_follow(
    services: AppServices,
    config: Config,
    console: Console,
    *,
    options: RunOptions,
    trigger_reason: str,
    detach: bool,
) -> int:
    """Ask the run, then follow it to its end.

    Args:
        services: The application services, with a live lease.
        config: The loaded configuration (the run's row lives in ``indexer.db_path``).
        console: Where the follower prints.
        options: What the run is asked to do.
        trigger_reason: The validated ``--trigger-reason``; empty for a plain CLI run.
        detach: Return once asked instead of following.

    Returns:
        The exit code: the run's, or ``0`` once detached.

    Raises:
        typer.Exit: Code 1 when the instance refuses the ask.
    """
    promised = os.environ.get(RUN_UID_ENV) or None
    try:
        asked = services.runs.ask_run(
            services.credentials.system_actor(),
            trigger=_trigger_of(trigger_reason),
            options=options,
            uid=RunUid(promised) if promised else None,
        )
    except AppRefusal as exc:
        code = exc.code if exc.code is not None else RefusalCode.INTERNAL
        scalars: dict[str, Any] = {
            name: value for name, value in exc.params.items() if isinstance(value, (str, int, float))
        }
        console.print("[red]" + t_code("cli_refusals", code, **scalars) + "[/red]")
        raise typer.Exit(1) from None
    uid = asked.uid
    if asked.joined:
        console.print(t("cli_core.run.joined", uid=uid), highlight=False)
    else:
        position = len(services.runs.queue_view().queued)
        console.print(t("cli_core.run.queued", uid=uid, position=position), highlight=False)
    if detach:
        console.print(t("cli_core.run.detached", uid=uid), highlight=False)
        return 0
    try:
        return _follow(services, config, console, uid, options)
    except KeyboardInterrupt:
        console.print(t("cli_core.run.detached", uid=uid), highlight=False)
        return 0


def _follow(services: AppServices, config: Config, console: Console, uid: RunUid, options: RunOptions) -> int:
    """Poll a request until it settles, printing each step as it closes.

    Args:
        services: The application services.
        config: The loaded configuration.
        console: Where it prints.
        uid: The request answering the ask.
        options: What the run was asked to do.

    Returns:
        The run's exit code.
    """
    printed = 0
    while True:
        request = services.runs.request(uid)
        steps = _closed_steps(config.indexer.db_path, uid)
        for step in steps[printed:]:
            console.print(
                t("cli_core.run.step_done", step=str(step.get("name", "?")), status=str(step.get("status", "?"))),
                highlight=False,
            )
        printed = len(steps)
        if request is None:
            log.warning("run_follow.request_vanished", uid=uid)
            console.print("[red]" + t("cli_core.run.finished", settlement=Settlement.ABANDONED.value) + "[/red]")
            return _EXIT_CODES[Settlement.ABANDONED]
        if request.state is RequestState.SETTLED and request.settlement is not None:
            return _finish(console, request, request.settlement, steps, options)
        time.sleep(POLL_INTERVAL_S)


def _finish(
    console: Console, request: RunRequest, settlement: Settlement, steps: list[dict[str, object]], options: RunOptions
) -> int:
    """Print the end of a settled request and compute its exit code.

    Args:
        console: Where it prints.
        request: The settled request.
        settlement: How it ended.
        steps: The steps its row closed.
        options: What the run was asked to do.

    Returns:
        ``0``, ``1``, ``2`` (a trailer abort), or ``130``.
    """
    code = _EXIT_CODES[settlement]
    if settlement is Settlement.ERROR and _trailers_aborted(steps, options):
        code = TRAILER_ABORT_CODE
    style = "green" if code == 0 else "red"
    console.print(
        f"[{style}]" + t("cli_core.run.finished", settlement=settlement.value, uid=request.uid) + f"[/{style}]",
        highlight=False,
    )
    return code


def _trailers_aborted(steps: list[dict[str, object]], options: RunOptions) -> bool:
    """Whether the run's row says the trailers step aborted it.

    The pipeline stops on a failed trailers step unless it was asked to continue on a trailer error,
    in which case the failure is an ordinary one.

    Args:
        steps: The steps the row closed.
        options: What the run was asked to do.

    Returns:
        ``True`` when ``trailers`` closed in error and the run was not told to carry on.
    """
    if options.continue_on_trailer_error:
        return False
    return any(step.get("name") == "trailers" and step.get("status") == "error" for step in steps)


@contextmanager
def _read_only(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open the indexer database for a read.

    Args:
        db_path: The indexer database.

    Yields:
        The connection, closed afterwards.
    """
    with closing(sqlite3.connect(str(db_path), isolation_level=None)) as conn:
        apply_pragmas(conn)
        yield conn


def _closed_steps(db_path: Path | None, uid: RunUid) -> list[dict[str, object]]:
    """Read the steps a run's ``pipeline_run`` row has closed so far.

    Fail-soft: the row appears once the worker's pipeline starts, so a missing database, table or
    row, or an unreadable ``steps_json``, is simply « no step yet ».

    Args:
        db_path: The indexer database, or ``None`` when the configuration names none.
        uid: The run's uid.

    Returns:
        The step entries in the order they closed.
    """
    if db_path is None or not db_path.exists():
        return []
    try:
        with _read_only(db_path) as conn:
            row = conn.execute("SELECT steps_json FROM pipeline_run WHERE run_uid = ?", (uid,)).fetchone()
        steps = json.loads(row[0]) if row and row[0] else []
    except (sqlite3.Error, json.JSONDecodeError, TypeError):
        log.warning("run_follow.row_unreadable", uid=uid, exc_info=True)
        return []
    return [step for step in steps if isinstance(step, dict)]
