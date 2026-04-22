# Phase 5 — Final Validation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Confirm the entire codebase is clean of VX references. Refresh any stale test counts. One final commit.

**Architecture:** Read-only verification pass, then optional cosmetic updates, then commit.

**Tech Stack:** grep, make, git

---

## Gate (entry condition)

Phase 4 must be complete. Verify:

```bash
cd "/Volumes/IznoServer SSD/A TRIER"

# Gate 1: no VX refs in Python source
grep -rn "\bV[0-9]\+\b" personalscraper/ --include="*.py" | \
  grep -v "Python 3\|TMDB\|TVDB\|VERSION\|\.v14\.bak"
# expected: no output

# Gate 2: test suite green
make test && make lint

# Gate 3: all 10 module commits present
git log --oneline | grep "strip VX refs" | wc -l
# expected: 10
```

---

## Detection Rules (global reference — final sweep)

| Pattern                      | Meaning                     | Action                           |
| ---------------------------- | --------------------------- | -------------------------------- |
| `\bV[0-9]+\b`                | "V3", "V12", "V14" isolated | must be zero                     |
| `\bv[0-9]+\b`                | "v3", "v12" lowercase       | review any remaining             |
| `V[0-9]+\.x`                 | "V7.x"                      | must be zero                     |
| `V[0-9]+\+V[0-9]+`           | "V9+V10+V13" composition    | must be zero                     |
| `\.v14\.bak`                 | runtime backup filename     | **KEEP** — must still be present |
| `Python 3\.10\+`             | Python version              | **KEEP**                         |
| `TMDB v3 API`, `TVDB v4 API` | external API version        | **KEEP**                         |
| CI badges, `VERSION=0.x.y`   | semver reference            | **KEEP**                         |

---

## Task 1: Full global sweep

- [ ] **Step 1: Run the canonical full-sweep grep**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
grep -rn "\bV[0-9]\+\b" \
  --include="*.md" --include="*.py" \
  --exclude-dir=archive --exclude-dir=.venv \
  --exclude-dir=".git"
```

Expected result: zero matches, or only KEEP-class matches (Python version, external APIs, semver badges).

- [ ] **Step 2: Triage any remaining matches**

For each match output from Step 1:

- Is it a project alpha version ref? → fix immediately (edit the file, re-run Step 1)
- Is it a KEEP-class ref (Python 3.x, TMDB v3, TVDB v4, VERSION=0.x.y)? → no action needed

- [ ] **Step 3: Verify the runtime contract is still intact**

```bash
grep "v14\.bak" "/Volumes/IznoServer SSD/A TRIER/personalscraper/conf/migration.py"
# expected: at least one line (runtime contract must not have been removed)
```

---

## Task 2: Full test and lint run

- [ ] **Step 4: Run the full quality gate**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
make test && make lint
```

Expected: all tests pass, lint clean. If any test fails, investigate immediately — a comment sweep must never break logic. The most likely cause is a grep that caught a live user-facing string in a comment that was also used as a log message; fix by restoring only the affected line.

---

## Task 3: Refresh stale test counts (optional but recommended)

- [ ] **Step 5: Check current test count**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
pytest --collect-only -q 2>/dev/null | tail -1
# example output: "1092 tests collected in 3.45s"
```

- [ ] **Step 6: Update README.md and CLAUDE.md if the count shown differs from the collected count**

Open `README.md` and `CLAUDE.md`. Search for a test count badge or sentence (e.g. "1092 tests"). If the number is stale, update it to match the collected count.

If neither file references a test count, skip this step.

---

## Task 4: Final commit

- [ ] **Step 7: Stage any files changed in Tasks 1-3 and commit**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
git status --short
# Stage only files that were actually changed (do not use git add -A blindly)
# Example if README.md and/or CLAUDE.md were updated:
# git add README.md CLAUDE.md
git commit -m "chore(legacy-cleanup): final sweep and validation"
```

**Always emit this commit**, even if Tasks 1-3 made no file changes, using `--allow-empty` if needed:

```bash
git commit --allow-empty -m "chore(legacy-cleanup): final sweep and validation"
```

Rationale: the INDEX commit table advertises this commit as _the_ Phase 5 milestone. Skipping it would leave downstream checks (`/implement:feature-pr` commit counting) expecting 14 commits but finding 13.

---

## Task 5: Success criteria check

- [ ] **Step 8: Verify all 5 success criteria from the DESIGN**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"

# Criterion 1: zero significant VX matches
# Capture output so a FAIL case shows which matches remain.
CRIT1_OUT=$(grep -rn "\bV[0-9]\+\b" --include="*.md" --include="*.py" \
  --exclude-dir=archive --exclude-dir=.venv --exclude-dir=.git | \
  grep -v "Python 3\|TMDB\|TVDB\|VERSION\|0\.[0-9]")
if [ -z "$CRIT1_OUT" ]; then
  echo "Criterion 1: PASS"
else
  echo "Criterion 1: FAIL"
  echo "Remaining matches:"
  echo "$CRIT1_OUT"
fi

# Criterion 2: lint + test green
make lint && make test && echo "Criterion 2: PASS" || echo "Criterion 2: FAIL"

# Criterion 3: no v[0-9]* directories under docs/
ls docs/ | grep -E '^v[0-9]' && echo "Criterion 3: FAIL" || echo "Criterion 3: PASS"

# Criterion 4: CLAUDE.md reads as current 0.x project (manual check)
echo "Criterion 4: manual — open CLAUDE.md and confirm no alpha history visible"

# Criterion 5: all 5 phases committed on feat/legacy-cleanup
git log --oneline feat/legacy-cleanup | grep -E \
  "archive v0-v15|rewrite root docs|clean reference docs|strip VX refs|final sweep"
echo "Criterion 5: count above should be >= 14 commits (1+1+1+10+1)"
```

---

## Exit condition — feature complete

Phase 5 is done when:

- `grep -rn "\bV[0-9]+\b" --include="*.md" --include="*.py" --exclude-dir=archive --exclude-dir=.venv` returns zero project-version matches
- `make test && make lint` is green
- `ls docs/` contains no `v[0-9]*` directory
- `CLAUDE.md` describes the 0.x project without alpha history
- The commit `chore(legacy-cleanup): final sweep and validation` is on `feat/legacy-cleanup`
- Branch is ready for PR + squash merge (invoke `/implement:feature-pr`)
