"""``RunService``: the one in-process enqueue every starter of a run converges on.

The web, the CLI and the watcher ask a run (or an item rescrape, or an acquisition pass) here; the
supervisor's lease is the only authority that starts it. An ask never fails for lack of room: an equal
ask waiting in the queue answers it (it is joined, the same uid comes back), else it is queued; a
caller that brings its own uid follows that uid's run and joins no other request. What joins what is
the model's rule (:meth:`~personalscraper.app.supervisor.model.RunRequest.joins`); this service looks
for the candidate and writes, in one ``BEGIN IMMEDIATE`` transaction so two concurrent equal asks
cannot both queue.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import authorise, requires
from personalscraper.app.accounts.requirements import OPERATION_RIGHTS
from personalscraper.app.accounts.rights import AnyOf, Right
from personalscraper.app.errors import AppForbidden, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import (
    AcquisitionJob,
    JobKind,
    Lane,
    RequestState,
    RunKind,
    RunOptions,
    RunRequest,
    RunTrigger,
)
from personalscraper.core.identity import ItemId
from personalscraper.logger import get_logger

log = get_logger("app.supervisor.service")

#: The contract's ``PipelineState`` subset an ask is answered with; ``idle`` only for a promised uid
#: whose request is already settled (nothing runs for it).
PipelineAnswer = Literal["queued", "running", "idle"]

_ANSWERS: Final[dict[RequestState, PipelineAnswer]] = {
    RequestState.QUEUED: "queued",
    RequestState.RUNNING: "running",
    RequestState.SETTLED: "idle",
}


#: The operations whose rights open each acquisition pass: the ones a caller holds to ask it. A ``prime``
#: is asked by the use case that made a follow take work (DESIGN § 2.3 and § 2.7: create, restore, update
#: or lift the pause of a follow, grab a season), under theirs.
_JOB_OPERATIONS: Final[dict[JobKind, tuple[str, ...]]] = {
    JobKind.DETECT: ("runDetection",),
    JobKind.SEARCH: ("searchForFollow",),
    JobKind.GRAB: ("grabForFollow",),
    JobKind.PRIME: ("createFollow", "restoreFollow", "updateFollow", "grabSeasonForFollow", "setAcquisitionPause"),
}


def _job_requirement(job_kind: JobKind) -> AnyOf:
    """The rights any one of which opens an acquisition pass.

    Args:
        job_kind: The pass.

    Returns:
        The union of the rights of its operations (:data:`_JOB_OPERATIONS`), read from the one table.
    """
    rights: set[Right] = set()
    for operation in _JOB_OPERATIONS[job_kind]:
        requirement = OPERATION_RIGHTS[operation]
        assert isinstance(requirement, AnyOf), f"{operation} is right-gated"
        rights |= requirement.rights
    return AnyOf(frozenset(rights))


class RequesterLookup(Protocol):
    """Who asked for a follow: what ``ask_acquisition`` needs of ``acquire.db``."""

    def requesters_of(self, followed_id: int) -> Collection[str]:
        """The accounts that asked for a follow.

        Args:
            followed_id: The follow's ``followed_series`` row.

        Returns:
            Their account ids; empty when nobody did (or the follow does not exist).
        """
        ...


@dataclass(frozen=True)
class RunAsked:
    """The answer to an ask.

    Attributes:
        uid: The request that answers it: the new one, or the one joined.
        state: ``running`` when the request answering already runs (a joined rescrape, or a promised
            uid's request), ``idle`` when a promised uid's request is already settled, else ``queued``.
        joined: ``True`` when the ask was answered by a request already in the queue (or settled) instead
            of queueing one.
    """

    uid: RunUid
    state: PipelineAnswer
    joined: bool


@dataclass(frozen=True)
class QueueView:
    """The queue as one read sees it (K8's seam).

    ``running`` and ``queued`` are the pipeline lane's (the runs and the rescrapes), what the watcher and
    ``run`` have always read; the acquisition lane's are beside them.

    Attributes:
        running: The pipeline-lane request being run, or ``None``.
        queued: The pipeline-lane requests still waiting, oldest ask first.
        lease_live: Whether a supervisor's lease is live, so a queued request will be started.
        acquisition_running: The acquisition-lane request being run, or ``None``.
        acquisition_queued: The acquisition-lane requests still waiting, oldest ask first.
    """

    running: RunRequest | None
    queued: tuple[RunRequest, ...]
    lease_live: bool
    acquisition_running: RunRequest | None = None
    acquisition_queued: tuple[RunRequest, ...] = ()


class RunService:
    """Asks runs and rescrapes into the queue, and reads it."""

    def __init__(
        self,
        *,
        store: AppStore,
        data_dir: Path,
        clock: Callable[[], float] = time.time,
        requesters: RequesterLookup | None = None,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            data_dir: The pipeline data directory.
            clock: The epoch clock.
            requesters: Who asked for a follow, to judge an ask's target; ``None`` knows nobody, so only
                an actor holding ``acquisition.pilot.any`` may ask a pass scoped to a follow.
        """
        self._store = store
        self._data_dir = data_dir
        self._clock = clock
        self._requesters = requesters

    @requires("runPipeline")
    def ask_run(self, actor: Actor, *, trigger: RunTrigger, options: RunOptions, uid: RunUid | None = None) -> RunAsked:
        """Ask a pipeline run: join the equal one waiting, else queue it.

        Args:
            actor: Who asks; needs the right to pilot the pipeline.
            trigger: What the ask comes from.
            options: What the run is asked to do.
            uid: The request's key when the caller already promised one (v0's run uid). The caller
                follows THAT uid's run, so the ask never joins another request: it is queued under
                this uid, or, when the uid is already in the queue, it is a retry and that request
                answers it (``joined``, its own state: ``queued``, ``running``, or ``idle`` once
                settled), nothing being inserted.

        Returns:
            The request answering the ask.

        Raises:
            AppForbidden: ``right.missing``, ``instance.forbidden_write`` or ``instance.read_only``,
                before anything is written.
        """
        asked = RunRequest.ask(RunKind.PIPELINE, trigger, options, actor.account_id, self._clock(), uid)
        return self._ask(asked, promised=uid is not None)

    @requires("rescrapeMedia")
    def ask_rescrape(self, actor: Actor, *, item_id: ItemId) -> RunAsked:
        """Ask the rescrape of one item: join the request of that item waiting or running, else queue it.

        Args:
            actor: Who asks; needs the right to rescrape media.
            item_id: The ``media_item`` row to rescrape.

        Returns:
            The request answering the ask; ``running`` when it joined one already running.

        Raises:
            AppForbidden: ``right.missing``, ``instance.forbidden_write`` or ``instance.read_only``,
                before anything is written.
        """
        asked = RunRequest.ask(
            RunKind.RESCRAPE, RunTrigger.WEB, RunOptions(item_id=item_id), actor.account_id, self._clock()
        )
        return self._ask(asked)

    # ``dismissClosure`` stands only for « a session write »: a signed-in actor, refused on a read-only
    # instance. The table holds contract operations alone (tests/http_v1/test_rights_table.py,
    # ``test_keys_are_the_contract_operations_and_the_pending_ones``, refuses another id), so this ask has
    # none of its own: the job's rights are checked in the body.
    @requires("dismissClosure")
    def ask_acquisition(self, actor: Actor, job: AcquisitionJob, *, trigger: RunTrigger = RunTrigger.WEB) -> RunAsked:
        """Ask one acquisition pass: join the equal one waiting, else queue it in the acquisition lane.

        Two equal asks queued together are one request; a pass already running does not absorb a new
        ask (what it works on was read when it started). Never a refusal for lack of room.

        The ask is authorised against its target, here, so no caller can skip it. The pass's operation
        opens it (:data:`_JOB_OPERATIONS`), then a search, a grab or a prime must be the actor's own to
        act on: scoped to a follow, the actor is among its requesters or holds ``acquisition.pilot.any``;
        a whole-queue pass (no follow) needs ``acquisition.pilot.any``. A detect is the pipeline's, whole
        or scoped: ``runDetection`` opens it.

        Args:
            actor: Who asks.
            job: The pass.
            trigger: What the ask comes from.

        Returns:
            The request answering the ask.

        Raises:
            AppForbidden: ``instance.read_only`` (a read-only instance), ``instance.forbidden_write`` or
                ``right.missing`` (the operation's rights, or ``acquisition.pilot.any`` for a follow that is
                not the actor's, whether it exists or not), before anything is written.
        """
        authorise(actor, _job_requirement(job.kind))
        self._authorise_target(actor, job)
        asked = RunRequest.ask(RunKind.ACQUISITION, trigger, job, actor.account_id, self._clock())
        return self._ask(asked)

    def _authorise_target(self, actor: Actor, job: AcquisitionJob) -> None:
        """Refuse a pass whose target the actor may not act on.

        Args:
            actor: Who asks.
            job: The pass.

        Raises:
            AppForbidden: ``right.missing`` (``acquisition.pilot.any``) for a whole-queue search or grab, or
                for a follow the actor is no requester of (a follow that does not exist has none).
        """
        if job.kind is JobKind.DETECT or actor.holds(Right.ACQUISITION_PILOT_ANY):
            return
        if job.followed_id is not None and self._requesters is not None:
            if actor.is_requester(self._requesters.requesters_of(job.followed_id)):
                return
        raise AppForbidden(
            "The signed-in account may not act on this acquisition.",
            code=RefusalCode.RIGHT_MISSING,
            params={"rights": [Right.ACQUISITION_PILOT_ANY.value]},
        )

    def queue_view(self) -> QueueView:
        """Read the queue: what runs, what waits in order, and whether a supervisor's lease is live.

        Returns:
            The view.
        """
        store = self._store
        with store.snapshot():
            running = store.runs.running(Lane.PIPELINE)
            queued = store.runs.queued(Lane.PIPELINE)
            acquisition_running = store.runs.running(Lane.ACQUISITION)
            acquisition_queued = store.runs.queued(Lane.ACQUISITION)
            lease = store.lease.read()
        return QueueView(
            running=running[0] if running else None,
            queued=queued,
            lease_live=lease is not None and lease.live(self._clock()),
            acquisition_running=acquisition_running[0] if acquisition_running else None,
            acquisition_queued=acquisition_queued,
        )

    def request(self, uid: RunUid) -> RunRequest | None:
        """Read one request.

        Args:
            uid: Its key.

        Returns:
            The request, or ``None``.
        """
        return self._store.runs.get(uid)

    def _ask(self, asked: RunRequest, *, promised: bool = False) -> RunAsked:
        """Queue a freshly made ask, or answer it with the request it joins; one transaction.

        Args:
            asked: The ask, made by :meth:`RunRequest.ask`.
            promised: Whether its uid was supplied by the caller: such an ask joins no other request,
                and a request already stored under that uid answers it.

        Returns:
            The answer.
        """
        runs = self._store.runs
        with self._store.immediate():
            if promised:
                joinable = runs.get(asked.uid)
            else:
                item_id = None if asked.kind is RunKind.ACQUISITION else asked.options.item_id
                joinable = runs.queued_like(asked.kind, asked.options_json, item_id)
                if joinable is None and asked.kind is RunKind.RESCRAPE:
                    joinable = next((request for request in runs.running() if asked.joins(request)), None)
                if joinable is not None and not asked.joins(joinable):
                    joinable = None
            if joinable is not None:
                answer = RunAsked(uid=joinable.uid, state=_ANSWERS[joinable.state], joined=True)
            else:
                runs.insert(asked)
                answer = RunAsked(uid=asked.uid, state="queued", joined=False)
        log.info(
            "app.runs.joined" if answer.joined else "app.runs.asked",
            uid=answer.uid,
            kind=asked.kind,
            trigger=asked.trigger,
            state=answer.state,
        )
        return answer
