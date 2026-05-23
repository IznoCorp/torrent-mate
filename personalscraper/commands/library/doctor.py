"""Health-check Typer command for the library indexer database.

Runs a suite of targeted checks against the indexer SQLite database and
reports results in a Rich table (default) or JSON (``--format json``).
Output format respects the global ``--format`` flag.  Exits 0 when all
checks pass, non-zero otherwise.

Health checks implemented (SH-8 / BD-Y / CL-M):

- **integrity_check** — ``PRAGMA integrity_check`` returns ``ok``.
- **foreign_keys_pragma** — ``PRAGMA foreign_keys`` returns 1 (FK enforcement on).
- **foreign_key_check** — ``PRAGMA foreign_key_check`` returns zero rows (no orphans).
- **schema_version_coherent** — ``schema_version`` table value matches ``user_version``.
- **no_stuck_scan_run** — no ``scan_run`` row stuck in ``status='running'`` for > 1 h.
- **repair_queue_backlog** — ``repair_queue`` pending rows < threshold (default 100).
- **index_outbox_lag** — oldest pending ``index_outbox`` row < threshold seconds old
  (default 3600 s).
- **merkle_drift** — live-recomputed merkle root matches stored value for all disks
  (zero drifted disks).
- **canonical_provider_populated** — ``canonical_provider`` set on > 50 % of items
  (post Phase 2.6 bootstrap).
- **phantom_paths** — zero phantom paths (``path`` rows whose resolved absolute path
  is gone from the filesystem, for mounted disks only).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.core.event_bus import EventBus

# ---------------------------------------------------------------------------
# Check result model
# ---------------------------------------------------------------------------


class CheckStatus(str, Enum):
    """Per-check outcome.

    Attributes:
        OK: Check passed — no issue detected.
        WARN: Soft failure; the operator should be aware but the DB is usable.
        FAIL: Hard failure; the DB may be unusable or data may be lost.
        SKIP: Check was skipped (e.g. table does not exist yet).
    """

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class CheckResult:
    """Result of a single health check.

    Attributes:
        name: Short identifier for the check (snake_case).
        status: One of ``ok``, ``warn``, ``fail``, ``skip``.
        message: Human-readable description of the finding.
        detail: Optional diagnostic detail (counts, sample rows, etc.).
    """

    name: str
    status: CheckStatus
    message: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        """Serialise to a plain dict for JSON output.

        Returns:
            Dict with ``name``, ``status``, ``message``, ``detail`` keys.
        """
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class DoctorReport:
    """Aggregate result of the ``library-doctor`` health check run.

    Attributes:
        checks: Ordered list of :class:`CheckResult` objects, one per check.
        elapsed_s: Wall-clock seconds taken to run all checks.
    """

    checks: list[CheckResult] = field(default_factory=list)
    elapsed_s: float = 0.0

    @property
    def overall_status(self) -> CheckStatus:
        """Worst status across all checks (fail > warn > skip > ok).

        Returns:
            The most severe :class:`CheckStatus` found in ``checks``.
        """
        priority = {CheckStatus.FAIL: 3, CheckStatus.WARN: 2, CheckStatus.SKIP: 1, CheckStatus.OK: 0}
        worst = CheckStatus.OK
        for c in self.checks:
            if priority[c.status] > priority[worst]:
                worst = c.status
        return worst

    @property
    def exit_code(self) -> int:
        """Return 0 if overall_status is ok or skip-only, non-zero otherwise.

        Returns:
            0 when all checks pass (or were skipped), 1 otherwise.
        """
        return 0 if self.overall_status in (CheckStatus.OK, CheckStatus.SKIP) else 1

    def as_dict(self) -> dict[str, object]:
        """Serialise to a plain dict for JSON output.

        Returns:
            Dict with ``overall_status``, ``elapsed_s``, and ``checks`` list.
        """
        return {
            "overall_status": self.overall_status.value,
            "elapsed_s": round(self.elapsed_s, 3),
            "checks": [c.as_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------


def _check_integrity(conn: sqlite3.Connection) -> CheckResult:
    """Run ``PRAGMA integrity_check`` and verify the result is ``ok``.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.

    Returns:
        :class:`CheckResult` with status ``ok`` when SQLite reports no
        structural errors, ``fail`` otherwise.
    """
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        result = row[0] if row else "unknown"
    except sqlite3.DatabaseError as exc:
        return CheckResult(
            name="integrity_check",
            status=CheckStatus.FAIL,
            message="PRAGMA integrity_check raised an error",
            detail=str(exc),
        )
    if result == "ok":
        return CheckResult(name="integrity_check", status=CheckStatus.OK, message="Database integrity OK")
    return CheckResult(
        name="integrity_check",
        status=CheckStatus.FAIL,
        message="PRAGMA integrity_check returned non-ok result",
        detail=str(result),
    )


def _check_foreign_keys_pragma(conn: sqlite3.Connection) -> CheckResult:
    """Verify ``PRAGMA foreign_keys`` is 1 (FK enforcement is active).

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.

    Returns:
        :class:`CheckResult` with status ``ok`` when FK enforcement is active,
        ``fail`` otherwise.
    """
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    value = row[0] if row else None
    if value == 1:
        return CheckResult(
            name="foreign_keys_pragma",
            status=CheckStatus.OK,
            message="PRAGMA foreign_keys = 1 (enforced)",
        )
    return CheckResult(
        name="foreign_keys_pragma",
        status=CheckStatus.FAIL,
        message="PRAGMA foreign_keys is not 1 — FK enforcement disabled",
        detail=f"foreign_keys = {value!r}",
    )


def _check_fk_orphans(conn: sqlite3.Connection) -> CheckResult:
    """Run ``PRAGMA foreign_key_check`` and verify zero orphan rows.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.

    Returns:
        :class:`CheckResult` with status ``ok`` when zero orphans are found,
        ``fail`` with sample rows otherwise.
    """
    orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    if not orphans:
        return CheckResult(name="foreign_key_check", status=CheckStatus.OK, message="No FK orphan rows")
    sample = str(orphans[:5])
    return CheckResult(
        name="foreign_key_check",
        status=CheckStatus.FAIL,
        message=f"{len(orphans)} FK orphan row(s) detected",
        detail=f"sample: {sample}",
    )


def _check_schema_version(conn: sqlite3.Connection) -> CheckResult:
    """Verify ``schema_version`` table value matches ``PRAGMA user_version``.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.

    Returns:
        :class:`CheckResult` with status ``ok`` when values match,
        ``warn`` when the ``schema_version`` table is missing (pre-migration DB),
        ``fail`` when values are present but diverge.
    """
    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        sv = row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        # Table does not exist yet — pre-migration DB is acceptable.
        return CheckResult(
            name="schema_version_coherent",
            status=CheckStatus.SKIP,
            message="schema_version table missing (pre-migration DB)",
            detail=f"user_version = {user_version}",
        )
    if sv == user_version:
        return CheckResult(
            name="schema_version_coherent",
            status=CheckStatus.OK,
            message=f"schema_version matches user_version ({sv})",
        )
    return CheckResult(
        name="schema_version_coherent",
        status=CheckStatus.FAIL,
        message="schema_version diverges from user_version",
        detail=f"schema_version.max = {sv}, PRAGMA user_version = {user_version}",
    )


def _check_no_stuck_scan_run(conn: sqlite3.Connection, stuck_threshold_s: int = 3600) -> CheckResult:
    """Check for scan_run rows stuck in ``status='running'`` for longer than threshold.

    A scan_run row is considered stuck when its ``started_at`` is more than
    ``stuck_threshold_s`` seconds ago and its ``status`` is still ``'running'``
    (i.e. ``finished_at`` is NULL).  This indicates a crashed or orphaned scanner
    process.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.
        stuck_threshold_s: Seconds after which a running scan is considered stuck.
            Default: 3600 (1 hour).

    Returns:
        :class:`CheckResult` with status ``ok`` when no stuck runs exist,
        ``warn`` otherwise (stuck runs do not corrupt data but block new scans).
    """
    cutoff = int(time.time()) - stuck_threshold_s
    try:
        rows = conn.execute(
            "SELECT id, mode, started_at FROM scan_run WHERE status='running' AND started_at < ?",
            (cutoff,),
        ).fetchall()
    except sqlite3.OperationalError:
        # scan_run table may not exist in an empty/pre-migration DB.
        return CheckResult(
            name="no_stuck_scan_run",
            status=CheckStatus.SKIP,
            message="scan_run table missing (pre-migration DB)",
        )
    if not rows:
        return CheckResult(name="no_stuck_scan_run", status=CheckStatus.OK, message="No stuck scan_run rows")
    sample = [(r[0], r[1], r[2]) for r in rows[:5]]
    return CheckResult(
        name="no_stuck_scan_run",
        status=CheckStatus.WARN,
        message=f"{len(rows)} scan_run row(s) stuck in 'running' > {stuck_threshold_s}s",
        detail=f"sample (id, mode, started_at): {sample}",
    )


def _check_repair_queue_backlog(conn: sqlite3.Connection, threshold: int = 100) -> CheckResult:
    """Check that pending ``repair_queue`` rows are below threshold.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.
        threshold: Maximum acceptable pending repair rows before warning.
            Default: 100.

    Returns:
        :class:`CheckResult` with status ``ok`` when count < threshold,
        ``warn`` otherwise.
    """
    try:
        row = conn.execute("SELECT COUNT(*) FROM repair_queue WHERE status='pending'").fetchone()
    except sqlite3.OperationalError:
        return CheckResult(
            name="repair_queue_backlog",
            status=CheckStatus.SKIP,
            message="repair_queue table missing (pre-migration DB)",
        )
    count = row[0] if row else 0
    if count < threshold:
        return CheckResult(
            name="repair_queue_backlog",
            status=CheckStatus.OK,
            message=f"repair_queue pending = {count} (< {threshold})",
        )
    return CheckResult(
        name="repair_queue_backlog",
        status=CheckStatus.WARN,
        message=f"repair_queue backlog high: {count} pending rows (threshold {threshold})",
        detail=f"pending = {count}",
    )


def _check_index_outbox_lag(conn: sqlite3.Connection, lag_threshold_s: int = 3600) -> CheckResult:
    """Check that the oldest pending ``index_outbox`` row is not too old.

    An old pending row indicates the outbox drainer is stalled or has not
    run recently.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.
        lag_threshold_s: Maximum age in seconds for the oldest pending row.
            Default: 3600 (1 hour).

    Returns:
        :class:`CheckResult` with status ``ok`` when lag is acceptable,
        ``warn`` when the oldest pending row exceeds the threshold,
        ``ok`` also when there are no pending rows.
    """
    try:
        row = conn.execute("SELECT MIN(created_at) FROM index_outbox WHERE status='pending'").fetchone()
    except sqlite3.OperationalError:
        return CheckResult(
            name="index_outbox_lag",
            status=CheckStatus.SKIP,
            message="index_outbox table missing (pre-migration DB)",
        )
    oldest_ts = row[0] if row else None
    if oldest_ts is None:
        # No pending rows — outbox is draining correctly.
        return CheckResult(
            name="index_outbox_lag",
            status=CheckStatus.OK,
            message="No pending index_outbox rows (outbox is empty)",
        )
    age_s = int(time.time()) - oldest_ts
    if age_s < lag_threshold_s:
        return CheckResult(
            name="index_outbox_lag",
            status=CheckStatus.OK,
            message=f"Oldest pending outbox row is {age_s}s old (< {lag_threshold_s}s)",
        )
    return CheckResult(
        name="index_outbox_lag",
        status=CheckStatus.WARN,
        message=f"Oldest pending index_outbox row is {age_s}s old (threshold {lag_threshold_s}s)",
        detail=f"oldest created_at = {oldest_ts}, age = {age_s}s",
    )


def _check_merkle_drift(conn: sqlite3.Connection) -> CheckResult:
    """Live-recompute merkle roots and verify they match stored values.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.

    Returns:
        :class:`CheckResult` with status ``ok`` when all disk merkle roots match,
        ``warn`` when one or more disk(s) have drifted.
    """
    try:
        from personalscraper.indexer.reconcile import detect_merkle_drift  # noqa: PLC0415
    except ImportError as exc:
        return CheckResult(
            name="merkle_drift",
            status=CheckStatus.SKIP,
            message="detect_merkle_drift unavailable",
            detail=str(exc),
        )
    try:
        drifted = detect_merkle_drift(conn)
    except sqlite3.OperationalError as exc:
        return CheckResult(
            name="merkle_drift",
            status=CheckStatus.SKIP,
            message="merkle_drift check failed (schema not ready?)",
            detail=str(exc),
        )
    if not drifted:
        return CheckResult(name="merkle_drift", status=CheckStatus.OK, message="Merkle roots match for all disks")
    return CheckResult(
        name="merkle_drift",
        status=CheckStatus.WARN,
        message=f"{len(drifted)} disk(s) have drifted merkle root",
        detail=f"drifted disk ids: {drifted}",
    )


def _check_canonical_provider_populated(conn: sqlite3.Connection, threshold_pct: float = 50.0) -> CheckResult:
    """Check that ``canonical_provider`` is set on more than ``threshold_pct`` of items.

    After the Phase 2.6 bootstrap (``library-init-canonical``), most items
    should have ``canonical_provider`` populated.  A low percentage indicates
    the bootstrap has not run or the column migration has not been applied.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.
        threshold_pct: Minimum percentage of items that must have
            ``canonical_provider`` set. Default: 50.0.

    Returns:
        :class:`CheckResult` with status ``ok`` when percentage >= threshold,
        ``warn`` when below threshold,
        ``skip`` when the table or column does not exist yet.
    """
    try:
        row = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()
    except sqlite3.OperationalError:
        return CheckResult(
            name="canonical_provider_populated",
            status=CheckStatus.SKIP,
            message="media_item table missing (pre-migration DB)",
        )
    total = row[0] if row else 0
    if total == 0:
        # Empty library — the check is vacuously satisfied.
        return CheckResult(
            name="canonical_provider_populated",
            status=CheckStatus.OK,
            message="No media_item rows — library is empty",
        )

    try:
        row = conn.execute("SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NOT NULL").fetchone()
    except sqlite3.OperationalError:
        # Column was added in migration 005 — skip if not present.
        return CheckResult(
            name="canonical_provider_populated",
            status=CheckStatus.SKIP,
            message="canonical_provider column missing (pre-migration 005 DB)",
        )
    populated = row[0] if row else 0
    pct = (populated / total) * 100.0 if total else 0.0
    if pct >= threshold_pct:
        return CheckResult(
            name="canonical_provider_populated",
            status=CheckStatus.OK,
            message=f"canonical_provider populated on {pct:.1f}% of items ({populated}/{total})",
        )
    return CheckResult(
        name="canonical_provider_populated",
        status=CheckStatus.WARN,
        message=f"canonical_provider populated on {pct:.1f}% of items — run library-init-canonical",
        detail=f"populated={populated}, total={total}, threshold={threshold_pct}%",
    )


def _check_phantom_paths(conn: sqlite3.Connection) -> CheckResult:
    """Check for phantom paths (path rows whose resolved absolute path is gone).

    Only evaluates mounted disks.  An unmounted disk's paths are not "phantom",
    just inaccessible — the correct remediation is the ``merkle`` or
    unreachable-strikes detectors.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.

    Returns:
        :class:`CheckResult` with status ``ok`` when zero phantom paths exist,
        ``warn`` otherwise.
    """
    try:
        from personalscraper.indexer.reconcile import detect_path_missing  # noqa: PLC0415
    except ImportError as exc:
        return CheckResult(
            name="phantom_paths",
            status=CheckStatus.SKIP,
            message="detect_path_missing unavailable",
            detail=str(exc),
        )
    try:
        missing = detect_path_missing(conn)
    except sqlite3.OperationalError as exc:
        return CheckResult(
            name="phantom_paths",
            status=CheckStatus.SKIP,
            message="phantom_paths check failed (schema not ready?)",
            detail=str(exc),
        )
    if not missing:
        return CheckResult(name="phantom_paths", status=CheckStatus.OK, message="No phantom paths detected")
    return CheckResult(
        name="phantom_paths",
        status=CheckStatus.WARN,
        message=f"{len(missing)} phantom path(s) detected (paths gone from filesystem)",
        detail=f"path ids (first 10): {missing[:10]}",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_doctor(
    conn: sqlite3.Connection,
    *,
    repair_queue_threshold: int = 100,
    outbox_lag_threshold_s: int = 3600,
    canonical_provider_threshold_pct: float = 50.0,
    stuck_scan_threshold_s: int = 3600,
) -> DoctorReport:
    """Run all health checks and return a :class:`DoctorReport`.

    Args:
        conn: Open :class:`sqlite3.Connection` on the indexer DB.
        repair_queue_threshold: Max acceptable pending repair_queue rows.
        outbox_lag_threshold_s: Max age in seconds for oldest pending outbox row.
        canonical_provider_threshold_pct: Minimum percent of items that must have
            ``canonical_provider`` set.
        stuck_scan_threshold_s: Seconds after which a running scan is stuck.

    Returns:
        Populated :class:`DoctorReport` with one :class:`CheckResult` per check.
    """
    start = time.monotonic()
    checks: list[CheckResult] = [
        _check_integrity(conn),
        _check_foreign_keys_pragma(conn),
        _check_fk_orphans(conn),
        _check_schema_version(conn),
        _check_no_stuck_scan_run(conn, stuck_threshold_s=stuck_scan_threshold_s),
        _check_repair_queue_backlog(conn, threshold=repair_queue_threshold),
        _check_index_outbox_lag(conn, lag_threshold_s=outbox_lag_threshold_s),
        _check_merkle_drift(conn),
        _check_canonical_provider_populated(conn, threshold_pct=canonical_provider_threshold_pct),
        _check_phantom_paths(conn),
    ]
    elapsed = time.monotonic() - start
    return DoctorReport(checks=checks, elapsed_s=elapsed)


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@app.command("library-doctor")
@handle_cli_errors
def library_doctor(
    ctx: typer.Context,
    repair_queue_threshold: int = typer.Option(
        100,
        "--repair-queue-threshold",
        help="Max pending repair_queue rows before WARN.",
    ),
    outbox_lag_threshold_s: int = typer.Option(
        3600,
        "--outbox-lag-threshold-s",
        help="Max age in seconds for oldest pending index_outbox row before WARN.",
    ),
    canonical_threshold_pct: float = typer.Option(
        50.0,
        "--canonical-threshold-pct",
        help="Min %% of media_item rows that must have canonical_provider set before WARN.",
    ),
    stuck_scan_threshold_s: int = typer.Option(
        3600,
        "--stuck-scan-threshold-s",
        help="Seconds after which a running scan_run is considered stuck.",
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Run health checks on the library indexer database.

    Executes a suite of targeted checks covering database integrity, schema
    coherence, scan-run lifecycle, outbox lag, Merkle drift, canonical-provider
    coverage, and phantom paths.  Output format respects the global
    ``--format`` flag (``personalscraper --format json library-doctor``).

    Exit code is 0 when all checks pass (status ok or skip), non-zero when any
    check is WARN or FAIL.

    Examples:
        personalscraper library-doctor
        personalscraper --format json library-doctor
        personalscraper library-doctor --repair-queue-threshold 50
        personalscraper library-doctor --outbox-lag-threshold-s 7200
    """
    import os as _os  # noqa: PLC0415

    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    cfg = ctx.obj.config if ctx.obj is not None else load_config(effective_config)

    if cfg.indexer.db_path is None:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)

    db_path = Path(cfg.indexer.db_path)
    migrations_dir = _os.path.dirname(_migrations_pkg.__file__)

    event_bus = EventBus()
    conn = open_db(db_path, event_bus=event_bus)
    apply_migrations(conn, Path(migrations_dir))

    try:
        report = run_doctor(
            conn,
            repair_queue_threshold=repair_queue_threshold,
            outbox_lag_threshold_s=outbox_lag_threshold_s,
            canonical_provider_threshold_pct=canonical_threshold_pct,
            stuck_scan_threshold_s=stuck_scan_threshold_s,
        )
    finally:
        conn.close()

    emit(
        report.as_dict(),
        rich_renderer=lambda: _print_table(report),
    )

    raise typer.Exit(code=report.exit_code)


def _print_table(report: DoctorReport) -> None:
    """Render the doctor report as a Rich table to the terminal.

    Rows are colour-coded:

    - Green (``[green]``) for ``ok``
    - Yellow (``[yellow]``) for ``warn`` and ``skip``
    - Red (``[red]``) for ``fail``

    Args:
        report: The :class:`DoctorReport` to render.
    """
    from rich.table import Table  # noqa: PLC0415

    console = state["console"]

    _STATUS_COLORS = {
        CheckStatus.OK: "green",
        CheckStatus.WARN: "yellow",
        CheckStatus.FAIL: "red",
        CheckStatus.SKIP: "yellow",
    }
    _STATUS_LABELS = {
        CheckStatus.OK: "OK",
        CheckStatus.WARN: "WARN",
        CheckStatus.FAIL: "FAIL",
        CheckStatus.SKIP: "SKIP",
    }

    table = Table(title="Library Doctor Report", show_header=True, header_style="bold")
    table.add_column("Check", style="bold", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Message")
    table.add_column("Detail", overflow="fold")

    for c in report.checks:
        color = _STATUS_COLORS[c.status]
        label = _STATUS_LABELS[c.status]
        table.add_row(
            c.name,
            f"[{color}]{label}[/{color}]",
            c.message,
            c.detail,
        )

    console.print(table)
    overall = report.overall_status
    color = _STATUS_COLORS[overall]
    label = _STATUS_LABELS[overall]
    console.print(f"\nOverall: [{color}]{label}[/{color}]  ({len(report.checks)} checks, {report.elapsed_s:.3f}s)")
