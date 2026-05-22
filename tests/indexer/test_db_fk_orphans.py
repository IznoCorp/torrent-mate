"""open_db FK orphan pre-check tests (Phase 1.2 / DEV #19).

DEV #19 — audit BDD a observé ``PRAGMA foreign_keys = 0`` côté sqlite3 CLI
(per-connection default) et conclu que ``open_db()`` ne l'activait pas. C'est
en fait incorrect : le code à ``db.py:321`` l'active déjà depuis commit
``5a6397cd`` (2026-04-30). Le vrai gap n'est PAS l'activation, c'est l'absence
de **pre-check** ``PRAGMA foreign_key_check`` au boot — silencieusement, des
orphans peuvent vivre en BDD si quelqu'un a inséré sans FK enforcement actif
dans une autre connexion (sqlite3 CLI, scripts ad-hoc, etc.).

Phase 1.2 du plan tech-debt 0.16.0 ajoute :

1. Pre-check ``PRAGMA foreign_key_check;`` AVANT activation FK ON
2. Si orphans détectés → log + raise ``IndexerFKOrphansError`` (nouveau type,
   distinct de ``IndexerCorruptError`` qui adresse la corruption structurelle
   pas l'inconsistance de données)
3. Si zéro orphan → activation FK ON normale (état actuel préservé)

Tests dans ce fichier :

- ``test_open_db_succeeds_when_no_fk_orphans`` — clean DB → open_db OK, FK ON.
- ``test_open_db_raises_on_fk_orphans`` — seed orphan, open_db raise.
- ``test_fk_orphans_error_carries_orphan_count`` — diagnostique inclut count.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import (
    apply_migrations,
    open_db,
)

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


def _bootstrap_db_with_migrations(db_path: Path) -> None:
    """Create DB at *db_path* with all migrations applied and FK enforcement on."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    conn.close()


def _seed_disk_and_path(conn: sqlite3.Connection) -> tuple[int, int]:
    """Seed one disk + one path row, return their PKs (helper for orphan tests)."""
    cur = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk-uuid", "DiskA", "/tmp/fake", 0, None, 1, 0),
    )
    disk_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
        (disk_id, "fake/rel"),
    )
    path_id = cur.lastrowid
    return disk_id, path_id


def test_open_db_succeeds_when_no_fk_orphans(tmp_path: Path) -> None:
    """Fresh DB has no orphans → open_db returns a usable connection with FK ON.

    Baseline behavior pin: the FK pre-check must NOT break the happy path.
    """
    db_path = tmp_path / "library.db"
    _bootstrap_db_with_migrations(db_path)

    conn = open_db(db_path, event_bus=EventBus())
    try:
        # FK enforcement is active
        fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_on == 1, f"PRAGMA foreign_keys must return 1, got {fk_on}"

        # foreign_key_check on a clean DB returns zero rows
        orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert orphans == [], f"Fresh DB must have no FK orphans, got {orphans}"
    finally:
        conn.close()


def test_open_db_raises_on_fk_orphans(tmp_path: Path) -> None:
    """Seed an FK orphan, then open_db must raise IndexerFKOrphansError (Phase 1.2 strict).

    Scenario : we open the DB with FK enforcement OFF (simulating a script that
    bypassed open_db), insert a ``media_release`` row pointing to a non-existent
    ``item_id``, close, then call ``open_db()``. The new pre-check must detect
    the orphan and refuse to return a connection.
    """
    db_path = tmp_path / "library.db"
    _bootstrap_db_with_migrations(db_path)

    # Bypass open_db to seed an FK orphan with foreign_keys OFF
    raw = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        # media_release.item_id REFERENCES media_item(id) — insert with bogus item_id
        raw.execute(
            "INSERT INTO media_release (item_id, quality, edition, primary_lang) VALUES (?, ?, ?, ?)",
            (99999, "1080p", "Director's Cut", "fr"),
        )
    finally:
        raw.close()

    # Confirm the orphan really exists at the SQLite level
    probe = sqlite3.connect(str(db_path))
    try:
        orphans = probe.execute("PRAGMA foreign_key_check").fetchall()
        assert len(orphans) >= 1, f"Test setup failed: expected ≥1 FK orphan after seeding, got {orphans}"
    finally:
        probe.close()

    # Now open_db must refuse
    from personalscraper.indexer.db import IndexerFKOrphansError  # noqa: PLC0415

    with pytest.raises(IndexerFKOrphansError) as exc_info:
        open_db(db_path, event_bus=EventBus())

    assert exc_info.value.orphan_count >= 1, (
        f"IndexerFKOrphansError must expose orphan_count, got {exc_info.value.orphan_count}"
    )


def test_fk_orphans_error_carries_diagnostic(tmp_path: Path) -> None:
    """IndexerFKOrphansError message includes the count + db path for ops debugging.

    Without diagnostic info, an operator hit by this error at boot can't know
    where to look. Message must include at minimum the db_path and the orphan count.
    """
    db_path = tmp_path / "library.db"
    _bootstrap_db_with_migrations(db_path)

    raw = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        # Seed 2 orphans to make the count meaningful
        raw.execute(
            "INSERT INTO media_release (item_id, quality, edition, primary_lang) VALUES (?, ?, ?, ?)",
            (88888, "720p", "Original", "en"),
        )
        raw.execute(
            "INSERT INTO media_release (item_id, quality, edition, primary_lang) VALUES (?, ?, ?, ?)",
            (77777, "2160p", "Extended", "en"),
        )
    finally:
        raw.close()

    from personalscraper.indexer.db import IndexerFKOrphansError  # noqa: PLC0415

    with pytest.raises(IndexerFKOrphansError) as exc_info:
        open_db(db_path, event_bus=EventBus())

    msg = str(exc_info.value)
    assert str(db_path) in msg, f"Error message must include db_path, got: {msg!r}"
    assert "orphan" in msg.lower(), f"Error message must mention 'orphan', got: {msg!r}"
    assert exc_info.value.orphan_count == 2, f"Expected orphan_count=2, got {exc_info.value.orphan_count}"
