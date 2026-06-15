"""``kanban logs [issue]`` — read the structured JSONL logs (DESIGN §5, ported from PoC ``plan_logs.py``).

The daemon writes structured **JSONL** to ``<root>/log/daemon.jsonl`` (one JSON object per line) via
:class:`~kanbanmate.daemon.jsonl_log.JSONLHandler` (installed in
:func:`~kanbanmate.daemon.loop.run_loop`). ``kanban logs`` reads that file and prints the most recent
lines; when an ``issue`` is given it keeps only entries whose ``issue`` field matches and surfaces the
path to the per-ticket ``<root>/log/ticket-<n>.log`` (written by the agent-side session, out of scope
for the daemon JSONL).

The reader is defensive: a malformed JSONL line is skipped rather than aborting the whole read (the
log is operator-facing observability, never a parser the daemon depends on). Everything is keyed off
a configurable ``root`` so tests point at a ``tmp_path`` and never read the real ``~/.kanban``.

**Divergence from the PoC (#11 KEEP+DOC).** The PoC ``cli/runners.py:113-125`` printed the FULL
per-ticket session-log TEXT inline plus a ``dispatch.jsonl`` transition history
(``<from> -> <to> (<uuid>)``). NEW keeps the daemon-JSONL model on two deliberate, pivot-anchored
grounds:

* ``dispatch.jsonl`` is REPLACED by ``daemon.jsonl``. ``dispatch.jsonl`` was a webhook-era artifact —
  one entry per dispatched webhook — and the polling model has NO per-dispatch event (the daemon
  reconciles the board by diff, it is never "dispatched to"), so there is nothing to log there. The
  structured ``daemon.jsonl`` (one JSON object per tick event) is its analogue, not a regression.
* The per-ticket session-log BODY is surfaced by PATH, not dumped. ``kanban logs <issue>`` resolves
  ``<root>/log/ticket-<n>.log`` and reports its path/presence; the operator ``cat``s / ``tail``s it
  themselves. This is intentional: a live agent's session log grows unbounded, and inlining it would
  flood the command output — so the path is the contract, the body is the operator's to read.

Everything is keyed off a configurable ``root`` so tests point at a ``tmp_path`` and never read the
real ``~/.kanban``.

Layering: ``cli`` is an entrypoint (DESIGN §3.2); this module is pure filesystem + JSON parsing and
imports nothing from the lower layers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# The structured-log subdirectory under the kanban root (DESIGN §5).
LOG_DIRNAME = "log"

# The daemon's structured JSONL log filename (DESIGN §5).
DAEMON_LOG_FILENAME = "daemon.jsonl"

# The per-ticket plain-log filename template (DESIGN §5).
TICKET_LOG_TEMPLATE = "ticket-{issue}.log"

# How many trailing log lines ``kanban logs`` shows by default — tail the last N lines
# (the file grows unbounded; size rotation is planned, DESIGN §5).
DEFAULT_TAIL = 50


@dataclass(frozen=True)
class LogView:
    """The resolved result of one ``kanban logs`` read.

    Attributes:
        entries: The parsed JSONL records (most recent last), already filtered by issue and
            truncated to the requested tail length.
        daemon_log: The path to the daemon JSONL log that was read.
        daemon_log_exists: ``True`` iff the daemon JSONL log file is present.
        ticket_log: The per-ticket log path, or ``None`` when no issue filter was given.
        ticket_log_exists: ``True`` iff a per-ticket log path was resolved and it exists.
    """

    entries: list[dict[str, object]] = field(default_factory=list)
    daemon_log: Path | None = None
    daemon_log_exists: bool = False
    ticket_log: Path | None = None
    ticket_log_exists: bool = False


def _log_dir(root: Path | str) -> Path:
    """Return the ``<root>/log`` directory holding the structured logs.

    Args:
        root: The kanban runtime root.

    Returns:
        The ``log`` subdirectory path under ``root``.
    """
    return Path(root) / LOG_DIRNAME


def _read_jsonl(path: Path, *, issue: int | None) -> list[dict[str, object]]:
    """Parse a JSONL file into records, skipping malformed lines and filtering by issue.

    Args:
        path: The JSONL file to read.
        issue: When not ``None``, keep only records whose ``issue`` field equals it.

    Returns:
        The parsed records in file order; an empty list when the file is absent.
    """
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            # A torn/partial line (mid-rotation, crash) must not abort the read — skip it.
            continue
        if not isinstance(row, dict):
            continue
        if issue is not None and row.get("issue") != issue:
            continue
        records.append(row)
    return records


def resolve_logs(
    root: Path | str,
    *,
    issue: int | None = None,
    tail: int = DEFAULT_TAIL,
) -> LogView:
    """Resolve the daemon JSONL entries (and per-ticket log path) for ``kanban logs``.

    Reads ``<root>/log/daemon.jsonl``, optionally keeping only entries for ``issue``, and returns at
    most ``tail`` of the most recent entries. When an issue is given, the per-ticket
    ``<root>/log/ticket-<n>.log`` path is resolved too so the caller can surface it.

    Args:
        root: The kanban runtime root holding the ``log`` directory. Configurable for tests.
        issue: When given, filter to that issue and resolve its per-ticket log path.
        tail: The maximum number of trailing entries to return (most recent).

    Returns:
        A :class:`LogView` with the filtered, tail-truncated entries and the log paths.
    """
    log_dir = _log_dir(root)
    daemon_log = log_dir / DAEMON_LOG_FILENAME
    entries = _read_jsonl(daemon_log, issue=issue)
    # Keep only the most recent ``tail`` entries (the file grows unbounded; tail the last N).
    tail_entries = entries[-tail:] if tail > 0 else entries

    ticket_log: Path | None = None
    ticket_log_exists = False
    if issue is not None:
        ticket_log = log_dir / TICKET_LOG_TEMPLATE.format(issue=issue)
        ticket_log_exists = ticket_log.exists()

    return LogView(
        entries=tail_entries,
        daemon_log=daemon_log,
        daemon_log_exists=daemon_log.exists(),
        ticket_log=ticket_log,
        ticket_log_exists=ticket_log_exists,
    )


def render_logs(view: LogView) -> str:
    """Render a :class:`LogView` as printable text (one compact JSON line per entry).

    Args:
        view: The resolved log view to render.

    Returns:
        The rendered log output as a single multi-line string (no trailing newline).
    """
    lines: list[str] = []
    if view.daemon_log is not None and not view.daemon_log_exists:
        lines.append(f"(no daemon log at {view.daemon_log})")
    if view.ticket_log is not None:
        presence = "present" if view.ticket_log_exists else "absent"
        lines.append(f"ticket log: {view.ticket_log} ({presence})")
    if not view.entries:
        lines.append("(no log entries)")
        return "\n".join(lines)
    for entry in view.entries:
        # An ``exc`` field carries a multi-line traceback (#8); rendering it INSIDE the compact JSON
        # line escapes the newlines into an unreadable ``\n`` soup. Pull it out, render the entry
        # line without it (still compact + greppable), then print the traceback on its own indented
        # lines below so the operator sees WHY a tick failed.
        exc = entry.get("exc")
        if isinstance(exc, str):
            without_exc = {k: v for k, v in entry.items() if k != "exc"}
            lines.append(json.dumps(without_exc, sort_keys=True))
            for exc_line in exc.splitlines():
                lines.append(f"    {exc_line}")
        else:
            # Compact, key-sorted JSON keeps each entry on one stable, greppable line.
            lines.append(json.dumps(entry, sort_keys=True))
    return "\n".join(lines)


def logs(root: Path | str, *, issue: int | None = None, tail: int = DEFAULT_TAIL) -> str:
    """Resolve and render the logs (the thin shell the Typer command calls).

    Args:
        root: The kanban runtime root holding the ``log`` directory.
        issue: When given, filter to that issue and surface its per-ticket log path.
        tail: The maximum number of trailing entries to show.

    Returns:
        The rendered log output, ready to print.
    """
    return render_logs(resolve_logs(root, issue=issue, tail=tail))
