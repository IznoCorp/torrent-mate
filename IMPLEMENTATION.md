# Implementation Progress — bosun

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Fully installable & controllable via KanbanMateUI — daemon control, health, redeploy, project onboarding (minor)
**Version bump**: 0.15.0 → 0.16.0
**Branch**: feat/bosun
**PR merge**: manual
**PR**: https://github.com/IznoCorp/kanban-mate/pull/73
**Design**: docs/features/bosun/DESIGN.md
**Master plan**: docs/features/bosun/plan/INDEX.md

## Phases

| #   | Phase                             | File                           | Status |
| --- | --------------------------------- | ------------------------------ | ------ |
| 1   | Jobs primitive + health dashboard | phase-01-jobs-and-health.md    | [x]    |
| 2   | Daemon control + CSRF + PAUSE     | phase-02-control-csrf-pause.md | [x]    |
| 3   | Redeploy from main                | phase-03-redeploy.md           | [x]    |
| 4   | Project onboarding                | phase-04-onboarding.md         | [x]    |
| 5   | First-run wizard + ACCEPTANCE     | phase-05-wizard-acceptance.md  | [x]    |

## Review cycles

### Cycle 1 — 2026-06-22 (PR #73, CI green at entry)

Multi-lens Opus review (security/correctness of the HTTP + jobs surface · test coverage vs
ACCEPTANCE · conventions/layering) + inline read of the pure `core/` validators. **Merge SKIPPED
(human-only).**

Retained + fixed:

- **Major — clone-mode path-confinement escape.** `onboard_exec` validated `target.parent` instead
  of the resolved target, and `validate_git_url` accepted `.`/`..`/empty repo segments, so a URL
  like `https://github.com/owner/..` derived a clone dir resolving above `ONBOARD_BASE_DIRS` yet
  passing the check. Fixed at the validator (root cause) + confine the target itself (defense-in-depth).
  `fix(bosun)` `1c8bed4`. DESIGN §5.2 updated.
- **Medium — ACC-08/ACC-12 detection proven only with the detector stubbed.** Added real unit tests
  for `_project_has_live_agent` (seeded RUNNING state in the per-project store) and
  `_any_allowlisted_pm2_app_exists` (real `pm2 jlist` parse), plus a redeploy `cwd` assertion.
  `test(bosun)` `be51cfc`.
- **Minor — cruft + auditability.** Enforce `_JOB_TYPES` in `create_job` (retires the unused-symbol
  anchor), close the parent log fd after the detached spawn, append `job_id` to every async-op audit
  line (joins `control/audit.log` to the durable job record), drop the dead `script_for_target`
  rebind, complete the `redeploy_target` docstring. `refactor(bosun)` `6967c59`.

Verdict: no critical findings; all retained critical/major/medium resolved. Local gate re-run green
(ruff + mypy 152 src files + 1517 area tests + layering 6/6 + size: no hard-ceiling). Loop exits;
**PR left OPEN for a human to merge.**

Acknowledged-but-deferred minors (non-blocking, noted for the human): a redundant happy-path
confinement test (F3), a cosmetic test rename coupled to the ACC-02 name mapping (F5), and routing
`status` reads through the job path (F6 — consistent + tested by design).

### Cycle 2 — 2026-06-22 (post-`main`-merge re-review; commit `e058acd`)

Adversarial multi-lens review of the tree after merging current `main` (#74/#72/#71/#62 …). 12
findings fixed, 2 flagged as design/pre-existing. **Merge SKIPPED (human-only).** (The commit subject
self-labels this "review cycle 1" — it is the first pass of the re-review run, chronologically after
Cycle 1 above.)

- **App.jsx** — treat `GET /api/projects` 503 (empty registry) as zero-projects so the first-run
  wizard renders (was dead-on-arrival).
- **AdminPanel** — redeploy now confirms the SERVED build-SHA flip (`admin/version` exposes `build`);
  a timeout counts as failed, not a false "done".
- **WizardPanel/AdminPanel/api.js** — `getDaemon()` unwraps `{apps:[…]}` centrally (daemon panel no
  longer crashes; bootstrap-done guard accurate).
- **core/git_url** — reject embedded credentials. **admin_routes** — daemon-logs degrade gracefully on
  pm2 missing/timeout; version `update_available` is a real SHA compare. **app/ops** — any runner
  exception marks the job failed (no stuck "running").
- **tests** — ACC-10 unauth/CSRF (403/401), git-URL creds, ops failure, daemon-logs degrade.
  **docs** — DESIGN/ACCEPTANCE corrected.

### Cycle 3 — 2026-06-22 (commit `9d689bd`)

10 findings fixed, 0 regressions. **Merge SKIPPED (human-only).** (Commit subject self-labels "review
cycle 2".)

- **cli/config** — loud stderr warning when binding non-loopback with auth disabled (privileged
  `/api/admin/*` would be world-open) — non-breaking.
- **app/audit** — log (warning, `exc_info`) on a swallowed audit-append failure, keeping it fail-soft
  (PAUSE/project-delete are audit-only).
- **admin_routes** — wizard first-run gate now FAILS CLOSED (503) when the pm2 probe is indeterminate
  (was fail-open).
- **app/ops** — stream full job stdout/stderr to the durable `<id>.log` (was only a 4 KiB in-record tail).
- **app/health_dashboard** — distinguish UNKNOWN (read-error + null heartbeat) from measured-down;
  narrowed excepts + logging.
- **scripts/deploy-staging.sh** — drop `pip install || true` so a failed build aborts before the pm2
  restart (matches `deploy.sh`).
- **tests** — ACC-02 authed-session, ACC-07 positive add-project, `_actor_login` auth-on identity,
  pm2-indeterminate, durable-log, unknown-vs-down.

## Next action

All 5 phases complete + three PR-review cycles run (see Review cycles). All retained
critical/major/medium findings fixed; local `feat/bosun` carries the Cycle 2/3 corrections and a clean
merge of current `main` (`5713b79`). Branch fast-forward-pushed to PR #73 (the CONFLICTING state was an
artifact of the stale remote head, not a real conflict — local `merge origin/main` is "already
up-to-date"). PR is OPEN — **merge is human-only** (NOT performed automatically). Live verification
(DESIGN §17) is post-merge per the operator rule.
