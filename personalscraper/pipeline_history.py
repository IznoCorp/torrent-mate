"""Run-history writer for the ``pipeline_run`` table (indexer migration 011).

Writes a durable, queryable record of every pipeline execution — one row per
run with per-step timing data stored as a JSON array in ``steps_json``.

The writer is **fail-soft**: every method wraps its DB work in a try/except,
logs a warning on failure, and never raises.  A history-write error must
never abort the pipeline.  It never creates the DB: a missing file is the named
``pipeline_history.db_missing`` condition, and the store is migrated at the run's boot.

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

from personalscraper.core.sqlite import refuse_newer_schema
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.indexer.library_view import IndexUnavailable, LibraryIndex
from personalscraper.indexer.migrations import MIGRATIONS_DIR as LIBRARY_MIGRATIONS_DIR
from personalscraper.logger import get_logger

log = get_logger("pipeline_history")

#: Max per-step reason strings persisted into ``steps_json`` (§8). A run with
#: thousands of per-item warnings would otherwise bloat the row; the raw log
#: tail (``output_tail``) keeps the exhaustive detail.
_MAX_PERSISTED_REASONS = 20


class _DbMissing(Exception):
    """The run-history DB file does not exist: a named condition, never a file created empty."""


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

    def _connect(self) -> sqlite3.Connection:
        """Open the existing DB for writing — never create it.

        A missing file is logged as ``pipeline_history.db_missing`` and refused: a plain
        ``sqlite3.connect`` would create an EMPTY file that the indexer's later migration then
        mistakes for a store, and every write would fail on a missing table. The store is
        migrated at the run's boot (:func:`~personalscraper.indexer.db.ensure_library_schema`).

        Returns:
            An open connection, with the newer-schema guard and the PRAGMAs applied.

        Raises:
            _DbMissing: The DB file does not exist.
            sqlite3.Error: The DB cannot be opened.
        """
        if not self._db_path.exists():
            log.warning("pipeline_history.db_missing", db_path=str(self._db_path))
            raise _DbMissing(str(self._db_path))
        # mode=rw: SQLite itself refuses to create the file if it vanishes between the check and here.
        conn = sqlite3.connect(f"{self._db_path.resolve().as_uri()}?mode=rw", uri=True, isolation_level=None)
        refuse_newer_schema(conn, LIBRARY_MIGRATIONS_DIR)
        apply_pragmas(conn)
        return conn

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
            conn = self._connect()
            conn.execute(
                f"{verb} pipeline_run "
                "(run_uid, trigger, dry_run, started_at, outcome, steps_json, pid, "
                "kind, command, options_json) "
                "VALUES (?, ?, ?, ?, 'running', '[]', ?, ?, ?, ?)",
                (run_uid, trigger, dry_run_int, started_at, pid, kind, command, options_json),
            )
            conn.commit()
        except _DbMissing:
            pass  # already logged once by _connect as pipeline_history.db_missing
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
            conn = self._connect()
            conn.execute(
                "UPDATE pipeline_run SET pid = ? WHERE run_uid = ?",
                (pid, run_uid),
            )
            conn.commit()
        except _DbMissing:
            pass  # already logged once by _connect as pipeline_history.db_missing
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
        *,
        success_count: int | None = None,
        skip_count: int | None = None,
        error_count: int | None = None,
        unmatched_count: int | None = None,
        counts: dict[str, int] | None = None,
        reasons: list[str] | None = None,
    ) -> None:
        """Append a step timing record to the row's ``steps_json`` array.

        Reads the current ``steps_json`` value for the given ``run_uid``,
        appends a new entry ``{name, started_at, ended_at, status}``, and
        writes the updated array back.

        The five keyword-only summary parameters (webui-ux Phase 2.2) are
        additive and optional. When supplied they are folded into the same
        ``steps_json`` entry so the persisted last-run report can surface the
        interpreted per-step counts after the live WS stream is gone. Each is
        omitted from the entry when ``None`` (or, for ``counts``, empty), so
        legacy rows and callers that pass only the timing fields keep the exact
        prior entry shape — every reader must default-parse missing keys.

        Args:
            run_uid: Unique run identifier.
            step_name: Name of the pipeline step (e.g. ``'ingest'``).
            started_at: Unix-epoch timestamp (``time.time()``) when the step
                started.
            ended_at: Unix-epoch timestamp (``time.time()``-based) when the
                step completed.
            status: Step outcome (``'success'`` or ``'error'``).
            success_count: :class:`~personalscraper.models.StepReport`
                ``success_count`` for this step, or ``None`` to omit.
            skip_count: StepReport ``skip_count`` for this step, or ``None``.
            error_count: StepReport ``error_count`` for this step, or ``None``.
            unmatched_count: Length of StepReport ``unmatched_paths`` for this
                step (folders the scraper could not confidently match), or
                ``None`` to omit.
            counts: A small StepReport ``counts`` sub-category dict (e.g.
                ``{"downloaded": 3, "bot_detected": 1}``), or ``None``/empty to
                omit.
            reasons: A bounded list of human-readable reason strings (StepReport
                ``warnings`` + ``details``) explaining WHY a step skipped /
                deferred / errored — e.g. "X: fichiers manquants sur le disque".
                Persisted (capped at :data:`_MAX_PERSISTED_REASONS`) so the
                operator sees the "why" after the live WS stream is gone (§8);
                without this the reasons died with the process and history
                showed bare counts. ``None``/empty omits the key.
        """
        entry: dict[str, object] = {
            "name": step_name,
            "started_at": started_at,
            "ended_at": ended_at,
            "status": status,
        }
        # Fold the StepReport summary into the entry only when present so the
        # persisted shape stays byte-identical for timing-only callers/rows.
        if success_count is not None:
            entry["success_count"] = success_count
        if skip_count is not None:
            entry["skip_count"] = skip_count
        if error_count is not None:
            entry["error_count"] = error_count
        if unmatched_count is not None:
            entry["unmatched_count"] = unmatched_count
        if counts:
            entry["counts"] = counts
        if reasons:
            # Cap so a pathological run (thousands of per-item warnings) cannot
            # bloat steps_json; the operator needs the representative reasons,
            # not every line (the raw log tail keeps the full detail).
            entry["reasons"] = list(reasons[:_MAX_PERSISTED_REASONS])
        try:
            conn = self._connect()
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
        except _DbMissing:
            pass  # already logged once by _connect as pipeline_history.db_missing
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
            conn = self._connect()
            conn.execute(
                "UPDATE pipeline_run SET ended_at = ?, outcome = ?, error = ?, output_tail = ? WHERE run_uid = ?",
                (ended_at, outcome, error, output_tail, run_uid),
            )
            conn.commit()
        except _DbMissing:
            pass  # already logged once by _connect as pipeline_history.db_missing
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

    def outcome(self, run_uid: str) -> str | None:
        """Read the outcome of one run's row — the one read of this writer, and the one that raises.

        A supervisor settling a silent worker must tell « no row » from « unreadable now »: a
        locked or broken store is retried, never taken for a missing row, so this read is not
        fail-soft. It goes through the library's read view (``mode=ro`` and ``query_only``): it
        can neither write nor create the store, and a store that does not exist holds no row.

        Args:
            run_uid: Unique run identifier.

        Returns:
            The row's ``outcome`` (``'running'`` while unfinished); ``None`` when no row has that uid.

        Raises:
            IndexUnavailable: If the store cannot be read (locked past the busy timeout, corrupt, unmigrated).
        """
        if not self._db_path.exists():
            return None
        try:
            with LibraryIndex(self._db_path).reader() as reader:
                return reader.run_outcome(run_uid)
        except sqlite3.Error as exc:
            raise IndexUnavailable(str(exc)) from exc
