"""``miss_strikes`` must be a CONSECUTIVE counter, as everything that reads it assumes.

Three strikes tombstone a file. Both the schema docstring
(``miss_strikes: Consecutive scans where this file was not found on disk``) and
``docs/production/indexer.md`` (*"The counter is reset to 0 the moment the file is
observed again"*) describe a counter that a sighting clears — and nothing cleared
it — except on a rename, where ``detect_rename`` has always reset it.
``reset_strikes_on_reappearance`` exists and is tested but is reachable only
through ``reconcile_file``, which has no production caller; the scanner's own
upsert listed ``miss_strikes`` among the columns it *intentionally preserved* on
conflict.

So the counter was a LIFETIME total: three separate absences, months apart, with
complete scans in between that saw the file every time, still tombstone it.

That is not hypothetical. On 2026-06-30 the operator's disk_1 accumulated three
strikes from three truncated runs (scan_run 83, 85, 89) and 49 553 rows were
tombstoned — while scan_run 87, a COMPLETE 49 476-file walk, sat between the
second and the third and cleared nothing.

A sighting reaches the database by THREE different writes, and the tests below
cover each, because a reset on some of them is not a reset:

- ``_upsert_file_row`` — quick mode, the ``_walk_dir`` fallback, and incremental's
  new-file branch;
- ``_flush_insert_buffer`` — full mode, which always batches;
- ``IncrementalVisitor.visit_file``'s own four ``UPDATE media_file SET …``
  statements, taken whenever incremental meets a file it already has a row for.

That third one is the one that matters most in practice: incremental is the mode
``post_maintenance`` runs after EVERY dispatch, and ``apply_soft_deletes`` runs
in incremental mode too.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.drift import apply_soft_deletes, mark_missed_files
from personalscraper.indexer.scanner._db_writes import _flush_insert_buffer, _upsert_file_row

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _seed(conn: sqlite3.Connection, *, strikes: int = 0, deleted_at: int | None = None) -> tuple[int, int, int]:
    """Insert disk → path → media_file carrying *strikes*; return their ids."""
    now = int(time.time())
    disk_id: int = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES ('uuid-strike', 'StrikeDisk', '/mnt/strike', ?, 1, 0)",
        (now,),
    ).lastrowid  # type: ignore[assignment]
    path_id: int = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, 'films/Movie (2020)')",
        (disk_id,),
    ).lastrowid  # type: ignore[assignment]
    file_id: int = conn.execute(
        "INSERT INTO media_file ("
        " release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,"
        " oshash, xxh3_partial, xxh3_full, scan_generation,"
        " last_verified_at, enriched_at, miss_strikes, deleted_at"
        ") VALUES (NULL, ?, 'Movie.mkv', 1024, ?, NULL, NULL, NULL, NULL, 1, ?, NULL, ?, ?)",
        (path_id, now * 1_000_000_000, now, strikes, deleted_at),
    ).lastrowid  # type: ignore[assignment]
    return disk_id, path_id, file_id


def _walk_the_file(conn: sqlite3.Connection, path_id: int, generation: int) -> None:
    """Do what a scan does when it SEES the file: upsert it at the new generation."""
    _upsert_file_row(
        conn,
        path_id=path_id,
        filename="Movie.mkv",
        size_bytes=1024,
        mtime_ns=int(time.time()) * 1_000_000_000,
        ctime_ns=None,
        generation=generation,
        oshash_value=None,
    )


def test_seeing_a_file_clears_its_strikes() -> None:
    """The sighting IS the reset — that is what both docs promise."""
    conn = _make_conn()
    _disk_id, path_id, file_id = _seed(conn, strikes=2)

    _walk_the_file(conn, path_id, generation=2)

    strikes = conn.execute("SELECT miss_strikes FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]
    assert strikes == 0, f"a walked file must leave the walk with zero strikes, got {strikes}"


def test_the_batched_path_clears_them_too() -> None:
    """``drop_indexes_during_full_scan`` routes the SAME sighting through a different write.

    A guard on one of the two write paths is a guard that depends on a config knob.
    """
    conn = _make_conn()
    _disk_id, path_id, file_id = _seed(conn, strikes=2)

    buffer: list = []
    _upsert_file_row(
        conn,
        path_id=path_id,
        filename="Movie.mkv",
        size_bytes=1024,
        mtime_ns=int(time.time()) * 1_000_000_000,
        ctime_ns=None,
        generation=2,
        oshash_value=None,
        insert_buffer=buffer,
    )
    _flush_insert_buffer(conn, buffer)

    strikes = conn.execute("SELECT miss_strikes FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]
    assert strikes == 0, f"the batched path must reset too, got {strikes}"


def test_a_complete_scan_between_two_misses_breaks_the_chain() -> None:
    """The 2026-06-30 shape, replayed: miss, miss, SIGHTING, miss → never three.

    This is the whole point of a consecutive counter. Before the reset existed the
    same sequence reached three and tombstoned a file that a complete walk had just
    confirmed present.
    """
    conn = _make_conn()
    disk_id, path_id, file_id = _seed(conn)

    mark_missed_files(conn, disk_id, current_generation=2)  # absent
    mark_missed_files(conn, disk_id, current_generation=3)  # absent
    _walk_the_file(conn, path_id, generation=4)  # SEEN — the chain breaks here
    mark_missed_files(conn, disk_id, current_generation=5)  # absent again

    strikes = conn.execute("SELECT miss_strikes FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]
    assert strikes == 1, f"after a sighting the count restarts; expected 1, got {strikes}"

    tombstoned = apply_soft_deletes(conn, disk_id, n_strikes_for_softdelete=3)
    assert tombstoned == 0, "a file seen one scan ago must not be tombstoned"
    deleted_at = conn.execute("SELECT deleted_at FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]
    assert deleted_at is None, "the row must still be live"


def test_three_uninterrupted_misses_still_tombstone() -> None:
    """The guard must not disarm the mechanism: a genuinely absent file still goes."""
    conn = _make_conn()
    disk_id, _path_id, file_id = _seed(conn)

    for generation in (2, 3, 4):
        mark_missed_files(conn, disk_id, current_generation=generation)

    assert apply_soft_deletes(conn, disk_id, n_strikes_for_softdelete=3) == 1
    deleted_at = conn.execute("SELECT deleted_at FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]
    assert deleted_at is not None, "three consecutive misses must still tombstone"


def test_a_sighting_does_NOT_resurrect_a_tombstoned_row() -> None:
    """Deliberately NOT changed: clearing ``deleted_at`` is a different decision.

    ``reset_strikes_on_reappearance`` clears both columns, and restoring tombstoned
    rows in bulk is exactly what the Merkle bulk-change freeze exists to arbitrate.
    This change is about the COUNTER — the half both docs describe and the half that
    can only ever prevent a tombstone, never cause one. Restoration stays where it
    is until someone decides it on purpose.
    """
    conn = _make_conn()
    _disk_id, path_id, file_id = _seed(conn, strikes=3, deleted_at=1_700_000_000)

    _walk_the_file(conn, path_id, generation=2)

    row = conn.execute("SELECT miss_strikes, deleted_at FROM media_file WHERE id = ?", (file_id,)).fetchone()
    assert row["miss_strikes"] == 0, "the counter resets"
    assert row["deleted_at"] == 1_700_000_000, "the tombstone is left exactly as it was"


# ---------------------------------------------------------------------------
# The mode that actually runs on a schedule
# ---------------------------------------------------------------------------
#
# `_upsert_file_row` is NOT where every sighting lands. `IncrementalVisitor`
# routes a file it already has a row for through four raw `UPDATE media_file
# SET …` statements of its own, and touches `miss_strikes` in none of them.
#
# That matters more than the wording: incremental is the mode `post_maintenance`
# runs after EVERY dispatch, and `apply_soft_deletes` runs in incremental mode
# too (commands/scan.py). So the exact failure this module exists to close —
# tombstoning a file the scan just stat'd — stayed reachable on the one mode
# with a schedule, while full and quick were fixed.


def _seed_disk_and_file(
    conn: sqlite3.Connection,
    mount: str,
    *,
    strikes: int,
    stale_tier1: bool,
) -> tuple[Any, int]:
    """Create a real file under *mount* and a row for it carrying *strikes*.

    Args:
        conn: Open SQLite connection.
        mount: Real directory standing in for a disk mount.
        strikes: ``miss_strikes`` to seed on the row.
        stale_tier1: When ``True`` the stored size/mtime deliberately disagree
            with the file on disk, so the visitor takes its drift branches
            instead of the cheap generation-only one.

    Returns:
        ``(disk_row, file_id)``.
    """
    from personalscraper.indexer.repos import disk_repo

    file_path = Path(mount) / "Movie.mkv"
    file_path.write_bytes(b"V" * 4096)
    stat_result = file_path.stat()

    disk_id: int = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, is_mounted, merkle_root, unreachable_strikes) "
        "VALUES ('uuid-inc', 'IncDisk', ?, 1, NULL, 0)",
        (mount,),
    ).lastrowid  # type: ignore[assignment]
    disk_row = disk_repo.get_by_id(conn, disk_id)
    path_id: int = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, '')",
        (disk_id,),
    ).lastrowid  # type: ignore[assignment]
    size = 1 if stale_tier1 else stat_result.st_size
    mtime = 1 if stale_tier1 else stat_result.st_mtime_ns
    file_id: int = conn.execute(
        "INSERT INTO media_file ("
        " release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,"
        " oshash, xxh3_partial, xxh3_full, scan_generation,"
        " last_verified_at, enriched_at, miss_strikes, deleted_at"
        ") VALUES (NULL, ?, 'Movie.mkv', ?, ?, ?, NULL, NULL, NULL, 1, ?, NULL, ?, NULL)",
        (path_id, size, mtime, stat_result.st_ctime_ns, int(time.time()), strikes),
    ).lastrowid  # type: ignore[assignment]
    return disk_row, file_id


def _run_incremental(conn: sqlite3.Connection, disk_row: Any, mount: str) -> None:
    """Drive the REAL incremental walk over *mount*."""
    from unittest.mock import patch as _patch

    from personalscraper.indexer._fs_capability import NTFS_MACFUSE
    from personalscraper.indexer.scanner._modes.incremental import _scan_disk_incremental

    with _patch("personalscraper.indexer.scanner.guard_disk_mounted", return_value=None):
        _scan_disk_incremental(conn, disk_row, mount, [0], [0], 2, [0], False, capability=NTFS_MACFUSE)


def test_an_incremental_scan_clears_strikes_on_an_unchanged_file(tmp_path: Path) -> None:
    """The commonest sighting there is: incremental walks a file nothing changed about."""
    conn = _make_conn()
    mount = str(tmp_path / "mnt")
    Path(mount).mkdir()
    disk_row, file_id = _seed_disk_and_file(conn, mount, strikes=2, stale_tier1=False)

    _run_incremental(conn, disk_row, mount)

    strikes = conn.execute("SELECT miss_strikes FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]
    assert strikes == 0, (
        f"incremental saw the file and left {strikes} strike(s) on it. This is the mode "
        "post-dispatch maintenance runs, and apply_soft_deletes runs in it too."
    )


def test_an_incremental_scan_clears_strikes_on_a_drifted_file(tmp_path: Path) -> None:
    """The other branches: stored tier-1 disagrees, so the visitor recomputes and repairs.

    A file whose metadata drifted is still a file that was SEEN.
    """
    conn = _make_conn()
    mount = str(tmp_path / "mnt")
    Path(mount).mkdir()
    disk_row, file_id = _seed_disk_and_file(conn, mount, strikes=2, stale_tier1=True)

    _run_incremental(conn, disk_row, mount)

    strikes = conn.execute("SELECT miss_strikes FROM media_file WHERE id = ?", (file_id,)).fetchone()[0]
    assert strikes == 0, f"a drifted-but-present file was seen; expected 0 strikes, got {strikes}"


def test_post_dispatch_incremental_cannot_tombstone_a_file_it_just_saw(tmp_path: Path) -> None:
    """End to end, the failure this module exists to close, on the scheduled mode.

    Two strikes standing, the file is on disk, an incremental scan walks it, and
    then ``apply_soft_deletes`` runs — exactly the order ``library_index_command``
    uses for incremental mode.
    """
    conn = _make_conn()
    mount = str(tmp_path / "mnt")
    Path(mount).mkdir()
    disk_row, file_id = _seed_disk_and_file(conn, mount, strikes=2, stale_tier1=False)

    _run_incremental(conn, disk_row, mount)
    mark_missed_files(conn, disk_row.id, current_generation=3)
    tombstoned = apply_soft_deletes(conn, disk_row.id, n_strikes_for_softdelete=3)

    assert tombstoned == 0, "a file walked one generation ago must not be tombstoned"
    # ``apply_soft_deletes`` resets ``conn.row_factory`` to None on its way out,
    # so read positionally rather than by name.
    strikes, deleted_at = conn.execute(
        "SELECT miss_strikes, deleted_at FROM media_file WHERE id = ?", (file_id,)
    ).fetchone()
    assert deleted_at is None, "the row must still be live — the file is on disk"
    assert strikes == 1, f"the sighting restarted the count; expected 1, got {strikes}"


def test_the_tombstone_records_why_the_row_was_retired() -> None:
    """The strike count is the only record of WHY, and it no longer survives on the row.

    Before this module's change the count sat on the live row indefinitely, so it
    could be read back — that is how the 2026-06-30 mass tombstone was diagnosed.
    Now any later sighting zeroes it on sight, so the count has to be captured at
    the moment of retirement or it is gone.
    """
    import json as _json

    conn = _make_conn()
    disk_id, _path_id, file_id = _seed(conn, strikes=0)
    for generation in (2, 3, 4):
        mark_missed_files(conn, disk_id, current_generation=generation)

    assert apply_soft_deletes(conn, disk_id, n_strikes_for_softdelete=3) == 1

    payload_json = conn.execute(
        "SELECT payload_json FROM deleted_item WHERE kind = 'file' AND original_id = ?",
        (file_id,),
    ).fetchone()[0]
    payload = _json.loads(payload_json)
    assert payload["miss_strikes"] == 3, (
        f"the tombstone must record the strike count that caused it, got {payload.get('miss_strikes')!r}"
    )
