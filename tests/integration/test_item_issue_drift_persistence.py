"""Regression tests for persisting episode_naming_drift in item_issue.

Sub-phase 12.6 — DEVIATION #11 (P2 mineur).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.scraper._drift_persistence import DriftIssueStore

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _make_config(db_path: Path) -> SimpleNamespace:
    """Build a minimal config stub with only ``indexer.db_path`` populated."""
    idx = SimpleNamespace()
    idx.db_path = db_path
    cfg = SimpleNamespace()
    cfg.indexer = idx
    return cfg


def _seed_show(conn: sqlite3.Connection, show_dir: Path, title: str, art: bool) -> int:
    """Insert a media_item + item_attribute(dispatch_path) and return the item id."""
    now_s = int(time.time())
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
        "VALUES ('show', ?, ?, 'tv_shows', ?, ?)",
        (title, title, now_s, now_s),
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    if art:
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, str(show_dir.resolve())),
        )
    conn.commit()
    return item_id


class TestItemIssueDriftPersistence:
    """Verification that scrape drift is persisted and resolved in item_issue."""

    def test_drift_persists_item_issue(self, tmp_path: Path) -> None:
        """A detected drift inserts an item_issue row for audit trail."""
        db_path = tmp_path / "library.db"
        show_dir = tmp_path / "test_show"
        show_dir.mkdir()

        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        item_id = _seed_show(conn, show_dir, "Test Show", art=True)
        conn.close()

        config = _make_config(db_path)
        store = DriftIssueStore.from_config(config)
        assert store is not None
        store.persist(show_dir, "episode_naming_drift:test.mkv")

        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute(
            "SELECT * FROM item_issue WHERE item_id = ? AND type = 'episode_naming_drift'",
            (item_id,),
        ).fetchall()
        conn2.close()

        assert len(rows) == 1
        assert rows[0]["detail"] == "episode_naming_drift:test.mkv"
        assert rows[0]["detected_at"] > 0

    def test_drift_resolves_clears_item_issue(self, tmp_path: Path) -> None:
        """A successful rescrape clears the previously persisted drift row."""
        db_path = tmp_path / "library.db"
        show_dir = tmp_path / "test_show_2"
        show_dir.mkdir()

        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        item_id = _seed_show(conn, show_dir, "Test Show 2", art=True)
        now_s = int(time.time())
        conn.execute(
            "INSERT INTO item_issue (item_id, type, detail, detected_at) VALUES (?, 'episode_naming_drift', ?, ?)",
            (item_id, "episode_naming_drift:test.mkv", now_s),
        )
        conn.commit()
        conn.close()

        config = _make_config(db_path)
        store = DriftIssueStore.from_config(config)
        assert store is not None
        store.clear(show_dir)

        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute(
            "SELECT * FROM item_issue WHERE item_id = ? AND type = 'episode_naming_drift'",
            (item_id,),
        ).fetchall()
        conn2.close()

        assert len(rows) == 0

    def test_drift_persist_skipped_when_no_item(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """When no media_item row exists, no insert is attempted and a warning is logged."""
        db_path = tmp_path / "library.db"
        show_dir = tmp_path / "test_show_nonexistent"
        show_dir.mkdir()

        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        # Seed a show but NO dispatch_path attribute — the lookup will fail
        _seed_show(conn, show_dir, "Other Show", art=False)
        conn.close()

        config = _make_config(db_path)

        store = DriftIssueStore.from_config(config)
        assert store is not None

        with caplog.at_level(logging.INFO, logger="scraper"):
            store.persist(show_dir, "episode_naming_drift:test.mkv")

        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute("SELECT * FROM item_issue").fetchall()
        conn2.close()

        assert len(rows) == 0
        assert any("item_issue_persist_skipped_no_item" in r.message for r in caplog.records)

    def test_clear_db_connect_failure_is_logged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Connect failure in clear_drift_issue is logged (not swallowed silently)."""
        db_path = tmp_path / "library.db"
        db_path.write_text("")  # passes is_file() check
        show_dir = tmp_path / "test_show"
        show_dir.mkdir()

        # Make sqlite3.connect raise to simulate a connection failure
        monkeypatch.setattr(
            sqlite3,
            "connect",
            lambda *a, **kw: (_ for _ in ()).throw(OSError("Permission denied")),
        )

        config = _make_config(db_path)
        store = DriftIssueStore.from_config(config)
        assert store is not None
        with caplog.at_level(logging.WARNING, logger="scraper"):
            store.clear(show_dir)

        assert any("item_issue_db_connect_failed" in r.message for r in caplog.records)

    def test_clear_with_str_db_path_succeeds(self, tmp_path: Path) -> None:
        """db_path passed as str (not Path) is converted and clear works correctly."""
        db_path = tmp_path / "library.db"
        show_dir = tmp_path / "test_show_str"
        show_dir.mkdir()

        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        item_id = _seed_show(conn, show_dir, "Test Show Str", art=True)
        now_s = int(time.time())
        conn.execute(
            "INSERT INTO item_issue (item_id, type, detail, detected_at) VALUES (?, 'episode_naming_drift', ?, ?)",
            (item_id, "episode_naming_drift:test.mkv", now_s),
        )
        conn.commit()
        conn.close()

        config = _make_config(str(db_path))  # str, not Path
        store = DriftIssueStore.from_config(config)
        assert store is not None
        store.clear(show_dir)

        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute(
            "SELECT * FROM item_issue WHERE item_id = ? AND type = 'episode_naming_drift'",
            (item_id,),
        ).fetchall()
        conn2.close()

        assert len(rows) == 0
