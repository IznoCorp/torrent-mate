# bosun — implementation plan (INDEX)

> **Codename**: bosun · **roadmap**: bosun · **bump**: minor (0.15.0 → 0.16.0) ·
> **Branch (next stage)**: `feat/bosun` · **Mode**: single feature branch (one PR).
> **Design**: `docs/features/bosun/DESIGN.md` · **Ticket**: #55

## Goal (one line)

Lift KanbanMate's whole **deployment control surface** into KanbanMateUI — aggregated health,
daemon control, live PM2 logs, PAUSE kill-switch, redeploy-from-main, project onboarding/removal,
and a first-run install wizard — every privileged op through an async **jobs** layer, **auth-gated +
CSRF + confirmed + audited**, no new third-party dependency (DESIGN §1).

## Phase ordering rationale

Order = **increasing risk** (DESIGN §14). Phase 1 lands read-only value (jobs primitive + health
dashboard + version badge) with **no writes → no CSRF needed yet**, so the jobs machinery is proven
on harmless ops before any mutation exists. Phase 2 adds the first writes (daemon control, PM2 logs,
PAUSE) and therefore introduces the **app-wide CSRF middleware** + confirm UX + the **persistent
session-secret** enforcement that redeploy depends on (DESIGN §12) — CSRF must exist before any
mutating route ships. Phase 3 (redeploy) is the self-restart crux and **requires** phase 1's
detached-job primitive to survive the config-server bounce (DESIGN §3.2). Phase 4 (onboarding) adds
the `core/git_url.py` + `core/onboard_paths.py` validators and project create/delete, building on
phase 2's CSRF + audit. Phase 5 (the full first-run wizard + PM2 bootstrap) is the highest-risk
surface — it composes every prior primitive (jobs, CSRF, audit, validators, board provisioning) and
ships last, most heavily acceptance-tested, alongside docs and the executable ACC-NN matrix.

## Phases

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | Jobs primitive + read-only health dashboard + version badge | phase-01-jobs-and-health.md | [x] |
| 2 | Daemon control + PM2 logs + PAUSE + CSRF middleware + persistent secret | phase-02-control-csrf-pause.md | [x] |
| 3 | Redeploy from main (prod + staging) | phase-03-redeploy.md | [x] |
| 4 | Project onboarding (add local / add clone / remove) + dir-browser | phase-04-onboarding.md | [x] |
| 5 | First-run install wizard + docs + ACCEPTANCE | phase-05-wizard-acceptance.md | [x] |

## Cross-cutting invariants (every phase upholds)

- **Layering (downward only)**: the three new `core/` validators
  (`pm2_allowlist`, `git_url`, `onboard_paths`) import **nothing** from `app`/`adapters`/`cli`/
  `daemon` and do **no I/O** — the imperative shell (`app/`) does the I/O (resolve symlinks, run
  `pm2`/`git`) then calls the pure validator for the decision (DESIGN §5). Verified pattern matches
  `core/webhook_sig.py:1-20` (pure, stdlib-only). The layering guard `tests/test_layering.py` walks
  the full AST, so a function-local import does **not** bypass it — keep `core/` clean.
- **No new endpoints in `http/config_api.py`** (already **921 LOC**, over the 800-LOC soft warning,
  under the 1000 hard ceiling — `http/config_api.py:921`). All bosun routes live in **new** `http/`
  modules registered on the shared `app` via **side-effect import**, exactly as tiller did
  (`http/monitor_routes.py:353` → `http/agent_terminal.py:29` decorates the shared `app`). New
  modules: `http/ops_routes.py`, `http/admin_routes.py`, `http/projects_routes.py`, `http/csrf_mw.py`.
- **Reused shared helpers** (imported from `http/config_api.py`): `app`, `_auth_config()`
  (`config_api.py:68`), `_kanban_root()` (`config_api.py:108`), `_request_is_secure()`
  (`config_api.py:73`), and `_load_registry`/`_projects_path` (defined in `cli/init.py:203`/`:191`,
  imported into `config_api.py:39-40`).
- **Auth unchanged**: the existing `_auth_guard` `@app.middleware("http")` (`config_api.py:84`)
  cookie check covers every new `/api/admin/*`, `/api/ops/*`, `/api/projects` route automatically
  (they are NOT in `_AUTH_OPEN_PATHS = {"/api/health","/api/login","/api/logout","/api/session"}`,
  `config_api.py:65`). Privileged dashboard data rides a **new authed** `/api/admin/health`, never
  the public `/api/health` (`config_api.py:241`).
- **No new third-party dependency**: subprocess `pm2`/`git` + stdlib only; FastAPI/uvicorn already
  in the `[ui]` extra (`pyproject.toml`). CI already installs `.[dev,ui,mcp]`
  (`.github/workflows/pr.yml`) — nothing to add.
- **Jobs are server-constructed only**: there is **no** generic `POST /api/ops`; every job's argv is
  built by a privileged endpoint from validated inputs — never a client-supplied command (DESIGN
  §11.4).
- **Tests mirror the layer tree** `tests/{core,app,http,...}` (confirmed dirs: `tests/core`,
  `tests/app`, `tests/http`). HTTP tests assert on **parsed JSON**, never Rich/ANSI substrings;
  `pytest.importorskip("fastapi")` guards the `[ui]`-extra tests (pattern:
  `tests/http/test_agent_terminal.py:384`).
- **`make check`** (ruff + mypy + tests + module-size guards, 1000-LOC hard ceiling) green at each
  phase gate.

## Acceptance (executable ACC-NN — full matrix in phase 5, DESIGN §16)

ACC-01..12 map to phases: ACC-01/02 (phase 1 health/version), ACC-03/04/09/10-partial/11 (phase 2
daemon/pause/CSRF/secret), ACC-05/06 (phase 3 redeploy), ACC-07/08/10-partial (phase 4 onboarding),
ACC-12 (phase 5 wizard). Each phase's plan lists the ACC rows it satisfies and adds the test that
proves it.
