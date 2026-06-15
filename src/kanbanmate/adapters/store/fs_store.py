"""Filesystem-backed :class:`~kanbanmate.ports.store.StateStore` adapter.

Ported from the PoC ``state.py`` persistence layer. State is stored as JSON
files under ``<root>/state/<issue>.json``. Slot reservation uses advisory
``flock`` serialisation (mirroring the PoC's ``engine/cap.py``) with an
``O_EXCL`` defence-in-depth layer so two daemons cannot grab the same ticket
slot. Writes are atomic via temp-file + ``os.replace`` — a concurrent reader
(the reaper) never observes a torn write.

Layering: adapters MAY import ``kanbanmate.ports.*`` and ``kanbanmate.core.*``;
MUST NOT import ``app``, ``daemon``, or ``cli``.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, replace
from typing import cast
from pathlib import Path

import fcntl
import glob
import json
import logging
import os
import time

from kanbanmate.adapters.store.fs_status_state import StatusUpdateStateMixin
from kanbanmate.ports.store import LIVE_STATUSES, TicketState, TicketStatus

logger = logging.getLogger(__name__)


def _warn_corrupt_state(path: Path, err: Exception) -> None:
    """Emit ONE breadcrumb naming a corrupt/unreadable state file (#17 PORT, routed via logger #8).

    Port of the PoC ``state.py`` ``iter_states`` diagnostic (state.py:333-387): a single
    truncated/partial ``state/<n>.json`` must be SKIPPED (not raise) so one poison file
    cannot wedge the reaper sweep — but the operator still needs a breadcrumb naming the
    offending file, which NEW had dropped (the skip went silent).

    The PoC printed to stderr; #8 routes this through the module logger instead, so the
    breadcrumb lands in ``daemon.jsonl`` where ``kanban logs`` reads it (a bare stderr print is
    swallowed into PM2 stdout and invisible to the operator's normal log surface).

    Args:
        path: The corrupt/unreadable state file that is being skipped.
        err: The exception raised while loading it (surfaced in the diagnostic).
    """
    logger.warning("skipping corrupt state file %s: %s", path, err)


# An advance breadcrumb is "recent" for this long (ported from the PoC
# ``state.py`` ``_ADVANCE_TTL``). It is the recency window the ✅/⚠️ split
# consults. DISTINCT from the reaper's ``HEARTBEAT_TTL`` (1800 s agent-liveness
# reap window, DESIGN §8.3) — do not conflate the two TTLs.
_ADVANCE_TTL = 300.0

# Per-item AUTO/bot move rate-limit sliding-window width in seconds (ported
# from the PoC ``state.py`` ``_RATE_WINDOW``). When an issue has accumulated >=
# the per-hour cap of AUTO/bot moves within this window, the daemon parks the
# ticket in the Blocked column (DESIGN §6 runaway-loop backstop).
# DISTINCT from ``_ADVANCE_TTL`` (300 s breadcrumb recency) AND from the
# reaper's ``HEARTBEAT_TTL`` (1800 s agent-liveness reap window, DESIGN §8.3)
# — the three TTLs govern different subsystems and must stay separate knobs.
_RATE_WINDOW = 3600.0


class FsStateStore(StatusUpdateStateMixin):
    """Filesystem-backed :class:`~kanbanmate.ports.store.StateStore` implementation.

    Persists per-ticket runtime state as JSON files under ``<root>/state/``.
    Slot reservation (concurrency cap) is managed under ``<root>/slots/`` with
    advisory ``flock`` serialisation ported from the PoC ``engine/cap.py``.

    The rolling project status-update markers (``<root>/status/``) live in
    :class:`~kanbanmate.adapters.store.fs_status_state.StatusUpdateStateMixin`,
    mixed in here (a behaviour-preserving extraction under the 1000-LOC ceiling,
    phase-24 §24.2); this class still satisfies the FULL ``StateStore`` Protocol.

    Attributes:
        root: The root directory for all persisted state (default ``~/.kanban/``).
    """

    def __init__(self, root: str | Path | None = None) -> None:
        """Initialise the state store.

        Args:
            root: Filesystem root for persisted state. Defaults to
                ``~/.kanban/`` (via :func:`Path.expanduser`). Pass a
                ``tmp_path`` in tests to isolate state.
        """
        if root is None:
            root = Path("~/.kanban/").expanduser()
        self.root = Path(root)
        (self.root / "state").mkdir(parents=True, exist_ok=True)
        (self.root / "slots").mkdir(parents=True, exist_ok=True)
        # The advance-breadcrumb directory (DESIGN §8.1.d); one marker per issue.
        (self.root / "advances").mkdir(parents=True, exist_ok=True)
        # Per-issue AUTO/bot move rate-limit history (DESIGN §6); one JSON list
        # per issue.  Issue-keyed — a deliberate divergence from the PoC, which
        # keyed ``moves/item_<item>.json`` by content node id.
        (self.root / "moves").mkdir(parents=True, exist_ok=True)
        # Per-(issue,key) fix-CI retry counter ledger (DESIGN §6 bounded loop
        # cap, N=2).  One counter file per (issue, key) pair; issue-keyed
        # (boundary 2 — a deliberate divergence from the PoC, which keyed by
        # content node id).
        (self.root / "retries").mkdir(parents=True, exist_ok=True)
        # Per-issue queue markers for capped launches (DESIGN §7); one marker
        # per enqueued ticket.  Issue-keyed — matches OLD's already-issue-keyed
        # ``queue/ticket-<issue>`` layout.
        (self.root / "queue").mkdir(parents=True, exist_ok=True)
        # Per-issue check-script output marker (15.6 / 15.7); one file per issue,
        # holding the latest check-script output so the fix-CI launch can fill
        # ``{{script_output}}``. Issue-keyed like every other per-ticket marker.
        (self.root / "script_output").mkdir(parents=True, exist_ok=True)
        # Rolling project status-update markers (phase-24 §24.2); BOARD-WIDE (not
        # per-issue): the rolling update's node id, the last-posted body hash (for
        # on-change diffing), and the bounded recent-events ring (≤10 newest).
        (self.root / "status").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # StateStore Protocol methods
    # ------------------------------------------------------------------

    def load(self, issue_number: int) -> TicketState | None:
        """Load the persisted state for ``issue_number``.

        Args:
            issue_number: The ticket's issue number.

        Returns:
            The :class:`TicketState`, or ``None`` when no state file exists
            (first contact, or after a Cancel teardown purged it) **or when the
            file is corrupt/unreadable/partial/schema-broken** (bad JSON, unknown
            status enum, renamed/extra field — any of these degrade to the no-state
            path so callers stay idempotent, with a named stderr breadcrumb).
        """
        path = self._state_path(issue_number)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as err:
            # Poison file → degrade to the no-state path (idempotent callers), emit the named
            # breadcrumb (#17), AND quarantine it so the re-parse noise stops (#11).
            self._skip_corrupt_state(path, err)
            return None
        try:
            data["status"] = TicketStatus(data["status"])
        except (ValueError, KeyError) as err:
            # Schema-corrupt status field (unknown enum value / missing key) — valid JSON but the
            # status is unreadable. Skip + breadcrumb + quarantine (#12 / M3, #11).
            self._skip_corrupt_state(path, err)
            return None
        try:
            return TicketState(**data)
        except TypeError as err:
            # Schema-corrupt fields (renamed key / extra unknown field) — the dataclass constructor
            # rejected the payload. Same degrade contract: skip + breadcrumb + quarantine (#11).
            self._skip_corrupt_state(path, err)
            return None

    def save(self, state: TicketState) -> None:
        """Persist ``state`` atomically via temp-file + ``os.replace``.

        The write goes to a temp file in the same directory, then is atomically
        renamed over the target. A concurrent reader (the reaper) therefore
        only ever observes a complete file — never a torn/partial write.

        Args:
            state: The ticket state to persist; its ``issue_number`` is the key.
        """
        target = self._state_path(state.issue_number)
        tmp = target.with_name(f"{state.issue_number}.json.{os.getpid()}.tmp")
        payload = asdict(state)
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, target)

    def touch_heartbeat(self, issue_number: int, now: float) -> None:
        """Refresh a running ticket's liveness heartbeat to ``now``.

        **NO-OP when the state is absent**: a late PostToolUse hook firing
        after a Cancel teardown must never resurrect a purged ticket's
        runtime state (DESIGN §8.3 no-resurrection).

        When the state is present, performs a read-modify-atomic-write cycle.

        Args:
            issue_number: The ticket whose heartbeat to refresh.
            now: The wall-clock timestamp to record as the new heartbeat.
        """
        current = self.load(issue_number)
        if current is None:
            # State purged (e.g. Cancel teardown) — never recreate it from a
            # late hook (DESIGN §8.3 no-resurrection).
            return
        # Create a new frozen instance with only the heartbeat advanced;
        # ``replace`` carries EVERY other field forward (including the widened
        # stage/profile/mode/started/worktree, DESIGN §8.1.d) so a heartbeat
        # touch never silently drops the launch metadata the finalizers read.
        updated = replace(current, heartbeat=now)
        self.save(updated)

    def release_slot(self, issue_number: int) -> None:
        """Release the concurrency-cap slot marker AND the retry counters for ``issue_number``.

        Unlinks ``slots/ticket-<issue>`` AND every ``retries/<issue>__*`` marker
        (glob + unlink-if-exists, idempotent — called on both cancel and clean-exit
        paths).  A cancelled or finished ticket must leave no stale retry ledger
        (the per-(issue, key) fix-CI counters are torn down alongside the slot).

        It does NOT purge the runtime state, the advance breadcrumb, the queue
        marker, or the move rate-limit history — those are purged by the
        exhaustive :meth:`purge_ticket`.  The slot + retries release is kept
        DISTINCT from the exhaustive purge so a launch-failure leak-safety path
        can free a slot + retries WHILE KEEPING the queued ticket's marker for a
        later retry.

        **Pivot-erased markers (#22 doc).** Several per-concern dirs the PoC's
        exhaustive ``purge_ticket`` (state.py:427-479) cleared have NO on-disk
        analogue in NEW and need no teardown here: ``columns/`` (the per-item
        column ledger collapsed into the in-memory diff baseline — #20),
        ``botmoves/`` (the on-disk bot-move dedup collapsed into the in-memory
        :class:`~kanbanmate.core.antiloop.AntiLoopState` — #19), and OLD's
        webhook-era ``processed/`` / ``inflight/`` (mooted by the polling pivot
        — no per-delivery dedup). ``retries/`` DOES still exist and IS purged
        (above + in :meth:`purge_ticket`). The in-memory rate-limit history that
        replaced ``botmoves``/``moves`` (#22) is reset by
        :func:`kanbanmate.core.antiloop.forget` on the ABANDONMENT path — the
        Cancel ``TeardownAction`` in :func:`kanbanmate.app.tick.tick` — since this
        filesystem method cannot reach that volatile state. (The reaper's
        ``keep_budgets=True`` teardown deliberately does NOT forget: the ticket may
        continue and the in-memory runaway-loop accumulator must survive — see the
        NOTE in :func:`kanbanmate.app.reaper.reap_stale_agents`.) The
        ``queue/ticket-<issue>`` purge is the QUEUE feature's concern (see
        :meth:`purge_ticket` / :meth:`clear_queued`) — not duplicated here.

        No-raise / idempotent: releasing an already-released slot or an absent
        retry marker is a silent no-op.

        Args:
            issue_number: The ticket whose concurrency-cap slot + retry markers
                to release.
        """
        self._unlink(self.root / "slots" / f"ticket-{issue_number}")
        # Purge every per-(issue, key) fix-CI retry counter for this issue
        # (idempotent — a cancelled/finished ticket leaves no stale retry ledger).
        # glob.escape so a metachar in a sibling issue can never widen the pattern
        # (over-match defence ported from OLD's purge_ticket).
        for marker in (self.root / "retries").glob(f"{glob.escape(str(issue_number))}__*"):
            self._unlink(marker)

    def purge_ticket(self, issue_number: int, *, keep_budgets: bool = False) -> None:
        """Idempotent ticket teardown purge (port of the PoC ``purge_ticket``).

        Removes the per-ticket RUNTIME markers for ``issue_number`` always:
          * ``state/<issue>.json``         — runtime state
          * ``slots/ticket-<issue>``       — concurrency-cap slot marker
          * ``advances/<issue>``           — agent-advance breadcrumb
          * ``queue/ticket-<issue>``       — relaunch queue marker

        And the per-issue BUDGET markers CONDITIONALLY (only when
        ``keep_budgets`` is ``False`` — the default, exhaustive teardown):
          * ``moves/<issue>.json``         — per-issue move rate-limit history
          * ``retries/<issue>__*``         — every per-(issue, key) fix-CI retry
                                             counter (glob with ``glob.escape``
                                             so a metachar in the issue can never
                                             widen the pattern — over-match
                                             defence ported from OLD's
                                             ``purge_ticket``).

        **Why the two budget markers are conditional (13.8 — PoC fidelity).**
        ``moves/<issue>.json`` (the §6 per-hour rate-limit) and
        ``retries/<issue>__*`` (the fix-CI loop budget) are *per-issue budgets*
        that must SURVIVE the ticket's lifecycle (sessions, reaps) so the durable
        rate-limit can actually ACCUMULATE across reaps; they are torn down ONLY
        when the ticket is truly abandoned. The PoC kept these across
        reaps/sessions (the reaper's ``_move_to_blocked`` used slot-only
        ``release_slot``; ``end_session`` set status=idle + slot-only release) and
        purged them ONLY on the deliberate Cancel / reset. So:

          * ``keep_budgets=True`` — the ticket MAY continue (the reaper's
            stale-agent teardown and ``kanban session-end``): purge the runtime
            markers but PRESERVE ``moves/`` + ``retries/`` so the rate-limit /
            fix-CI budgets accumulate across the gap. WITHOUT this, the reaper's
            teardown wiped ``moves/<issue>.json`` one step BEFORE the same reap
            read it for the rate-limit gate, so the durable §6 counter perpetually
            reset to 1 and ``_rate_limited`` could never observe ``>= cap``.
          * ``keep_budgets=False`` (default) — the ticket is ABANDONED (Cancel via
            :class:`~kanbanmate.app.actions.TeardownAction`, or Cancel→Backlog
            re-arm via :class:`~kanbanmate.app.actions.ResetAction`): the FULL
            exhaustive purge, dropping the budgets too so a future ticket reusing
            the same issue starts from a clean slate.

        Each removal is independently guarded (no-raise on absent) so a
        teardown→reset double-purge never raises — idempotent per OLD's
        ``purge_ticket`` contract. The advance-breadcrumb purge is
        unlink-if-exists / no-raise: on a clean exit, session-end (8.1.f)
        already called ``clear_agent_advance``, so the subsequent purge here
        silently no-ops; on the cancel path it is the purge that removes it.
        Safe on BOTH paths.

        Args:
            issue_number: The ticket whose markers to purge.
            keep_budgets: When ``True``, PRESERVE the per-issue budget markers
                (``moves/`` + ``retries/``) and purge only the runtime markers
                (reaper stale-agent teardown + session-end — the ticket may
                continue). When ``False`` (default), the exhaustive teardown that
                also drops the budgets (Cancel / reset — the ticket is abandoned).
        """
        self._unlink(self._state_path(issue_number))
        self._unlink(self.root / "slots" / f"ticket-{issue_number}")
        # Purge the advance breadcrumb too (idempotent / no-raise): a cancelled
        # ticket must not leave a stale breadcrumb that a later session-end could
        # misread as a clean advance.
        self._unlink(self._advance_path(issue_number))
        # ── widened purge (port of OLD purge_ticket's issue-keyed targets) ──
        # Queue marker — a ticket parked in the queue at Cancel time must not
        # be drained later.
        self._unlink(self._queue_path(issue_number))
        # Per-issue BUDGET markers — preserved when keep_budgets is True so the
        # durable §6 rate-limit / fix-CI loop budgets survive a reap or an
        # inter-session idle and can ACCUMULATE (13.8 PoC fidelity); torn down
        # only on a true abandonment (Cancel / reset).
        if keep_budgets:
            return
        # Per-issue move rate-limit history — a cancelled ticket leaves no
        # stale history that could block a future ticket reusing the same issue.
        self._unlink(self._moves_path(issue_number))
        # Per-(issue,key) fix-CI retry counters — glob the issue prefix with
        # glob.escape so a metachar in a sibling issue can never widen the
        # pattern (over-match defence ported from OLD's purge_ticket).
        for marker in (self.root / "retries").glob(f"{glob.escape(str(issue_number))}__*"):
            self._unlink(marker)

    def kill_switch_active(self) -> bool:
        """Return whether the kill-switch sentinel (``<root>/PAUSE``) is present.

        The operator drops a ``PAUSE`` file under the store root
        (``~/.kanban/PAUSE`` in production) to halt all launches (DESIGN §10 /
        H5). The tick reads this at the start of every cycle, so dropping or
        removing the file takes effect on the very next poll.

        This is a **pure read**: it touches no state, raises nothing on
        absence, and has no side effects — a missing sentinel simply means the
        switch is off.

        Returns:
            ``True`` iff the ``PAUSE`` sentinel file exists under the store
            root, ``False`` otherwise.
        """
        return (self.root / "PAUSE").exists()

    def list_running(self) -> tuple[TicketState, ...]:
        """Return the persisted states of every currently tracked ticket.

        Corrupt files (non-JSON, unknown status enum, missing/renamed/extra
        fields) are silently skipped so a single poison file cannot wedge the
        reaper sweep — mirroring the PoC's ``iter_states`` defensive parsing
        (H1 safety-net). Every skip emits a named stderr breadcrumb so a
        schema-broken file that would silently drop a stale agent from the
        reaper's source of truth is not lost (#17 → #12/M3).

        Returns:
            An immutable tuple of every persisted :class:`TicketState` whose
            ``status`` is a LIVE status — :attr:`TicketStatus.RUNNING` OR
            :attr:`TicketStatus.WAITING` (an agent awaiting human input is still
            alive; the reaper must keep observing it to detect resume / death,
            phase-27 §B).
        """
        states: list[TicketState] = []
        for path in sorted((self.root / "state").glob("*.json")):
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as err:
                # A single poison file must not abort the reaper sweep (H1) — skip it, name it via
                # the logger (#17/#8), AND quarantine it so the sweep stops re-reading it (#11).
                self._skip_corrupt_state(path, err)
                continue
            try:
                data["status"] = TicketStatus(data["status"])
            except (ValueError, KeyError) as err:
                self._skip_corrupt_state(path, err)
                continue
            try:
                ts = TicketState(**data)
            except TypeError as err:
                self._skip_corrupt_state(path, err)
                continue
            # Both RUNNING and WAITING are LIVE — the reaper iterates this list and must keep
            # observing a WAITING (awaiting-human) agent to restore it on a heartbeat refresh or
            # reap it on a dead session (phase-27 §B). IDLE (the terminal pre-teardown write) stays
            # excluded so a reaped zombie is invisible to the sweep (#21).
            if ts.status in LIVE_STATUSES:
                states.append(ts)
        return tuple(states)

    def list_all(self) -> tuple[TicketState, ...]:
        """Return every persisted ticket regardless of status.

        Iterates every ``state/<n>.json`` and loads each :class:`TicketState`
        WITHOUT filtering for :attr:`TicketStatus.RUNNING` — the PoC
        ``_known_issues`` analogue. Corrupt files (non-JSON, unknown status enum,
        missing/renamed/extra fields) are silently skipped, mirroring
        :meth:`list_running`'s defensive parsing (H1 safety-net) with named stderr
        breadcrumbs for every skip.

        Returns:
            An immutable tuple of every persisted :class:`TicketState`, sorted
            by issue number (ascending).
        """
        states: list[TicketState] = []
        for path in sorted((self.root / "state").glob("*.json")):
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as err:
                # Same corrupt-skip + breadcrumb + quarantine (#17/#11) as list_running: one poison
                # file must not wedge the full-state iterator (and must not re-noise every sweep).
                self._skip_corrupt_state(path, err)
                continue
            try:
                data["status"] = TicketStatus(data["status"])
            except (ValueError, KeyError) as err:
                self._skip_corrupt_state(path, err)
                continue
            try:
                ts = TicketState(**data)
            except TypeError as err:
                self._skip_corrupt_state(path, err)
                continue
            states.append(ts)
        return tuple(states)

    # ------------------------------------------------------------------
    # Per-dispatch append-only audit log (port of PoC audit.append_dispatch)
    # ------------------------------------------------------------------

    def append_dispatch(self, record: dict[str, object]) -> None:
        """Append one JSON line per dispatch to ``<root>/log/dispatch.jsonl``.

        Ported verbatim-in-spirit from the PoC ``audit.append_dispatch``
        (audit.py:24-30): ``mkdir -p <root>/log``, shallow-copy the record, stamp
        ``logged_at`` with ``time.time()``, ``json.dumps(..., ensure_ascii=False)``
        so a non-ASCII repo/title round-trips intact, then APPEND the line + ``"\n"``
        to the log (utf-8). The write is an APPEND (``open(path, "a")``), NOT the
        atomic temp-file + ``os.replace`` every other write uses — the audit log is
        append-only by design (mirroring the PoC exactly).

        **Determinism split (load-bearing).** ``logged_at`` is stamped here with
        ``time.time()`` so the port contract stays clock-free (matching the PoC),
        while the caller (:class:`~kanbanmate.app.actions.LaunchAction`) puts
        ``ts=now`` (the injected clock's now) IN the record — so a test asserts
        ``ts`` deterministically and only checks ``logged_at`` is a float.

        Args:
            record: The launch record (issue / repo / to-column / profile /
                session uuid / worktree / tmux / ts) — a JSON-serialisable dict.
        """
        log_dir = self.root / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        # Shallow-copy + stamp so a caller's literal dict is never mutated.
        stamped = dict(record)
        stamped["logged_at"] = time.time()
        line = json.dumps(stamped, ensure_ascii=False)
        # Append-only (not atomic-replace): the audit log accumulates one line
        # per dispatch, port of the PoC's open("a") write.
        with (log_dir / "dispatch.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # ------------------------------------------------------------------
    # Agent-advance breadcrumb (the ✅/⚠️ discriminator, DESIGN §8.1.d)
    # ------------------------------------------------------------------

    def record_agent_advance(self, issue_number: int, *, now: float) -> None:
        """Drop a breadcrumb that the agent advanced its own card (DESIGN §8.1.d).

        Writes ``<root>/advances/<issue>`` = ``{"ts": now}``. Written
        SYNCHRONOUSLY before the agent's ``claude`` exits (the NEW analogue of
        the PoC ``kanban-move``), so session-end can tell "advanced then
        finished" (breadcrumb present → daemon finalized ✅) from "died without
        advancing" (breadcrumb absent → session-end finalizes ⚠️) without
        racing the asynchronous poll — exactly the PoC's race-closing design.

        **Breadcrumb-keying INVARIANT (load-bearing).** Keyed by the **issue
        number** — never a content node id. The WRITER (here) and the READERS
        (:meth:`recent_agent_advance` / :meth:`clear_agent_advance`) MUST share
        the identical issue key, or the ✅/⚠️ split mis-fires. Deliberate
        divergence from the PoC, which keyed by content node id.

        Args:
            issue_number: The ticket whose advance to record (the breadcrumb key).
            now: The wall-clock timestamp written into the breadcrumb.
        """
        self._advance_path(issue_number).write_text(json.dumps({"ts": now}))

    def recent_agent_advance(self, issue_number: int, *, now: float) -> bool:
        """Return whether a recent advance breadcrumb exists for ``issue_number``.

        ``True`` iff ``<root>/advances/<issue>`` exists and ``now - ts`` is
        within :data:`_ADVANCE_TTL` (300 s). That recency window is DISTINCT
        from the reaper's ``HEARTBEAT_TTL`` (1800 s, DESIGN §8.3) — the two TTLs
        are not the same knob.

        **Breadcrumb-keying INVARIANT (load-bearing, DESIGN §8.1.d).** Keyed by
        the **issue number** — the SAME key :meth:`record_agent_advance` wrote
        with. A key mismatch makes the breadcrumb always look "absent" and
        finalizes ⚠️ after a clean advance.

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

        Unlinks ``<root>/advances/<issue>``; no-op when absent (the PoC's
        ``FileNotFoundError`` swallow), so consuming an already-cleared (or
        never-written) breadcrumb never raises.

        **Breadcrumb-keying INVARIANT (load-bearing, DESIGN §8.1.d).** Keyed by
        the **issue number** — the SAME key the writer/recency-reader use.
        Session-end MUST call this with the identical issue key (never a content
        node id).

        Args:
            issue_number: The ticket whose breadcrumb to clear (the key).
        """
        self._unlink(self._advance_path(issue_number))

    # ------------------------------------------------------------------
    # Adapter-specific: slot reservation (ported from PoC engine/cap.py)
    # ------------------------------------------------------------------

    def reserve_slot(self, issue_number: int, cap: int) -> bool:
        """Atomically reserve a concurrency-cap slot for ``issue_number``.

        The count check + reservation is serialised under ``flock("cap")`` to
        close the TOCTOU window — two simultaneous daemons can never both see
        N-1 and both reserve the N-th slot (mirroring the PoC's
        ``engine/cap.py``).

        Idempotent per ticket: if ``issue_number`` already holds a slot,
        returns ``True`` without consuming another.

        Args:
            issue_number: The ticket to reserve a slot for.
            cap: The maximum number of concurrent slots allowed.

        Returns:
            ``True`` if the slot was reserved (or was already held),
            ``False`` if the cap is already exhausted.
        """
        with self._lock("cap"):
            slots_dir = self.root / "slots"
            marker = slots_dir / f"ticket-{issue_number}"
            if marker.exists():
                return True  # already holds a slot (idempotent)
            # Count existing slots while holding the lock (TOCTOU-safe).
            count = sum(1 for _ in slots_dir.iterdir())
            if count >= cap:
                return False
            # Defence-in-depth: O_EXCL ensures only one process creates the
            # marker even if two somehow race within the flock (belt-and-suspenders).
            try:
                fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                os.close(fd)
            except FileExistsError:
                # Another process slipped in — treat as "already held".
                return True
            return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _state_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s state file."""
        return self.root / "state" / f"{issue_number}.json"

    def _skip_corrupt_state(self, path: Path, err: Exception) -> None:
        """Breadcrumb + quarantine a corrupt state file (#11/#17): the shared skip-don't-raise path.

        Emits the named breadcrumb (via the module logger, #8) AND moves the poison file to
        ``state/corrupt/`` so it is read at most once more — stopping the every-tick re-parse storm
        a corrupt file otherwise causes (the reaper sweep + every ``load`` re-read it forever).

        Args:
            path: The corrupt state file being skipped.
            err: The exception raised while loading it (named in the breadcrumb).
        """
        _warn_corrupt_state(path, err)
        self._quarantine_corrupt_state(path)

    def _quarantine_corrupt_state(self, path: Path) -> None:
        """Move a corrupt state file to ``state/corrupt/`` to preserve evidence + stop re-parse noise (#11).

        A poison ``state/<n>.json`` is read on EVERY tick (the reaper's ``list_running``/``list_all``
        sweep + every ``load``), so a single corrupt file emits a breadcrumb every poll forever.
        Moving it to ``state/corrupt/<n>-<ts>.json`` stops the re-parse storm while PRESERVING the
        file for an operator to inspect (it is NOT deleted). The timestamp suffix avoids clobbering a
        prior quarantined copy of the same issue.

        **It does NOT make the orphan reaper-visible** (rank-12 verdict): the live session/worktree/
        slot are invisible once the state is gone either way — surfacing the pinned slot is the
        doctor "slot without state" check's job, not this quarantine. Fully fail-soft: a move failure
        is swallowed (the worst case is the breadcrumb keeps firing, never a crash).

        Args:
            path: The corrupt state file to quarantine.
        """
        try:
            import time as _time

            corrupt_dir = self.root / "state" / "corrupt"
            corrupt_dir.mkdir(parents=True, exist_ok=True)
            dest = corrupt_dir / f"{path.stem}-{int(_time.time())}{path.suffix}"
            path.replace(dest)
            logger.warning("quarantined corrupt state file %s -> %s", path, dest)
        except OSError as exc:
            # Swallow: quarantine is best-effort evidence preservation, never load-bearing.
            logger.warning("failed to quarantine corrupt state file %s: %s", path, exc)

    def _advance_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s advance breadcrumb.

        Keyed by the issue number (the breadcrumb-keying invariant, DESIGN
        §8.1.d), so the writer and the readers always agree on the marker path.
        """
        return self.root / "advances" / f"{issue_number}"

    def _moves_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s move rate-limit history.

        **Issue-keyed (boundary 2):** the PoC keyed ``moves/item_<item>.json``
        by the content node id; NEW keys by the issue number (``moves/<issue>.json``),
        like the slot/queue/advance markers.  Same deliberate divergence as the
        advance breadcrumb (DESIGN §8.1.d).
        """
        return self.root / "moves" / f"{issue_number}.json"

    def _retry_path(self, issue_number: int, key: str) -> Path:
        """Return the filesystem path for ``(issue_number, key)``'s retry counter.

        **Issue-keyed (boundary 2):** the PoC keyed ``retries/<safe-item>__<key>``
        by the content node id; NEW keys by the issue number
        (``retries/<issue>__<safe-key>``).

        **Sanitisation INVARIANT.** ``key`` is sanitised with the same
        alphanumeric/``._-`` filter the :meth:`_lock` helper uses (any
        character outside that set is replaced with ``_``), so a column name
        with a space or slash (e.g. ``"PR Ready"``) stays confined to a single
        file under ``retries/`` and cannot escape to a parent or sibling
        directory. An empty (or all-replaced) key defaults to ``"_"`` — the
        same fallback the PoC used via ``_INFLIGHT_SAFE``.
        """
        safe_key = "".join(c if c.isalnum() or c in "._-" else "_" for c in key) or "_"
        return self.root / "retries" / f"{issue_number}__{safe_key}"

    def _queue_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s queue marker.

        **Issue-keyed**: ``<root>/queue/ticket-<issue>`` — matches OLD's
        already-issue-keyed ``queue/ticket-<issue>`` layout (the PoC was
        issue-keyed for queue markers even before NEW).

        Args:
            issue_number: The ticket whose queue marker path to compute.
        """
        return self.root / "queue" / f"ticket-{issue_number}"

    def _script_output_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s check-script output marker.

        **Issue-keyed**: ``<root>/script_output/<issue>`` — one file per issue
        holding the latest check-script output for the fix-CI ``{{script_output}}``
        placeholder (15.6 / 15.7).

        Args:
            issue_number: The ticket whose script-output marker path to compute.
        """
        return self.root / "script_output" / f"{issue_number}"

    # ------------------------------------------------------------------
    # Per-issue AUTO/bot move rate-limit (DESIGN §6 durable backstop)
    # ------------------------------------------------------------------

    def record_move_for_item(self, issue_number: int, *, now: float) -> None:
        """Append a timestamp to ``issue_number``'s on-disk move history.

        Port of the PoC ``state.py:306-310`` (``record_move_for_item``), but
        **re-keyed by the issue number** (boundary 2) instead of the content
        node id.  The history lives at ``<root>/moves/<issue>.json`` — a JSON
        list of float wall-clock timestamps, one per move.

        This is fed **ONLY by an AUTO/bot move the daemon itself issues**
        (the reaper's move-to-Blocked is the only such move in NEW today) —
        NEVER a human launch or the agent's own ``kanban-move``.  The §6
        per-hour cap guards the bot loop, not the human workflow.

        Args:
            issue_number: The ticket whose move to record.
            now: The wall-clock timestamp to append to the history.
        """
        path = self._moves_path(issue_number)
        hist: list[float] = []
        if path.exists():
            try:
                hist = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                hist = []
        hist.append(now)
        path.write_text(json.dumps(hist))

    def move_count_for_item_last_hour(self, issue_number: int, *, now: float) -> int:
        """Return the number of AUTO/bot moves for ``issue_number`` within the
        sliding rate-limit window (:data:`_RATE_WINDOW`).

        Port of the PoC ``state.py:312-317`` (``move_count_for_item_last_hour``),
        but **re-keyed by the issue number** (boundary 2).

        Returns:
            The count of timestamps where ``now - t`` <= :data:`_RATE_WINDOW`.

        Degrades gracefully:
            - When the moves file is absent → returns ``0``.
            - When the moves file is corrupt/unreadable → returns ``0`` (never
              raises) AND emits a :func:`_warn_corrupt_state` breadcrumb naming the
              file (#13), so a poison ``moves/`` file is visible rather than
              silently under-counting the §6 backstop.  A bad file must not wedge
              the launch gate — the same poison-file degrade pattern that
              :meth:`load` uses.
        """
        path = self._moves_path(issue_number)
        if not path.exists():
            return 0
        try:
            hist: list[float] = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as err:
            # Degrade to 0 (don't raise — a poison rate-limit file must not wedge the launch
            # gate), but leave a breadcrumb so a corrupt moves/<n>.json is visible. Without it
            # the degrade silently UNDER-counts the §6 backstop, letting a runaway slip the cap
            # unseen. Same diagnostic helper as the schema-corrupt state files (#13, sibling of
            # 18.4); skip-don't-raise is preserved.
            _warn_corrupt_state(path, err)
            return 0
        return sum(1 for t in hist if (now - t) <= _RATE_WINDOW)

    # ------------------------------------------------------------------
    # Per-(issue,key) fix-CI retry counter (DESIGN §6 bounded loop cap)
    # ------------------------------------------------------------------

    def bump_retry(self, issue_number: int, key: str) -> int:
        """Increment and return the per-(issue, key) fix-CI retry counter (starts at 1).

        Port of the PoC ``state.py:212-221`` (``bump_retry``), but **re-keyed
        by the issue number** instead of the content node id (boundary 2).
        The counter is stored as ``{"n": n}`` under
        ``<root>/retries/<issue>__<safe-key>`` (issue-keyed).

        Backs the bounded fix-CI loop (DESIGN §6, N=2): the consumer bumps on
        each auto-retry and parks the ticket in Blocked once the count exceeds
        the cap.

        **Key-shape note (load-bearing).** This per-(issue, key) ledger is
        DISTINCT from the bare ``TicketState.retries`` field (the per-ticket
        reaper-retry counter, refreshed via :meth:`save`). The reaper retry
        (15.2) rides on ``TicketState.retries``; the fix-CI cap (15.7) rides
        on this ``retries/<issue>__<key>`` ledger via ``bump_retry``. Two
        separate counters, never conflated — matching the PoC's separation of
        ``data["retries"]`` vs ``bump_retry``.

        The write is atomic via temp-file + ``os.replace`` so a concurrent
        reader never observes a torn counter file.

        Args:
            issue_number: The ticket whose retry counter to bump.
            key: The loop budget key (e.g. the destination column key, port of
                OLD's ``onfail:<to>`` semantics). Sanitised by
                :meth:`_retry_path`.

        Returns:
            The new retry count (1 on first call, 2 on second, etc.).
        """
        path = self._retry_path(issue_number, key)
        count = (json.loads(path.read_text()).get("n", 0) if path.exists() else 0) + 1
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"n": count}))
        os.replace(tmp, path)
        return count

    def reset_retry(self, issue_number: int, key: str) -> None:
        """Unlink the per-(issue, key) fix-CI retry counter marker.

        Port of the PoC ``state.py:223-225`` (``reset_retry``), but **re-keyed
        by the issue number** (boundary 2) AND **changed to unlink** instead of
        writing ``{"n": 0}`` — a deliberate divergence: removing the marker is
        simpler and :meth:`bump_retry` already treats an absent file as count 0.
        Called when the fix-CI loop succeeds / the ticket leaves the cycle, so
        the next cycle starts fresh.

        No-op when the marker is absent (``FileNotFoundError`` is swallowed),
        mirroring the PoC's idempotent contract.

        Args:
            issue_number: The ticket whose retry counter to unlink.
            key: The loop budget key (sanitised by :meth:`_retry_path`).
        """
        try:
            self._retry_path(issue_number, key).unlink()
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Per-issue check-script output (15.6 / 15.7 {{script_output}} sink)
    # ------------------------------------------------------------------

    def save_script_output(self, issue_number: int, output: str) -> None:
        """Persist the latest check-script output for ``issue_number``.

        Backs the fix-CI prompt's ``{{script_output}}`` placeholder (15.7): a
        failing check stashes its output here so the SUBSEQUENT fix-CI launch can
        fill the placeholder; the success path writes ``""`` so a stale failure
        output never bleeds into a later launch. Written atomically (temp-file +
        ``os.replace``) so a concurrent reader never observes a torn file. An
        empty ``output`` is persisted as an empty file (the explicit "cleared"
        state) — both an empty file and an absent file read back as ``""``.

        Args:
            issue_number: The ticket whose script output to persist (the key).
            output: The combined script output to stash (``""`` clears it).
        """
        path = self._script_output_path(issue_number)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(output)
        os.replace(tmp, path)

    def load_script_output(self, issue_number: int) -> str:
        """Load the stashed check-script output for ``issue_number``.

        Returns the output :meth:`save_script_output` last wrote, or ``""`` when
        the marker is absent OR unreadable (the same poison-file degrade pattern
        :meth:`load` uses) so a bad marker never wedges a fix-CI launch.

        Args:
            issue_number: The ticket whose script output to read (the key).

        Returns:
            The stashed output, or ``""`` when absent or unreadable.
        """
        path = self._script_output_path(issue_number)
        if not path.exists():
            return ""
        try:
            return path.read_text()
        except OSError:
            return ""

    # ------------------------------------------------------------------
    # Queue persistence (DESIGN §7 concurrency-cap queue)
    # ------------------------------------------------------------------

    def enqueue_launch(self, issue_number: int, payload: Mapping[str, object]) -> None:
        """Write a relaunch queue marker for ``issue_number``.

        Port of the PoC's queue-marker write (``runner.py:711-728``), but
        NEW's payload is **intentionally thinner**: NEW's ``LaunchAction``
        re-derives its worktree/profile/agent_command from ``Deps`` + the
        snapshot, so the marker only needs enough to **re-identify** the
        ticket at drain time.  The caller passes
        ``{"item_id": …, "stage": …, "enqueued_at": now}``.

        OLD persisted the fully-filled prompt + GitHub coords because its
        launcher re-read the marker; NEW's ``LaunchAction`` is self-contained
        so the payload stays minimal.

        **Issue-keyed** — writes ``queue/ticket-<issue>``.

        Args:
            issue_number: The ticket to enqueue.
            payload: A mapping with ``item_id``, ``stage``, and ``enqueued_at``
                keys — enough to re-identify the ticket at drain time.
        """
        self._queue_path(issue_number).write_text(json.dumps(dict(payload)))

    def dequeue_pending(self) -> tuple[int, ...]:
        """Return the issue numbers of every queued ticket, ordered lexicographically.

        The order is **lexicographic by marker name** (``ticket-<n>``), a
        faithful port of the PoC ``sorted(store.queue_dir().glob("ticket-*"))``
        (``reaper.py:58``) — NOT numeric order (e.g. ``ticket-10`` sorts before
        ``ticket-5``). Skips a marker whose name does not parse to an ``int`` —
        port of OLD's ``try/except (IndexError, ValueError)`` — so a stray
        non-conforming file under ``queue/`` never crashes the drain sweep.

        Returns:
            An immutable (possibly empty) tuple of issue numbers, in the
            lexicographic order of their ``ticket-<n>`` marker names (the same
            sort OLD's ``sorted(glob(…))`` produces).
        """
        queue_dir = self.root / "queue"
        if not queue_dir.exists():
            return ()
        issues: list[int] = []
        for path in sorted(queue_dir.glob("ticket-*")):
            try:
                issue = int(path.name.split("-", 1)[1])
            except (IndexError, ValueError):
                continue
            issues.append(issue)
        return tuple(issues)

    def load_queued(self, issue_number: int) -> dict[str, object] | None:
        """Read and parse the queue marker payload for ``issue_number``.

        Returns ``None`` when the marker is absent **or corrupt/unreadable**
        — the same poison-file degrade pattern :meth:`load` uses, so a bad
        queue file never wedges the drain.

        **Issue-keyed** — reads ``queue/ticket-<issue>``.

        Args:
            issue_number: The ticket whose queue marker to read.

        Returns:
            The parsed payload ``dict``, or ``None`` when absent or corrupt.
        """
        path = self._queue_path(issue_number)
        if not path.exists():
            return None
        try:
            return cast(dict[str, object], json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError):
            return None

    def clear_queued(self, issue_number: int) -> None:
        """Remove the queue marker for ``issue_number``.

        No-op when the marker is absent (unlink-if-exists / no-raise) — the
        drain calls this after a confirmed launch without checking existence
        first.  Idempotent across the teardown path (:meth:`release_slot`
        already purged it).

        **Issue-keyed** — unlinks ``queue/ticket-<issue>``.

        Args:
            issue_number: The ticket whose queue marker to clear.
        """
        self._unlink(self._queue_path(issue_number))

    @contextmanager
    def _lock(self, resource: str) -> Generator[None, None, None]:
        """Hold an exclusive advisory ``flock`` on *resource* for the duration of the block.

        Ported from the PoC ``engine/locks.py``. The lock file lives under
        ``<root>/locks/<resource>.lock``. The lock is released (and the fd
        closed) on exit, even on exception.

        Args:
            resource: A logical resource name (e.g. ``"cap"``). Non-alphanumeric
                characters are replaced to prevent directory escape.
        """
        locks_dir = self.root / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        # Sanitise the resource name so it cannot escape the locks directory.
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in resource)
        path = locks_dir / f"{safe}.lock"
        fh = path.open("a+")
        acquired = False
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            acquired = True
            yield
        finally:
            if acquired:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            fh.close()

    @staticmethod
    def _unlink(path: Path) -> None:
        """Remove *path* if it exists; no-op otherwise."""
        try:
            path.unlink()
        except FileNotFoundError:
            pass
