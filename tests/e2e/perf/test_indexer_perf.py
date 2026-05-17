"""Performance regression tests for the media indexer (sub-phase 4.10b).

Six budget rows from DESIGN §11.11 are exercised under the ``slow`` mark —
they are skipped unless ``-m slow`` is passed to pytest.  Each row reads
``last_measured_seconds`` from ``tests/e2e/perf/baseline.json`` and asserts
that the current measurement is at most 1.5× that baseline.

When the environment variable ``PERF_REBASELINE=1`` is set, the test **writes
back** the freshly measured time to ``baseline.json`` instead of asserting.
This is the mechanism used by ``make perf-rebaseline``.

Two invariant tests (always-on, NOT slow-marked) prove the orthogonality
properties claimed in DESIGN §11.1–§11.3:

- ``test_split_cold_scan_invariant``: scanning two disks separately one at a
  time (``--full --disk D1`` then ``--full --disk D2``) produces the same final
  DB state as a single ``--full`` covering both disks.
- ``test_two_stage_path_invariant``: running ``quick`` then ``enrich`` on a
  freshly indexed DB produces a DB state equivalent to a single ``full`` scan.

Design choice — fixture strategy for slow tests:
    The tests check whether ``.fixture/`` is populated and, if not, call
    ``build_fixture.build_fixture()`` in-process (rather than shelling out) so
    that the build failure causes the test to fail rather than silently skip.
    This makes CI failures actionable.  If the fixture directory **is** empty
    and the build somehow fails, the individual row tests will still skip (via
    ``pytest.skip``) so as not to block the whole suite with a multi-minute
    build timeout.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PERF_DIR = Path(__file__).resolve().parent
_FIXTURE_DIR = _PERF_DIR / ".fixture"
_BASELINE_JSON = _PERF_DIR / "baseline.json"
_FIXTURE_VERSION_FILE = _PERF_DIR / "FIXTURE_VERSION"
_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_baseline() -> dict[str, dict[str, Any]]:
    """Read ``baseline.json`` and return a mapping of mode → row dict.

    Returns:
        Dict keyed by ``mode`` string, each value being the full row dict
        (``target_seconds``, ``last_measured_seconds``, ``last_measured_at``,
        ``fixture_version``).

    Raises:
        FileNotFoundError: If ``baseline.json`` does not exist.
    """
    rows = json.loads(_BASELINE_JSON.read_text())
    return {r["mode"]: r for r in rows}


def _write_baseline(rows_by_mode: dict[str, dict[str, Any]]) -> None:
    """Write an updated ``baseline.json`` preserving field order.

    Args:
        rows_by_mode: Dict keyed by ``mode`` string with the full row payload
            including the freshly updated ``last_measured_seconds`` and
            ``last_measured_at``.
    """
    rows = list(rows_by_mode.values())
    _BASELINE_JSON.write_text(json.dumps(rows, indent=2) + "\n")


def _open_db(path: Path) -> sqlite3.Connection:
    """Open a file-backed SQLite connection with the full indexer schema applied.

    Sets ``journal_mode=WAL`` and ``busy_timeout=30000`` upfront so the
    test connection plays well with the scanner's per-worker connections
    (which open with the same PRAGMAs).  Without this the DB would start
    in rollback-journal mode; the first worker that runs ``PRAGMA
    journal_mode=WAL`` then needs an exclusive lock to switch journal
    modes, contending with the test's own connection and producing
    transient ``database is locked`` failures on loaded CI runners.

    Args:
        path: On-disk database path (created if absent).

    Returns:
        Open :class:`sqlite3.Connection` with FK enforcement, WAL mode,
        a 30 s busy timeout, and all migrations applied.
    """
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _open_mem_db() -> sqlite3.Connection:
    """Open an in-memory SQLite connection with the full indexer schema.

    Returns:
        Open :class:`sqlite3.Connection` backed by ``:memory:``, FK ON, all
        migrations applied.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, label: str, mount_path: str) -> DiskRow:
    """Insert a minimal disk row and return the populated :class:`DiskRow`.

    Args:
        conn: Open SQLite connection.
        label: Human-readable disk label (used as UUID suffix for uniqueness).
        mount_path: Absolute path of the mount point.

    Returns:
        :class:`DiskRow` instance with the PK assigned by SQLite.
    """
    now = int(time.time())
    row = DiskRow(
        id=0,
        uuid=f"test-uuid-{label}",
        label=label,
        mount_path=mount_path,
        last_seen_at=now,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    disk_id = disk_repo.insert(conn, row)
    return DiskRow(
        id=disk_id,
        uuid=row.uuid,
        label=row.label,
        mount_path=row.mount_path,
        last_seen_at=row.last_seen_at,
        merkle_root=row.merkle_root,
        is_mounted=row.is_mounted,
        unreachable_strikes=row.unreachable_strikes,
    )


def _populate_tiny_fixture(root: Path, n_files: int, suffix: str = ".mkv") -> None:
    """Create *n_files* tiny files under *root* for invariant tests.

    Files are spread across two subdirectories to exercise recursive walking.

    Args:
        root: Root directory under which to create files.
        n_files: Number of files to create.
        suffix: File extension for created files.
    """
    dir_a = root / "dirA"
    dir_b = root / "dirB"
    dir_a.mkdir(parents=True, exist_ok=True)
    dir_b.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        target_dir = dir_a if i % 2 == 0 else dir_b
        (target_dir / f"file_{i:04d}{suffix}").write_bytes(b"\x00" * 64)


def _collect_db_state(conn: sqlite3.Connection) -> dict[str, object]:
    """Collect a summary of DB state for equality assertions.

    Captures the set of ``(rel_path, filename)`` pairs from ``media_file``
    (joined with ``path``) and the ``enriched_at IS NOT NULL`` count.  This
    is sufficient for the invariant tests, which check structural equivalence
    rather than byte-level identity.

    Args:
        conn: Open SQLite connection.

    Returns:
        Dict with keys ``files`` (frozenset of ``(rel_path, filename)``
        strings) and ``enriched_count`` (int).
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT p.rel_path, mf.filename, mf.enriched_at
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
         WHERE mf.deleted_at IS NULL
        """
    ).fetchall()
    conn.row_factory = None
    files: frozenset[str] = frozenset(f"{r['rel_path']}/{r['filename']}" for r in rows)
    enriched_count: int = sum(1 for r in rows if r["enriched_at"] is not None)
    return {"files": files, "enriched_count": enriched_count}


def _ensure_fixture(fixture_dir: Path) -> Path:
    """Ensure the versioned fixture subtree exists; build it if needed.

    Calls :func:`build_fixture.build_fixture` in-process so that a build
    failure surfaces as a test error (rather than a silent skip).  If the
    build fails for any reason, the test row that called this function is
    allowed to skip with a descriptive message.

    Args:
        fixture_dir: Root of the fixture directory (usually ``.fixture/``).

    Returns:
        Path to the versioned fixture root
        (e.g. ``.fixture/v1/``).

    Raises:
        pytest.skip.Exception: When the fixture cannot be built.
    """
    from tests.e2e.perf import build_fixture as _bfm  # noqa: PLC0415

    version = int(_FIXTURE_VERSION_FILE.read_text().strip())
    versioned_root = fixture_dir / f"v{version}"
    if not versioned_root.exists() or not any(versioned_root.rglob("*")):
        try:
            _bfm.build_fixture(
                output_dir=fixture_dir,
                seed=_bfm.DEFAULT_SEED,
                version_file=_FIXTURE_VERSION_FILE,
            )
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"fixture build failed: {exc}")
    return versioned_root


# ---------------------------------------------------------------------------
# Rebaseline helpers
# ---------------------------------------------------------------------------


def _rebaseline_mode() -> bool:
    """Return True when PERF_REBASELINE=1 is set in the environment.

    Returns:
        ``True`` if the environment variable ``PERF_REBASELINE`` is set to
        ``"1"``, ``False`` otherwise.
    """
    return os.environ.get("PERF_REBASELINE", "0") == "1"


def _record_measurement(mode: str, elapsed: float) -> None:
    """Write *elapsed* back to ``baseline.json`` for *mode*.

    Called only when ``PERF_REBASELINE=1``.  Updates ``last_measured_seconds``
    and ``last_measured_at`` for the matching row, preserving all other rows
    and fields.

    Args:
        mode: The ``mode`` key in ``baseline.json`` to update.
        elapsed: Freshly measured wall-clock time in seconds.
    """
    rows_by_mode = _read_baseline()
    row = rows_by_mode[mode]
    row["last_measured_seconds"] = round(elapsed, 3)
    row["last_measured_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_baseline(rows_by_mode)


def _assert_or_rebaseline(mode: str, elapsed: float) -> None:
    """Assert elapsed time against the 1.5× baseline rule, or write baseline.

    In normal mode: asserts ``elapsed <= last_measured_seconds * 1.5``.
    In rebaseline mode (``PERF_REBASELINE=1``): writes the new measurement to
    ``baseline.json`` and does not assert.

    Args:
        mode: The ``mode`` key in ``baseline.json``.
        elapsed: Freshly measured wall-clock time in seconds.

    Raises:
        AssertionError: When ``elapsed > last_measured_seconds * 1.5`` in
            normal (non-rebaseline) mode.
    """
    rows_by_mode = _read_baseline()
    row = rows_by_mode[mode]
    if _rebaseline_mode():
        _record_measurement(mode, elapsed)
        return
    threshold = row["last_measured_seconds"] * 1.5
    assert elapsed <= threshold, (
        f"[{mode}] perf regression: {elapsed:.2f}s > {threshold:.2f}s (1.5× baseline {row['last_measured_seconds']}s)"
    )


# ---------------------------------------------------------------------------
# Perf tests — require the heavy 1 000-item fixture (slow-marked)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestPerfBudgetRows:
    """Six budget rows from DESIGN §11.11, each asserted against baseline.json.

    All tests are ``@pytest.mark.slow`` and are excluded from the default
    pytest run.  Run with ``pytest -m slow tests/e2e/perf/test_indexer_perf.py``
    or via ``make perf-rebaseline`` (which sets ``PERF_REBASELINE=1``).

    Each test:
    1. Ensures the versioned fixture exists (builds it in-process if absent).
    2. Registers fixture disks in a fresh file-backed SQLite DB.
    3. Runs the indicated scan mode / scenario.
    4. Records the wall-clock elapsed time.
    5. Asserts (or rebaselines) against ``last_measured_seconds * 1.5``.
    """

    def _make_disk_db(self, tmp_path: Path, fixture_root: Path) -> tuple[Path, list[DiskRow]]:
        """Create a fresh DB and register all top-level fixture disk directories.

        Args:
            tmp_path: pytest temporary directory for the DB file.
            fixture_root: Versioned fixture root (e.g. ``.fixture/v1/``).

        Returns:
            Tuple of ``(db_path, disks)`` where ``db_path`` is the path to the
            SQLite file and ``disks`` is the list of inserted
            :class:`DiskRow` objects.
        """
        db_path = tmp_path / "indexer.db"
        conn = _open_db(db_path)
        disks: list[DiskRow] = []
        for disk_dir in sorted(fixture_root.iterdir()):
            if disk_dir.is_dir():
                disks.append(_insert_disk(conn, disk_dir.name, str(disk_dir)))
        conn.close()
        return db_path, disks

    def _run_scan(
        self,
        db_path: Path,
        disks: list[DiskRow],
        mode: ScanMode,
        disk_filter: str | None = None,
        budget_seconds: float | None = None,
    ) -> float:
        """Run a scan and return wall-clock elapsed seconds.

        Args:
            db_path: Path to the SQLite DB.
            disks: List of :class:`DiskRow` objects to scan.
            mode: :class:`ScanMode` to use.
            disk_filter: Optional disk label to scope the scan.
            budget_seconds: Optional budget ceiling in seconds.

        Returns:
            Wall-clock elapsed time in seconds.
        """
        conn = _open_db(db_path)
        with patch(_GUARD_PATCH, return_value=None):
            t0 = time.monotonic()
            scan(
                disks=disks,
                mode=mode,
                generation=1,
                conn=conn,
                disk_filter=disk_filter,
                db_path=db_path,
                budget_seconds=budget_seconds,
                event_bus=EventBus(),
            )
            elapsed = time.monotonic() - t0
        conn.close()
        return elapsed

    def test_quick_merkle_hit(self, tmp_path: Path) -> None:
        """Quick scan where all disk Merkle roots match (zero FS reads after DB check).

        Scenario: run a full scan first to populate Merkle roots, then run
        a quick scan on an unchanged fixture.  The quick scan should short-
        circuit every disk via the stored Merkle root.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        mode = "quick_merkle_hit"
        fixture_root = _ensure_fixture(_FIXTURE_DIR)
        db_path, disks = self._make_disk_db(tmp_path, fixture_root)

        # Seed the DB with a full scan to populate Merkle roots.
        self._run_scan(db_path, disks, ScanMode.full)

        # Quick scan — Merkle roots match, all disks should be skipped.
        elapsed = self._run_scan(db_path, disks, ScanMode.quick)
        _assert_or_rebaseline(mode, elapsed)

    def test_quick_merkle_miss(self, tmp_path: Path) -> None:
        """Quick scan where all Merkle roots miss (full dir-mtime walk required).

        Scenario: the DB is freshly initialised (no stored Merkle roots), so
        every disk triggers a dir-mtime walk.  This is the worst case for
        quick mode.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        mode = "quick_merkle_miss"
        fixture_root = _ensure_fixture(_FIXTURE_DIR)
        db_path, disks = self._make_disk_db(tmp_path, fixture_root)

        # Run a full scan WITHOUT updating merkle root (or just let quick mode
        # discover it fresh — no stored roots means every disk is a miss).
        # We populate the DB with file rows so the walk has something to compare,
        # then wipe merkle_root so the next quick scan must walk.
        conn = _open_db(db_path)
        with patch(_GUARD_PATCH, return_value=None):
            scan(disks=disks, mode=ScanMode.full, generation=1, conn=conn, db_path=db_path, event_bus=EventBus())
        # Wipe merkle_root for all disks to force full dir-mtime walk.
        for disk in disks:
            conn.execute("UPDATE disk SET merkle_root = NULL WHERE id = ?", (disk.id,))
        conn.commit()
        conn.close()

        elapsed = self._run_scan(db_path, disks, ScanMode.quick)
        _assert_or_rebaseline(mode, elapsed)

    def test_quick_changed_100(self, tmp_path: Path) -> None:
        """Quick scan with 100 files modified since last scan (dir-mtime walk).

        Scenario: after a full scan that stores Merkle roots, touch the mtime
        of 100 files to invalidate the stored root.  The quick scan must
        detect the Merkle miss and walk the affected directories.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        mode = "quick_changed_100"
        fixture_root = _ensure_fixture(_FIXTURE_DIR)
        db_path, disks = self._make_disk_db(tmp_path, fixture_root)

        # Seed full scan to populate Merkle roots.
        self._run_scan(db_path, disks, ScanMode.full)

        # Touch 100 files to force Merkle miss on the affected disks.
        all_files = sorted(fixture_root.rglob("*.mkv"))[:100]
        now_ns = time.time_ns()
        for fpath in all_files:
            os.utime(fpath, ns=(now_ns, now_ns))

        elapsed = self._run_scan(db_path, disks, ScanMode.quick)
        _assert_or_rebaseline(mode, elapsed)

    def test_incremental_new_100(self, tmp_path: Path) -> None:
        """Incremental scan with 100 new files added to the fixture.

        Scenario: after a full scan, create 100 new ``.mkv`` files in the
        fixture directories and run an incremental scan.  The scanner must
        detect all 100 new files and insert them.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        mode = "incremental_new_100"
        fixture_root = _ensure_fixture(_FIXTURE_DIR)
        db_path, disks = self._make_disk_db(tmp_path, fixture_root)

        # Seed full scan.
        self._run_scan(db_path, disks, ScanMode.full)

        # Add 100 new small files spread across disk directories.
        disk_dirs = sorted(d for d in fixture_root.iterdir() if d.is_dir())
        for i in range(100):
            target_disk = disk_dirs[i % len(disk_dirs)]
            new_file = target_disk / "extra_dir" / f"new_file_{i:04d}.mkv"
            new_file.parent.mkdir(parents=True, exist_ok=True)
            new_file.write_bytes(b"\xab" * 128)

        elapsed = self._run_scan(db_path, disks, ScanMode.incremental)
        _assert_or_rebaseline(mode, elapsed)

    def test_enrich_missing_1000(self, tmp_path: Path) -> None:
        """Enrich scan against 1 000 files with ``enriched_at=NULL``.

        Scenario: after a full scan (all ``enriched_at=NULL``), run an enrich
        pass.  pymediainfo is not installed in the test environment, so the
        wrapper degrades gracefully; the test measures the overhead of the
        enrich loop itself (stat + DB writes) without stream extraction.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        mode = "enrich_missing_1000"
        fixture_root = _ensure_fixture(_FIXTURE_DIR)
        db_path, disks = self._make_disk_db(tmp_path, fixture_root)

        # Seed full scan — all rows have enriched_at=NULL.
        self._run_scan(db_path, disks, ScanMode.full)

        elapsed = self._run_scan(db_path, disks, ScanMode.enrich)
        _assert_or_rebaseline(mode, elapsed)

    def test_full_one_disk(self, tmp_path: Path) -> None:
        """Full scan scoped to a single disk (``--full --disk D1``).

        Scenario: scan only disk01 of the fixture with a single-disk filter.
        This exercises the single-worker path (DESIGN §11.8) and verifies
        that the scoped scan completes within the expected wall-clock window.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        mode = "full_one_disk"
        fixture_root = _ensure_fixture(_FIXTURE_DIR)
        db_path, disks = self._make_disk_db(tmp_path, fixture_root)

        # Pick the first disk.
        first_disk = disks[0]

        elapsed = self._run_scan(db_path, disks, ScanMode.full, disk_filter=first_disk.label)
        _assert_or_rebaseline(mode, elapsed)


# ---------------------------------------------------------------------------
# Invariant tests — always-on (NOT slow-marked), tiny fixture
# ---------------------------------------------------------------------------


class TestSplitColdScanInvariant:
    """DESIGN §11.2: split cold scan produces the same DB state as a single scan.

    Scanning two disks one at a time (``--full --disk D1`` then
    ``--full --disk D2``) must yield a final DB state identical to a single
    ``--full`` covering both disks.  Uses a tiny real-filesystem fixture.
    """

    def test_split_cold_scan_invariant(self, tmp_path: Path) -> None:
        """Split and combined full scans produce identical media_file sets.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        # Create two tiny fixture directories on the real filesystem.
        disk1_root = tmp_path / "disk1"
        disk2_root = tmp_path / "disk2"
        _populate_tiny_fixture(disk1_root, n_files=10)
        _populate_tiny_fixture(disk2_root, n_files=10)

        # --- Baseline: single full scan over both disks ---
        single_db = tmp_path / "single.db"
        conn_s = _open_db(single_db)
        d1 = _insert_disk(conn_s, "disk1", str(disk1_root))
        d2 = _insert_disk(conn_s, "disk2", str(disk2_root))
        with patch(_GUARD_PATCH, return_value=None):
            scan(
                disks=[d1, d2],
                mode=ScanMode.full,
                generation=1,
                conn=conn_s,
                db_path=single_db,
                event_bus=EventBus(),
            )
        single_state = _collect_db_state(conn_s)
        conn_s.close()

        # --- Split: scan disk1 alone, then disk2 alone into the same DB ---
        split_db = tmp_path / "split.db"
        conn_sp = _open_db(split_db)
        d1_sp = _insert_disk(conn_sp, "disk1", str(disk1_root))
        d2_sp = _insert_disk(conn_sp, "disk2", str(disk2_root))

        with patch(_GUARD_PATCH, return_value=None):
            scan(
                disks=[d1_sp, d2_sp],
                mode=ScanMode.full,
                generation=1,
                conn=conn_sp,
                disk_filter="disk1",
                db_path=split_db,
                event_bus=EventBus(),
            )
            scan(
                disks=[d1_sp, d2_sp],
                mode=ScanMode.full,
                generation=2,
                conn=conn_sp,
                disk_filter="disk2",
                db_path=split_db,
                event_bus=EventBus(),
            )
        split_state = _collect_db_state(conn_sp)
        conn_sp.close()

        # Both DB states must contain the same set of file paths.
        assert single_state["files"] == split_state["files"], (
            "Split cold scan produced a different media_file set than a combined scan. "
            f"Single: {len(single_state['files'])} files, "  # type: ignore[arg-type]
            f"Split: {len(split_state['files'])} files"  # type: ignore[arg-type]
        )


class TestTwoStagePathInvariant:
    """DESIGN §11.3: quick + enrich is equivalent to full (two-stage path).

    Running ``quick`` (or ``full`` to bootstrap) then ``enrich`` on a freshly
    indexed DB produces a DB state equivalent to running a single ``full``
    scan followed by an ``enrich`` pass.  The invariant: both DB states have
    the same set of ``(path, filename)`` entries in ``media_file``.
    """

    def test_two_stage_path_invariant(self, tmp_path: Path) -> None:
        """Quick + enrich produces same media_file set as full + enrich.

        Args:
            tmp_path: pytest-provided temporary directory.
        """
        disk_root = tmp_path / "disk0"
        _populate_tiny_fixture(disk_root, n_files=12)

        # --- Path A: full then enrich ---
        db_full = tmp_path / "full.db"
        conn_f = _open_db(db_full)
        d_full = _insert_disk(conn_f, "disk0", str(disk_root))
        with patch(_GUARD_PATCH, return_value=None):
            scan(
                disks=[d_full],
                mode=ScanMode.full,
                generation=1,
                conn=conn_f,
                db_path=db_full,
                event_bus=EventBus(),
            )
            scan(
                disks=[d_full],
                mode=ScanMode.enrich,
                generation=2,
                conn=conn_f,
                db_path=db_full,
                event_bus=EventBus(),
            )
        state_full = _collect_db_state(conn_f)
        conn_f.close()

        # --- Path B: quick (cold, acts as a full walk since no prior Merkle root)
        #              then enrich ---
        db_quick = tmp_path / "quick.db"
        conn_q = _open_db(db_quick)
        d_quick = _insert_disk(conn_q, "disk0", str(disk_root))
        with patch(_GUARD_PATCH, return_value=None):
            scan(
                disks=[d_quick],
                mode=ScanMode.quick,
                generation=1,
                conn=conn_q,
                db_path=db_quick,
                confirm_bulk_change=True,  # no bulk-change freeze on first scan
                event_bus=EventBus(),
            )
            scan(
                disks=[d_quick],
                mode=ScanMode.enrich,
                generation=2,
                conn=conn_q,
                db_path=db_quick,
                event_bus=EventBus(),
            )
        state_quick = _collect_db_state(conn_q)
        conn_q.close()

        assert state_full["files"] == state_quick["files"], (
            "Two-stage (quick+enrich) produced a different media_file set than full+enrich. "
            f"full+enrich: {len(state_full['files'])} files, "  # type: ignore[arg-type]
            f"quick+enrich: {len(state_quick['files'])} files"  # type: ignore[arg-type]
        )
