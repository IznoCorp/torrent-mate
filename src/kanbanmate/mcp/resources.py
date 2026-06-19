"""Pure serializers backing the MCP read resources (conduit DESIGN §5).

Each function takes already-wired ports (:class:`~kanbanmate.ports.board.BoardReader`,
:class:`~kanbanmate.ports.store.StateStore`) plus plain values and returns a JSON-serialisable
``dict`` (or ``list``/``str``/``None``) — so every resource is unit-testable WITHOUT the MCP SDK.

The serializers reuse the existing read models verbatim and surface their REAL fields:

* :func:`board` reuses the imperative ``cli.state.state(...)`` shell (it already reads
  ``PAUSE``/``DEGRADED``/daemon-heartbeat/queue off ``root`` and renders the stable JSON shape).
* :func:`ticket` crosses ``board_reader.issue_context(n)`` with the matching ``Ticket`` from a
  fresh snapshot, mirroring the launch-prompt enrichment (``app/launch_context.py:70-77``).
* :func:`agents` / :func:`queue` / :func:`health` / :func:`events` read the narrower store methods
  directly so each resource stays cheap.
"""

from __future__ import annotations

import json
from pathlib import Path

from kanbanmate.cli.doctor import HEARTBEAT_TTL_FLOOR
from kanbanmate.cli.state import state as state_shell
from kanbanmate.ports.board import BoardReader
from kanbanmate.ports.store import StateStore


def board(board_reader: BoardReader, store: StateStore, *, root: Path) -> dict[str, object]:
    """Serialize the unified board read-model (the ``kanban://board`` resource).

    Reuses the imperative ``cli.state.state(...)`` shell (``cli/state.py:190``) with
    ``as_json=True`` and parses its JSON back into a ``dict`` — it already reads the
    ``PAUSE``/``DEGRADED``/daemon-heartbeat/queue signals off ``root`` and renders the stable shape:
    ``health, paused, degraded, board{columns,total}, agents[], queue[], events[] (newest-first),
    daemon`` (``cli/state.py:108-155``). ``HEARTBEAT_TTL_FLOOR`` is the same daemon-heartbeat
    freshness window the CLI ``state``/``status`` commands use (``cli/doctor.py:91``).

    Args:
        board_reader: The board read side (a full snapshot is taken by the shell).
        store: The persisted runtime state (running agents, events ring, health-pill marker).
        root: The runtime root holding the PAUSE/DEGRADED/heartbeat/queue markers.

    Returns:
        The unified state as a JSON-serialisable ``dict``.
    """
    rendered = state_shell(board_reader, store, root=root, ttl=HEARTBEAT_TTL_FLOOR, as_json=True)
    parsed: dict[str, object] = json.loads(rendered)
    return parsed


def ticket(board_reader: BoardReader, n: int) -> dict[str, object]:
    """Serialize one ticket's rich context (the ``kanban://ticket/{n}`` resource).

    Crosses ``board_reader.issue_context(n)`` (``ports/board.py:68`` →
    :class:`~kanbanmate.adapters.github.types.IssueContext` carrying ``body`` / ``comments`` /
    ``linked_issue_body``) with the matching :class:`~kanbanmate.core.domain.Ticket` from a fresh
    ``board_reader.snapshot()`` (``ports/board.py:41``) for the ``title`` + ``column_key``. This is
    the same enrichment ``app/launch_context.py:70-77`` builds for the launch prompt.

    Args:
        board_reader: The board read side (snapshot + issue-context calls).
        n: The issue number whose rich context to fetch.

    Returns:
        ``{issue_number, title, column_key, body, comments[], linked_issue_body}``. ``title`` /
        ``column_key`` are ``None`` when the ticket is not present on the board snapshot.
    """
    ctx = board_reader.issue_context(n)
    snapshot = board_reader.snapshot()
    match = next((t for t in snapshot.tickets if t.issue_number == n), None)
    return {
        "issue_number": n,
        "title": match.title if match is not None else None,
        "column_key": match.column_key if match is not None else None,
        "body": ctx.body,
        # IssueContext.comments is a tuple (≤50, chronological); list() for JSON.
        "comments": list(ctx.comments),
        "linked_issue_body": ctx.linked_issue_body,
    }


def agents(store: StateStore) -> list[dict[str, object]]:
    """Serialize the live agents (the ``kanban://agents`` resource).

    One row per LIVE :class:`~kanbanmate.ports.store.TicketState` from ``store.list_running()``
    (``ports/store.py:293``). The serialized fields are the REAL ``TicketState`` attributes
    (``ports/store.py:81-161``); ``status`` is rendered as its enum ``.value`` so the payload is
    JSON-serialisable.

    Args:
        store: The persisted runtime state.

    Returns:
        A list of agent rows, one per running/waiting ticket.
    """
    return [
        {
            "issue_number": s.issue_number,
            "item_id": s.item_id,
            "session_id": s.session_id,
            "status": s.status.value,
            "heartbeat": s.heartbeat,
            "stage": s.stage,
            "profile": s.profile,
            "mode": s.mode,
            "started": s.started,
            "worktree": s.worktree,
            "retries": s.retries,
        }
        for s in store.list_running()
    ]


def queue(store: StateStore) -> list[dict[str, object]]:
    """Serialize the launch queue (the ``kanban://queue`` resource).

    Each queued ticket from ``store.dequeue_pending()`` (``ports/store.py:667``) crossed with its
    marker payload from ``store.load_queued(n)`` (``ports/store.py:687``), which persists ``stage``
    and ``enqueued_at`` (``cli/status.py:416-436`` reads the same keys). A corrupt/absent marker
    degrades to an empty payload (``None`` → ``{}``).

    Args:
        store: The persisted runtime state.

    Returns:
        ``[{issue_number, stage, enqueued_at}]`` in the store's lexicographic queue order.
    """
    rows: list[dict[str, object]] = []
    for issue in store.dequeue_pending():
        payload = store.load_queued(issue) or {}
        rows.append(
            {
                "issue_number": issue,
                "stage": payload.get("stage"),
                "enqueued_at": payload.get("enqueued_at"),
            }
        )
    return rows


def health(store: StateStore) -> str | None:
    """Serialize the health pill (the ``kanban://health`` resource).

    Returns ``store.get_status_last_enum()`` (``ports/store.py:805``) — the last-posted
    ``ProjectV2StatusUpdateStatus`` enum, or ``None`` when nothing has been posted yet.

    Args:
        store: The persisted runtime state.

    Returns:
        The last-posted status enum string, or ``None``.
    """
    return store.get_status_last_enum()


def events(store: StateStore) -> list[dict[str, object]]:
    """Serialize the recent-events ring (the ``kanban://events`` resource).

    Reads ``store.read_status_events()`` (``ports/store.py:873``), which returns the ≤10-event ring
    OLDEST-first, and surfaces it NEWEST-first (matching the live dashboard, ``cli/state.py:143``).
    Each row is the raw persisted mapping (``{ts, kind, issue, detail}``, ``ports/store.py:857-871``).

    Args:
        store: The persisted runtime state.

    Returns:
        The recent-events ring (≤10), newest-first, as plain dicts.
    """
    # The ring is persisted oldest-first; surface it newest-first to match the dashboard render.
    return [dict(e) for e in reversed(store.read_status_events())]
