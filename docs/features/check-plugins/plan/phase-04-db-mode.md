# Phase 4 — DB-Mode Unification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `from_index()` to the four indexable checks (`nfo_present`, `nfo_valid`, `poster_present`, `artwork_landscape`). Replace `validate_from_index`'s inline field-inspection with a registry loop over `IndexableCheck` plugins. The golden for the DB entry point must match.

**Architecture:** Each indexable plugin gets a `from_index(row, ictx)` method that mirrors the exact `nfo_status` / `artwork_json` field logic from `validate_from_index`. `validate_from_index` becomes: build `IndexContext` per row, collect `check.from_index(row, ictx)` for every `IndexableCheck` in `registry.checks_for(DISPATCH, mt)`, `None` → skip. The `nfo_status NULL → []` (unflagged) behavior is preserved.

**Tech Stack:** Python 3.11 `sqlite3`, `IndexableCheck` protocol, `IndexContext`, pytest (in-memory SQLite fixtures)

---

## ⚠️ PLAN CORRECTIONS (post-verification 2026-06-01)

- **GOLD**: this phase rewrites `validate_from_index` → its gate MUST assert real-equality on the `library_from_index` golden (captured in Phase 0): `pytest tests/verify/test_characterization_golden.py -q`. The in-memory-SQLite integration tests in 4.2 are additive, not a substitute for the golden assertion.

---

## Gate (previous phase)

- `MediaFixer` deleted; residual-import greps rc=1.
- `pytest tests/verify/test_characterization_golden.py -q` → all pass.
- `pytest tests/verify tests/enforce -q` → all pass.

---

## Sub-phase 4.1 — Add `from_index()` to the four indexable checks

**Files:**

- Modify: `personalscraper/verify/checks/nfo.py` (`NfoPresent`, `NfoValid`)
- Modify: `personalscraper/verify/checks/artwork.py` (`PosterPresent`, `ArtworkLandscape`)

- [ ] **Step 1: Write failing tests for `from_index()`**

```python
# tests/verify/checks/test_from_index.py
"""Unit tests for IndexableCheck.from_index() on the four indexable plugins."""
import json
from unittest.mock import MagicMock
import pytest
from personalscraper.verify.checks.base import CheckStage, IndexContext, Severity


def _ictx(media_type: str = "movie", category: str = "movies") -> IndexContext:
    return IndexContext(row={}, media_type=media_type, category=category)


def test_nfo_present_from_index_missing():
    from personalscraper.verify.checks.nfo import NfoPresent
    row = {"nfo_status": "missing"}
    results = NfoPresent().from_index(row, _ictx())
    assert results is not None
    assert len(results) == 1
    assert not results[0].passed
    assert results[0].name == "nfo_present"


def test_nfo_present_from_index_valid():
    from personalscraper.verify.checks.nfo import NfoPresent
    row = {"nfo_status": "valid"}
    results = NfoPresent().from_index(row, _ictx())
    assert results == []  # valid → no finding


def test_nfo_present_from_index_null_skipped():
    from personalscraper.verify.checks.nfo import NfoPresent
    row = {"nfo_status": None}
    results = NfoPresent().from_index(row, _ictx())
    assert results == []  # NULL → unflagged (cannot distinguish from not-yet-enriched)


def test_nfo_valid_from_index_invalid():
    from personalscraper.verify.checks.nfo import NfoValid
    row = {"nfo_status": "invalid"}
    results = NfoValid().from_index(row, _ictx())
    assert results is not None and len(results) == 1
    assert not results[0].passed
    assert results[0].name == "nfo_valid"


def test_poster_present_from_index_missing():
    from personalscraper.verify.checks.artwork import PosterPresent
    row = {"artwork_json": json.dumps({})}  # no poster key
    results = PosterPresent().from_index(row, _ictx())
    assert results is not None and len(results) == 1
    assert not results[0].passed


def test_poster_present_from_index_present():
    from personalscraper.verify.checks.artwork import PosterPresent
    row = {"artwork_json": json.dumps({"poster": "poster.jpg"})}
    results = PosterPresent().from_index(row, _ictx())
    assert results == []


def test_artwork_landscape_from_index_movie_missing():
    from personalscraper.verify.checks.artwork import ArtworkLandscape
    row = {"artwork_json": json.dumps({})}
    results = ArtworkLandscape().from_index(row, _ictx(media_type="movie"))
    assert results is not None and len(results) == 1
    assert results[0].severity == Severity.WARNING


def test_artwork_landscape_from_index_tvshow_skipped():
    """DB-mode landscape is movie-only today — preserved."""
    from personalscraper.verify.checks.artwork import ArtworkLandscape
    row = {"artwork_json": json.dumps({})}
    results = ArtworkLandscape().from_index(row, _ictx(media_type="tvshow"))
    assert results is None  # tvshow → not derivable in DB-mode
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/verify/checks/test_from_index.py -q
```

Expected: `AttributeError: 'NfoPresent' object has no attribute 'from_index'`

- [ ] **Step 3: Add `from_index()` to `NfoPresent` in `nfo.py`**

```python
def from_index(self, row: Mapping, ctx: IndexContext) -> list[CheckResult] | None:
    """Derive nfo_present result from DB row.

    Args:
        row: DB row with nfo_status field.
        ctx: IndexContext with media_type and category.

    Returns:
        [failed CheckResult] if nfo_status=="missing"; [] otherwise; None never.
    """
    nfo_status = row["nfo_status"] if hasattr(row, "__getitem__") else getattr(row, "nfo_status", None)
    if nfo_status == "missing":
        return [CheckResult(name="nfo_present", passed=False, severity=Severity.ERROR,
                            message="NFO missing (from index)")]
    return []  # "valid", "invalid", or NULL → not flagged by this check
```

- [ ] **Step 4: Add `from_index()` to `NfoValid` in `nfo.py`**

```python
def from_index(self, row: Mapping, ctx: IndexContext) -> list[CheckResult] | None:
    """Derive nfo_valid result from DB row.

    Args:
        row: DB row with nfo_status field.
        ctx: IndexContext.

    Returns:
        [failed CheckResult] if nfo_status=="invalid"; [] otherwise.
    """
    nfo_status = row["nfo_status"] if hasattr(row, "__getitem__") else getattr(row, "nfo_status", None)
    if nfo_status == "invalid":
        return [CheckResult(name="nfo_valid", passed=False, severity=Severity.ERROR,
                            message="NFO invalid (from index)")]
    return []
```

- [ ] **Step 5: Add `from_index()` to `PosterPresent` in `artwork.py`**

```python
def from_index(self, row: Mapping, ctx: IndexContext) -> list[CheckResult] | None:
    """Derive poster_present result from DB row artwork_json.

    Args:
        row: DB row with artwork_json field.
        ctx: IndexContext.

    Returns:
        [failed CheckResult] if poster absent; [] if present; None if no artwork_json.
    """
    import json as _json
    artwork_raw = row["artwork_json"] if hasattr(row, "__getitem__") else getattr(row, "artwork_json", None)
    if not artwork_raw:
        return None
    try:
        artwork = _json.loads(artwork_raw)
    except (TypeError, ValueError):
        artwork = {}
    if not artwork.get("poster"):
        return [CheckResult(name="poster_present", passed=False, severity=Severity.ERROR,
                            message="Poster missing (from index)")]
    return []
```

- [ ] **Step 6: Add `from_index()` to `ArtworkLandscape` in `artwork.py`**

```python
def from_index(self, row: Mapping, ctx: IndexContext) -> list[CheckResult] | None:
    """Derive artwork_landscape result from DB row — movie-only in DB-mode.

    Args:
        row: DB row with artwork_json field.
        ctx: IndexContext.

    Returns:
        None for tvshow (not derivable); [result] or [] for movie.
    """
    import json as _json
    if ctx.media_type != "movie":
        return None  # DB-mode landscape is movie-only (DESIGN §9 quirk)
    artwork_raw = row["artwork_json"] if hasattr(row, "__getitem__") else getattr(row, "artwork_json", None)
    if not artwork_raw:
        return None
    try:
        artwork = _json.loads(artwork_raw)
    except (TypeError, ValueError):
        artwork = {}
    if not artwork.get("landscape"):
        return [CheckResult(name="artwork_landscape", passed=False, severity=Severity.WARNING,
                            message="Landscape missing (from index)")]
    return []
```

- [ ] **Step 7: Run from_index tests — expect pass**

```bash
pytest tests/verify/checks/test_from_index.py -q
```

Expected: `8 passed`

- [ ] **Step 8: Commit**

```bash
git add personalscraper/verify/checks/nfo.py personalscraper/verify/checks/artwork.py tests/verify/checks/test_from_index.py
git commit -m "feat(check-plugins): add from_index() to nfo_present, nfo_valid, poster_present, artwork_landscape"
```

---

## Sub-phase 4.2 — `validate_from_index` becomes a registry loop

**Files:**

- Modify: `personalscraper/verify/library_checks.py` (`validate_from_index`)

- [ ] **Step 1: Write failing integration test using in-memory SQLite**

```python
# tests/verify/test_validate_from_index_registry.py
"""Integration test: validate_from_index uses IndexableCheck registry loop."""
import json
import sqlite3
import pytest
from personalscraper.verify.library_checks import validate_from_index


def _make_db(items: list[dict]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE media_item (
            id INTEGER PRIMARY KEY, kind TEXT, title TEXT, year INTEGER,
            category_id TEXT, nfo_status TEXT, artwork_json TEXT, title_sort TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE item_attribute (
            item_id INTEGER, key TEXT, value TEXT
        )
    """)
    for i, item in enumerate(items, start=1):
        conn.execute(
            "INSERT INTO media_item VALUES (?,?,?,?,?,?,?,?)",
            (i, item["kind"], item["title"], item.get("year"), item.get("category_id", "movies"),
             item.get("nfo_status"), item.get("artwork_json"), item["title"])
        )
        if "disk" in item:
            conn.execute("INSERT INTO item_attribute VALUES (?,?,?)", (i, "dispatch_disk", item["disk"]))
    conn.commit()
    return conn


def test_validate_from_index_nfo_missing_flagged():
    conn = _make_db([
        {"kind": "movie", "title": "Orphan", "nfo_status": "missing",
         "artwork_json": json.dumps({"poster": "p.jpg", "landscape": "l.jpg"})}
    ])
    result = validate_from_index(conn)
    assert result.issues_count == 1
    item = result.items[0]
    assert "nfo_present" in item.errors


def test_validate_from_index_null_nfo_status_not_flagged():
    conn = _make_db([
        {"kind": "movie", "title": "Mystery", "nfo_status": None,
         "artwork_json": json.dumps({"poster": "p.jpg", "landscape": "l.jpg"})}
    ])
    result = validate_from_index(conn)
    assert result.valid_count == 1


def test_validate_from_index_landscape_movie_only():
    conn = _make_db([
        {"kind": "show", "title": "Series", "nfo_status": "valid",
         "artwork_json": json.dumps({"poster": "p.jpg"})}  # no landscape
    ])
    result = validate_from_index(conn)
    # TV shows: landscape is NOT checked in DB-mode
    assert result.valid_count == 1
```

- [ ] **Step 2: Run tests — should already pass (existing behavior) OR fail if registry loop breaks something**

```bash
pytest tests/verify/test_validate_from_index_registry.py -q
```

Expected: `3 passed` (existing code already correct; tests confirm behavior before touching it)

- [ ] **Step 3: Replace inline field-inspection in `validate_from_index` with registry loop**

```python
# In validate_from_index, replace the per-row errors/warnings building block:
import personalscraper.verify.checks  # trigger registration
from personalscraper.verify.checks.base import CheckStage, IndexContext, IndexableCheck
from personalscraper.verify.checks.registry import registry

# Per row (replacing the manual nfo_status / artwork_json blocks):
media_type = "tvshow" if row["kind"] == "show" else "movie"
ictx = IndexContext(row=row, media_type=media_type, category=row["category_id"])
errors: list[str] = []
warnings: list[str] = []
for check in registry.checks_for(CheckStage.DISPATCH, media_type):
    if not isinstance(check, IndexableCheck):
        continue
    results = check.from_index(row, ictx)
    if results is None:
        continue
    for r in results:
        if not r.passed:
            if r.severity.value == "error":
                errors.append(r.name)
            else:
                warnings.append(r.name)
```

- [ ] **Step 4: Re-run tests — must still pass (golden parity)**

```bash
pytest tests/verify/test_validate_from_index_registry.py -q
pytest tests/verify/test_characterization_golden.py -q
pytest tests/verify/test_library_checks.py -q
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add personalscraper/verify/library_checks.py tests/verify/test_validate_from_index_registry.py
git commit -m "refactor(check-plugins): validate_from_index becomes IndexableCheck registry loop"
```

---

## Phase Gate

```bash
make lint && make test && make check
pytest tests/verify/test_characterization_golden.py -q   # ACC-01
pytest tests/verify tests/enforce -q                      # ACC-02
python3 scripts/check-module-size.py                      # ACC-07
python -c "import personalscraper"
```

Expected: all green. DB-mode entry point now driven by `from_index()` on 4 registered plugins.
