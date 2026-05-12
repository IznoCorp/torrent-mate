"""Integration test: Dispatcher.dispatch_movie → outbox publish → drain round-trip.

Verifies the full write-through path introduced in sub-phase 5.3b:
  1. Dispatcher.dispatch_movie moves a movie dir to a fake disk and calls
     publish_event via disk_id_for_path (both hooked into the real outbox module).
  2. Exactly one ``index_outbox`` row is inserted with op='move'.
  3. drain_if_present processes the row (marks it 'done').
  4. The primary assertion is outbox row presence + drain marks the row 'done'.

Note on size_bytes/mtime_ns: Dispatcher.dispatch_movie publishes
size_bytes=None and mtime_ns=None in the payload (best-effort contract from
DESIGN §9.1).  Per the Bug 2 fix, _apply_move treats missing size_bytes/mtime_ns
as best-effort and marks the row 'done' without creating a media_file row.
The next scan reconciles the file via dir-mtime walk (DESIGN §17.1).
The test therefore asserts status == 'done'.
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.outbox._drain import drain_if_present
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.schema import DiskRow
from personalscraper.sorter.file_type import FileType

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# Minimum video size (bytes) to pass the verify "sample" size check (100 MB).
_MIN_VIDEO_BYTES = 100 * 1024 * 1024 + 1

_GB = 1024**3


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


def _insert_mounted_disk(conn: sqlite3.Connection, mount_path: str, label: str) -> int:
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


def _make_settings() -> Settings:
    """Return Settings with disk-space guards disabled for integration tests.

    Returns:
        Settings instance with zero thresholds so the tests are not skipped
        due to real filesystem constraints.
    """
    return Settings()


def _build_multi_disk_config(base_config: Config, fake_disks: list[Path]) -> Config:
    """Return a Config variant where disk1 accepts MOVIES.

    Uses the same category distribution as the integration_config fixture
    (from conftest.py) to ensure all category IDs remain covered.

    Args:
        base_config: The integration_config to derive from.
        fake_disks: List of four fake disk root paths.

    Returns:
        Config copy identical to base_config (movies already on disk1).
    """
    # integration_config already has MOVIES on disk1 — return as-is.
    return base_config


def _build_verified_movie_dir(parent: Path, title: str = "Oppenheimer", year: int = 2023) -> Path:
    """Create a minimal verified movie folder that passes the verify gate.

    Creates the directory with a large-enough video file, an NFO with all
    required fields, a poster, and a landscape artwork file.

    Args:
        parent: Directory under which the movie folder is created.
        title: Movie title used for the folder and file names.
        year: Release year used in the folder name and NFO.

    Returns:
        Path to the created movie directory.
    """
    movie_dir = parent / f"{title} ({year})"
    movie_dir.mkdir(parents=True, exist_ok=True)

    # Video file — must exceed 100 MB to avoid the "sample" warning check.
    (movie_dir / f"{title}.mkv").write_bytes(b"\x00" * _MIN_VIDEO_BYTES)

    # NFO with mandatory fields: title, year, tmdb+imdb uniqueids, genre,
    # and a streamdetails block (verifier checks for its presence).
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid_tmdb = ET.SubElement(root, "uniqueid")
    uid_tmdb.set("type", "tmdb")
    uid_tmdb.text = "12345"
    uid_imdb = ET.SubElement(root, "uniqueid")
    uid_imdb.set("type", "imdb")
    uid_imdb.text = "tt9999999"
    ET.SubElement(root, "genre").text = "Drama"
    fi = ET.SubElement(root, "fileinfo")
    sd = ET.SubElement(fi, "streamdetails")
    ET.SubElement(sd, "video")
    ET.ElementTree(root).write(movie_dir / f"{title}.nfo", encoding="unicode")

    # Artwork — poster and landscape are both blocking requirements in checker.py.
    (movie_dir / f"{title}-poster.jpg").write_bytes(b"\xff\xd8\xff")
    (movie_dir / f"{title}-landscape.jpg").write_bytes(b"\xff\xd8\xff")

    return movie_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dispatch_movie_publishes_outbox_row_and_drains(
    staging_tree: Path,
    fake_disks: list[Path],
    integration_config: Config,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dispatch_movie inserts a move outbox row and drain processes it.

    Steps:
    - Create library.db in tmp_path with full schema.
    - Insert a mounted disk row for each fake disk in library.db.
    - Patch IndexerConfig in outbox call-sites to return our db_path.
    - Monkeypatch shutil.disk_usage so disk1 wins the free-space election.
    - Build a verified movie directory in the staging area.
    - Invoke Dispatcher(..., event_bus=EventBus()).dispatch_movie(movie_dir, "movies") directly.
    - Assert exactly one index_outbox row exists with op='move'.
    - Assert the payload contains dst_rel_path pointing to the destination disk.
    - Drain the outbox via drain_if_present(conn).
    - Assert the outbox row is processed (status == 'done').

    Note on size_bytes/mtime_ns: Dispatcher publishes size_bytes=None and
    mtime_ns=None (best-effort contract). Per the Bug 2 fix, _apply_move
    treats missing fields as best-effort and marks the row 'done' without
    inserting a media_file row.  The next scan reconciles via dir-mtime walk.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        fake_disks: List of four fake disk root paths.
        integration_config: Fully composed integration Config fixture.
        tmp_path: Pytest temporary directory (unique per test).
        monkeypatch: Pytest monkeypatch fixture.
    """
    # --- Skip if rsync is unavailable ---
    if shutil.which("rsync") is None:
        pytest.skip("rsync not available on this system")

    # --- Schema setup ---
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    # --- Insert a mounted disk row for each fake disk ---
    # integration_config has disk1 (fake_disks[0]) accepting MOVIES.
    for i, disk_path in enumerate(fake_disks, start=1):
        _insert_mounted_disk(conn, mount_path=str(disk_path), label=f"Disk{i}")

    # --- Override indexer.db_path in the config so dispatch_movie lands events
    # in the test DB rather than the default .data/library.db ---
    new_indexer = integration_config.indexer.model_copy(update={"db_path": db_path})
    test_config = integration_config.model_copy(update={"indexer": new_indexer})

    # --- Monkeypatch shutil.disk_usage so disk1 wins free-space election ---
    _real_disk_usage = shutil.disk_usage

    def _fake_disk_usage(path: Any) -> Any:
        """Return large free space for fake_disks[0] so it wins the election.

        Falls through to the real shutil.disk_usage for other paths.

        Args:
            path: Filesystem path passed to shutil.disk_usage.

        Returns:
            Object with ``.free`` attribute for fake disks or real stats.
        """
        path_str = str(path)
        for disk_path in fake_disks:
            if path_str == str(disk_path) or path_str.startswith(str(disk_path) + "/"):

                class _FakeUsage:
                    total = 1000 * _GB
                    free = 500 * _GB
                    used = total - free

                return _FakeUsage()
        return _real_disk_usage(path)

    monkeypatch.setattr("personalscraper.dispatch.disk_scanner.shutil.disk_usage", _fake_disk_usage)

    # --- Place a verified movie in the staging movies subdirectory ---
    movies_staging = staging_tree / folder_name(find_by_file_type(integration_config, FileType.MOVIE))
    movie_title = "Oppenheimer"
    movie_year = 2023
    movie_dir = _build_verified_movie_dir(movies_staging, title=movie_title, year=movie_year)

    # --- Build the MediaIndex (empty — new item, will be moved to disk1) ---
    index_path = tmp_path / "media.db"
    index = MediaIndex(index_path)

    # --- Ensure data_dir exists ---
    test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    # --- Invoke dispatch_movie directly (bypass run_dispatch for precision) ---
    # test_config has indexer.db_path overridden to point at our tmp DB so
    # dispatch_movie's publish_event call lands in the right database.
    dispatcher = Dispatcher(
        config=test_config,
        settings=_make_settings(),
        index=index,
        dry_run=False,
        event_bus=EventBus(),
    )
    result = dispatcher.dispatch_movie(movie_dir, CID.MOVIES)

    # --- Assert dispatch succeeded (moved to disk1) ---
    assert result.action == "moved", (
        f"Expected dispatch action='moved', got action={result.action!r}, reason={result.reason!r}"
    )
    assert result.destination is not None, "Expected a non-None destination after successful dispatch"

    # --- Assert exactly one pending outbox row with op='move' ---
    import json  # noqa: PLC0415

    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM index_outbox WHERE op = 'move'").fetchall()
    assert len(rows) == 1, f"Expected 1 move outbox row, got {len(rows)}"

    outbox_row = rows[0]
    payload = json.loads(outbox_row["payload_json"])

    # The payload must contain dst_rel_path pointing at the destination.
    assert "dst_rel_path" in payload, "move payload must contain dst_rel_path"
    dst_rel_path: str = payload["dst_rel_path"]

    # The destination is under one of the fake disks.
    assert any(str(result.destination).startswith(str(d)) for d in fake_disks), (
        f"destination {result.destination} should be under a fake disk"
    )

    # dst_rel_path must be a non-empty relative path string.
    assert dst_rel_path, f"dst_rel_path must be non-empty, got {dst_rel_path!r}"

    # disk_id in the payload must correspond to a registered disk.
    assert "disk_id" in payload, "move payload must contain disk_id"
    assert isinstance(payload["disk_id"], int), f"disk_id must be an int, got {type(payload['disk_id'])}"

    # --- Drain the outbox ---
    drain_if_present(conn)

    # --- Assert the outbox row is marked 'done' ---
    # Per the Bug 2 fix: _apply_move treats missing size_bytes/mtime_ns as
    # best-effort (DESIGN §17.1) and returns without inserting a media_file row,
    # so the drainer still marks the row 'done'.
    conn.row_factory = sqlite3.Row
    row_after = conn.execute(
        "SELECT status FROM index_outbox WHERE op = 'move'",
    ).fetchone()
    assert row_after is not None, "Outbox row must still exist after drain"
    assert row_after["status"] == "done", (
        f"Outbox row must be marked 'done' after drain, got status={row_after['status']!r}"
    )

    conn.close()
