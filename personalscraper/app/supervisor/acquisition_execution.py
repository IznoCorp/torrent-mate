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
from dataclasses import asdict, dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

from personalscraper.acquire.detect import DetectResult, DetectStatus
from personalscraper.acquire.service import RunSummary, SearchRunSummary
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

    def run(self, *, series: str | None, dry_run: bool, today: date, now: int) -> DetectResult:
        """Run one detect pass over the active followed set.

        Args:
            series: An integer ``followed_id`` as text, or a title substring; ``None`` for every follow.
            dry_run: Preview without writing.
            today: The reference date for the airing poll.
            now: The epoch stamped on new rows.

        Returns:
            The pass's result: its status, its actions and its counts.
        """
        ...


class SearchPass(Protocol):
    """What the worker asks of the acquisition service for a search (:meth:`AcquisitionService.run_search`)."""

    def run_search(self, *, limit: int | None = None, followed_id: int | None = None) -> SearchRunSummary:
        """Run the search pass over the pending wanted items.

        Args:
            limit: The most items attempted; ``None`` for all.
            followed_id: Restrict the pass to one follow; ``None`` for the whole queue.

        Returns:
            The pass's counts.
        """
        ...


class GrabPass(Protocol):
    """What the worker asks of the acquisition service for a grab (:meth:`AcquisitionService.run`)."""

    def run(
        self,
        *,
        limit: int | None = None,
        followed_id: int | None = None,
        run_uid: str | None = None,
        release: str | None = None,
    ) -> RunSummary:
        """Run the grab pass over the available wanted items.

        Args:
            limit: The most items attempted; ``None`` for all.
            followed_id: Restrict the pass to one follow; ``None`` for the whole queue.
            run_uid: The run the grabbed items are stamped with.
            release: The release a person named, taken if it is still offered; passed ONLY when the
                job names one, so a grab without it is called exactly as before.

        Returns:
            The pass's counts.
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
    """Run the passes of *job* through *engine*, each scoped to the job's follow, and settle by what they did.

    A ``prime`` runs its follow's detect, then search, then grab, as the v0 runner's three steps did; with
    no grab service (no torrent client) it runs the first two, logs the grab it skipped and exits 1. Every
    pass logs its counts (``worker.acquisition_pass``). A pass scoped to a follow that the detect cannot find
    (no such follow, or not active) ends the job with exit 1, and so does a search that concluded on nothing
    (every item unverified: « panne ≠ absence »). A pass that raises ends the job: the exception goes to the
    caller, which turns it into an exit 1.

    A grab that names a release (a person's choice, DESIGN O-14) asks the engine for that release alone. When
    it was not taken the request ends with exit 1 and says why: ``worker.acquisition_release_gone`` when the
    release is no longer offered (the wanted row records ``chosen_release_gone``, nothing was added, no other
    release stands in), ``worker.acquisition_release_not_taken`` when nothing was grabbed for another reason.

    Args:
        job: What is asked.
        engine: The services to call.
        run_uid: The request's uid, stamped on what a grab takes.
        clock: The epoch clock.

    Returns:
        The exit code: 0 when every pass ran and did what was asked of it; 1 otherwise.

    Raises:
        AcquisitionUnavailable: If a service the job needs is not in *engine* (a prime's grab excepted).
    """
    code = 0
    if job.kind in (JobKind.DETECT, JobKind.PRIME) and not _detect(job, engine, clock, run_uid):
        return 1
    if job.kind in (JobKind.SEARCH, JobKind.PRIME):
        if engine.search is None:
            raise AcquisitionUnavailable("the engine has no search service")
        searched = engine.search.run_search(limit=job.limit, followed_id=job.followed_id)
        _log_pass("search", job, run_uid, asdict(searched))
        if searched.unverified and not (searched.available or searched.waiting or searched.abandoned):
            log.error("worker.acquisition_search_inconclusive", uid=run_uid, followed_id=job.followed_id)
            code = 1
    if job.kind in (JobKind.GRAB, JobKind.PRIME):
        if engine.grab is None:
            if job.kind is not JobKind.PRIME:
                raise AcquisitionUnavailable("the engine has no grab service")
            log.warning("worker.acquisition_grab_skipped", uid=run_uid, followed_id=job.followed_id, reason="no_client")
            return 1
        # ``release`` goes to the service only when the job names one: a grab without it is called as ever.
        if job.release is None:
            grabbed = engine.grab.run(limit=job.limit, followed_id=job.followed_id, run_uid=run_uid)
        else:
            grabbed = engine.grab.run(
                limit=job.limit, followed_id=job.followed_id, run_uid=run_uid, release=job.release
            )
        _log_pass("grab", job, run_uid, asdict(grabbed))
        if job.release is not None and not grabbed.grabbed:
            # What a person chose was not taken, and no other release stands in for it (DESIGN O-14).
            event = (
                "worker.acquisition_release_gone" if grabbed.release_gone else "worker.acquisition_release_not_taken"
            )
            log.error(event, uid=run_uid, followed_id=job.followed_id, release=job.release, gone=grabbed.release_gone)
            code = 1
    return code


def _detect(job: AcquisitionJob, engine: AcquisitionEngine, clock: Callable[[], float], run_uid: RunUid) -> bool:
    """Run the detect pass of *job* and judge its result.

    Args:
        job: The job; its follow, when it has one, is the pass's ``series`` filter.
        engine: The services.
        clock: The epoch clock.
        run_uid: The request's uid, for the log.

    Returns:
        ``False`` when the job names a follow the pass did not find at work (``no_match``: it does not
        exist, or ``no_active``: it is not active), so nothing further can be done for it; ``True`` otherwise.

    Raises:
        AcquisitionUnavailable: If *engine* has no detect service.
    """
    if engine.detect is None:
        raise AcquisitionUnavailable("the engine has no detect service")
    now = clock()
    result = engine.detect.run(
        series=None if job.followed_id is None else str(job.followed_id),
        dry_run=False,
        today=date.fromtimestamp(now),
        now=int(now),
    )
    _log_pass("detect", job, run_uid, {"status": result.status.value, **asdict(result.summary)})
    if job.followed_id is not None and result.status is not DetectStatus.OK:
        log.error("worker.acquisition_follow_not_found", uid=run_uid, followed_id=job.followed_id, status=result.status)
        return False
    return True


def _log_pass(name: str, job: AcquisitionJob, run_uid: RunUid, counts: dict[str, object]) -> None:
    """Log what a pass did; a pass scoped to a follow that did nothing at all is a warning.

    Args:
        name: The pass.
        job: The job it ran for.
        run_uid: The request's uid.
        counts: What the pass reported.
    """
    log.info("worker.acquisition_pass", uid=run_uid, step=name, followed_id=job.followed_id, **counts)
    if job.followed_id is not None and not any(value for key, value in counts.items() if key != "status"):
        log.warning("worker.acquisition_pass_idle", uid=run_uid, step=name, followed_id=job.followed_id)
