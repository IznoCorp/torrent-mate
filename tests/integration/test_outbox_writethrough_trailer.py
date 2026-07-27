"""Integration test: TrailersOrchestrator.run() → outbox publish → drain round-trip.

Verifies the full write-through path introduced in sub-phase 5.3e:
  1. On DownloadStatus.SUCCESS the orchestrator calls disk_id_for_path + publish_event
     which inserts one row in ``index_outbox`` with op='trailer_download'.
  2. The payload contains the correct ``rel_path`` derived from the trailer file path.
  3. drain_if_present drains the row (best-effort — status != 'pending').
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.outbox._drain import drain_if_present
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.schema import DiskRow
from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus
from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.scanner import ScanItem

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


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


def _make_config(tmp_path: Path) -> MagicMock:
    """Build a minimal mock config for the orchestrator.

    Mirrors the factory used in tests/trailers/test_orchestrator.py so that
    TrailersOrchestrator.__init__ can complete without real config/env access.

    Args:
        tmp_path: Pytest tmp_path used for state-file location.

    Returns:
        MagicMock with all attributes the orchestrator constructor reads.
    """
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.languages = ["fr-FR", "en-US"]
    cfg.trailers.fallback_youtube_search = True
    cfg.trailers.search_query_format = "{title} {year} bande annonce"
    cfg.trailers.filters.min_file_size_bytes = 0  # accept tiny synthetic files
    cfg.trailers.filters.max_filesize_mb = 500
    cfg.trailers.state_file = str(tmp_path / ".data" / "trailers_state.json")
    cfg.trailers.retry_after_days = [1, 7, 30]
    cfg.trailers.ytdlp.format = "best[ext=mp4]/best"
    cfg.trailers.ytdlp.socket_timeout_sec = 30
    cfg.trailers.ytdlp.retries = 3
    cfg.trailers.seasons.enabled = False
    cfg.trailers.library_check.movies = False
    cfg.trailers.library_check.tv_shows = False  # disable library scan entirely
    cfg.trailers.step.max_duration_sec = 1800
    return cfg


# ---------------------------------------------------------------------------
# Main outbox round-trip test
# ---------------------------------------------------------------------------


def test_trailer_download_publishes_outbox_row_and_drains(tmp_path: Path) -> None:
    """run() inserts a trailer_download outbox row on SUCCESS and drain marks it done.

    Steps:
    - Create library.db in tmp_path with the full schema.
    - Insert a mounted disk row whose mount_path is tmp_path/Disk1.
    - Create tmp_path/Disk1/Movies/Test (2024)/ on disk.
    - Write a tiny synthetic trailer file there (the SOT and disk_id_for_path checks
      both inspect the real filesystem path, so the file must exist).
    - Patch IndexerConfig in outbox module to point at our db_path.
    - Mock _finder, _downloader, _state_store and _scanner on the orchestrator.
    - Invoke orchestrator.run([scan_item]).
    - Assert exactly one index_outbox row with op='trailer_download'.
    - Assert payload contains 'rel_path' and 'trailer_path'.
    - Drain the outbox.
    - Assert the row status is no longer 'pending'.
    """
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)

    # Insert mounted disk so disk_id_for_path can resolve the trailer path.
    disk_mount = str(tmp_path / "Disk1")
    _insert_mounted_disk(conn, mount_path=disk_mount)

    # Create only the media directory — NOT the trailer file yet.
    # The trailer must not exist before run() so the orchestrator's SOT recheck
    # does not short-circuit to already_present before reaching the download branch.
    media_dir = tmp_path / "Disk1" / "Movies" / "Test (2024)"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Build the ScanItem — the orchestrator reads path, media_type, title, year, tmdb_id.
    scan_item = ScanItem(
        path=media_dir,
        media_type="movie",
        title="Test",
        year=2024,
        tmdb_id="99999",
    )

    # Set indexer.db_path on the mock config so publish_event and disk_id_for_path
    # inside the orchestrator connect to the same test database that contains our disk row.
    config = _make_config(tmp_path)
    config.indexer.db_path = db_path
    orch = TrailersOrchestrator(
        config=config,
        staging_dir=tmp_path,
        event_bus=EventBus(),
        registry=MagicMock(spec=ProviderRegistry),
    )

    def _download_side_effect(url: str, dest: Path) -> DownloadResult:
        """Create the trailer file on disk (as yt-dlp would) then return SUCCESS."""
        dest.write_bytes(b"x" * 64)
        return DownloadResult(status=DownloadStatus.SUCCESS, output_path=dest)

    with (
        patch.object(orch._scanner, "scan_staging", return_value=[scan_item]),
        patch.object(orch._finder, "find", return_value="https://youtube.com/watch?v=FAKE"),
        patch.object(orch._downloader, "download", side_effect=_download_side_effect),
        # Suppress state-store I/O (not what we're testing here).
        patch.object(orch._state_store, "should_skip", return_value=False),
        patch.object(orch._state_store, "set"),
        patch.object(orch._state_store, "auto_gc"),
    ):
        counts = orch.run()

    assert counts["downloaded"] == 1, f"Expected downloaded=1, got {counts}"

    # Assert exactly one trailer_download outbox row was inserted.
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM index_outbox WHERE op = 'trailer_download'").fetchall()
    assert len(rows) == 1, f"Expected 1 trailer_download row, got {len(rows)}"

    payload = json.loads(rows[0]["payload_json"])
    assert "rel_path" in payload, "trailer_download payload must contain rel_path"
    assert "trailer_path" in payload, "trailer_download payload must contain trailer_path"
    # rel_path should be relative to the disk mount — must not start with '/'.
    assert not payload["rel_path"].startswith("/"), f"rel_path must be relative, got {payload['rel_path']!r}"
    # The rel_path should include the media folder and trailer filename.
    assert "Test (2024)" in payload["rel_path"], f"rel_path {payload['rel_path']!r} should reference 'Test (2024)'"

    # Drain the outbox.
    drain_if_present(conn)

    # After drain the row status must no longer be 'pending'.
    conn.row_factory = sqlite3.Row
    row_after = conn.execute(
        "SELECT status FROM index_outbox WHERE op = 'trailer_download'",
    ).fetchone()
    assert row_after is not None
    assert row_after["status"] != "pending", "Expected outbox row to be drained, but status is still 'pending'"

    conn.close()


# ---------------------------------------------------------------------------
# No outbox row when trailer path is not under a registered disk
# ---------------------------------------------------------------------------


def test_no_outbox_row_when_trailer_not_under_registered_disk(tmp_path: Path) -> None:
    """run() does not insert an outbox row when the output path matches no disk.

    When disk_id_for_path returns None (the trailer is not under any registered
    disk mount), publish_event is never called and index_outbox stays empty.
    """
    db_path = tmp_path / "library.db"
    conn = _open_db(db_path)
    # No disk row inserted — no match for disk_id_for_path.

    # Media dir is under an unregistered path.  Do NOT pre-create the trailer file
    # — the orchestrator's SOT recheck would short-circuit to already_present
    # before reaching the download branch where the hook fires.
    media_dir = tmp_path / "UnknownDisk" / "Movies" / "Ghost (2001)"
    media_dir.mkdir(parents=True, exist_ok=True)

    scan_item = ScanItem(
        path=media_dir,
        media_type="movie",
        title="Ghost",
        year=2001,
        tmdb_id="11888",
    )

    config = _make_config(tmp_path)
    config.indexer.db_path = db_path
    orch = TrailersOrchestrator(
        config=config,
        staging_dir=tmp_path,
        event_bus=EventBus(),
        registry=MagicMock(spec=ProviderRegistry),
    )

    def _download_side_effect(url: str, dest: Path) -> DownloadResult:
        """Create the trailer file on disk (as yt-dlp would) then return SUCCESS."""
        dest.write_bytes(b"x" * 64)
        return DownloadResult(status=DownloadStatus.SUCCESS, output_path=dest)

    with (
        patch.object(orch._scanner, "scan_staging", return_value=[scan_item]),
        patch.object(orch._finder, "find", return_value="https://youtube.com/watch?v=FAKE"),
        patch.object(orch._downloader, "download", side_effect=_download_side_effect),
        patch.object(orch._state_store, "should_skip", return_value=False),
        patch.object(orch._state_store, "set"),
        patch.object(orch._state_store, "auto_gc"),
    ):
        counts = orch.run()

    assert counts["downloaded"] == 1

    # No disk registered → no outbox row.
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM index_outbox").fetchall()
    assert len(rows) == 0, f"Expected no outbox rows when disk is not registered, got {len(rows)}"

    conn.close()
