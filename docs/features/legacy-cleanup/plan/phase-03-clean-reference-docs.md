# Phase 3 — Clean Reference Docs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 8 `docs/reference/*.md` files intemporal — no VX version tags anywhere. Sharp removal where the sentence survives; reformulation where meaning would be lost.

**Architecture:** File edits only. One commit at the end of the phase.

**Tech Stack:** git, text editor / sed

---

## Gate (entry condition)

Phase 2 must be complete. Verify:

```bash
cd "/Volumes/IznoServer SSD/A TRIER"

# Gate 1: no VX refs in root .md files
grep -rn "\bV[0-9]\+\b" *.md 2>/dev/null | \
  grep -v "Python 3\|TMDB\|TVDB\|VERSION\|0\.[0-9]"
# expected: no output

# Gate 2: MIGRATION.md gone
ls MIGRATION.md 2>/dev/null && echo "FAIL" || echo "OK"

# Gate 3: commit exists
git log --oneline | grep "rewrite root docs without VX refs"
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

### Reformulation examples

| Before                                                     | After                                         |
| ---------------------------------------------------------- | --------------------------------------------- |
| `Full pipeline (V9+V10+V13) executes 8 steps sequentially` | `Full pipeline executes 8 steps sequentially` |
| `V1: qBittorrent → staging`                                | `Ingest module: qBittorrent → staging`        |
| `V8 circuit breaker`                                       | `circuit breaker`                             |
| `V0-V14 implemented — see architecture.md`                 | remove the parenthetical                      |
| `Based on the V12 spec`                                    | remove the attribution                        |

---

## Task 1: Scan all 8 reference files

- [ ] **Step 1: Run discovery grep**

```bash
grep -n "\bV[0-9]\+\b\|V[0-9]\++V[0-9]\+\|V[0-9]\+\.x" \
  "/Volumes/IznoServer SSD/A TRIER/docs/reference/architecture.md" \
  "/Volumes/IznoServer SSD/A TRIER/docs/reference/commands.md" \
  "/Volumes/IznoServer SSD/A TRIER/docs/reference/storage.md" \
  "/Volumes/IznoServer SSD/A TRIER/docs/reference/naming.md" \
  "/Volumes/IznoServer SSD/A TRIER/docs/reference/testing.md" \
  "/Volumes/IznoServer SSD/A TRIER/docs/reference/scraping.md" \
  "/Volumes/IznoServer SSD/A TRIER/docs/reference/libraries.md" \
  "/Volumes/IznoServer SSD/A TRIER/docs/reference/pipeline-internals.md"
```

Review the output. For each match apply the decision rule:

```
For each grep match:
├─ Is it a project version ref (V0-V15)?
│  ├─ YES → remove it
│  │        └─ Does the sentence still make sense?
│  │           ├─ YES → sharp removal
│  │           └─ NO  → reformulate intemporally, preserving the "why"
│  └─ NO (external API, Python, runtime file) → leave as-is
```

---

## Task 2: Edit architecture.md

- [ ] **Step 2: Open `docs/reference/architecture.md` and apply all fixes**

High-likelihood targets:

- "V0-V14 implemented" header or sentence → remove
- "V0-V15 version history" references → remove or replace with "see git log"
- "V9+V10+V13 pipeline" compositions → rewrite as plain description
- Module map entries using VX labels → remove the VX label, keep the module description

- [ ] **Step 3: Verify architecture.md clean**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/architecture.md"
# expected: no output
```

---

## Task 3: Edit commands.md

- [ ] **Step 4: Open `docs/reference/commands.md` and apply all fixes**

- [ ] **Step 5: Verify commands.md clean**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/commands.md"
# expected: no output
```

---

## Task 4: Edit storage.md

- [ ] **Step 6: Open `docs/reference/storage.md` and apply all fixes**

- [ ] **Step 7: Verify storage.md clean**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/storage.md"
# expected: no output
```

---

## Task 5: Edit naming.md

- [ ] **Step 8: Open `docs/reference/naming.md` and apply all fixes**

- [ ] **Step 9: Verify naming.md clean**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/naming.md"
# expected: no output
```

---

## Task 6: Edit testing.md

- [ ] **Step 10: Open `docs/reference/testing.md` and apply all fixes**

- [ ] **Step 11: Verify testing.md clean**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/testing.md"
# expected: no output
```

---

## Task 7: Edit scraping.md

- [ ] **Step 12: Open `docs/reference/scraping.md` and apply all fixes**

- [ ] **Step 13: Verify scraping.md clean**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/scraping.md"
# expected: no output
```

---

## Task 8: Edit libraries.md

- [ ] **Step 14: Open `docs/reference/libraries.md` and apply all fixes**

- [ ] **Step 15: Verify libraries.md clean**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/libraries.md"
# expected: no output
```

---

## Task 9: Edit pipeline-internals.md

- [ ] **Step 16: Open `docs/reference/pipeline-internals.md` and apply all fixes**

Common targets:

- "V8 circuit breaker" → "circuit breaker"
- "V9 sequential pipeline" → "sequential pipeline"
- "V10 resilience" → remove label

- [ ] **Step 17: Verify pipeline-internals.md clean**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/pipeline-internals.md"
# expected: no output
```

---

## Task 10: Gate check and commit

- [ ] **Step 18: Full gate check across all 8 files**

```bash
grep -n "\bV[0-9]\+\b" "/Volumes/IznoServer SSD/A TRIER/docs/reference/"*.md | \
  grep -v "Python 3\|TMDB\|TVDB\|VERSION"
# expected: no output
```

- [ ] **Step 19: Visual pass — check for orphan fragments**

Open each file and scan for:

- Sentences that start with "ex. after removing version" (artifact of deletion)
- Dangling parentheticals like "(based on the spec)"
- Empty section headers
- "the VX approach" / "since VX" fragments left after removal

Fix any orphan fragments found.

- [ ] **Step 20: Commit**

```bash
cd "/Volumes/IznoServer SSD/A TRIER"
git add docs/reference/architecture.md \
        docs/reference/commands.md \
        docs/reference/storage.md \
        docs/reference/naming.md \
        docs/reference/testing.md \
        docs/reference/scraping.md \
        docs/reference/libraries.md \
        docs/reference/pipeline-internals.md
git status --short
git commit -m "chore(legacy-cleanup): clean reference docs of VX refs"
```

---

## Exit condition for Phase 4

Phase 4 may start only when:

- `grep -n "V[0-9]\b" docs/reference/*.md` returns no project-version matches
- All 8 files pass the visual orphan-fragment check
- The commit `chore(legacy-cleanup): clean reference docs of VX refs` is on the branch
