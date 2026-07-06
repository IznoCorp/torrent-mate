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

    def insert(self, run_uid: str, trigger: str, dry_run: bool, pid: int) -> None:
        """Insert a new row into ``pipeline_run`` with ``outcome="running"``.

        Args:
            run_uid: Unique run identifier (UUID string).
            trigger: How the run was triggered (``'cli'``, ``'web'``, ``'cron'``).
            dry_run: ``True`` if this is a dry run.
            pid: OS process ID of the pipeline process.
        """
        started_at = time.time()
        dry_run_int = 1 if dry_run else 0
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            conn.execute(
                "INSERT INTO pipeline_run "
                "(run_uid, trigger, dry_run, started_at, outcome, steps_json, pid) "
                "VALUES (?, ?, ?, ?, 'running', '[]', ?)",
                (run_uid, trigger, dry_run_int, started_at, pid),
            )
            conn.commit()
        except Exception:
            log.warning(
                "pipeline_history.insert_failed",
                run_uid=run_uid,
                trigger=trigger,
                dry_run=dry_run,
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
    ) -> None:
        """Finalize a pipeline run by setting ``ended_at`` and ``outcome``.

        Args:
            run_uid: Unique run identifier.
            outcome: Final outcome (``'success'``, ``'error'``, or ``'killed'``).
            error: Optional error message when ``outcome`` is ``'error'``.
        """
        ended_at = time.time()
        try:
            conn = sqlite3.connect(str(self._db_path), isolation_level=None)
            apply_pragmas(conn)
            conn.execute(
                "UPDATE pipeline_run SET ended_at = ?, outcome = ?, error = ? WHERE run_uid = ?",
                (ended_at, outcome, error, run_uid),
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
