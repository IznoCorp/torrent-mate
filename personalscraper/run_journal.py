"""Universal run journal for non-web pipeline invocations.

Closes the 2026-07-08 "silent run" gap: pipeline invocations that do not go
through the web UI — direct CLI step commands (``dispatch``, ``process``, …)
and daemon-spawned runs — left no ``pipeline_run`` row and no ``output_tail``,
so the TorrentMate run journal showed a running pipeline with no log at all.

Two building blocks:

- :class:`LogTailHandler` — a ring-buffer ``logging.Handler`` capturing the
  last N bytes of formatted log output (structlog routes through the stdlib
  root logger, so attaching here captures exactly what the console shows).
- :func:`cli_step_journal` — a fail-soft context manager wrapping ONE direct
  CLI step command: inserts a ``pipeline_run`` row (``trigger='cli'``,
  ``kind='pipeline'``, ``command=<step>``), captures the log tail, and
  finalizes the row with the outcome on exit. A journaling failure must never
  break the wrapped command.

The full ``personalscraper run`` path (web, safety_net, and manual CLI
triggers alike) keeps its existing wiring inside ``Pipeline.run`` and gains
the tail through the ``output_tail_provider`` parameter instead.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import click
import typer

from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("run_journal")

#: Byte cap for the captured log tail — matches the maintenance runner's
#: 64 KiB ``output_tail`` contract (migration 012).
DEFAULT_TAIL_BYTES = 65536


class LogTailHandler(logging.Handler):
    """Ring-buffer logging handler keeping the last ``max_bytes`` of output.

    Formatted lines are appended to a deque; oldest lines are dropped first
    once the byte budget is exceeded, so the buffer always holds the most
    recent output (what an operator wants to see after a failure).

    Args:
        max_bytes: Byte cap for the joined tail. Defaults to
            :data:`DEFAULT_TAIL_BYTES` (64 KiB).
    """

    def __init__(self, max_bytes: int = DEFAULT_TAIL_BYTES) -> None:
        """Initialise an empty ring buffer.

        Args:
            max_bytes: Byte cap for the joined tail.
        """
        super().__init__()
        self._max_bytes = max_bytes
        self._lines: deque[str] = deque()
        self._size = 0

    def emit(self, record: logging.LogRecord) -> None:
        """Append the formatted record, trimming oldest lines past the cap.

        Args:
            record: The log record being emitted.
        """
        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001 — a formatting error must never break the command
            return
        self._lines.append(line)
        self._size += len(line.encode("utf-8", errors="replace")) + 1
        while self._size > self._max_bytes and self._lines:
            dropped = self._lines.popleft()
            self._size -= len(dropped.encode("utf-8", errors="replace")) + 1

    def tail(self) -> str | None:
        """Return the captured tail, or ``None`` when nothing was logged.

        Returns:
            Newline-joined captured lines, or ``None`` for an empty buffer
            (stored as NULL, matching rows that genuinely have no output).
        """
        if not self._lines:
            return None
        return "\n".join(self._lines)

    def install(self) -> None:
        """Attach to the root logger, mirroring its first handler's formatter.

        Reusing the console handler's formatter makes the captured tail
        byte-identical to what the operator saw on stdout.
        """
        # ``logging.root`` (public module attribute) — the convention checker
        # forbids ``logging.getLogger()`` emission-side calls; this is a
        # handler attachment, not a logger acquisition.
        root = logging.root
        if root.handlers:
            self.setFormatter(root.handlers[0].formatter)
        root.addHandler(self)

    def uninstall(self) -> None:
        """Detach from the root logger (idempotent)."""
        logging.root.removeHandler(self)


@contextmanager
def cli_step_journal(config: Config, *, command: str, dry_run: bool) -> Iterator[str | None]:
    """Journal one direct CLI pipeline step into ``pipeline_run``.

    Wraps the body of a step command (``ingest``, ``sort``, ``scrape``,
    ``verify``, ``enforce``, ``dispatch``, ``clean``, ``cleanup``,
    ``process``) so the run is visible in the TorrentMate run journal exactly
    like a web-launched run:

    1. Insert a ``pipeline_run`` row (``trigger='cli'``, ``kind='pipeline'``,
       ``command=<step>``, ``outcome='running'``).
    2. Capture the log tail via :class:`LogTailHandler` for the duration.
    3. Finalize the row on exit — ``success`` on a clean return (or a
       zero-code ``typer.Exit``), ``killed`` on ``KeyboardInterrupt``,
       ``error`` otherwise — with the captured ``output_tail``.

    Every journaling step is fail-soft: a missing/unwritable DB or a logging
    problem must never break the wrapped command (same contract as
    :class:`~personalscraper.pipeline_history.PipelineRunWriter`).

    Args:
        config: Loaded configuration (``config.indexer.db_path`` locates the
            ``pipeline_run`` table).
        command: Step command name recorded in the row (e.g. ``'dispatch'``).
        dry_run: Whether the wrapped invocation is a dry run.

    Yields:
        The ``run_uid`` of the journal row, or ``None`` when journaling could
        not start.
    """
    writer: PipelineRunWriter | None = None
    run_uid = uuid.uuid4().hex
    try:
        db_path = config.indexer.db_path
        # No journal without an existing indexer DB (fresh clone, tests):
        # silently skipping beats fail-soft warnings whose chained tracebacks
        # pollute the CLI output of the wrapped command.
        if db_path is not None and db_path.exists():
            writer = PipelineRunWriter(db_path)
            writer.insert(
                run_uid,
                trigger="cli",
                dry_run=dry_run,
                pid=os.getpid(),
                kind="pipeline",
                command=command,
            )
    except Exception:  # noqa: BLE001 — journaling must never break the command
        log.warning("run_journal.init_failed", command=command, exc_info=True)
        writer = None

    tail_handler = LogTailHandler()
    try:
        tail_handler.install()
    except Exception:  # noqa: BLE001 — same fail-soft contract
        log.warning("run_journal.tail_install_failed", command=command, exc_info=True)

    outcome = "success"
    error_msg: str | None = None
    try:
        yield run_uid if writer is not None else None
    except (typer.Exit, click.exceptions.Exit) as exc:
        # Both carry ``exit_code``; code 0 is a normal CLI termination.
        if getattr(exc, "exit_code", 1) not in (0, None):
            outcome = "error"
            error_msg = f"exit code {exc.exit_code}"
        raise
    except KeyboardInterrupt:
        outcome = "killed"
        error_msg = "KeyboardInterrupt"
        raise
    except BaseException as exc:
        outcome = "error"
        error_msg = str(exc) or type(exc).__name__
        raise
    finally:
        try:
            tail_handler.uninstall()
        except Exception:  # noqa: BLE001 — same fail-soft contract
            log.warning("run_journal.tail_uninstall_failed", command=command, exc_info=True)
        if writer is not None:
            writer.finalize(run_uid, outcome, error=error_msg, output_tail=tail_handler.tail())
