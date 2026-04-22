# Phase 4 — Repo Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove staging directories (`001-MOVIES`, …, `099-SCRIPTS`) from git tracking via `git rm --cached`. Replace the 17+ individual `.gitignore` lines with a single wildcard pattern. Physical files remain on disk untouched.

**Architecture:** Git-only operation — no Python changes. Preamble measures blast radius before the rm. Gate asserts physical file count under `099-SCRIPTS/` is unchanged after the commit.

**Tech Stack:** git, bash

---

## Gate (entry)

Phase 3 must be complete:

- [ ] `make lint && make test` green
- [ ] `ensure_staging_tree` wired in `pipeline.py` and `cli.py`
- [ ] `personalscraper run --dry-run` creates staging tree from empty dir

---

## Preamble gate — measure blast radius BEFORE any git rm

Run the following commands and **record the output**. Do not proceed until both counts are captured.

- [ ] Count tracked files under staging trees and `099-SCRIPTS`:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && \
git ls-files 001-MOVIES 002-TVSHOWS 003-EBOOKS 004-AUDIO 005-APPS \
             006-ANDROID 097-TEMP 098-AUTRES 099-SCRIPTS \
  | tee /tmp/tracked-before.txt | wc -l
```

Record the number: **\_** tracked files will be untracked.

- [ ] Count physical files under `099-SCRIPTS` (this must be unchanged after the commit):

```bash
find "/Volumes/IznoServer SSD/A TRIER/099-SCRIPTS" -type f | wc -l
```

Record the number: **\_** physical files in `099-SCRIPTS`.

- [ ] View the tracked-before list to understand what will be removed from git:

```bash
cat /tmp/tracked-before.txt
```

If the blast radius is unexpectedly large (thousands of files), stop and investigate before continuing.

---

## Task 1: `git rm --cached` for all staging and scripts directories

**Files:**

- No Python changes.
- Git index modified.

### Step 1.1 — Run `git rm --cached`

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && \
git rm -r --cached \
  001-MOVIES 002-TVSHOWS 003-EBOOKS 004-AUDIO 005-APPS \
  006-ANDROID 097-TEMP 098-AUTRES 099-SCRIPTS
```

Expected: git prints `rm 'NNN-XXX/.gitkeep'` (and other tracked files) for each entry. No error about missing directories (directories that were never tracked produce a "pathspec did not match" warning — this is acceptable).

### Step 1.2 — Verify staging directories are no longer tracked

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && git ls-files | grep -E "^[0-9]{3}-"
```

Expected: **0 lines** (nothing tracked under the numeric directories).

### Step 1.3 — Verify physical files are still on disk

- [ ] Run:

```bash
find "/Volumes/IznoServer SSD/A TRIER/099-SCRIPTS" -type f | wc -l
```

Expected: **same count as the preamble** (physical files unchanged).

---

## Task 2: Update `.gitignore`

**Files:**

- Modify: `.gitignore`

### Step 2.1 — Identify current staging-related lines in `.gitignore`

- [ ] Run:

```bash
grep -n "0[0-9][0-9]-\|\.gitkeep\|099-SCRIPTS" "/Volumes/IznoServer SSD/A TRIER/.gitignore"
```

Note the line numbers. You will remove:

- All lines matching `0XX-*/*` (8 lines, one per staging dir)
- All lines matching `!0XX-*/.gitkeep` (8 lines, negation exceptions)
- The line `099-SCRIPTS/plex/contents.json` (or similar specific file exclusions)

### Step 2.2 — Replace with single wildcard pattern

- [ ] Remove all the lines identified in Step 2.1 from `.gitignore`.
- [ ] Add the following single line in their place (in the appropriate section of `.gitignore`):

```
[0-9][0-9][0-9]-*/
```

This pattern matches any directory starting with three digits and a hyphen, preventing any `NNN-XXX/` directory from being tracked in the future.

### Step 2.3 — Verify `.gitignore` is correct

- [ ] Run:

```bash
grep "[0-9][0-9][0-9]-" "/Volumes/IznoServer SSD/A TRIER/.gitignore"
```

Expected: only the single line `[0-9][0-9][0-9]-*/` (no old individual lines remaining).

- [ ] Confirm git now ignores the staging dirs:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && git status --short | grep "^?" | grep -E "^[?].*[0-9]{3}-" | head -5
```

If staging directories show up as `??` (untracked), the `.gitignore` pattern is working. If they show up as modified/staged, something is wrong — check the pattern.

---

## Task 3: Optional — remove orphaned `.gitkeep` files from disk

After `git rm --cached`, the `.gitkeep` files remain on disk as untracked orphans. The `.gitignore` pattern will prevent them from reappearing in git status, but they can be cleaned up for hygiene.

- [ ] (Optional) Remove `.gitkeep` files:

```bash
find "/Volumes/IznoServer SSD/A TRIER" -maxdepth 2 -name ".gitkeep" -path "*/[0-9][0-9][0-9]-*/*" -delete
```

This is safe — `.gitkeep` files are empty markers with no content.

---

## Task 4: Run test suite

### Step 4.1 — Run full suite to confirm nothing broken

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && make lint && make test
```

Expected: all PASS. No Python code changed in this phase — failures here indicate a test was importing a `.gitkeep` path or had a filesystem side-effect.

---

## Task 5: Commit

### Step 5.1 — Stage `.gitignore`

- [ ] Run:

```bash
cd "/Volumes/IznoServer SSD/A TRIER" && git add .gitignore
```

- [ ] Check `git status` to confirm only `.gitignore` is staged (plus deletions of tracked `.gitkeep` files):

```bash
git status --short
```

Expected output pattern:

```
D  001-MOVIES/.gitkeep
D  002-TVSHOWS/.gitkeep
...
D  099-SCRIPTS/...
M  .gitignore
```

### Step 5.2 — Commit

- [ ] Run:

```bash
git commit -m "chore(ext-staging): remove staging directories and 099-SCRIPTS from repo"
```

---

## Exit gate

- [ ] `git ls-files | grep -E "^[0-9]{3}-"` → **0 lines**
- [ ] Physical file count under `099-SCRIPTS/`: `find 099-SCRIPTS -type f | wc -l` → **same as preamble count**
- [ ] `make lint && make test` green
- [ ] `.gitignore` contains `[0-9][0-9][0-9]-*/` and no longer contains any `0XX-*/` or `!0XX-*/.gitkeep` lines
