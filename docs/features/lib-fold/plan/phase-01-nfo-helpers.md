# Phase 1 — Extract NFO helpers → `nfo_utils`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `parse_title_year`, `extract_nfo_ids`, and `extract_nfo_metadata` out of `library/scanner.py` into the existing `personalscraper/nfo_utils.py`, then repoint all importers. No back-compat shim (pre-1.0).

**Architecture:** `nfo_utils.py` already exists with `glob_nfo_candidates` and `is_nfo_complete`; the three helpers are appended. All callers currently reaching into `library.scanner` are updated to the new path. `library/scanner.py` itself retains only internal call-sites (which resolve after Phase 3 deletes the file).

**Tech Stack:** Python 3.11, `xml.etree.ElementTree` (already used by the helpers), pytest, ruff, mypy.

---

## Gate

Phase 0 must be complete:

- `rg -t py '_TV_SEASON_DIR_RE *=|_SEASON_DIR_RE *=' personalscraper/library/ personalscraper/indexer/ personalscraper/trailers/` returns zero matches.
- `make lint && make test && make check` green.

---

## Objective

1. Copy `parse_title_year`, `extract_nfo_ids`, `extract_nfo_metadata` verbatim into `personalscraper/nfo_utils.py`.
2. Update every external importer: `trailers/scanner.py`, `library/analyzer.py`, `library/rescraper.py`.
3. Update `library/scanner.py` internal calls to use the new location (forward-compatibility until Phase 3 deletes the file).
4. Verify `rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/` returns zero.

---

## Files to create / modify

| Action        | File                                                                                     |
| ------------- | ---------------------------------------------------------------------------------------- |
| Modify        | `personalscraper/nfo_utils.py` (append three helpers)                                    |
| Modify        | `personalscraper/trailers/scanner.py` (repoint import)                                   |
| Modify        | `personalscraper/library/analyzer.py` (repoint import)                                   |
| Modify        | `personalscraper/library/rescraper.py` (repoint import)                                  |
| Modify        | `personalscraper/library/scanner.py` (self-import → nfo_utils, internal calls unchanged) |
| Create/Modify | `tests/test_nfo_utils.py` (unit tests for the three moved helpers)                       |

---

## Sub-tasks

### Task 1: Write unit tests for the three helpers (TDD — they must pass BEFORE we touch importers)

**Files:**

- Create/Modify: `tests/test_nfo_utils.py`

- [ ] **Step 1.1: Write the tests**

Check existing test file:

```bash
ls /Users/izno/dev/PersonnalScaper/tests/test_nfo_utils.py 2>/dev/null || echo "does not exist"
```

Write (or append) the following tests. They will fail until the helpers are added to `nfo_utils.py`:

```python
# tests/test_nfo_utils.py
import textwrap
from pathlib import Path

import pytest

from personalscraper.nfo_utils import (
    extract_nfo_ids,
    extract_nfo_metadata,
    parse_title_year,
)


# --- parse_title_year ---

@pytest.mark.parametrize("dirname,expected_title,expected_year", [
    ("The Godfather (1972)", "The Godfather", 1972),
    ("Inception (2010)", "Inception", 2010),
    ("No Year Here", "No Year Here", None),
    ("Bad Boys for Life (2020)", "Bad Boys for Life", 2020),
])
def test_parse_title_year(dirname: str, expected_title: str, expected_year: int | None) -> None:
    title, year = parse_title_year(dirname)
    assert title == expected_title
    assert year == expected_year


# --- extract_nfo_ids ---

def _write_nfo(tmp_path: Path, content: str) -> Path:
    nfo = tmp_path / "movie.nfo"
    nfo.write_text(textwrap.dedent(content), encoding="utf-8")
    return nfo


def test_extract_nfo_ids_tvdb(tmp_path: Path) -> None:
    nfo = _write_nfo(tmp_path, """\
        <?xml version="1.0" encoding="UTF-8"?>
        <tvshow>
          <uniqueid type="tvdb" default="true">12345</uniqueid>
          <uniqueid type="tmdb">67890</uniqueid>
        </tvshow>
    """)
    tvdb_id, tmdb_id = extract_nfo_ids(nfo)
    assert tvdb_id == "12345"
    assert tmdb_id == "67890"


def test_extract_nfo_ids_missing(tmp_path: Path) -> None:
    nfo = _write_nfo(tmp_path, """\
        <?xml version="1.0" encoding="UTF-8"?>
        <movie><title>No IDs</title></movie>
    """)
    tvdb_id, tmdb_id = extract_nfo_ids(nfo)
    assert tvdb_id is None
    assert tmdb_id is None


# --- extract_nfo_metadata ---

def test_extract_nfo_metadata_returns_dict(tmp_path: Path) -> None:
    nfo = _write_nfo(tmp_path, """\
        <?xml version="1.0" encoding="UTF-8"?>
        <movie>
          <uniqueid type="tmdb" default="true">99</uniqueid>
          <uniqueid type="imdb">tt0000001</uniqueid>
        </movie>
    """)
    meta = extract_nfo_metadata(nfo)
    assert isinstance(meta, dict)
    assert meta.get("tmdb_id") == "99" or "tmdb" in str(meta)
```

- [ ] **Step 1.2: Run to confirm ImportError (helpers not yet in nfo_utils)**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/test_nfo_utils.py -v 2>&1 | tail -15
```

Expected: `ImportError: cannot import name 'parse_title_year' from 'personalscraper.nfo_utils'`.

---

### Task 2: Copy the three helpers into `nfo_utils.py`

**Files:**

- Modify: `personalscraper/nfo_utils.py`
- Reference source: `personalscraper/library/scanner.py` lines 159–295 (parse_title_year, extract_nfo_ids, extract_nfo_metadata)

- [ ] **Step 2.1: Read the exact function bodies from scanner.py**

```bash
sed -n '155,300p' /Users/izno/dev/PersonnalScaper/personalscraper/library/scanner.py
```

- [ ] **Step 2.2: Append the three functions verbatim to `nfo_utils.py`**

Open `personalscraper/nfo_utils.py` and append the three functions exactly as they appear in `scanner.py` (including all docstrings and inline comments). Ensure all imports they depend on (e.g. `re`, `xml.etree.ElementTree`, `Path`, `Any`) are present at the top of `nfo_utils.py`. Do not remove the originals from `scanner.py` yet — Phase 3 does that when the file is deleted.

Example top-of-file additions if not already present:

```python
import re
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
```

- [ ] **Step 2.3: Run the new tests — they must now pass**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/test_nfo_utils.py -v 2>&1 | tail -20
```

Expected: all `test_nfo_utils.py` tests PASS.

- [ ] **Step 2.4: Verify ACC-02b (importable from new home)**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "from personalscraper.nfo_utils import parse_title_year, extract_nfo_ids, extract_nfo_metadata; print('OK')"
```

Expected: `OK`.

- [ ] **Step 2.5: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/nfo_utils.py tests/test_nfo_utils.py && git commit -m "feat(lib-fold): add parse_title_year, extract_nfo_ids, extract_nfo_metadata to nfo_utils"
```

---

### Task 3: Repoint all external importers

**Files:**

- Modify: `personalscraper/trailers/scanner.py`
- Modify: `personalscraper/library/analyzer.py`
- Modify: `personalscraper/library/rescraper.py`

- [ ] **Step 3.1: Find every external importer**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/
```

Note the exact `import` lines in each file.

- [ ] **Step 3.2: Update `trailers/scanner.py`**

The current import (line 16) is:

```python
from personalscraper.library.scanner import extract_nfo_ids, parse_title_year
```

Replace with:

```python
from personalscraper.nfo_utils import extract_nfo_ids, parse_title_year
```

- [ ] **Step 3.3: Update `library/analyzer.py`**

Find the import line:

```bash
grep -n 'from.*library.scanner import\|from.*scanner import.*parse_title_year\|extract_nfo' /Users/izno/dev/PersonnalScaper/personalscraper/library/analyzer.py
```

Update whatever `parse_title_year` / `extract_nfo_ids` / `extract_nfo_metadata` imports exist to pull from `personalscraper.nfo_utils` instead of `personalscraper.library.scanner`.

- [ ] **Step 3.4: Update `library/rescraper.py`**

```bash
grep -n 'from.*library.scanner import\|parse_title_year\|extract_nfo' /Users/izno/dev/PersonnalScaper/personalscraper/library/rescraper.py
```

Apply the same repoint.

- [ ] **Step 3.5: Verify ACC-02 — no importer reaches into library.scanner for NFO helpers**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/ ; echo "rc=$?"
```

Expected: no output, then `rc=1`.

- [ ] **Step 3.6: Run full test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test 2>&1 | tail -20
```

Expected: zero lint errors, all tests pass.

- [ ] **Step 3.7: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/trailers/scanner.py personalscraper/library/analyzer.py personalscraper/library/rescraper.py && git commit -m "refactor(lib-fold): repoint NFO helper importers to nfo_utils"
```

---

### Task 4: Phase 1 gate

- [ ] **Step 4.1: Full gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test && make check ; echo "rc=$?"
```

Expected: ruff+mypy clean, `NNNN passed` 0 failed/errors, coverage ≥ 90 %, `rc=0`.

- [ ] **Step 4.2: Gate commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git commit --allow-empty -m "chore(lib-fold): phase 1 gate — NFO helpers in nfo_utils"
```

---

## Acceptance

```bash
# ACC-02  no importer reaches into library.scanner for NFO helpers
rg -t py 'from personalscraper.library.scanner import' personalscraper/ tests/ ; echo "rc=$?"
# Expected: no output, then rc=1

# ACC-02b  helpers callable from new home
python -c "from personalscraper.nfo_utils import parse_title_year, extract_nfo_ids, extract_nfo_metadata; print('OK')"
# Expected: OK
```

---

## Risks & mitigations

| Risk                                                                        | Mitigation                                                                                                                           |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `scanner.py` internal calls break if originals removed too early            | Originals stay in `scanner.py` until Phase 3 deletes the whole file; Phase 1 only adds to `nfo_utils` and repoints external callers. |
| Test coverage drop if `tests/library/test_scanner.py` covered these helpers | Verify coverage gate (`make check`) passes; if it drops, add unit tests in `tests/test_nfo_utils.py`.                                |
| Import cycle (`nfo_utils` → `library`)                                      | `nfo_utils.py` must not import anything from `library/`; the three helpers are pure-stdlib (regex + XML).                            |
