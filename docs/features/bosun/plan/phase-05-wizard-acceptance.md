# Phase 5 — First-run install wizard + docs + ACCEPTANCE

## Gate

Phases 1–4 complete and green (jobs, CSRF, audit, redeploy, onboarding). `make check` green on
phase-4 HEAD. This is the **highest-risk** surface (PM2 bootstrap from the UI) — it composes every
prior primitive and ships last, most heavily acceptance-tested (DESIGN §10, §14.5). Satisfies
**ACC-12** and consolidates the executable ACC-01..11 matrix.

## Overview

Add the full first-run install wizard (token → first project → board provisioning → PM2 bootstrap)
as confirm+CSRF+audited steps (long steps as jobs), the packaged `scripts/bootstrap-pm2.sh`
(first-run-only), the operator docs, and the executable `ACCEPTANCE.md` matrix that maps ACC-01..12
to their proving tests. Six sub-phases.

---

## Sub-phase 5.1 — Wizard token + first-project sub-routes

**Commit:** `feat(bosun): install-wizard token + first-project routes`

**Files touched:**

- Modify: `src/kanbanmate/http/admin_routes.py` — add `POST /api/admin/wizard/token`,
  `POST /api/admin/wizard/project`.
- Create: `tests/http/test_wizard_token_project.py`

**What to implement** (DESIGN §10 steps 1–2):

- `POST /api/admin/wizard/token` body `{token}` → write `<root>/token` mode **0600**, sync, audited.
  Reuse the token-path convention (`load_token` reads `<root>/token` — confirm the exact path helper
  in `cli/init.py`/`adapters` before writing; `init` calls `load_token()`, `cli/init.py:414`).
- `POST /api/admin/wizard/project` → same body/behaviour as `POST /api/projects` (phase 4) — a job
  doing clone/register + `kanban init`. Delegate to the phase-4 path (call the same job-creating
  helper) rather than duplicating.

**Tests:** token route writes a 0600 file with the given content (assert `oct(stat.st_mode & 0o777)
== "0o600"`); project route returns a `job_id` (monkeypatch `ops.create_job`). Run targeted pytest →
PASS.

---

## Sub-phase 5.2 — Board provisioning wizard step

**Commit:** `feat(bosun): install-wizard board-provisioning route (job)`

**Files touched:**

- Modify: `src/kanbanmate/http/admin_routes.py` — add `POST /api/admin/wizard/provision`.
- Create: `tests/http/test_wizard_provision.py`

**What to implement** (DESIGN §10 step 3) — a job calling `app/board_provision.provision_board`
(`app/board_provision.py:81`) / `app/board_import.import_board` (`app/board_import.py:18`). Match
their real signatures before wiring (read both `provision_board` and `import_board` defs and pass the
exact args). The route validates the target project then `ops.create_job(type="...")` shelling a
hidden `kanban` provision command or calling the helper inside the job body.

> Ground the two board primitives' signatures (`grep -n "^def provision_board" app/board_provision.py`
> and `"^def import_board" app/board_import.py`) — the design cites `:81` and `:18`; confirm and match
> argument names exactly (a call that doesn't match the real def is a defect).

**Test:** route returns a `job_id` (monkeypatch the job creator); unknown project → 404/422 per the
resolver. Run targeted pytest → PASS.

---

## Sub-phase 5.3 — PM2 bootstrap: `scripts/bootstrap-pm2.sh` + first-run-only route

**Commit:** `feat(bosun): first-run-only PM2 bootstrap (script + route)`

**Files touched:**

- Create: `scripts/bootstrap-pm2.sh` (`set -euo pipefail`; `pm2 start` the known-four apps then
  `pm2 save`).
- Modify: `src/kanbanmate/http/admin_routes.py` — add `POST /api/admin/wizard/bootstrap`.
- Create: `tests/http/test_wizard_bootstrap.py`
- Create: `tests/test_bootstrap_script.py` (text guard, alongside `tests/test_deploy_scripts.py`).

**What to implement** (DESIGN §10 step 4, D3) — **first-run-only**: refuse (409) if any allowlisted
PM2 app already exists (parse `pm2 jlist`); otherwise spawn a job shelling `scripts/bootstrap-pm2.sh`.
The chicken-and-egg of D1 is benign: the allowlist is the static known-four set, so bootstrap creates
exactly `kanban-km`, `kanban-km-serve`, `kanban-km-config` (DESIGN §10):

```python
@app.post("/api/admin/wizard/bootstrap")
async def wizard_bootstrap(request: fastapi.Request) -> JSONResponse:
    """First-run-only PM2 bootstrap (DESIGN §10). 409 if any allowlisted app already exists."""
    if _any_allowlisted_pm2_app_exists():        # parse `pm2 jlist`, intersect PM2_ALLOWLIST
        raise HTTPException(status_code=409, detail="PM2 apps already exist — bootstrap is first-run only")
    login = _actor_login(request)
    job_id = ops.create_job(_kanban_root(), type="wizard_bootstrap", actor=login,
                            argv=["bash", "scripts/bootstrap-pm2.sh"], args_summary="bootstrap")
    append_audit(_kanban_root(), login, "wizard_bootstrap", "first-run")
    return JSONResponse(content={"job_id": job_id})
```

`scripts/bootstrap-pm2.sh` (mirrors the deploy-script reuse principle — privileged shell logic stays
in an audited script):

```bash
#!/usr/bin/env bash
# bootstrap-pm2.sh — first-run PM2 bootstrap for KanbanMate (bosun §10).
set -euo pipefail
pm2 start kanban run --name kanban-km -- --root "${KANBAN_ROOT:-$HOME/.kanban-km}"
pm2 start kanban serve --name kanban-km-serve -- --root "${KANBAN_ROOT:-$HOME/.kanban-km}"
pm2 start kanban config serve --name kanban-km-config -- --root "${KANBAN_ROOT:-$HOME/.kanban-km}"
pm2 save
```

> Ground the exact `kanban run`/`serve`/`config serve` invocations against the existing
> `ecosystem.config.js` / `deploy.sh` app definitions before finalising the script (the app names
> `kanban-km`/`kanban-km-serve`/`kanban-km-config` are confirmed at `deploy.sh:54`); match the real
> CLI subcommands + `--root` flag the deployed apps use. This script is operator-reviewed; the route
> only shells it.

**Tests:**
- `tests/http/test_wizard_bootstrap.py`: with a stubbed "app exists" → 409; with stubbed "none
  exist" + monkeypatched `ops.create_job` → 200 `{job_id}`. (**ACC-12**.)
- `tests/test_bootstrap_script.py`: text guard — `set -euo pipefail` present, references the three
  app names + `pm2 save`.

Run targeted pytest → PASS.

---

## Sub-phase 5.4 — UI: install wizard flow

**Commit:** `feat(bosun): KanbanMateUI first-run install wizard`

**Files touched:**

- Create: `web/src/panels/WizardPanel.jsx` — stepper: token → first project (reuses the phase-4
  onboarding form + browser) → provision → PM2 bootstrap (confirm modal; first-run-only, disabled
  once apps exist via `GET /api/admin/daemon`).
- Modify: `web/src/` nav to show the wizard when no project is registered (`GET /api/admin/health`
  returns zero projects).

Run `cd web && npm run build` → succeeds.

---

## Sub-phase 5.5 — Operator docs

**Commit:** `docs(bosun): operator guide for in-UI control + onboarding`

**Files touched:**

- Create: `docs/reference/bosun-control.md` — how to: pin `KANBAN_MATE_UI_SESSION_SECRET` (DESIGN
  §12), use the health dashboard, control the daemon, tail logs, toggle PAUSE, redeploy prod/staging,
  onboard/remove a project, run the first-run wizard. Cross-reference `docs/reference/deployment.md`
  and `docs/reference/repo-safety.md`.
- Modify: `CLAUDE.md` "Current Feature" pointer is updated by the feature lifecycle, not here; this
  sub-phase only adds the reference doc.

No tests (docs). Verify links resolve.

---

## Sub-phase 5.6 — Executable ACCEPTANCE matrix

**Commit:** `docs(bosun): executable ACCEPTANCE matrix (ACC-01..12)`

**Files touched:**

- Create: `docs/features/bosun/ACCEPTANCE.md` — the ACC-01..12 table (DESIGN §16) with, for each
  row: the criterion, the **proving test path::test_name** (from phases 1–5), and the live-verify
  step (DESIGN §17) where the criterion can only be proven on the deployed build.

**Mapping (each ACC → its automated proof + live check):**

| ACC | Criterion (DESIGN §16) | Automated proof | Live (§17) |
|-----|------------------------|-----------------|------------|
| ACC-01 | `/api/health` unchanged, unauth | existing health test + phase 1 DoD | n/a |
| ACC-02 | `/api/admin/health` authed rows | `test_admin_health_authed_returns_rows`, `test_admin_health_requires_auth_when_enabled` | health rows live |
| ACC-03 | restart → job succeeded | `test_daemon_restart_allowed_app_creates_job` | `pm2 jlist` online |
| ACC-04 | UI-app standalone refused 422 | `test_daemon_restart_ui_app_refused_422` + `test_ui_app_standalone_mutation_refused` | redeploy CAN bounce it |
| ACC-05 | redeploy prod+staging | `test_redeploy_prod_creates_job` + `test_*_maps_to_*` | bounce + reconnect live |
| ACC-06 | pip fails before restart | `test_deploy_sh_has_strict_mode_and_pip_before_restart` | n/a (script-guarded) |
| ACC-07 | add local/clone registers | `test_create_local_*`, `test_create_clone_*` (422 negatives) + onboard tests | daemon picks up live |
| ACC-08 | remove deregisters; 409 live agent | `test_delete_refused_409_with_live_agent`, `test_delete_removes_entry` | n/a |
| ACC-09 | PAUSE toggle observed | `test_pause_on_creates_sentinel_and_store_sees_it` | daemon halts launches live |
| ACC-10 | 401/403/422 negatives | CSRF/auth/allowlist/path/url tests across phases 2 & 4 | n/a |
| ACC-11 | token survives pinned-secret restart | `test_token_survives_restart_with_pinned_secret` | no logout live |
| ACC-12 | bootstrap first-run-only | `test_wizard_bootstrap` (409 once apps exist) | first-run only live |

No new tests here (it indexes the existing ones) — but the gate **runs the full suite** to confirm
every referenced test exists and passes.

---

## Definition of Done

- [ ] `make check` → green across the WHOLE suite (all phases' tests).
- [ ] `pytest tests/http/test_wizard_token_project.py tests/http/test_wizard_provision.py tests/http/test_wizard_bootstrap.py tests/test_bootstrap_script.py -v` — all PASS.
- [ ] Every ACC row in `docs/features/bosun/ACCEPTANCE.md` names a test that exists and passes (grep
  each `test_*` name → present).
- [ ] `python -c "import kanbanmate.http.admin_routes, kanbanmate.http.projects_routes, kanbanmate.http.ops_routes, kanbanmate.http.csrf_mw"` → no import error.
- [ ] `cd web && npm run build` → succeeds; wizard renders for a zero-project root.
- [ ] No module over 1000 LOC; `http/config_api.py` only ever gained side-effect import lines.
- [ ] **ACC-12** holds; the full ACC-01..12 matrix is documented + proven.
- [ ] Operator docs (`docs/reference/bosun-control.md`) cover secret-pinning + every control surface.
- [ ] Feature is ready for `/implement:feature-pr` (push + PR + CI). Live verification (DESIGN §17)
  is post-merge per the operator rule.
