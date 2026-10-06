"""The supervisor's domain events: a run was queued, admitted, settled.

Codes and ids only, no text (the stream carries them as they are). Registered by being imported
(``Event.__init_subclass__``), which ``personalscraper.app.services`` does like the accounts' E8.
"""

from __future__ import annotations

from dataclasses import dataclass

from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import RunKind, RunTrigger, Settlement
from personalscraper.core.event_bus import Event


@dataclass(frozen=True, kw_only=True)
class RunQueued(Event):
    """A run was asked: queued as a new request, or joined to one already queued.

    Attributes:
        uid: The request that answers the ask.
        kind: A pipeline run or an item rescrape.
        trigger: Who asked.
        joined: ``True`` when the ask joined an existing request instead of queueing a new one.
    """

    uid: RunUid
    kind: RunKind
    trigger: RunTrigger
    joined: bool


@dataclass(frozen=True, kw_only=True)
class RunAdmitted(Event):
    """The supervisor started a request's worker.

    Attributes:
        uid: The request admitted.
        kind: A pipeline run or an item rescrape.
    """

    uid: RunUid
    kind: RunKind


@dataclass(frozen=True, kw_only=True)
class RunSettled(Event):
    """A request ended.

    Attributes:
        uid: The request settled.
        kind: A pipeline run or an item rescrape.
        settlement: How it ended.
    """

    uid: RunUid
    kind: RunKind
    settlement: Settlement
