# Phase 01 — Root-cause fix: NFC-normalize `_canonical_title`

## Gate

Previous phase: none — this is the first phase.

## Goal

Add `unicodedata.normalize("NFC", ...)` inside `_canonical_title()` so that
NFD folder names from macOS `iterdir()` are stored and looked up as NFC, matching
the existing NFC rows. Locked with 2 mandatory regression tests (TDD red→green).

## Files

- Modify: `personalscraper/indexer/repos/item_repo.py` (lines ~12-14, ~61)
- Create: `tests/indexer/test_canonical_title_nfc.py`

---

### Sub-phase 1.1 — Write failing regression tests

**Commit:** `test(nfc-dedup): red tests — _canonical_title NFC + upsert no-dup`

- [ ] **Step 1: Create the test file**

```python
# tests/indexer/test_canonical_title_nfc.py
"""Regression tests for NFD/NFC duplicate-row bug (nfc-dedup).

Bug: _canonical_title() did not Unicode-normalize, so an NFD folder name
(macOS iterdir()) missed the existing NFC row and caused a duplicate INSERT.

Test (a): _canonical_title NFC-normalizes an NFD+year input.
Test (b): upsert with an NFD title when an NFC row already exists performs
          UPDATE (no second row) — reproduces the bug, must pass after fix.
"""

from __future__ import annotations

import sqlite3
import time
import unicodedata
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.schema import MediaItemRow

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# NFC precomposed: "Fantômes (1996)" (ô = U+00F4, single codepoint)
_NFC_TITLE_WITH_YEAR = unicodedata.normalize("NFC", "Fantômes (1996)")
# NFD decomposed: same string with ô decomposed to o + combining circumflex
_NFD_TITLE_WITH_YEAR = unicodedata.normalize("NFD", "Fantômes (1996)")
# Expected canonical (NFC base, no year suffix)
_NFC_BASE = unicodedata.normalize("NFC", "Fantômes")


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with all migrations applied.

    Returns:
        An open :class:`sqlite3.Connection`.
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, _MIGRATIONS_DIR)
    return c


def _make_item(title: str, year: int | None = 1996) -> MediaItemRow:
    """Return a minimal MediaItemRow for testing.

    Args:
        title: Display title (may be NFC or NFD).
        year: Release year.

    Returns:
        Populated :class:`MediaItemRow` ready for insertion.
    """
    now = int(time.time())
    return MediaItemRow(
        id=0,
        kind="movie",
        title=title,
        title_sort=title,
        original_title=None,
        year=year,
        category_id="movies",
        external_ids_json="{}",
        ratings_json=None,
        canonical_provider=None,
        nfo_status=None,
        artwork_json=None,
        date_created=now,
        date_modified=now,
        date_metadata_refreshed=None,
        is_locked=0,
        preferred_lang="fr",
    )


# ---------------------------------------------------------------------------
# Test (a): _canonical_title NFC-normalizes
# ---------------------------------------------------------------------------


def test_canonical_title_nfc_normalizes_nfd_input() -> None:
    """_canonical_title with NFD+year input returns NFC base (no year, NFC).

    Reproduces the root cause: before the fix, _canonical_title returned
    an NFD string, causing the DB lookup to miss the NFC row.
    """
    result = item_repo._canonical_title(_NFD_TITLE_WITH_YEAR)
    assert result == _NFC_BASE, (
        f"Expected NFC base {_NFC_BASE!r} (len={len(_NFC_BASE)}), "
        f"got {result!r} (len={len(result)})"
    )
    # Also verify the result is truly NFC-normalized.
    assert result == unicodedata.normalize("NFC", result), "Result must be NFC"


# ---------------------------------------------------------------------------
# Test (b): upsert with NFD title does not create a duplicate row
# ---------------------------------------------------------------------------


def test_upsert_nfd_title_updates_existing_nfc_row(conn: sqlite3.Connection) -> None:
    """Upsert with NFD title when NFC row exists → UPDATE (no duplicate INSERT).

    Reproduces the production bug:
    - Seed: insert an NFC row (as stored in DB from initial scan).
    - Act: call upsert() with an NFD title (as returned by macOS iterdir()).
    - Assert: still exactly 1 row — the upsert matched and updated the NFC row.
    """
    # Seed: insert via item_repo.insert so _canonical_title is bypassed — we
    # want the stored title to be NFC as it would be from an original NFC scan.
    nfc_item = _make_item(_NFC_TITLE_WITH_YEAR)
    original_id = item_repo.upsert(conn, nfc_item)

    # Act: upsert with an NFD title (simulates macOS iterdir() decomposed name).
    nfd_item = _make_item(_NFD_TITLE_WITH_YEAR)
    result_id = item_repo.upsert(conn, nfd_item)

    # Assert: same row, no duplicate.
    count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'movie'").fetchone()[0]
    assert count == 1, f"Expected 1 row (UPDATE), got {count} rows (duplicate INSERT!)"
    assert result_id == original_id, (
        f"Expected same row id={original_id}, got id={result_id}"
    )

    # Stored title must be NFC-normalized.
    stored = item_repo.get_by_id(conn, result_id)
    assert stored is not None
    assert stored.title == _NFC_BASE, f"Stored title must be NFC base, got {stored.title!r}"
```

- [ ] **Step 2: Run tests to verify they FAIL (red)**

```bash
cd /Users/izno/dev/PersonnalScaper
python -m pytest tests/indexer/test_canonical_title_nfc.py -v 2>&1 | tail -20
```

Expected: both tests FAIL. `test_canonical_title_nfc_normalizes_nfd_input` fails
because `_canonical_title` returns NFD. `test_upsert_nfd_title_updates_existing_nfc_row`
fails with `count == 2` (duplicate INSERT).

---

### Sub-phase 1.2 — Fix `_canonical_title` and make tests green

**Commit:** `fix(nfc-dedup): NFC-normalize _canonical_title — stop NFD duplicate rows`

- [ ] **Step 3: Add `unicodedata` import to `item_repo.py`**

Current imports (lines ~12-14):

```python
import re
import sqlite3
```

Add `unicodedata` on the line after `import re`:

```python
import re
import sqlite3
import unicodedata
```

File: `personalscraper/indexer/repos/item_repo.py`

- [ ] **Step 4: NFC-normalize in `_canonical_title`**

Current body (line ~61):

```python
    return _CANONICAL_RE.sub("", title)
```

Replace with:

```python
    stripped = _CANONICAL_RE.sub("", title)
    return unicodedata.normalize("NFC", stripped)
```

File: `personalscraper/indexer/repos/item_repo.py`

- [ ] **Step 5: Run tests to verify they PASS (green)**

```bash
python -m pytest tests/indexer/test_canonical_title_nfc.py -v 2>&1 | tail -10
```

Expected: `2 passed`.

- [ ] **Step 6: Smoke-test: ACC-1 shell command**

```bash
python -c "import unicodedata as u; from personalscraper.indexer.repos.item_repo import _canonical_title; print(_canonical_title(u.normalize('NFD','Fantômes (1996)')) == u.normalize('NFC','Fantômes'))"
```

Expected: `True`

- [ ] **Step 7: Full regression suite**

```bash
make test 2>&1 | tail -3
```

Expected: `NNNN passed` with 0 failed / 0 errors.

- [ ] **Step 8: Lint**

```bash
make lint 2>&1 | tail -5
```

Expected: zero errors.

- [ ] **Step 9: Commit**

```bash
git add tests/indexer/test_canonical_title_nfc.py personalscraper/indexer/repos/item_repo.py
git commit -m "$(cat <<'EOF'
fix(nfc-dedup): NFC-normalize _canonical_title — stop NFD duplicate rows

macOS iterdir() returns NFD folder names; DB stores NFC titles.
_canonical_title() now normalizes to NFC so NFD lookups match
existing NFC rows → no duplicate INSERT on accented-title scans.
Locked by 2 regression tests (test_canonical_title_nfc.py).
EOF
)"
```
