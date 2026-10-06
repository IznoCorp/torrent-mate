"""``RunService``: the one in-process enqueue every starter of a run converges on.

The web, the CLI and the watcher ask a run (or an item rescrape) here; the supervisor's lease is
the only authority that starts it. An ask never fails for lack of room: an equal ask waiting in the
queue answers it (it is joined, the same uid comes back), else it is queued; a caller that brings its
own uid follows that uid's run and joins no other request. What joins what is the model's rule
(:meth:`~personalscraper.app.supervisor.model.RunRequest.joins`); this service looks for the candidate
and writes, in one ``BEGIN IMMEDIATE`` transaction so two concurrent equal asks
cannot both queue.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import RequestState, RunKind, RunOptions, RunRequest, RunTrigger
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

    Attributes:
        running: The request being run, or ``None``.
        queued: The requests still waiting, oldest ask first.
        lease_live: Whether a supervisor's lease is live, so a queued request will be started.
    """

    running: RunRequest | None
    queued: tuple[RunRequest, ...]
    lease_live: bool


class RunService:
    """Asks runs and rescrapes into the queue, and reads it."""

    def __init__(self, *, store: AppStore, data_dir: Path, clock: Callable[[], float] = time.time) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            data_dir: The pipeline data directory.
            clock: The epoch clock.
        """
        self._store = store
        self._data_dir = data_dir
        self._clock = clock

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

    def queue_view(self) -> QueueView:
        """Read the queue: what runs, what waits in order, and whether a supervisor's lease is live.

        Returns:
            The view.
        """
        store = self._store
        with store.snapshot():
            running = store.runs.running()
            queued = store.runs.queued()
            lease = store.lease.read()
        return QueueView(
            running=running[0] if running else None,
            queued=queued,
            lease_live=lease is not None and lease.live(self._clock()),
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
                joinable = runs.queued_like(asked.kind, asked.options_json, asked.options.item_id)
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
