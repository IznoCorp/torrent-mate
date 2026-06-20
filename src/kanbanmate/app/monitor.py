"""Pure read-only builders for the Monitoring tab (helm PR 2-bis).

Each function takes ALREADY-FETCHED data (GitHub snapshot, persisted running states, tmux
liveness, ticket body/comments) and returns a JSON-serialisable payload. No I/O here — the HTTP
endpoints do the fetching and call these (DESIGN §4). Pure → fully unit-testable.

Layering: ``app`` may import ``core`` (pure marker parsers); it does NOT import ``cli``/``daemon``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from typing import Any

from kanbanmate.core.body_edit import roadmap_marker
from kanbanmate.core.ticket_fields import parse_ticket_fields

_KNOWN_STATES = frozenset({"running", "waiting", "blocked"})


def derive_state(status: object) -> str:
    """Map a persisted ``TicketState.status`` to a UI agent state.

    Accepts a ``TicketStatus`` enum (``(str, Enum)`` with lowercase values), or a plain string
    in any case. Normalises to lowercase and keeps only the known live/blocked states.

    Args:
        status: The store status (enum or string, e.g. ``TicketStatus.RUNNING`` / ``"RUNNING"``).

    Returns:
        ``"running"`` / ``"waiting"`` / ``"blocked"``, or ``"idle"`` for anything else.
    """
    raw = getattr(status, "value", status)  # enum → its str value; plain str passes through
    key = str(raw).lower()
    return key if key in _KNOWN_STATES else "idle"


def build_board(
    columns: Sequence[tuple[str, str, str]],
    tickets: Sequence[tuple[int, str, str]],
    running_by_issue: dict[int, str],
) -> dict[str, Any]:
    """Assemble the board-overview payload.

    Args:
        columns: ``(key, name, column_class)`` triples in board order.
        tickets: ``(number, title, column_key)`` triples.
        running_by_issue: ``{issue: state}`` for tickets with a live agent.

    Returns:
        ``{"columns", "tickets", "agents_summary"}`` (see DESIGN §5.1).
    """
    summary = {"running": 0, "waiting": 0, "blocked": 0}
    for state in running_by_issue.values():
        if state in summary:
            summary[state] += 1
    # The snapshot's ticket column is the GitHub Status option NAME (e.g. "Ready to dev"), but the
    # config columns key on a stable key that may differ ("ReadyToDev"). Map name→key (and key→key)
    # so a ticket lands under its column even for multi-word columns — without this the UI groups by
    # key and a card in a renamed/multi-word column renders nowhere.
    key_by_token: dict[str, str] = {}
    for k, n, _c in columns:
        key_by_token[k] = k
        key_by_token[n] = k
    return {
        "columns": [{"key": k, "name": n, "column_class": c} for (k, n, c) in columns],
        "tickets": [
            {
                "number": num,
                "title": title,
                "column_key": key_by_token.get(col, col),
                "agent_state": running_by_issue.get(num),
            }
            for (num, title, col) in tickets
        ],
        "agents_summary": summary,
    }


def build_agents(
    states: Iterable[Any], alive_by_issue: dict[int, bool], now: float
) -> list[dict[str, Any]]:
    """Assemble the live-agents payload from persisted states + tmux liveness.

    Args:
        states: Persisted running ``TicketState``-like objects (``.issue_number``, ``.status``,
            ``.heartbeat``, ``.stage``, ``.started``, ``.worktree``, ``.title``).
        alive_by_issue: ``{issue_number: bool}`` tmux session liveness.
        now: Wall-clock epoch (heartbeat-age + duration reference).

    Returns:
        One dict per agent (see DESIGN §5.2); the ``issue`` key is the issue number.
    """
    agents: list[dict[str, Any]] = []
    for s in states:
        issue = s.issue_number
        agents.append(
            {
                "issue": issue,
                "title": getattr(s, "title", ""),
                "stage": s.stage,
                "state": derive_state(s.status),
                "heartbeat_age": (now - s.heartbeat) if s.heartbeat else None,
                "duration_s": (now - s.started) if s.started else None,
                "branch": os.path.basename(s.worktree) if s.worktree else "",
                "session_alive": alive_by_issue.get(issue, False),
            }
        )
    return agents


def build_ticket_detail(
    number: int,
    title: str,
    column_key: str,
    body: str,
    comments: Iterable[Any],
    progress: Iterable[dict[str, str]],
) -> dict[str, Any]:
    """Assemble the on-demand ticket-detail payload (markers + comments + merged timeline).

    Args:
        number: Issue number.
        title: Issue title.
        column_key: The ticket's current column.
        body: The issue body markdown (for marker parsing).
        comments: Comment bodies in chronological order (the engine's ``IssueContext.comments``
            carries plain strings — no author/timestamp).
        progress: ``{"at", "text"}`` progress events from the store (``at`` optional).

    Returns:
        ``{number, title, column_key, body, markers, comments, timeline}`` (DESIGN §5.4). The
        timeline lists progress milestones first, then the chronological comments (the engine's
        comments have no timestamps, so a strict cross-merge isn't possible).
    """
    fields = parse_ticket_fields(body)
    markers = {
        "roadmap": roadmap_marker(body),
        "codename": fields.get("codename") or None,
        "design": fields.get("design_path") or None,
        "plans": fields.get("plan_paths") or None,
    }
    comment_list = [str(c) for c in comments]
    timeline = [
        {"kind": "progress", "at": p.get("at", ""), "text": p["text"]} for p in progress
    ] + [{"kind": "comment", "at": "", "text": c} for c in comment_list]
    return {
        "number": number,
        "title": title,
        "column_key": column_key,
        "body": body,
        "markers": markers,
        "comments": comment_list,
        "timeline": timeline,
    }
