"""The supervisor's domain: a request to run, the lease that authorises starting it — and the rules they carry.

A :class:`RunRequest` is one asked run in the queue; its rules are methods, so no service holds an
``if`` on its state: coalescing (:meth:`~RunRequest.joins`), the legal moves
(:meth:`~RunRequest.admit`, :meth:`~RunRequest.back_to_queue`, :meth:`~RunRequest.settle`) and
staleness (:meth:`~RunRequest.stale`). A move the state machine does not allow raises
:class:`RunRequestStateError`: a programming error of the caller, never an answer on the wire.

The :class:`Lease` is the supervisor's authority to start a run: live until its expiry, claimable
once it is not, or once its holder is gone.

Every timestamp is epoch ``time.time()``. The uid is typed (``RunUid``, in ``ids``).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Final

from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.supervisor.ids import RunUid

#: Seconds between two heartbeats of a running worker.
HEARTBEAT_INTERVAL_S: Final = 30.0

#: A running request whose last heartbeat is older than this many seconds is stale (three heartbeats).
STALE_AFTER_S: Final = 3 * HEARTBEAT_INTERVAL_S

#: How long a claimed or renewed lease lives, in seconds.
LEASE_TTL_S: Final = 60.0


class RunKind(StrEnum):
    """What a request asks for."""

    PIPELINE = "pipeline"
    RESCRAPE = "rescrape"


class RunTrigger(StrEnum):
    """Who asked: the codes the ``run_request.trigger`` column and the events carry."""

    COMPLETION = "completion"
    SAFETY_NET = "safety_net"
    MANUAL = "manual"
    WEB = "web"
    CLI = "cli"
    SCRAPE_RESOLVE = "scrape-resolve"


class RequestState(StrEnum):
    """Where a request stands in its life."""

    QUEUED = "queued"
    RUNNING = "running"
    SETTLED = "settled"


class Settlement(StrEnum):
    """How a request ended."""

    SUCCESS = "success"
    ERROR = "error"
    KILLED = "killed"
    INTERRUPTED = "interrupted"
    ABANDONED = "abandoned"


class WaitReason(StrEnum):
    """Why a queued request is not running yet; ``supervisor_absent`` is derived at read time, never stored."""

    BEHIND_RUN = "behind_run"
    PIPELINE_LOCK_HELD = "pipeline_lock_held"
    PAUSED = "paused"
    SUPERVISOR_ABSENT = "supervisor_absent"


@dataclass(frozen=True)
class RunOptions:
    """What a pipeline run or an item rescrape is asked to do.

    Attributes:
        dry_run: Preview the run without modifying files.
        skip_trailers: Skip the trailers step.
        continue_on_trailer_error: Carry on when the trailers step fails.
        no_post_maintenance: Skip the post-run maintenance.
        item_id: The indexer row of a rescrape; ``None`` for a pipeline run.
    """

    dry_run: bool = False
    skip_trailers: bool = False
    continue_on_trailer_error: bool = False
    no_post_maintenance: bool = False
    item_id: int | None = None


class RunRequestStateError(Exception):
    """A request was asked to make a move its state does not allow (a programming error, never a wire answer)."""


@dataclass
class RunRequest:
    """One asked run in the queue; it carries the rules of its own life.

    Attributes:
        uid: Its key.
        kind: A pipeline run or an item rescrape.
        trigger: Who asked.
        options_json: What was asked, canonical (sorted keys): two equal asks have equal text.
        asked_by: The account that asked.
        asked_at: When it was asked (epoch); the queue is FIFO on it.
        state: Queued, running or settled.
        admitted_at: When its worker was started (epoch); ``None`` while queued.
        worker_pid: Its worker's process id; ``None`` while queued.
        heartbeat_at: The worker's last sign of life (epoch); ``None`` while queued.
        settled_at: When it ended (epoch); ``None`` until settled.
        settlement: How it ended; ``None`` until settled.
        wait_reason: Why it waits, when it does; ``None`` otherwise.
    """

    uid: RunUid
    kind: RunKind
    trigger: RunTrigger
    options_json: str
    asked_by: AccountId
    asked_at: float
    state: RequestState = RequestState.QUEUED
    admitted_at: float | None = None
    worker_pid: int | None = None
    heartbeat_at: float | None = None
    settled_at: float | None = None
    settlement: Settlement | None = None
    wait_reason: WaitReason | None = None

    @classmethod
    def ask(
        cls, kind: RunKind, trigger: RunTrigger, options: RunOptions, asked_by: AccountId, now: float
    ) -> RunRequest:
        """Make a new request, queued.

        Args:
            kind: A pipeline run or an item rescrape.
            trigger: Who asks.
            options: What the run is asked to do.
            asked_by: The account that asks.
            now: The epoch of the ask.

        Returns:
            The queued request, under a fresh uid.
        """
        return cls(
            uid=RunUid(uuid.uuid4().hex),
            kind=kind,
            trigger=trigger,
            options_json=json.dumps(asdict(options), sort_keys=True),
            asked_by=asked_by,
            asked_at=now,
        )

    @property
    def options(self) -> RunOptions:
        """What was asked, parsed back from its canonical text."""
        return RunOptions(**json.loads(self.options_json))

    def joins(self, other: RunRequest) -> bool:
        """Whether this ask is answered by *other*, a request already in the queue.

        A pipeline run sweeps the whole staging, so an ask equal in kind and options to a request
        still queued joins it; a running one does not absorb it (new arrivals may have come). A
        rescrape joins a queued or a running request of the same item. Never a refusal: an ask that
        does not join is queued.

        Args:
            other: The request to join.

        Returns:
            ``True`` when *other* answers this ask.
        """
        if self.kind is not other.kind:
            return False
        if self.kind is RunKind.RESCRAPE:
            item_id = self.options.item_id
            return (
                item_id is not None
                and other.options.item_id == item_id
                and other.state in (RequestState.QUEUED, RequestState.RUNNING)
            )
        return other.state is RequestState.QUEUED and other.options_json == self.options_json

    def admit(self, pid: int, now: float) -> None:
        """Start it: ``queued`` → ``running``, under its worker's process id.

        Args:
            pid: The worker's process id.
            now: The epoch of the admission; also its first heartbeat.

        Raises:
            RunRequestStateError: If it is not queued.
        """
        self._require(RequestState.QUEUED, "admit")
        self.state = RequestState.RUNNING
        self.worker_pid = pid
        self.admitted_at = now
        self.heartbeat_at = now
        self.wait_reason = None

    def back_to_queue(self, reason: WaitReason) -> None:
        """Send it back: ``running`` → ``queued`` (its worker lost ``pipeline.lock``), waiting for *reason*.

        Args:
            reason: Why it waits.

        Raises:
            RunRequestStateError: If it is not running.
        """
        self._require(RequestState.RUNNING, "send back")
        self.state = RequestState.QUEUED
        self.worker_pid = None
        self.admitted_at = None
        self.heartbeat_at = None
        self.wait_reason = reason

    def settle(self, settlement: Settlement, now: float) -> None:
        """End it: ``running`` → ``settled``.

        Args:
            settlement: How it ended.
            now: The epoch it ended.

        Raises:
            RunRequestStateError: If it is not running.
        """
        self._require(RequestState.RUNNING, "settle")
        self.state = RequestState.SETTLED
        self.settlement = settlement
        self.settled_at = now

    def stale(self, now: float) -> bool:
        """Whether it is running and its worker has not shown a sign of life for three heartbeats.

        Args:
            now: The epoch to judge at.

        Returns:
            ``True`` when it is running and its last heartbeat is older than ``STALE_AFTER_S``.
        """
        if self.state is not RequestState.RUNNING or self.heartbeat_at is None:
            return False
        return now - self.heartbeat_at > STALE_AFTER_S

    def _require(self, state: RequestState, move: str) -> None:
        """Refuse a move out of any state but *state*.

        Args:
            state: The one state the move starts from.
            move: The move's name, for the message.

        Raises:
            RunRequestStateError: If the request is not in *state*.
        """
        if self.state is not state:
            raise RunRequestStateError(f"cannot {move} request {self.uid}: it is {self.state}, not {state}")


@dataclass(frozen=True)
class Lease:
    """The supervisor's authority to start a run: at most one exists.

    Attributes:
        holder_pid: The supervisor's process id.
        holder_host: The machine it runs on.
        taken_at: When it was first claimed (epoch).
        renewed_at: When it was last renewed (epoch).
        expires_at: When it lapses (epoch).
    """

    holder_pid: int
    holder_host: str
    taken_at: float
    renewed_at: float
    expires_at: float

    def live(self, now: float) -> bool:
        """Whether it still authorises its holder.

        Args:
            now: The epoch to judge at.

        Returns:
            ``True`` while *now* is before its expiry.
        """
        return self.expires_at > now

    def claimable(self, now: float, pid_alive: Callable[[int], bool]) -> bool:
        """Whether another supervisor may take it over: it has lapsed, or its holder is gone.

        Args:
            now: The epoch to judge at.
            pid_alive: Whether a process id names a live process of this machine.

        Returns:
            ``True`` when it is not live, or its holder process no longer runs.
        """
        return not self.live(now) or not pid_alive(self.holder_pid)
