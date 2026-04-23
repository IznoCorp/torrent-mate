# Phase 4 — Clean Source Code

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all VX tags from comments and docstrings in 41 Python files. Zero logic changes. One commit per module.

**Architecture:** 10 module sweeps in sequence. After each sweep: grep check + `make test && make lint`. Special case: `conf/migration.py` — reword comments only, never touch `.v14.bak` code paths.

**Tech Stack:** Python (comments/docstrings only), make, git

---

## Gate (entry condition)

Phase 3 must be complete. Verify:

```bash
cd "/Volumes/IznoServer SSD/A TRIER"

# Gate 1: reference docs clean
grep -n "\bV[0-9]\+\b" docs/reference/*.md | grep -v "Python 3\|TMDB\|TVDB\|VERSION"
# expected: no output

# Gate 2: commit exists
git log --oneline | grep "clean reference docs of VX refs"
# expected: one matching line
```

---

## Detection Rules (relevant to this phase)

| Pattern                       | Meaning                                   | Action                      |
| ----------------------------- | ----------------------------------------- | --------------------------- |
| `\bV[0-9]+\b`                 | "V3", "V12", "V14" in comments/docstrings | remove                      |
| `\bv[0-9]+\b`                 | "v3", "v12" lowercase                     | remove (context check)      |
| `V[0-9]+\.x`                  | "V7.x"                                    | remove                      |
| `V[0-9]+\+V[0-9]+`            | "V9+V10+V13"                              | reformulate                 |
| `\.v14\.bak`                  | runtime backup filename                   | **KEEP** (runtime contract) |
| `\.personalscraper\.v14\.bak` | runtime backup                            | **KEEP**                    |
| `Python 3\.10\+`              | Python version                            | **KEEP**                    |
| `TMDB v3 API`, `TVDB v4 API`  | external API version                      | **KEEP**                    |

### Strict invariants for every sub-phase

- Edit **only** lines inside `# …` comments or `"""…"""` / `'''…'''` docstrings
- No change to variable names, function names, class names, imports, or control flow
- `git diff` for each commit must show only comment/docstring lines changed
- `make test && make lint` must be green after each commit

---

## Sub-phase 4.1 — Top-level files

**Files:** `personalscraper/cli.py`, `config.py`, `models.py`, `naming_patterns.py`, `pipeline.py`, `text_utils.py`

- [ ] **Step 1: Scan**

```bash
grep -n "\bV[0-9]\+\b\|V[0-9]\++V[0-9]\+" \
  "/Volumes/IznoServer SSD/A TRIER/personalscraper/cli.py" \
  "/Volumes/IznoServer SSD/A TRIER/personalscraper/config.py" \
  "/Volumes/IznoServer SSD/A TRIER/personalscraper/models.py" \
  "/Volumes/IznoServer SSD/A TRIER/personalscraper/naming_patterns.py" \
  "/Volumes/IznoServer SSD/A TRIER/personalscraper/pipeline.py" \
  "/Volumes/IznoServer SSD/A TRIER/personalscraper/text_utils.py"
```

- [ ] **Step 2: Edit each file — comments/docstrings only**
- [ ] **Step 3: Verify + test + commit**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
grep -n "\bV[0-9]\+\b" personalscraper/cli.py personalscraper/config.py \
  personalscraper/models.py personalscraper/naming_patterns.py \
  personalscraper/pipeline.py personalscraper/text_utils.py
# expected: no output
make test && make lint
git add personalscraper/cli.py personalscraper/config.py personalscraper/models.py \
        personalscraper/naming_patterns.py personalscraper/pipeline.py personalscraper/text_utils.py
git commit -m "chore(legacy-cleanup): strip VX refs from top-level modules"
```

---

## Sub-phase 4.2 — commands/

**Files:** `personalscraper/commands/init_config.py`

- [ ] **Step 4: Scan, edit, verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/commands/init_config.py"
# edit file
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/commands/init_config.py"
# expected: no output
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/commands/init_config.py
git commit -m "chore(legacy-cleanup): strip VX refs from commands module"
```

---

## Sub-phase 4.3 — conf/

**Files:** `personalscraper/conf/__init__.py`, `classifier.py`, `migration.py`, `models.py`, `resolver.py`

**Special case `migration.py`:** The code that creates/reads `.v14.bak` files is a runtime contract — do NOT touch string literals, file names, or any identifier referring to `.v14.bak`. Only reword comments and docstrings. Replace "V14 format" with "legacy format", "V15 format" with "current format".

**Concrete rewording examples** (to disambiguate comment vs runtime filename):

```python
# BEFORE
"""Migrate V14 library_index.json to V15 format."""
# Backup original as library_index.json.v14.bak

# AFTER
"""Migrate legacy library_index.json to the current format.

Backups use the .v14.bak suffix (runtime contract — do not rename).
"""
# Backup original as library_index.json.v14.bak (legacy-suffix marker)
```

Key rule: the `.v14.bak` suffix **is the runtime contract** and stays verbatim in both code AND comments. Only wording _around_ it changes.

- [ ] **Step 5: Scan**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/conf/"*.py
```

- [ ] **Step 6: Edit — reword comments/docstrings only. In migration.py: leave all `.v14.bak` string literals untouched.**
- [ ] **Step 7: Verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/conf/"*.py
# expected: no output (v14.bak string literals are exempt — verify they are still present)
grep "v14\.bak" "/Volumes/IznoServer SSD/A TRIER/personalscraper/conf/migration.py"
# expected: at least one line (runtime contract intact)
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/conf/__init__.py personalscraper/conf/classifier.py \
        personalscraper/conf/migration.py personalscraper/conf/models.py \
        personalscraper/conf/resolver.py
git commit -m "chore(legacy-cleanup): strip VX refs from conf module"
```

---

## Sub-phase 4.4 — ingest/

**Files:** `personalscraper/ingest/__init__.py`

- [ ] **Step 8: Scan, edit, verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/ingest/__init__.py"
# edit file
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/ingest/__init__.py"
# expected: no output
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/ingest/__init__.py
git commit -m "chore(legacy-cleanup): strip VX refs from ingest module"
```

---

## Sub-phase 4.5 — sorter/

**Files:** `personalscraper/sorter/__init__.py`, `cleaner.py`, `matcher.py`, `run.py`, `sorter.py`, `strategies.py`

- [ ] **Step 9: Scan**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/sorter/"*.py
```

- [ ] **Step 10: Edit — comments/docstrings only**
- [ ] **Step 11: Verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/sorter/"*.py
# expected: no output
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/sorter/__init__.py personalscraper/sorter/cleaner.py \
        personalscraper/sorter/matcher.py personalscraper/sorter/run.py \
        personalscraper/sorter/sorter.py personalscraper/sorter/strategies.py
git commit -m "chore(legacy-cleanup): strip VX refs from sorter module"
```

---

## Sub-phase 4.6 — scraper/

**Files:** `personalscraper/scraper/__init__.py`, `episode_manager.py`, `mediainfo.py`, `nfo_generator.py`, `providers.py`, `run.py`, `scraper.py`

- [ ] **Step 12: Scan**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/scraper/"*.py
```

- [ ] **Step 13: Edit — comments/docstrings only**
- [ ] **Step 14: Verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/scraper/"*.py
# expected: no output
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/scraper/__init__.py personalscraper/scraper/episode_manager.py \
        personalscraper/scraper/mediainfo.py personalscraper/scraper/nfo_generator.py \
        personalscraper/scraper/providers.py personalscraper/scraper/run.py \
        personalscraper/scraper/scraper.py
git commit -m "chore(legacy-cleanup): strip VX refs from scraper module"
```

---

## Sub-phase 4.7 — verify/

**Files:** `personalscraper/verify/checker.py`, `run.py`, `verifier.py`

- [ ] **Step 15: Scan**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/verify/"*.py
```

- [ ] **Step 16: Edit — comments/docstrings only**
- [ ] **Step 17: Verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/verify/"*.py
# expected: no output
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/verify/checker.py personalscraper/verify/run.py \
        personalscraper/verify/verifier.py
git commit -m "chore(legacy-cleanup): strip VX refs from verify module"
```

---

## Sub-phase 4.8 — enforce/

**Files:** `personalscraper/enforce/coherence_checker.py`, `run.py`

- [ ] **Step 18: Scan**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/enforce/"*.py
```

- [ ] **Step 19: Edit — comments/docstrings only**
- [ ] **Step 20: Verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/enforce/"*.py
# expected: no output
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/enforce/coherence_checker.py personalscraper/enforce/run.py
git commit -m "chore(legacy-cleanup): strip VX refs from enforce module"
```

---

## Sub-phase 4.9 — dispatch/

**Files:** `personalscraper/dispatch/dispatcher.py`, `disk_scanner.py`, `media_index.py`, `run.py`

- [ ] **Step 21: Scan**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/dispatch/"*.py
```

- [ ] **Step 22: Edit — comments/docstrings only**
- [ ] **Step 23: Verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/dispatch/"*.py
# expected: no output
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/dispatch/dispatcher.py personalscraper/dispatch/disk_scanner.py \
        personalscraper/dispatch/media_index.py personalscraper/dispatch/run.py
git commit -m "chore(legacy-cleanup): strip VX refs from dispatch module"
```

---

## Sub-phase 4.10 — library/

**Files:** `personalscraper/library/analyzer.py`, `disk_cleaner.py`, `models.py`, `rescraper.py`, `scanner.py`, `validator.py`

- [ ] **Step 24: Scan**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/library/"*.py
```

- [ ] **Step 25: Edit — comments/docstrings only**
- [ ] **Step 26: Verify, test, commit**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/personalscraper/library/"*.py
# expected: no output
cd "/Volumes/IznoServer SSD/A TRIER" && make test && make lint
git add personalscraper/library/analyzer.py personalscraper/library/disk_cleaner.py \
        personalscraper/library/models.py personalscraper/library/rescraper.py \
        personalscraper/library/scanner.py personalscraper/library/validator.py
git commit -m "chore(legacy-cleanup): strip VX refs from library module"
```

---

## Phase 4 gate check (after all 10 sub-phases)

- [ ] **Step 27: Full source gate**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"

# Check 1: no VX refs anywhere in personalscraper/
grep -rn "\bV[0-9]\+\b" personalscraper/ --include="*.py" | \
  grep -v "Python 3\|TMDB\|TVDB\|VERSION\|\.v14\.bak"
# expected: no output

# Check 2: runtime contract intact
grep "v14\.bak" personalscraper/conf/migration.py
# expected: at least one line

# Check 3: full test suite green
make test && make lint
```

---

## Exit condition for Phase 5

Phase 5 may start only when:

- `grep -rn "\bV[0-9]+\b" personalscraper/ --include="*.py"` returns no project-version matches
- `make test && make lint` is green
- All 10 module commits are on the branch `feat/legacy-cleanup`
- `conf/migration.py` still contains `.v14.bak` runtime code (verify with grep)
