"""E2E tests for ``personalscraper library-relink`` — CLI-level harness.

Validates release_id rebinding for media_file rows with NULL release_id.
Dry-run-by-default: the default invocation must NEVER write to the database.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    json_from_result,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _seed_null_release_files(
    db_path: Path,
    mount: Path,
    rel_path: str,
    filename: str,
    item_title: str,
    count: int = 1,
) -> None:
    """Seed DB rows + real files so ``link_file_to_release`` can resolve them.

    Creates the directory *mount / rel_path*, writes a dummy file, and inserts
    a media_item (title match strategy), disk, path, and media_file row(s) with
    ``release_id=NULL``.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())

    # Create real directory and file.
    dir_path = mount / rel_path
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    file_path.write_bytes(b"fake video content for relink test")

    # Disk row.
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        ("uuid-relink", "RelinkDisk", str(mount), now),
    )
    disk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Media item — title match strategy (strategy 2 in find_item_for_path).
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
        "VALUES ('movie', ?, ?, 'movies', ?, ?)",
        (item_title, item_title, now, now),
    )
    conn.execute("SELECT last_insert_rowid()").fetchone()  # item_id consumed by release linker later

    # Path row.
    conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, ?)",
        (disk_id, rel_path, int(dir_path.stat().st_mtime_ns)),
    )
    path_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # media_file rows with NULL release_id.
    for i in range(count):
        suffix = f"_{i}" if count > 1 else ""
        fname = f"{Path(filename).stem}{suffix}{Path(filename).suffix}"
        fpath = dir_path / fname
        fpath.write_bytes(b"test content")
        conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns, "
            "oshash, scan_generation, last_verified_at, enriched_at, deleted_at) "
            "VALUES (NULL, ?, ?, ?, ?, ?, NULL, 1, ?, NULL, NULL)",
            (path_id, fname, fpath.stat().st_size, int(fpath.stat().st_mtime_ns), now, now),
        )

    conn.commit()
    conn.close()


# ── 1. Smoke ─────────────────────────────────────────────────────────────────────


def test_relink_help_exits_zero(test_config) -> None:
    """``library-relink --help`` exits 0."""
    result = run_cli(["library-relink", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-relink" in result.output


# ── 2. Empty DB / zero orphans ──────────────────────────────────────────────────


def test_relink_empty_db_zero_files(tmp_path, test_config) -> None:
    """Empty DB → 'No orphan media_file rows', exit 0."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-relink"])

    assert result.exit_code == 0, result.output
    assert "nothing to relink" in result.output


# ── 3. Dry-run safety (CRITICAL) ────────────────────────────────────────────────


def test_relink_dry_run_no_writes(tmp_path, test_config) -> None:
    """Default invocation (no ``--apply``) MUST NOT write release_id to the DB.

    Seeds a single linkable file with ``release_id=NULL``.  Asserts that the
    DRY-RUN message appears AND that the database row still has NULL after.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "mount"
    mount.mkdir()
    _seed_null_release_files(db_path, mount, "TestMovie", "test.mkv", "TestMovie")

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-relink"])

    assert result.exit_code == 0, result.output
    clean = result.output
    assert "DRY-RUN" in clean, f"Expected DRY-RUN marker, got: {clean}"
    assert "No orphan" not in clean, f"Should have found orphan files, got: {clean}"

    # Verify release_id is still NULL.
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT release_id FROM media_file LIMIT 1").fetchone()
    conn.close()
    assert row is not None and row[0] is None, f"DRY-RUN leaked write: release_id={row[0]}"


# ── 4. Apply mode ───────────────────────────────────────────────────────────────


def test_relink_apply_persists_link_updates(tmp_path, test_config) -> None:
    """``--apply`` writes non-NULL release_id for linkable files."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "mount"
    mount.mkdir()
    _seed_null_release_files(db_path, mount, "TestMovie", "test.mkv", "TestMovie")

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-relink", "--apply"])

    assert result.exit_code == 0, result.output
    assert "Applied:" in result.output, result.output

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT release_id FROM media_file LIMIT 1").fetchone()
    conn.close()
    assert row is not None and row[0] is not None, f"--apply did not persist: release_id={row[0]}"


def test_relink_apply_mutually_exclusive_with_dry_run(tmp_path, test_config) -> None:
    """Passing both ``--apply`` and ``--dry-run`` exits non-zero."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-relink", "--apply", "--dry-run"])

    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}: {result.output}"
    assert "mutually exclusive" in result.output.lower(), result.output


# ── 5. Unmatched files ──────────────────────────────────────────────────────────


def test_relink_reports_unmatched_files(tmp_path, test_config) -> None:
    """File whose parent directory resolves to no item → counted as unmatched.

    The directory name does not match any media_item title, and no
    dispatch_path / title-year strategy finds a match.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "mount"
    mount.mkdir()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())

    dir_path = mount / "NoSuchItem"
    dir_path.mkdir()
    file_path = dir_path / "orphan.mkv"
    file_path.write_bytes(b"test content")

    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES ('uuid-unmatched', 'UnmatchedDisk', ?, ?, 1, 0)",
        (str(mount), now),
    )
    conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (1, 'NoSuchItem', ?)",
        (int(dir_path.stat().st_mtime_ns),),
    )
    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns, "
        "oshash, scan_generation, last_verified_at, enriched_at, deleted_at) "
        "VALUES (NULL, 1, 'orphan.mkv', ?, ?, ?, NULL, 1, ?, NULL, NULL)",
        (file_path.stat().st_size, int(file_path.stat().st_mtime_ns), now, now),
    )
    conn.commit()
    conn.close()

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-relink"])

    assert result.exit_code == 0, result.output
    clean = result.output
    assert "DRY-RUN" in clean, result.output
    assert "unmatched=1" in clean, f"Expected unmatched=1, got: {clean}"


# ── 6. Errors ──


def test_relink_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-relink", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_relink_config_absent_exits_gracefully(monkeypatch) -> None:
    """load_config raises ConfigNotFoundError → friendly error, no traceback."""
    from personalscraper.conf.loader import ConfigNotFoundError

    def _raise(*_a, **_kw):
        raise ConfigNotFoundError("no config found")

    monkeypatch.setattr("personalscraper.conf.loader.load_config", _raise)
    result = run_cli(["library-relink"])
    assert result.exit_code != 0
    assert "error" in result.output.lower() or "config" in result.output.lower()
    assert_no_python_traceback(result)


def test_relink_corrupt_db_exits_gracefully(tmp_path, test_config) -> None:
    """Corrupt (non-SQLite) DB file → graceful exit, no Python traceback."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_text("this is not a sqlite database")
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-relink"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


# ── 7. Output ──


def test_relink_output_no_traceback(tmp_path, test_config) -> None:
    """Output is Rich-formatted, never a Python traceback."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-relink"])
    assert result.exit_code == 0
    assert_no_python_traceback(result)


def test_relink_error_exits_nonzero(monkeypatch) -> None:
    """Config error → non-zero exit code."""
    from personalscraper.conf.loader import ConfigNotFoundError

    def _raise(*_a, **_kw):
        raise ConfigNotFoundError("no config found")

    monkeypatch.setattr("personalscraper.conf.loader.load_config", _raise)
    result = run_cli(["library-relink"])
    assert result.exit_code != 0


# ── 8. Events ──

# N/A: ``library-relink`` uses a raw ``sqlite3.connect`` call directly — no
# EventBus is created or injected.  Output is Rich console text via
# ``console.print``.  No domain event is published.


# ── 9. Idempotence ──


def test_relink_idempotent_second_run_noop(tmp_path, test_config) -> None:
    """Running ``--apply`` twice: second run finds nothing to link.

    After the first --apply, all linkable media_file rows have non-NULL
    release_id.  A second --apply must report "nothing to relink" with
    exit code 0.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "mount"
    mount.mkdir()
    _seed_null_release_files(db_path, mount, "TestMovie", "test.mkv", "TestMovie")

    # First run: apply the link.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["library-relink", "--apply"])
    assert r1.exit_code == 0, r1.output
    assert "Applied:" in r1.output, r1.output

    # Verify release_id is now non-NULL.
    conn = sqlite3.connect(str(db_path))
    release_id = conn.execute("SELECT release_id FROM media_file LIMIT 1").fetchone()[0]
    conn.close()
    assert release_id is not None, f"release_id should be set after first --apply, got {release_id}"

    # Second run: nothing left to link.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r2 = run_cli(["library-relink", "--apply"])
    assert r2.exit_code == 0, r2.output
    assert "No orphan" in r2.output, f"Second run should find nothing: {r2.output}"


# ── 10. Closure-of-loop ──


def test_relink_apply_then_reconcile_zero_orphans(tmp_path, test_config) -> None:
    """After ``relink --apply``, ``reconcile --enqueue-repairs`` reports 0 orphan files.

    Cross-command closure: relink binds NULL release_id rows, and reconcile's
    ``detect_files_without_release`` must confirm the binding is complete.
    Verifies the broader "no file left behind" invariant end-to-end.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    mount = tmp_path / "mount"
    mount.mkdir()
    _seed_null_release_files(db_path, mount, "TestMovie", "test.mkv", "TestMovie")

    # Step 1: link the orphan files.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r1 = run_cli(["library-relink", "--apply"])
    assert r1.exit_code == 0, r1.output
    assert "Applied:" in r1.output, r1.output

    # Step 2: reconcile must report zero files_without_release.
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        r2 = run_cli(["--format", "json", "library-reconcile", "--enqueue-repairs"])
    assert r2.exit_code == 0, r2.output
    payload = json_from_result(r2)
    assert payload["files_without_release"] == 0, (
        f"Cross-command closure broken: {payload['files_without_release']} files still without release after relink"
    )


# ── Span repair (pass 2, migration 014) ─────────────────────────────────────────


def _seed_linked_span_file_without_end(db_path: Path, mount: Path) -> None:
    """Seed a show whose S09E23-24 file is linked to a pre-014 release (no end)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())

    season_dir = mount / "series" / "Friends (1994)" / "Saison 09"
    season_dir.mkdir(parents=True)
    fname = "S09E23-24 - Barbade.mkv"
    (season_dir / fname).write_bytes(b"span content")

    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES ('uuid-span', 'SpanDisk', ?, ?, 1, 0)",
        (str(mount), now),
    )
    disk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
        "VALUES ('show', 'Friends', 'Friends', 'tv_shows', ?, ?)",
        (now, now),
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("INSERT INTO season (item_id, number) VALUES (?, 9)", (item_id,))
    season_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("INSERT INTO episode (season_id, number) VALUES (?, 23)", (season_id,))
    e23 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    # Pre-014 shape: release linked to the FIRST episode only, no span end.
    conn.execute("INSERT INTO media_release (episode_id) VALUES (?)", (e23,))
    release_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, 'series/Friends (1994)/Saison 09', 1)",
        (disk_id,),
    )
    path_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, "
        "oshash, scan_generation, last_verified_at) VALUES (?, ?, ?, 100, 1, 'abcd', 1, ?)",
        (release_id, path_id, fname, now),
    )
    conn.commit()
    conn.close()


def test_relink_span_repair_upgrades_pre_014_release(tmp_path, test_config) -> None:
    """Pass 2 sets episode_end_id and creates the covered episode row.

    Live incident (2026-07-15): « Friends S09E23-24 » linked pre-migration-014
    owned only E23 — the wanted row for E24 stayed pending forever.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    mount = tmp_path / "mount"
    mount.mkdir()
    _seed_linked_span_file_without_end(db_path, mount)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-relink", "--apply"])

    assert result.exit_code == 0, result.output
    assert "span_repaired=1" in result.output, result.output

    conn = sqlite3.connect(str(db_path))
    end_num = conn.execute(
        "SELECT e.number FROM media_release mr JOIN episode e ON e.id = mr.episode_end_id "
        "WHERE mr.episode_end_id IS NOT NULL"
    ).fetchone()
    numbers = [r[0] for r in conn.execute("SELECT number FROM episode ORDER BY number")]
    conn.close()
    assert end_num is not None and end_num[0] == 24, "release must gain the span end"
    assert numbers == [23, 24], f"the covered episode row must exist, got {numbers}"


def test_relink_span_repair_is_idempotent(tmp_path, test_config) -> None:
    """A second --apply run finds nothing left to span-repair."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    mount = tmp_path / "mount"
    mount.mkdir()
    _seed_linked_span_file_without_end(db_path, mount)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        first = run_cli(["library-relink", "--apply"])
        second = run_cli(["library-relink", "--apply"])

    assert first.exit_code == 0 and second.exit_code == 0
    assert "span_repaired=1" in first.output
    assert "span_repaired=0" in second.output, second.output
