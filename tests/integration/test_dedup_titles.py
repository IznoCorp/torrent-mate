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

from tests.commands._e2e_helpers import make_synthetic_db, run_cli, seed_disk

_NFC = unicodedata.normalize
_NFD_TITLE = _NFC("NFD", "Fantômes contre fantômes")
_NFC_TITLE = _NFC("NFC", "Fantômes contre fantômes")


def _json_from(result: Any) -> dict[str, Any]:
    """Extract the last JSON object from CLI output (strips ANSI codes)."""
    raw = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    for match in re.finditer(r"\{", raw):
        try:
            data, end = json.JSONDecoder().raw_decode(raw[match.start() :])
        except json.JSONDecodeError:
            continue
        if not raw[match.start() + end :].strip():
            return data  # type: ignore[no-any-return]
    raise ValueError(f"No JSON in output: {result.output!r}")


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


# ── survivor holds the files; deletions are journaled ─────────────────────────

_FILES_DISPATCH = "/Volumes/Disk1/movies/Batman, le défi (1989)"
_BATMAN_NFC = _NFC("NFC", "Batman, le défi")
_BATMAN_NFD = _NFC("NFD", "Batman, le défi")


def _seed_group(db_path: Path, *, holders: tuple[bool, bool]) -> tuple[int, int]:
    """Seed an NFC/NFD duplicate pair: the older row first, then the newer-refreshed one.

    Args:
        db_path: Migrated database.
        holders: Whether ``(older, newer)`` holds a live ``media_file``.

    Returns:
        ``(older_id, newer_id)``.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    now = int(time.time())
    older = _insert_item(
        conn, _BATMAN_NFC, year=1989, date_metadata_refreshed=now - 1000, dispatch_path=_FILES_DISPATCH
    )
    newer = _insert_item(conn, _BATMAN_NFD, year=1989, date_metadata_refreshed=now, dispatch_path=_FILES_DISPATCH)
    disk_id = seed_disk(conn, "Disk1", Path("/Volumes/Disk1"))
    for item_id, holds in zip((older, newer), holders, strict=True):
        if holds:
            release_id = conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (item_id,)).lastrowid
            seed_media_file_on_disk_row(conn, disk_id, release_id, f"movies/Batman-{item_id}")
    conn.commit()
    conn.close()
    return older, newer


def seed_media_file_on_disk_row(conn: sqlite3.Connection, disk_id: int, release_id: int | None, rel_path: str) -> None:
    """Insert a live ``path`` + ``media_file`` row (no file on disk is needed).

    Args:
        conn: Open connection.
        disk_id: ``disk.id``.
        release_id: ``media_release.id`` the file belongs to.
        rel_path: Folder path under the disk.
    """
    path_id = conn.execute("INSERT INTO path (disk_id, rel_path) VALUES (?, ?)", (disk_id, rel_path)).lastrowid
    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
        " scan_generation, last_verified_at, deleted_at) VALUES (?, ?, 'movie.mkv', 1, 1, '0', 1, 1, NULL)",
        (release_id, path_id),
    )


def _ids(db_path: Path) -> set[int]:
    """Return the ``media_item`` ids still in the database."""
    conn = sqlite3.connect(str(db_path))
    try:
        return {r[0] for r in conn.execute("SELECT id FROM media_item")}
    finally:
        conn.close()


def _count(db_path: Path, table: str) -> int:
    """Return the row count of *table*."""
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def _dedup(db_path: Path, test_config: Any, *flags: str) -> dict[str, Any]:
    """Run ``library-dedup-titles`` on *db_path* and return its JSON output."""
    with patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), *flags])
    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    return _json_from(result)


def test_apply_keeps_the_older_row_that_holds_the_files_over_a_newer_phantom(tmp_path: Path, test_config: Any) -> None:
    """A newer-refreshed 0-file phantom must not outrank the older row holding the files."""
    db_path = make_synthetic_db(tmp_path)
    older, newer = _seed_group(db_path, holders=(True, False))

    data = _dedup(db_path, test_config, "--apply")

    assert data["deleted"] == 1
    assert _ids(db_path) == {older}, "the row holding the files survives, the phantom goes"
    assert _count(db_path, "media_file") == 1, "the files are still there"
    assert newer not in _ids(db_path)


def test_a_group_where_both_rows_hold_files_is_skipped_and_reported(tmp_path: Path, test_config: Any) -> None:
    """Two rows holding files: nothing is merged, the output and stats say so, dry run and apply alike."""
    db_path = make_synthetic_db(tmp_path)
    older, newer = _seed_group(db_path, holders=(True, True))

    for flags in ((), ("--apply",)):
        data = _dedup(db_path, test_config, *flags)
        assert data["deleted" if flags else "would_delete"] == 0
        assert data["skipped_both_hold_files"] == 1
        assert data["skipped_groups"] == [{"ids": [older, newer], "reason": "both_hold_files"}]
    assert _ids(db_path) == {older, newer}
    assert _count(db_path, "media_file") == 2


def test_apply_journals_every_deletion(tmp_path: Path, test_config: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each deleted row leaves a ``deleted_item`` tombstone and a ``destructive_op`` row with the runner's uid."""
    monkeypatch.setenv("PERSONALSCRAPER_RUN_UID", "run-abc")
    db_path = make_synthetic_db(tmp_path)
    older, newer = _seed_group(db_path, holders=(True, False))

    _dedup(db_path, test_config, "--apply")

    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT op, path, actor, run_uid FROM destructive_op").fetchall() == [
            ("delete", f"index:media_item/{newer}", "maintenance", "run-abc")
        ]
        assert conn.execute("SELECT kind, original_id, reason FROM deleted_item").fetchall() == [
            ("item", newer, "dedup_titles_removed")
        ]
    finally:
        conn.close()


def test_dry_run_plan_names_the_survivor_and_why_and_mutates_nothing(tmp_path: Path, test_config: Any) -> None:
    """The dry run lists, per group, the survivor and the reason; nothing is written or journaled."""
    db_path = make_synthetic_db(tmp_path)
    older, newer = _seed_group(db_path, holders=(True, False))

    data = _dedup(db_path, test_config)

    assert data["plan"] == [{"survivor": older, "reason": "holds_files", "deleted": [newer]}]
    assert _ids(db_path) == {older, newer}
    assert _count(db_path, "destructive_op") == 0
    assert _count(db_path, "deleted_item") == 0


def test_among_rows_holding_no_file_the_newest_refresh_survives_and_is_reported(
    tmp_path: Path, test_config: Any
) -> None:
    """With no file anywhere the old order stays: newest refresh wins, reason ``newest_refresh``."""
    db_path = make_synthetic_db(tmp_path)
    older, newer = _seed_group(db_path, holders=(False, False))

    data = _dedup(db_path, test_config, "--apply")

    assert data["plan"] == [{"survivor": newer, "reason": "newest_refresh", "deleted": [older]}]
    assert _ids(db_path) == {newer}
