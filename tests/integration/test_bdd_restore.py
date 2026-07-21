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
from personalscraper.scraper._db_restore import (
    AmbiguousNfo,
    CopyFailed,
    NoDb,
    NoDispatchPath,
    NoMatch,
    NoNfoAtDispatch,
    Restored,
    _restore_from_db,
)

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _make_config(db_path: Path | None | str) -> SimpleNamespace:
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
        """Config is None → restoration returns NoDb."""
        outcome = _restore_from_db(None, False, Path("/staging"), "Mikado", 2024)
        assert isinstance(outcome, NoDb)
        assert outcome.reason == "config_is_none"

    def test_restore_skipped_when_db_path_none(self) -> None:
        """config.indexer.db_path is None → restoration returns NoDb."""
        config = _make_config(None)
        outcome = _restore_from_db(config, False, Path("/staging"), "Mikado", 2024)
        assert isinstance(outcome, NoDb)
        assert outcome.reason == "db_path_is_none"

    def test_restore_skipped_when_db_path_not_path(self, caplog: pytest.LogCaptureFixture) -> None:
        """db_path is not a Path or str → defensive guard logs and returns NoDb."""
        idx = SimpleNamespace()
        idx.db_path = MagicMock()  # not a str or Path
        cfg = SimpleNamespace()
        cfg.indexer = idx

        with caplog.at_level(logging.INFO, logger="scraper"):
            outcome = _restore_from_db(cfg, False, Path("/staging"), "Mikado", 2024)
        assert isinstance(outcome, NoDb)
        assert outcome.reason == "db_path_not_path"
        assert any("movie_db_restore_skipped_db_path_not_path" in r.message for r in caplog.records)

    def test_restore_skipped_when_no_match(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """DB has no row matching the title → restoration returns NoMatch with log."""
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        conn.close()

        config = _make_config(db_path)

        with caplog.at_level(logging.INFO, logger="scraper"):
            outcome = _restore_from_db(config, False, Path("/staging"), "Unknown Movie", 2024)
        assert isinstance(outcome, NoMatch)
        assert outcome.title == "Unknown Movie"
        assert any("movie_db_restore_skipped_no_match" in r.message for r in caplog.records)

    def test_restore_skipped_when_dispatch_path_missing(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """DB has match but dispatch_path doesn't exist on disk → returns NoDispatchPath."""
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        item_id = _seed_movie(conn, "Mikado", "/nonexistent/dispatch/path")
        conn.close()

        config = _make_config(db_path)

        with caplog.at_level(logging.INFO, logger="scraper"):
            outcome = _restore_from_db(config, False, Path("/staging"), "Mikado", 2024)
        assert isinstance(outcome, NoDispatchPath)
        assert outcome.item_id == item_id
        assert any("movie_db_restore_skipped_dispatch_path_missing" in r.message for r in caplog.records)

    def test_restore_copies_nfo_and_artwork(self, tmp_path: Path) -> None:
        """Full restore: NFO + artwork copied from dispatch to staging."""
        dispatch_dir = tmp_path / "dispatched" / "Mikado (2024)"
        dispatch_dir.mkdir(parents=True)
        nfo_file = dispatch_dir / "Mikado (2024).nfo"
        nfo_file.write_text("<movie><title>Mikado</title></movie>")
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

        outcome = _restore_from_db(config, False, staging_dir, "Mikado", 2024)
        assert isinstance(outcome, Restored)
        assert outcome.files_copied == 4  # NFO + 3 artwork files
        assert outcome.nfo_path == staging_dir / "Mikado (2024).nfo"

        staging_nfo = staging_dir / "Mikado (2024).nfo"
        assert staging_nfo.exists()
        assert staging_nfo.read_text() == "<movie><title>Mikado</title></movie>"

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

        with caplog.at_level(logging.INFO, logger="scraper"):
            outcome = _restore_from_db(config, True, staging_dir, "Mikado", 2024)
        assert isinstance(outcome, Restored)
        assert outcome.files_copied == 0  # dry-run copies nothing
        assert outcome.nfo_path == staging_dir / "Mikado (2024).nfo"

        assert not (staging_dir / "Mikado (2024).nfo").exists()
        assert not (staging_dir / "poster.jpg").exists()

        assert any("movie_db_restore_would_copy" in r.message for r in caplog.records)

    def test_restore_skipped_when_no_artwork_at_dispatch(self, tmp_path: Path) -> None:
        """Restore still succeeds when dispatch has NFO but no artwork files."""
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

        config = _make_config(db_path)

        outcome = _restore_from_db(config, False, staging_dir, "Mikado", 2024)
        assert isinstance(outcome, Restored)
        assert outcome.files_copied == 1  # NFO only
        assert outcome.nfo_path == staging_dir / "Mikado (2024).nfo"
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

        outcome = _restore_from_db(config, False, staging_dir, "Mikado", 2024)
        assert isinstance(outcome, Restored)
        assert outcome.files_copied == 1  # NFO only (no artwork)
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

        with caplog.at_level(logging.WARNING, logger="scraper"):
            outcome = _restore_from_db(config, False, staging_dir, "Mikado", 2024)

        assert isinstance(outcome, CopyFailed)
        assert outcome.files_rolled_back == 1  # NFO was copied first
        assert "Simulated disk full" in outcome.error

        # NFO was copied first, so it must be rolled back
        nfo_dest = staging_dir / "Mikado (2024).nfo"
        assert not nfo_dest.exists(), "copied NFO should be rolled back"

        assert any("movie_db_restore_failed" in r.message for r in caplog.records)

    def test_restore_returns_nomatch_for_unknown_movie(self, tmp_path: Path) -> None:
        """No DB match → NoMatch outcome (type enforces caller handling)."""
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        conn.close()

        config = _make_config(db_path)

        outcome = _restore_from_db(config, False, Path("/staging"), "Unknown Movie", 2024)
        assert isinstance(outcome, NoMatch)
        assert outcome.title == "Unknown Movie"

    def test_restore_skipped_ambiguous_nfo(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Multiple NFO files at dispatch → AmbiguousNfo outcome."""
        dispatch_dir = tmp_path / "dispatched" / "Mikado (2024)"
        dispatch_dir.mkdir(parents=True)
        (dispatch_dir / "movie.nfo").write_text("<movie><title>Mikado</title></movie>")
        (dispatch_dir / "Mikado (2024).nfo").write_text("<movie><title>Mikado</title></movie>")

        staging_dir = tmp_path / "staging" / "Mikado (2024)"
        staging_dir.mkdir(parents=True)

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        item_id = _seed_movie(conn, "Mikado", str(dispatch_dir))
        conn.close()

        config = _make_config(db_path)

        with caplog.at_level(logging.INFO, logger="scraper"):
            outcome = _restore_from_db(config, False, staging_dir, "Mikado", 2024)
        assert isinstance(outcome, AmbiguousNfo)
        assert outcome.item_id == item_id
        assert len(outcome.candidates) == 2
        assert any("movie_db_restore_skipped_ambiguous_nfo" in r.message for r in caplog.records)

    def test_restore_skipped_no_nfo_at_dispatch(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Dispatch dir exists but has no NFO files → NoNfoAtDispatch outcome."""
        dispatch_dir = tmp_path / "dispatched" / "Mikado (2024)"
        dispatch_dir.mkdir(parents=True)
        # No NFO file — only artwork
        (dispatch_dir / "poster.jpg").write_bytes(b"\xff\xd8\xff\xe0")

        staging_dir = tmp_path / "staging" / "Mikado (2024)"
        staging_dir.mkdir(parents=True)

        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        item_id = _seed_movie(conn, "Mikado", str(dispatch_dir))
        conn.close()

        config = _make_config(db_path)

        with caplog.at_level(logging.INFO, logger="scraper"):
            outcome = _restore_from_db(config, False, staging_dir, "Mikado", 2024)
        assert isinstance(outcome, NoNfoAtDispatch)
        assert outcome.item_id == item_id
        assert str(dispatch_dir) in outcome.dispatch_path
        assert any("movie_db_restore_skipped_no_nfo_at_dispatch" in r.message for r in caplog.records)
