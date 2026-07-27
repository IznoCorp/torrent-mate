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
                  '{}',NULL,NULL,?,?,
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


_VALID_NFO = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<movie><title>Cube</title><uniqueid type="tmdb">280</uniqueid></movie>\n'
)
# Present but content-invalid: a uniqueid whose value is the "0" placeholder.
_PLACEHOLDER_NFO = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<movie><title>Cube</title><uniqueid type="tmdb">0</uniqueid></movie>\n'
)
_TRUNCATED_NFO = '<?xml version="1.0" encoding="UTF-8"?>\n<movie><title>Cube</tit'


class TestCheckNfoStatusContent:
    """_check_nfo_status converges on the strict content definition (§9 / VERIFY-MAINTENANCE-03).

    Pre-P5.5 the enrich scan mode reported ``valid`` for *any* ``.nfo`` file
    (existence-only). It now delegates validity to
    ``core.completeness.nfo_status`` (→ ``nfo_utils.is_nfo_complete``): a present
    NFO that is unparseable or carries only placeholder ``<uniqueid>`` values is
    now ``invalid``, and AppleDouble sidecars never count as a real NFO.
    """

    def test_valid_nfo_returns_valid(self, tmp_path: Path) -> None:
        """A parseable NFO with a non-placeholder uniqueid → 'valid'."""
        (tmp_path / "Cube.nfo").write_text(_VALID_NFO, encoding="utf-8")
        assert _check_nfo_status(str(tmp_path)) == "valid"

    def test_placeholder_uniqueid_returns_invalid(self, tmp_path: Path) -> None:
        """A present NFO whose only uniqueid is the '0' placeholder → 'invalid' (was 'valid')."""
        (tmp_path / "Cube.nfo").write_text(_PLACEHOLDER_NFO, encoding="utf-8")
        assert _check_nfo_status(str(tmp_path)) == "invalid"

    def test_unparseable_nfo_returns_invalid(self, tmp_path: Path) -> None:
        """A present but truncated/unparseable NFO → 'invalid' (was 'valid')."""
        (tmp_path / "Cube.nfo").write_text(_TRUNCATED_NFO, encoding="utf-8")
        assert _check_nfo_status(str(tmp_path)) == "invalid"

    def test_apple_double_only_returns_missing(self, tmp_path: Path) -> None:
        """A directory holding only an AppleDouble ``._*.nfo`` sidecar → 'missing' (was 'valid')."""
        (tmp_path / "._Cube.nfo").write_bytes(b"\x00\x05\x16\x07binary-xattr-blob")
        assert _check_nfo_status(str(tmp_path)) == "missing"

    def test_no_nfo_returns_missing(self, tmp_path: Path) -> None:
        """A directory with no ``.nfo`` file at all → 'missing'."""
        (tmp_path / "Cube.mkv").write_bytes(b"video")
        assert _check_nfo_status(str(tmp_path)) == "missing"


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


# ---------------------------------------------------------------------------
# _enrich_one_file — trailer_found derived-index refresh (P6.4 single-truth)
# ---------------------------------------------------------------------------


def _empty_artwork_json() -> str:
    """Return a serialised all-absent :class:`ArtworkInventory` for seeding.

    Returns:
        The ``model_dump_json`` of an inventory with every artwork kind absent.
    """
    return ArtworkInventory(
        poster=False,
        fanart=False,
        landscape=False,
        banner=False,
        clearlogo=False,
        clearart=False,
        discart=False,
        characterart=False,
    ).model_dump_json()


class TestEnrichRefreshesTrailerFound:
    """P6.4: enrich reconciles the derived ``trailer_found`` index from the disk.

    The filesystem is the single truth for trailer existence (constitution P26);
    ``trailer_found`` is a DERIVED index that enrich refreshes from the on-disk
    trailer via the P5 completeness read-model.
    """

    def test_trailer_found_set_when_present_and_flipped_when_deleted(self, tmp_path: Path) -> None:
        """A present trailer sets ``trailer_found``; deleting it flips the index off.

        Args:
            tmp_path: Pytest tmp_path fixture (real media dir for the FS probe).
        """
        conn = _make_conn()
        item_id, file_id = _seed_db(conn, nfo_status="valid", artwork_json=_empty_artwork_json())

        # Real movie directory + video so media_completeness can probe the disk.
        movie_dir = tmp_path / "Fight Club (1999)"
        movie_dir.mkdir()
        video = movie_dir / "movie.mkv"
        video.write_bytes(b"\x00" * 4096)
        trailer = movie_dir / "Fight Club (1999)-trailer.mp4"
        trailer.write_bytes(b"x" * 200_000)

        # Enrich once — trailer present → trailer_found row is created.
        _enrich_one_file(conn, file_id, video, item_id, None)
        present = conn.execute(
            "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'trailer_found'",
            (item_id,),
        ).fetchone()
        assert present is not None, "trailer_found must be set when the trailer is on disk"

        # Delete the trailer, re-enrich — the derived index flips off.
        trailer.unlink()
        _enrich_one_file(conn, file_id, video, item_id, None)
        after = conn.execute(
            "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'trailer_found'",
            (item_id,),
        ).fetchone()
        assert after is None, "a trailer deleted on disk must flip trailer_found off on the next enrich"

    def test_trailer_found_absent_when_no_trailer(self, tmp_path: Path) -> None:
        """Enrich on a dir with no trailer leaves ``trailer_found`` absent.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        conn = _make_conn()
        item_id, file_id = _seed_db(conn, nfo_status="valid", artwork_json=_empty_artwork_json())

        movie_dir = tmp_path / "Heat (1995)"
        movie_dir.mkdir()
        video = movie_dir / "movie.mkv"
        video.write_bytes(b"\x00" * 4096)

        _enrich_one_file(conn, file_id, video, item_id, None)
        row = conn.execute(
            "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'trailer_found'",
            (item_id,),
        ).fetchone()
        assert row is None, "trailer_found must stay absent when no trailer exists on disk"

    def test_trailer_found_preserves_existing_precise_outbox_path(self, tmp_path: Path) -> None:
        """A precise outbox-written path survives the refresh (only presence is asserted).

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        conn = _make_conn()
        item_id, file_id = _seed_db(conn, nfo_status="valid", artwork_json=_empty_artwork_json())

        movie_dir = tmp_path / "Se7en (1995)"
        movie_dir.mkdir()
        video = movie_dir / "movie.mkv"
        video.write_bytes(b"\x00" * 4096)
        trailer = movie_dir / "Se7en (1995)-trailer.mp4"
        trailer.write_bytes(b"x" * 200_000)

        # Simulate the download outbox having written the precise trailer file path.
        precise = str(trailer)
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'trailer_found', ?)",
            (item_id, precise),
        )

        _enrich_one_file(conn, file_id, video, item_id, None)
        row = conn.execute(
            "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'trailer_found'",
            (item_id,),
        ).fetchone()
        assert row is not None
        assert row["value"] == precise, "the precise outbox path must be preserved (ON CONFLICT DO NOTHING)"
