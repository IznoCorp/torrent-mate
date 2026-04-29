"""Integration test: NFOGenerator.write_nfo → outbox publish → drain round-trip.

Verifies the full write-through path introduced in sub-phase 5.3c:
  1. NFOGenerator.write_nfo writes a file and calls publish_event via
     disk_id_for_path (both hooked into the real outbox module).
  2. Exactly one ``index_outbox`` row is inserted with op='nfo_write'.
  3. drain_if_present drains the row and marks it 'done'.
  4. If the drainer cannot resolve a media_item (best-effort contract), the
     test still passes — primary assertion is outbox presence + drain status.
"""

from __future__ import annotations

import sqlite3
import time
import types
from pathlib import Path
from unittest.mock import patch

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.outbox import drain_if_present
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.schema import DiskRow
from personalscraper.scraper.nfo_generator import NFOGenerator

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys and WAL mode.

    Args:
        db_path: Path to the ``library.db`` file.

    Returns:
        An open :class:`sqlite3.Connection` with the full schema applied.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_mounted_disk(conn: sqlite3.Connection, mount_path: str, label: str = "Disk1") -> int:
    """Insert a mounted disk row and return its id.

    Args:
        conn: Open SQLite connection.
        mount_path: Absolute path to the disk mount point.
        label: Display label for the disk.

    Returns:
        Rowid of the newly inserted disk row.
    """
    row = DiskRow(
        id=0,
        uuid=f"uuid-{label}",
        label=label,
        mount_path=mount_path,
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    return disk_repo.insert(conn, row)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_write_nfo_publishes_outbox_row_and_drains(tmp_path: Path) -> None:
    """write_nfo inserts an nfo_write outbox row and drain marks it done.

    Steps:
    - Create library.db in tmp_path with full schema.
    - Insert a mounted disk row whose mount_path is tmp_path/Disk1.
    - Create the target directory on disk (tmp_path/Disk1/Movies/Test (2024)).
    - Patch IndexerConfig in both outbox call-sites to return our db_path.
    - Call NFOGenerator().write_nfo("<movie></movie>", target_path).
    - Assert exactly one index_outbox row with op='nfo_write'.
    - Drain the outbox with drain_if_present(conn).
    - Assert the outbox row is marked 'done'.

    Per the Bug 3 fix, _apply_nfo_write now resolves path_id via the parent
    directory of the .nfo FILE path in rel_path (not the path directly).
    The path row for "Movies/Test (2024)" is not seeded in this test (scope
    is intentionally light: outbox round-trip only), so _apply_nfo_write
    will log a path_not_found warning and return silently — the row is still
    marked 'done' by the drainer per the best-effort contract (DESIGN §9.1).
    """
    db_path = tmp_path / "library.db"

    # --- Schema setup ---
    conn = _open_db(db_path)

    # --- Insert mounted disk ---
    disk_mount = str(tmp_path / "Disk1")
    disk_id = _insert_mounted_disk(conn, mount_path=disk_mount)

    # --- Create the target directory on disk ---
    target_dir = tmp_path / "Disk1" / "Movies" / "Test (2024)"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "Test (2024).nfo"

    # --- Patch IndexerConfig to use our tmp db_path ---
    # publish_event and disk_id_for_path both call IndexerConfig() internally.
    fake_config = types.SimpleNamespace(db_path=db_path)

    with patch(
        "personalscraper.indexer.outbox.IndexerConfig",
        return_value=fake_config,
    ):
        NFOGenerator().write_nfo("<movie></movie>", target_path)

    # --- Assert the NFO file was written ---
    assert target_path.exists(), "write_nfo must create the NFO file on disk"

    # --- Assert exactly one pending outbox row with op='nfo_write' ---
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM index_outbox WHERE op = 'nfo_write'").fetchall()
    assert len(rows) == 1, f"Expected 1 nfo_write row, got {len(rows)}"

    outbox_row = rows[0]
    # disk_id and rel_path live inside payload_json, not as top-level columns.
    import json  # noqa: PLC0415

    payload = json.loads(outbox_row["payload_json"])
    assert payload.get("disk_id") == disk_id, f"disk_id mismatch: expected {disk_id}, got {payload.get('disk_id')}"
    assert "rel_path" in payload, "nfo_write payload must contain rel_path"
    assert payload["rel_path"].startswith("Movies/Test (2024)/"), (
        f"rel_path {payload['rel_path']!r} does not start with 'Movies/Test (2024)/'"
    )

    # --- Drain the outbox ---
    # drain_if_present opens no extra connection; it uses the conn we pass.
    # The drainer's _apply_nfo_write may not find a media_item (best-effort).
    drain_if_present(conn)

    # --- Assert the outbox row is marked 'done' ---
    conn.row_factory = sqlite3.Row
    row_after = conn.execute(
        "SELECT status FROM index_outbox WHERE op = 'nfo_write'",
    ).fetchone()
    assert row_after is not None
    assert row_after["status"] == "done", f"Expected outbox row status='done', got {row_after['status']!r}"

    conn.close()


def test_write_nfo_no_outbox_row_when_disk_not_registered(tmp_path: Path) -> None:
    """write_nfo does not insert an outbox row when the path matches no disk.

    When disk_id_for_path returns None (the path is not under any registered
    disk), publish_event is never called and index_outbox stays empty.
    """
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)
    # No disk row inserted — no match for disk_id_for_path.

    target_dir = tmp_path / "UnknownDisk" / "Movies" / "Ghost (2001)"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "Ghost (2001).nfo"

    fake_config = types.SimpleNamespace(db_path=db_path)

    with patch(
        "personalscraper.indexer.outbox.IndexerConfig",
        return_value=fake_config,
    ):
        NFOGenerator().write_nfo("<movie></movie>", target_path)

    assert target_path.exists()

    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM index_outbox").fetchall()
    assert len(rows) == 0, f"Expected no outbox rows, got {len(rows)}"

    conn.close()
