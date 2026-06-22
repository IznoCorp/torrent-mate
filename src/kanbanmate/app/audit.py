"""Shared audit sink (bosun §13) — one audit story across #47 and bosun.

Generalises the line shape ``agent_terminal._audit`` writes (``http/agent_terminal.py:158``):
``<ISO-8601Z> audit: operator <login> <action>: <summary>`` appended to ``<root>/control/audit.log``.
Fail-soft — a file error must never interrupt the privileged op.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def append_audit(root: Path, login: str, action: str, summary: str) -> None:
    """Append one audit line to ``<root>/control/audit.log`` (fail-soft, DESIGN §13).

    Args:
        root: The kanban runtime root.
        login: The authenticated operator login.
        action: The action verb (e.g. ``pause_on``, ``daemon_restart``).
        summary: A short, sanitised description of the args.
    """
    try:
        log_path = root / "control" / "audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ts} audit: operator {login} {action}: {summary}\n")
    except Exception as exc:
        # Fail-soft: audit file errors must never interrupt a privileged op. But leave a breadcrumb —
        # PAUSE-toggle and project-delete are recorded ONLY here (no job record), so a silent drop on
        # those would erase the only trace of a privileged act exactly when it matters (disk full,
        # control/ not writable, perms regression).
        logger.warning("audit append failed for %s/%s: %s", action, summary, exc, exc_info=True)
