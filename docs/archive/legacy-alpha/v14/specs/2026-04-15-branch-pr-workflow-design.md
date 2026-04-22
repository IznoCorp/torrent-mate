# Branch + PR Workflow for Implementation Skills

**Date:** 2026-04-15
**Scope:** Modify `/implement-version`, `/implement-phase`, and `/archive-version` skills
**Goal:** Each new version gets its own git branch and PR, enabling code review before merge to main

## Decisions

| Decision              | Choice                                                                                   |
| --------------------- | ---------------------------------------------------------------------------------------- |
| Granularity           | One branch per version                                                                   |
| Branch creation       | In `/implement-version`, after archiving, before brainstorming                           |
| Branch naming         | `{type}/{name}` — conventional commits prefix (`feat`, `chore`, `fix`, `docs`, `tests`…) |
| PR creation           | End of last phase in `/implement-phase`                                                  |
| PR title              | `{type}: {description}` — conventional commits format                                    |
| PR = living workspace | Yes — review, fixes, additions allowed after creation                                    |
| PR creation tool      | `/github-curl` skill                                                                     |
| PR merge              | Checked/executed in `/archive-version` (auto or manual, chosen upfront)                  |
| Auto-merge options    | User chooses between merge commit and squash merge                                       |
| Branch cleanup        | Delete local branch only — remote branch preserved                                       |
| Config stored in      | `IMPLEMENTATION.md` (metadata block at top)                                              |

## IMPLEMENTATION.md Metadata

Three new fields added to the metadata block:

```markdown
**Branch:** `{type}/{name}`
**PR merge:** auto | manual
**PR:** _(created after last phase)_
```

These are the single source of truth read by all 3 skills.

## Skill Modifications

### `/implement-version`

New steps inserted **after** `/archive-version` completes and **before** brainstorming:

1. **Ask conventional commit type** — prompt: "Type de commit conventionnel ? (feat, chore, fix, docs, tests…)"
2. **Ask feature name** — prompt: "Nom de la feature pour la branch ?"
   - Slugified: lowercase, hyphens, no spaces (e.g., `library-maintenance`)
3. **Ask merge strategy** — prompt: "La PR sera auto-mergée à l'archivage ou mergée manuellement ? (auto/manual)"
4. **Create branch** — `git checkout -b {type}/{name}`
5. **Inject config into `IMPLEMENTATION.md`** — fill the `Branch` and `PR merge` fields
6. **Commit** — `git add IMPLEMENTATION.md && git commit -m "init: branch {type}/{name}"`
7. **Launch brainstorming** — as today, specs + plans commit on this branch

If `/archive-version` was not needed (first version), steps 1-6 still execute before brainstorming.

### `/implement-phase`

Single addition at the end of the **phase review gate** (step 5):

1. **Detect last phase** — read `IMPLEMENTATION.md`, check all phases are `[x]` or `✅`
2. **If last phase → create PR:**
   - Read `**Branch:**` from `IMPLEMENTATION.md`
   - Push branch: `git push -u origin {type}/{name}`
   - Create PR via `/github-curl`:
     - **Title:** `{type}: {description}` (extracted from design spec first heading or summary)
     - **Body:** auto-generated summary of completed phases + link to design spec
     - **Base:** `main`
   - Add PR URL to `IMPLEMENTATION.md`:
     ```markdown
     **PR:** https://github.com/owner/repo/pull/123
     ```
   - Commit + push this change
3. **If not last phase** — no change to current behavior

Everything else in `/implement-phase` remains unchanged: TDD, coherence checks, commits per task.

### `/archive-version`

New steps inserted **between pre-flight checks and archiving**:

#### 1. Read config from `IMPLEMENTATION.md`

- `**Branch:**` → branch name
- `**PR merge:**` → `auto` or `manual`
- `**PR:**` → PR URL

#### 2. Verify PR exists and is ready

- Via `/github-curl`: fetch PR status
- If PR not found → error: "No PR found. Run the last /implement-phase first."

#### 3. Execute merge strategy

**If `auto`:**

- Ask user: "Merge commit ou squash merge ?"
- Merge PR via `/github-curl` with chosen strategy
- `git checkout main && git pull`

**If `manual`:**

- Check if PR is already merged via `/github-curl`
- If not merged → error: "PR not merged yet. Merge it manually then re-run /archive-version."
- If merged → `git checkout main && git pull`

#### 4. Cleanup

- Delete local branch: `git branch -d {type}/{name}`
- Remote branch is **not** deleted (preserved for history)

#### 5. Continue with existing archiving flow

Pre-flight checks, scan, git mv, new `IMPLEMENTATION.md`, CLAUDE.md update, commit milestone — unchanged.

## Complete Workflow

```
/implement-version
  ├── /archive-version (if previous version exists)
  │     ├── Pre-flight checks (repo clean, tests pass, all phases DONE)
  │     ├── Read Branch + PR merge + PR URL from IMPLEMENTATION.md
  │     ├── Verify PR exists
  │     ├── auto → ask merge|squash → merge PR via /github-curl → checkout main
  │     │   manual → verify PR merged → checkout main
  │     ├── Archive (git mv, new IMPLEMENTATION.md)
  │     ├── git branch -d {type}/{name} (local only)
  │     └── Commit milestone
  ├── Ask conventional commit type + feature name
  ├── Ask merge strategy (auto|manual)
  ├── git checkout -b {type}/{name}
  ├── Inject Branch + PR merge into IMPLEMENTATION.md
  ├── Commit init
  └── /brainstorming → /writing-plans

/implement-phase (×N)
  ├── Coherence check
  ├── TDD + commits per task
  ├── Phase review gate
  └── If last phase:
        ├── git push -u origin {type}/{name}
        ├── /github-curl → create PR ({type}: {description})
        ├── Add PR URL to IMPLEMENTATION.md
        └── Commit + push
```

## Edge Cases

### First version (no previous archive)

`/implement-version` skips the `/archive-version` call. Branch creation and config injection proceed normally.

### PR already exists

If `/implement-phase` detects the last phase but a PR URL is already in `IMPLEMENTATION.md`, skip PR creation (idempotent).

### Archive without PR (legacy versions)

If `IMPLEMENTATION.md` has no `**Branch:**` field, `/archive-version` falls back to current behavior (no PR check, no branch cleanup). This ensures backward compatibility with pre-workflow versions.

### Branch already exists

If `git checkout -b` fails because the branch exists, ask the user: switch to existing branch or pick a new name.

## Acceptance Criteria

This modification is complete when:

1. `/implement-version` creates a branch with conventional commit naming and injects config into `IMPLEMENTATION.md`
2. `/implement-phase` creates a PR via `/github-curl` when the last phase completes
3. `/archive-version` verifies/merges the PR before archiving and cleans up the local branch
4. All 3 skills are backward-compatible with projects that don't use branches
5. The workflow has been tested end-to-end on a real version cycle
