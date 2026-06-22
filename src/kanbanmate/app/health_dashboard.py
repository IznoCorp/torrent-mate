"""Per-project health dashboard data (bosun §7.1).

Computes the authed dashboard payload: one row per registered project plus global flags. Reads
heartbeat files + a cheap probe; never the public ``/api/health`` data. Imperative shell (fs reads).

Distinct from :mod:`kanbanmate.app.health_reporter` (which maintains the per-card GitHub Health
**field** on the board — a board-level observability concern). This module computes project-level
liveness fresh from the per-project heartbeat markers the daemon writes after every tick.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from kanbanmate.core.heartbeat import parse_heartbeat
from kanbanmate.core.registry_resolve import safe_project_id

logger = logging.getLogger(__name__)

# A heartbeat older than this is considered stale (daemon down or hung).
_HEARTBEAT_FRESH_S: float = 120.0


def _read_registry(root: Path) -> dict[str, dict[str, Any]]:
    """Read ``<root>/projects.json`` as a ``{project_id: entry-dict}`` mapping, fail-soft.

    The registry FILE reader lives in :mod:`kanbanmate.cli.init`, but ``cli`` is an upper layer
    the ``app`` composition root must not import (hexagonal downward-only rule, DESIGN §3.2). The
    dashboard needs only a couple of fields per entry (``repo``, ``token_ref``), so it reads the
    JSON directly here as plain dicts rather than reaching up into ``cli`` for the typed loader.

    Args:
        root: The kanban runtime root holding ``projects.json``.

    Returns:
        The ``{project_id: entry-dict}`` mapping, or ``{}`` when the file is absent or unreadable.
    """
    try:
        raw = json.loads((root / "projects.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def build_health(root: Path) -> dict[str, Any]:
    """Return per-project rows + global flags for the authed health dashboard (DESIGN §7.1).

    Args:
        root: The kanban runtime root (holds ``projects.json``, ``PAUSE`` sentinel, etc.).

    Returns:
        A dict with keys ``projects`` (list of per-project row dicts), ``pause_active`` (bool),
        ``session_secret_pinned`` (bool), and ``agents_waiting`` (int). Each row carries
        ``project_id``, ``repo``, ``daemon_alive``, ``heartbeat_age_s``, ``github_api_ok``,
        ``board_ok``, and ``token_present``. Probe failures degrade a per-row flag to ``False``
        rather than raising — the dashboard must always render.
    """
    registry = _read_registry(root)
    now = time.time()
    projects = [_build_row(root, pid, entry, now) for pid, entry in registry.items()]
    pause_active = (root / "PAUSE").exists()
    session_secret_pinned = bool(os.environ.get("KANBAN_MATE_UI_SESSION_SECRET"))
    agents_waiting = _count_waiting(root, registry)
    return {
        "projects": projects,
        "pause_active": pause_active,
        "session_secret_pinned": session_secret_pinned,
        "agents_waiting": agents_waiting,
    }


def _build_row(root: Path, pid: str, entry: Any, now: float) -> dict[str, Any]:
    """Build one per-project health row, fail-soft on every I/O read.

    Args:
        root: The runtime root.
        pid: The Project v2 node id (registry key).
        entry: The raw ``projects.json`` entry dict for this project.
        now: The current wall-clock timestamp (one frozen ``time.time()`` for the whole dashboard).

    Returns:
        A dict with the per-project health fields. A genuinely-down project reports its flags
        ``False`` with ``heartbeat_age_s = -1.0`` and ``read_error = False``. A read/parse FAILURE
        (corrupt heartbeat, FS hiccup) is signalled distinctly: ``read_error = True`` and
        ``heartbeat_age_s = None`` (unknown, not "measured down"), plus a logged warning — so a
        transient parse error never silently paints a healthy project red (bosun review-c2). The
        dashboard never raises: a single broken file still renders.
    """
    safe = safe_project_id(pid)
    hb_path = root / "projects" / "heartbeats" / f"{safe}.heartbeat"

    # ---- heartbeat-derived fields ----
    daemon_alive = False
    heartbeat_age_s: float | None = -1.0
    github_api_ok = False
    board_ok = False
    read_error = False
    try:
        if hb_path.exists():
            hb = parse_heartbeat(hb_path.read_text(encoding="utf-8"))
            age = now - hb.ts
            heartbeat_age_s = max(0.0, age)
            daemon_alive = age < _HEARTBEAT_FRESH_S
            # last_tick_ok signals the tick completed without raising — a proxy for
            # GitHub API reachability. consecutive_failures == 0 means no recent auth
            # or network failures (the circuit-breaker is cold).
            github_api_ok = hb.last_tick_ok and hb.consecutive_failures == 0
            board_ok = hb.last_tick_ok
    except (OSError, ValueError) as exc:
        # Narrow: OSError = FS read hiccup; ValueError = parse_heartbeat on a truncated/garbage
        # marker (e.g. a read racing the daemon's non-atomic write). Distinguish "unknown due to
        # read error" from "measured down" so a transient flake never masquerades as an outage and
        # triggers an unnecessary restart/redeploy. heartbeat_age_s = None signals UNKNOWN.
        read_error = True
        heartbeat_age_s = None
        logger.warning("health-dashboard heartbeat read failed for %s: %s", pid, exc, exc_info=True)

    # ---- token presence ----
    token_present = False
    try:
        token_ref = entry.get("token_ref", "") or ""
        token_path = root / "token" if not token_ref else root / "tokens" / token_ref
        token_present = token_path.exists()
    except (OSError, AttributeError) as exc:
        # OSError = FS hiccup; AttributeError = a malformed registry entry (not a dict). Leave
        # token_present False but log so a recurring failure is visible rather than silently red.
        logger.warning("health-dashboard token read failed for %s: %s", pid, exc, exc_info=True)

    return {
        "project_id": pid,
        "repo": entry.get("repo", "") if isinstance(entry, dict) else "",
        "daemon_alive": daemon_alive,
        "heartbeat_age_s": heartbeat_age_s,
        "github_api_ok": github_api_ok,
        "board_ok": board_ok,
        "token_present": token_present,
        "read_error": read_error,
    }


def _count_waiting(root: Path, registry: dict[str, Any]) -> int:
    """Count WAITING tickets across all projects, fail-soft.

    Scans ``<root>/projects/<safe(pid)>/state/*.json`` for each registered project.
    A corrupt or unreadable file is silently skipped — a single broken state file never
    skews the count or crashes the dashboard render.

    Args:
        root: The runtime root.
        registry: The ``{project_id: entry-dict}`` mapping from ``_read_registry`` (plain dicts,
            not typed ``ProjectEntry`` objects — ``app`` must not import the ``cli`` loader).

    Returns:
        The total number of tracked tickets whose persisted ``status`` is ``"waiting"``.
    """
    total = 0
    for pid in registry:
        try:
            safe = safe_project_id(pid)
            state_dir = root / "projects" / safe / "state"
            if not state_dir.is_dir():
                continue
            for sf in state_dir.glob("*.json"):
                try:
                    data = json.loads(sf.read_text(encoding="utf-8"))
                    if data.get("status") == "waiting":
                        total += 1
                except Exception:
                    pass
        except Exception:
            pass
    return total
