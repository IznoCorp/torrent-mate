"""Regression tests for the ``library-dedup-titles`` CLI command (nfc-dedup).

Covers:
- dry-run: reports pairs, mutates nothing (row count unchanged).
- --apply: deletes orphan rows, keeps survivor, NFC-normalizes survivor title.
- --apply: preserves distinct year-variants (different year → different group).
- idempotence: second --apply pass reports 0 deletions.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tests.commands._e2e_helpers import make_synthetic_db, run_cli

_NFC = unicodedata.normalize
_NFD_TITLE = _NFC("NFD", "Fantômes contre fantômes")
_NFC_TITLE = _NFC("NFC", "Fantômes contre fantômes")


def _json_from(result: Any) -> dict[str, Any]:
    """Extract the last JSON object from CLI output (strips ANSI codes)."""
    raw = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    start = raw.rfind("{")
    if start == -1:
        raise ValueError(f"No JSON in output: {result.output!r}")
    return json.loads(raw[start:])


def _insert_item(
    conn: sqlite3.Connection,
    title: str,
    kind: str = "movie",
    year: int | None = 1996,
    date_metadata_refreshed: int | None = None,
    dispatch_path: str | None = None,
) -> int:
    """Insert a minimal ``media_item`` row and optional ``dispatch_path`` attribute.

    Args:
        conn: Open SQLite connection.
        title: Title to store verbatim (may be NFC or NFD).
        kind: ``'movie'`` or ``'show'``.
        year: Release year, or ``None``.
        date_metadata_refreshed: Epoch timestamp or ``None`` for orphan rows.
        dispatch_path: Value for ``item_attribute`` key ``'dispatch_path'``,
            or ``None``.

    Returns:
        The new ``media_item.id``.
    """
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO media_item "
        "(kind, title, title_sort, year, category_id, date_created, date_modified, "
        "date_metadata_refreshed) "
        "VALUES (?, ?, ?, ?, 'movies', ?, ?, ?)",
        (kind, title, title, year, now, now, date_metadata_refreshed),
    )
    item_id: int = cursor.lastrowid  # type: ignore[assignment]
    if dispatch_path is not None:
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, dispatch_path),
        )
    conn.commit()
    return item_id


@pytest.fixture()
def db_with_nfc_nfd_pair(tmp_path: Path) -> tuple[Path, int, int]:
    """DB seeded with an NFC/NFD duplicate pair on the same ``dispatch_path``.

    Returns:
        ``(db_path, nfc_id, nfd_id)`` — ``nfc_id`` is the live survivor (has
        ``date_metadata_refreshed``), ``nfd_id`` is the orphan (NULL).
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    dispatch = "/Volumes/Disk1/movies/Fantômes contre fantômes (1996)"
    now = int(time.time())
    nfc_id = _insert_item(
        conn,
        _NFC_TITLE,
        year=1996,
        date_metadata_refreshed=now,
        dispatch_path=dispatch,
    )
    nfd_id = _insert_item(
        conn,
        _NFD_TITLE,
        year=1996,
        date_metadata_refreshed=None,
        dispatch_path=dispatch,
    )
    conn.close()
    return db_path, nfc_id, nfd_id


@pytest.fixture()
def db_with_divergent_path_pair(tmp_path: Path) -> tuple[Path, int, int]:
    """DB seeded with an NFC/NFD duplicate pair with divergent dispatch_path strings.

    Same physical folder but NFC vs NFD normalization makes the raw path
    strings differ — exactly the real-world bug this feature must handle.

    Returns:
        ``(db_path, nfc_id, nfd_id)`` — ``nfc_id`` is the live survivor (has
        ``date_metadata_refreshed``), ``nfd_id`` is the orphan (NULL).
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    dispatch_nfc = "/Volumes/Disk1/movies/Fantômes contre fantômes (1996)"
    dispatch_nfd = _NFC("NFD", dispatch_nfc)
    now = int(time.time())
    nfc_id = _insert_item(
        conn,
        _NFC_TITLE,
        year=1996,
        date_metadata_refreshed=now,
        dispatch_path=dispatch_nfc,
    )
    nfd_id = _insert_item(
        conn,
        _NFD_TITLE,
        year=1996,
        date_metadata_refreshed=None,
        dispatch_path=dispatch_nfd,
    )
    conn.close()
    return db_path, nfc_id, nfd_id


@pytest.fixture()
def db_with_year_variants(tmp_path: Path) -> tuple[Path, int, int]:
    """DB seeded with two items sharing the same base title but different years.

    These must NOT be merged by ``--apply`` (distinct year-variants / remakes).

    Returns:
        ``(db_path, id_2001, id_2026)``
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    id_2001 = _insert_item(
        conn,
        "Scrubs",
        kind="show",
        year=2001,
        date_metadata_refreshed=now,
        dispatch_path="/Volumes/Disk1/shows/Scrubs (2001)",
    )
    id_2026 = _insert_item(
        conn,
        "Scrubs",
        kind="show",
        year=2026,
        date_metadata_refreshed=now,
        dispatch_path="/Volumes/Disk1/shows/Scrubs (2026)",
    )
    conn.close()
    return db_path, id_2001, id_2026


@pytest.fixture()
def db_with_solo_nfd_title(tmp_path: Path) -> tuple[Path, int, str, str]:
    """DB seeded with a single NFD-titled row (no duplicate twin).

    Returns:
        ``(db_path, item_id, nfd_title, nfc_title)``
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    nfd_title = _NFC("NFD", "Amélie")
    nfc_title = _NFC("NFC", "Amélie")
    assert nfd_title != nfc_title, "NFD form must differ from NFC for this test"
    now = int(time.time())
    item_id = _insert_item(
        conn,
        nfd_title,
        year=2001,
        date_metadata_refreshed=now,
        dispatch_path="/Volumes/Disk1/movies/Amélie (2001)",
    )
    conn.close()
    return db_path, item_id, nfd_title, nfc_title


def test_apply_dedups_nfc_nfd_divergent_dispatch_paths(
    db_with_divergent_path_pair: tuple[Path, int, int],
    test_config: Any,
) -> None:
    """--apply deduplicates NFC/NFD twins even when dispatch_path strings differ by normalization."""
    db_path, nfc_id, nfd_id = db_with_divergent_path_pair

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    data = _json_from(result)
    assert data["deleted"] >= 1, f"Expected ≥1 deleted, got {data}"
    assert data["duplicate_groups"] >= 1, f"Expected ≥1 duplicate_groups, got {data}"
    assert data.get("skipped", 0) == 0, f"Expected 0 skipped, got {data}"

    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (nfd_id,)).fetchone() is None, (
        f"Orphan row id={nfd_id} must be deleted"
    )
    survivor = conn.execute("SELECT title FROM media_item WHERE id = ?", (nfc_id,)).fetchone()
    assert survivor is not None, f"Survivor row id={nfc_id} must exist"
    assert survivor[0] == _NFC("NFC", survivor[0]), "Survivor title must be NFC"
    conn.close()


def test_dry_run_reports_pairs_and_mutates_nothing(
    db_with_nfc_nfd_pair: tuple[Path, int, int],
    test_config: Any,
) -> None:
    """dry-run outputs the duplicate group and leaves the DB unchanged."""
    db_path, _nfc_id, _nfd_id = db_with_nfc_nfd_pair
    conn = sqlite3.connect(str(db_path))
    before = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path)])

    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    data = _json_from(result)
    assert data["apply"] is False
    assert data["would_delete"] >= 1
    assert data["duplicate_groups"] >= 1

    conn = sqlite3.connect(str(db_path))
    after = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    conn.close()
    assert after == before, f"dry-run must not mutate DB ({before} → {after})"


def test_apply_deletes_orphan_keeps_survivor(
    db_with_nfc_nfd_pair: tuple[Path, int, int],
    test_config: Any,
) -> None:
    """--apply deletes the NFD orphan and keeps the NFC live row."""
    db_path, nfc_id, nfd_id = db_with_nfc_nfd_pair

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    assert _json_from(result)["deleted"] >= 1

    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (nfd_id,)).fetchone() is None, (
        f"Orphan row id={nfd_id} must be deleted"
    )
    survivor = conn.execute("SELECT title FROM media_item WHERE id = ?", (nfc_id,)).fetchone()
    assert survivor is not None, f"Survivor row id={nfc_id} must exist"
    assert survivor[0] == _NFC("NFC", survivor[0]), "Survivor title must be NFC"
    conn.close()


def test_apply_preserves_distinct_year_variants(
    db_with_year_variants: tuple[Path, int, int],
    test_config: Any,
) -> None:
    """--apply never merges items with different explicit years (remake guard)."""
    db_path, id_2001, id_2026 = db_with_year_variants
    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])
    assert result.exit_code == 0

    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (id_2001,)).fetchone() is not None
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (id_2026,)).fetchone() is not None
    conn.close()


def test_apply_idempotent(
    db_with_nfc_nfd_pair: tuple[Path, int, int],
    test_config: Any,
) -> None:
    """Running --apply twice reports 0 on the second pass."""
    db_path, _nfc_id, _nfd_id = db_with_nfc_nfd_pair
    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        run_cli(["library-dedup-titles", "--db", str(db_path), "--apply"])

        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0
    data = _json_from(result)
    assert data["deleted"] == 0
    assert data["duplicate_groups"] == 0


def test_apply_skips_divergent_real_folders(
    tmp_path: Path,
    test_config: Any,
) -> None:
    """--apply skips a group whose members point to genuinely different real folders."""
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    # Use NFD vs NFC to get the same canonical key with different raw strings.
    id_a = _insert_item(
        conn,
        _NFC_TITLE,
        year=1984,
        date_metadata_refreshed=now,
        dispatch_path="/Volumes/Disk1/movies/X (1984)",
    )
    id_b = _insert_item(
        conn,
        _NFD_TITLE,
        year=1984,
        date_metadata_refreshed=now,
        dispatch_path="/Volumes/Disk1/movies/Y (1984)",
    )
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    data = _json_from(result)
    assert data["deleted"] == 0, f"Expected 0 deleted for divergent folders, got {data}"
    assert data.get("skipped", 0) >= 1, f"Expected ≥1 skipped, got {data}"

    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (id_a,)).fetchone() is not None, (
        f"Row id={id_a} must survive (different real folder)"
    )
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (id_b,)).fetchone() is not None, (
        f"Row id={id_b} must survive (different real folder)"
    )
    conn.close()


def test_apply_skips_partial_none_dispatch_path(
    tmp_path: Path,
    test_config: Any,
) -> None:
    """--apply skips a group where one row has a dispatch_path and the other has None.

    This locks the F1 fix: before the fix the guard ``if p is not None``
    would make the missing path invisible, keep the path-less row, and
    cascade-delete the verifiable one.
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    # Path-bearing row (orphan, NFD title — no date_metadata_refreshed)
    id_path = _insert_item(
        conn,
        _NFD_TITLE,
        year=1996,
        date_metadata_refreshed=None,
        dispatch_path="/Volumes/Disk1/movies/Fantômes contre fantômes (1996)",
    )
    # Path-less row (live, NFC title — has date_metadata_refreshed, higher id)
    id_nopath = _insert_item(
        conn,
        _NFC_TITLE,
        year=1996,
        date_metadata_refreshed=now,
        dispatch_path=None,
    )
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    data = _json_from(result)
    assert data.get("skipped", 0) >= 1, f"Expected ≥1 skipped for partial-None group, got {data}"
    assert data["deleted"] == 0, f"Expected 0 deleted (partial-None → skip), got {data}"

    # The path-bearing row must NOT be deleted — that's the critical assertion.
    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (id_path,)).fetchone() is not None, (
        f"Path-bearing row id={id_path} must NOT be deleted (partial-None → skip)"
    )
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (id_nopath,)).fetchone() is not None, (
        f"Path-less row id={id_nopath} must survive too"
    )
    conn.close()


def test_apply_cascade_removes_children(
    db_with_nfc_nfd_pair: tuple[Path, int, int],
    test_config: Any,
) -> None:
    """--apply CASCADE-deletes child rows (item_attribute) of the removed orphan."""
    db_path, nfc_id, nfd_id = db_with_nfc_nfd_pair

    # Seed a child row (item_attribute) on the orphan that should be cascade-deleted.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT OR REPLACE INTO item_attribute (item_id, key, value) VALUES (?, 'test_key', 'test_value')",
        (nfd_id,),
    )
    conn.commit()
    # Verify the child exists before --apply.
    assert (
        conn.execute(
            "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'test_key'",
            (nfd_id,),
        ).fetchone()
        is not None
    )
    conn.close()

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    data = _json_from(result)
    assert data["deleted"] >= 1, f"Expected ≥1 deleted, got {data}"

    conn = sqlite3.connect(str(db_path))
    # Orphan row gone.
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (nfd_id,)).fetchone() is None
    # Child item_attribute row must also be gone (CASCADE fired).
    assert (
        conn.execute(
            "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'test_key'",
            (nfd_id,),
        ).fetchone()
        is None
    ), f"Child item_attribute row for orphan id={nfd_id} must be cascade-deleted"
    # Survivor still present.
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (nfc_id,)).fetchone() is not None
    conn.close()


def test_apply_idempotent_normalized_zero(
    db_with_nfc_nfd_pair: tuple[Path, int, int],
    test_config: Any,
) -> None:
    """Second --apply pass reports normalized==0 (idempotent)."""
    db_path, _nfc_id, _nfd_id = db_with_nfc_nfd_pair

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        run_cli(["library-dedup-titles", "--db", str(db_path), "--apply"])

        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0
    data = _json_from(result)
    assert data["deleted"] == 0
    assert data["duplicate_groups"] == 0
    assert data.get("normalized", 0) == 0, f"Expected normalized==0 on second pass (already NFC), got {data}"


def test_apply_normalizes_solo_nfd_title(
    db_with_solo_nfd_title: tuple[Path, int, str, str],
    test_config: Any,
) -> None:
    """--apply NFC-normalizes a solo NFD-titled row (no duplicate, no deletion)."""
    db_path, item_id, _nfd_title, nfc_title = db_with_solo_nfd_title

    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    data = _json_from(result)
    assert data["deleted"] == 0, f"Expected 0 deleted, got {data}"
    assert data["normalized"] >= 1, f"Expected ≥1 normalized, got {data}"

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT title FROM media_item WHERE id = ?", (item_id,)).fetchone()
    assert row is not None, f"Row id={item_id} must still exist"
    assert row[0] == nfc_title, f"Title must be NFC: {row[0]!r} != {nfc_title!r}"
    conn.close()
