"""``kanban sessions`` — list live agent sessions in PoC TSV format (DESIGN §3.3).

``kanban sessions`` crosses the full set of persisted :class:`~kanbanmate.ports.store.TicketState`
records with the live tmux sessions: for every known ticket it asks
:meth:`~kanbanmate.ports.workspace.Sessions.is_alive` whether the ticket's session still exists.
The three-way flag mirrors the PoC ``reports.build_sessions_report`` (``reports.py:42-59``):

* ``live`` — the session is alive (:meth:`is_alive` returns ``True``).
* ``DEAD`` — ``status == RUNNING`` but the session is gone (a reaper candidate, DESIGN §8.3).
* ``stopped`` — has persisted state, NOT running, and the session is gone (the restored bucket,
  PoC parity — the state was kept-and-marked-idle, or the ticket finished).

The command is read-only (no kill, no teardown — that is ``kanban cancel``). The pure
:func:`build_sessions` builds the read-model from the two reads so tests inject fakes; the Typer
command calls :func:`sessions`.

Layering: ``cli`` is an entrypoint at the top of the import hierarchy (DESIGN §3.2); it speaks only
``ports`` Protocols here, so the store and sessions adapters are injectable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from kanbanmate.ports.store import StateStore, TicketState, TicketStatus
from kanbanmate.ports.workspace import Sessions

# The session-name convention shared with the launch/teardown flow (``ticket-<n>``). Used as a
# fallback when a persisted state has no recorded ``session_id`` (e.g. an idle record).
_SESSION_NAME_TEMPLATE = "ticket-{issue}"


@dataclass(frozen=True)
class SessionRow:
    """One session row crossing persisted state with the live tmux session.

    Attributes:
        issue_number: The ticket's GitHub issue number (the state key).
        session_name: The tmux session name probed for liveness.
        status: The coarse lifecycle marker recorded in state (a :class:`TicketStatus`).
        alive: ``True`` iff the tmux session currently exists.
        dead: ``True`` iff the state says running but no session exists — a reaper
            candidate (DESIGN §8.3).
        stopped: ``True`` iff the state is NOT running and the session is gone —
            the restored third bucket (PoC parity, ``reports.py:56-58``).
    """

    issue_number: int
    session_name: str
    status: str
    alive: bool
    dead: bool
    stopped: bool

    @property
    def flag(self) -> Literal["live", "DEAD", "stopped"]:
        """The three-way PoC flag — ``runners.py:108`` exact.

        Returns:
            ``"live"`` when the session is alive, ``"DEAD"`` when it's a reaper
            candidate, or ``"stopped"`` for a non-running ticket whose session is
            gone.
        """
        if self.alive:
            return "live"
        if self.dead:
            return "DEAD"
        return "stopped"


@dataclass(frozen=True)
class SessionsReport:
    """The full read-model of one ``kanban sessions`` invocation.

    Attributes:
        rows: One :class:`SessionRow` per known persisted ticket, issue-number
            ascending.
    """

    rows: list[SessionRow] = field(default_factory=list)


def build_sessions(store: StateStore, agent_sessions: Sessions) -> SessionsReport:
    """Build the sessions read-model by crossing every persisted state with live tmux.

    Iterates :meth:`~kanbanmate.ports.store.StateStore.list_all` — the PoC
    ``_known_issues`` analogue — so the third ``stopped`` bucket is reachable for
    non-running persisted tickets whose session is gone. The three-way flag matches
    the PoC ``reports.build_sessions_report`` (:42-59) exactly.

    Args:
        store: The persisted runtime state; :meth:`~kanbanmate.ports.store.StateStore.list_all`
            supplies the rows to probe.
        agent_sessions: The tmux session lifecycle port; only :meth:`is_alive` is called.

    Returns:
        A :class:`SessionsReport` with one row per known ticket, issue-number ascending.
    """
    rows: list[SessionRow] = []
    for state in sorted(store.list_all(), key=lambda st: st.issue_number):
        name = _session_name(state)
        alive = agent_sessions.is_alive(name)
        rows.append(
            SessionRow(
                issue_number=state.issue_number,
                session_name=name,
                status=state.status.value,
                alive=alive,
                # A reaper candidate: state claims running, but the tmux session is gone.
                dead=(state.status == TicketStatus.RUNNING and not alive),
                # The restored third bucket: has state, NOT running, session gone.
                stopped=(state.status != TicketStatus.RUNNING and not alive),
            )
        )
    return SessionsReport(rows=rows)


def _session_name(state: TicketState) -> str:
    """Return the tmux session name for a persisted state.

    Prefers the recorded ``session_id``; falls back to the ``ticket-<n>`` convention when absent so
    an idle record (no session id) still probes the canonical name.

    Args:
        state: The persisted runtime state to derive the session name from.

    Returns:
        The tmux session name to probe.
    """
    return state.session_id or _SESSION_NAME_TEMPLATE.format(issue=state.issue_number)


def render_sessions(report: SessionsReport) -> str:
    """Render a :class:`SessionsReport` as the PoC TSV session table.

    One TSV line per row: ``#<N>\\t<tmux>\\t<flag>\\t<status>`` where ``flag`` is
    ``live``, ``DEAD``, or ``stopped`` — the PoC ``runners.py:108`` format exactly.
    An empty report renders an explicit ``(none)`` sentinel.

    Args:
        report: The sessions read-model to render.

    Returns:
        The multi-line TSV as a single string (no trailing newline).
    """
    if not report.rows:
        return "(none)"
    lines: list[str] = []
    for row in report.rows:
        lines.append(f"#{row.issue_number}\t{row.session_name}\t{row.flag}\t{row.status}")
    return "\n".join(lines)


def sessions(store: StateStore, agent_sessions: Sessions) -> str:
    """Build and render the sessions report (the thin shell the Typer command calls).

    Args:
        store: The persisted runtime state (injected; an ``FsStateStore`` in production).
        agent_sessions: The tmux session lifecycle port (injected; ``TmuxSessions`` in production).

    Returns:
        The rendered PoC TSV session table, ready to print.
    """
    return render_sessions(build_sessions(store, agent_sessions))
