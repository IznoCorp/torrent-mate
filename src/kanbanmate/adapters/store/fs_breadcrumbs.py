"""Agent-breadcrumb persistence for the filesystem state store.

Extracted from :mod:`kanbanmate.adapters.store.fs_store` (the Option-1 done-breadcrumb landed it at
the 1000-LOC hard ceiling — a behaviour-preserving move, mirroring the earlier
:mod:`kanbanmate.adapters.store.fs_status_state` / :mod:`kanbanmate.adapters.store.fs_intents`
extractions). The markers, their TTLs, their issue-keyed paths, and the poison-file degrade are
byte-identical to the rest of the store.

Two distinct issue-keyed breadcrumbs live here, both written SYNCHRONOUSLY by the agent before its
``claude`` process exits:

* ``advances/<issue>`` — the ✅/⚠️ discriminator (DESIGN §8.1.d): the agent moved its OWN card. Read
  by session-end to tell "advanced then finished" (✅, leave the sticky) from "died without
  advancing" (⚠️ finalize). Recency window :data:`_ADVANCE_TTL` (300 s).
* ``done/<issue>`` — the Option-1 clean-termination signal (#1): the agent ran ``kanban-done`` as
  its FINAL step. Read by the reaper to cleanly EXIT an ALIVE + IDLE session's REPL so the trailing
  ``; kanban-session-end`` fires (teardown → the card flows). Recency window :data:`_DONE_TTL`
  (1800 s — the reaper HEARTBEAT_TTL horizon, so a done signal a hung daemon never consumed still
  ages out).

A third issue-keyed marker (firm-exit) mirrors the done breadcrumb but counts the reaper's done-exit
attempts rather than a timestamp:

* ``end_attempts/<issue>`` = ``{"n": <int>}`` — the reaper's bounded-retry counter. It bumps once per
  ``end_session`` dispatch for a done + idle session; once the count reaches
  :data:`~kanbanmate.app.reaper.MAX_END_ATTEMPTS` the reaper escalates to ``kill_repl_process``. No
  TTL (it is reset by ``purge_ticket`` at teardown and by the reaper's defensive not-done reset).

This mixin is **self-contained** (it owns its TTL constants + path helpers + atomic-write
discipline), so mixing it into :class:`~kanbanmate.adapters.store.fs_store.FsStateStore` adds only
one import line there. Layering: imports only the standard library.
"""

from __future__ import annotations

import json
from pathlib import Path

# An advance breadcrumb is "recent" for this long (ported from the PoC ``state.py`` ``_ADVANCE_TTL``).
# It is the recency window the ✅/⚠️ split consults. DISTINCT from the reaper's ``HEARTBEAT_TTL``
# (1800 s agent-liveness reap window, DESIGN §8.3) — do not conflate the two TTLs.
_ADVANCE_TTL = 300.0

# A done breadcrumb is "recent" for this long. Sized to the reaper HEARTBEAT_TTL horizon (1800 s)
# so a done signal the daemon never consumed (e.g. a daemon restart between the kanban-done write
# and the next reap tick) still ages out instead of pinning forever. DISTINCT from _ADVANCE_TTL.
_DONE_TTL = 1800.0


class AgentBreadcrumbsMixin:
    """Agent-advance + agent-done breadcrumbs (mixed into the fs state store).

    Operates on the host store's ``root`` directory. The ``advances/`` and ``done/`` directories are
    created by the host store's ``__init__`` (so an empty store directory tree is well-formed); reads
    degrade gracefully on a missing/poison marker.

    Attributes:
        root: The state-store root directory (set by the host store's ``__init__``).
    """

    root: Path

    @staticmethod
    def _unlink(path: Path) -> None:  # pragma: no cover - provided by the host store
        """Remove *path* if it exists; no-op otherwise (host-store helper).

        Declared here only so mypy sees the member the mixin relies on; the concrete
        implementation is :meth:`~kanbanmate.adapters.store.fs_store.FsStateStore._unlink`.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Agent-advance breadcrumb (the ✅/⚠️ discriminator, DESIGN §8.1.d)
    # ------------------------------------------------------------------

    def _advance_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s advance breadcrumb.

        Keyed by the issue number (the breadcrumb-keying invariant, DESIGN §8.1.d), so the writer
        and the readers always agree on the marker path.
        """
        return self.root / "advances" / f"{issue_number}"

    def record_agent_advance(self, issue_number: int, *, now: float) -> None:
        """Drop a breadcrumb that the agent advanced its own card (DESIGN §8.1.d).

        Writes ``<root>/advances/<issue>`` = ``{"ts": now}``. Written SYNCHRONOUSLY before the
        agent's ``claude`` exits (the NEW analogue of the PoC ``kanban-move``), so session-end can
        tell "advanced then finished" (breadcrumb present → daemon finalized ✅) from "died without
        advancing" (breadcrumb absent → session-end finalizes ⚠️) without racing the asynchronous
        poll — exactly the PoC's race-closing design.

        **Breadcrumb-keying INVARIANT (load-bearing).** Keyed by the **issue number** — never a
        content node id. The WRITER (here) and the READERS (:meth:`recent_agent_advance` /
        :meth:`clear_agent_advance`) MUST share the identical issue key, or the ✅/⚠️ split mis-fires.
        Deliberate divergence from the PoC, which keyed by content node id.

        Args:
            issue_number: The ticket whose advance to record (the breadcrumb key).
            now: The wall-clock timestamp written into the breadcrumb.
        """
        self._advance_path(issue_number).write_text(json.dumps({"ts": now}))

    def recent_agent_advance(self, issue_number: int, *, now: float) -> bool:
        """Return whether a recent advance breadcrumb exists for ``issue_number``.

        ``True`` iff ``<root>/advances/<issue>`` exists and ``now - ts`` is within
        :data:`_ADVANCE_TTL` (300 s). That recency window is DISTINCT from the reaper's
        ``HEARTBEAT_TTL`` (1800 s, DESIGN §8.3) — the two TTLs are not the same knob.

        **Breadcrumb-keying INVARIANT (load-bearing, DESIGN §8.1.d).** Keyed by the **issue
        number** — the SAME key :meth:`record_agent_advance` wrote with. A key mismatch makes the
        breadcrumb always look "absent" and finalizes ⚠️ after a clean advance.

        Args:
            issue_number: The ticket whose breadcrumb to check (the key).
            now: The wall-clock timestamp the TTL is measured against.

        Returns:
            ``True`` iff a breadcrumb exists and is within the advance TTL.
        """
        path = self._advance_path(issue_number)
        if not path.exists():
            return False
        try:
            ts = float(json.loads(path.read_text()).get("ts", 0.0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return False
        return (now - ts) <= _ADVANCE_TTL

    def clear_agent_advance(self, issue_number: int) -> None:
        """Remove ``issue_number``'s advance breadcrumb (consumed by session-end).

        Unlinks ``<root>/advances/<issue>``; no-op when absent (the PoC's ``FileNotFoundError``
        swallow), so consuming an already-cleared (or never-written) breadcrumb never raises.

        **Breadcrumb-keying INVARIANT (load-bearing, DESIGN §8.1.d).** Keyed by the **issue
        number** — the SAME key the writer/recency-reader use. Session-end MUST call this with the
        identical issue key (never a content node id).

        Args:
            issue_number: The ticket whose breadcrumb to clear (the key).
        """
        self._unlink(self._advance_path(issue_number))

    # ------------------------------------------------------------------
    # Agent-done breadcrumb (the Option-1 clean-termination signal, #1)
    # ------------------------------------------------------------------

    def _done_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s done breadcrumb (issue-keyed, #1)."""
        return self.root / "done" / f"{issue_number}"

    def record_agent_done(self, issue_number: int, *, now: float) -> None:
        """Drop a breadcrumb that the agent ran ``kanban-done`` — its FINAL terminal step (#1).

        Writes ``<root>/done/<issue>`` = ``{"ts": now}``. Written SYNCHRONOUSLY by
        ``bin/kanban_done.py`` as the agent's last action (Option 1): it signals the agent has
        finished and the REPL may be cleanly exited. The reaper consumes it on its next tick — for an
        ALIVE + IDLE session it calls :meth:`~kanbanmate.ports.workspace.Sessions.end_session` so
        ``claude`` exits and the trailing ``; kanban-session-end <issue>`` fires (teardown → the card
        flows). Distinct from the ADVANCE breadcrumb (:meth:`record_agent_advance`): advance means "I
        moved my own card"; done means "I am finished, exit the REPL". Both keyed by the issue number.

        Args:
            issue_number: The ticket whose done-signal to record (the breadcrumb key).
            now: The wall-clock timestamp written into the breadcrumb.
        """
        self._done_path(issue_number).write_text(json.dumps({"ts": now}))

    def recent_agent_done(self, issue_number: int, *, now: float) -> bool:
        """Return whether a recent done breadcrumb exists for ``issue_number`` (#1).

        ``True`` iff ``<root>/done/<issue>`` exists and ``now - ts`` is within :data:`_DONE_TTL`
        (1800 s — the reaper HEARTBEAT_TTL horizon, so a done signal a hung daemon never consumed
        still ages out instead of pinning the slot forever). The reaper reads this to decide whether
        to exit an alive + idle session. Degrades to ``False`` on a corrupt/unreadable marker (no
        raise — a poison done file must never wedge the sweep).

        Args:
            issue_number: The ticket whose done breadcrumb to check (the key).
            now: The wall-clock timestamp the TTL is measured against.

        Returns:
            ``True`` iff a breadcrumb exists and is within the done TTL.
        """
        path = self._done_path(issue_number)
        if not path.exists():
            return False
        try:
            ts = float(json.loads(path.read_text()).get("ts", 0.0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return False
        return (now - ts) <= _DONE_TTL

    def clear_agent_done(self, issue_number: int) -> None:
        """Remove ``issue_number``'s done breadcrumb (no-op when absent).

        Unlinks ``<root>/done/<issue>``; no-op when absent. Called defensively — the breadcrumb is
        normally consumed by ``purge_ticket`` at teardown (so it does not leak after the session
        ends).

        Args:
            issue_number: The ticket whose done breadcrumb to clear (the key).
        """
        self._unlink(self._done_path(issue_number))

    # ------------------------------------------------------------------
    # Reaper done-exit attempt counter (firm-exit kill-escalation)
    # ------------------------------------------------------------------

    def _end_attempts_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s done-exit attempt counter (issue-keyed)."""
        return self.root / "end_attempts" / f"{issue_number}"

    def get_end_attempts(self, issue_number: int) -> int:
        """Return the persisted done-exit attempt count for ``issue_number`` (0 when absent/corrupt).

        Reads ``<root>/end_attempts/<issue>`` = ``{"n": n}``. Degrades a missing or corrupt marker to
        ``0`` (no raise) so a poison file never wedges the reaper sweep (mirrors :meth:`recent_agent_done`).

        Args:
            issue_number: The ticket whose attempt count to read (the marker key).

        Returns:
            The persisted attempt count, or ``0`` when absent / unreadable / corrupt.
        """
        path = self._end_attempts_path(issue_number)
        if not path.exists():
            return 0
        try:
            return int(json.loads(path.read_text()).get("n", 0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return 0

    def bump_end_attempt(self, issue_number: int) -> int:
        """Increment and return ``issue_number``'s done-exit attempt counter (starts at 1).

        Writes ``<root>/end_attempts/<issue>`` = ``{"n": n}`` where ``n`` is the prior count
        (:meth:`get_end_attempts`, which degrades a corrupt/absent file to ``0``) plus one. The reaper
        bumps this each time it dispatches ``end_session`` for a done + idle session; once the count
        reaches :data:`~kanbanmate.app.reaper.MAX_END_ATTEMPTS` it escalates to ``kill_repl_process``.

        Args:
            issue_number: The ticket whose attempt counter to bump (the marker key).

        Returns:
            The new (incremented) attempt count.
        """
        n = self.get_end_attempts(issue_number) + 1
        self._end_attempts_path(issue_number).write_text(json.dumps({"n": n}))
        return n

    def clear_end_attempts(self, issue_number: int) -> None:
        """Remove ``issue_number``'s done-exit attempt counter (no-op when absent).

        Unlinks ``<root>/end_attempts/<issue>``; no-op when absent. Called on the escalation-clear
        and the defensive not-done reset (so a future agent on the same ticket starts clean), and by
        ``purge_ticket`` at teardown (so the counter never leaks).

        Args:
            issue_number: The ticket whose attempt counter to clear (the marker key).
        """
        self._unlink(self._end_attempts_path(issue_number))
