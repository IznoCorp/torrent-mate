"""E2E tests: drift mechanism — miss-strike lifecycle (MUST-17) and CLI wiring (DEV #18).

MUST-17 / BD-B — ``test_miss_strike_lifecycle_on_deleted_file`` exercises the full
miss-strike lifecycle using a **real filesystem** and a **file-based SQLite DB**:

1. A file exists on disk; a ``media_file`` row is seeded at ``scan_generation=1``.
2. The file is deleted from the filesystem.
3. N successive simulated scans call ``mark_missed_files(conn, disk_id, generation)``
   with increasing generation values (the file is absent so its generation does not
   advance via ``reconcile_file``).  After each call, ``miss_strikes`` is asserted to
   have incremented by 1.
4. Once ``miss_strikes`` reaches the configured threshold, ``apply_soft_deletes`` is
   called and the row is asserted to have ``deleted_at NOT NULL`` with a matching
   tombstone in ``deleted_item``.

This complements the spy-based tests below (DEV #18) which verify the *CLI wiring*
(``mark_missed_files`` called from ``library_index_command``).  The lifecycle test
validates the *data contract*: that the DB state progressively reflects the absences
and that the soft-delete fires at the correct threshold.

DEV #18 — pre tech-debt 0.16.0, ``personalscraper.indexer.drift.mark_missed_files``
was defined but NEVER called from production code (only from unit tests in
``tests/indexer/test_drift.py``). The function increments ``miss_strikes`` on
``media_file`` rows for files that were not visited by the current scan
generation. Without a production caller, ``miss_strikes`` stayed at 0
indefinitely, so ``apply_soft_deletes`` (which filters by
``miss_strikes >= n_strikes_for_softdelete``) could never tombstone anything.

Phase 1.1 of tech-debt 0.16.0 wires ``mark_missed_files`` into
``library_index_command`` (``personalscraper/indexer/commands/scan.py``) so the
drift mechanism becomes operational. This file pins the regression: the CLI
flow must invoke ``mark_missed_files`` once per visited disk when running in
``full`` mode and not in ``--dry-run``.

The test uses the existing ``test_cli.py`` harness pattern (CliRunner +
patched config + mocked scanner.scan for speed) and spies on
``mark_missed_files`` to assert it was called.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.cli import app
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.drift import apply_soft_deletes, mark_missed_files
from personalscraper.indexer.scanner import ScanRunResult
from tests.conftest import make_cli_runner

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_SCAN = "personalscraper.indexer.scanner.scan"

runner = make_cli_runner()


def _make_config(tmp_path: Path) -> Any:
    """Build a minimal Config whose ``indexer.db_path`` lives under *tmp_path*.

    Mirrors ``tests/indexer/test_cli.py::_make_config`` but kept private here
    to avoid coupling test_drift_e2e.py to a sibling test file's private helper.
    """
    from personalscraper.conf.models.indexer import IndexerConfig

    mock_cfg = MagicMock()
    ic = IndexerConfig(db_path=tmp_path / "library.db")
    mock_cfg.indexer = ic
    mock_cfg.paths.staging_dir = tmp_path / "staging"
    mock_cfg.all_category_ids = frozenset({"movies", "tv_shows", "anime", "standup"})
    # No torrent client configured (DESIGN D9): keep ``torrent.active`` falsey
    # so the boot fail-fast in _build_app_context does not trip.
    mock_cfg.torrent.active = ""
    return mock_cfg


def _make_conn(db_path: Path) -> sqlite3.Connection:
    """Open a real file-based SQLite DB with all migrations applied."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _fake_scan_result(scan_run_id: int = 1, files: int = 0, dirs: int = 0) -> ScanRunResult:
    """Synthetic scan result that lets the CLI proceed to post-walk steps."""
    return ScanRunResult(
        scan_run_id=scan_run_id,
        files_visited=files,
        dirs_visited=dirs,
        status="ok",
        disks_skipped=0,
    )


# ---------------------------------------------------------------------------
# MUST-17 / BD-B — Miss-strike lifecycle (real FS, real DB)
# ---------------------------------------------------------------------------


def test_miss_strike_lifecycle_on_deleted_file(tmp_path: Path) -> None:
    """Miss-strike progression + soft-delete on real FS deletion (MUST-17 / BD-B).

    This test exercises the full drift lifecycle using a real filesystem and a
    file-based SQLite DB, validating the *data contract* end-to-end:

    Phase A — setup (file present):
      A real media file exists in *tmp_path*.  A ``disk``, ``path``, and
      ``media_file`` row are seeded at ``scan_generation=1`` mirroring what the
      scanner would have written after first seeing the file.

    Phase B — deletion:
      The real file is deleted from the filesystem.  The DB row is unchanged
      (``miss_strikes=0``, ``deleted_at=NULL``).

    Phase C — N successive missed scans:
      ``mark_missed_files(conn, disk_id, generation)`` is called N times with
      generations 2 … N+1.  Because the file's DB row stays at
      ``scan_generation=1`` (no ``reconcile_file`` call — the file is absent),
      every call increments ``miss_strikes`` by 1.  After each call the value is
      asserted so the progression is pinned row by row.

    Phase D — soft-delete at threshold:
      After N strikes, ``apply_soft_deletes(conn, disk_id, n_strikes=N)`` is
      called.  The ``media_file`` row must have ``deleted_at NOT NULL`` and a
      corresponding ``deleted_item`` tombstone must exist with ``reason='n_strikes'``.

    Phase E — idempotence guard:
      A second call to ``apply_soft_deletes`` returns 0 (already deleted, row is
      excluded by the ``deleted_at IS NULL`` filter in the query).

    Args:
        tmp_path: Pytest-provided temporary directory (unique per test run).
    """
    n_strikes_threshold = 3  # threshold used by apply_soft_deletes

    # ---- Phase A: setup — real file + seeded DB rows ----

    mount_dir = tmp_path / "disk1"
    mount_dir.mkdir()
    media_file_path = mount_dir / "movie.mkv"
    media_file_path.write_bytes(b"\x00" * 1024)  # 1 KiB placeholder

    db_path = tmp_path / "library.db"
    conn = _make_conn(db_path)

    # Seed disk row (mount_path must match the real temp directory so that
    # mark_missed_files path resolution would succeed if it needed to walk FS).
    disk_cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("lifecycle-uuid", "LifecycleDisk", str(mount_dir), int(time.time()), None, 1, 0),
    )
    disk_id: int = disk_cursor.lastrowid  # type: ignore[assignment]

    # Seed path row (rel_path="" = root of the disk mount).
    path_cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
        (disk_id, ""),
    )
    path_id: int = path_cursor.lastrowid  # type: ignore[assignment]

    # Seed media_file row at generation=1 (as if the scanner had visited it once).
    st = media_file_path.stat()
    conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (NULL, ?, ?, ?, ?, ?, NULL, NULL, NULL, 1, 0, NULL, 0, NULL)
        """,
        (path_id, "movie.mkv", st.st_size, st.st_mtime_ns, st.st_ctime_ns),
    )
    file_cursor = conn.execute("SELECT last_insert_rowid()")
    file_id: int = file_cursor.fetchone()[0]
    conn.commit()

    # Sanity: row is present, strikes at 0, not deleted.
    row = conn.execute("SELECT miss_strikes, deleted_at FROM media_file WHERE id = ?", (file_id,)).fetchone()
    assert row is not None
    assert row[0] == 0, f"Initial miss_strikes must be 0, got {row[0]}"
    assert row[1] is None, "Initial deleted_at must be NULL"

    # ---- Phase B: delete the real file ----
    media_file_path.unlink()
    assert not media_file_path.exists(), "File must be gone from filesystem"

    # ---- Phase C: N successive missed scans → miss_strikes progression ----
    # Each call uses a generation strictly greater than 1 (the file's stored
    # scan_generation), so the file is treated as missed every time.
    for scan_number in range(1, n_strikes_threshold + 1):
        current_generation = 1 + scan_number  # 2, 3, 4

        count = mark_missed_files(conn, disk_id=disk_id, current_generation=current_generation)
        assert count == 1, (
            f"Scan {scan_number}: mark_missed_files must report 1 incremented row (1 absent file), got {count}"
        )

        row = conn.execute("SELECT miss_strikes FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert row is not None
        assert row[0] == scan_number, (
            f"After scan {scan_number}: expected miss_strikes={scan_number}, got {row[0]}. "
            f"miss_strikes must increment by 1 per missed scan."
        )

    # At this point miss_strikes == n_strikes_threshold but deleted_at is still NULL
    # (apply_soft_deletes has not been called yet).
    pre_delete_row = conn.execute("SELECT miss_strikes, deleted_at FROM media_file WHERE id = ?", (file_id,)).fetchone()
    assert pre_delete_row is not None
    assert pre_delete_row[0] == n_strikes_threshold, (
        f"Expected miss_strikes={n_strikes_threshold} before soft-delete, got {pre_delete_row[0]}"
    )
    assert pre_delete_row[1] is None, "deleted_at must still be NULL before apply_soft_deletes is called"

    # ---- Phase D: soft-delete at threshold ----
    deleted_count = apply_soft_deletes(conn, disk_id=disk_id, n_strikes_for_softdelete=n_strikes_threshold)
    assert deleted_count == 1, (
        f"apply_soft_deletes must report 1 row soft-deleted at threshold "
        f"n_strikes={n_strikes_threshold}, got {deleted_count}"
    )

    post_delete_row = conn.execute(
        "SELECT miss_strikes, deleted_at FROM media_file WHERE id = ?", (file_id,)
    ).fetchone()
    assert post_delete_row is not None
    assert post_delete_row[1] is not None, (
        "deleted_at must be set (NOT NULL) after apply_soft_deletes reaches threshold"
    )
    assert isinstance(post_delete_row[1], int), (
        f"deleted_at must be an integer epoch-seconds timestamp, got {type(post_delete_row[1])}"
    )
    assert post_delete_row[1] > 0, f"deleted_at must be a positive timestamp, got {post_delete_row[1]}"

    # Verify tombstone inserted into deleted_item.
    tombstone = conn.execute(
        "SELECT kind, original_id, reason FROM deleted_item WHERE original_id = ?",
        (file_id,),
    ).fetchone()
    assert tombstone is not None, f"A deleted_item tombstone must exist for file_id={file_id} after soft-delete"
    assert tombstone[0] == "file", f"Tombstone kind must be 'file', got {tombstone[0]!r}"
    assert tombstone[1] == file_id, f"Tombstone original_id must match file_id={file_id}"
    assert tombstone[2] == "n_strikes", f"Tombstone reason must be 'n_strikes', got {tombstone[2]!r}"

    # ---- Phase E: idempotence guard ----
    # A second apply_soft_deletes call must return 0: the row is already deleted
    # (deleted_at IS NOT NULL), so it is excluded by the query filter.
    second_count = apply_soft_deletes(conn, disk_id=disk_id, n_strikes_for_softdelete=n_strikes_threshold)
    assert second_count == 0, (
        f"Second apply_soft_deletes must return 0 (already deleted, excluded by "
        f"deleted_at IS NULL filter), got {second_count}"
    )

    conn.close()


# ---------------------------------------------------------------------------
# DEV #18 — CLI wiring: mark_missed_files invoked from library_index_command
# ---------------------------------------------------------------------------


def test_library_index_full_mode_invokes_mark_missed_files(tmp_path: Path) -> None:
    """library-index --mode full DOIT appeler mark_missed_files par disk (DEV #18).

    Sans le fix Phase 1.1, mark_missed_files n'est jamais appelé depuis le
    flow CLI → miss_strikes reste à 0 pour les fichiers absents → apply_soft_deletes
    ne tombstone jamais. Ce test passe APRÈS le fix : mark_missed_files est
    invoqué une fois par disk visité (full mode only).
    """
    cfg = _make_config(tmp_path)
    db_path: Path = cfg.indexer.db_path
    conn = _make_conn(db_path)
    # Seed 2 disks so we can assert N calls = N disks
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk1-uuid", "Disk1", None, int(time.time()), None, 0, 0),
    )
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk2-uuid", "Disk2", None, int(time.time()), None, 0, 0),
    )
    conn.close()

    fake_result = _fake_scan_result(scan_run_id=1)

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_SCAN, return_value=fake_result),
        patch("personalscraper.indexer.drift.mark_missed_files", return_value=0) as spy,
    ):
        result = runner.invoke(app, ["library-index", "--mode", "full"])

    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
    assert spy.call_count == 2, (
        f"mark_missed_files must be called once per visited disk in full mode "
        f"(2 disks seeded → expected 2 calls, got {spy.call_count}). "
        f"This pins the DEV #18 fix wired in Phase 1.1."
    )
    # Verify args : (conn, disk_id, current_generation). Generations match next_gen=1.
    for call in spy.call_args_list:
        args, kwargs = call
        # mark_missed_files(conn, disk_id, current_generation) — positional or kw
        if kwargs:
            assert "disk_id" in kwargs or len(args) >= 2
            gen = kwargs.get("current_generation") or (args[2] if len(args) >= 3 else None)
        else:
            assert len(args) == 3, f"Expected 3 positional args, got {len(args)}: {args}"
            gen = args[2]
        assert gen == 1, f"Expected current_generation=1 (next_gen for empty DB), got {gen}"


def test_library_index_dry_run_does_not_invoke_mark_missed_files(tmp_path: Path) -> None:
    """--dry-run skips mark_missed_files (no mutation in dry-run by contract).

    The drift mechanism is a write operation. Dry-run mode must NEVER mutate
    miss_strikes — otherwise re-running the same dry-run twice would accumulate
    state, breaking dry-run idempotence.
    """
    cfg = _make_config(tmp_path)
    db_path: Path = cfg.indexer.db_path
    conn = _make_conn(db_path)
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk1-uuid", "Disk1", None, int(time.time()), None, 0, 0),
    )
    conn.close()

    fake_result = _fake_scan_result(scan_run_id=2)

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_SCAN, return_value=fake_result),
        patch("personalscraper.indexer.drift.mark_missed_files", return_value=0) as spy,
    ):
        result = runner.invoke(app, ["library-index", "--mode", "full", "--dry-run"])

    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
    assert spy.call_count == 0, (
        f"mark_missed_files must NOT be called in dry-run mode "
        f"(would mutate miss_strikes outside transaction). Got {spy.call_count} calls."
    )


def test_library_index_quick_mode_does_not_invoke_mark_missed_files(tmp_path: Path) -> None:
    """Quick mode skips mark_missed_files (no full walk → no accumulated strikes).

    Mark_missed_files compares scan_generation per file against the current
    generation. Quick mode uses Merkle short-circuit and does NOT visit every
    file, so bumping miss_strikes universally would incorrectly strike all
    unvisited files. Only full mode warrants the drift bump (matches plan
    Phase 1.1 conditions ``scan_mode in (ScanMode.full,)``).
    """
    cfg = _make_config(tmp_path)
    db_path: Path = cfg.indexer.db_path
    conn = _make_conn(db_path)
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk1-uuid", "Disk1", None, int(time.time()), None, 0, 0),
    )
    conn.close()

    fake_result = _fake_scan_result(scan_run_id=3)

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_SCAN, return_value=fake_result),
        patch("personalscraper.indexer.drift.mark_missed_files", return_value=0) as spy,
    ):
        result = runner.invoke(app, ["library-index", "--mode", "quick"])

    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
    assert spy.call_count == 0, (
        f"mark_missed_files must NOT be called in quick mode "
        f"(no full walk → strikes would be wrong). Got {spy.call_count} calls."
    )
