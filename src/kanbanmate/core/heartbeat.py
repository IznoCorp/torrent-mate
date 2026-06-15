"""Daemon heartbeat marker serialization (DESIGN §5).

The daemon writes a ``daemon.heartbeat`` marker after every tick so ``kanban doctor``
can tell whether the background loop is alive AND succeeding. Historically the marker
was a bare POSIX-epoch float string ("liveness only"); a token that 401-looped left the
marker green forever (the write happens after the swallowed tick exception), so the
operator's worst incident class — hours of silent failure — was invisible.

This module upgrades the marker to a structured JSON record carrying tick HEALTH, not
just liveness:

* ``ts`` — the POSIX timestamp the marker was written (the freshness signal).
* ``last_tick_ok`` — whether the most recent tick completed without raising.
* ``consecutive_failures`` — how many ticks in a row have raised; doctor FAILs past a
  small threshold so a persistently-failing daemon stops looking healthy.

**Backward-compat parsing is mandatory.** A marker written by an OLD daemon mid-upgrade
is a plain epoch string; :func:`parse_heartbeat` falls back to ``float(text)`` and
reports ``last_tick_ok=True`` / ``consecutive_failures=0`` for it, so doctor never
false-FAILs across a daemon restart that straddles the format change.

Layering: ``core`` is pure (DESIGN §3.2) — this module imports only the stdlib and is
imported by BOTH the daemon writer (:mod:`kanbanmate.daemon.loop`) and the doctor reader
(:mod:`kanbanmate.cli.doctor`), so there is exactly one serialization surface.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# Doctor FAILs the daemon-heartbeat check once this many consecutive ticks have raised.
# Three keeps a single transient blip from flipping doctor red while still surfacing a
# wedged daemon promptly (~30 s at the fixed 10 s cadence).
DEFAULT_FAILURE_THRESHOLD = 3


@dataclass(frozen=True)
class Heartbeat:
    """A parsed daemon-heartbeat marker (DESIGN §5).

    Attributes:
        ts: The POSIX timestamp (seconds) the marker was written — the freshness signal.
        last_tick_ok: Whether the most recent tick completed without raising. A legacy
            plain-epoch marker (old daemon mid-upgrade) parses to ``True``.
        consecutive_failures: How many ticks in a row have raised. A legacy marker parses
            to ``0`` so an upgrade straddle never false-FAILs doctor.
    """

    ts: float
    last_tick_ok: bool = True
    consecutive_failures: int = 0


def render_heartbeat(heartbeat: Heartbeat) -> str:
    """Serialize a :class:`Heartbeat` to the compact JSON written to the marker file.

    Args:
        heartbeat: The heartbeat record to render.

    Returns:
        A single-line, key-sorted JSON object string (no trailing newline).
    """
    return json.dumps(
        {
            "ts": heartbeat.ts,
            "last_tick_ok": heartbeat.last_tick_ok,
            "consecutive_failures": heartbeat.consecutive_failures,
        },
        sort_keys=True,
    )


def parse_heartbeat(text: str) -> Heartbeat:
    """Parse a daemon-heartbeat marker, tolerating BOTH the JSON and legacy formats.

    Two on-disk formats are accepted (backward-compat is mandatory — DESIGN §5):

    1. **JSON** (current) — ``{"ts": …, "last_tick_ok": …, "consecutive_failures": …}``.
    2. **Plain epoch** (legacy / old daemon mid-upgrade) — a bare float string. It is read
       as a fresh, healthy marker (``last_tick_ok=True``, ``consecutive_failures=0``) so a
       restart straddling the format change never false-FAILs doctor.

    A malformed/empty marker raises :class:`ValueError` so the caller can degrade to a
    "cannot parse" note rather than silently treating garbage as healthy.

    Args:
        text: The raw marker-file contents (whitespace is stripped).

    Returns:
        The parsed :class:`Heartbeat`.

    Raises:
        ValueError: When ``text`` is neither valid JSON nor a parseable float.
    """
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty heartbeat marker")
    # Try the structured JSON form first; fall back to the legacy plain-epoch float.
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        data = None
    if isinstance(data, dict):
        # A JSON record: read each field defensively (an old/partial record may omit
        # the health fields — treat a missing field as the healthy default).
        return Heartbeat(
            ts=float(data["ts"]),
            last_tick_ok=bool(data.get("last_tick_ok", True)),
            consecutive_failures=int(data.get("consecutive_failures", 0)),
        )
    # Legacy plain-epoch marker (or JSON that decoded to a bare number): read it as a
    # fresh healthy heartbeat. ``float(stripped)`` raises ValueError on real garbage.
    return Heartbeat(ts=float(stripped), last_tick_ok=True, consecutive_failures=0)
