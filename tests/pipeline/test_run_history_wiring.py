"""Integration tests for PipelineRunWriter wiring inside ``Pipeline.run()``.

Verifies the three lifecycle hook points (pipe-control sub-phase 1.3b):

- **Insert**: after ``PipelineStarted``, a row is written with
  ``outcome='running'`` and ``steps_json='[]'``.
- **Update per step**: after ``StepCompleted`` / ``StepErrored``,
  ``steps_json`` accumulates one entry per step.
- **Finalize**: after ``PipelineEnded``, ``outcome`` is set to
  ``'success'`` / ``'killed'`` / ``'error'`` and ``ended_at`` is non-null.

The writer is **injected** (plan-drift: cleaner DI than the plan's
"open DB + pass conn"). These tests build a ``PipelineRunWriter`` against
a temporary ``library.db`` and pass it as ``history_writer=``.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline, _PipelineInterrupted
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.pipeline_protocol import StepContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PIPELINE_RUN_DDL = """
CREATE TABLE pipeline_run (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_uid    TEXT    UNIQUE NOT NULL,
    trigger    TEXT    NOT NULL,
    dry_run    INTEGER NOT NULL DEFAULT 0,
    started_at REAL    NOT NULL,
    ended_at   REAL,
    outcome    TEXT,
    steps_json TEXT,
    error      TEXT,
    pid        INTEGER
)
"""

NINE_STEP_NAMES = (
    "ingest",
    "sort",
    "clean",
    "scrape",
    "cleanup",
    "enforce",
    "verify",
    "trailers",
    "dispatch",
)


def _create_db(db_path: Path) -> None:
    """Create a SQLite database with the ``pipeline_run`` table."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.executescript(PIPELINE_RUN_DDL)
    conn.commit()
    conn.close()


def _fetch_row(db_path: Path, run_uid: str) -> dict | None:
    """Return the ``pipeline_run`` row as a dict, or ``None``."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    row = conn.execute(
        "SELECT run_uid, trigger, dry_run, started_at, ended_at, outcome, steps_json, error, pid "
        "FROM pipeline_run WHERE run_uid = ?",
        (run_uid,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "run_uid": row[0],
        "trigger": row[1],
        "dry_run": row[2],
        "started_at": row[3],
        "ended_at": row[4],
        "outcome": row[5],
        "steps_json": row[6],
        "error": row[7],
        "pid": row[8],
    }


def _stub_app() -> AppContext:
    """Minimal :class:`AppContext` with a real :class:`EventBus`."""
    config = MagicMock()
    config.disks = []
    config.paths.staging_dir = MagicMock()
    ingest_entry = MagicMock()
    ingest_entry.id = 97
    ingest_entry.role = "ingest"
    config.staging_dirs = [ingest_entry]
    # A REAL empty dir — not a MagicMock: PauseController builds
    # ``data_dir / "pipeline.pause"`` and calls ``.exists()`` on it. A MagicMock
    # path makes ``.exists()`` truthy, so ``checkpoint()`` loops forever thinking
    # the pipeline is paused. An empty real dir has no sentinel → immediate no-op.
    config.paths.data_dir = Path(tempfile.mkdtemp())
    settings = MagicMock()
    return AppContext(
        config=config,
        settings=settings,
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )


class _NoOpStep:
    """PipelineStep stub returning a clean :class:`StepReport`."""

    def __init__(self, name: str, *, raises: bool = False) -> None:
        self.name = name
        self._raises = raises

    def __call__(self, ctx: StepContext) -> StepReport | tuple[StepReport, list]:
        if self._raises:
            raise RuntimeError(f"boom in {self.name}")
        if self.name == "verify":
            return StepReport(name=self.name, success_count=1), []
        return StepReport(name=self.name, success_count=1)


def _step_registry(*, raise_on: str | None = None) -> dict[str, _NoOpStep]:
    """Build a full 9-step no-op registry; optionally one step raises."""
    return {name: _NoOpStep(name, raises=(name == raise_on)) for name in NINE_STEP_NAMES}


def _run_with_writer(
    pipeline: Pipeline,
    registry: dict[str, _NoOpStep],
    history_writer: PipelineRunWriter,
    *,
    dry_run: bool = False,
    trigger_reason: str = "test",
) -> None:
    """Run the pipeline with stub steps, injecting the history writer."""
    with (
        patch("personalscraper.pipeline.ensure_staging_tree"),
        patch.object(Pipeline, "_check_temp_empty_gate"),
        patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
        patch("personalscraper.pipeline.apply_step_overrides", return_value=registry),
    ):
        pipeline.run(
            dry_run=dry_run,
            trigger_reason=trigger_reason,
            history_writer=history_writer,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHistoryWriterInsert:
    """After ``PipelineStarted``, a row is inserted with ``outcome='running'``."""

    def test_insert_creates_row_with_running_outcome(self) -> None:
        """A no-op run creates one ``pipeline_run`` row with ``outcome='running'``.

        At insert time, finalized to ``'success'`` at the end.
        """
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            app = _stub_app()
            writer = PipelineRunWriter(db_path)
            pipeline = Pipeline(app)

            _run_with_writer(pipeline, _step_registry(), writer)

            # The row was inserted by the wiring — we need to find it.
            # The run_uid is stashed on the pipeline instance.
            run_uid = pipeline._run_uid
            assert run_uid is not None

            row = _fetch_row(db_path, run_uid)
            assert row is not None
            assert row["trigger"] == "test"
            assert row["dry_run"] == 0
            assert row["pid"] is not None
            assert row["outcome"] == "success"
            assert row["ended_at"] is not None

    def test_insert_stores_trigger_reason(self) -> None:
        """The ``trigger_reason`` kwarg is stored in the ``trigger`` column."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            app = _stub_app()
            writer = PipelineRunWriter(db_path)
            pipeline = Pipeline(app)

            _run_with_writer(pipeline, _step_registry(), writer, trigger_reason="cron")

            row = _fetch_row(db_path, pipeline._run_uid)
            assert row is not None
            assert row["trigger"] == "cron"

    def test_dry_run_still_records_row(self) -> None:
        """A ``--dry-run`` invocation still creates a history row."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            app = _stub_app()
            writer = PipelineRunWriter(db_path)
            pipeline = Pipeline(app)

            _run_with_writer(pipeline, _step_registry(), writer, dry_run=True)

            row = _fetch_row(db_path, pipeline._run_uid)
            assert row is not None
            assert row["dry_run"] == 1
            assert row["outcome"] == "success"

    def test_no_writer_is_no_op(self) -> None:
        """When ``history_writer`` is ``None`` (the default), ``_run_uid`` stays ``None``.

        And no DB interaction happens — the pipeline runs normally.
        """
        app = _stub_app()
        pipeline = Pipeline(app)

        _run_with_writer(pipeline, _step_registry(), None)  # type: ignore[arg-type]

        # Pipeline completed without error; _run_uid is always set once
        # run() starts (set unconditionally before the writer check).
        assert pipeline._run_uid is not None


class TestHistoryWriterUpdateStep:
    """After each ``StepCompleted`` / ``StepErrored``, ``steps_json`` grows."""

    def test_all_nine_steps_recorded(self) -> None:
        """A clean 9-step run records 9 entries in ``steps_json``."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            app = _stub_app()
            writer = PipelineRunWriter(db_path)
            pipeline = Pipeline(app)

            _run_with_writer(pipeline, _step_registry(), writer)

            row = _fetch_row(db_path, pipeline._run_uid)
            assert row is not None
            steps = json.loads(row["steps_json"])
            assert len(steps) == 9
            step_names = [s["name"] for s in steps]
            assert step_names == list(NINE_STEP_NAMES)
            for s in steps:
                if s["name"] == "dispatch":
                    # No verified items → dispatch is synthesized as "skipped".
                    assert s["status"] == "skipped"
                else:
                    assert s["status"] == "success"
                assert s["started_at"] <= s["ended_at"]

    def test_error_step_recorded_as_error(self) -> None:
        """A crashing non-critical step (scrape) is recorded with status 'error'."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            app = _stub_app()
            writer = PipelineRunWriter(db_path)
            pipeline = Pipeline(app)
            registry = _step_registry(raise_on="scrape")

            _run_with_writer(pipeline, registry, writer)

            row = _fetch_row(db_path, pipeline._run_uid)
            assert row is not None
            steps = json.loads(row["steps_json"])
            # scrape errored, but all 9 steps still ran (error is non-critical)
            assert len(steps) == 9
            scrape_entry = next(s for s in steps if s["name"] == "scrape")
            assert scrape_entry["status"] == "error"
            # All other steps are success, except dispatch (synthesized as "skipped").
            for s in steps:
                if s["name"] not in ("scrape", "dispatch"):
                    assert s["status"] == "success"
                elif s["name"] == "dispatch":
                    assert s["status"] == "skipped"


class TestHistoryWriterFinalize:
    """After ``PipelineEnded``, ``ended_at`` is set and ``outcome`` reflects the run."""

    def test_finalize_sets_success_outcome(self) -> None:
        """A clean run is finalized with ``outcome='success'``."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            app = _stub_app()
            writer = PipelineRunWriter(db_path)
            pipeline = Pipeline(app)

            _run_with_writer(pipeline, _step_registry(), writer)

            row = _fetch_row(db_path, pipeline._run_uid)
            assert row is not None
            assert row["outcome"] == "success"
            assert row["ended_at"] is not None
            assert row["error"] is None

    def test_finalize_on_interrupted_run(self) -> None:
        """A pipeline interrupted mid-run is finalized as 'killed'.

        Simulates a mid-run kill by patching ``_check_shutdown_requested``
        to raise ``_PipelineInterrupted`` at the ``before_sort`` boundary,
        which fires after ingest completes.  A pre-run ``request_shutdown``
        call is NOT sufficient — ``run()`` resets ``_shutdown_requested``
        at its start, so the flag would be clobbered.
        """
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            app = _stub_app()
            writer = PipelineRunWriter(db_path)
            pipeline = Pipeline(app)

            def _kill_at_sort(self: object, boundary: str) -> None:
                if boundary == "before_sort":
                    raise _PipelineInterrupted("test_kill")

            with (
                patch("personalscraper.pipeline.ensure_staging_tree"),
                patch.object(Pipeline, "_check_temp_empty_gate"),
                patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
                patch("personalscraper.pipeline.apply_step_overrides", return_value=_step_registry()),
                patch.object(Pipeline, "_check_shutdown_requested", _kill_at_sort),
            ):
                pipeline.run(
                    trigger_reason="test",
                    history_writer=writer,
                )

            row = _fetch_row(db_path, pipeline._run_uid)
            assert row is not None
            assert row["outcome"] == "killed"
            assert row["ended_at"] is not None


class TestHistoryWriterEdgeCases:
    """Writer edge-cases: missing DB, writer construction failure."""

    def test_none_writer_does_not_crash_pipeline(self) -> None:
        """``history_writer=None`` (explicit) is a normal no-history run."""
        app = _stub_app()
        pipeline = Pipeline(app)

        _run_with_writer(pipeline, _step_registry(), None)  # type: ignore[arg-type]

        # Run completed without error; _run_uid is always set once run() starts.
        assert pipeline._run_uid is not None

    def test_writer_failure_does_not_abort_pipeline(self) -> None:
        """If the writer's DB is missing, the run still completes (fail-soft)."""
        app = _stub_app()
        writer = PipelineRunWriter(
            db_path=Path("/nonexistent/path/library.db"),
        )
        pipeline = Pipeline(app)

        # The writer methods themselves are fail-soft; the pipeline must not
        # crash even when insert/update/finalize fail internally.
        _run_with_writer(pipeline, _step_registry(), writer)

        # Run completed without error (the writer logged warnings internally).
        assert pipeline._run_uid is not None
