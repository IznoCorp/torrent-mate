"""State-store port: the persisted runtime-state boundary.

The daemon's source of truth lives outside the repo in ``~/.kanban/``. This
Protocol describes the runtime-state operations the polling loop needs —
loading/saving a ticket's state, refreshing its liveness heartbeat, releasing
its concurrency slot, and listing the running tickets to reap.

The filesystem adapter (:mod:`kanbanmate.adapters.store`) implements state writes
with temp-file + :func:`os.replace` for atomicity; the atomic slot reservation
(:meth:`StateStore.reserve_slot`) uses ``O_EXCL`` + ``flock`` for serialisation
(DESIGN §6 H-subset). ``reserve_slot`` is part of this Protocol because the
concurrency-cap gate in :mod:`kanbanmate.app.tick` (gate 13.5) reserves a slot
through the live ``store`` port BEFORE dispatching a launch. This module declares
only the contract and a minimal :class:`TicketState` record. No persistence logic
lives here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol


class TicketStatus(str, Enum):
    """The closed lifecycle status set for a :class:`TicketState`.

    A ``str``-valued enum so the on-disk JSON value is the plain member value
    (``"running"`` / ``"idle"``) — no custom encoder needed and existing state
    files stay valid.  The type keeps the writer and every reader anchored to a
    single source of truth; mypy rejects off-set values at construction sites.
    """

    RUNNING = "running"
    """The ticket has a live agent session in flight."""

    WAITING = "waiting"
    """The ticket's agent is ALIVE but AWAITING HUMAN INPUT — do NOT reap (phase-27 §B).

    A stale-heartbeat agent sitting at an interactive prompt (a choice/confirmation it cannot
    answer itself) is NOT hung: reaping/relaunching it would discard the human's pending decision.
    The reaper (:func:`kanbanmate.app.reaper.reap_stale_agents`) classifies a stale-but-ALIVE
    session's captured pane via :func:`kanbanmate.core.launch_keys.is_waiting_for_input`; a waiting
    pane transitions the ticket here (signalled to the user via the ⏳ stage header + the dashboard
    AT_RISK pill) instead of being reaped. It is RESTORED to ``RUNNING`` once the human answers and
    the heartbeat refreshes, or reaped if the session dies. Like ``RUNNING`` it is a LIVE status, so
    :meth:`StateStore.list_running` includes ``WAITING`` tickets — the reaper must keep observing
    them to detect the heartbeat refresh (resume) or a dead session (reap)."""

    IDLE = "idle"
    """The ticket's agent session has ended; no agent is currently running.

    **LOAD-BEARING (#21 KEEP+DOC — do NOT remove).** Originally slated for removal as a
    vestigial post-pivot status, ``IDLE`` became load-bearing in phase 15.2: the reaper
    writes ``status=IDLE`` BEFORE its teardown purge (:func:`kanbanmate.app.reaper.reap_stale_agents`,
    the ``save(replace(state, status=IDLE))`` at the BLOCK branch) so that a fail-soft
    ``purge_ticket`` failure cannot leave a refreshed-heartbeat RUNNING zombie that the next
    sweep skips as "fresh" (a high-sev defect caught by adversarial verification). It is NEW's
    port of the PoC ``reaper._move_to_blocked`` "write a terminal non-RUNNING status before
    releasing" ordering, and is the ONLY non-RUNNING terminal status — :meth:`StateStore.list_running`
    filters to ``RUNNING``, so an ``IDLE`` record is invisible to the reaper's stale-agent list.
    Deleting this member would revert the 15.2 fix (re-introducing the zombie) or force a new
    status member. An asserting test (``tests/app/test_tick.py``) pins the reaper's ``IDLE`` write."""


# The LIVE status set: a ticket whose agent session is in flight (#3). ``RUNNING`` and ``WAITING``
# are BOTH live — a WAITING agent is alive, merely paused on a human prompt, so it holds its slot
# and its tmux session. This single set is the one authoritative answer to "is this agent live?",
# used by the drain's already-running guard, the tick's pre-launch already-live guard, the
# Done-arrival teardown, and ``list_running``. Before #3 the drain guard tested ``RUNNING`` only,
# so a re-dispatch of a WAITING ticket pre-killed the live session (phase-27 idempotent launch
# calls ``_kill_if_present`` before ``new-session``) — DISCARDING the pending human decision. The
# set closes that hole at every call site at once.
LIVE_STATUSES = frozenset({TicketStatus.RUNNING, TicketStatus.WAITING})


@dataclass(frozen=True)
class TicketState:
    """The persisted runtime state of a single in-flight ticket.

    A minimal, typed view of the per-ticket ``state/<issue>.json`` record. The
    adapter may persist a superset of these fields, but the port contract is
    limited to what the polling loop and reaper consume.

    Attributes:
        issue_number: The ticket's GitHub issue number (the state key).
        item_id: The ``ProjectV2Item`` node id the ticket maps to.
        session_id: The tmux session name hosting the agent, or ``None`` when
            no session is currently running (e.g. idle after session end).
        status: A coarse lifecycle marker; one of :class:`TicketStatus`.
        heartbeat: The wall-clock timestamp of the last liveness heartbeat,
            used by the reaper's stale-agent TTL check.
        stage: The column key the launch entered — the stage the finalizers
            (✅ advance / ⚠️ session-end / ⛔ reaper) finalize. Defaulted to
            ``""`` so an old-format on-disk record (predating the widened
            ``TicketState``) still loads cleanly via the adapter's
            ``TicketState(**data)`` round-trip (DESIGN §8.1.d).
        profile: The permission profile the agent runs under — the ``profile``
            bullet a terminal sticky's ``header_from_state`` renders. Defaulted.
        mode: The materialised Claude permission mode (e.g. ``"auto"``)
            — the ``mode`` bullet ``header_from_state`` renders. Defaulted.
        started: The launch wall-clock epoch — ``header_from_state`` formats it
            via ``fmt_timestamp`` into the ``started`` bullet. Defaulted.
        worktree: The worktree path the agent runs in — ``header_from_state``
            shows ``Path(worktree).name`` in the ``worktree`` bullet. Defaulted.
        retries: How many times the reaper has relaunched this stale session
            (the reaper relaunch-once budget; capped at
            ``reaper.RETRY_LIMIT``). The reaper increments this on each retry
            via :meth:`StateStore.save`; the bare counter rides on the
            ``TicketState`` (NOT the ``(issue, key)`` ledger — those are two
            distinct counters, never conflated). Defaulted to 0 so an
            old-format state file lacking the key still loads cleanly.
        prompt: The matched transition's FILLED-AT-LAUNCH prompt template — one
            of the **relaunch inputs** persisted so the reaper can rebuild the
            EXACT launch command (PoC ``launch.py`` "Re-launch inputs persisted",
            phase-25 §25.2). Without it a reaper relaunch spawns a PROMPTLESS
            idle agent that never does a tool call and is re-reaped at the TTL.
            ``None`` for a bare (prompt-less) launch. Defaulted so an old-format
            state file lacking the key still loads cleanly.
        script: The matched transition's launch-transition script — a relaunch
            input persisted alongside :attr:`prompt` so the reaper rebuilds the
            full :class:`~kanbanmate.app.actions.LaunchAction`. ``None`` when the
            transition carried no script. Defaulted.
        on_fail: The matched transition's ``on_fail`` policy — a relaunch input
            so the rebuilt LaunchAction keeps the original failure routing.
            Defaulted ``""``.
        advance: The matched transition's ``advance`` directive — a relaunch
            input so the rebuilt LaunchAction keeps the original advance policy.
            Defaulted ``""`` (note: the reaper relaunch re-supplies the directive
            verbatim; an empty string means "carry whatever was persisted").
    """

    issue_number: int
    item_id: str
    session_id: Optional[str]
    status: TicketStatus
    heartbeat: float
    # The launch stage + header metadata re-threaded for the rich sticky
    # finalizers (DESIGN §8.1.d). Every new field is DEFAULTED so an old-format
    # state file lacking them still deserialises via ``TicketState(**data)``.
    stage: str = ""
    profile: str = ""
    mode: str = ""
    started: float = 0.0
    worktree: str = ""
    retries: int = 0
    # The RELAUNCH INPUTS (phase-25 §25.2): persisted at launch so the reaper can
    # rebuild the EXACT LaunchAction (prompt + script + on_fail + advance; the
    # permission_mode already rides on ``mode``, the profile on ``profile``).
    # Without these a reaper relaunch is PROMPTLESS — a regression vs the PoC,
    # which persisted prompt/profile/permission_mode/… precisely so the reaper
    # could re-deliver the prompt via send-keys. All DEFAULTED so an old-format
    # state file still loads via ``TicketState(**data)``.
    prompt: Optional[str] = None
    script: Optional[str] = None
    on_fail: str = ""
    advance: str = ""
    # The ticket's title + body at launch (defect 4): persisted so a reaper RELAUNCH rebuilds the
    # Ticket with the REAL title/body, not a synthetic ``ticket-N`` / empty body. An empty body
    # makes ``parse_ticket_fields`` yield empty codename/design_path/plan_paths, and the Plan /
    # Prepare prompts hard-instruct "if empty → DESYNC, END the session" — so a relaunched
    # Spec→Plan agent self-DESYNCs and burns its one retry. The drain queue payload already proves
    # this shape (it persists title/body). Both DEFAULTED so an old-format state still loads.
    title: str = ""
    body: str = ""


class StateStore(Protocol):
    """Persisted per-ticket runtime state for the polling daemon.

    Keyed by issue number throughout, matching the worktree/session keying in
    :mod:`kanbanmate.ports.workspace`.
    """

    def load(self, issue_number: int) -> TicketState | None:
        """Load the persisted state for ``issue_number``.

        Args:
            issue_number: The ticket's issue number.

        Returns:
            The :class:`TicketState`, or ``None`` when no state is persisted
            (first contact, or after a Cancel teardown purged it).
        """
        ...

    def save(self, state: TicketState) -> None:
        """Persist ``state`` atomically (temp file + ``os.replace``).

        A concurrent reader (the reaper) must never observe a torn write.

        Args:
            state: The ticket state to persist; its ``issue_number`` is the key.
        """
        ...

    def touch_heartbeat(self, issue_number: int, now: float) -> None:
        """Refresh a running ticket's liveness heartbeat to ``now``.

        NO-OP when the state is absent: it must NEVER recreate a purged ticket's
        state (DESIGN §8.3 no-resurrection — a late hook firing after a Cancel
        teardown must not bring the ticket back).

        Args:
            issue_number: The ticket whose heartbeat to refresh.
            now: The wall-clock timestamp to record.
        """
        ...

    def reserve_slot(self, issue_number: int, cap: int) -> bool:
        """Atomically reserve a concurrency-cap slot for ``issue_number``.

        The count check + reservation is serialised (``flock`` + ``O_EXCL`` in
        the fs adapter) to close the TOCTOU window — two simultaneous daemons
        can never both see ``cap - 1`` and both reserve the ``cap``-th slot
        (port of the PoC ``engine/cap.py``).

        Idempotent per ticket: if ``issue_number`` already holds a slot, returns
        ``True`` without consuming another, so a re-queued ticket that already
        holds a slot reserves nothing extra.

        Consumed by the gate 13.5 cap gate in :mod:`kanbanmate.app.tick`: a
        launch reserves a slot BEFORE dispatch; on a full cap the launch diverts
        to the queue (no agent starts). The drain reserves again before
        re-launching a queued ticket so it never exceeds the cap.

        Args:
            issue_number: The ticket to reserve a slot for.
            cap: The maximum number of concurrent slots allowed.

        Returns:
            ``True`` if the slot was reserved (or was already held), ``False``
            if the cap is already exhausted.
        """
        ...

    def release_slot(self, issue_number: int) -> None:
        """Release ONLY ``issue_number``'s concurrency-cap slot marker AND retry counters.

        Frees the slot, purges every ``retries/<issue>__*`` marker (the per-(issue, key)
        fix-CI retry counters — idempotent, called on both cancel and clean-exit paths),
        and NOTHING ELSE: it does NOT purge the runtime state, the advance breadcrumb,
        the queue marker, or the move rate-limit history. Faithful port of the PoC
        ``engine/cap.py`` ``release_slot`` (slot-only) extended with the retry-ledger
        purge so a cancelled/finished ticket leaves no stale retry counters. The
        exhaustive teardown lives in :meth:`purge_ticket`.

        Idempotent: releasing an already-released (or never-reserved) slot is a
        no-op, so a teardown/session-end race cannot double-free.

        Args:
            issue_number: The ticket whose concurrency-cap slot + retry markers
                to release.
        """
        ...

    def purge_ticket(self, issue_number: int, *, keep_budgets: bool = False) -> None:
        """Idempotent teardown purge of a ticket's markers for ``issue_number``.

        Removes the per-ticket RUNTIME footprint ALWAYS:
          * ``state/<issue>.json``    — persisted runtime state
          * ``slots/ticket-<issue>``  — concurrency-cap slot marker
          * ``advances/<issue>``      — agent-advance breadcrumb (DESIGN §8.1.d)
          * ``queue/ticket-<issue>``  — relaunch queue marker (DESIGN §7)

        And the per-issue BUDGET markers CONDITIONALLY (only when ``keep_budgets``
        is ``False`` — the default exhaustive teardown):
          * ``moves/<issue>.json``    — per-issue move rate-limit history (§6)
          * ``retries/<issue>__*``    — every per-(issue, key) fix-CI retry
            counter (the fs adapter ``glob.escape``s the interpolated issue so a
            metachar can never widen the pattern — over-match defence).

        The budget markers are *per-issue budgets* that must persist across the
        ticket's lifecycle (sessions, reaps) so the durable §6 rate-limit can
        ACCUMULATE, and are torn down ONLY when the ticket is truly abandoned
        (13.8 — PoC fidelity). Each removal is independently guarded (no-raise on
        absent) so a teardown→reset (or session-end/teardown) double-purge never
        raises — idempotent per the PoC ``purge_ticket`` contract.

        Used by:
          * ``keep_budgets=True`` — the reaper's stale-agent teardown
            (:class:`~kanbanmate.app.actions.TeardownAction` constructed with the
            flag) and ``kanban session-end``: the ticket MAY continue, so its
            rate-limit / fix-CI budgets are PRESERVED across the gap.
          * ``keep_budgets=False`` (default) — the Cancel-column
            ``TeardownAction`` and the Cancel→Backlog ``ResetAction``: the ticket
            is ABANDONED, so the full exhaustive purge drops the budgets too.

        Args:
            issue_number: The ticket whose persisted markers to purge.
            keep_budgets: When ``True``, preserve ``moves/`` + ``retries/`` (the
                per-issue budgets) and purge only the runtime markers (reaper /
                session-end — the ticket may continue). When ``False`` (default),
                the exhaustive teardown (Cancel / reset — abandonment).
        """
        ...

    def list_running(self) -> tuple[TicketState, ...]:
        """Return the persisted states of every currently LIVE ticket.

        Consumed by the reaper to find stale agents (heartbeat past the TTL). A
        LIVE ticket is one whose ``status`` is :attr:`TicketStatus.RUNNING` OR
        :attr:`TicketStatus.WAITING` (an agent awaiting human input is alive — the
        reaper must keep observing it to restore it on a heartbeat refresh or reap
        it on a dead session, phase-27 §B).

        Returns:
            An immutable tuple of every persisted :class:`TicketState` whose
            ``status`` is :attr:`TicketStatus.RUNNING` or
            :attr:`TicketStatus.WAITING`.
        """
        ...

    def list_all(self) -> tuple[TicketState, ...]:
        """Return every persisted ticket regardless of status.

        The PoC ``_known_issues`` analogue — iterates every ``state/<n>.json``
        without filtering. Distinct from :meth:`list_running`, which returns only
        running tickets. Consumed by the ``sessions`` report (the third ``stopped``
        bucket needs non-running states too) and any future read-model that must
        see the full persisted set.

        Returns:
            An immutable tuple of every persisted :class:`TicketState`, in
            issue-number-ascending order.
        """
        ...

    def append_dispatch(self, record: dict[str, object]) -> None:
        """Append one JSON line per dispatch to ``<root>/log/dispatch.jsonl``.

        Port of the PoC ``audit.append_dispatch`` (audit.py:14-30): one
        structured launch record per line under the audit log, written on every
        dispatch (the decided launch AND the reaper relaunch). The record is
        **shallow-copied** and stamped with a wall-clock ``logged_at`` (epoch
        seconds) before the write, so a caller may pass a literal dict without
        mutation surprises.

        **Determinism split (load-bearing).** ``logged_at`` is stamped with
        ``time.time()`` INSIDE the adapter (so the port stays clock-free,
        matching the PoC), whereas the CALLER (:class:`~kanbanmate.app.actions.LaunchAction`)
        puts ``ts=now`` (the injected clock's now) IN the record. A test
        therefore asserts ``ts`` (deterministic) and only that ``logged_at``
        EXISTS (a float), not its exact value.

        Fail-soft is the CALLER's responsibility: this method may raise on an
        I/O error; :class:`~kanbanmate.app.actions.LaunchAction` wraps the call
        so an audit-log write failure never breaks a launch.

        Args:
            record: The launch record (issue / repo / to-column / profile /
                session uuid / worktree / tmux / ts) — a JSON-serialisable dict.
        """
        ...

    def record_agent_advance(self, issue_number: int, *, now: float) -> None:
        """Drop a breadcrumb that the agent advanced its own card (DESIGN §8.1.d).

        Written SYNCHRONOUSLY before the agent's ``claude`` process exits (the
        NEW analogue of the PoC's ``kanban-move``), so session-end can later
        distinguish "advanced then finished" (breadcrumb present → the daemon
        already finalized ✅) from "died without advancing" (breadcrumb absent →
        session-end finalizes ⚠️) without depending on the asynchronous poll's
        timing — exactly the PoC's race-closing design.

        **Breadcrumb-keying INVARIANT (load-bearing).** The breadcrumb is keyed
        by the **issue number** — never a content node id. The WRITER (this
        method) and the READERS (:meth:`recent_agent_advance` /
        :meth:`clear_agent_advance`) MUST use the identical issue key, or the
        ✅/⚠️ split mis-fires (the breadcrumb always looks "absent" and a clean
        advance is wrongly finalized ⚠️). This is a deliberate divergence from
        the PoC, which keyed by content node id.

        Args:
            issue_number: The ticket whose advance to record (the breadcrumb key).
            now: The wall-clock timestamp written into the breadcrumb.
        """
        ...

    def recent_agent_advance(self, issue_number: int, *, now: float) -> bool:
        """Return whether a recent advance breadcrumb exists for ``issue_number``.

        ``True`` iff the breadcrumb exists and ``now - ts`` is within the
        advance TTL (300 s). This recency window is a DISTINCT knob from the
        reaper's ``HEARTBEAT_TTL`` (1800 s, DESIGN §8.3) — the two must not be
        conflated.

        **Breadcrumb-keying INVARIANT (load-bearing).** Keyed by the **issue
        number** — the SAME key :meth:`record_agent_advance` wrote with. A
        mismatch (one side keying by issue, the other by node id) makes the
        breadcrumb always look "absent" and finalizes ⚠️ after a clean advance.

        Args:
            issue_number: The ticket whose breadcrumb to check (the key).
            now: The wall-clock timestamp the TTL is measured against.

        Returns:
            ``True`` iff a breadcrumb exists and is within the advance TTL.
        """
        ...

    def clear_agent_advance(self, issue_number: int) -> None:
        """Remove ``issue_number``'s advance breadcrumb (consumed by session-end).

        No-op when the breadcrumb is absent (the PoC's ``FileNotFoundError``
        swallow), so consuming an already-cleared (or never-written) breadcrumb
        never raises.

        **Breadcrumb-keying INVARIANT (load-bearing).** Keyed by the **issue
        number** — the SAME key the writer/recency-reader use. Session-end MUST
        call this with the identical issue key (never a content node id).

        Args:
            issue_number: The ticket whose breadcrumb to clear (the key).
        """
        ...

    def kill_switch_active(self) -> bool:
        """Return whether the kill-switch (``~/.kanban/PAUSE``) is engaged.

        A pure read consulted at the start of every tick: when ``True`` the
        decision core downgrades every launch to a block, so dropping the
        sentinel between ticks halts launches on the next poll (DESIGN §10 / H5).

        Returns:
            ``True`` iff the kill-switch sentinel is present.
        """
        ...

    def record_move_for_item(self, issue_number: int, *, now: float) -> None:
        """Append a timestamp to ``issue_number``'s on-disk AUTO/bot move history.

        Port of the PoC ``state.py:306-310`` (``record_move_for_item``), but
        **re-keyed by the issue number** instead of the content node id (boundary
        2 — the same deliberate divergence as the advance breadcrumb,
        DESIGN §8.1.d).  The history file MUST be ``moves/<issue>.json`` —
        issue-keyed, NOT ``moves/item_<node>.json``.

        Fed **ONLY by an AUTO/bot move the daemon itself issues** (the reaper's
        move-to-Blocked is the only such move in NEW today) — NEVER a human
        launch or the agent's own ``kanban-move``.  The §6 per-hour cap guards
        the bot loop, not the human workflow.

        Args:
            issue_number: The ticket whose AUTO/bot move to record.
            now: The wall-clock timestamp to append to the JSON history list.
        """
        ...

    def move_count_for_item_last_hour(self, issue_number: int, *, now: float) -> int:
        """Return the number of AUTO/bot moves for ``issue_number`` within the
        sliding rate-limit window (3600 s).

        Port of the PoC ``state.py:312-317`` (``move_count_for_item_last_hour``),
        but **re-keyed by the issue number** (boundary 2).  The history file
        MUST be ``moves/<issue>.json`` — issue-keyed.

        Must degrade gracefully: absent file → ``0``; corrupt/unreadable file →
        ``0`` (never raise).  A bad ``moves/`` file must not wedge the launch
        gate.

        Args:
            issue_number: The ticket whose move history to query.
            now: The wall-clock timestamp the sliding window is measured against.

        Returns:
            The count of timestamps within the rate-limit window, or ``0`` when
            the history is absent or corrupt.
        """
        ...

    def bump_retry(self, issue_number: int, key: str) -> int:
        """Increment and return the per-(issue, key) fix-CI retry counter (starts at 1).

        Port of the PoC ``state.py:212-221`` (``bump_retry``), but **re-keyed by
        the issue number** instead of the content node id (boundary 2 — the same
        deliberate divergence as the advance breadcrumb, DESIGN §8.1.d).

        Backs the bounded fix-CI loop (DESIGN §6, N=2): the consumer bumps on
        each auto-retry and parks the ticket in Blocked once the count exceeds
        the cap.

        **Sanitisation INVARIANT.** ``key`` is sanitised with the same
        alphanumeric/``._-`` filter used for lock paths: any character outside
        that set is replaced; an empty (or all-replaced) key defaults to ``"_"``.
        A column name with a space/slash (e.g. ``"PR Ready"``) must stay confined
        to a single file under ``retries/`` — no directory escape.

        The counter is stored as ``{"n": n}`` under
        ``<root>/retries/<issue>__<safe-key>`` (issue-keyed).

        Args:
            issue_number: The ticket whose retry counter to bump.
            key: The loop budget key (e.g. the destination column key, port of
                OLD's ``onfail:<to>`` semantics). Sanitised per the invariant
                above.

        Returns:
            The new retry count (1 on first call, 2 on second, etc.).
        """
        ...

    def reset_retry(self, issue_number: int, key: str) -> None:
        """Unlink the per-(issue, key) fix-CI retry counter marker.

        Port of the PoC ``state.py:223-225`` (``reset_retry``), but **re-keyed
        by the issue number** (boundary 2) AND **changed to unlink** instead of
        writing ``{"n": 0}`` — a deliberate divergence from the PoC: removing
        the marker is simpler and ``bump_retry`` already treats an absent file
        as count 0.  Called when the fix-CI loop succeeds / the ticket leaves
        the cycle, so the next cycle starts fresh.

        No-op when the marker is absent (``FileNotFoundError`` is swallowed),
        mirroring the PoC's idempotent contract.

        **Sanitisation INVARIANT.** Same sanitisation as :meth:`bump_retry` —
        the ``key`` IS sanitised identically so the same (issue, key) pair maps
        to the same file on both the bump and reset paths.

        Args:
            issue_number: The ticket whose retry counter to unlink.
            key: The loop budget key (sanitised per the invariant above).
        """
        ...

    def save_script_output(self, issue_number: int, output: str) -> None:
        """Persist the latest check-script output for ``issue_number``.

        Backs the fix-CI prompt's ``{{script_output}}`` placeholder (15.7): when a
        check script FAILS, its combined stdout/stderr is stashed here so the
        SUBSEQUENT fix-CI launch (the ``PRCI→InProgress`` retry, whose prompt
        references ``{{script_output}}``) can fill that placeholder with the
        failing CI output. On SUCCESS the routing CLEARS this (writes ``""``) so a
        stale failure output never bleeds into a later launch.

        The marker lives at ``<root>/script_output/<issue>`` (issue-keyed, like
        every other per-ticket marker). Written atomically (temp-file +
        ``os.replace``) so a concurrent reader never observes a torn file. Empty
        ``output`` is persisted as an empty file (the explicit "cleared" state),
        distinct from an ABSENT file (never written) — both read back as ``""``.

        Args:
            issue_number: The ticket whose script output to persist (the key).
            output: The combined script output to stash (``""`` clears it).
        """
        ...

    def load_script_output(self, issue_number: int) -> str:
        """Load the stashed check-script output for ``issue_number``.

        Returns the output :meth:`save_script_output` last wrote, or ``""`` when
        the marker is absent OR unreadable — the same poison-file degrade pattern
        :meth:`load` uses, so a bad marker never wedges a fix-CI launch. Consumed
        by 15.7 to fill the ``{{script_output}}`` placeholder on the fix-CI
        prompt.

        Args:
            issue_number: The ticket whose script output to read (the key).

        Returns:
            The stashed output, or ``""`` when absent or unreadable.
        """
        ...

    def enqueue_launch(self, issue_number: int, payload: Mapping[str, object]) -> None:
        """Write a relaunch queue marker for ``issue_number``.

        Port of the PoC's queue-marker write (``runner.py``). The payload is a RICH mapping
        (minor (g): the earlier "intentionally thinner" docstring was stale): the drain
        (:func:`kanbanmate.app.drain._drain_queue`) rebuilds a :class:`~kanbanmate.app.actions.LaunchAction`
        BYTE-IDENTICAL to a direct cap-gate launch from it — the filled per-transition
        ``/implement:*`` prompt is preserved (operator decision 2026-06-06: parity over thinness),
        so a queued launch is indistinguishable from one dispatched under the cap. The caller
        (:func:`kanbanmate.app.transition_step.process_transition`) passes ``item_id`` / ``stage`` /
        ``title`` / ``body`` / ``prompt`` / ``script`` / ``profile`` / ``permission_mode`` /
        ``on_fail`` / ``advance`` / ``enqueued_at``.

        **Issue-keyed** — the marker path is ``queue/ticket-<issue>``.

        Args:
            issue_number: The ticket to enqueue.
            payload: The rich relaunch mapping the drain rebuilds the LaunchAction from (the keys
                listed above). ``item_id`` is load-bearing — the drain skips a payload lacking it.
        """
        ...

    def dequeue_pending(self) -> tuple[int, ...]:
        """Return the issue numbers of every queued ticket, ordered lexicographically.

        Mirrors OLD's ``sorted(store.queue_dir().glob("ticket-*"))``
        (``reaper.py``).  Non-conforming files (those whose name does not parse
        to an ``int``) are skipped — port of OLD's ``try/except (IndexError,
        ValueError)`` — so a stray file under ``queue/`` never crashes the drain
        sweep.

        **Issue-keyed** — each marker is ``queue/ticket-<issue>``.  The order is
        **lexicographic by marker name** (a faithful port of the PoC
        ``sorted(glob("ticket-*"))``), NOT numeric — e.g. ``ticket-10`` sorts
        before ``ticket-5``.

        Returns:
            An immutable (possibly empty) tuple of issue numbers, in the
            lexicographic order of their ``ticket-<n>`` marker names.
        """
        ...

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
        ...

    def clear_queued(self, issue_number: int) -> None:
        """Remove the queue marker for ``issue_number``.

        No-op when the marker is absent (unlink-if-exists / no-raise).  Called
        by the drain **after** a confirmed launch; also called indirectly by
        :meth:`release_slot` during teardown (idempotent — double-purge never
        raises).

        **Issue-keyed** — unlinks ``queue/ticket-<issue>``.

        Args:
            issue_number: The ticket whose queue marker to clear.
        """
        ...

    # ------------------------------------------------------------------
    # Rolling project status-update state (the live dashboard, phase-24 §24.2)
    # ------------------------------------------------------------------

    def get_status_update_id(self) -> str | None:
        """Return the persisted rolling status-update node id, or ``None``.

        The daemon posts ONE rolling status update in the Project's "Status
        updates" section (phase-24): the first post records the new id here so
        every later on-change refresh can ``update`` that id rather than create a
        new pill. ``None`` means no rolling update has been posted yet (first
        contact, or the stored id was cleared after a stale-id re-create).

        Returns:
            The stored ``ProjectV2StatusUpdate`` node id, or ``None`` when none
            is persisted (or the marker is absent/unreadable).
        """
        ...

    def set_status_update_id(self, status_update_id: str | None) -> None:
        """Persist the rolling status-update node id (atomically).

        Records the id :meth:`get_status_update_id` reads back. Passing ``None``
        clears the marker so the next refresh falls back to a fresh ``create``
        (used when an ``update`` failed because the stored id went stale/deleted).

        Args:
            status_update_id: The ``ProjectV2StatusUpdate`` node id to persist, or
                ``None`` to clear the marker.
        """
        ...

    def get_status_project_id(self) -> str | None:
        """Return the project node id the persisted rolling status state belongs to.

        The ``update_id`` / ``body_hash`` markers are BOARD-WIDE and carry no
        project binding of their own; this marker records WHICH project they were
        posted against (phase-33). The reporter compares it to the live
        ``deps.project_id`` and, on a mismatch (the registry was re-pointed at a
        new project), ignores the stale id+hash and posts a fresh update so the new
        board's dashboard is not suppressed by the previous project's hash.

        Returns:
            The stored project node id, or ``None`` when none is persisted (or the
            marker is absent/unreadable) — treated as a project change → fresh post.
        """
        ...

    def set_status_project_id(self, project_id: str | None) -> None:
        """Persist the project node id the rolling status state belongs to (atomically).

        Records the id :meth:`get_status_project_id` reads back, written alongside
        the first post on a new board so a later registry re-point is detectable.
        Passing ``None`` clears the marker.

        Args:
            project_id: The project node id to bind the status markers to, or
                ``None`` to clear the marker.
        """
        ...

    def get_status_body_hash(self) -> str | None:
        """Return the hash of the last-posted status-update body, or ``None``.

        Backs the on-change diffing (phase-24): the reporter renders the dashboard
        every tick but only calls the GraphQL mutation when the freshly-hashed
        body differs from this stored hash — no per-tick spam. ``None`` means
        nothing has been posted yet (so the first render always posts).

        Returns:
            The stored body hash, or ``None`` when absent/unreadable.
        """
        ...

    def set_status_body_hash(self, body_hash: str | None) -> None:
        """Persist the hash of the last-posted status-update body (atomically).

        Records the hash :meth:`get_status_body_hash` reads back, written after a
        successful post so the next tick can detect an unchanged body and skip the
        mutation. Passing ``None`` clears the marker.

        Args:
            body_hash: The body hash to persist, or ``None`` to clear it.
        """
        ...

    def get_status_last_enum(self) -> str | None:
        """Return the GitHub status ENUM last posted for the rolling update, or ``None``.

        GitHub only refreshes a Project's denormalised status PILL when a status
        update is *created* — an in-place ``update`` mutates the record's fields
        (visible via the API) but leaves the project pill frozen at the value the
        rolling update had when it was first created (observed live: a board stuck
        ``OFF_TRACK`` for days while the record read ``ON_TRACK``). The reporter
        therefore re-creates the rolling update whenever the health enum changes;
        this marker records the LAST-posted enum so a change is detectable.
        ``None`` means nothing has been posted yet (so the first render posts).

        Returns:
            The last-posted ``ProjectV2StatusUpdateStatus`` value, or ``None``
            when absent/unreadable.
        """
        ...

    def set_status_last_enum(self, status: str | None) -> None:
        """Persist the GitHub status ENUM last posted for the rolling update (atomically).

        Records the value :meth:`get_status_last_enum` reads back, written after a
        successful post alongside the body hash so the next tick can detect an
        enum change (which forces a re-create to move the project pill). Passing
        ``None`` clears the marker (e.g. on a project rebind).

        Args:
            status: The ``ProjectV2StatusUpdateStatus`` value to persist, or
                ``None`` to clear the marker.
        """
        ...

    def append_status_event(self, event: Mapping[str, object]) -> None:
        """Append one event to the bounded recent-events ring (newest kept).

        The reporter appends a small record per significant action (launch,
        teardown/cancel, gate result, auto-advance, block, reap, rate-limit-park)
        so the rendered dashboard can show "recent events". The ring is CAPPED at
        the 10 NEWEST events: appending the 11th drops the oldest. Each event is a
        small JSON-serialisable mapping, e.g. ``{"ts": …, "kind": …, "issue": …,
        "detail": …}``.

        Args:
            event: A JSON-serialisable mapping describing the event (typically
                ``ts`` / ``kind`` / ``issue`` / ``detail``).
        """
        ...

    def read_status_events(self) -> tuple[dict[str, object], ...]:
        """Return the recent-events ring, oldest-first (≤ the 10-event cap).

        Reads back the events :meth:`append_status_event` accumulated. The order
        is append order (oldest-first); the render decides the display order
        (newest-first). Degrades to an empty tuple when the ring is
        absent/corrupt — a poison ring file must never wedge the dashboard.

        Returns:
            An immutable tuple of the stored event dicts (≤10), oldest-first, or
            an empty tuple when none are persisted.
        """
        ...
