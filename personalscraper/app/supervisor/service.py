"""``RunService``: the one in-process enqueue every starter of a run converges on.

The web, the CLI and the watcher ask a run (or an item rescrape) here; the supervisor's lease is
the only authority that starts it. An ask never fails for lack of room: an equal ask waiting in the
queue answers it (it is joined, the same uid comes back), else it is queued. What joins what is the
model's rule (:meth:`~personalscraper.app.supervisor.model.RunRequest.joins`); this service looks
for the candidate and writes, in one ``BEGIN IMMEDIATE`` transaction so two concurrent equal asks
cannot both queue.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import RequestState, RunKind, RunOptions, RunRequest, RunTrigger
from personalscraper.core.identity import ItemId
from personalscraper.logger import get_logger

log = get_logger("app.supervisor.service")

#: The contract's ``PipelineState`` subset an ask is answered with.
PipelineAnswer = Literal["queued", "running"]


@dataclass(frozen=True)
class RunAsked:
    """The answer to an ask.

    Attributes:
        uid: The request that answers it: the new one, or the one joined.
        state: ``running`` only when the joined request already runs (a rescrape), else ``queued``.
        joined: ``True`` when the ask joined a request already in the queue instead of queueing one.
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
            uid: The request's key when the caller already promised one (it is kept); ignored when
                the ask joins a request that already has its own.

        Returns:
            The request answering the ask.

        Raises:
            AppForbidden: ``right.missing``, ``instance.forbidden_write`` or ``instance.read_only``,
                before anything is written.
        """
        return self._ask(RunRequest.ask(RunKind.PIPELINE, trigger, options, actor.account_id, self._clock(), uid))

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

    def _ask(self, asked: RunRequest) -> RunAsked:
        """Queue a freshly made ask, or answer it with the request it joins; one transaction.

        Args:
            asked: The ask, made by :meth:`RunRequest.ask`.

        Returns:
            The answer.
        """
        runs = self._store.runs
        with self._store.immediate():
            joinable = runs.queued_like(asked.kind, asked.options_json, asked.options.item_id)
            if joinable is None and asked.kind is RunKind.RESCRAPE:
                joinable = next((request for request in runs.running() if asked.joins(request)), None)
            if joinable is not None and asked.joins(joinable):
                answer = RunAsked(
                    uid=joinable.uid,
                    state="running" if joinable.state is RequestState.RUNNING else "queued",
                    joined=True,
                )
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
