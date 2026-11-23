"""An acquisition request's passes, as callables over the engine's services.

The worker runs a detect, a search or a grab IN-PROCESS: it calls the engine's services
(:class:`~personalscraper.acquire.detect.DetectService`, :class:`~personalscraper.acquire.service.AcquisitionService`)
with the job's follow, never a CLI step. The services reach it through :class:`AcquisitionEngine`, a port the
worker fills (with fakes in a test); this module imports no engine module at runtime, nor ``commands`` nor
``cli_helpers``. It takes no ``pipeline.lock``: its caller is the acquisition lane, which holds none.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

from personalscraper.app.supervisor.model import AcquisitionJob, JobKind
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from personalscraper.app.supervisor.ids import RunUid
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings

log = get_logger("app.supervisor.acquisition_execution")


class AcquisitionUnavailable(RuntimeError):
    """The engine cannot run the pass asked: a service it needs is not wired (no store, no torrent client)."""


class DetectPass(Protocol):
    """What the worker asks of the detect service (:meth:`DetectService.run`)."""

    def run(self, *, series: str | None, dry_run: bool, today: date, now: int) -> object:
        """Run one detect pass over the active followed set.

        Args:
            series: An integer ``followed_id`` as text, or a title substring; ``None`` for every follow.
            dry_run: Preview without writing.
            today: The reference date for the airing poll.
            now: The epoch stamped on new rows.

        Returns:
            The pass's result.
        """
        ...


class SearchPass(Protocol):
    """What the worker asks of the acquisition service for a search (:meth:`AcquisitionService.run_search`)."""

    def run_search(self, *, limit: int | None = None, followed_id: int | None = None) -> object:
        """Run the search pass over the pending wanted items.

        Args:
            limit: The most items attempted; ``None`` for all.
            followed_id: Restrict the pass to one follow; ``None`` for the whole queue.

        Returns:
            The pass's summary.
        """
        ...


class GrabPass(Protocol):
    """What the worker asks of the acquisition service for a grab (:meth:`AcquisitionService.run`)."""

    def run(self, *, limit: int | None = None, followed_id: int | None = None, run_uid: str | None = None) -> object:
        """Run the grab pass over the available wanted items.

        Args:
            limit: The most items attempted; ``None`` for all.
            followed_id: Restrict the pass to one follow; ``None`` for the whole queue.
            run_uid: The run the grabbed items are stamped with.

        Returns:
            The pass's summary.
        """
        ...


@dataclass(frozen=True)
class AcquisitionEngine:
    """The engine services a job needs; each is ``None`` when the job needs none of it.

    Attributes:
        detect: The detect pass.
        search: The search pass.
        grab: The grab pass.
    """

    detect: DetectPass | None = None
    search: SearchPass | None = None
    grab: GrabPass | None = None


#: Opens the engine for one job, and closes it after: the worker's boundary (the CLI's ``per_step_boundary``).
EngineOpener = Callable[["Config", "Settings", AcquisitionJob], "AbstractContextManager[AcquisitionEngine]"]

#: Whether a pass needs a connected torrent client, which only a grab adds a torrent through.
NEEDS_TORRENT_CLIENT = frozenset({JobKind.GRAB, JobKind.PRIME})


def run_acquisition_job(
    job: AcquisitionJob,
    engine: AcquisitionEngine,
    *,
    run_uid: RunUid,
    clock: Callable[[], float] = time.time,
) -> int:
    """Run the passes of *job* through *engine*, each scoped to the job's follow.

    A ``prime`` runs its follow's detect, then search, then grab, as the v0 runner's three steps did.
    A pass that raises ends the job: the exception goes to the caller, which turns it into an exit 1.

    Args:
        job: What is asked.
        engine: The services to call.
        run_uid: The request's uid, stamped on what a grab takes.
        clock: The epoch clock.

    Returns:
        The exit code: 0 when every pass ran; 1 when the job asks for what the engine cannot do.

    Raises:
        AcquisitionUnavailable: If a service the job needs is not in *engine*.
    """
    if job.release is not None:
        # The engine takes no named release yet: grabbing the follow's ordinary pick instead would be a silent
        # substitute for what was asked (DESIGN O-14), so nothing runs.
        log.error("worker.acquisition_release_unsupported", uid=run_uid, followed_id=job.followed_id)
        return 1
    if job.kind in (JobKind.DETECT, JobKind.PRIME):
        _detect(job, engine, clock)
    if job.kind in (JobKind.SEARCH, JobKind.PRIME):
        if engine.search is None:
            raise AcquisitionUnavailable("the engine has no search service")
        engine.search.run_search(limit=job.limit, followed_id=job.followed_id)
    if job.kind in (JobKind.GRAB, JobKind.PRIME):
        if engine.grab is None:
            raise AcquisitionUnavailable("the engine has no grab service")
        engine.grab.run(limit=job.limit, followed_id=job.followed_id, run_uid=run_uid)
    return 0


def _detect(job: AcquisitionJob, engine: AcquisitionEngine, clock: Callable[[], float]) -> None:
    """Run the detect pass of *job*.

    Args:
        job: The job; its follow, when it has one, is the pass's ``series`` filter.
        engine: The services.
        clock: The epoch clock.

    Raises:
        AcquisitionUnavailable: If *engine* has no detect service.
    """
    if engine.detect is None:
        raise AcquisitionUnavailable("the engine has no detect service")
    now = clock()
    engine.detect.run(
        series=None if job.followed_id is None else str(job.followed_id),
        dry_run=False,
        today=date.fromtimestamp(now),
        now=int(now),
    )
