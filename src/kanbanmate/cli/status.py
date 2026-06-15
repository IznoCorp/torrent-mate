"""``kanban status`` — board reconciliation summary (DESIGN §3.3, ported from PoC ``cli/reports.py``).

``kanban status`` answers "what does the board look like right now, and which agents are running?"
by crossing two read sources:

1. a :class:`~kanbanmate.core.domain.BoardSnapshot` from a :class:`~kanbanmate.ports.board.BoardReader`
   (the per-column card counts), and
2. the persisted running :class:`~kanbanmate.ports.store.TicketState` records from a
   :class:`~kanbanmate.ports.store.StateStore` (the live-agent rows).

The whole command is read-only: it never moves a card, comments, or touches a worktree. The summary
is built by the pure :func:`build_status` from the two reads, so tests drive fakes and assert on the
returned model without any I/O; :func:`render_status` turns that model into the printed table and
:func:`status` is the thin shell the Typer command calls.

Layering: ``cli`` is an entrypoint at the top of the import hierarchy (DESIGN §3.2); it composes the
concrete adapters in production but speaks only ``ports`` Protocols in its logic, so the reader and
store are injectable.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from kanbanmate.core.heartbeat import DEFAULT_FAILURE_THRESHOLD, Heartbeat, parse_heartbeat
from kanbanmate.ports.board import BoardReader
from kanbanmate.ports.store import StateStore, TicketState

# Root-level sentinel / marker filenames the operator pane crosses (DESIGN §5 / §10). They live
# beside ``config.yml`` in the runtime root (``~/.kanban`` in production); the names mirror the
# daemon writers (``daemon.loop.PAUSE_FILENAME`` / ``DEGRADED_FILENAME`` / the heartbeat write).
_PAUSE_FILENAME = "PAUSE"
_DEGRADED_FILENAME = "DEGRADED"
_HEARTBEAT_FILENAME = "daemon.heartbeat"


@dataclass(frozen=True)
class AgentRow:
    """One running-agent row in the status report.

    Attributes:
        issue_number: The ticket's GitHub issue number (the state key).
        session_id: The tmux session hosting the agent, or ``None`` when idle.
        status: The coarse lifecycle marker recorded in state (e.g. ``"running"``).
        heartbeat: The wall-clock timestamp of the agent's last liveness heartbeat.
        column_key: The ticket's CURRENT board column, resolved from the live
            snapshot by issue number (#9 PoC parity, ``cli/reports.py:26-39``). It is
            ``None`` when the ticket is not present on the snapshot (a running agent
            whose card was moved off the board / closed between the launch and this
            read) — surfaced as ``?`` so the absence is explicit, never blank.
    """

    issue_number: int
    session_id: str | None
    status: str
    heartbeat: float
    column_key: str | None = None
    heartbeat_age: float | None = None
    attach_hint: str = ""


@dataclass(frozen=True)
class QueuedRow:
    """One queued (waiting-to-launch) ticket row in the operator pane (31.1).

    A ticket is enqueued when the concurrency cap is full at launch time (DESIGN §7); the marker
    persists ``{item_id, stage, enqueued_at}`` so the queue survives a restart. The status pane
    surfaces these so a queued card no longer looks like a dead card.

    Attributes:
        issue_number: The queued ticket's GitHub issue number.
        stage: The column the queued launch will fire into when a slot frees (from the marker).
        age: Seconds the ticket has been queued (``now - enqueued_at``), or ``None`` when the
            marker carried no ``enqueued_at`` (old-format) so the absence is explicit, never ``0``.
    """

    issue_number: int
    stage: str
    age: float | None = None


@dataclass(frozen=True)
class DaemonHealth:
    """The daemon's liveness + tick-health, crossed from the heartbeat marker (31.1).

    Built from the ``daemon.heartbeat`` JSON (DESIGN §5, phase-30 ``core/heartbeat.py``). It tells
    the operator whether the background loop is alive AND succeeding — the kill-switch is folklore
    and a silent 401-loop stays green without this surfaced on the daily interface.

    Attributes:
        present: Whether a heartbeat marker was found (a daemon that never ticked has none).
        age: Seconds since the marker was written (``now - ts``), or ``None`` when absent/unparseable.
        ok: Whether the daemon is healthy — fresh AND below the consecutive-failure threshold.
        last_tick_ok: Whether the most recent tick returned without raising (from the marker).
        consecutive_failures: How many ticks in a row have raised (from the marker).
        note: A short human note when the marker is absent or could not be parsed (else ``""``).
    """

    present: bool
    age: float | None = None
    ok: bool = False
    last_tick_ok: bool = True
    consecutive_failures: int = 0
    note: str = ""


@dataclass(frozen=True)
class StatusReport:
    """The full read-model of one ``kanban status`` invocation.

    Attributes:
        column_counts: ``{column_key: card_count}`` over every ticket on the board, in board
            (insertion) order as observed in the snapshot.
        agents: One :class:`AgentRow` per persisted running ticket, ordered by issue number.
        total_cards: The total number of cards on the board (sum of ``column_counts``).
        paused: Whether the ``PAUSE`` kill-switch sentinel is engaged (→ a banner; 31.1).
        degraded: A short DEGRADED note (a 401/403 auth breadcrumb the daemon dropped), or ``""``.
        daemon: The daemon liveness + tick-health, or ``None`` when not crossed (pure-test path).
        queued: The queued-to-launch tickets with ages, ordered by issue number (31.1).
    """

    column_counts: dict[str, int]
    agents: list[AgentRow] = field(default_factory=list)
    total_cards: int = 0
    paused: bool = False
    degraded: str = ""
    daemon: DaemonHealth | None = None
    queued: list[QueuedRow] = field(default_factory=list)


def build_status(
    board_reader: BoardReader,
    store: StateStore,
    *,
    paused: bool = False,
    degraded: str = "",
    daemon: DaemonHealth | None = None,
    queued: list[QueuedRow] | None = None,
    now: float | None = None,
) -> StatusReport:
    """Build the status read-model from a board snapshot, persisted state, and operator-pane inputs.

    A pure aggregation: per-column card counts come from the snapshot, the running-agent rows from
    the store's running states, and the single-pane operator signals (paused / degraded / daemon
    health / queue) are passed in already-read by the imperative :func:`status` shell so this stays
    pure and testable (DESIGN §3.3 ``status``; 31.1). No card is moved and nothing is written.

    Args:
        board_reader: The board read side; a full :meth:`~kanbanmate.ports.board.BoardReader.snapshot`
            is taken (cheap-probe gating is the daemon's concern, not the operator's status view).
        store: The persisted runtime state; :meth:`~kanbanmate.ports.store.StateStore.list_running`
            supplies the live-agent rows.
        paused: Whether the ``PAUSE`` kill-switch is engaged (renders a banner, 31.1).
        degraded: A DEGRADED auth breadcrumb note, or ``""`` when none (31.1).
        daemon: The crossed daemon liveness + tick-health, or ``None`` (pure-test default).
        queued: The queued-to-launch tickets with ages, or ``None`` (treated as empty, 31.1).
        now: The wall-clock time the per-agent heartbeat ages are measured against; ``None`` (the
            default, used by the pure tests) leaves the ages ``None`` so the table omits them.

    Returns:
        A :class:`StatusReport` with the per-column counts, agent rows, and operator-pane signals.
    """
    snapshot = board_reader.snapshot()
    # Counter preserves first-seen order on Python 3.7+, so the table mirrors the board's column
    # order as the snapshot yields it rather than re-sorting alphabetically.
    counts: Counter[str] = Counter()
    # Issue → current column lookup so the running-agents section can show each agent's
    # CURRENT board column (#9 PoC parity — recovers the per-ticket column the PoC TSV gave).
    column_by_issue: dict[int, str] = {}
    for ticket in snapshot.tickets:
        counts[ticket.column_key] += 1
        if ticket.issue_number is not None:
            column_by_issue[ticket.issue_number] = ticket.column_key

    agents = [_agent_row(state, column_by_issue, now) for state in _sorted_running(store)]
    return StatusReport(
        column_counts=dict(counts),
        agents=agents,
        total_cards=sum(counts.values()),
        paused=paused,
        degraded=degraded,
        daemon=daemon,
        queued=queued if queued is not None else [],
    )


def _sorted_running(store: StateStore) -> list[TicketState]:
    """Return the persisted running states ordered by issue number (stable table output).

    Args:
        store: The persisted runtime state to read running tickets from.

    Returns:
        The running :class:`~kanbanmate.ports.store.TicketState` records, issue-number ascending.
    """
    return sorted(store.list_running(), key=lambda st: st.issue_number)


def _agent_row(state: TicketState, column_by_issue: dict[int, str], now: float | None) -> AgentRow:
    """Project a persisted :class:`~kanbanmate.ports.store.TicketState` onto an :class:`AgentRow`.

    The current board column is resolved from ``column_by_issue`` (built from the
    live snapshot) so the running-agents section recovers the PoC's per-ticket
    ``#issue column status session_uuid`` tuple (#9). A running ticket absent from
    the snapshot maps to ``None`` (rendered ``?``).

    The per-agent heartbeat AGE (``now - heartbeat``) is computed when ``now`` is supplied and the
    agent has a non-zero heartbeat — collected for completeness (31.1) though deliberately not
    rendered in the table. A concrete ``tmux attach -t ticket-<n>`` hint is always built so the
    operator has a copy-pasteable way to drop into any running/waiting agent's session.

    Args:
        state: The persisted running state to project.
        column_by_issue: The ``{issue_number: column_key}`` map from the snapshot.
        now: The wall-clock time the heartbeat age is measured against, or ``None`` to skip it.

    Returns:
        The corresponding :class:`AgentRow` for the report.
    """
    # Heartbeat age is collected (31.1) but never rendered — a 0.0/absent heartbeat means "no
    # heartbeat yet" → None, otherwise the elapsed seconds since the last liveness touch.
    heartbeat_age = (now - state.heartbeat) if (now is not None and state.heartbeat) else None
    return AgentRow(
        issue_number=state.issue_number,
        session_id=state.session_id,
        status=state.status,
        heartbeat=state.heartbeat,
        column_key=column_by_issue.get(state.issue_number),
        heartbeat_age=heartbeat_age,
        # Concrete drop-in hint — the tmux session name is ``ticket-<issue>`` everywhere (the same
        # derivation the launcher/reaper use), so the operator can attach without guessing.
        attach_hint=f"tmux attach -t ticket-{state.issue_number}",
    )


def render_status(report: StatusReport) -> str:
    """Render a :class:`StatusReport` as the printable two-section text table.

    The first section lists per-column card counts (one line per column plus a total); the second
    lists the running agents (issue, current column, session, status). An empty board / no agents
    render an explicit "(none)" so the output is never ambiguously blank.

    **#9 PoC parity (PORT, snapshot-adapted).** The PoC (``cli/runners.py:87-96`` +
    ``reports.build_status_report:26-39``) emitted one TSV row per persisted ticket —
    ``#<issue>\t<column>\t<status>\t<session_uuid>``. NEW's TSV *form* is
    intentionally dropped (the two-section table is the richer artifact the polling
    model warrants), but the per-ticket DATA the TSV carried is RESTORED here: each
    running agent's CURRENT board ``column`` (resolved from the live snapshot by
    issue number) is rendered alongside its ``session`` and ``status``, recovering
    the PoC's ``#issue column status session_uuid`` tuple per ticket. This is a
    data-model restoration, not a format rollback.

    **Single pane of glass (31.1).** When operator-pane signals are present the render leads with a
    banner block: a PAUSED line (kill-switch engaged), a DEGRADED line (a 401/403 auth breadcrumb),
    and a one-line daemon-health summary (last-tick age + OK/FAILING from the heartbeat JSON). A
    queued-tickets section lists cards waiting on a free slot with their ages, and each running/
    waiting agent line carries a concrete ``tmux attach -t ticket-<n>`` hint. A board with no
    operator-pane data crossed (the pure-test path) renders only the two original sections.

    Args:
        report: The status read-model to render.

    Returns:
        The multi-line table as a single string (no trailing newline).
    """
    lines: list[str] = []
    _render_banner(report, lines)

    lines.append("Board columns:")
    if report.column_counts:
        width = max(len(key) for key in report.column_counts)
        for column_key, count in report.column_counts.items():
            lines.append(f"  {column_key:<{width}}  {count}")
        lines.append(f"  {'TOTAL':<{width}}  {report.total_cards}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Running agents:")
    if report.agents:
        for row in report.agents:
            session = row.session_id or "-"
            # The CURRENT column from the snapshot; ``?`` when the running ticket is
            # absent from the board (moved off / closed since launch) — never blank.
            column = row.column_key if row.column_key else "?"
            lines.append(
                f"  #{row.issue_number}  column={column}  session={session}  status={row.status}"
            )
            # The concrete drop-in hint (31.1): a copy-pasteable tmux attach for this agent.
            if row.attach_hint:
                lines.append(f"      attach: {row.attach_hint}")
    else:
        lines.append("  (none)")

    _render_queued(report, lines)
    return "\n".join(lines)


def _render_banner(report: StatusReport, lines: list[str]) -> None:
    """Append the operator-pane banner (PAUSED / DEGRADED / daemon health) to ``lines`` (31.1).

    A no-op when no operator-pane signal is present (the pure-test path renders only the two
    original sections). Otherwise the banner leads the output so the kill-switch, an auth-degraded
    daemon, and the loop's last-tick health are visible at a glance — the single-pane intent.

    Args:
        report: The status read-model carrying the operator-pane signals.
        lines: The output line accumulator, appended in place.
    """
    emitted = False
    if report.paused:
        lines.append("⏸  PAUSED — kill-switch engaged (PAUSE sentinel); no agents will launch.")
        emitted = True
    if report.degraded:
        lines.append(f"⚠  DEGRADED — {report.degraded}")
        emitted = True
    daemon = report.daemon
    if daemon is not None:
        if not daemon.present:
            note = daemon.note or "no heartbeat marker (daemon may not be running)"
            lines.append(f"Daemon: UNKNOWN — {note}")
        else:
            age = "?" if daemon.age is None else f"{daemon.age:.0f}s ago"
            health = "OK" if daemon.ok else "FAILING"
            lines.append(
                f"Daemon: {health} — last tick {age} "
                f"(last_tick_ok={daemon.last_tick_ok}, failures={daemon.consecutive_failures})"
            )
        emitted = True
    if emitted:
        lines.append("")


def _render_queued(report: StatusReport, lines: list[str]) -> None:
    """Append the queued-to-launch section to ``lines`` (31.1).

    A no-op when nothing is queued AND no operator-pane data was crossed (the pure-test path keeps
    its two-section output). When the operator pane is active the section is always emitted (even
    empty, as ``(none)``) so a queued card is never mistaken for a dead one.

    Args:
        report: The status read-model carrying the queued rows.
        lines: The output line accumulator, appended in place.
    """
    # Only render the section when the operator pane is active (any of the crossed signals present)
    # or there is something queued — the pure-test path crosses none of these and keeps its output.
    pane_active = report.paused or bool(report.degraded) or report.daemon is not None
    if not report.queued and not pane_active:
        return
    lines.append("")
    lines.append("Queued (waiting for a free slot):")
    if report.queued:
        for row in report.queued:
            age = "?" if row.age is None else f"{row.age:.0f}s"
            stage = row.stage or "?"
            lines.append(f"  #{row.issue_number}  stage={stage}  queued={age}")
    else:
        lines.append("  (none)")


def read_daemon_health(root: Path, now: float, ttl: float) -> DaemonHealth:
    """Cross the ``daemon.heartbeat`` marker into a :class:`DaemonHealth` (31.1, DESIGN §5).

    Mirrors the doctor heartbeat check (``cli/doctor._check_heartbeat_fresh``) but degrades to a
    NOTE instead of failing: a missing marker is ``present=False`` (daemon not running / never
    ticked), an unparseable marker carries a parse note, and a present one is ``ok`` only when it
    is BOTH fresh (age ≤ ``ttl``) AND below the consecutive-failure threshold — so a silent
    401-loop daemon stops looking healthy on the operator's daily pane.

    Args:
        root: The runtime root holding the ``daemon.heartbeat`` marker.
        now: The wall-clock time the heartbeat age is measured against.
        ttl: The freshness window in seconds; an older marker is not ``ok``.

    Returns:
        The crossed :class:`DaemonHealth`.
    """
    marker_file = root / _HEARTBEAT_FILENAME
    if not marker_file.exists():
        return DaemonHealth(present=False, note="no heartbeat marker (daemon may not be running)")
    try:
        heartbeat: Heartbeat = parse_heartbeat(marker_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return DaemonHealth(present=True, note=f"cannot parse heartbeat marker: {exc}")
    age = now - heartbeat.ts
    fresh = age <= ttl
    healthy = fresh and heartbeat.consecutive_failures < DEFAULT_FAILURE_THRESHOLD
    return DaemonHealth(
        present=True,
        age=age,
        ok=healthy,
        last_tick_ok=heartbeat.last_tick_ok,
        consecutive_failures=heartbeat.consecutive_failures,
    )


def read_degraded(root: Path) -> str:
    """Return the DEGRADED auth-breadcrumb note (a 401/403 the daemon dropped), or ``""`` (31.1).

    Args:
        root: The runtime root holding the ``DEGRADED`` sentinel.

    Returns:
        The trimmed sentinel contents when present, else ``""`` (absent / unreadable).
    """
    sentinel = root / _DEGRADED_FILENAME
    try:
        return sentinel.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_queued(store: StateStore, now: float) -> list[QueuedRow]:
    """Read the queued-to-launch tickets with ages from the store (31.1, DESIGN §7).

    Crosses each queue marker's persisted ``enqueued_at`` into an age; a marker without it
    (old-format) leaves the age ``None`` rather than reporting a misleading ``0``. Rows are
    issue-number ascending for a stable pane.

    Args:
        store: The persisted runtime state; ``dequeue_pending`` lists the queued issues and
            ``load_queued`` reads each marker payload.
        now: The wall-clock time the queued ages are measured against.

    Returns:
        The queued rows, issue-number ascending (possibly empty).
    """
    rows: list[QueuedRow] = []
    for issue in store.dequeue_pending():
        payload = store.load_queued(issue) or {}
        enqueued_at = payload.get("enqueued_at")
        age = (now - float(enqueued_at)) if isinstance(enqueued_at, (int, float)) else None
        rows.append(QueuedRow(issue_number=issue, stage=str(payload.get("stage", "")), age=age))
    return sorted(rows, key=lambda r: r.issue_number)


def status(
    board_reader: BoardReader,
    store: StateStore,
    *,
    root: Path | None = None,
    ttl: float,
) -> str:
    """Build and render the status report (the thin shell the Typer command calls).

    When ``root`` is given the shell crosses the runtime root's operator-pane signals — the
    ``PAUSE`` kill-switch, the ``DEGRADED`` auth breadcrumb, the ``daemon.heartbeat`` health, and
    the launch queue — into the single pane (31.1). The pure :func:`build_status` /
    :func:`render_status` do the aggregation/formatting; this shell owns only the marker/queue I/O.

    Args:
        board_reader: The board read side (injected; a ``GithubClient`` in production).
        store: The persisted runtime state (injected; an ``FsStateStore`` in production).
        root: The runtime root holding the PAUSE/DEGRADED/heartbeat markers; ``None`` crosses none
            (a board-only view).
        ttl: The daemon-heartbeat freshness window in seconds (the same TTL doctor derives).

    Returns:
        The rendered status table, ready to print.
    """
    now = time.time()
    if root is None:
        return render_status(build_status(board_reader, store, now=now))
    return render_status(
        build_status(
            board_reader,
            store,
            paused=(root / _PAUSE_FILENAME).exists(),
            degraded=read_degraded(root),
            daemon=read_daemon_health(root, now, ttl),
            queued=read_queued(store, now),
            now=now,
        )
    )


@dataclass(frozen=True)
class PauseResult:
    """The outcome of a :func:`pause` / :func:`resume` toggle (31.1).

    Attributes:
        paused: The resulting kill-switch state (``True`` after ``pause``, ``False`` after ``resume``).
        changed: Whether this call actually flipped the sentinel (``False`` when it was already in
            the target state — idempotent no-op).
        sentinel: The absolute path to the ``PAUSE`` sentinel the toggle acted on.
    """

    paused: bool
    changed: bool
    sentinel: Path


def pause(root: Path) -> PauseResult:
    """Engage the kill-switch by creating the ``PAUSE`` sentinel under ``root`` (DESIGN §10, 31.1).

    Idempotent: when the sentinel already exists the call is a no-op (``changed=False``). The
    sentinel's mere presence is the signal — its content is not read by the daemon, so an empty
    marker file suffices.

    Args:
        root: The kanban runtime root the ``PAUSE`` sentinel is created under.

    Returns:
        The :class:`PauseResult` describing the resulting state.
    """
    sentinel = root / _PAUSE_FILENAME
    if sentinel.exists():
        return PauseResult(paused=True, changed=False, sentinel=sentinel)
    # Create the empty sentinel (the daemon reads only its PRESENCE). ``touch`` is sufficient and
    # leaves an existing root untouched; the parent root is assumed to exist (created by install).
    sentinel.touch()
    return PauseResult(paused=True, changed=True, sentinel=sentinel)


def resume(root: Path) -> PauseResult:
    """Release the kill-switch by removing the ``PAUSE`` sentinel under ``root`` (DESIGN §10, 31.1).

    Idempotent: when the sentinel is absent the call is a no-op (``changed=False``).

    Args:
        root: The kanban runtime root the ``PAUSE`` sentinel is removed from.

    Returns:
        The :class:`PauseResult` describing the resulting state.
    """
    sentinel = root / _PAUSE_FILENAME
    if not sentinel.exists():
        return PauseResult(paused=False, changed=False, sentinel=sentinel)
    # unlink-if-exists; a missing sentinel is already handled above, so this only races with a
    # concurrent resume (rare for a solo operator) — tolerate that with missing_ok.
    sentinel.unlink(missing_ok=True)
    return PauseResult(paused=False, changed=True, sentinel=sentinel)


def render_pause(result: PauseResult) -> str:
    """Render the message for a :func:`pause` outcome (the thin shell the Typer command echoes).

    Args:
        result: The pause outcome to render.

    Returns:
        A one-line human message naming the resulting state and whether it changed.
    """
    if result.changed:
        return f"kanban pause: kill-switch ENGAGED — {result.sentinel} created; no agents launch."
    return f"kanban pause: already paused — {result.sentinel} present (no change)."


def render_resume(result: PauseResult) -> str:
    """Render the message for a :func:`resume` outcome (the thin shell the Typer command echoes).

    Args:
        result: The resume outcome to render.

    Returns:
        A one-line human message naming the resulting state and whether it changed.
    """
    if result.changed:
        return f"kanban resume: kill-switch RELEASED — {result.sentinel} removed; launches resume."
    return f"kanban resume: not paused — {result.sentinel} absent (no change)."
