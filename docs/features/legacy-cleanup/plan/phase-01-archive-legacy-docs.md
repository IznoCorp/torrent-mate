# Phase 1 — Archive Legacy Docs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all 16 alpha-era `docs/v*-*/` directories plus `docs/archive/v13/` and `docs/archive/v14/` into a single `docs/archive/legacy-alpha/` root. Remove the legacy `docs/IMPLEMENTATION.md` tracker.

**Architecture:** Pure `git mv` + `git rm` operations. No file content changes. One commit.

**Tech Stack:** git

---

## Gate (entry condition)

This is the first phase — no prior gate. Verify you are on branch `feat/legacy-cleanup`:

```bash
git branch --show-current
# expected: feat/legacy-cleanup
```

---

## Detection Rules (relevant to this phase)

| Pattern       | Meaning                 | Action          |
| ------------- | ----------------------- | --------------- |
| `\bV[0-9]+\b` | alpha version dir names | move to archive |

---

## Task 1: Create the archive root

- [ ] **Step 1: Create `docs/archive/legacy-alpha/` with a placeholder so git tracks it**

```bash
mkdir -p "/Volumes/IznoServer SSD/A TRIER/docs/archive/legacy-alpha"
touch "/Volumes/IznoServer SSD/A TRIER/docs/archive/legacy-alpha/.gitkeep"
git -C "/Volumes/IznoServer SSD/A TRIER" add docs/archive/legacy-alpha/.gitkeep
```

---

## Task 2: Move the 16 alpha version directories

- [ ] **Step 2: git mv each docs/v*-*/ directory**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
for dir in \
  docs/v0-project-setup \
  docs/v1-ingest \
  docs/v2-sort-clean \
  docs/v3-scrape \
  docs/v4-verify \
  docs/v5-dispatch \
  docs/v6-log-notify \
  docs/v7-e2e-tests \
  docs/v7x-test-audit \
  docs/v8-robustness \
  docs/v9-pipeline-integrity \
  docs/v10-pipeline-resilience \
  docs/v11-code-quality \
  docs/v12-pipeline-hardening \
  docs/v13-pipeline-correctness \
  docs/v15-config-driven; do
  [ -d "$dir" ] && git mv "$dir" "docs/archive/legacy-alpha/$(basename $dir)"
done
```

- [ ] **Step 3: Verify all 16 dirs are now under archive**

```bash
ls "/Volumes/IznoServer SSD/A TRIER/docs/archive/legacy-alpha/" | grep -E '^v[0-9]' | wc -l
# expected: 16 (adjust if some dirs didn't exist)
```

---

## Task 3: Move existing archive/v13 and archive/v14

- [ ] **Step 4: git mv docs/archive/v13 and docs/archive/v14**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
[ -d docs/archive/v13 ] && git mv docs/archive/v13 docs/archive/legacy-alpha/v13
[ -d docs/archive/v14 ] && git mv docs/archive/v14 docs/archive/legacy-alpha/v14
```

- [ ] **Step 5: Verify docs/archive/ no longer contains bare v[0-9]\* entries**

```bash
ls "/Volumes/IznoServer SSD/A TRIER/docs/archive/" | grep -E '^v[0-9]'
# expected: no output
```

---

## Task 4: Remove legacy docs/IMPLEMENTATION.md

- [ ] **Step 6: git rm the legacy tracker**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
[ -f docs/IMPLEMENTATION.md ] && git rm docs/IMPLEMENTATION.md
```

---

## Task 5: Gate check and commit

- [ ] **Step 7: Run gate checks**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"

# Check 1: no v[0-9] dirs directly under docs/
ls docs/ | grep -E '^v[0-9]'
# expected: no output

# Check 2: docs/archive/ contains legacy-alpha/ and features/, no bare v[0-9]*
ls docs/archive/
# expected: features/  legacy-alpha/  (and possibly other non-v[0-9] entries)

# Check 3: no docs/IMPLEMENTATION.md
ls docs/IMPLEMENTATION.md 2>/dev/null && echo "FAIL: still present" || echo "OK: removed"
```

- [ ] **Step 8: Commit**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
git add -A docs/archive/legacy-alpha/ docs/archive/v13 docs/archive/v14 2>/dev/null || true
git status --short
git commit -m "chore(legacy-cleanup): archive v0-v15 alpha docs"
```

---

## Exit condition for Phase 2

Phase 2 may start only when:

- `ls docs/ | grep -E '^v[0-9]'` produces no output
- `docs/archive/legacy-alpha/` exists and contains at least the moved directories
- `docs/IMPLEMENTATION.md` does not exist
- The commit `chore(legacy-cleanup): archive v0-v15 alpha docs` is on the branch
