"""Run-history writer for the ``pipeline_run`` table (indexer migration 011).

Writes a durable, queryable record of every pipeline execution — one row per
run with per-step timing data stored as a JSON array in ``steps_json``.

The writer is **fail-soft**: every method wraps its DB work in a try/except,
logs a warning on failure, and never raises.  A history-write error must
never abort the pipeline.

Each method opens a short-lived ``sqlite3`` connection (open → write →
commit → close), matching the indexer's connection conventions (WAL pragmas
applied via :func:`personalscraper.core.sqlite._pragmas.apply_pragmas`).

Usage inside ``Pipeline.run()``::

    from personalscraper.pipeline_history import PipelineRunWriter

    writer = PipelineRunWriter(db_path)
    writer.insert(run_uid, trigger="web", dry_run=False, pid=os.getpid())
    # ... after each step ...
    writer.update_step(run_uid, "ingest", started_at, ended_at, "success")
    # ... at end ...
    writer.finalize(run_uid, "success")

Maintenance actions (S3 maint-dash) supply ``kind``, ``command``,
``options_json``, and ``output_tail`` — all defaulted so existing S2 callers
are unaffected::

    writer = PipelineRunWriter(db_path)
    writer.insert(run_uid, trigger="web", dry_run=False, pid=os.getpid(),
                  kind="maintenance", command="library-clean",
                  options_json='{"only":"actors"}')
    # ...
    writer.finalize(run_uid, "success", output_tail="...[last 64 KiB]...")
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger

log = get_logger("pipeline_history")


class PipelineRunWriter:
    """Durable run-history writer for the ``pipeline_run`` table.

    Opens a short-lived ``sqlite3`` connection for each method call so that
    a DB failure never affects the pipeline's main loop.  All methods are
    fail-soft — they catch and log exceptions without re-raising.

    Args:
        db_path: Path to the indexer SQLite database (``library.db``).
    """

    def __init__(self, db_path: Path) -> None:
        """Store the DB path.

        Args:
            db_path: Path to the indexer SQLite database.
        """
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def insert(
        self,
        run_uid: str,
        trigger: str,
        dry_run: bool,
        pid: int,
        kind: str = "pipeline",
        command: str | None = None,
        options_json: str | None = None,
        if_absent: bool = False,
    ) -> None:
        """Insert a new row into ``pipeline_run`` with ``outcome="running"``.

        The *kind*, *command*, and *options_json* parameters are additive
        (migration 012) and defaulted so existing S2 callers are unchanged.

        Args:
            run_uid: Unique run identifier (UUID string).
            trigger: How the run was triggered (``'cli'``, ``'web'``, ``'cron'``).
            dry_run: ``True`` if this is a dry run.
            pid: OS process ID of the pipeline process.
            kind: Run kind discriminator (``'pipeline'`` or ``'maintenance'``).
            command: CLI command name for maintenance actions (``None`` for
                pipeline runs).
            options_json: Canonical JSON of the action options (``None`` for
                pipeline runs).
            if_absent: When ``True`` use ``INSERT OR IGNORE`` so a row already
                present (e.g. reserved synchronously by the maintenance POST
                handler before the runner started) is not duplicated and the
                ``run_uid`` UNIQUE constraint never raises. S2 callers keep the
                default (plain ``INSERT``).
        """
        started_at = time.time()
        dry_run_int = 1 if dry_run else 0
        verb = "INSERT OR IGNORE INTO" if if_absent else "INSERT INTO"
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            conn.execute(
                f"{verb} pipeline_run "
                "(run_uid, trigger, dry_run, started_at, outcome, steps_json, pid, "
                "kind, command, options_json) "
                "VALUES (?, ?, ?, ?, 'running', '[]', ?, ?, ?, ?)",
                (run_uid, trigger, dry_run_int, started_at, pid, kind, command, options_json),
            )
            conn.commit()
        except Exception:
            log.warning(
                "pipeline_history.insert_failed",
                run_uid=run_uid,
                trigger=trigger,
                dry_run=dry_run,
                pid=pid,
                kind=kind,
                command=command,
                exc_info=True,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def update_pid(self, run_uid: str, pid: int) -> None:
        """Set the ``pid`` column for an existing run row (idempotent).

        Used by the maintenance flow to claim ownership of a row: the POST
        handler reserves the row with a placeholder pid, then updates it to the
        spawned runner's pid; the runner also refreshes it to its own pid at
        startup. When the row is absent the ``UPDATE`` affects zero rows, which
        is harmless. Fail-soft — never raises.

        Args:
            run_uid: Unique run identifier.
            pid: OS process ID to store in the row.
        """
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            conn.execute(
                "UPDATE pipeline_run SET pid = ? WHERE run_uid = ?",
                (pid, run_uid),
            )
            conn.commit()
        except Exception:
            log.warning(
                "pipeline_history.update_pid_failed",
                run_uid=run_uid,
                pid=pid,
                exc_info=True,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def update_step(
        self,
        run_uid: str,
        step_name: str,
        started_at: float,
        ended_at: float,
        status: str,
    ) -> None:
        """Append a step timing record to the row's ``steps_json`` array.

        Reads the current ``steps_json`` value for the given ``run_uid``,
        appends a new entry ``{name, started_at, ended_at, status}``, and
        writes the updated array back.

        Args:
            run_uid: Unique run identifier.
            step_name: Name of the pipeline step (e.g. ``'ingest'``).
            started_at: Monotonic timestamp when the step started.
            ended_at: Monotonic timestamp when the step completed.
            status: Step outcome (``'success'`` or ``'error'``).
        """
        entry = {
            "name": step_name,
            "started_at": started_at,
            "ended_at": ended_at,
            "status": status,
        }
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            row = conn.execute(
                "SELECT steps_json FROM pipeline_run WHERE run_uid = ?",
                (run_uid,),
            ).fetchone()
            if row is None:
                log.warning(
                    "pipeline_history.update_step_missing_run",
                    run_uid=run_uid,
                    step_name=step_name,
                )
                return
            current_raw = row[0]
            try:
                steps = json.loads(current_raw) if current_raw else []
            except (json.JSONDecodeError, TypeError):
                log.warning(
                    "pipeline_history.update_step_bad_json",
                    run_uid=run_uid,
                    step_name=step_name,
                )
                steps = []
            steps.append(entry)
            conn.execute(
                "UPDATE pipeline_run SET steps_json = ? WHERE run_uid = ?",
                (json.dumps(steps), run_uid),
            )
            conn.commit()
        except Exception:
            log.warning(
                "pipeline_history.update_step_failed",
                run_uid=run_uid,
                step_name=step_name,
                exc_info=True,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def finalize(
        self,
        run_uid: str,
        outcome: str,
        error: str | None = None,
        output_tail: str | None = None,
    ) -> None:
        """Finalize a pipeline run by setting ``ended_at`` and ``outcome``.

        The *output_tail* parameter is additive (migration 012) and stores the
        last 64 KiB of command output for maintenance actions.

        Args:
            run_uid: Unique run identifier.
            outcome: Final outcome (``'success'``, ``'error'``, or ``'killed'``).
            error: Optional error message when ``outcome`` is ``'error'``.
            output_tail: Optional tail of the command output (last 64 KiB) for
                maintenance actions.
        """
        ended_at = time.time()
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            conn.execute(
                "UPDATE pipeline_run SET ended_at = ?, outcome = ?, error = ?, output_tail = ? WHERE run_uid = ?",
                (ended_at, outcome, error, output_tail, run_uid),
            )
            conn.commit()
        except Exception:
            log.warning(
                "pipeline_history.finalize_failed",
                run_uid=run_uid,
                outcome=outcome,
                exc_info=True,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass
