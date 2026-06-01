# Phase 0 — Season-dir SSOT (widen-first) + VIDEO_EXTENSIONS

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the canonical `SEASON_DIR_RE` to the FR+EN+Specials union and add `season_number_from_dir()`, guard it with a no-regression test, then replace all 5 ad-hoc copies. Kill local `VIDEO_EXTENSIONS` re-definitions pointing to `core.media_types`.

**Architecture:** Widen first, replace second — reversing this order would silently drop `Season N` / `Specials` matches from callers that currently rely on the wider ad-hoc patterns.

**Tech Stack:** Python 3.11, `re`, pytest, ruff, mypy.

---

## Gate

_Phase 0 is the first phase — no predecessor gate required._

---

## Objective

1. Widen `naming_patterns.SEASON_DIR_RE` (currently `^Saison (\d+)$`, French-only) to match `Saison N`, `Season N`, and `Specials` (all case-insensitive on the keyword, case-sensitive on the capital).
2. Add `season_number_from_dir(name: str) -> int | None` to `naming_patterns.py`: returns the season number from `Saison N` / `Season N`, returns `0` for `Specials`, returns `None` for non-matching names.
3. Replace the 5 ad-hoc copies with imports of the canonical SSOT.
4. Remove local `VIDEO_EXTENSIONS` re-definitions (not re-imports) in `library/` modules, replacing with imports from `core.media_types`.

---

## Files to create / modify

| Action        | File                                                                           |
| ------------- | ------------------------------------------------------------------------------ |
| Modify        | `personalscraper/naming_patterns.py`                                           |
| Modify        | `personalscraper/library/disk_cleaner.py` (line 68 ad-hoc copy)                |
| Modify        | `personalscraper/indexer/scanner/_modes/enrich.py` (line 122 ad-hoc copy)      |
| Modify        | `personalscraper/indexer/scanner/_modes/incremental.py` (line 667 ad-hoc copy) |
| Modify        | `personalscraper/indexer/release_linker.py` (line 34 capture-group copy)       |
| Modify        | `personalscraper/trailers/scanner.py` (line 27 2-digit French-only copy)       |
| Create/Modify | `tests/test_naming_patterns.py` (no-regression + new behaviour)                |

---

## Sub-tasks

### Task 1: Write the no-regression test FIRST (TDD)

**Files:**

- Create/Modify: `tests/test_naming_patterns.py`

- [ ] **Step 1.1: Write the failing tests**

Check whether `tests/test_naming_patterns.py` already exists:

```bash
ls tests/test_naming_patterns.py 2>/dev/null || echo "does not exist"
```

Write (or append) these tests:

```python
# tests/test_naming_patterns.py
import pytest
from personalscraper.naming_patterns import SEASON_DIR_RE, season_number_from_dir


# --- SEASON_DIR_RE no-regression: every form any of the 5 ad-hoc copies matched ---

@pytest.mark.parametrize("name", [
    # French forms (canonical — must always have matched)
    "Saison 1", "Saison 01", "Saison 12",
    # English forms (matched by disk_cleaner / enrich / incremental copies)
    "Season 1", "Season 01", "Season 12",
    # Specials (matched by disk_cleaner / enrich / incremental copies)
    "Specials", "Special",
    # Mixed-case keywords (the ad-hoc copies used re.IGNORECASE on the keyword)
    "saison 3", "season 3",
])
def test_season_dir_re_matches(name: str) -> None:
    assert SEASON_DIR_RE.match(name), f"SEASON_DIR_RE did not match {name!r}"


@pytest.mark.parametrize("name", [
    "Movies", "2023", "Extras", "Behind the Scenes", "",
])
def test_season_dir_re_does_not_match(name: str) -> None:
    assert not SEASON_DIR_RE.match(name), f"SEASON_DIR_RE wrongly matched {name!r}"


# --- season_number_from_dir ---

@pytest.mark.parametrize("name,expected", [
    ("Saison 3", 3),
    ("Saison 03", 3),
    ("Season 12", 12),
    ("Specials", 0),
    ("Special", 0),
    ("saison 5", 5),
    ("season 5", 5),
    ("Movies", None),
    ("", None),
])
def test_season_number_from_dir(name: str, expected: int | None) -> None:
    assert season_number_from_dir(name) == expected
```

- [ ] **Step 1.2: Run to confirm they fail (SEASON_DIR_RE is currently French-only)**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/test_naming_patterns.py -v 2>&1 | tail -30
```

Expected: most parametrize cases for English/Specials FAIL with `AssertionError`; `season_number_from_dir` fails with `ImportError`.

---

### Task 2: Widen `naming_patterns.py`

**Files:**

- Modify: `personalscraper/naming_patterns.py`

- [ ] **Step 2.1: Read the current SEASON_DIR_RE area**

```bash
grep -n 'SEASON_DIR_RE\|season_dir\|_build_dir_regex\|season_number' /Users/izno/dev/PersonnalScaper/personalscraper/naming_patterns.py
```

- [ ] **Step 2.2: Replace the SEASON_DIR_RE definition and add the helper**

The current `SEASON_DIR_RE` is built from `_build_dir_regex(PATTERNS.season_dir)` which resolves to `^Saison (\d+)$`. Replace the single line that assigns `SEASON_DIR_RE` with an explicit widened pattern, and add `season_number_from_dir` immediately after:

```python
import re as _re

# Widened to FR+EN+Specials union — the authoritative SSOT used by all callers.
# Matches: "Saison N", "Season N" (any digit count, case-insensitive keyword),
# "Specials", "Special" (case-insensitive).
SEASON_DIR_RE: _re.Pattern[str] = _re.compile(
    r"^(?:saison|season)\s+(\d+)$|^specials?$",
    _re.IGNORECASE,
)


def season_number_from_dir(name: str) -> int | None:
    """Return the season number from a season directory name.

    Args:
        name: Directory name, e.g. ``"Saison 3"``, ``"Season 12"``,
            ``"Specials"``.

    Returns:
        Season number as int (0 for Specials/Special, positive int for
        numbered seasons), or ``None`` when ``name`` does not match any
        known season-directory form.
    """
    m = SEASON_DIR_RE.match(name)
    if m is None:
        return None
    # Group 1 is present for "Saison N" / "Season N"; absent for "Specials".
    return int(m.group(1)) if m.lastindex and m.group(1) else 0
```

- [ ] **Step 2.3: Verify tests now pass**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/test_naming_patterns.py -v 2>&1 | tail -20
```

Expected: all tests PASS.

- [ ] **Step 2.4: Run lint**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint 2>&1 | tail -20
```

Expected: zero errors.

- [ ] **Step 2.5: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/naming_patterns.py tests/test_naming_patterns.py && git commit -m "feat(lib-fold): widen SEASON_DIR_RE to FR+EN+Specials; add season_number_from_dir"
```

---

### Task 3: Replace the 5 ad-hoc season-regex copies

**Files:**

- Modify: `personalscraper/library/disk_cleaner.py`
- Modify: `personalscraper/indexer/scanner/_modes/enrich.py`
- Modify: `personalscraper/indexer/scanner/_modes/incremental.py`
- Modify: `personalscraper/indexer/release_linker.py`
- Modify: `personalscraper/trailers/scanner.py`

- [ ] **Step 3.1: Replace `disk_cleaner.py:68` ad-hoc copy**

Remove the local `_TV_SEASON_DIR_RE = re.compile(...)` constant (line 68) and replace with:

```python
from personalscraper.naming_patterns import SEASON_DIR_RE as _TV_SEASON_DIR_RE
```

All downstream uses of `_TV_SEASON_DIR_RE` in `disk_cleaner.py` remain unchanged (the alias preserves the local name).

- [ ] **Step 3.2: Replace `enrich.py:122` ad-hoc copy**

Remove the local `_TV_SEASON_DIR_RE = re.compile(...)` constant and replace with:

```python
from personalscraper.naming_patterns import SEASON_DIR_RE as _TV_SEASON_DIR_RE
```

- [ ] **Step 3.3: Replace `incremental.py:667` ad-hoc copy**

Same pattern — remove local definition, add import alias.

> **NOTE (2026-05-31, C0 correction):** The Phase 0 audit found that
> `incremental.py`'s local `_TV_SEASON_DIR_RE` had **zero consumers** (dead code).
> Rather than adding an unused import alias (which would be dead code / ruff F401),
> the constant was simply **deleted** with no replacement. This is a correct
> resolution of the plan's literal step text, which assumed the constant was
> live.

- [ ] **Step 3.4: Replace `release_linker.py:34` capture-group copy**

`release_linker.py` uses `parse_season_dir()` which internally uses `_SEASON_DIR_RE`. Replace both the constant and the helper:

```python
from personalscraper.naming_patterns import season_number_from_dir as parse_season_dir
```

Remove the local `_SEASON_DIR_RE` constant and the local `parse_season_dir` function entirely.

- [ ] **Step 3.5: Replace `trailers/scanner.py:27` 2-digit French-only copy**

Remove `_SEASON_DIR_RE = re.compile(r"^Saison (\d{2})$")` and replace usages with `SEASON_DIR_RE` from `naming_patterns`:

```python
from personalscraper.naming_patterns import SEASON_DIR_RE as _SEASON_DIR_RE
```

The widened pattern is a superset — 2-digit French still matches.

- [ ] **Step 3.6: Verify ACC-00 and ACC-00b**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py '_TV_SEASON_DIR_RE *=|_SEASON_DIR_RE *=' personalscraper/library/ personalscraper/indexer/ personalscraper/trailers/ ; echo "rc=$?"
```

Expected: no output, then `rc=1`.

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "from personalscraper.naming_patterns import SEASON_DIR_RE as r; assert all(r.match(s) for s in ['Saison 1','Saison 01','Season 1','Specials']); print('OK')"
```

Expected: `OK`.

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "from personalscraper.naming_patterns import season_number_from_dir as f; assert f('Saison 3')==3 and f('Season 12')==12 and f('Specials') in (0, None); print('OK')"
```

Expected: `OK`.

- [ ] **Step 3.7: Run tests**

```bash
cd /Users/izno/dev/PersonnalScaper && make test 2>&1 | tail -20
```

Expected: all tests pass, 0 failed/errors.

- [ ] **Step 3.8: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/library/disk_cleaner.py personalscraper/indexer/scanner/_modes/enrich.py personalscraper/indexer/scanner/_modes/incremental.py personalscraper/indexer/release_linker.py personalscraper/trailers/scanner.py && git commit -m "refactor(lib-fold): replace 5 ad-hoc season-regex copies with naming_patterns SSOT"
```

---

### Task 4: Kill local `VIDEO_EXTENSIONS` re-definitions in `library/`

**Files:**

- Modify: `personalscraper/library/disk_cleaner.py`
- (check others in `library/` before editing)

- [ ] **Step 4.1: Pin which files have re-DEFINITIONS (not re-imports)**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py 'VIDEO_EXTENSIONS\s*[:=]\s*frozenset|VIDEO_EXTENSIONS\s*=\s*\{' personalscraper/library/ ; echo "rc=$?"
```

Expected: any hits are the targets; if `rc=1` there are none and this task is already done.

- [ ] **Step 4.2: For each re-definition found, replace with an import**

Replace any local `_VIDEO_EXTENSIONS = frozenset({...})` or `VIDEO_EXTENSIONS = frozenset({...})` constant with:

```python
from personalscraper.core.media_types import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS
```

(Use whatever local alias the consuming code uses.)

- [ ] **Step 4.3: Verify ACC-00d**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py 'VIDEO_EXTENSIONS\s*[:=]\s*frozenset|VIDEO_EXTENSIONS\s*=\s*\{' personalscraper/library/ ; echo "rc=$?"
```

Expected: no output, then `rc=1`.

- [ ] **Step 4.4: Run tests and lint**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test 2>&1 | tail -20
```

Expected: zero lint errors, all tests pass.

- [ ] **Step 4.5: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/library/disk_cleaner.py && git commit -m "refactor(lib-fold): replace local VIDEO_EXTENSIONS re-definitions with core.media_types SSOT"
```

---

### Task 5: Phase 0 gate

- [ ] **Step 5.1: Full gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint && make test && make check ; echo "rc=$?"
```

Expected: ruff+mypy clean, `NNNN passed` 0 failed/errors, coverage ≥ 90 %, `rc=0`.

- [ ] **Step 5.2: Gate commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git commit --allow-empty -m "chore(lib-fold): phase 0 gate — season SSOT + VIDEO_EXTENSIONS"
```

---

## Acceptance

```bash
# ACC-00  no ad-hoc season-dir regex constant left in migrated files
rg -t py '_TV_SEASON_DIR_RE *=|_SEASON_DIR_RE *=' personalscraper/library/ personalscraper/indexer/ personalscraper/trailers/ ; echo "rc=$?"
# Expected: no output, then rc=1

# NOTE (2026-05-31, C0 correction): the canonical SEASON_DIR_RE uses \s* (zero-or-more spaces)
# to match the FULL union of the 5 ad-hoc copies, including no-space degenerate forms like
# 'Season1' / 'Saison1' / 'saison5' that the original \s* copies matched. This is the
# DESIGN §3.4 parity promise: "every form each copy matched still matches."

# ACC-00b  widened canonical matches French + English + Specials
python -c "from personalscraper.naming_patterns import SEASON_DIR_RE as r; assert all(r.match(s) for s in ['Saison 1','Saison 01','Season 1','Specials']); print('OK')"
# Expected: OK

# ACC-00c  numbered helper extracts the season number
python -c "from personalscraper.naming_patterns import season_number_from_dir as f; assert f('Saison 3')==3 and f('Season 12')==12 and f('Specials') in (0,None); print('OK')"
# Expected: OK

# ACC-00d  VIDEO_EXTENSIONS SSOT is core.media_types (no library re-definition)
rg -t py 'VIDEO_EXTENSIONS\s*[:=]\s*frozenset|VIDEO_EXTENSIONS\s*=\s*\{' personalscraper/library/ ; echo "rc=$?"
# Expected: no output, then rc=1
```

---

## Risks & mitigations

| Risk                                                                          | Mitigation                                                                                                                                                     |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **#1 — Folding before widening silently loses English/Specials matches**      | Task ordering is strict: widen + regression-test in Task 1–2 BEFORE any replacement in Task 3. Never reverse the order.                                        |
| Season-regex change in `trailers`/`release_linker` alters placement behaviour | Phase 0 regression tests (Task 1) assert the NEW correct behaviour for all forms, not just French equality.                                                    |
| `re.compile` flag differences between ad-hoc copies and canonical             | The widened canonical uses `re.IGNORECASE` on the keyword part only (keyword is in alternation); all ad-hoc copies used `re.IGNORECASE` — verified consistent. |
