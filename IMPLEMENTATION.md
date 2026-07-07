# Implementation Progress — maint-dash

> For Claude: read this file at session start. Current feature tracker.

**Feature**: S3 — Maintenance dashboard (web UI): monitoring panels + library-* actions
**Type**: feat
**Version bump**: 0.41.0 → 0.42.0 (minor)
**Branch**: feat/maint-dash
**PR merge**: auto
**PR**: https://github.com/IznoCorp/torrent-mate/pull/228
**Design**: docs/features/maint-dash/DESIGN.md
**Master plan**: docs/features/maint-dash/plan/INDEX.md

## Phases

| #   | Phase                      | File                               | Status |
| --- | -------------------------- | ---------------------------------- | ------ |
| 1   | DB + Registry              | phase-01-db-registry.md            | [x]    |
| 2   | Panels Backend             | phase-02-panels-backend.md         | [x]    |
| 3   | Actions Backend            | phase-03-actions-backend.md        | [x]    |
| 4   | History Unification        | phase-04-history-unification.md    | [x]    |
| 5   | Frontend                   | phase-05-frontend.md               | [x]    |
| 6   | Deploy + Docs + ACCEPTANCE | phase-06-deploy-docs-acceptance.md | [x]    |

## Review cycles

### Cycle 1

4 adversarial reviewers on PR #228 (backend routes+runner, silent-failure hunt, security
option→argv/dry-run/auth, frontend dry-run gate). Security: no blocking findings (argv is a
list + shell=False, SQL fully parameterized, dry-run gate fail-closed, auth double-guarded —
all verified, incl. empirical click 8.3.3 parsing). Retained + confirmed against code:

- **CRITICAL** — runner had no try/finally around insert→finalize: a UnicodeDecodeError on a
  non-UTF-8/NFD media filename (this library has them), a mid-stream exception, or SIGTERM
  left the `pipeline_run` row stuck `running` forever + orphaned a live destructive child.
- **MAJOR** — `library-validate` apply always exited 1 (`--apply requires --fix`, `fix` not
  exposed): a destructive catalog action that could never apply.
- **MEDIUM** ×5 — invisible `run_uid` + concurrency TOCTOU (row inserted late by the runner);
  index-health masked a broken/mis-migrated DB as a pristine empty library; concurrency guard
  failed open at debug on a DB read error; history-detail masked operational errors as 404;
  frontend destructive Apply unlocked on the 202 spawn (not a successful dry-run) and never
  re-locked on a failed dry-run (DESIGN §5 contract violation; backend 428 kept it safe).
- Folded MINOR: `--` positional separator in the runner argv (flag-injection hardening),
  models.py scan_run docstring drift.
- Follow-up (not this PR, cross-cutting S2+S3): panel/guard reads open read-write + run the
  WAL pragma — consistent with the S2 history route; a mode=ro change should touch both.

Fix: two Opus dispatches (backend robustness/guards cluster; frontend dry-run gate), each
with reproducing regression tests.

## Next action

All phases complete — run /implement:feature-pr (push + PR + CI). ACC-01..09 to be exercised on staging pre-merge (6.1 operational).
