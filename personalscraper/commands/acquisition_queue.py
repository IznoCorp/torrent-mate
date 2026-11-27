"""``follow detect``, ``search`` and ``grab`` under a live supervisor lease: ask the pass, then follow it.

While a supervisor's lease is live the pass is asked through the acquisition lane and followed
(:func:`personalscraper.commands.run_follow.enqueue_and_follow_acquisition`); its worker runs it and writes
its ``pipeline_run`` row. With no live lease the command's direct path runs; a ``--dry-run`` writes nothing,
so its command never comes here. The command writes no row of its own, with two exceptions:

* a spawner promised a run uid (``PERSONALSCRAPER_RUN_UID``): it owns that row, and the command appends to
  it the counts the worker recorded, as the direct path appends its own;
* ``follow detect --series`` finds no follow to ask for: the direct path's line and its success row.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING

import typer

from personalscraper import cli_helpers
from personalscraper.acquire.store import build_acquire_store
from personalscraper.app.supervisor.acquisition_execution import PASS_COMMANDS
from personalscraper.app.supervisor.model import AcquisitionJob, JobKind
from personalscraper.commands import run_follow
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.i18n import t

if TYPE_CHECKING:
    from rich.console import Console

    from personalscraper.acquire.domain import FollowedSeries
    from personalscraper.conf.models.config import Config


def supervised(config: Config, console: Console) -> bool:
    """Whether a supervisor's lease is live, so the pass is asked through the queue.

    Args:
        config: The loaded configuration.
        console: Where a refusal prints.

    Returns:
        ``True`` when the stored lease has not expired.

    Raises:
        typer.Exit: Code 1 when the lease cannot be read: the lease alone authorises a pass.
    """
    try:
        return run_follow.lease_live(config)
    except run_follow.SupervisorStateUnreadable:
        console.print("[red]" + t("cli_core.run.supervisor_state_unreadable") + "[/red]")
        raise typer.Exit(1) from None


def queue_pass(config: Config, console: Console, kind: JobKind, *, followed_id: int | None, limit: int | None) -> None:
    """Ask a search or a grab through the queue and follow it to its end.

    Args:
        config: The loaded configuration.
        console: Where it prints.
        kind: ``search`` or ``grab``.
        followed_id: The command's ``--followed-id``, carried by the job.
        limit: The command's ``--limit``, carried by the job.

    Raises:
        typer.Exit: Code 2 for a limit below 1, which no job takes; else the pass's code when not 0.
    """
    if limit is not None and limit < 1:
        console.print("[red]" + t("cli_acquisition.queue.limit_too_low") + "[/red]")
        raise typer.Exit(2)
    _ask_and_follow(config, console, [AcquisitionJob(kind, followed_id=followed_id, limit=limit)])


def queue_detect(config: Config, console: Console, *, series: str | None) -> None:
    """Ask the detect through the queue: the whole one, or one per follow ``--series`` names.

    A job names a follow by its row, so ``--series`` is resolved here as the detect pass resolves it.

    Args:
        config: The loaded configuration.
        console: Where it prints.
        series: The command's ``--series``: an integer ``followed_id`` or a title substring; ``None``
            for every follow.

    Raises:
        typer.Exit: The first non-zero code among the asked detects.
    """
    if series is None:
        _ask_and_follow(config, console, [AcquisitionJob(JobKind.DETECT)])
        return
    store = build_acquire_store(config.acquire)
    try:
        # The set the detect pass polls: the active follows and the one-off requests.
        polled = [*store.follow.list_active(), *store.follow.list_requests()]
    finally:
        store.close()
    matched = _matching(polled, series)
    if not matched:
        key = "no_match" if polled else "no_active"
        with cli_run_row(config, PASS_COMMANDS[JobKind.DETECT]):
            console.print("[yellow]" + t(f"cli_acquisition.follow.detect.{key}") + "[/yellow]")
        return
    _ask_and_follow(config, console, [AcquisitionJob(JobKind.DETECT, followed_id=follow.id) for follow in matched])


def _matching(polled: list[FollowedSeries], series: str) -> list[FollowedSeries]:
    """The follows ``--series`` names, by :meth:`~personalscraper.acquire.detect.DetectService.run`'s rule.

    Args:
        polled: The follows the detect pass polls.
        series: An integer ``followed_id``, else a case-insensitive title substring.

    Returns:
        The matches.
    """
    try:
        followed_id = int(series)
    except ValueError:
        return [follow for follow in polled if series.lower() in follow.title.lower()]
    return [follow for follow in polled if follow.id == followed_id]


def _ask_and_follow(config: Config, console: Console, jobs: Sequence[AcquisitionJob]) -> None:
    """Ask the jobs, follow them, and copy their counts onto a promised row.

    Args:
        config: The loaded configuration.
        console: Where it prints.
        jobs: Jobs of one kind.

    Raises:
        typer.Exit: The first non-zero code among the followed requests.
    """
    services = run_follow.open_services(config, cli_helpers.get_settings())
    try:
        if not os.environ.get(run_follow.RUN_UID_ENV):
            code, _ = run_follow.enqueue_and_follow_acquisition(services, config, console, jobs)
        else:
            with cli_run_row(config, PASS_COMMANDS[jobs[0].kind]) as run_rec:
                code, uids = run_follow.enqueue_and_follow_acquisition(services, config, console, jobs)
                for uid in uids:
                    for counts in run_follow.pass_counts(config.indexer.db_path, uid):
                        run_rec.record_counts(counts)
    finally:
        services.close()
    if code:
        raise typer.Exit(code)
