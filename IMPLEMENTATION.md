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
**Master plan**: docs/features/config-home/plan/INDEX.md

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

| #   | Phase                                                                                                            | File                             | Status |
| --- | ---------------------------------------------------------------------------------------------------------------- | -------------------------------- | ------ |
| 1   | Sync engine — additive JSON5 deep-merge + `init-config --sync` CLI + golden tests                                | phase-01-sync-engine.md          | [x]    |
| 2   | Config git mini-repo — `config_git.py` helper + S4 auto-commit hook + unit tests                                 | phase-02-config-git.md           | [x]    |
| 3   | Verify + ecosystem tests — `config_home` check + ecosystem test pins + worktree-invariant + integration tests    | phase-03-verify-and-tests.md     | [x]    |
| 4   | Migration + config changes — `migrate-config-home.sh` + `ecosystem.config.js` + `deploy.sh` + git untrack + docs | phase-04-migration-and-config.md | [x]    |
| 5   | ACCEPTANCE + final gate — ACCEPTANCE.md (ACC-01..06) + `make check`                                              | phase-05-acceptance-and-gate.md  | [x]    |

## Review cycles

_(filled by implement:pr-review — operator contract: multiple adversarial review passes)_

## Next action

All phases complete — run /implement:feature-pr (push + PR + CI + adversarial reviews +
auto-merge per operator contract). Then: run scripts/migrate-config-home.sh (the live
migration), re-exercise ACC-01..06, and exercise the deferred manual gates (« web-UI save →
config_edit commit »). Recorded anomaly: sub-phase 4.2 dispatch omitted the MODEL_IDENTITY
probe (report-contract miss); work independently verified by orchestrator gates — accepted.
Expected-red window CLOSED at phase 4 (ecosystem tests 40/40 green).
