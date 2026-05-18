"""Unit tests for personalscraper.indexer.scanner._modes — fail-safe helpers.

Covers sub-phase 9.3 acceptance criteria:
- :func:`_inventory_artwork` returns ``None`` on :exc:`OSError` and emits a
  ``indexer.enrich.artwork_inventory_failed`` warning.
- :func:`_check_nfo_status` returns ``None`` on :exc:`OSError` and emits a
  ``indexer.enrich.nfo_check_failed`` warning.
- :func:`_enrich_one_file` skips the ``media_item`` column update when either
  helper returns ``None`` (previously-valid data is preserved).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner._modes import (
    _check_nfo_status,
    _enrich_one_file,
    _inventory_artwork,
)
from personalscraper.indexer.schema import ArtworkInventory

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied.

    Returns:
        Open :class:`sqlite3.Connection` with FK checks enabled and all
        migrations applied.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _seed_db(
    conn: sqlite3.Connection,
    *,
    nfo_status: str | None = "valid",
    artwork_json: str | None,
) -> tuple[int, int]:
    """Insert minimal disk → path → media_item → media_file rows.

    Args:
        conn: Open SQLite connection.
        nfo_status: Initial ``nfo_status`` value to seed on ``media_item``.
        artwork_json: Initial ``artwork_json`` value to seed on ``media_item``.

    Returns:
        Tuple of ``(item_id, file_id)`` for the inserted rows.
    """
    now = int(time.time())

    # disk
    disk_id: int = conn.execute(
        """
        INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes)
        VALUES ('test-uuid', 'TestDisk', '/mnt/test', ?, 1, 0)
        """,
        (now,),
    ).lastrowid  # type: ignore[assignment]

    # path
    path_id: int = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, '001-MOVIES/TestMovie')",
        (disk_id,),
    ).lastrowid  # type: ignore[assignment]

    # media_item (pre-seeded with valid data that must survive a scan failure)
    item_id: int = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, original_title, year, category_id,
            external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json,
            date_created, date_modified, date_metadata_refreshed,
            is_locked, preferred_lang
        ) VALUES ('movie','Test Movie','Test Movie',NULL,2024,'movies',
                  NULL,NULL,NULL,?,?,
                  ?,?,NULL,0,'fr')
        """,
        (nfo_status, artwork_json, now, now),
    ).lastrowid  # type: ignore[assignment]

    # media_file
    file_id: int = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (NULL, ?, 'movie.mkv', 1048576, ?, NULL,
                  NULL, NULL, NULL, 1, ?, NULL, 0, NULL)
        """,
        (path_id, now * 1_000_000_000, now),
    ).lastrowid  # type: ignore[assignment]

    return item_id, file_id


# ---------------------------------------------------------------------------
# _inventory_artwork — unit tests
# ---------------------------------------------------------------------------


class TestInventoryArtworkFailSafe:
    """_inventory_artwork returns None and logs a warning on OSError."""

    def test_returns_none_on_oserror(self) -> None:
        """OSError from os.scandir causes _inventory_artwork to return None."""
        with patch("personalscraper.indexer.scanner._modes.os.scandir", side_effect=OSError("Permission denied")):
            result = _inventory_artwork("/nonexistent/dir")

        assert result is None

    def test_emits_warning_on_oserror(self, caplog: pytest.LogCaptureFixture) -> None:
        """OSError triggers a warning log with event 'indexer.enrich.artwork_inventory_failed'."""
        with caplog.at_level(logging.WARNING):
            with patch("personalscraper.indexer.scanner._modes.os.scandir", side_effect=OSError("EPERM")):
                _inventory_artwork("/locked/dir")

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("artwork_inventory_failed" in t for t in warning_texts), (
            f"Expected 'artwork_inventory_failed' in warning records; got: {warning_texts}"
        )

    def test_returns_artwork_inventory_on_success(self) -> None:
        """Normal scan returns a non-None ArtworkInventory."""
        # os.scandir is used as a context manager; wrap the empty list in a MagicMock
        # so that the 'with os.scandir(...) as it:' protocol is satisfied.
        cm = MagicMock()
        cm.__enter__.return_value = iter([])
        cm.__exit__.return_value = False
        with patch("personalscraper.indexer.scanner._modes.os.scandir", return_value=cm):
            result = _inventory_artwork("/some/dir")

        assert isinstance(result, ArtworkInventory)

    def test_warning_includes_error_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """Warning record includes error and error_type contextual fields."""
        with caplog.at_level(logging.WARNING):
            with patch(
                "personalscraper.indexer.scanner._modes.os.scandir",
                side_effect=PermissionError("EPERM"),
            ):
                _inventory_artwork("/locked/dir")

        # structlog renders key=value pairs into getMessage(); check both fields appear.
        all_text = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
        assert "PermissionError" in all_text, f"error_type missing from warning; got: {all_text}"


# ---------------------------------------------------------------------------
# _check_nfo_status — unit tests
# ---------------------------------------------------------------------------


class TestCheckNfoStatusFailSafe:
    """_check_nfo_status returns None and logs a warning on OSError."""

    def test_returns_none_on_oserror(self) -> None:
        """OSError from os.scandir causes _check_nfo_status to return None."""
        with patch("personalscraper.indexer.scanner._modes.os.scandir", side_effect=OSError("EIO")):
            result = _check_nfo_status("/bad/dir")

        assert result is None

    def test_emits_warning_on_oserror(self, caplog: pytest.LogCaptureFixture) -> None:
        """OSError triggers a warning log with event 'indexer.enrich.nfo_check_failed'."""
        with caplog.at_level(logging.WARNING):
            with patch("personalscraper.indexer.scanner._modes.os.scandir", side_effect=OSError("EIO")):
                _check_nfo_status("/bad/dir")

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("nfo_check_failed" in t for t in warning_texts), (
            f"Expected 'nfo_check_failed' in warning records; got: {warning_texts}"
        )

    def test_returns_missing_when_no_nfo(self) -> None:
        """Returns 'missing' when scandir succeeds but no .nfo file is found."""
        # os.scandir is used as a context manager; wrap the empty list in a MagicMock.
        cm = MagicMock()
        cm.__enter__.return_value = iter([])
        cm.__exit__.return_value = False
        with patch("personalscraper.indexer.scanner._modes.os.scandir", return_value=cm):
            result = _check_nfo_status("/empty/dir")

        assert result == "missing"

    def test_warning_includes_error_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """Warning record includes error and error_type contextual fields."""
        with caplog.at_level(logging.WARNING):
            with patch(
                "personalscraper.indexer.scanner._modes.os.scandir",
                side_effect=PermissionError("EPERM"),
            ):
                _check_nfo_status("/locked/dir")

        all_text = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
        assert "PermissionError" in all_text, f"error_type missing from warning; got: {all_text}"


# ---------------------------------------------------------------------------
# _enrich_one_file — column-skip integration tests
# ---------------------------------------------------------------------------


class TestEnrichOneFileSkipsColumnOnNone:
    """_enrich_one_file skips media_item column update when helpers return None.

    When os.scandir raises OSError, both _inventory_artwork and _check_nfo_status
    return None.  The caller must NOT overwrite previously-valid DB values.
    """

    def test_artwork_column_preserved_on_oserror(self) -> None:
        """artwork_json is not overwritten when _inventory_artwork returns None."""
        conn = _make_conn()
        prior_artwork = ArtworkInventory(
            poster=True,
            fanart=True,
            landscape=False,
            banner=False,
            clearlogo=False,
            clearart=False,
            discart=False,
            characterart=False,
        ).model_dump_json()

        item_id, file_id = _seed_db(conn, nfo_status="valid", artwork_json=prior_artwork)

        # Simulate OSError on both helpers; neither column must be changed.
        with patch("personalscraper.indexer.scanner._modes.os.scandir", side_effect=OSError("EACCES")):
            _enrich_one_file(conn, file_id, Path("/mnt/test/001-MOVIES/TestMovie/movie.mkv"), item_id, None)

        row = conn.execute("SELECT nfo_status, artwork_json FROM media_item WHERE id = ?", (item_id,)).fetchone()
        assert row is not None
        assert row["artwork_json"] == prior_artwork, (
            f"artwork_json was overwritten by a transient OS error; got: {row['artwork_json']}"
        )
        assert row["nfo_status"] == "valid", (
            f"nfo_status was overwritten by a transient OS error; got: {row['nfo_status']}"
        )

    def test_nfo_column_preserved_on_oserror(self) -> None:
        """nfo_status is not overwritten when _check_nfo_status returns None."""
        conn = _make_conn()
        prior_artwork = ArtworkInventory(
            poster=False,
            fanart=False,
            landscape=False,
            banner=False,
            clearlogo=False,
            clearart=False,
            discart=False,
            characterart=False,
        ).model_dump_json()

        item_id, file_id = _seed_db(conn, nfo_status="valid", artwork_json=prior_artwork)

        with patch("personalscraper.indexer.scanner._modes.os.scandir", side_effect=OSError("EPERM")):
            _enrich_one_file(conn, file_id, Path("/mnt/test/001-MOVIES/TestMovie/movie.mkv"), item_id, None)

        row = conn.execute("SELECT nfo_status FROM media_item WHERE id = ?", (item_id,)).fetchone()
        assert row is not None
        assert row["nfo_status"] == "valid", (
            f"nfo_status was changed from 'valid' to {row['nfo_status']!r} after transient OSError"
        )

    def test_warning_emitted_on_oserror(self, caplog: pytest.LogCaptureFixture) -> None:
        """Both warning events are emitted when os.scandir raises OSError."""
        conn = _make_conn()
        prior_artwork = ArtworkInventory(
            poster=False,
            fanart=False,
            landscape=False,
            banner=False,
            clearlogo=False,
            clearart=False,
            discart=False,
            characterart=False,
        ).model_dump_json()

        item_id, file_id = _seed_db(conn, nfo_status="missing", artwork_json=prior_artwork)

        with caplog.at_level(logging.WARNING):
            with patch("personalscraper.indexer.scanner._modes.os.scandir", side_effect=OSError("EACCES")):
                _enrich_one_file(
                    conn,
                    file_id,
                    Path("/mnt/test/001-MOVIES/TestMovie/movie.mkv"),
                    item_id,
                    None,
                )

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("artwork_inventory_failed" in t for t in warning_texts), (
            f"Expected 'artwork_inventory_failed' warning; got: {warning_texts}"
        )
        assert any("nfo_check_failed" in t for t in warning_texts), (
            f"Expected 'nfo_check_failed' warning; got: {warning_texts}"
        )

    def test_enriched_at_still_set_on_oserror(self) -> None:
        """enriched_at is updated even when artwork/nfo scan fails (file is not re-queued infinitely)."""
        conn = _make_conn()
        prior_artwork = ArtworkInventory(
            poster=False,
            fanart=False,
            landscape=False,
            banner=False,
            clearlogo=False,
            clearart=False,
            discart=False,
            characterart=False,
        ).model_dump_json()

        item_id, file_id = _seed_db(conn, nfo_status="missing", artwork_json=prior_artwork)

        # Verify enriched_at is NULL before enrichment.
        before = conn.execute("SELECT enriched_at FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert before["enriched_at"] is None

        with patch("personalscraper.indexer.scanner._modes.os.scandir", side_effect=OSError("EACCES")):
            _enrich_one_file(
                conn,
                file_id,
                Path("/mnt/test/001-MOVIES/TestMovie/movie.mkv"),
                item_id,
                None,
            )

        after = conn.execute("SELECT enriched_at FROM media_file WHERE id = ?", (file_id,)).fetchone()
        assert after["enriched_at"] is not None, "enriched_at must be set even after a transient OS error"
        assert after["enriched_at"] > 0
