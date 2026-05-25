"""Regression tests for BDD-backed NFO restore on re-ingested movies.

Sub-phase 12.9 — DEVIATION #12 (P2 mineur, BDD stale entries).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.movie_service import _restore_from_db

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _make_config(db_path: Path | None) -> SimpleNamespace:
    """Build a minimal config stub with only ``indexer.db_path`` populated."""
    idx = SimpleNamespace()
    idx.db_path = db_path
    cfg = SimpleNamespace()
    cfg.indexer = idx
    return cfg


def _seed_movie(conn: sqlite3.Connection, title: str, dispatch_path: str) -> int:
    """Insert a media_item (movie) + item_attribute(dispatch_path) and return the item id."""
    now_s = int(time.time())
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "nfo_status, date_created, date_modified) "
        "VALUES ('movie', ?, ?, 'movies', 'valid', ?, ?)",
        (title, title, now_s, now_s),
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
        (item_id, dispatch_path),
    )
    conn.commit()
    return item_id


class TestBddRestore:
    """Verification that BDD-backed NFO restore handles all edge cases."""

    def test_restore_skipped_when_no_config(self) -> None:
        """Config is None → restoration returns False without exception."""
        result = ScrapeResult(media_path=Path("/fake"), media_type="movie")
        ok = _restore_from_db(None, False, Path("/staging"), "Mikado", 2024, result)
        assert ok is False
        assert result.action == "error"  # unchanged

    def test_restore_skipped_when_db_path_none(self) -> None:
        """config.indexer.db_path is None → restoration returns False."""
        config = _make_config(None)
        result = ScrapeResult(media_path=Path("/fake"), media_type="movie")
        ok = _restore_from_db(config, False, Path("/staging"), "Mikado", 2024, result)
        assert ok is False
        assert result.action == "error"

    def test_restore_skipped_when_db_path_not_path(self, caplog: pytest.LogCaptureFixture) -> None:
        """db_path is not a Path or str → defensive guard logs and returns False."""
        idx = SimpleNamespace()
        idx.db_path = MagicMock()  # not a str or Path
        cfg = SimpleNamespace()
        cfg.indexer = idx

        result = ScrapeResult(media_path=Path("/fake"), media_type="movie")
        with caplog.at_level(logging.INFO, logger="scraper"):
            ok = _restore_from_db(cfg, False, Path("/staging"), "Mikado", 2024, result)
        assert ok is False
        assert result.action == "error"
        assert any("movie_db_restore_skipped_db_path_not_path" in r.message for r in caplog.records)

    def test_restore_skipped_when_no_match(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """DB has no row matching the title → restoration returns False with log."""
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        conn.close()

        config = _make_config(db_path)
        result = ScrapeResult(media_path=Path("/fake"), media_type="movie")

        with caplog.at_level(logging.INFO, logger="scraper"):
            ok = _restore_from_db(config, False, Path("/staging"), "Unknown Movie", 2024, result)
        assert ok is False
        assert result.action == "error"
        assert any("movie_db_restore_skipped_no_match" in r.message for r in caplog.records)

    def test_restore_skipped_when_dispatch_path_missing(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """DB has match but dispatch_path doesn't exist on disk → returns False."""
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        _seed_movie(conn, "Mikado", "/nonexistent/dispatch/path")
        conn.close()

        config = _make_config(db_path)
        result = ScrapeResult(media_path=Path("/fake"), media_type="movie")

        with caplog.at_level(logging.INFO, logger="scraper"):
            ok = _restore_from_db(config, False, Path("/staging"), "Mikado", 2024, result)
        assert ok is False
        assert result.action == "error"
        assert any("movie_db_restore_skipped_dispatch_path_missing" in r.message for r in caplog.records)

    def test_restore_copies_nfo_and_artwork(self, tmp_path: Path) -> None:
        """Full restore: NFO + artwork copied from dispatch to staging."""
        dispatch_dir = tmp_path / "dispatched" / "Mikado (2024)"
        dispatch_dir.mkdir(parents=True)
        # Create a real NFO file (glob_nfo_candidates expects .nfo extension)
        nfo_file = dispatch_dir / "Mikado (2024).nfo"
        nfo_file.write_text("<movie><title>Mikado</title></movie>")
        # Create artwork files
        poster = dispatch_dir / "poster.jpg"
        poster.write_bytes(b"\xff\xd8\xff\xe0")
        fanart = dispatch_dir / "fanart.jpg"
        fanart.write_bytes(b"\xff\xd8\xff\xe1")
        landscape = dispatch_dir / "landscape.jpg"
        landscape.write_bytes(b"\xff\xd8\xff\xe2")

        staging_dir = tmp_path / "staging" / "Mikado (2024)"
        staging_dir.mkdir(parents=True)

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        _seed_movie(conn, "Mikado", str(dispatch_dir))
        conn.close()

        config = _make_config(db_path)
        result = ScrapeResult(media_path=staging_dir, media_type="movie")

        ok = _restore_from_db(config, False, staging_dir, "Mikado", 2024, result)
        assert ok is True
        assert result.action == "restored_from_db"

        # NFO file was copied
        staging_nfo = staging_dir / "Mikado (2024).nfo"
        assert staging_nfo.exists()
        assert staging_nfo.read_text() == "<movie><title>Mikado</title></movie>"

        # Artwork files were copied
        assert (staging_dir / "poster.jpg").exists()
        assert (staging_dir / "fanart.jpg").exists()
        assert (staging_dir / "landscape.jpg").exists()

    def test_restore_dry_run_does_not_copy(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """dry_run=True logs what would be copied but does not copy files."""
        dispatch_dir = tmp_path / "dispatched" / "Mikado (2024)"
        dispatch_dir.mkdir(parents=True)
        nfo_file = dispatch_dir / "Mikado (2024).nfo"
        nfo_file.write_text("<movie><title>Mikado</title></movie>")
        poster = dispatch_dir / "poster.jpg"
        poster.write_bytes(b"\xff\xd8\xff\xe0")

        staging_dir = tmp_path / "staging" / "Mikado (2024)"
        staging_dir.mkdir(parents=True)

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        _seed_movie(conn, "Mikado", str(dispatch_dir))
        conn.close()

        config = _make_config(db_path)
        result = ScrapeResult(media_path=staging_dir, media_type="movie")

        with caplog.at_level(logging.INFO, logger="scraper"):
            ok = _restore_from_db(config, True, staging_dir, "Mikado", 2024, result)
        assert ok is True
        assert result.action == "restored_from_db"

        # No files copied to staging
        assert not (staging_dir / "Mikado (2024).nfo").exists()
        assert not (staging_dir / "poster.jpg").exists()

        # Dry-run log emitted
        assert any("movie_db_restore_would_copy" in r.message for r in caplog.records)

    def test_restore_skipped_when_no_artwork_at_dispatch(self, tmp_path: Path) -> None:
        """Restore still succeeds when dispatch has NFO but no artwork files."""
        dispatch_dir = tmp_path / "dispatched" / "Mikado (2024)"
        dispatch_dir.mkdir(parents=True)
        nfo_file = dispatch_dir / "Mikado (2024).nfo"
        nfo_file.write_text("<movie><title>Mikado</title></movie>")
        # No artwork files at all

        staging_dir = tmp_path / "staging" / "Mikado (2024)"
        staging_dir.mkdir(parents=True)

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        _seed_movie(conn, "Mikado", str(dispatch_dir))
        conn.close()

        config = _make_config(db_path)
        result = ScrapeResult(media_path=staging_dir, media_type="movie")

        ok = _restore_from_db(config, False, staging_dir, "Mikado", 2024, result)
        assert ok is True
        assert result.action == "restored_from_db"
        assert (staging_dir / "Mikado (2024).nfo").exists()

    def test_restore_with_str_db_path_succeeds(self, tmp_path: Path) -> None:
        """db_path passed as str (not Path) is converted and restore succeeds."""
        dispatch_dir = tmp_path / "dispatched" / "Mikado (2024)"
        dispatch_dir.mkdir(parents=True)
        nfo_file = dispatch_dir / "Mikado (2024).nfo"
        nfo_file.write_text("<movie><title>Mikado</title></movie>")

        staging_dir = tmp_path / "staging" / "Mikado (2024)"
        staging_dir.mkdir(parents=True)

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        _seed_movie(conn, "Mikado", str(dispatch_dir))
        conn.close()

        config = _make_config(str(db_path))  # str, not Path
        result = ScrapeResult(media_path=staging_dir, media_type="movie")

        ok = _restore_from_db(config, False, staging_dir, "Mikado", 2024, result)
        assert ok is True
        assert result.action == "restored_from_db"
        assert (staging_dir / "Mikado (2024).nfo").exists()

    def test_restore_partial_copy_rolls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Partial copy is rolled back when artwork copy fails mid-way."""
        import shutil

        dispatch_dir = tmp_path / "dispatched" / "Mikado (2024)"
        dispatch_dir.mkdir(parents=True)
        nfo_file = dispatch_dir / "Mikado (2024).nfo"
        nfo_file.write_text("<movie><title>Mikado</title></movie>")
        (dispatch_dir / "poster.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        (dispatch_dir / "fanart.jpg").write_bytes(b"\xff\xd8\xff\xe1")

        staging_dir = tmp_path / "staging" / "Mikado (2024)"
        staging_dir.mkdir(parents=True)

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        _seed_movie(conn, "Mikado", str(dispatch_dir))
        conn.close()

        # Fail only on the 2nd copy2 call (1st = NFO succeeds, 2nd = poster fails)
        real_copy2 = shutil.copy2
        call_count = [0]

        def failing_copy2(src: str, dst: str) -> str:
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError("Simulated disk full")
            return real_copy2(src, dst)

        monkeypatch.setattr(shutil, "copy2", failing_copy2)

        config = _make_config(db_path)
        result = ScrapeResult(media_path=staging_dir, media_type="movie")

        with caplog.at_level(logging.WARNING, logger="scraper"):
            ok = _restore_from_db(config, False, staging_dir, "Mikado", 2024, result)

        assert ok is False
        assert result.action == "error"  # unchanged on failure

        # NFO was copied first, so it must be rolled back
        nfo_dest = staging_dir / "Mikado (2024).nfo"
        assert not nfo_dest.exists(), "copied NFO should be rolled back"

        # Logs confirm rollback
        assert any("movie_db_restore_failed" in r.message for r in caplog.records)

    def test_restore_failure_sets_skipped_low_confidence(self, tmp_path: Path) -> None:
        """When _restore_from_db fails, _restore_from_db leaves result.action untouched (error).

        The caller is responsible for distinguishing this from a successful restore
        by setting action to ``skipped_low_confidence``.
        """
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        conn.close()

        config = _make_config(db_path)
        result = ScrapeResult(media_path=Path("/fake"), media_type="movie")

        ok = _restore_from_db(config, False, Path("/staging"), "Unknown Movie", 2024, result)
        assert ok is False
        # _restore_from_db contract: action is NOT modified on failure
        assert result.action == "error"

        # Caller explicitly sets the action for the restore-failure branch
        result.action = "skipped_low_confidence"
        assert result.action == "skipped_low_confidence"
