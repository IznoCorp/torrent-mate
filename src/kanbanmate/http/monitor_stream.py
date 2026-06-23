"""Server-Sent-Events push source for the Monitoring + board views (keel STEP 4).

Steps 2-3 made the board view + Monitoring tab read PLACEMENT from the local ``board.json``
(authority) and poll it at ~4 s. This module pushes that same change signal to the SPA over a
single long-lived ``text/event-stream`` connection so a board change (an operator drag through
KanbanMateUI, OR the daemon's intent-drain / auto-advance — BOTH bump the store ``version``)
surfaces SUB-SECOND instead of waiting out the next poll.

What the stream emits, and what it must NEVER do:

* **Change signal only** — the per-project ``board.json`` ``version`` int (the same cheap token the
  board endpoints already return) plus the daemon ``daemon.heartbeat`` ``ts`` (so a daemon tick is
  observable even when placement is unchanged). The client RE-FETCHES the real payloads
  (``/api/monitor/board`` + ``/api/board/state``) on a change event — the stream carries no board
  state, so a dropped event only costs one extra refetch.
* **NO GitHub in the stream path** (CONSTRAINT). The version read is a local ``stat`` + a tiny JSON
  parse of ``board.json``; the tick read is a local file read of ``daemon.heartbeat``. Neither
  touches the network — a GitHub outage never stalls or kills the stream.
* **Bounded CPU** — the generator SLEEPS ``poll_interval`` (default ~1 s) between cheap local reads;
  it never busy-spins. A keep-alive SSE comment is emitted at most every ``keepalive_interval`` so an
  idle board still proves the connection is live (and keeps intermediaries from reaping it).

Auth + the project selector are enforced by the THIN route in ``monitor_routes.py`` (it resolves the
entry via ``_resolve_entry`` and runs behind the same ``@app.middleware('http')`` auth guard every
other ``/api/*`` route uses) — a streaming endpoint that bypassed auth would leak board state. This
module is the pure-ish stream BODY: it is handed the already-resolved version/tick readers, so it has
no knowledge of auth, FastAPI, or the registry, which keeps it directly unit-testable.

Layering: ``http`` is a top entrypoint — it may import ``adapters`` (the board store) + ``core``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

# Defaults (overridable by the route / tests). The poll interval is the sub-second floor on how
# stale the change signal can be; the keep-alive bounds how long an idle connection stays silent.
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_KEEPALIVE_INTERVAL = 20.0


def read_board_version(board_path: Path) -> int | None:
    """Read JUST the ``version`` int from a ``board.json`` (cheap: stat-gated + a tiny parse).

    Returns the integer board revision, or ``None`` when the file is absent / unreadable / malformed
    / carries no integer ``version`` (an un-imported board, or a torn write mid-``os.replace``). The
    caller treats ``None`` as "no change to report" so a transient read race never emits a bogus
    event nor crashes the stream. NO GitHub, NO lock — a lock-free read is safe because the writer
    replaces ``board.json`` atomically (``os.replace``), so a reader sees either the old or the new
    whole file, never a torn one.

    Args:
        board_path: The per-project ``board.json`` path.

    Returns:
        The ``version`` integer, or ``None`` when it cannot be read.
    """
    try:
        # stat-gate first: ``exists()`` avoids raising on the common absent-board case.
        if not board_path.exists():
            return None
        raw = board_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return None
    version = doc.get("version") if isinstance(doc, dict) else None
    # ``bool`` is an ``int`` subclass — a JSON ``true`` must not read as version 1.
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


def read_daemon_tick(heartbeat_path: Path) -> float | None:
    """Read the daemon ``daemon.heartbeat`` freshness ``ts`` (the tick signal), or ``None``.

    The daemon rewrites this marker after every tick (``loop.py`` — JSON ``{"ts": …}``, or a legacy
    bare-epoch float). A changing ``ts`` proves a tick happened even when placement is unchanged (e.g.
    a heartbeat-only tick) so the SPA can keep its agent overlay fresh. Fully local — NO GitHub.
    ``None`` on any read/parse failure (treated as "no tick change to report").

    Args:
        heartbeat_path: The runtime-root ``daemon.heartbeat`` path.

    Returns:
        The heartbeat ``ts`` (POSIX seconds), or ``None`` when unreadable.
    """
    try:
        if not heartbeat_path.exists():
            return None
        raw = heartbeat_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    # Reuse the canonical heartbeat parser so JSON + legacy plain-epoch are handled identically to
    # doctor/status; degrade to None on garbage rather than letting it kill the stream.
    try:
        from kanbanmate.core.heartbeat import parse_heartbeat  # noqa: PLC0415

        return parse_heartbeat(raw).ts
    except ValueError:
        return None


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """Format one SSE message frame (``event:`` + a single ``data:`` JSON line + a blank line)."""
    return f"event: {event}\ndata: {json.dumps(data, sort_keys=True)}\n\n"


def _sse_comment(text: str) -> str:
    """Format an SSE keep-alive comment line (``:`` prefix — ignored by EventSource, keeps it open)."""
    return f": {text}\n\n"


async def monitor_event_stream(
    version_reader: Callable[[], int | None],
    tick_reader: Callable[[], float | None],
    *,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    keepalive_interval: float = DEFAULT_KEEPALIVE_INTERVAL,
    max_iterations: int | None = None,
    sleep: Callable[[float], Any] | None = None,
) -> AsyncIterator[str]:
    """Yield SSE frames: a ``change`` event on a version/tick change + periodic keep-alive comments.

    The loop, per iteration: read the (local, cheap) version + tick; if EITHER differs from the
    last-emitted value, yield an ``event: change`` carrying both; else, once ``keepalive_interval``
    has elapsed since the last frame, yield a keep-alive comment. Then SLEEP ``poll_interval`` (the
    bounded-CPU discipline — never a busy-loop). An initial ``change`` is always emitted first so the
    client can confirm the stream is live and seed its baseline without waiting for the first edit.

    The readers are injected (the route binds them to the resolved project's ``board.json`` +
    ``daemon.heartbeat``) so this body is unit-testable with plain callables and a fake sleep, and
    carries no FastAPI / auth / GitHub knowledge.

    Args:
        version_reader: Zero-arg callable returning the current board ``version`` int (or ``None``).
        tick_reader: Zero-arg callable returning the daemon heartbeat ``ts`` (or ``None``).
        poll_interval: Seconds slept between cheap local reads (the sub-second change floor).
        keepalive_interval: Max seconds of silence before a keep-alive comment is emitted.
        max_iterations: Stop after this many loop iterations (tests); ``None`` runs until the client
            disconnects (the ASGI server closes the generator).
        sleep: Async sleep function (defaults to :func:`asyncio.sleep`; injectable for tests so the
            loop does not actually wait).

    Yields:
        SSE-formatted ``str`` frames (``event: change`` / keep-alive comments).
    """
    do_sleep = sleep if sleep is not None else asyncio.sleep
    last_version: int | None = None
    last_tick: float | None = None
    # Track elapsed-since-last-frame in units of poll_interval so the keep-alive cadence holds without
    # a wall-clock read each loop (and stays deterministic under an injected fake sleep).
    silent_for = 0.0
    primed = False
    iterations = 0

    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        version = version_reader()
        tick = tick_reader()
        changed = (not primed) or version != last_version or tick != last_tick
        if changed:
            last_version, last_tick = version, tick
            primed = True
            silent_for = 0.0
            yield _sse_event("change", {"version": version, "tick": tick})
        else:
            silent_for += poll_interval
            if silent_for >= keepalive_interval:
                silent_for = 0.0
                yield _sse_comment("keepalive")
        await do_sleep(poll_interval)
