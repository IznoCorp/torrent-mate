# Phase 8: pipeline-monitor skill (bug #14)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Fix the pipeline-monitor skill to STOP on critical errors instead of continuing.

**Architecture:** Update SKILL.md error detection list, gate checks, and add INGEST abort rule.

**Tech Stack:** Markdown (skill file, no Python code)

---

## Task 1: Expand critical error detection

**Files:**

- Modify: `.claude/skills/pipeline-monitor/SKILL.md`

- [ ] **Step 1: Update section "2.3 Display output and analyze"**

Find the current critical error list (around line 186-189):

```markdown
3. Check for critical errors:
   - 2+ identical errors → SYSTEMIC → go to STOP PROTOCOL
   - "Operation not permitted" → PERMISSIONS → go to STOP PROTOCOL
   - "Forbidden403Error" → IP BAN → go to STOP PROTOCOL
   - "No space left" → DISK FULL → go to STOP PROTOCOL
```

Replace with:

```markdown
3. Check for critical errors:
   - 2+ identical errors → SYSTEMIC → go to STOP PROTOCOL
   - "Operation not permitted" → PERMISSIONS → go to STOP PROTOCOL
   - "Forbidden403Error" → IP BAN → go to STOP PROTOCOL
   - "No space left" → DISK FULL → go to STOP PROTOCOL
   - "QBitAuthLockoutError" or "auth lockout active" → AUTH LOCKOUT → go to STOP PROTOCOL
   - "rsync failed" + "Invalid argument" → NTFS ILLEGAL CHARS → go to STOP PROTOCOL (systemic: all items with `:` will fail)
   - INGEST error_count > 0 AND 097-TEMP is empty → INGEST FAILED → go to STOP PROTOCOL (nothing new to process)
   - INGEST error_count > 0 AND 097-TEMP has items → WARNING only, continue (prior run items still need processing)
```

- [ ] **Step 2: Commit**

```bash
git add ".claude/skills/pipeline-monitor/SKILL.md"
git commit -m "v12.8.1: Expand pipeline-monitor critical error detection"
```

## Task 2: Strengthen gate checks

**Files:**

- Modify: `.claude/skills/pipeline-monitor/SKILL.md`

- [ ] **Step 1: Update section "2.6 Gate checklist"**

Find the current gate checklist (around line 220-228):

```markdown
- [ ] Command terminated
- [ ] Output displayed and analyzed
- [ ] 3 technical agents launched AND results received
- [ ] Business agent launched AND result received (if applicable)
- [ ] Reports aggregated in BUG LIST
- [ ] Markdown updated (step section filled with results)
- [ ] Tasks updated
- [ ] No critical error detected
```

Replace with:

```markdown
- [ ] Command terminated
- [ ] Output displayed and analyzed
- [ ] 3 technical agents launched AND results received
- [ ] Business agent launched AND result received (if applicable)
- [ ] Reports aggregated in BUG LIST
- [ ] Markdown updated (step section filled with results)
- [ ] Tasks updated
- [ ] No critical error detected
- [ ] For INGEST: error_count == 0 OR 097-TEMP has items from prior run
- [ ] For DISPATCH: no rsync failures with "Invalid argument" (NTFS-illegal chars)
```

- [ ] **Step 2: Commit**

```bash
git add ".claude/skills/pipeline-monitor/SKILL.md"
git commit -m "v12.8.2: Strengthen pipeline-monitor gate checks for INGEST and DISPATCH"
```

## Task 3: Add INGEST abort rule documentation

**Files:**

- Modify: `.claude/skills/pipeline-monitor/SKILL.md`

- [ ] **Step 1: Add rationale section after 2.3**

After the critical error list, add a new subsection:

````markdown
### 2.3.1 INGEST abort rule

INGEST is the pipeline entry point. If it fails:

- **No new media enters the pipeline** — sort/process/verify/dispatch run on stale data only
- **The root cause must be fixed first** — qBit credentials, IP ban, disk space, etc.

**Decision logic:**

- `error_count > 0` AND `097-TEMP` is empty → **STOP PROTOCOL** (nothing to process)
- `error_count > 0` AND `097-TEMP` has items → **WARNING, continue** (items from prior interrupted run still need processing)
- `error_count == 0` → **PASS** (normal flow)

To check 097-TEMP:

```bash
ls "/Volumes/IznoServer SSD/A TRIER/097-TEMP/" 2>/dev/null | grep -v "^$" | wc -l
```
````

If count > 0 (excluding .DS_Store, .gitkeep) → items exist → continue with WARNING.

````

- [ ] **Step 2: Commit**

```bash
git add ".claude/skills/pipeline-monitor/SKILL.md"
git commit -m "v12.8.3: Add INGEST abort rule with 097-TEMP check"
````

## Task 4: Update IMPLEMENTATION.md

- [ ] **Step 1: Mark Phase 8 complete**
- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.8.4: Update IMPLEMENTATION.md — Phase 8 complete"
```
