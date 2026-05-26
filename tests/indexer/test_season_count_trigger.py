"""Regression tests for migration 008 — season.episode_count auto-maintenance via triggers.

Covers:
- Trigger increments episode_count on INSERT.
- Trigger decrements episode_count on DELETE.
- Trigger handles episode move between seasons (UPDATE OF season_id).
- Migration backfill corrects pre-existing drift.
- Idempotent re-apply (second apply_migrations is a no-op).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations, open_db

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _apply_scripts_through(conn: sqlite3.Connection, up_to_version: int) -> None:
    """Apply migration scripts 001..up_to_version manually via executescript.

    Args:
        conn: An open :class:`sqlite3.Connection`.
        up_to_version: Apply scripts with version <= this number.
    """
    scripts = sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    for script in scripts:
        version = int(script.name.split("_", 1)[0])
        if version > up_to_version:
            break
        sql = script.read_text(encoding="utf-8")
        conn.executescript(sql)


def _seed_show_and_season(conn: sqlite3.Connection, episode_count: int = 0) -> tuple[int, int]:
    """Insert a minimal show + season and return (show_id, season_id).

    Args:
        conn: An open :class:`sqlite3.Connection`.
        episode_count: Initial value for season.episode_count.

    Returns:
        A tuple of ``(show_id, season_id)``.
    """
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, external_ids_json, date_created, date_modified) "
        "VALUES ('show', 'Test Show', 'test show', 'tv_shows', '{}', 1, 1)"
    )
    show_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO season (item_id, number, episode_count) VALUES (?, 1, ?)",
        (show_id, episode_count),
    )
    season_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return show_id, season_id


class TestSeasonCountTrigger:
    """Triggers from migration 008 auto-maintain season.episode_count."""

    def test_trigger_increments_on_episode_insert(self, tmp_path: Path) -> None:
        """Inserting 3 episodes increments season.episode_count from 0 to 3."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, _MIGRATIONS_DIR)

        _show_id, season_id = _seed_show_and_season(conn, episode_count=0)

        for ep_num in range(1, 4):
            conn.execute(
                "INSERT INTO episode (season_id, number) VALUES (?, ?)",
                (season_id, ep_num),
            )

        row = conn.execute("SELECT episode_count FROM season WHERE id = ?", (season_id,)).fetchone()
        assert row[0] == 3

    def test_trigger_decrements_on_episode_delete(self, tmp_path: Path) -> None:
        """Deleting 1 of 3 episodes decrements episode_count from 3 to 2."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, _MIGRATIONS_DIR)

        _show_id, season_id = _seed_show_and_season(conn, episode_count=0)

        for ep_num in range(1, 4):
            conn.execute(
                "INSERT INTO episode (season_id, number) VALUES (?, ?)",
                (season_id, ep_num),
            )

        conn.execute("DELETE FROM episode WHERE season_id = ? AND number = 2", (season_id,))

        row = conn.execute("SELECT episode_count FROM season WHERE id = ?", (season_id,)).fetchone()
        assert row[0] == 2

    def test_trigger_handles_episode_season_move(self, tmp_path: Path) -> None:
        """Moving an episode between seasons updates both counts correctly."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, _MIGRATIONS_DIR)

        _show_id, s1_id = _seed_show_and_season(conn, episode_count=0)
        conn.execute(
            "INSERT INTO season (item_id, number, episode_count) VALUES (?, 2, 0)",
            (_show_id,),
        )
        s2_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("INSERT INTO episode (season_id, number) VALUES (?, 1)", (s1_id,))

        conn.execute(
            "UPDATE episode SET season_id = ? WHERE season_id = ? AND number = 1",
            (s2_id, s1_id),
        )

        s1_count = conn.execute("SELECT episode_count FROM season WHERE id = ?", (s1_id,)).fetchone()[0]
        s2_count = conn.execute("SELECT episode_count FROM season WHERE id = ?", (s2_id,)).fetchone()[0]
        assert s1_count == 0
        assert s2_count == 1

    def test_migration_008_backfills_existing_drift(self, tmp_path: Path) -> None:
        """One-shot backfill corrects season.episode_count=99 to 3 when 3 episodes exist."""
        db_path = tmp_path / "lib.db"
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        conn.execute("PRAGMA foreign_keys=ON")

        # Apply migrations 001-007 only (skip 008).
        _apply_scripts_through(conn, up_to_version=7)
        conn.execute("PRAGMA user_version = 7")

        _show_id, season_id = _seed_show_and_season(conn, episode_count=99)
        for ep_num in range(1, 4):
            conn.execute(
                "INSERT INTO episode (season_id, number) VALUES (?, ?)",
                (season_id, ep_num),
            )

        # Verify drift exists before migration 008.
        row = conn.execute("SELECT episode_count FROM season WHERE id = ?", (season_id,)).fetchone()
        assert row[0] == 99

        # Apply migration 008.
        apply_migrations(conn, _MIGRATIONS_DIR)

        # Drift must be corrected.
        row = conn.execute("SELECT episode_count FROM season WHERE id = ?", (season_id,)).fetchone()
        assert row[0] == 3

        conn.close()

    def test_idempotent_re_apply(self, tmp_path: Path) -> None:
        """Second apply_migrations call is a no-op — triggers are not duplicated."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, _MIGRATIONS_DIR)

        user_version_after_first = conn.execute("PRAGMA user_version").fetchone()[0]

        # Second apply must be a no-op.
        apply_migrations(conn, _MIGRATIONS_DIR)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == user_version_after_first

        # Each trigger must exist exactly once.
        triggers = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND name LIKE 'trg_season_episode_count%' ORDER BY name"
        ).fetchall()
        assert len(triggers) == 3
        assert [t[0] for t in triggers] == [
            "trg_season_episode_count_after_delete",
            "trg_season_episode_count_after_insert",
            "trg_season_episode_count_after_update",
        ]

    def test_trigger_handles_pre_populated_episode_count(self, tmp_path: Path) -> None:
        """Recompute trigger converges when scanner pre-populates episode_count.

        Pre-12.12.fix (inc/dec design): seeding episode_count=3 and inserting
        3 episode rows produced final episode_count=6 (double count).
        Post-12.12.fix (recompute): the AFTER INSERT trigger recomputes
        ``SELECT COUNT(*) FROM episode WHERE season_id = ?`` regardless of the
        cached value, so final episode_count is always 3.
        """
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, _MIGRATIONS_DIR)

        _show_id, season_id = _seed_show_and_season(conn, episode_count=3)

        for ep_num in range(1, 4):
            conn.execute(
                "INSERT INTO episode (season_id, number) VALUES (?, ?)",
                (season_id, ep_num),
            )

        final_count = conn.execute("SELECT episode_count FROM season WHERE id = ?", (season_id,)).fetchone()[0]
        assert final_count == 3
