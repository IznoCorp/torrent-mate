# Phase 5 — `verify`/`maintenance` re-home + proactive no-NFO + delete `library/`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-home `validator.py` as a standalone `verify/library_checks.py` (NOT inlined into `checker.py`). Move `disk_cleaner.py` and `rescraper.py` into a new `maintenance/` package. Split the remaining `library/models.py` dataclasses to their correct homes per DESIGN §4.6. Add the proactive no-NFO visibility line to `library doctor` / `audit`. Delete `library/__init__.py` and the entire `library/` package. Gate: residual-import grep returns zero.

**Architecture:** `verify/checker.py` is already 716 non-blank LOC — inlining `validator.py` (395 LOC) would breach the 1000-LOC hard ceiling. `verify/library_checks.py` is a standalone module the future Check plugin system can register. `maintenance/` is distinct from `indexer/repair.py` (DB-only) because `disk_cleaner` and `rescraper` perform filesystem mutations.

**Tech Stack:** Python 3.11, SQLite, pytest, ruff, mypy, `python3 scripts/check-module-size.py`.

---

## Gate

Phase 4 must be complete:

- `python -c "import personalscraper.insights.analytics, personalscraper.insights.reporter, personalscraper.insights.recommender; print('OK')"` prints `OK`.
- `rg -t py 'extract_stream_info' personalscraper/library/ personalscraper/insights/` returns zero matches.
- `make lint && make test && make check` green.

---

## Objective

1. Create `personalscraper/verify/library_checks.py` — standalone re-home of `validator.py`; must NOT be inlined into `checker.py`.
2. Create `personalscraper/maintenance/__init__.py`, `maintenance/disk_cleaner.py`, `maintenance/rescraper.py`.
3. Split the remaining `library/models.py` dataclasses to their correct destinations per DESIGN §4.6:
   - `SeasonInfo`, `LibraryScanItem`, `NfoStatus`, `ArtworkStatus` → `indexer/scanner/_modes/_item_stage.py` types module (or a new `_item_stage_types.py` sibling to stay under size ceiling).
   - `ValidationItem`, `LibraryValidationResult` → `verify/library_checks.py`.
   - `RescrapeAction`, `LibraryRescrapeResult` → `maintenance/rescraper.py`.
4. Add proactive no-NFO visibility to `library doctor` and `library audit`: emit a line "N item(s) without a valid NFO — run `library-rescrape --target nfo_missing` to repair."
5. Repoint `commands/library/maintenance.py` to `maintenance/` and `verify/library_checks.py`.
6. Delete `library/__init__.py`, `library/models.py`, `library/validator.py`, `library/disk_cleaner.py`, `library/rescraper.py`.
7. Confirm `rg -t py 'personalscraper.library' personalscraper/ tests/` returns zero.

---

## Files to create / modify

| Action  | File                                                                                             |
| ------- | ------------------------------------------------------------------------------------------------ |
| Create  | `personalscraper/verify/library_checks.py`                                                       |
| Create  | `personalscraper/maintenance/__init__.py`                                                        |
| Create  | `personalscraper/maintenance/disk_cleaner.py`                                                    |
| Create  | `personalscraper/maintenance/rescraper.py`                                                       |
| Create  | `personalscraper/indexer/scanner/_modes/_item_stage_types.py` (if needed to stay under 1000 LOC) |
| Modify  | `personalscraper/commands/library/doctor.py`                                                     |
| Modify  | `personalscraper/commands/library/audit.py`                                                      |
| Modify  | `personalscraper/commands/library/maintenance.py`                                                |
| Delete  | `personalscraper/library/validator.py`                                                           |
| Delete  | `personalscraper/library/disk_cleaner.py`                                                        |
| Delete  | `personalscraper/library/rescraper.py`                                                           |
| Delete  | `personalscraper/library/models.py`                                                              |
| Delete  | `personalscraper/library/__init__.py`                                                            |
| Migrate | `tests/library/test_validator.py` → `tests/verify/test_library_checks.py`                        |
| Migrate | `tests/library/test_disk_cleaner.py` → `tests/maintenance/test_disk_cleaner.py`                  |
| Migrate | `tests/library/test_rescraper.py` → `tests/maintenance/test_rescraper.py`                        |
| Migrate | `tests/library/test_models.py` → distributed to new home test files                              |

---

## Sub-tasks

### Task 1: Create `verify/library_checks.py` — standalone validator re-home

**Files:**

- Create: `personalscraper/verify/library_checks.py`

- [ ] **Step 1.1: Read `library/validator.py` structure**

```bash
grep -n 'def \|^class ' /Users/izno/dev/PersonnalScaper/personalscraper/library/validator.py
wc -l /Users/izno/dev/PersonnalScaper/personalscraper/library/validator.py
```

- [ ] **Step 1.2: Check `verify/checker.py` current size**

```bash
python3 /Users/izno/dev/PersonnalScaper/scripts/check-module-size.py 2>&1 | grep checker
```

Expected: ~716 non-blank. Confirm inlining would breach 1000 → use standalone file.

- [ ] **Step 1.3: Create `verify/library_checks.py`**

Copy `library/validator.py` verbatim. Update imports from `library.models` to the new dataclass homes (see Task 4 for the split). Add module docstring:

```python
# personalscraper/verify/library_checks.py
"""Library media-item validation checks — standalone verify module.

Wraps :class:`verify.checker.MediaChecker` and :class:`verify.fixer.MediaFixer`
to produce per-item validation results. Kept standalone (NOT inlined into
``checker.py``) to respect the 1000-LOC hard ceiling on that module and to
enable future registration in the Check plugin system.

Dataclasses: ``ValidationItem``, ``LibraryValidationResult`` live here
(DESIGN §4.6 — validator is the producer/consumer).
"""
from __future__ import annotations
# ... (copy verbatim from library/validator.py, updating imports)
```

- [ ] **Step 1.4: Migrate `tests/library/test_validator.py`**

```bash
mkdir -p /Users/izno/dev/PersonnalScaper/tests/verify
touch /Users/izno/dev/PersonnalScaper/tests/verify/__init__.py
```

Copy test functions from `tests/library/test_validator.py` into `tests/verify/test_library_checks.py`, updating imports to `personalscraper.verify.library_checks`. Also copy `tests/library/test_validator_fix.py` if it exists.

- [ ] **Step 1.5: Run migrated tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/verify/test_library_checks.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 1.6: Check module size**

```bash
python3 /Users/izno/dev/PersonnalScaper/scripts/check-module-size.py 2>&1 | grep -E 'library_checks|WARN|BLOCK'
```

Expected: `library_checks.py` under 800 non-blank (soft warn).

- [ ] **Step 1.7: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/verify/library_checks.py tests/verify/__init__.py tests/verify/test_library_checks.py && git commit -m "feat(lib-fold): add verify/library_checks.py — standalone validator re-home"
```

---

### Task 2: Create `maintenance/` package with `disk_cleaner.py` and `rescraper.py`

**Files:**

- Create: `personalscraper/maintenance/__init__.py`
- Create: `personalscraper/maintenance/disk_cleaner.py`
- Create: `personalscraper/maintenance/rescraper.py`

- [ ] **Step 2.1: Read `library/disk_cleaner.py` key anchors**

```bash
grep -n 'def \|^class \|VIDEO_EXTENSIONS\|SEASON_DIR_RE\|_publish_deleted' /Users/izno/dev/PersonnalScaper/personalscraper/library/disk_cleaner.py | head -30
```

- [ ] **Step 2.2: Create `maintenance/__init__.py`**

```python
# personalscraper/maintenance/__init__.py
"""Operator-upkeep package for filesystem and re-scrape maintenance.

Distinct from ``indexer.repair`` (DB-only). This package performs
filesystem mutations (``disk_cleaner``) and targeted TMDB/TVDB re-scrapes
(``rescraper``).
"""
```

- [ ] **Step 2.3: Create `maintenance/disk_cleaner.py`**

Copy `library/disk_cleaner.py` verbatim. The `VIDEO_EXTENSIONS` and `SEASON_DIR_RE` local constants were already replaced with SSOT imports in Phase 0 — verify they now use `core.media_types` and `naming_patterns`. Update any remaining `library.*` imports. Add module docstring:

```python
# personalscraper/maintenance/disk_cleaner.py
"""Filesystem-level cleanup for the media library.

Performs ``rmtree``-based deletion (``_scandir_rmtree``), handles NTFS
ghost-dirents (macFUSE/NTFS known issue), and writes outbox events
(``_publish_deleted``) for downstream consumers.

Moved from ``library.disk_cleaner`` during lib-fold Phase 5.
"""
```

- [ ] **Step 2.4: Create `maintenance/rescraper.py`**

Copy `library/rescraper.py` verbatim. Update imports (`extract_nfo_ids`, `parse_title_year` → `nfo_utils`; `SEASON_DIR_RE` → `naming_patterns`; dataclasses → new homes). Add module docstring:

```python
# personalscraper/maintenance/rescraper.py
"""Targeted TMDB/TVDB re-scrape for library repair.

``rescrape_library`` walks ``media_item`` rows that ``_detect_needs``
flags (``needs_nfo = not is_nfo_complete``, stale artwork, etc.) and
re-scrapes them. Backs the ``library-rescrape`` CLI command.

Moved from ``library.rescraper`` during lib-fold Phase 5.
"""
```

- [ ] **Step 2.5: Migrate maintenance tests**

```bash
mkdir -p /Users/izno/dev/PersonnalScaper/tests/maintenance
touch /Users/izno/dev/PersonnalScaper/tests/maintenance/__init__.py
```

Copy `tests/library/test_disk_cleaner.py` → `tests/maintenance/test_disk_cleaner.py` (update imports).
Copy `tests/library/test_rescraper.py` → `tests/maintenance/test_rescraper.py` (update imports).

- [ ] **Step 2.6: Run migrated tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/maintenance/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 2.7: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/maintenance/ tests/maintenance/ && git commit -m "feat(lib-fold): create maintenance/ package — disk_cleaner + rescraper re-homed"
```

---

### Task 3: Split remaining `library/models.py` dataclasses to correct homes

**Files:**

- Modify: `personalscraper/indexer/scanner/_modes/_item_stage.py` (or new `_item_stage_types.py`)
- Modify: `personalscraper/verify/library_checks.py`
- Modify: `personalscraper/maintenance/rescraper.py`

- [ ] **Step 3.1: Read the remaining dataclasses in `library/models.py`**

```bash
grep -n '^@dataclass\|^class ' /Users/izno/dev/PersonnalScaper/personalscraper/library/models.py
```

Per DESIGN §4.6, the remaining un-migrated classes are:

- `SeasonInfo`, `LibraryScanItem`, `NfoStatus`, `ArtworkStatus` → `_item_stage` (or `_item_stage_types.py` sibling)
- `ValidationItem`, `LibraryValidationResult` → already placed in `verify/library_checks.py` (Task 1)
- `RescrapeAction`, `LibraryRescrapeResult` → already placed in `maintenance/rescraper.py` (Task 2)

- [ ] **Step 3.2: Move scan-stage types**

If `_item_stage.py` is already ≥ 700 non-blank LOC, create a sibling:

```bash
python3 /Users/izno/dev/PersonnalScaper/scripts/check-module-size.py 2>&1 | grep _item_stage
```

If under the soft warn, append `SeasonInfo`, `LibraryScanItem`, `NfoStatus`, `ArtworkStatus` directly to `_item_stage.py`. Otherwise create `_item_stage_types.py`:

```python
# personalscraper/indexer/scanner/_modes/_item_stage_types.py
"""Dataclasses produced and consumed by the item-stage scan pass.

``NfoStatus`` and ``ArtworkStatus`` are cross-consumer (also used by
``verify.library_checks``) — they live with their producer (DESIGN §4.6).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
# ... (copy SeasonInfo, LibraryScanItem, NfoStatus, ArtworkStatus verbatim)
```

Update `verify/library_checks.py` to import `NfoStatus`, `ArtworkStatus` from `_item_stage_types` (or `_item_stage`) rather than `library.models`.

- [ ] **Step 3.3: Run full test suite (no deletions yet)**

```bash
cd /Users/izno/dev/PersonnalScaper && make test 2>&1 | tail -20
```

Expected: all pass. This confirms the new import chains are correct before any deletion.

- [ ] **Step 3.4: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/indexer/scanner/_modes/ personalscraper/verify/library_checks.py personalscraper/maintenance/rescraper.py && git commit -m "refactor(lib-fold): distribute library/models.py dataclasses to producer homes (§4.6)"
```

---

### Task 4: Add proactive no-NFO visibility to `library doctor` and `library audit`

**Files:**

- Modify: `personalscraper/commands/library/doctor.py`
- Modify: `personalscraper/commands/library/audit.py`

- [ ] **Step 4.1: Add an `nfo_missing` check function to `doctor.py`**

```python
def _check_nfo_missing(conn: sqlite3.Connection) -> CheckResult:
    """Report items without a valid NFO so the operator can run library-rescrape.

    Args:
        conn: Open SQLite connection to the indexer DB.

    Returns:
        CheckResult with status ``warn`` when NFO-less items exist, ``ok`` otherwise.
    """
    count = conn.execute(
        "SELECT COUNT(DISTINCT item_id) FROM item_issue WHERE type IN ('nfo_missing','nfo_incomplete')"
    ).fetchone()[0]
    if count == 0:
        return CheckResult(name="nfo_missing", status=CheckStatus.ok, message="All items have a valid NFO.")
    return CheckResult(
        name="nfo_missing",
        status=CheckStatus.warn,
        message=(
            f"{count} item(s) without a valid NFO — "
            "run `library-rescrape --target nfo_missing` to repair."
        ),
    )
```

Register `_check_nfo_missing` in the `run_doctor` check list alongside the existing checks.

- [ ] **Step 4.2: Add the no-NFO line to `library audit` output**

In `audit.py`, add a query for `item_issue` rows of type `nfo_missing` / `nfo_incomplete` and emit a summary line in the audit output:

```python
nfo_missing_count = conn.execute(
    "SELECT COUNT(DISTINCT item_id) FROM item_issue WHERE type IN ('nfo_missing','nfo_incomplete')"
).fetchone()[0]
if nfo_missing_count > 0:
    console.print(
        f"[yellow]⚠ {nfo_missing_count} item(s) without a valid NFO — "
        "run `library-rescrape --target nfo_missing` to repair.[/yellow]"
    )
```

- [ ] **Step 4.3: Verify ACC-06b**

```bash
cd /Users/izno/dev/PersonnalScaper && personalscraper library-doctor 2>&1 | rg -i 'nfo' ; echo "rc=$?"
```

Expected: a line mentioning items without a valid NFO; `rc=0`.

- [ ] **Step 4.4: Run doctor and audit tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/commands/test_library_doctor.py tests/commands/test_library_doctor_e2e.py tests/commands/test_library_audit.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 4.5: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/commands/library/doctor.py personalscraper/commands/library/audit.py && git commit -m "feat(lib-fold): add proactive no-NFO visibility to library-doctor and library-audit"
```

---

### Task 5: Repoint `commands/library/maintenance.py` and delete `library/`

**Files:**

- Modify: `personalscraper/commands/library/maintenance.py`
- Delete: `personalscraper/library/validator.py`, `disk_cleaner.py`, `rescraper.py`, `models.py`, `__init__.py`

- [ ] **Step 5.1: Read `commands/library/maintenance.py` imports**

```bash
head -30 /Users/izno/dev/PersonnalScaper/personalscraper/commands/library/maintenance.py
```

- [ ] **Step 5.2: Update imports**

Replace all `from personalscraper.library.disk_cleaner import ...`, `from personalscraper.library.validator import ...`, `from personalscraper.library.models import ...` with their new-home equivalents:

```python
from personalscraper.maintenance.disk_cleaner import ...
from personalscraper.maintenance.rescraper import ...
from personalscraper.verify.library_checks import ...
```

- [ ] **Step 5.3: Run `test_library_maintenance.py` to confirm repoint works**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/commands/test_library_maintenance.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 5.4: Final residual-import grep before deletion**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py 'personalscraper\.library' personalscraper/ tests/ ; echo "rc=$?"
```

Expected: zero matches, `rc=1`. If any remain, fix them before proceeding to deletion.

- [ ] **Step 5.5: Delete all remaining `library/` modules**

```bash
cd /Users/izno/dev/PersonnalScaper && git rm personalscraper/library/validator.py personalscraper/library/disk_cleaner.py personalscraper/library/rescraper.py personalscraper/library/models.py personalscraper/library/__init__.py
rmdir personalscraper/library/ 2>/dev/null || true
```

- [ ] **Step 5.6: Verify ACC-06 — library/ gone, all files re-homed, zero residual imports**

```bash
test -f /Users/izno/dev/PersonnalScaper/personalscraper/verify/library_checks.py && \
test -f /Users/izno/dev/PersonnalScaper/personalscraper/maintenance/disk_cleaner.py && \
test -f /Users/izno/dev/PersonnalScaper/personalscraper/maintenance/rescraper.py && \
echo "rehomed"

cd /Users/izno/dev/PersonnalScaper && rg -t py 'personalscraper\.library' personalscraper/ tests/ ; echo "rc=$?"

test ! -d /Users/izno/dev/PersonnalScaper/personalscraper/library && echo "package removed"
```

Expected: `rehomed` ; then no output, then `rc=1` ; then `package removed`.

- [ ] **Step 5.7: Commit deletion**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/commands/library/maintenance.py && git commit -m "refactor(lib-fold): repoint maintenance command; delete library/ package"
```

---

### Task 6: Phase 5 gate

- [ ] **Step 6.1: Full gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test && make check ; echo "rc=$?"
```

Expected: ruff+mypy clean, `NNNN passed` 0 failed/errors, coverage ≥ 90 %, `rc=0`.

- [ ] **Step 6.2: Module-size check (ACC-06c)**

```bash
cd /Users/izno/dev/PersonnalScaper && python3 scripts/check-module-size.py ; echo "rc=$?"
```

Expected: `rc=0` — no module ≥ 1000 non-blank LOC.

- [ ] **Step 6.3: Smoke test**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "import personalscraper; print('import-ok')"
```

Expected: `import-ok`.

- [ ] **Step 6.4: Gate commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git commit --allow-empty -m "chore(lib-fold): phase 5 gate — library/ deleted; verify+maintenance re-homed; no-NFO visible"
```

---

## Acceptance

```bash
# ACC-06  all files re-homed; library/ gone; zero residual imports
test -f personalscraper/verify/library_checks.py && test -f personalscraper/maintenance/disk_cleaner.py && test -f personalscraper/maintenance/rescraper.py && echo "rehomed"
rg -t py 'personalscraper\.library' personalscraper/ tests/ ; echo "rc=$?"
test ! -d personalscraper/library && echo "package removed"
# Expected: rehomed ; then no output, then rc=1 ; then package removed

# ACC-06b  proactive no-NFO visibility in doctor output
personalscraper library-doctor 2>&1 | rg -i 'nfo' ; echo "rc=$?"
# Expected: a line mentioning items without a valid NFO; rc=0

# ACC-06c  module-size hard ceiling respected
python3 scripts/check-module-size.py ; echo "rc=$?"
# Expected: rc=0

# ACC-SMOKE
python -c "import personalscraper; print('import-ok')"
# Expected: import-ok
```

---

## Risks & mitigations

| Risk                                                                  | Mitigation                                                                                                                            |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Test re-homing (~9773 LOC / 16 files) drops branch coverage below 90% | Each gate runs `make check` (coverage included); migrate unique coverage in Tasks 1–2 before deletion; do not just delete test files. |
| Module-size guardrail dodge via `__init__.py`                         | Re-homed bodies go in named non-`__init__` files (`library_checks.py`, `disk_cleaner.py`, etc.); ACC-06c gate enforces the ceiling.   |
| `_item_stage.py` size explosion after absorbing scan-stage types      | Monitor with `check-module-size.py` in Step 3.2; create `_item_stage_types.py` sibling if needed.                                     |
| `verify/checker.py` accidentally absorbs validator inline             | Task 1 creates `verify/library_checks.py` as a standalone file; a size check in Step 1.6 catches any accidental inlining.             |
| Residual imports missed in test files                                 | Step 5.4 runs the full grep including `tests/` before any deletion; zero-match is a hard prerequisite for deletion.                   |
