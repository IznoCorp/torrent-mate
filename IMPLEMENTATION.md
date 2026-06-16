# Implementation Progress — hybrid-flow (robustness batch 2: make the HYBRID lifecycle flow)

> For Claude: read this file at session start. Current feature tracker.

**Feature**: hybrid-flow — turn the dead `advance:auto:<col>` config into a live engine backstop,
configure the doc/build transitions for the HYBRID flow (auto through Plan, human gate at Planned,
auto-build to PR, CI gate auto-promotes to Review, Review stops, merge = human), make cross-stage
artifacts durable via a per-ticket WIP branch, harden the implement-stage prompts, and give the docs
profile the minimal shell its doc stages need.
**Version bump**: minor (Y+1) — 0.1.1 → 0.2.0
**Branch**: `feat/hybrid-flow`
**PR merge**: manual (human-only)
**PR**: _(created after the gate)_
**Design**: `docs/features/hybrid-flow/DESIGN.md`
**Master plan**: _(single feature branch — sub-phases below)_

## Phases

| Phase | Scope | Status | Commit |
|-------|-------|--------|--------|
| 1 | Pure edits: HYBRID transition table advance directives (C2) + docs profile minimal shell (C5) + implement/fix-CI prompt guards (C4) + design/plan COMMIT + repo-relative markers (C3 prompt wording) in `core/transitions_defaults.py` and `adapters/perms.py`; tests | DONE | `feat(hybrid-flow): HYBRID advance directives + docs shell + implement-stage prompt guards` |
| 2 | Engine backstop (C1): new `bin/_clone_config.py` (lifted loaders + `auto_advance_target`); `bin/kanban_session_end._auto_advance` branch 4c (clean-done, idempotent, fail-soft, records the move, rate-limit park); `kanban_move` re-imports for back-compat; tests | DONE | `feat(hybrid-flow): engine honors advance:auto on launch stages (session-end backstop)` |
| 3 | Durable cross-stage carry (C3): `adapters/workspace/worktree.ensure_worktree` per-ticket WIP branch `kanban/ticket-<n>` (+ `wip_branch` helper); `discover_branch` docstring; worktree unit + shared-`.git` integration tests | DONE | `feat(hybrid-flow): per-ticket WIP branch for durable cross-stage artifact carry` |
| 4 | Docs + tracker delta: `docs/features/hybrid-flow/DESIGN.md`, this IMPLEMENTATION.md, VERSION + pyproject bump to 0.2.0 | DONE | `docs(hybrid-flow): DESIGN + IMPLEMENTATION + version bump 0.2.0` |

## Behaviour deltas (gate requirement)

- **Engine honours `advance:auto:<col>` on launch stages.** Previously dead config: a launch stage's
  persisted `advance:auto:<col>` was never consumed. Now `bin/kanban_session_end` moves the card to
  `<col>` on a CLEAN done (`kanban-done` breadcrumb present) when the agent did NOT advance its own
  card — idempotent, fail-soft, recorded via `record_move_for_item` (so the daemon diff fires the next
  stage), and rate-limited (park in Blocked at/over `move_rate_limit_per_hour`). `advance:stop` → no
  move (the human gates). Mirrors `app/script_route._route_success`.
- **HYBRID transition table.** Backlog→Brainstorming `auto:Spec`, Brainstorming→Spec `auto:Plan`,
  Spec→Plan `auto:Planned`, ReadyToDev→PrepareFeature `auto:InProgress`, PrepareFeature→InProgress
  `auto:PRCI` (unchanged), InProgress→PRCI SCRIPT `auto:Review` (green CI fires pr-review). Plan→Planned
  and Planned→ReadyToDev stay no-ops (the single human review gate); PRCI→Review and Review→Merge stay
  `stop` (Review stops, merge = human-only).
- **Durable cross-stage carry.** Worktrees are now checked out on a per-ticket WIP branch
  `kanban/ticket-<n>` (created off `origin/<base>` first, reused thereafter) instead of detached HEAD.
  The design/plan stages COMMIT their `docs/features/<codename>/` artifacts to it, and — because
  worktrees share one `.git` — the next stage's worktree sees them on checkout (no push). Markers are
  now repo-relative paths the next worktree can `cat`. `discover_branch` honestly reports the named
  branch (the InProgress→PRCI gate's `KANBAN_BRANCH` is populated earlier).
- **Implement-stage prompt guards.** `_IMPLEMENT_PROMPT` carries STOP-AT-PR-CREATION + a never-`gh pr
  merge` ban + a CI-not-green terminal branch (move PR/CI anyway, do not idle). `_FIXCI_PROMPT` gained
  the same never-merge + do-not-idle-on-CI discipline.
- **docs profile shell.** The `docs` profile allow-list gained `Bash(mkdir*)`/`Bash(ls*)`/`Bash(cat*)`
  — the minimum the doc stages need — without a broad `Bash` (no push, no gh-write).

## Deferred

- **create-branch SKILL.md reconciliation** (DESIGN §6): the `implement:create-branch` SKILL.md edit
  (Step 3 branch-off-WIP, Step 4 idempotent `mv`, the error-row carry exception) is a portable-config
  change in the SEPARATE, gitignored `.claude/` repo shared by the live daemons — documented in DESIGN
  §6 for the operator / the create-branch stage to apply, NOT mutated from this isolated worktree.
