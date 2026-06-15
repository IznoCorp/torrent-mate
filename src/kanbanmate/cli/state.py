"""Read-only unified ``kanban state`` view — board + agents + queue + events + health pill (cockpit PR1).

This is a thin **cli-layer** extension of the existing single-pane ``status`` read model
(:mod:`kanbanmate.cli.status`): it crosses ``build_status`` (per-column counts + running agents +
queue + daemon health + PAUSE/DEGRADED banners) with two extra pieces the operator/agents want at a
glance — the **recent-events ring** (``store.read_status_events``) and the **health pill** (read off
the daemon's ``status/last_status`` marker, i.e. the LAST enum the daemon computed, so this view needs
no recompute and no extra network beyond the snapshot ``build_status`` already takes).

It adds a machine-readable ``--json`` shape (for agents/scripts) alongside the human render. It is
**read-only**: nothing is moved, posted, or written (the write surface — move / ticket CRUD / pill —
lands in cockpit PR2/PR3 via the intent queue). Layering: this stays in ``cli`` (which may import
``core``/``app``/``ports``), so no ``core → cli`` edge is introduced (the aggregation deliberately
does NOT live in ``core``).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from kanbanmate.cli.status import (
    _PAUSE_FILENAME,
    DaemonHealth,
    QueuedRow,
    StatusReport,
    build_status,
    read_daemon_health,
    read_degraded,
    read_queued,
    render_status,
)
from kanbanmate.ports.board import BoardReader
from kanbanmate.ports.store import StateStore


@dataclass(frozen=True)
class StateReport:
    """The full read-model of one ``kanban state`` invocation.

    Attributes:
        status: The single-pane :class:`~kanbanmate.cli.status.StatusReport` (board counts, running
            agents, queue, daemon health, PAUSE/DEGRADED) — reused verbatim.
        events: The recent-events ring as the store persists it (oldest-first dicts ``{ts, kind,
            issue, detail}``); the renderers display it newest-first.
        health: The current health pill — the daemon's LAST-posted status enum
            (``store.get_status_last_enum``), or ``None`` when nothing has been posted yet.
    """

    status: StatusReport
    events: tuple[dict[str, object], ...] = ()
    health: str | None = None


def build_state(
    board_reader: BoardReader,
    store: StateStore,
    *,
    paused: bool = False,
    degraded: str = "",
    daemon: DaemonHealth | None = None,
    queued: list[QueuedRow] | None = None,
    now: float | None = None,
) -> StateReport:
    """Aggregate the unified read-model (pure cross of status + events ring + health pill).

    A pure aggregation over already-read inputs (the imperative :func:`state` shell reads the
    operator-pane signals): ``build_status`` supplies the board/agents/queue/daemon view, the store
    supplies the recent-events ring and the last-posted health enum. No card is moved and nothing is
    written.

    Args:
        board_reader: The board read side (a full snapshot is taken by ``build_status``).
        store: The persisted runtime state (running agents, events ring, health-pill marker).
        paused: Whether the ``PAUSE`` kill-switch is engaged (banner).
        degraded: A DEGRADED auth breadcrumb note, or ``""``.
        daemon: The crossed daemon liveness/tick-health, or ``None``.
        queued: The queued-to-launch tickets with ages, or ``None`` (treated as empty).
        now: The wall-clock the per-agent heartbeat ages are measured against, or ``None``.

    Returns:
        The assembled :class:`StateReport`.
    """
    status = build_status(
        board_reader,
        store,
        paused=paused,
        degraded=degraded,
        daemon=daemon,
        queued=queued,
        now=now,
    )
    return StateReport(
        status=status,
        events=tuple(store.read_status_events()),
        health=store.get_status_last_enum(),
    )


def _fmt_hhmm(epoch: float) -> str:
    """Format epoch seconds as a local-time ``HH:MM`` string (matches the live dashboard)."""
    t = time.localtime(epoch)
    return f"{t.tm_hour:02d}:{t.tm_min:02d}"


def render_state_json(report: StateReport) -> str:
    """Render the unified state as a machine-readable JSON string (for agents/scripts).

    The shape is stable: ``health, paused, degraded, board{columns,total}, agents[], queue[],
    events[] (newest-first), daemon``. Heartbeat ages are seconds (or ``null``); event entries are the
    raw ring dicts.

    Args:
        report: The aggregated state read-model.

    Returns:
        A pretty-printed JSON document.
    """
    s = report.status
    d = s.daemon
    payload: dict[str, object] = {
        "health": report.health,
        "paused": s.paused,
        "degraded": s.degraded,
        "board": {"columns": s.column_counts, "total": s.total_cards},
        "agents": [
            {
                "issue_number": a.issue_number,
                "session_id": a.session_id,
                "status": a.status,
                "column_key": a.column_key,
                "heartbeat_age": a.heartbeat_age,
                "attach_hint": a.attach_hint,
            }
            for a in s.agents
        ],
        "queue": [
            {"issue_number": q.issue_number, "stage": q.stage, "age": q.age} for q in s.queued
        ],
        # The ring is persisted oldest-first; surface it newest-first to match the dashboard.
        "events": [dict(e) for e in reversed(report.events)],
        "daemon": None
        if d is None
        else {
            "present": d.present,
            "age": d.age,
            "ok": d.ok,
            "last_tick_ok": d.last_tick_ok,
            "consecutive_failures": d.consecutive_failures,
            "note": d.note,
        },
    }
    return json.dumps(payload, indent=2)


def render_state_human(report: StateReport) -> str:
    """Render the unified state as the human operator pane (extends the ``status`` render).

    Appends a ``Health`` pill line and a newest-first ``Recent events`` block beneath the existing
    single-pane status render.

    Args:
        report: The aggregated state read-model.

    Returns:
        The multi-line human-readable pane.
    """
    lines = [
        render_status(report.status),
        "",
        f"Health: {report.health or '—'}",
        "",
        "Recent events",
    ]
    if report.events:
        # Newest-first: the ring is persisted oldest-first.
        for e in reversed(report.events):
            issue = f" #{e.get('issue')}" if e.get("issue") is not None else ""
            ts = e.get("ts")
            stamp = _fmt_hhmm(float(ts)) if isinstance(ts, (int, float)) else "--:--"
            detail = f" {e.get('detail')}" if e.get("detail") else ""
            lines.append(f"- {stamp} {e.get('kind', '')}{issue}{detail}".rstrip())
    else:
        lines.append("- (none)")
    return "\n".join(lines)


def state(
    board_reader: BoardReader,
    store: StateStore,
    *,
    root: Path,
    ttl: float,
    now: float | None = None,
    as_json: bool = False,
) -> str:
    """Imperative shell: read the operator-pane signals off ``root`` and render the unified state.

    Mirrors :func:`kanbanmate.cli.status.status` — reads the ``PAUSE`` kill-switch, the ``DEGRADED``
    breadcrumb, the ``daemon.heartbeat`` health, and the launch queue, then builds and renders the
    state. Read-only.

    Args:
        board_reader: The board read side.
        store: The persisted runtime state.
        root: The runtime root holding the PAUSE/DEGRADED/heartbeat markers.
        ttl: The daemon-heartbeat freshness window in seconds.
        now: The wall-clock to measure ages against; ``None`` reads the clock.
        as_json: When ``True`` emit the machine JSON shape, else the human pane.

    Returns:
        The rendered state (JSON or human), ready to print.
    """
    now = now if now is not None else time.time()
    report = build_state(
        board_reader,
        store,
        paused=(root / _PAUSE_FILENAME).exists(),
        degraded=read_degraded(root),
        daemon=read_daemon_health(root, now, ttl),
        queued=read_queued(store, now),
        now=now,
    )
    return render_state_json(report) if as_json else render_state_human(report)
