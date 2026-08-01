# Implementation Progress — config-home

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Config Home — relocate the canonical config out of every git working tree
(ticket #326 Config-Shared): canonical moves to `~/.torrentmate/config` (local mini git repo),
`init-config --sync` additive migration, ecosystem/deploy/test pins updated, worktree-invariant
guard test + `config_home` verify check.
**Type**: feat
**Version bump**: 0.72.2 → 0.73.0 (minor)
**Branch**: feat/config-home
**Ticket**: #326 — claimed (kanban-work, card in Brainstorming → advance as phases progress)
**PR merge**: auto — operator contract: MULTIPLE adversarial reviews + solid tests REQUIRED
before the auto-merge fires; merge only on clean adversarial review + green CI.
**PR**: _(created after last phase)_
**Design**: docs/features/config-home/DESIGN.md
**Master plan**: _(to be defined after /implement:plan)_

## Non-negotiable invariants

- The canonical config dir must NEVER live inside a git working tree (the #320/#322 risk
  class) — enforced by the new ecosystem test invariant + the `config_home` verify check.
- `extra="forbid"` strict loading STAYS (deliberate quality choice — rejected tolerance).
- Single shared canonical config (prod + staging + crons + dev + web-UI S4) — only the
  LOCATION changes (operator decision D2).
- `init-config --sync` is ADDITIVE ONLY: never modifies or removes an existing key/value.
- Mini-repo commits are fail-soft: a git failure never blocks a config save.
- No VERSION file in this repo — version lives in `personalscraper/__init__.py`
  (pyproject dynamic attr); do not recreate VERSION.

## Phases

_(filled by /implement:plan)_

## Review cycles

_(filled by implement:pr-review — operator contract: multiple adversarial review passes)_

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.
