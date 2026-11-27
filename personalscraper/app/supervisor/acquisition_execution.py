"""An acquisition request's passes, as callables over the engine's services.

The worker runs a detect, a search or a grab IN-PROCESS: it calls the engine's services
(:class:`~personalscraper.acquire.detect.DetectService`, :class:`~personalscraper.acquire.service.AcquisitionService`)
with the job's follow, never a CLI step. The services reach it through :class:`AcquisitionEngine`, a port the
worker fills (with fakes in a test), and so does what runs around a pass (the reconcile before it, the
grab's subscribers). This module imports neither ``commands`` nor ``cli_helpers``. It takes no
``pipeline.lock``: its caller is the acquisition lane, which holds none.

It also holds the numbers a pass records on its ``pipeline_run`` row, which the CLI commands' direct path
records too.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import asdict, dataclass
from datetime import date
from typing import TYPE_CHECKING, Final, Protocol

from personalscraper.acquire.detect import DetectResult, DetectStatus, DetectSummary
from personalscraper.acquire.reconcile import ReconcileSummary
from personalscraper.acquire.service import RunSummary, SearchRunSummary
from personalscraper.app.supervisor.model import AcquisitionJob, JobKind
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.app.supervisor.ids import RunUid
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings

log = get_logger("app.supervisor.acquisition_execution")

#: The ``pipeline_run`` command each job's row is recorded under: the names the CLI commands and v0's runner use.
PASS_COMMANDS: Final[dict[JobKind, str]] = {
    JobKind.DETECT: "follow-detect",
    JobKind.SEARCH: "search",
    JobKind.GRAB: "grab",
    JobKind.PRIME: "prime",
}

#: Records one pass's numbers on the job's row: the pass's command, then its counts.
CountsRecorder = Callable[[str, dict[str, int]], None]


def detect_counts(summary: DetectSummary) -> dict[str, int]:
    """The numbers a detect records on its row.

    Args:
        summary: What the detect did.

    Returns:
        The counts.
    """
    return {
        "detected": summary.detected,
        "enqueued": summary.enqueued,
        "skipped_owned": summary.skipped_owned,
        "skipped_dup": summary.skipped_dup,
        "skipped_covered": summary.skipped_covered,
        "resurrected": summary.resurrected,
        "closed_owned": summary.closed_owned,
    }


def search_counts(summary: SearchRunSummary, reconcile: ReconcileSummary) -> dict[str, int]:
    """The numbers a search records on its row, the reconcile's before it included.

    ``requeued_missing`` is not recorded: a search holds no torrent client, so it can requeue nothing, and
    a hardcoded 0 would read as « nothing vanished ».

    Args:
        summary: What the search did.
        reconcile: What the ownership sweep before it did.

    Returns:
        The counts.
    """
    return {
        "available": summary.available,
        "waiting": summary.waiting,
        "unverified": summary.unverified,
        "abandoned": summary.abandoned,
        "skipped": summary.skipped,
        "absorbed": summary.absorbed,
        "closed_owned": reconcile.closed_owned,
        "fell_back_to_episodes": reconcile.fell_back_to_episodes,
    }


def grab_counts(summary: RunSummary, reconcile: ReconcileSummary) -> dict[str, int]:
    """The numbers a grab records on its row, the reconcile's before it included.

    Args:
        summary: What the grab did.
        reconcile: What the reconcile before it did.

    Returns:
        The counts.
    """
    return {
        "grabbed": summary.grabbed,
        "retried": summary.retried,
        "abandoned": summary.abandoned,
        "skipped": summary.skipped,
        "absorbed": summary.absorbed,
        "closed_owned": reconcile.closed_owned,
        "requeued_missing": reconcile.requeued_missing,
        # A grab recovered out of the add→confirm crash window is a real acquisition this run is
        # responsible for (§5 « résultat chiffré »: a run states all its numbers).
        "confirmed_grabbed": reconcile.confirmed_grabbed,
        # A season whose pack landed incomplete is a real state change this run made: the season row
        # went terminal and its gaps were re-queued.
        "fell_back_to_episodes": reconcile.fell_back_to_episodes,
    }


def _nothing_reconciled() -> ReconcileSummary:
    """The default of a pass with nothing around it.

    Returns:
        An all-zero sweep.
    """
    return ReconcileSummary()


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
        wanted_id: int | None = None,
        release_id: str | None = None,
    ) -> RunSummary:
        """Run the grab pass over the available wanted items.

        Args:
            limit: The most items attempted; ``None`` for all.
            followed_id: Restrict the pass to one follow; ``None`` for the whole queue.
            run_uid: The run the grabbed items are stamped with.
            release: The release a person named, taken if it is still offered; passed ONLY when the
                job names one, so a grab without it is called exactly as before.
            wanted_id: The one row the named release is asked of; passed only when the job names one.
            release_id: The handle of the very release picked on that row; passed only when the job names one.

        Returns:
            The pass's counts.
        """
        ...


@dataclass(frozen=True)
class AcquisitionEngine:
    """The engine services a job needs, and what runs around them; a service is ``None`` when the job needs none.

    Attributes:
        detect: The detect pass.
        search: The search pass.
        grab: The grab pass.
        before_search: Runs before a search; answers what it reconciled.
        before_grab: Runs before a grab; answers what it reconciled.
        grab_listeners: Opens the subscribers that hear the grab, from before :attr:`before_grab` (which
            emits download events) until the grab ends.
    """

    detect: DetectPass | None = None
    search: SearchPass | None = None
    grab: GrabPass | None = None
    before_search: Callable[[], ReconcileSummary] = _nothing_reconciled
    before_grab: Callable[[], ReconcileSummary] = _nothing_reconciled
    grab_listeners: Callable[[], AbstractContextManager[object]] = nullcontext


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
    record: CountsRecorder = lambda _command, _counts: None,
) -> int:
    """Run the passes of *job* through *engine*, each scoped to the job's follow, and settle by what they did.

    A ``prime`` runs its follow's detect, then search, then grab, as the v0 runner's three steps did; with
    no grab service (no torrent client) it runs the first two, logs the grab it skipped and exits 1. Every
    pass logs its counts (``worker.acquisition_pass``) and records them (*record*), a detect only when it
    polled (``ok``), as its command did. A pass scoped to a follow that the detect cannot find
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
        record: Receives each pass's numbers.

    Returns:
        The exit code: 0 when every pass ran and did what was asked of it; 1 otherwise.

    Raises:
        AcquisitionUnavailable: If a service the job needs is not in *engine* (a prime's grab excepted).
    """
    code = 0
    if job.kind in (JobKind.DETECT, JobKind.PRIME) and not _detect(job, engine, clock, run_uid, record):
        return 1
    if job.kind in (JobKind.SEARCH, JobKind.PRIME):
        if engine.search is None:
            raise AcquisitionUnavailable("the engine has no search service")
        reconciled = engine.before_search()
        searched = engine.search.run_search(limit=job.limit, followed_id=job.followed_id)
        _log_pass("search", job, run_uid, asdict(searched))
        record(PASS_COMMANDS[JobKind.SEARCH], search_counts(searched, reconciled))
        if searched.unverified and not (searched.available or searched.waiting or searched.abandoned):
            log.error("worker.acquisition_search_inconclusive", uid=run_uid, followed_id=job.followed_id)
            code = 1
    if job.kind in (JobKind.GRAB, JobKind.PRIME):
        if engine.grab is None:
            if job.kind is not JobKind.PRIME:
                raise AcquisitionUnavailable("the engine has no grab service")
            log.warning("worker.acquisition_grab_skipped", uid=run_uid, followed_id=job.followed_id, reason="no_client")
            return 1
        with engine.grab_listeners():
            reconciled = engine.before_grab()
            grabbed = _grab(job, engine.grab, run_uid)
        _log_pass("grab", job, run_uid, asdict(grabbed))
        record(PASS_COMMANDS[JobKind.GRAB], grab_counts(grabbed, reconciled))
        if job.release is not None and not grabbed.grabbed:
            # What a person chose was not taken, and no other release stands in for it (DESIGN O-14).
            event = (
                "worker.acquisition_release_gone" if grabbed.release_gone else "worker.acquisition_release_not_taken"
            )
            log.error(event, uid=run_uid, followed_id=job.followed_id, release=job.release, gone=grabbed.release_gone)
            code = 1
    return code


def _grab(job: AcquisitionJob, service: GrabPass, run_uid: RunUid) -> RunSummary:
    """Run the grab pass of *job*.

    ``release``, ``wanted_id`` and ``release_id`` go to the service only when the job names them: a grab
    without them is called as ever.

    Args:
        job: The job.
        service: The grab service.
        run_uid: The request's uid, stamped on what the grab takes.

    Returns:
        The pass's counts.
    """
    if job.release is None:
        return service.run(limit=job.limit, followed_id=job.followed_id, run_uid=run_uid)
    if job.wanted_id is None:
        return service.run(limit=job.limit, followed_id=job.followed_id, run_uid=run_uid, release=job.release)
    if job.release_id is None:
        return service.run(
            limit=job.limit,
            followed_id=job.followed_id,
            run_uid=run_uid,
            release=job.release,
            wanted_id=job.wanted_id,
        )
    return service.run(
        limit=job.limit,
        followed_id=job.followed_id,
        run_uid=run_uid,
        release=job.release,
        wanted_id=job.wanted_id,
        release_id=job.release_id,
    )


def _detect(
    job: AcquisitionJob,
    engine: AcquisitionEngine,
    clock: Callable[[], float],
    run_uid: RunUid,
    record: CountsRecorder,
) -> bool:
    """Run the detect pass of *job* and judge its result.

    Args:
        job: The job; its follow, when it has one, is the pass's ``series`` filter.
        engine: The services.
        clock: The epoch clock.
        run_uid: The request's uid, for the log.
        record: Receives the pass's numbers.

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
    if result.status is DetectStatus.OK:
        record(PASS_COMMANDS[JobKind.DETECT], detect_counts(result.summary))
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
