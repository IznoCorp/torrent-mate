# Phase 2 — Rewrite Root Docs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip all VX references from user-facing documentation at the project root. Remove MIGRATION.md. Rewrite ROADMAP.md to future-only. Clean CLAUDE.md, CONFIGURATION.md, MANUAL.md, INSTALLATION.md.

**Architecture:** File edits only (no git mv). One commit at the end of the phase.

**Tech Stack:** git, text editor / sed

---

## Gate (entry condition)

Phase 1 must be complete before starting this phase. Verify:

```bash
cd "/Volumes/IznoServer SSD/A TRIER"

# Gate 1: no v[0-9] dirs under docs/
ls docs/ | grep -E '^v[0-9]'
# expected: no output

# Gate 2: docs/archive/legacy-alpha/ exists
ls docs/archive/legacy-alpha/ | wc -l
# expected: >= 16

# Gate 3: docs/IMPLEMENTATION.md gone
ls docs/IMPLEMENTATION.md 2>/dev/null && echo "FAIL" || echo "OK"

# Gate 4: commit exists
git log --oneline | grep "archive v0-v15 alpha docs"
# expected: one matching line
```

---

## Detection Rules (relevant to this phase)

| Pattern                      | Meaning                     | Action                         |
| ---------------------------- | --------------------------- | ------------------------------ |
| `\bV[0-9]+\b`                | "V3", "V12", "V14" isolated | remove                         |
| `\bv[0-9]+\b`                | "v3", "v12" lowercase       | remove (context check)         |
| `V[0-9]+\.x`                 | "V7.x"                      | remove                         |
| `V[0-9]+\+V[0-9]+`           | "V9+V10+V13" composition    | reformulate                    |
| `V15 \(config-driven\)`      | explicit feature title      | remove label, keep description |
| `Python 3\.10\+`             | Python version              | **KEEP**                       |
| `TMDB v3 API`, `TVDB v4 API` | external API version        | **KEEP**                       |
| CI badges, `VERSION=0.x.y`   | semver reference            | **KEEP**                       |

---

## Task 1: Remove MIGRATION.md

- [ ] **Step 1: git rm MIGRATION.md**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
[ -f MIGRATION.md ] && git rm MIGRATION.md
```

- [ ] **Step 2: Verify removal**

```bash
ls "/Volumes/IznoServer SSD/A TRIER/MIGRATION.md" 2>/dev/null && echo "FAIL: still present" || echo "OK: removed"
```

---

## Task 2: Scan root markdown files for VX refs

- [ ] **Step 3: Run discovery grep on all root .md files**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
grep -n "\bV[0-9]\+\b\|v[0-9]\+\b\|V[0-9]\+\.x\|V[0-9]\++V[0-9]\+" \
  ROADMAP.md CLAUDE.md CONFIGURATION.md MANUAL.md INSTALLATION.md 2>/dev/null
```

Review each match. For each:

- Is it a project alpha version ref (V0-V15)? → remove or reformulate
- Is it Python version, external API, semver badge? → **KEEP**

---

## Task 3: Rewrite ROADMAP.md

- [ ] **Step 4: Open ROADMAP.md and remove the "Implemented V0-V14" history table**

The file must retain only future-oriented sections. The "Implemented" / "Done" table (listing V0-V14 phases) must be deleted entirely.

Keep sections such as:

- Auto-Download (tracker APIs)
- Watcher / hot-folder
- YoutubeTrailerScraper integration
- Config System Overhaul
- Decouple Staging
- Library Indexer

If a section header references a VX (e.g. "V15 Config System"), rewrite it as the plain feature name (e.g. "Config System").

- [ ] **Step 5: Verify ROADMAP.md — no VX refs remain**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/ROADMAP.md"
# expected: no output
```

---

## Task 4: Clean CLAUDE.md

- [ ] **Step 6: Open CLAUDE.md and apply these targeted removals/rewrites**

Patterns to remove or reformulate:

- Line/paragraph containing "V0-V15 implemented" → remove
- Sentence "V15 (config-driven): All storage paths…" → rewrite as "All storage paths and category names are now in `config.json5`." (drop the V15 label)
- "Config-driven key points (v15 baseline)" section header → rewrite as "Config-driven key points"
- Any sentence mentioning "V14 → V15 migration" → remove the migration mention; if context is lost, reformulate
- "Run `personalscraper init-config --from-current` to migrate from V14." → "Run `personalscraper init-config --from-current` to create `config.json5` from your current setup."
- "See `MIGRATION.md`." → remove (file deleted)

- [ ] **Step 7: Verify CLAUDE.md — no VX refs remain**

```bash
grep -n "\bV[0-9]\+\b\|v[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/CLAUDE.md" | \
  grep -v "Python 3\|TMDB\|TVDB\|VERSION\|0\.x\|0\.2\|0\.3"
# expected: no output (Python/API/semver refs are acceptable)
```

---

## Task 5: Clean CONFIGURATION.md, MANUAL.md, INSTALLATION.md

- [ ] **Step 8: Scan each file and apply the decision rule**

For each match from Step 3:

```
For each grep match:
├─ Is it a project version ref (V0-V15)?
│  ├─ YES → remove it
│  │        └─ Does the sentence still make sense?
│  │           ├─ YES → sharp removal
│  │           └─ NO  → reformulate, preserving the "why"
│  └─ NO (external API, Python, runtime file) → leave as-is
```

Common patterns to rewrite:

- "V14 format" → "legacy format"
- "V15 config system" → "config system"
- "migrated from V14" → "migrated from the legacy .env format"
- "requires V14 .env" → remove or reformulate

- [ ] **Step 9: Verify all three files — no VX refs remain**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
grep -n "\bV[0-9]\+\b" CONFIGURATION.md MANUAL.md INSTALLATION.md 2>/dev/null | \
  grep -v "Python 3\|TMDB\|TVDB\|VERSION"
# expected: no output
```

---

## Task 6: Gate check and commit

- [ ] **Step 10: Full gate check**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"

# Check 1: no VX refs in root .md files (ignoring Python/API/semver)
grep -rn "\bV[0-9]\+\b" *.md 2>/dev/null | \
  grep -v "Python 3\|TMDB\|TVDB\|VERSION\|0\.[0-9]"
# expected: no output

# Check 2: MIGRATION.md gone
ls MIGRATION.md 2>/dev/null && echo "FAIL" || echo "OK"

# Check 3: ROADMAP.md contains no history table
grep -c "Implemented\|V0\|V1[0-5]" ROADMAP.md
# expected: 0
```

- [ ] **Step 11: Commit**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
git add ROADMAP.md CLAUDE.md CONFIGURATION.md MANUAL.md INSTALLATION.md
git status --short
git commit -m "chore(legacy-cleanup): rewrite root docs without VX refs"
```

---

## Exit condition for Phase 3

Phase 3 may start only when:

- `grep -rn "\bV[0-9]+\b" *.md` returns no project-version matches
- `MIGRATION.md` does not exist
- `ROADMAP.md` contains only future ideas (no implemented history table)
- `CLAUDE.md` describes the current 0.x project without alpha history mentions
- The commit `chore(legacy-cleanup): rewrite root docs without VX refs` is on the branch
