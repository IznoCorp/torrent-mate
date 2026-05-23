"""E2E tests for ``personalscraper library-init-canonical`` — CLI-level harness.

Covers smoke, dry-run, NFO-based canonical_provider bootstrap, idempotence,
and the CHECK-safe unsupported-provider filter (anidb regression guard).
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

from tests.commands._e2e_helpers import (
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"

# ── helpers ───────────────────────────────────────────────────────────────────


def _insert_media_item(
    conn: sqlite3.Connection,
    title: str = "My Show",
    kind: str = "show",
    year: int = 2020,
    category_id: str = "tv_shows",
    canonical_provider: str | None = None,
) -> int:
    """Insert a minimal media_item row and return its id."""
    now = 1700000000
    cursor = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, year, category_id,
            date_created, date_modified, canonical_provider
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (kind, title, title, year, category_id, now, now, canonical_provider),
    )
    conn.commit()
    return cursor.lastrowid


def _set_dispatch_path(conn: sqlite3.Connection, item_id: int, path: str) -> None:
    """Set the dispatch_path attribute on a media_item."""
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
        (item_id, path),
    )
    conn.commit()


def _tvshow_nfo_with_canonical(tvdb_id: str = "12345", canonical_type: str = "tvdb") -> str:
    r"""Return tvshow.nfo XML with a `<uniqueid default=\"true\">`."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tvshow>\n"
        "  <title>My Show</title>\n"
        f'  <uniqueid type="{canonical_type}" default="true">{tvdb_id}</uniqueid>\n'
        '  <uniqueid type="tmdb">67890</uniqueid>\n'
        "</tvshow>\n"
    )


def _run_init_canonical(args: list[str], config, db_path):
    """Run library-init-canonical with config patched."""
    cfg = make_test_config_with_db(config, db_path)
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        return run_cli(["library-init-canonical", *args])


# ── 1. Smoke ─────────────────────────────────────────────────────────────────


def test_init_canonical_help_exits_zero() -> None:
    """``library-init-canonical --help`` exits 0."""
    result = run_cli(["library-init-canonical", "--help"])
    assert result.exit_code == 0


# ── 2. Dry-run ───────────────────────────────────────────────────────────────


def test_init_canonical_dry_run_no_writes(tmp_path, test_config) -> None:
    """Dry-run reports counts but does not modify DB."""
    db_path = make_synthetic_db(tmp_path)

    # Seed an item with NULL canonical_provider.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, canonical_provider=None)
    conn.close()

    result = _run_init_canonical(["--dry-run"], test_config, db_path)
    assert result.exit_code == 0, result.output
    # Output is JSON from Rich console — check it contains dry_run=true.
    assert "dry_run" in result.output.replace("\n", "").replace(" ", "")

    # Verify canonical_provider was NOT changed.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    cp = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    conn.close()
    assert cp is None, f"Dry-run should not modify DB, got canonical_provider={cp}"


# ── 3. Realistic bootstrap ───────────────────────────────────────────────────


def test_init_canonical_populates_from_tvdb_nfo(tmp_path, test_config) -> None:
    """Items with a valid NFO get canonical_provider set from `<uniqueid default>."""
    db_path = make_synthetic_db(tmp_path)

    # Create media dir with tvshow.nfo on disk.
    show_dir = tmp_path / "MyShow"
    show_dir.mkdir()
    nfo_path = show_dir / "tvshow.nfo"
    nfo_path.write_text(_tvshow_nfo_with_canonical("12345", "tvdb"))

    # Seed media_item with dispatch_path pointing at the show dir.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, canonical_provider=None)
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    result = _run_init_canonical([], test_config, db_path)
    assert result.exit_code == 0, result.output
    assert "canonical_provider_populated" in result.output

    # Verify canonical_provider is now 'tvdb'.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    cp = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    conn.close()
    assert cp == "tvdb", f"Expected canonical_provider='tvdb', got {cp}"


# ── 4. Idempotence ───────────────────────────────────────────────────────────


def test_init_canonical_skips_items_with_existing_canonical(tmp_path, test_config) -> None:
    """Items that already have canonical_provider set are not overwritten."""
    db_path = make_synthetic_db(tmp_path)

    # Create two shows with NFOs.
    show_a = tmp_path / "ShowA"
    show_a.mkdir()
    (show_a / "tvshow.nfo").write_text(_tvshow_nfo_with_canonical("11111", "tvdb"))

    show_b = tmp_path / "ShowB"
    show_b.mkdir()
    # Show B's NFO claims tmdb as canonical, but we'll pre-set tvdb.
    (show_b / "tvshow.nfo").write_text(_tvshow_nfo_with_canonical("22222", "tmdb"))

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    # Item A: NULL → should be populated.
    item_a = _insert_media_item(conn, title="Show A", canonical_provider=None)
    _set_dispatch_path(conn, item_a, str(show_a))
    # Item B: already has 'tvdb' → should NOT be overwritten
    # even though the NFO says tmdb.
    item_b = _insert_media_item(conn, title="Show B", canonical_provider="tvdb")
    _set_dispatch_path(conn, item_b, str(show_b))
    conn.close()

    _run_init_canonical([], test_config, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    cp_a = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_a,)).fetchone()[0]
    cp_b = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_b,)).fetchone()[0]
    conn.close()
    assert cp_a == "tvdb", f"Item A should be populated as tvdb, got {cp_a}"
    assert cp_b == "tvdb", f"Item B pre-set as tvdb should NOT be overwritten, got {cp_b}"


# ── 5. Unsupported provider filter ───────────────────────────────────────────


def test_init_canonical_unsupported_provider_filtered(tmp_path, test_config) -> None:
    r"""Items with type='anidb' (unsupported) are skipped — no CHECK crash.

    Regression for the c83888d follow-up commit: live DBs crashed because
    NFOs with type='anidb' on <uniqueid default=\"true\"> were not caught,
    and the CHECK(canonical_provider IN ('tvdb','tmdb')) triggered mid-walk.
    """
    db_path = make_synthetic_db(tmp_path)

    # Create a show with an NFO whose default uniqueid type is 'anidb'.
    show_dir = tmp_path / "AnidbShow"
    show_dir.mkdir()
    nfo_path = show_dir / "tvshow.nfo"
    # Only an anidb uniqueid with default=true, no tvdb/tmdb fallback.
    nfo_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<tvshow>\n"
        "  <title>Anidb Show</title>\n"
        '  <uniqueid type="anidb" default="true">7777</uniqueid>\n'
        "</tvshow>\n"
    )

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    item_id = _insert_media_item(conn, title="Anidb Show", canonical_provider=None)
    _set_dispatch_path(conn, item_id, str(show_dir))
    conn.close()

    result = _run_init_canonical([], test_config, db_path)
    assert result.exit_code == 0, f"Should NOT crash on unsupported provider (anidb): {result.output}"

    # Verify the item was skipped (canonical_provider still NULL).
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    cp = conn.execute("SELECT canonical_provider FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    conn.close()
    assert cp is None, f"Item with anidb default should be skipped (cp still NULL), got {cp}"
