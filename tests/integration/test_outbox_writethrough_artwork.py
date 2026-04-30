"""Integration test: ArtworkDownloader.download_image → outbox publish → drain round-trip.

Verifies the full write-through path introduced in sub-phase 5.3d:
  1. ArtworkDownloader.download_image writes a file and calls publish_event
     via disk_id_for_path (both hooked into the real outbox module).
  2. Exactly one ``index_outbox`` row is inserted with op='artwork_write'.
  3. The payload contains the correct ``kind`` derived from the filename stem.
  4. drain_if_present drains the row (best-effort — status != 'pending').
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.outbox import drain_if_present
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.schema import DiskRow
from personalscraper.scraper.artwork import ArtworkDownloader

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# A minimal PNG byte sequence (header + 100 zero bytes) — non-empty, passes check.
_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection and apply the full migration schema.

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


def _make_fake_session() -> MagicMock:
    """Build a mock requests session whose .get() returns fake PNG bytes.

    Returns:
        A :class:`MagicMock` that behaves like ``requests.Session``.
    """
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = _FAKE_PNG
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp
    return mock_session


# ---------------------------------------------------------------------------
# Main outbox round-trip test
# ---------------------------------------------------------------------------


def test_download_image_publishes_artwork_write_and_drains(tmp_path: Path) -> None:
    """download_image inserts an artwork_write outbox row and drain marks it done.

    Steps:
    - Create library.db in tmp_path with the full schema.
    - Insert a mounted disk row whose mount_path is tmp_path/Disk1.
    - Create tmp_path/Disk1/Movies/Test (2024)/ on disk.
    - Patch IndexerConfig in outbox module to point at our db_path.
    - Mock the HTTP session so no real network call is made.
    - Call download_image("http://fake/poster.jpg", dest).
    - Assert exactly one index_outbox row with op='artwork_write' and kind='poster'.
    - Drain the outbox.
    - Assert the outbox row status != 'pending' (best-effort contract).
    """
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    # Insert mounted disk.
    disk_mount = str(tmp_path / "Disk1")
    _insert_mounted_disk(conn, mount_path=disk_mount)

    # Create the target directory on disk.
    target_dir = tmp_path / "Disk1" / "Movies" / "Test (2024)"
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / "poster.jpg"

    downloader = ArtworkDownloader(dry_run=False, artwork_language="en", db_path=db_path)

    with patch.object(downloader, "_session", _make_fake_session()):
        result = downloader.download_image("http://fake/poster.jpg", dest)

    assert result is True, "download_image should return True on success"
    assert dest.exists(), "download_image must write the file to disk"

    # Assert exactly one artwork_write outbox row.
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM index_outbox WHERE op = 'artwork_write'").fetchall()
    assert len(rows) == 1, f"Expected 1 artwork_write row, got {len(rows)}"

    payload = json.loads(rows[0]["payload_json"])
    assert payload.get("kind") == "poster", f"Expected kind='poster', got {payload.get('kind')!r}"
    assert "rel_path" in payload, "artwork_write payload must contain rel_path"
    assert payload["rel_path"].startswith("Movies/Test (2024)/"), (
        f"rel_path {payload['rel_path']!r} does not start with 'Movies/Test (2024)/'"
    )

    # Drain the outbox.
    drain_if_present(conn)

    # Assert the row is no longer pending (best-effort: 'done' or 'failed' are both acceptable).
    conn.row_factory = sqlite3.Row
    row_after = conn.execute(
        "SELECT status FROM index_outbox WHERE op = 'artwork_write'",
    ).fetchone()
    assert row_after is not None
    assert row_after["status"] != "pending", "Expected outbox row to be drained, but status is still 'pending'"

    conn.close()


# ---------------------------------------------------------------------------
# Kind derivation tests
# ---------------------------------------------------------------------------


def test_kind_derivation(tmp_path: Path) -> None:
    """download_image derives the correct whitelisted ``kind`` from the filename stem.

    Stems whose tokens are in :data:`_ALLOWED_ARTWORK_KINDS` map to the
    corresponding kind; stems with no recognised token cause the producer to
    skip the outbox publish entirely (no row is inserted).  See cycle 2 fix:
    emitting ``thumb`` or ``unknown`` would land permanently-failed rows in
    ``index_outbox`` because those values are not whitelisted.

    Covers:
    - ``poster.jpg``    → kind='poster'
    - ``landscape.jpg`` → kind='landscape'
    - ``fanart.jpg``    → kind='fanart'
    - ``backdrop.jpg``  → kind='fanart' (backdrop alias)
    - ``thumb.jpg``     → no outbox row inserted
    - ``random.jpg``    → no outbox row inserted
    """
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    disk_mount = str(tmp_path / "Disk1")
    _insert_mounted_disk(conn, mount_path=disk_mount)

    target_dir = tmp_path / "Disk1" / "Movies" / "Kind (2024)"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Whitelisted kinds: outbox row should be inserted with the expected kind.
    whitelisted_cases = [
        ("poster.jpg", "poster"),
        ("landscape.jpg", "landscape"),
        ("fanart.jpg", "fanart"),
        ("backdrop.jpg", "fanart"),
    ]
    # Unrecognised stems: producer must skip publish_event so no row is created.
    unrecognised_filenames = ["thumb.jpg", "random.jpg"]

    for filename, expected_kind in whitelisted_cases:
        dest = target_dir / filename
        downloader = ArtworkDownloader(dry_run=False, artwork_language="en", db_path=db_path)

        with patch.object(downloader, "_session", _make_fake_session()):
            downloader.download_image(f"http://fake/{filename}", dest)

        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT payload_json FROM index_outbox WHERE op = 'artwork_write' ORDER BY id DESC LIMIT 1",
        ).fetchone()
        assert row is not None, f"No artwork_write row found for {filename!r}"
        payload = json.loads(row["payload_json"])
        assert payload.get("kind") == expected_kind, (
            f"filename={filename!r}: expected kind={expected_kind!r}, got {payload.get('kind')!r}"
        )

    # Snapshot the outbox row count before testing the unrecognised cases so we
    # can prove no new rows are inserted when the stem is not whitelisted.
    rows_before = conn.execute("SELECT COUNT(*) FROM index_outbox WHERE op = 'artwork_write'").fetchone()[0]

    for filename in unrecognised_filenames:
        dest = target_dir / filename
        downloader = ArtworkDownloader(dry_run=False, artwork_language="en", db_path=db_path)

        with patch.object(downloader, "_session", _make_fake_session()):
            downloader.download_image(f"http://fake/{filename}", dest)

    rows_after = conn.execute("SELECT COUNT(*) FROM index_outbox WHERE op = 'artwork_write'").fetchone()[0]
    assert rows_after == rows_before, (
        f"Unrecognised stems must not insert outbox rows; row count went from {rows_before} to {rows_after}"
    )

    conn.close()


# ---------------------------------------------------------------------------
# No outbox row when path is not under a registered disk
# ---------------------------------------------------------------------------


def test_download_image_no_outbox_row_when_disk_not_registered(tmp_path: Path) -> None:
    """download_image does not insert an outbox row when the path matches no disk.

    When disk_id_for_path returns None (the destination is not under any
    registered disk), publish_event is never called and index_outbox stays empty.
    """
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)
    # No disk row inserted — no match for disk_id_for_path.

    target_dir = tmp_path / "UnknownDisk" / "Movies" / "Ghost (2001)"
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / "poster.jpg"

    downloader = ArtworkDownloader(dry_run=False, artwork_language="en", db_path=db_path)

    with patch.object(downloader, "_session", _make_fake_session()):
        result = downloader.download_image("http://fake/poster.jpg", dest)

    assert result is True
    assert dest.exists()

    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM index_outbox").fetchall()
    assert len(rows) == 0, f"Expected no outbox rows, got {len(rows)}"

    conn.close()
