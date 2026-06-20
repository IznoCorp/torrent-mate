# Phase 02a — Failing tests for `library-dedup-titles`

## Gate

Phase 1 must be merged-ready:

- `personalscraper/indexer/repos/item_repo.py` — `_canonical_title` NFC-normalizes.
- `tests/indexer/test_canonical_title_nfc.py` — 2 regression tests green.
- `make test` passes with 0 failures.

## Goal

Write 4 failing tests (TDD red) that will drive the `library-dedup-titles` command
implementation in phase 02b. Tests live in `tests/integration/test_dedup_titles.py`.

## Files

- Create: `tests/integration/test_dedup_titles.py`

---

### Sub-phase 2.1 — Write failing tests

**Commit:** `test(nfc-dedup): red tests — library-dedup-titles dry-run + apply`

- [ ] **Step 1: Create `tests/integration/test_dedup_titles.py`**

```python
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
        conn, _NFC_TITLE, year=1996, date_metadata_refreshed=now, dispatch_path=dispatch,
    )
    nfd_id = _insert_item(
        conn, _NFD_TITLE, year=1996, date_metadata_refreshed=None, dispatch_path=dispatch,
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
        conn, "Scrubs", kind="show", year=2001, date_metadata_refreshed=now,
        dispatch_path="/Volumes/Disk1/shows/Scrubs (2001)",
    )
    id_2026 = _insert_item(
        conn, "Scrubs", kind="show", year=2026, date_metadata_refreshed=now,
        dispatch_path="/Volumes/Disk1/shows/Scrubs (2026)",
    )
    conn.close()
    return db_path, id_2001, id_2026


def test_dry_run_reports_pairs_and_mutates_nothing(
    db_with_nfc_nfd_pair: tuple[Path, int, int], test_config: Any,
) -> None:
    """dry-run outputs the duplicate group and leaves the DB unchanged."""
    db_path, _nfc_id, _nfd_id = db_with_nfc_nfd_pair
    conn = sqlite3.connect(str(db_path))
    before = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    conn.close()

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
    db_with_nfc_nfd_pair: tuple[Path, int, int], test_config: Any,
) -> None:
    """--apply deletes the NFD orphan and keeps the NFC live row."""
    db_path, nfc_id, nfd_id = db_with_nfc_nfd_pair

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
    db_with_year_variants: tuple[Path, int, int], test_config: Any,
) -> None:
    """--apply never merges items with different explicit years (remake guard)."""
    db_path, id_2001, id_2026 = db_with_year_variants
    result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])
    assert result.exit_code == 0

    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (id_2001,)).fetchone() is not None
    assert conn.execute("SELECT id FROM media_item WHERE id = ?", (id_2026,)).fetchone() is not None
    conn.close()


def test_apply_idempotent(
    db_with_nfc_nfd_pair: tuple[Path, int, int], test_config: Any,
) -> None:
    """Running --apply twice reports 0 on the second pass."""
    db_path, _nfc_id, _nfd_id = db_with_nfc_nfd_pair
    run_cli(["library-dedup-titles", "--db", str(db_path), "--apply"])

    result = run_cli(["--format", "json", "library-dedup-titles", "--db", str(db_path), "--apply"])

    assert result.exit_code == 0
    data = _json_from(result)
    assert data["deleted"] == 0
    assert data["duplicate_groups"] == 0
```

- [ ] **Step 2: Run tests to verify they FAIL (red)**

```bash
python -m pytest tests/integration/test_dedup_titles.py -v 2>&1 | tail -10
```

Expected: all 4 tests FAIL — the `library-dedup-titles` command does not exist yet.

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/integration/test_dedup_titles.py
git commit -m "test(nfc-dedup): red tests — library-dedup-titles dry-run + apply"
```
