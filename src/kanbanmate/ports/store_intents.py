"""Board-mutation intent queue port (cockpit PR2 — the daemon is the sole writer/executor).

Extracted from :mod:`kanbanmate.ports.store` (LOC-ceiling headroom — store.py sat at 996/1000, so
adding the cockpit result-GC ``gc_intent_results`` stub there would have breached the hard ceiling).
:class:`~kanbanmate.ports.store.StateStore` composes this Protocol (``StateStore(HealthStateStore,
IntentStore, Protocol)``), so the concrete filesystem adapter
(:mod:`kanbanmate.adapters.store.fs_intents`) satisfies the SAME surface — only its declaration moved
here.

The CLI/agent enqueues an intent (``intents/<id>.json``); the daemon's ``drain_intents`` tick step is
the only consumer/executor and writes a result (``intents/<id>.result.json``) the CLI ``--wait``
polls.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class IntentStore(Protocol):
    """Persisted board-mutation intent queue + their results (cockpit PR2)."""

    def enqueue_intent(self, intent_id: str, payload: Mapping[str, object]) -> None:
        """Persist a pending board-mutation intent atomically (the CLI/agent enqueue side).

        The daemon's ``drain_intents`` tick step is the ONLY consumer/executor. The payload is the
        JSON-serialisable intent mapping (``kind`` / ``issue`` / ``args`` / ``requested_at`` /
        ``caller``).

        Args:
            intent_id: The intent id (its marker filename stem).
            payload: The JSON-serialisable intent mapping.
        """
        ...

    def load_intent(self, intent_id: str) -> dict[str, object] | None:
        """Return the pending intent payload, or ``None`` when absent/corrupt (poison-tolerant)."""
        ...

    def clear_intent(self, intent_id: str) -> None:
        """Remove the pending intent marker (the drain clears it after writing the result)."""
        ...

    def list_pending_intents(self) -> tuple[str, ...]:
        """Return the ids of all pending intents (result files excluded), or ``()`` when none.

        The drain orders these by the intents' ``requested_at`` before executing; this returns them
        in a stable (lexicographic) order and degrades to ``()`` when the queue is absent/empty.
        """
        ...

    def save_intent_result(self, intent_id: str, payload: Mapping[str, object]) -> None:
        """Persist an intent's result atomically (the CLI ``--wait`` polls it).

        Args:
            intent_id: The intent id whose result to write.
            payload: The JSON-serialisable result mapping (``state`` / ``detail``).
        """
        ...

    def gc_intent_results(self, *, now: float, ttl: float) -> None:
        """TTL-expire stale ``intents/<id>.result.json`` files (cockpit DESIGN §10 Result GC).

        The cockpit design promised a cheap housekeeping pass so ``intents/`` does not grow
        unbounded, but no path ever deleted a result file: :meth:`clear_intent` removes only the
        PENDING marker, and the CLI ``--wait`` never deleted the result it read. This bounded sweep
        unlinks any ``*.result.json`` whose mtime is older than ``now - ttl``. FAIL-SOFT: a missing
        directory is a no-op and any per-file stat/unlink error is swallowed — the GC must never
        raise into the tick.

        Args:
            now: The current wall-clock time (epoch seconds) the TTL window is measured against.
            ttl: The maximum age (seconds) a result file may reach before it is unlinked.
        """
        ...
