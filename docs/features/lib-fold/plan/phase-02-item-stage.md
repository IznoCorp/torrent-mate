# Phase 2 — Build `_item_stage` + `_canonical`; rewire `scan_library` (parallel path)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `_item_stage.py` (unified item/season/episode/issue upsert) and `_canonical.py` (kind-deterministic canonical SSOT). Wire `full.py` to invoke the stage as pass 1. Rewire `scan_library` to call the same stage (parallel path — legacy path stays green). Gate = characterization golden test asserting DB end-state equals the legacy `library-scan` baseline. NO deletions in this phase.

**Architecture:** This is the XL crux phase. The parallel path means both `library-scan` (old) and `library-index --mode full` (new) produce identical DB rows. The golden test is the safety net that makes Phase 3's deletion safe. `_canonical.py` absorbs both `_normalize_canonical_provider` (from `scanner.py`) and the kind-deterministic logic from `backfill_ids_canonical.py`, replacing the NFO-XML-order fallback with a WARN.

**Tech Stack:** Python 3.11, SQLite (`indexer/repos/item_repo.py`, `indexer/repos/tv_repo.py`), pytest, ruff, mypy.

---

## Gate

Phase 1 must be complete:

- NFO **helper** importers are sourced from `nfo_utils` (Phase 1's actual deliverable):
  `rg -t py 'from personalscraper.library.scanner import (parse_title_year|extract_nfo_ids|extract_nfo_metadata)' personalscraper/` returns zero matches.
  > NOTE: `scan_library` / `scan_movie_dir` / `scan_tvshow_dir` importers legitimately **remain** at Phase 2 entry — `library/scanner.py` is the live legacy path until **Phase 3** deletes it. Do **not** expect `rg -t py 'from personalscraper.library.scanner import' …` to return zero matches here; that is a post-Phase-3 state, not a Phase-2 gate.
- Phase 1 gate commit present: `git log --oneline | rg -q 'phase 1 gate'`.
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

> **CRITICAL — behavior parity:** `derive_canonical_provider` must be **byte-identical in behavior** to the existing `library.scanner._normalize_canonical_provider` (scanner.py:69). The golden test (Task 5) asserts the new full-mode DB end-state equals the legacy `library-scan` baseline; any divergence here breaks it. Port the logic verbatim, including the **movie + tvdb_id-only → `None`** anomaly branch (the legacy fn keeps it NULL so the CLI repair can pick it up — it does **not** return `"tmdb"`).
>
> **CRITICAL — logging:** use the project's structlog logger (`from personalscraper.logger import get_logger`), **not** the stdlib `logging` module. `logging.Logger.warning("event", kind=...)` raises `TypeError` on the structlog-style kwargs — the whole codebase uses `get_logger(...)` (see scanner.py:66).

```python
# personalscraper/indexer/scanner/_modes/_canonical.py
"""Kind-deterministic canonical-provider SSOT.

The single source of truth for deriving ``canonical_provider`` from a
media item's kind and known provider IDs. Replaces both
``library.scanner._normalize_canonical_provider`` and the NFO-XML-order
fallback in ``backfill_ids_canonical._parse_canonical_from_nfo``.

Rule (§4.4 DESIGN; ports library.scanner._normalize_canonical_provider):
- show  + tvdb_id present              → ``"tvdb"``
- show  + no tvdb_id, tmdb_id present   → ``"tmdb"``
- movie + tmdb_id present               → ``"tmdb"``
- movie + tvdb_id only (no tmdb_id)     → ``None``   (anomaly kept NULL)
- no usable ID                          → ``None``

The NFO ``<uniqueid default="true">`` flag is intentionally ignored for
the derivation; we WARN when it disagrees (see §3.3).
"""
from __future__ import annotations

from personalscraper.logger import get_logger

log = get_logger("indexer.scanner.canonical")


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
        nfo_default: The ``<uniqueid default="true">`` type from the NFO
            (maps to the legacy ``nfo_declared`` arg), or ``None``. Used
            only for a WARN when it contradicts the deterministic result.

    Returns:
        ``"tvdb"``, ``"tmdb"``, or ``None`` when no usable ID exists.
    """
    kind_lower = (kind or "").lower()

    result: str | None
    if kind_lower == "show":
        if tvdb_id:
            result = "tvdb"
        elif tmdb_id:
            result = "tmdb"
        else:
            result = None
    else:
        # movie and all other kinds — TMDB is canonical; a tvdb-only movie
        # is an anomaly kept NULL (parity with _normalize_canonical_provider).
        if tmdb_id:
            result = "tmdb"
        else:
            result = None

    # Warn when the NFO-declared default contradicts the deterministic rule
    # (parity with the legacy "library_canonical_provider_overridden" trail).
    if nfo_default and result is not None and nfo_default != result:
        log.warning(
            "indexer_canonical_provider_overridden",
            kind=kind,
            nfo_default=nfo_default,
            computed=result,
            tvdb_id=tvdb_id,
            tmdb_id=tmdb_id,
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

> Real signature (verify before editing): `def _parse_canonical_from_nfo(nfo_path: Path) -> tuple[str | None, str, dict[str, str]]:` at line 86 — returns `(provider, outcome, extracted_ids)`. The current fallback derives the provider from the first `<uniqueid default="true">` of a supported type, then the first supported sibling `<uniqueid>` (NFO-XML-order). `extracted_ids` is the `{type: value}` dict parsed from all `<uniqueid>` tags. The function does **not** currently receive a `kind` argument.

- [ ] **Step 2.2: Add import and delegate in `_parse_canonical_from_nfo`**

Add at the top of `backfill_ids_canonical.py`:

```python
from personalscraper.indexer.scanner._modes._canonical import derive_canonical_provider
```

In `_parse_canonical_from_nfo`, after building `extracted_ids`, replace the NFO-XML-order fallback with a delegation to the SSOT. `derive_canonical_provider` needs `kind` + the `tvdb`/`tmdb` ids:

```python
# kind: prefer the NFO root tag (movie → "movie", tvshow/episodedetails → "show").
# If the function has no kind in scope, derive it from the NFO root or the
# caller's media_item.kind — DO NOT default blindly (a wrong kind flips the rule).
kind = _kind_from_nfo_root(root)          # adapt: read root.tag of the parsed NFO
tvdb_id = extracted_ids.get("tvdb")
tmdb_id = extracted_ids.get("tmdb")
provider = derive_canonical_provider(kind, tvdb_id, tmdb_id, nfo_default=None)
```

Preserve the existing return shape `(provider, outcome, extracted_ids)`. `derive_canonical_provider` already emits the disagreement WARN, so drop any duplicate derivation-time warning; keep only logging that flags genuinely _unsupported_ uniqueid types (anidb/tvmaze/etc.), which is orthogonal to the canonical rule.

> If wiring `kind` into `_parse_canonical_from_nfo` proves invasive (the function may be called from a context that lacks the kind), pass `kind` down from the caller in `backfill_ids_canonical` (it iterates `media_item` rows that already carry `kind`). Verify the call sites before choosing.

- [ ] **Step 2.3: Carry the canonical regression guards forward**

> CORRECTION: there is **no** dedicated "194-show" assertion in either `test_init_canonical.py`. "194 shows" is a historical incident documented only in the `_normalize_canonical_provider` docstring (scanner.py:83). The real regression guards are: (a) both existing `test_init_canonical.py` suites, and (b) the `test_kind_beats_nfo_xml_order` unit test added in Task 1 (the explicit "kind beats NFO XML order" invariant). Both `test_init_canonical.py` files exist (`tests/indexer/test_init_canonical.py` and `tests/indexer/scanner/test_init_canonical.py`).

Verify both canonical suites still pass after the delegation:

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/test_init_canonical.py tests/indexer/test_init_canonical.py tests/indexer/scanner/_modes/test_canonical.py -v 2>&1 | tail -20
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

> **CORRECTED — use the REAL schema, not a hand-rolled one.** The original draft hard-coded a pre-migration-005 schema (`norm_title`/`tvdb_id`/`tmdb_id`/`artwork_status`/`disk_id`/`dispatch_path` columns; `item_attr`; `item_issue` without `detected_at`; `nfo_status="complete"`). None of that exists today. Migration 005 dropped the flat ID columns (→ `external_ids_json`), there is **no** `norm_title`/`artwork_status`/`disk_id`/`dispatch_path` column (those are `item_attribute` flex rows keyed `dispatch_normalized_title`/`dispatch_disk`/`dispatch_path`), the table is `item_attribute` (PK `(item_id,key)`), `item_issue` is `(item_id, type, detail, detected_at)` PK `(item_id,type)` with `detected_at NOT NULL`, and `nfo_status` is `CHECK IN ('missing','invalid','valid')`. Build the schema with `apply_migrations` so the test can never drift from reality.

```python
# tests/indexer/scanner/_modes/test_item_stage.py
import json
import sqlite3
import time
from pathlib import Path

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.scanner._modes._item_stage import (
    build_item_row,
    upsert_item_with_attrs,
)

# tests/indexer/scanner/_modes/ → parents[4] == repo root
MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"


def _make_db() -> sqlite3.Connection:
    """Real indexer schema (post-005) via apply_migrations — never drifts."""
    conn = sqlite3.connect(":memory:")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def test_build_item_row_routes_ids_and_canonical() -> None:
    row = build_item_row(
        title="The Godfather",
        kind="movie",
        year=1972,
        category_id="movies",
        tvdb_id=None,
        tmdb_id="238",
        nfo_default="tmdb",
        nfo_status="valid",
    )
    assert row["canonical_provider"] == "tmdb"
    assert row["title"] == "The Godfather"
    assert row["kind"] == "movie"
    # IDs live in external_ids_json (migration 005), NOT flat columns.
    assert json.loads(row["external_ids_json"])["tmdb"]["series_id"] == "238"


def test_upsert_item_with_attrs_creates_row() -> None:
    conn = _make_db()
    row = build_item_row(
        title="Breaking Bad",
        kind="show",
        year=2008,
        category_id="tv_shows",
        tvdb_id="81189",
        tmdb_id="1396",
        nfo_default="tvdb",
        nfo_status="valid",
    )
    item_id = upsert_item_with_attrs(
        conn,
        row,
        attrs={
            item_repo._ATTR_DISPATCH_NORM_TITLE: "breaking bad",
            item_repo._ATTR_DISPATCH_DISK: "disk1",
            item_repo._ATTR_DISPATCH_PATH: "/mnt/disk1/series/Breaking Bad (2008)",
        },
    )
    assert isinstance(item_id, int)
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 1
    # show + tvdb_id → tvdb (kind beats the NFO-declared default).
    cp = conn.execute("SELECT canonical_provider FROM media_item WHERE id=?", (item_id,)).fetchone()[0]
    assert cp == "tvdb"
    # dispatch_normalized_title attr persisted (trailers / dispatch INNER JOIN on it).
    nt = conn.execute(
        "SELECT value FROM item_attribute WHERE item_id=? AND key=?",
        (item_id, item_repo._ATTR_DISPATCH_NORM_TITLE),
    ).fetchone()[0]
    assert nt == "breaking bad"


def test_upsert_item_nfo_missing_flags_issue() -> None:
    """NFO-less dirs must be indexed (folder-name fallback) AND flagged — never dropped."""
    conn = _make_db()
    row = build_item_row(
        title="Unknown Show",
        kind="show",
        year=None,
        category_id="tv_shows",
        tvdb_id=None,
        tmdb_id=None,
        nfo_default=None,
        nfo_status="missing",
    )
    item_id = upsert_item_with_attrs(
        conn,
        row,
        attrs={},
        issues=[{"type": "nfo_missing", "detail": None}],
    )
    # item must exist (folder-name fallback) — never silently dropped.
    assert conn.execute("SELECT COUNT(*) FROM media_item WHERE id=?", (item_id,)).fetchone()[0] == 1
    # issue must be flagged with a detected_at timestamp.
    issue_count = conn.execute(
        "SELECT COUNT(*) FROM item_issue WHERE item_id=? AND type='nfo_missing'", (item_id,)
    ).fetchone()[0]
    assert issue_count >= 1
```

> The test references `item_repo._ATTR_DISPATCH_*` (module constants: `dispatch_path`, `dispatch_disk`, `dispatch_normalized_title`). Create the `tests/indexer/scanner/_modes/` directory (no `__init__.py` needed — pytest rootdir handles discovery).

Run to confirm failure:

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/scanner/_modes/test_item_stage.py -v 2>&1 | tail -10
```

Expected: `ImportError` (module not created yet).

- [ ] **Step 3.2: Read the scanner.py source functions that `_item_stage` must absorb**

```bash
sed -n '342,870p' /Users/izno/dev/PersonnalScaper/personalscraper/library/scanner.py
```

- [ ] **Step 3.3: Create `_item_stage.py`**

The module must expose (signatures aligned to the **real** post-005 schema — IDs go to `external_ids_json`; `disk`/`path`/`norm_title` are `item_attribute` rows, never columns):

- `build_item_row(*, title, kind, year, category_id, tvdb_id, tmdb_id, imdb_id=None, nfo_default=None, nfo_status, artwork_json="{}", ratings=None) -> dict[str, Any]` — constructs a dict keyed by the **real** `media_item` columns (`kind`, `title`, `title_sort`, `original_title`, `year`, `category_id`, `external_ids_json`, `ratings_json`, `canonical_provider`, `nfo_status`, `artwork_json`, …). Builds `external_ids_json` from the ids (`{"tvdb": {"series_id": …, "episode_id": None}, …}`, mirroring scanner.py:645-652, `{}` when empty). Sets `canonical_provider = derive_canonical_provider(kind, tvdb_id, tmdb_id, nfo_default)`. `nfo_status` ∈ `{"missing","invalid","valid"}`.
- `upsert_item_with_attrs(conn, row, attrs, issues=None, *, now_s=None) -> int` — writes the row via `item_repo.upsert(conn, MediaItemRow(**row))` (idempotent on **`(kind, title)`** — `item_repo._canonical_title` strips a trailing `(YYYY)`), writes each `attrs` pair via `item_repo.upsert_attr(conn, ItemAttributeRow(item_id, key, value))` (`ON CONFLICT(item_id,key)`), then **replaces** the issue set: `DELETE FROM item_issue WHERE item_id=?` followed by `INSERT OR IGNORE INTO item_issue (item_id, type, detail, detected_at) VALUES (?,?,?,?)` (mirrors scanner.py:716-721; `now_s` defaults to `int(time.time())`). Returns `item_id`.
- `scan_and_stage_dir(conn, media_dir, disk_cfg, category_id, kind, now_s=None) -> int` — reads the NFO in `media_dir` (`nfo_utils.extract_nfo_metadata` + `parse_title_year` for the folder-name fallback), builds `attrs` for the three `_ATTR_DISPATCH_*` keys (path = abs media dir, disk = `disk_cfg.id`, norm_title = NFC-lower-stripped title — see scanner.py:699-708), detects issues (`_detect_issues`), and upserts. **Missing/incomplete NFO → still indexed** (folder-name fallback) **and flagged** (`nfo_missing` / `nfo_incomplete` in `item_issue`). Calls `_ensure_disk_row` first.
- `_ensure_disk_row(conn, disk_cfg, now_s) -> DiskRow` — DEV #50: SELECT-by-label then INSERT if absent; **same signature as scanner.py:851** (`disk_cfg: DiskConfig`, returns the `DiskRow`), not `(disk_id, mount_point)`.

Adapt the bodies **verbatim** from the scanner.py source functions; replace `_normalize_canonical_provider` with `derive_canonical_provider` from `_canonical.py`; use `nfo_utils` for NFO parsing; use `SEASON_DIR_RE` from `naming_patterns` for season dirs.

```python
# personalscraper/indexer/scanner/_modes/_item_stage.py
"""Unified item/season/episode/issue upsert stage for ScanMode.full.

Exports
-------
build_item_row          Build a ``media_item`` column dict from parsed NFO inputs.
upsert_item_with_attrs  Write media_item (item_repo.upsert) + item_attribute + item_issue.
scan_and_stage_dir      High-level: parse the NFO in a media dir and upsert.
_ensure_disk_row        DEV #50: guarantee a disk row exists before FK writes.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.repos import tv_repo
from personalscraper.indexer.schema import (
    DiskRow,
    ItemAttributeRow,
    MediaItemKind,
    MediaItemRow,
)
from personalscraper.indexer.scanner._modes._canonical import derive_canonical_provider
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.nfo_utils import extract_nfo_metadata, parse_title_year

log = get_logger("indexer.scanner.item_stage")

# ... (full implementation ported from scanner.py:_upsert_media_item / _upsert_seasons_and_episodes / _detect_issues / _ensure_disk_row)
```

Fill in the full implementation by adapting the bodies of `_upsert_media_item` (:600), `_upsert_seasons_and_episodes` (:726), `_detect_issues` (:342), and `_ensure_disk_row` (:851) from `library/scanner.py`. The public signatures above are the contract pinned by the Task 3.1 tests; internal helpers may be `_`-prefixed.

> **Module-size watch:** porting the season/episode + issue-detection logic may push `_item_stage.py` toward the 1000-LOC ceiling. Run `python3 scripts/check-module-size.py` at each commit; if it warns, split the TV path into `_item_stage_tv.py` (per the Risks table).

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

- [ ] **Step 4.1: Read `full.py` AND its orchestrator**

```bash
cat /Users/izno/dev/PersonnalScaper/personalscraper/indexer/scanner/_modes/full.py
# The orchestrator that calls _scan_disk_full per disk (where config/disks live):
sed -n '1,60p;300,420p' /Users/izno/dev/PersonnalScaper/personalscraper/indexer/scanner/__init__.py
# The reference iteration to mirror (disks × categories × media dirs):
sed -n '902,1003p' /Users/izno/dev/PersonnalScaper/personalscraper/library/scanner.py
```

> REALITY (verify): `full.py` exposes only `_scan_disk_full(conn, disk: DiskRow, mount: str, …)` — the **file-level** walk (`media_file`/`media_stream`) via `_walk_dir_full_buffered`. There is **no** `_iter_media_dirs` and **no** `category` object in that scope; `_scan_disk_full` has only a `DiskRow` + mount string, not a `DiskConfig` or the category map. The fabricated `for media_dir in _iter_media_dirs(category)` / `category.kind` / `category.id` / `disk.id` snippet does not match any existing API.

- [ ] **Step 4.2: Wire the item-stage pass 1**

The pass-1 item stage must replicate `library.scanner.scan_library`'s iteration — **config disks × categories × media dirs** — which requires the `Config`/`DiskConfig`/categories that live in the `scan()` orchestrator (`personalscraper/indexer/scanner/__init__.py`), **not** inside `_scan_disk_full`. Choose the insertion layer that actually has config + disks in scope (the orchestrator, or a small `_stage_items(conn, config, disks, now_s)` helper invoked from it **before** the per-disk file walk). For each `(disk_cfg, category_id, kind, media_dir)`:

```python
from personalscraper.indexer.scanner._modes._item_stage import scan_and_stage_dir

# Pass 1: upsert rich media_item rows (title, canonical_provider, attrs, seasons,
# issues) for every media directory — mirrors library.scanner.scan_library's walk.
scan_and_stage_dir(conn, media_dir, disk_cfg=disk_cfg, category_id=category_id, kind=kind, now_s=now_s)
```

Read `scan_library` (scanner.py:902) for the exact disk/category/media-dir iteration (folder*name resolution, kind per category via `TV_CATEGORY_IDS`, NFC handling) and port that walk. Adjust the objective's "modify full.py" to whichever layer has config in scope — the goal is \_pass 1 runs before the file walk*, not literally a one-liner inside `full.py`. The existing file walk (pass 2) continues unchanged after pass 1.

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

This test runs the legacy `scan_library` on a fixture, captures the `media_item` DB end-state as the baseline, then on a fresh DB runs the new `library-index --mode full` path, and asserts the end-states are equal.

> **CORRECTED harness — the originals don't exist.** There is **no** `init_db`; DB schema is built with `apply_migrations(conn, MIGRATIONS_DIR)`. `scan_library` is `scan_library(config: Config, conn, *, event_bus: EventBus)` — **not** `scan_library(conn, root=…)`. The indexer entry is `scan(disks: list[DiskRow], mode: ScanMode, generation: int, conn, *, …, event_bus: EventBus) -> ScanRunResult` — **not** `scan(conn, root=…, mode="full")`. And the snapshot must read **real** columns: `title` (no `norm_title` column), IDs via `json_extract(external_ids_json, …)` (no `tvdb_id`/`tmdb_id` columns), disk via an `item_attribute` join on `key='dispatch_disk'` (no `disk_id` column).
>
> **Model the harness on existing integration tests** — read both before writing:
>
> - Baseline (legacy) → `tests/library/test_integration.py` (`apply_migrations(conn, MIGRATIONS_DIR)` + `scan_library(config, conn, event_bus=EventBus())`, with its `mini_library`/`Config` setup).
> - New path (indexer full scan over a seeded fs) → `tests/integration/test_scan_reconcile_clean.py` (uses `seeded_library_fs`; shows how to build the `DiskRow` list + `ScanMode.FULL` + `generation` + `EventBus` and call `scan(...)`).
>   Both paths must run against the **same** on-disk fixture and the **same** `Config`/disks so the comparison is apples-to-apples.

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

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "personalscraper" / "indexer" / "migrations"


def _snapshot_media_items(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Sorted media_item rows as dicts — REAL post-005 columns only.

    IDs come from external_ids_json (migration 005 dropped the flat columns);
    disk comes from the item_attribute flex row (key='dispatch_disk').
    """
    rows = conn.execute(
        """
        SELECT mi.title, mi.kind, mi.year, mi.canonical_provider,
               json_extract(mi.external_ids_json, '$.tvdb.series_id') AS tvdb,
               json_extract(mi.external_ids_json, '$.tmdb.series_id') AS tmdb,
               mi.nfo_status, mi.category_id,
               (SELECT value FROM item_attribute
                 WHERE item_id = mi.id AND key = 'dispatch_disk') AS disk
          FROM media_item mi
         ORDER BY mi.title, mi.kind
        """
    ).fetchall()
    cols = ["title", "kind", "year", "canonical_provider", "tvdb", "tmdb",
            "nfo_status", "category_id", "disk"]
    return [dict(zip(cols, r)) for r in rows]


@pytest.mark.integration
def test_full_mode_db_equals_library_scan_baseline(tmp_path: Path, seeded_library_fs) -> None:
    """library-index --mode full must produce the same media_item rows as library-scan."""
    from personalscraper.library.scanner import scan_library
    # NOTE: build `config` + `disks` (list[DiskRow]) from seeded_library_fs —
    # see tests/integration/test_scan_reconcile_clean.py for the exact setup.

    # --- Baseline: legacy scan_library ---
    conn_legacy = sqlite3.connect(":memory:")
    apply_migrations(conn_legacy, MIGRATIONS_DIR)
    scan_library(config, conn_legacy, event_bus=EventBus())  # config from the fixture
    baseline = _snapshot_media_items(conn_legacy)
    conn_legacy.close()

    # --- New path: indexer full scan (ScanMode.FULL) ---
    from personalscraper.indexer.scanner import ScanMode, scan
    conn_new = sqlite3.connect(":memory:")
    apply_migrations(conn_new, MIGRATIONS_DIR)
    scan(disks, mode=ScanMode.FULL, generation=1, conn=conn_new, event_bus=EventBus())  # disks from the fixture
    result = _snapshot_media_items(conn_new)
    conn_new.close()

    assert baseline, "Baseline must not be empty — fixture has media dirs"
    assert result == baseline, (
        f"DB end-state mismatch.\nBaseline ({len(baseline)} rows):\n{baseline[:3]}\n"
        f"Result ({len(result)} rows):\n{result[:3]}"
    )
```

The `config` / `disks` construction above is intentionally elided — wire it from `seeded_library_fs` exactly as the two reference integration tests do (verify the `seeded_library_fs` return type and the `scan()` kwargs before writing). If full `scan()` proves too heavy to drive directly in a unit-style test, it is acceptable to drive the new path through the CLI command layer (`personalscraper library-index --mode full`) against a temp config, as long as both paths hit the same fixture.

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
