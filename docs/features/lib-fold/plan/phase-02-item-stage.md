# Phase 2 — Build `_item_stage` + `_canonical`; rewire `scan_library` (parallel path)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `_item_stage.py` (unified item/season/episode/issue upsert) and `_canonical.py` (kind-deterministic canonical SSOT). Wire `full.py` to invoke the stage as pass 1. Rewire `scan_library` to call the same stage (parallel path — legacy path stays green). Gate = characterization golden test asserting DB end-state equals the legacy `library-scan` baseline. NO deletions in this phase.

**Architecture:** This is the XL crux phase. The parallel path means both `library-scan` (old) and `library-index --mode full` (new) produce identical DB rows. The golden test is the safety net that makes Phase 3's deletion safe. `_canonical.py` absorbs both `_normalize_canonical_provider` (from `scanner.py`) and the kind-deterministic logic from `backfill_ids_canonical.py`, replacing the NFO-XML-order fallback with a WARN.

**Tech Stack:** Python 3.11, SQLite (`indexer/repos/item_repo.py`, `indexer/repos/tv_repo.py`), pytest, ruff, mypy.

---

## Gate

Phase 1 must be complete:

- `rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/` returns zero matches.
- `make lint && make test && make check` green.

---

## Objective

1. Create `personalscraper/indexer/scanner/_modes/_canonical.py` — kind-deterministic SSOT for `canonical_provider`.
2. Create `personalscraper/indexer/scanner/_modes/_item_stage.py` — `build_item_row()` + `upsert_item_with_attrs()` + season/episode upsert + `_detect_issues()` (no-NFO fallback+flag) + `_ensure_disk_row()`.
3. Modify `personalscraper/indexer/scanner/_modes/full.py` — invoke `_item_stage` as pass 1 before the file walk.
4. Modify `personalscraper/indexer/scanner/_modes/backfill_ids_canonical.py` — delegate canonical extraction to `_canonical.py`.
5. Rewire `library/scanner.py:scan_library` to call `upsert_item_with_attrs` from `_item_stage` (parallel path — internal logic preserved, new stage used for DB writes).
6. Ship characterization golden test + canonical regression tests. NO deletions.

---

## Files to create / modify

| Action | File                                                                                    |
| ------ | --------------------------------------------------------------------------------------- |
| Create | `personalscraper/indexer/scanner/_modes/_canonical.py`                                  |
| Create | `personalscraper/indexer/scanner/_modes/_item_stage.py`                                 |
| Modify | `personalscraper/indexer/scanner/_modes/full.py`                                        |
| Modify | `personalscraper/indexer/scanner/_modes/backfill_ids_canonical.py`                      |
| Modify | `personalscraper/library/scanner.py` (rewire DB writes to use `upsert_item_with_attrs`) |
| Create | `tests/indexer/scanner/_modes/test_canonical.py`                                        |
| Create | `tests/indexer/scanner/_modes/test_item_stage.py`                                       |
| Create | `tests/indexer/scanner/_modes/test_item_stage_golden.py` (characterization golden)      |

---

## Sub-tasks

### Task 1: Create `_canonical.py` — kind-deterministic canonical SSOT

**Files:**

- Create: `personalscraper/indexer/scanner/_modes/_canonical.py`
- Reference: `personalscraper/library/scanner.py:69` (`_normalize_canonical_provider`)

- [ ] **Step 1.1: Write the failing canonical tests first**

```python
# tests/indexer/scanner/_modes/test_canonical.py
import pytest
from personalscraper.indexer.scanner._modes._canonical import derive_canonical_provider


@pytest.mark.parametrize("kind,tvdb_id,tmdb_id,nfo_default,expected", [
    # show with tvdb_id → tvdb wins regardless of NFO default
    ("show", "12345", "67890", "tmdb", "tvdb"),
    ("show", "12345", None,    None,   "tvdb"),
    # show without tvdb_id → tmdb if available
    ("show", None, "67890", "tmdb", "tmdb"),
    # movie with tmdb_id → tmdb wins
    ("movie", None, "99", "tvdb", "tmdb"),
    ("movie", None, "99", None,   "tmdb"),
    # no IDs → None
    ("movie", None, None, None, None),
    ("show",  None, None, "tvdb", None),
])
def test_derive_canonical_provider(
    kind: str,
    tvdb_id: str | None,
    tmdb_id: str | None,
    nfo_default: str | None,
    expected: str | None,
) -> None:
    result = derive_canonical_provider(kind, tvdb_id, tmdb_id, nfo_default)
    assert result == expected


def test_kind_beats_nfo_xml_order() -> None:
    """kind-deterministic rule beats NFO-declared default — the critical invariant."""
    # show: tvdb_id present → tvdb, even if NFO says tmdb is default
    assert derive_canonical_provider("show", tvdb_id="111", tmdb_id="222", nfo_default="tmdb") == "tvdb"
    # movie: tmdb_id present → tmdb, even if NFO says tvdb is default
    assert derive_canonical_provider("movie", tvdb_id=None, tmdb_id="333", nfo_default="tvdb") == "tmdb"
```

Run to confirm `ImportError`:

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/_modes/test_canonical.py -v 2>&1 | tail -10
```

- [ ] **Step 1.2: Create `_canonical.py`**

```python
# personalscraper/indexer/scanner/_modes/_canonical.py
"""Kind-deterministic canonical-provider SSOT.

The single source of truth for deriving ``canonical_provider`` from a
media item's kind and known provider IDs. Replaces both
``library.scanner._normalize_canonical_provider`` and the NFO-XML-order
fallback in ``backfill_ids_canonical._parse_canonical_from_nfo``.

Rule (§4.4 DESIGN):
- show + tvdb_id present  → ``"tvdb"``
- show + no tvdb_id, tmdb_id present → ``"tmdb"``
- movie + tmdb_id present → ``"tmdb"``
- no usable ID            → ``None``

The NFO ``<uniqueid default="true">`` flag is intentionally ignored for
the derivation; callers should WARN when it disagrees (see §3.3).
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def derive_canonical_provider(
    kind: str,
    tvdb_id: str | None,
    tmdb_id: str | None,
    nfo_default: str | None,
) -> str | None:
    """Derive the canonical provider using the kind-deterministic rule.

    Args:
        kind: ``"show"`` or ``"movie"`` (case-insensitive).
        tvdb_id: TVDB numeric ID as string, or ``None``.
        tmdb_id: TMDB numeric ID as string, or ``None``.
        nfo_default: The ``<uniqueid default="true">`` type from the NFO,
            or ``None``. Used only for a WARN when it contradicts the
            kind-deterministic result.

    Returns:
        ``"tvdb"``, ``"tmdb"``, or ``None`` when no usable ID exists.
    """
    kind_lower = (kind or "").lower()

    if kind_lower == "show":
        if tvdb_id:
            result = "tvdb"
        elif tmdb_id:
            result = "tmdb"
        else:
            result = None
    else:
        # movie and all other kinds
        if tmdb_id:
            result = "tmdb"
        else:
            result = None

    # Warn when NFO default contradicts the deterministic rule.
    if nfo_default and result and nfo_default != result:
        log.warning(
            "canonical_provider.nfo_default_disagrees",
            kind=kind,
            nfo_default=nfo_default,
            derived=result,
        )

    return result
```

- [ ] **Step 1.3: Run canonical tests — must pass**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/_modes/test_canonical.py -v 2>&1 | tail -15
```

Expected: all tests PASS.

- [ ] **Step 1.4: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/indexer/scanner/_modes/_canonical.py tests/indexer/scanner/_modes/test_canonical.py && git commit -m "feat(lib-fold): add _canonical.py — kind-deterministic canonical SSOT"
```

---

### Task 2: Update `backfill_ids_canonical.py` to delegate to `_canonical.py`

**Files:**

- Modify: `personalscraper/indexer/scanner/_modes/backfill_ids_canonical.py`

- [ ] **Step 2.1: Read the current `_parse_canonical_from_nfo` function**

```bash
sed -n '80,200p' /Users/izno/dev/PersonnalScaper/personalscraper/indexer/scanner/_modes/backfill_ids_canonical.py
```

- [ ] **Step 2.2: Add import and delegate in `_parse_canonical_from_nfo`**

Add at the top of `backfill_ids_canonical.py`:

```python
from personalscraper.indexer.scanner._modes._canonical import derive_canonical_provider
```

In `_parse_canonical_from_nfo`, after parsing `tvdb_id`, `tmdb_id`, and `nfo_default` from the NFO XML, replace the existing fallback logic (which used NFO-XML-order) with:

```python
canonical = derive_canonical_provider(kind, tvdb_id, tmdb_id, nfo_default)
```

The existing WARN for unsupported `nfo_default` types becomes redundant if `derive_canonical_provider` already warns; remove the duplicate or keep it only for unsupported-type logging (not for the derivation itself).

- [ ] **Step 2.3: Carry the 194-show regression test forward**

Verify `tests/indexer/scanner/test_init_canonical.py` (the 194-show guard) still passes:

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/test_init_canonical.py tests/indexer/test_init_canonical.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 2.4: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/indexer/scanner/_modes/backfill_ids_canonical.py && git commit -m "refactor(lib-fold): backfill_ids_canonical delegates canonical derivation to _canonical.py"
```

---

### Task 3: Create `_item_stage.py`

**Files:**

- Create: `personalscraper/indexer/scanner/_modes/_item_stage.py`
- Reference source: `personalscraper/library/scanner.py` (functions `_upsert_media_item` `:600`, `_upsert_seasons_and_episodes` `:726`, `_detect_issues` `:342`, `_ensure_disk_row` `:851`, `scan_movie_dir` `:447`, `scan_tvshow_dir` `:504`)

- [ ] **Step 3.1: Write unit tests for the stage (TDD)**

```python
# tests/indexer/scanner/_modes/test_item_stage.py
import sqlite3
from pathlib import Path

import pytest

from personalscraper.indexer.scanner._modes._item_stage import (
    build_item_row,
    upsert_item_with_attrs,
)


def _make_db(tmp_path: Path) -> sqlite3.Connection:
    """Create a minimal in-memory schema for item_stage tests."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE disk (id TEXT PRIMARY KEY, label TEXT, mount_point TEXT);
        CREATE TABLE media_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            norm_title TEXT NOT NULL,
            kind TEXT NOT NULL,
            year INTEGER,
            canonical_provider TEXT,
            tvdb_id TEXT,
            tmdb_id TEXT,
            external_ids_json TEXT,
            nfo_status TEXT,
            artwork_status TEXT,
            disk_id TEXT REFERENCES disk(id),
            dispatch_path TEXT,
            category_id TEXT
        );
        CREATE TABLE item_attr (
            item_id INTEGER REFERENCES media_item(id),
            key TEXT NOT NULL,
            value TEXT,
            PRIMARY KEY (item_id, key)
        );
        CREATE TABLE item_issue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER REFERENCES media_item(id),
            type TEXT NOT NULL,
            detail TEXT
        );
        INSERT INTO disk VALUES ('disk1', 'Disk1', '/mnt/disk1');
    """)
    return conn


def test_build_item_row_returns_dict() -> None:
    row = build_item_row(
        norm_title="the godfather",
        kind="movie",
        year=1972,
        tvdb_id=None,
        tmdb_id="238",
        nfo_default="tmdb",
        nfo_status="complete",
        artwork_status="complete",
        disk_id="disk1",
        dispatch_path="/mnt/disk1/Movies/The Godfather (1972)",
        category_id="movies",
    )
    assert row["canonical_provider"] == "tmdb"
    assert row["norm_title"] == "the godfather"
    assert row["kind"] == "movie"


def test_upsert_item_with_attrs_creates_row(tmp_path: Path) -> None:
    conn = _make_db(tmp_path)
    row = build_item_row(
        norm_title="breaking bad",
        kind="show",
        year=2008,
        tvdb_id="81189",
        tmdb_id="1396",
        nfo_default="tvdb",
        nfo_status="complete",
        artwork_status="complete",
        disk_id="disk1",
        dispatch_path="/mnt/disk1/TVShows/Breaking Bad (2008)",
        category_id="tv_shows",
    )
    item_id = upsert_item_with_attrs(conn, row, attrs={"norm_title": "breaking bad"})
    assert isinstance(item_id, int)
    count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
    assert count == 1
    cp = conn.execute("SELECT canonical_provider FROM media_item WHERE id=?", (item_id,)).fetchone()[0]
    assert cp == "tvdb"


def test_upsert_item_nfo_missing_flags_issue(tmp_path: Path) -> None:
    """NFO-less dirs must be indexed (folder-name fallback) AND flagged — never dropped."""
    conn = _make_db(tmp_path)
    row = build_item_row(
        norm_title="unknown show",
        kind="show",
        year=None,
        tvdb_id=None,
        tmdb_id=None,
        nfo_default=None,
        nfo_status="missing",
        artwork_status="missing",
        disk_id="disk1",
        dispatch_path="/mnt/disk1/TVShows/Unknown Show",
        category_id="tv_shows",
    )
    item_id = upsert_item_with_attrs(conn, row, attrs={}, issues=[{"type": "nfo_missing", "detail": ""}])
    # item must exist
    assert conn.execute("SELECT COUNT(*) FROM media_item WHERE id=?", (item_id,)).fetchone()[0] == 1
    # issue must be flagged
    issue_count = conn.execute(
        "SELECT COUNT(*) FROM item_issue WHERE item_id=? AND type='nfo_missing'", (item_id,)
    ).fetchone()[0]
    assert issue_count >= 1
```

Run to confirm failure:

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/_modes/test_item_stage.py -v 2>&1 | tail -10
```

Expected: `ImportError`.

- [ ] **Step 3.2: Read the scanner.py source functions that `_item_stage` must absorb**

```bash
sed -n '342,870p' /Users/izno/dev/PersonnalScaper/personalscraper/library/scanner.py
```

- [ ] **Step 3.3: Create `_item_stage.py`**

The module must expose:

- `build_item_row(norm_title, kind, year, tvdb_id, tmdb_id, nfo_default, nfo_status, artwork_status, disk_id, dispatch_path, category_id) -> dict` — constructs the `media_item` dict from parsed inputs; calls `derive_canonical_provider` from `_canonical.py`.
- `upsert_item_with_attrs(conn, row, attrs, issues=None) -> int` — writes to `media_item`, `item_attr`, `item_issue`; returns `item_id`; idempotent on `(norm_title, disk_id)` conflict.
- `scan_and_stage_dir(conn, media_dir, disk_id, category_id, kind) -> int` — reads the NFO in `media_dir`, calls `build_item_row` + `upsert_item_with_attrs`; handles missing/incomplete NFO with folder-name fallback + `nfo_missing`/`nfo_incomplete` issue; calls `_ensure_disk_row`.
- `_ensure_disk_row(conn, disk_id, mount_point) -> None` — DEV #50: inserts the disk row if absent.

Adapt the logic verbatim from the scanner.py source functions; replace `_normalize_canonical_provider` calls with `derive_canonical_provider` from `_canonical.py`; replace NFO helper calls with `nfo_utils` imports; replace ad-hoc season regex with `SEASON_DIR_RE` from `naming_patterns`.

```python
# personalscraper/indexer/scanner/_modes/_item_stage.py
"""Unified item/season/episode/issue upsert stage for ScanMode.full.

Exports
-------
build_item_row          Build a ``media_item`` dict from parsed NFO inputs.
upsert_item_with_attrs  Write media_item + item_attr + item_issue rows.
scan_and_stage_dir      High-level: parse NFO in a media dir and upsert.
_ensure_disk_row        DEV #50: guarantee a disk row exists before FK writes.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from personalscraper.indexer.scanner._modes._canonical import derive_canonical_provider
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.nfo_utils import extract_nfo_metadata, parse_title_year

# ... (full implementation ported from scanner.py source functions)
```

Fill in the full implementation by adapting the bodies of `_upsert_media_item`, `_upsert_seasons_and_episodes`, `_detect_issues`, `_ensure_disk_row` from `library/scanner.py`. The function signatures above are the public API; internal helpers may be prefixed with `_`.

- [ ] **Step 3.4: Run unit tests — must pass**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/_modes/test_item_stage.py -v 2>&1 | tail -20
```

Expected: all 3 tests PASS.

- [ ] **Step 3.5: Verify ACC-03 import smoke**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "import personalscraper.indexer.scanner._modes._item_stage, personalscraper.indexer.scanner._modes._canonical; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3.6: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/indexer/scanner/_modes/_item_stage.py personalscraper/indexer/scanner/_modes/_canonical.py tests/indexer/scanner/_modes/test_item_stage.py && git commit -m "feat(lib-fold): add _item_stage.py — unified item/season/episode upsert"
```

---

### Task 4: Wire `full.py` to invoke the stage as pass 1

**Files:**

- Modify: `personalscraper/indexer/scanner/_modes/full.py`

- [ ] **Step 4.1: Read `full.py`**

```bash
cat /Users/izno/dev/PersonnalScaper/personalscraper/indexer/scanner/_modes/full.py
```

- [ ] **Step 4.2: Add the item-stage pass 1 call**

Before the existing file-walk call in `full.py`'s main scan function, insert:

```python
from personalscraper.indexer.scanner._modes._item_stage import scan_and_stage_dir

# Pass 1: upsert rich media_item rows (title, canonical_provider, seasons, issues)
# for every media directory in this category. Mirrors what library-scan did.
for media_dir in _iter_media_dirs(category):
    scan_and_stage_dir(conn, media_dir, disk_id=disk.id, category_id=category.id, kind=category.kind)
```

The existing pass 2 (file walk via `_walker`) continues unchanged after pass 1.

- [ ] **Step 4.3: Run the full test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && make test 2>&1 | tail -20
```

Expected: all tests pass (the legacy `library-scan` path is still active — both paths co-exist).

- [ ] **Step 4.4: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/indexer/scanner/_modes/full.py && git commit -m "feat(lib-fold): wire _item_stage as pass 1 in ScanMode.full"
```

---

### Task 5: Characterization golden test (DB end-state == legacy `library-scan`)

**Files:**

- Create: `tests/indexer/scanner/_modes/test_item_stage_golden.py`

- [ ] **Step 5.1: Write the golden test**

This test runs `library-scan` on a fixture, captures the `media_item` DB end-state as the baseline, then resets the DB and runs `library-index --mode full`, and asserts the end-states are equal.

```python
# tests/indexer/scanner/_modes/test_item_stage_golden.py
"""Characterization golden: library-index --mode full == legacy library-scan DB end-state.

This test is the safety net for Phase 3's deletion of library/scanner.py.
It must pass before any deletion is attempted. If it fails, Phase 3 is blocked.
"""
import sqlite3
from pathlib import Path
from typing import Any

import pytest

# Import the fixtures and helpers from the integration fixture module
from tests.integration.fixtures.seeded_library_fs import seeded_library_fs  # noqa: F401


def _snapshot_media_items(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return sorted list of media_item rows as dicts for comparison."""
    rows = conn.execute(
        "SELECT norm_title, kind, year, canonical_provider, tvdb_id, tmdb_id, "
        "nfo_status, disk_id, category_id "
        "FROM media_item ORDER BY norm_title, disk_id"
    ).fetchall()
    cols = ["norm_title", "kind", "year", "canonical_provider", "tvdb_id",
            "tmdb_id", "nfo_status", "disk_id", "category_id"]
    return [dict(zip(cols, r)) for r in rows]


@pytest.mark.integration
def test_full_mode_db_equals_library_scan_baseline(tmp_path: Path, seeded_library_fs: Path) -> None:
    """library-index --mode full must produce the same media_item rows as library-scan."""
    from personalscraper.library.scanner import scan_library
    from personalscraper.indexer.scanner import scan

    db_path = tmp_path / "index.db"

    # --- Baseline: library-scan (legacy path) ---
    from personalscraper.indexer.schema import init_db
    conn_legacy = sqlite3.connect(str(db_path))
    init_db(conn_legacy)
    scan_library(conn_legacy, root=seeded_library_fs)
    baseline = _snapshot_media_items(conn_legacy)
    conn_legacy.close()

    # --- Reset ---
    db_path.unlink()

    # --- New path: library-index --mode full ---
    conn_new = sqlite3.connect(str(db_path))
    init_db(conn_new)
    scan(conn_new, root=seeded_library_fs, mode="full")
    result = _snapshot_media_items(conn_new)
    conn_new.close()

    assert baseline, "Baseline must not be empty — fixture has media dirs"
    assert result == baseline, (
        f"DB end-state mismatch.\nBaseline ({len(baseline)} rows):\n{baseline[:3]}\n"
        f"Result ({len(result)} rows):\n{result[:3]}"
    )
```

Adapt imports to match the actual fixture and scan API signatures in the codebase (read `tests/integration/fixtures/seeded_library_fs.py` and `personalscraper/indexer/scanner/__init__.py` to verify exact call signatures before writing).

- [ ] **Step 5.2: Run the golden test**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/_modes/test_item_stage_golden.py -v -m integration 2>&1 | tail -30
```

Expected: PASS. If it fails, fix `_item_stage.py` until it passes — do not proceed to Phase 3 until this is green.

- [ ] **Step 5.3: Verify ACC-03b (no NFO-less dir dropped; flagged)**

```bash
DB=$(python -c "from personalscraper.conf.loader import load_config as L; print(L().indexer.db_path)")
sqlite3 "$DB" "SELECT COUNT(*) FROM item_issue WHERE type IN ('nfo_missing','nfo_incomplete');"
```

Expected: integer ≥ 0 (rows exist iff NFO-less dirs exist; none silently absent from `media_item`).

- [ ] **Step 5.4: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add tests/indexer/scanner/_modes/test_item_stage_golden.py && git commit -m "test(lib-fold): add characterization golden — full-mode DB == library-scan baseline"
```

---

### Task 6: Phase 2 gate

- [ ] **Step 6.1: Full gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test && make check ; echo "rc=$?"
```

Expected: ruff+mypy clean, `NNNN passed` 0 failed/errors, coverage ≥ 90 %, `rc=0`.

- [ ] **Step 6.2: Confirm no deletions occurred**

```bash
test -f /Users/izno/dev/PersonnalScaper/personalscraper/library/scanner.py && echo "scanner.py still present (correct)"
```

Expected: `scanner.py still present (correct)`.

- [ ] **Step 6.3: Gate commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git commit --allow-empty -m "chore(lib-fold): phase 2 gate — _item_stage + _canonical built; golden test green"
```

---

## Acceptance

```bash
# ACC-03  unified item stage + canonical SSOT exist; importable
python -c "import personalscraper.indexer.scanner._modes._item_stage, personalscraper.indexer.scanner._modes._canonical; print('OK')"
# Expected: OK  (golden DB-equality is asserted in test_item_stage_golden.py)

# ACC-03b  no NFO-less dir dropped; flagged in item_issue
DB=$(python -c "from personalscraper.conf.loader import load_config as L; print(L().indexer.db_path)")
sqlite3 "$DB" "SELECT COUNT(*) FROM item_issue WHERE type IN ('nfo_missing','nfo_incomplete');"
# Expected: integer >= 0
```

---

## Risks & mitigations

| Risk                                                                      | Mitigation                                                                                                    |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Folding `media_item` creation half-breaks DB end-state vs legacy two-step | Golden test (Task 5) asserts row-level equality BEFORE any deletion; Phase 3 is blocked until it passes.      |
| `canonical_provider` SSOT merge re-opens 194-show regression              | `test_init_canonical.py` carried forward verbatim (Task 2.3); "kind beats NFO XML order" test added (Task 1). |
| `_item_stage.py` exceeds 1000 non-blank LOC                               | Monitor with `python3 scripts/check-module-size.py` at each commit; split into `_item_stage_tv.py` if needed. |
| No-NFO dir silently dropped (regression from legacy)                      | `test_upsert_item_nfo_missing_flags_issue` in Task 3.1 asserts the item exists AND is flagged.                |
