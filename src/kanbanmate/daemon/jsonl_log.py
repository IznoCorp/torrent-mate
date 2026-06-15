"""A tiny logging Handler that writes structured JSONL to ``<root>/log/daemon.jsonl``.

This is the writer half of the daemon structured-log pair; the reader is
:mod:`kanbanmate.cli.logs`. The handler is installed by :func:`kanbanmate.daemon.loop.run_loop`
and writes one JSON object per line. Write failures are best-effort — a log-write error
must not crash the daemon (the worst case is a gap in the JSONL, not a daemon crash).

Layering: ``daemon`` is an entrypoint (DESIGN §3.2); this module owns the writer-side path
constants and the handler class. It imports nothing beyond the stdlib.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

# The structured-log subdirectory under the kanban root (DESIGN §5).
LOG_DIRNAME = "log"

# The daemon's structured JSONL log filename (DESIGN §5).
DAEMON_LOG_FILENAME = "daemon.jsonl"

# Size-based rotation threshold for the JSONL log (#8). When the file grows past this many bytes it
# is rotated to ``<file>.1`` (single generation, overwriting any prior) and a fresh file is started,
# so the daemon's log cannot grow unbounded on a long-lived host. ~10 MB keeps a useful tail while
# bounding disk use.
MAX_LOG_BYTES = 10 * 1024 * 1024


class JSONLHandler(logging.Handler):
    """A :class:`logging.Handler` that appends structured JSONL records.

    Each ``emit`` writes one JSON object (compact, key-sorted) to the configured file,
    creating the parent directory on first use.  Fields written per record:

    * ``ts`` — ISO-8601 UTC timestamp of the log event.
    * ``level`` — the log-level name (``INFO``, ``ERROR``, …).
    * ``logger`` — the logger name (e.g. ``kanbanmate.daemon.loop``).
    * ``msg`` — the formatted log message.
    * ``issue`` — only when the log record carries an ``issue`` extra attribute
      (set via ``logger.info(..., extra={'issue': 42})``), so ``kanban logs <n>``
      can filter by ticket.

    Write failures (missing directory, permission denied, …) are handled via
    :meth:`logging.Handler.handleError` — they are printed to stderr but never raised,
    keeping the daemon tolerant of a full disk or missing ``log/`` directory.
    """

    def __init__(self, log_path: Path) -> None:
        """Initialise the handler with the target JSONL file path.

        Args:
            log_path: The full path to the JSONL log file (e.g.
                ``<kanban_root>/log/daemon.jsonl``). The parent directory is
                created on first write.
        """
        super().__init__()
        self._log_path = log_path

    def emit(self, record: logging.LogRecord) -> None:
        """Format *record* as a JSON object and append it to the log file.

        Adds an ``exc`` field carrying the formatted traceback whenever the record was logged with
        ``exc_info`` (``logger.exception(...)`` or ``logger.error(..., exc_info=True)``), so
        ``kanban logs`` can finally show WHY a tick failed — the live log was full of bare "tick
        raised; continuing" lines with the cause only in PM2 stdout (#8). The file is size-rotated
        at :data:`MAX_LOG_BYTES` so it cannot grow unbounded.

        Args:
            record: The log record to emit.
        """
        try:
            data: dict[str, object] = {
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
            issue = getattr(record, "issue", None)
            if issue is not None:
                data["issue"] = issue
            # Surface the traceback so ``kanban logs`` shows the CAUSE of a failure (#8). The base
            # ``logging.Handler`` has no traceback formatter, so use the stdlib ``traceback`` module
            # directly to render ``exc_info`` (a ``(type, value, tb)`` triple) to a string.
            if record.exc_info and record.exc_info[0] is not None:
                data["exc"] = "".join(traceback.format_exception(*record.exc_info)).rstrip()
            line = json.dumps(data, sort_keys=True)
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            self.handleError(record)

    def _rotate_if_needed(self) -> None:
        """Rotate the log to ``<file>.1`` when it exceeds :data:`MAX_LOG_BYTES` (#8).

        Single-generation rotation: the current file is renamed to ``<file>.1`` (replacing any
        prior ``.1``) once it grows past the threshold, and the next write starts a fresh file. This
        bounds disk use on a long-lived daemon while keeping the most recent ~10 MB readable. A
        rotation failure is swallowed by the caller's ``except`` (logging must never crash the
        daemon); the worst case is the file growing slightly past the threshold.
        """
        try:
            if self._log_path.exists() and self._log_path.stat().st_size >= MAX_LOG_BYTES:
                # ``replace`` is atomic and overwrites an existing ``.1`` so only one rolled
                # generation is kept (the older one is discarded — bounded disk use).
                self._log_path.replace(self._log_path.with_suffix(self._log_path.suffix + ".1"))
        except OSError:
            # A rotation hiccup (race, perms) must not block the log write — let the append proceed.
            pass
