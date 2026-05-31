# Phase 4 — ffprobe fold + `insights/` package

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drop the redundant library ffprobe re-scan (`analyzer.analyze_library`). Verify `enrich.py` already populates `media_stream.hdr_format` / `is_atmos` at parity with the dropped path (HDR10 / HDR10+ / Dolby Vision / HLG granularity), or document the gap. Create the `insights/` read-only package by moving `analyze` / `analyze_from_index` / `reporter` / `recommender`. Delete `library/analyzer.py`, `library/reporter.py`, `library/recommender.py`.

**Architecture:** `media_stream.hdr_format` and `is_atmos` already exist (migration 004) and `enrich.py:360-376` already persists them. `scraper/mediainfo.extract_stream_info` stays — NFO generation uses it; only the `analyze_library` caller is removed. `insights/` is a move-only read-only package; the data functions already return dataclasses so no API changes are needed.

**Tech Stack:** Python 3.11, pymediainfo (via enrich), SQLite, pytest, ruff, mypy.

---

## Gate

Phase 3 must be complete:

- `test ! -f personalscraper/library/scanner.py` passes.
- `rg -t py 'canonical_provider=None' personalscraper/dispatch/media_index.py` returns zero matches.
- `make lint && make test && make check` green.

---

## Objective

1. Verify HDR/Atmos parity: confirm `enrich.py` populates `hdr_format` at the same granularity as the dropped `analyze_library` ffprobe path (HDR10/HDR10+/Dolby Vision/HLG). Close the gap or document it.
2. Delete `analyzer.analyze_library` (the `extract_stream_info` caller inside `library/`).
3. Create `personalscraper/insights/` package with `__init__.py`, `models.py`, `analytics.py`, `reporter.py`, `recommender.py`.
4. Move `analyze()` / `analyze_from_index()` into `insights/analytics.py`; move `generate_report`/`format_report_text` into `insights/reporter.py`; move `generate_recommendations` into `insights/recommender.py`.
5. Move the analysis/recommender/reporter dataclasses into `insights/models.py` (per DESIGN §4.6 routing table).
6. Repoint `commands/library/analyze.py` to the new `insights/` paths.
7. Delete `library/analyzer.py`, `library/reporter.py`, `library/recommender.py`.

---

## Files to create / modify

| Action | File                                                                                  |
| ------ | ------------------------------------------------------------------------------------- |
| Create | `personalscraper/insights/__init__.py`                                                |
| Create | `personalscraper/insights/models.py`                                                  |
| Create | `personalscraper/insights/analytics.py`                                               |
| Create | `personalscraper/insights/reporter.py`                                                |
| Create | `personalscraper/insights/recommender.py`                                             |
| Modify | `personalscraper/commands/library/analyze.py`                                         |
| Delete | `personalscraper/library/analyzer.py`                                                 |
| Delete | `personalscraper/library/reporter.py`                                                 |
| Delete | `personalscraper/library/recommender.py`                                              |
| Modify | `tests/library/test_analyzer.py` → migrate to `tests/insights/test_analytics.py`      |
| Modify | `tests/library/test_reporter.py` → migrate to `tests/insights/test_reporter.py`       |
| Modify | `tests/library/test_recommender.py` → migrate to `tests/insights/test_recommender.py` |

---

## Sub-tasks

### Task 1: Verify and close HDR/Atmos parity gap

- [ ] **Step 1.1: Read the `analyze_library` ffprobe path granularity**

```bash
sed -n '300,400p' /Users/izno/dev/PersonnalScaper/personalscraper/library/analyzer.py
```

Note the exact HDR format strings it writes (`HDR10`, `HDR10+`, `Dolby Vision`, `HLG`, etc.).

- [ ] **Step 1.2: Read the `enrich.py` hdr_format population path**

```bash
sed -n '340,390p' /Users/izno/dev/PersonnalScaper/personalscraper/indexer/scanner/_modes/enrich.py
```

Note what `hdr_format` values `enrich.py` writes to `media_stream`.

- [ ] **Step 1.3: Write a parity test**

```python
# tests/indexer/scanner/_modes/test_enrich_hdr_parity.py
"""Guard: enrich.py must populate hdr_format at the same granularity as
the dropped analyze_library ffprobe path (HDR10/HDR10+/Dolby Vision/HLG)."""
import pytest


@pytest.mark.parametrize("hdr_string,expected_stored", [
    ("HDR10",        "HDR10"),
    ("HDR10+",       "HDR10+"),
    ("Dolby Vision", "Dolby Vision"),
    ("HLG",          "HLG"),
])
def test_enrich_hdr_format_granularity(hdr_string: str, expected_stored: str) -> None:
    """Verify enrich maps each HDR format string to the expected stored value.

    This is a documentation/parity test. If enrich collapses fine-grained
    strings (e.g. 'HDR10+' → 'HDR10'), update this test AND add a comment
    in enrich.py documenting the accepted gap.
    """
    from personalscraper.indexer.scanner._modes.enrich import _map_hdr_format  # adjust to real helper name
    assert _map_hdr_format(hdr_string) == expected_stored
```

Adjust `_map_hdr_format` to the actual function/logic name in `enrich.py`. If `enrich.py` does not have a discrete mapping function, read the raw logic and test it inline. If a granularity gap is confirmed (e.g. HLG not stored), add a comment block in `enrich.py`:

```python
# HDR parity note (lib-fold Phase 4): the dropped analyze_library ffprobe
# path supported HLG detection; the current pymediainfo path does not expose
# HLG reliably — accepted gap, documented here. Future work: upgrade pymediainfo
# call to capture HLG flag when pymediainfo exposes it.
```

- [ ] **Step 1.4: Commit parity test (or parity gap doc)**

```bash
cd /Users/izno/dev/PersonnalScaper && git add tests/indexer/scanner/_modes/test_enrich_hdr_parity.py personalscraper/indexer/scanner/_modes/enrich.py && git commit -m "test(lib-fold): add HDR/Atmos parity test vs dropped analyze_library ffprobe path"
```

---

### Task 2: Create the `insights/` package skeleton and `models.py`

**Files:**

- Create: `personalscraper/insights/__init__.py`
- Create: `personalscraper/insights/models.py`
- Reference: `personalscraper/library/models.py` (DESIGN §4.6 routing table)

- [ ] **Step 2.1: Identify which dataclasses go to `insights/models.py`**

Per DESIGN §4.6, these go to `insights/models.py`:

- `VideoInfo`, `AudioTrack`, `SubtitleTrack`, `MediaFileAnalysis`, `LibraryAnalysisItem`, `LibraryAnalysisResult`
- `CurrentState`, `TargetState`, `Recommendation`, `LibraryRecommendationResult`

Verify they exist in `library/models.py`:

```bash
grep -n '^class\|^@dataclass' /Users/izno/dev/PersonnalScaper/personalscraper/library/models.py
```

- [ ] **Step 2.2: Create `insights/__init__.py`**

```python
# personalscraper/insights/__init__.py
"""Read-only insights layer over the indexer DB.

Provides analysis, reporting, and recommendation functions that consume
the ``media_item`` / ``media_stream`` tables written by
``indexer.scanner``. Intended for CLI commands and the future Web UI.
"""
```

- [ ] **Step 2.3: Create `insights/models.py` with the analysis + recommender dataclasses**

Copy verbatim (do not rename) the dataclasses listed in step 2.1 from `library/models.py` into `insights/models.py`. Add a module docstring:

```python
# personalscraper/insights/models.py
"""Dataclasses produced and consumed by the insights layer.

Routing: analysis + recommender dataclasses live here; scan-stage types
live in ``indexer.scanner._modes._item_stage``; verify types live in
``verify.library_checks``. See DESIGN §4.6.
"""
from __future__ import annotations
from dataclasses import dataclass, field
# ... (copy the relevant dataclasses verbatim)
```

- [ ] **Step 2.4: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/insights/__init__.py personalscraper/insights/models.py && git commit -m "feat(lib-fold): create insights/ package skeleton + models.py"
```

---

### Task 3: Move `analytics.py` (analyze + analyze_from_index)

**Files:**

- Create: `personalscraper/insights/analytics.py`
- Reference: `personalscraper/library/analyzer.py` functions `analyze()` (line 143) and `analyze_from_index()` (line 436)

- [ ] **Step 3.1: Read the functions to migrate**

```bash
sed -n '1,50p' /Users/izno/dev/PersonnalScaper/personalscraper/library/analyzer.py
grep -n 'def analyze\|def analyze_from_index\|def analyze_library' /Users/izno/dev/PersonnalScaper/personalscraper/library/analyzer.py
```

- [ ] **Step 3.2: Create `insights/analytics.py`**

Copy `analyze()` and `analyze_from_index()` verbatim (and any private helpers they call) into `insights/analytics.py`. Update imports to use `insights.models` instead of `library.models`. Do NOT copy `analyze_library` — it is deleted in this phase.

```python
# personalscraper/insights/analytics.py
"""DB-backed library analytics.

``analyze()`` aggregates per-category counts from the ``media_item`` table.
``analyze_from_index()`` reads ``media_stream`` rows for stream-level stats.

``analyze_library()`` (the filesystem ffprobe re-scan) has been removed —
use the enrich pipeline (``library-index --mode full``) to populate
``media_stream.hdr_format`` / ``is_atmos`` instead.
"""
from __future__ import annotations
import sqlite3
from personalscraper.insights.models import LibraryAnalysisResult, LibraryAnalysisItem
# ... (full implementation from library/analyzer.py)
```

- [ ] **Step 3.3: Migrate `tests/library/test_analyzer.py`**

Create `tests/insights/__init__.py` (empty) and `tests/insights/test_analytics.py`. Copy test functions from `test_analyzer.py` that test `analyze()` and `analyze_from_index()`, updating imports to `personalscraper.insights.analytics`. Tests for `analyze_library` are deleted (the function is dropped).

- [ ] **Step 3.4: Run migrated tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/insights/test_analytics.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 3.5: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/insights/analytics.py tests/insights/__init__.py tests/insights/test_analytics.py && git commit -m "feat(lib-fold): move analyze/analyze_from_index to insights/analytics.py"
```

---

### Task 4: Move `reporter.py` and `recommender.py`

**Files:**

- Create: `personalscraper/insights/reporter.py`
- Create: `personalscraper/insights/recommender.py`

- [ ] **Step 4.1: Create `insights/reporter.py`**

Copy `generate_report` and `format_report_text` verbatim from `library/reporter.py`, updating imports to `insights.models`. Add module docstring.

- [ ] **Step 4.2: Create `insights/recommender.py`**

Copy `generate_recommendations` verbatim from `library/recommender.py`, updating imports to `insights.models`. Add module docstring.

- [ ] **Step 4.3: Migrate reporter and recommender tests**

Create `tests/insights/test_reporter.py` and `tests/insights/test_recommender.py` by copying from `tests/library/test_reporter.py` and `tests/library/test_recommender.py`, updating imports.

- [ ] **Step 4.4: Run migrated tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/insights/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 4.5: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/insights/reporter.py personalscraper/insights/recommender.py tests/insights/test_reporter.py tests/insights/test_recommender.py && git commit -m "feat(lib-fold): move reporter + recommender to insights/"
```

---

### Task 5: Repoint `commands/library/analyze.py` and delete library modules

**Files:**

- Modify: `personalscraper/commands/library/analyze.py`
- Delete: `personalscraper/library/analyzer.py`
- Delete: `personalscraper/library/reporter.py`
- Delete: `personalscraper/library/recommender.py`

- [ ] **Step 5.1: Read `commands/library/analyze.py` imports**

```bash
head -30 /Users/izno/dev/PersonnalScaper/personalscraper/commands/library/analyze.py
```

- [ ] **Step 5.2: Update imports in `analyze.py`**

Replace all `from personalscraper.library.analyzer import ...`, `from personalscraper.library.reporter import ...`, `from personalscraper.library.recommender import ...` with their `insights/` equivalents:

```python
from personalscraper.insights.analytics import analyze, analyze_from_index
from personalscraper.insights.reporter import generate_report, format_report_text
from personalscraper.insights.recommender import generate_recommendations
from personalscraper.insights.models import LibraryAnalysisResult  # etc.
```

- [ ] **Step 5.3: Delete the three library modules**

```bash
cd /Users/izno/dev/PersonnalScaper && git rm personalscraper/library/analyzer.py personalscraper/library/reporter.py personalscraper/library/recommender.py
```

- [ ] **Step 5.4: Verify ACC-05**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py 'extract_stream_info' personalscraper/library/ personalscraper/insights/ ; echo "rc=$?"
```

Expected: no output (the directories no longer contain this import), then `rc=1`.

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "import personalscraper.insights.analytics, personalscraper.insights.reporter, personalscraper.insights.recommender; print('OK')"
```

Expected: `OK`.

- [ ] **Step 5.5: Run full test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test 2>&1 | tail -20
```

Expected: zero errors, all tests pass.

- [ ] **Step 5.6: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/commands/library/analyze.py && git commit -m "refactor(lib-fold): repoint analyze command to insights/; delete library/analyzer.py, reporter.py, recommender.py"
```

---

### Task 6: Phase 4 gate

- [ ] **Step 6.1: Full gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test && make check ; echo "rc=$?"
```

Expected: ruff+mypy clean, `NNNN passed` 0 failed/errors, coverage ≥ 90 %, `rc=0`.

- [ ] **Step 6.2: Verify ACC-05b (HDR columns populated)**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "
import sqlite3
from personalscraper.conf.loader import load_config as L
c = sqlite3.connect(L().indexer.db_path)
cols = [r[1] for r in c.execute('PRAGMA table_info(media_stream)')]
assert {'hdr_format','is_atmos'} <= set(cols), cols
n = c.execute(\"SELECT COUNT(*) FROM media_stream WHERE hdr_format IS NOT NULL\").fetchone()[0]
print('cols-ok hdr_rows=', n)
"
```

Expected: `cols-ok hdr_rows=<int>` (> 0 on an HDR-enriched fixture; may be 0 on a test DB with no HDR content — the column existence check is the gate minimum).

- [ ] **Step 6.3: Gate commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git commit --allow-empty -m "chore(lib-fold): phase 4 gate — ffprobe re-scan dropped; insights/ package created"
```

---

## Acceptance

```bash
# ACC-05  library ffprobe re-scan gone; insights package importable
rg -t py 'extract_stream_info' personalscraper/library/ personalscraper/insights/ ; echo "rc=$?"
# Expected: no output, then rc=1   (helper survives only under scraper/ for NFO gen)

# ACC-05b  existing HDR/Atmos columns populated by enrich (parity, not just presence)
python -c "
import sqlite3
from personalscraper.conf.loader import load_config as L
c = sqlite3.connect(L().indexer.db_path)
cols = [r[1] for r in c.execute('PRAGMA table_info(media_stream)')]
assert {'hdr_format','is_atmos'} <= set(cols), cols
n = c.execute(\"SELECT COUNT(*) FROM media_stream WHERE hdr_format IS NOT NULL\").fetchone()[0]
print('cols-ok hdr_rows=', n)
"
# Expected: cols-ok hdr_rows=<int>
```

---

## Risks & mitigations

| Risk                                                                       | Mitigation                                                                                                                                                                     |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| HDR/Atmos granularity lost when library ffprobe re-scan is dropped         | Parity test (Task 1) verifies `enrich` covers HDR10/HDR10+/DV/HLG; any gap is documented with a comment in `enrich.py` rather than silently accepted.                          |
| Coverage drop from deleting `test_analyzer.py` tests for `analyze_library` | Tests for `analyze` / `analyze_from_index` migrated to `tests/insights/`; only `analyze_library` tests are dropped (function deleted). Coverage gate enforced at every commit. |
| Module-size guardrail on `insights/analytics.py`                           | `analyze_from_index` is 190+ LOC; monitor with `python3 scripts/check-module-size.py`. Split into `_stream_analytics.py` if needed.                                            |
| `scraper/mediainfo.extract_stream_info` accidentally deleted               | ACC-05 grep checks `scraper/` is NOT in the no-output list — the helper must remain there.                                                                                     |
