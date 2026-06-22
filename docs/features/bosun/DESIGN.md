# bosun — Fully installable & controllable via KanbanMateUI

> Daemon control · aggregated health · redeploy from main · project onboarding · kill-switch —
> every privileged operation from the web UI, no SSH for day-to-day ops.

Ticket: **#55** · Codename: **bosun** · Branch (next stage): `feat/bosun`
Grounded against merged `main` @ `d394522` (post-#47 tiller, post-#52 anchor). Every "exists/missing"
claim below is cited as `path:line` from that HEAD.

---

## 1. Purpose & scope

KanbanMate today is operated by SSH: the daemon, deploys, PAUSE kill-switch, and project onboarding
are all command-line. **bosun** lifts the whole _deployment control surface_ into **KanbanMateUI**
(`web/`, the PM2 app `kanban-km-config`). From the UI the operator can:

- see **aggregated health** per project (daemon liveness, heartbeat freshness, GitHub-API reach,
  board reachability, token presence) plus a **version/update badge** (local vs `origin/main`);
- **control the daemon** (start / stop / restart / status of allowlisted PM2 apps);
- tail **live PM2 logs**;
- toggle the **PAUSE kill-switch**;
- **redeploy from main** (prod and staging) including the config server's own self-restart;
- **onboard a project** (local folder or git clone) and **remove** one;
- run a **first-run install wizard** (token → first project → board provisioning → PM2 bootstrap).

Every privileged or long-running op runs through an async **jobs** layer, is **auth-gated + CSRF +
confirmed**, and is **audited**. Quick reads stay synchronous.

### In scope

The seven capability groups above, the jobs primitive, an app-wide CSRF layer, the pure validators
(PM2 allowlist · git-URL · path confinement), and the install wizard.

### Out of scope

- **Agent I/O** (tmux `send-keys` to a _running agent_) — that is **#47 (tiller, merged)**. bosun may
  _display_ "N agents WAITING" but never drives an agent. The **shared concern is the auth/CSRF
  model**, kept identical across both features.
- Multi-host control, token-rotation UI, backup/restore (future follow-ups).

---

## 2. Decisions (brainstorm, operator-confirmed 2026-06-21)

| #   | Decision                                                                                                                                                                                                                                                                                                                                                             | Consequence in this design                                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **Lockout safety → PM2 allowlist; self-restart only via redeploy.** Allowlist = `{kanban-km, kanban-km-serve, kanban-km-config, kanban-staging-config}`. Daemon-control may act on any allowlisted app **except a standalone stop/restart of a UI app** (`kanban-km-config`, `kanban-staging-config`). The UI app is bounced **only** as the tail of a redeploy job. | §5 `core/pm2_allowlist.py`; §7.2 daemon endpoint refuses UI-app standalone actions with 422; §8 redeploy is the only path that bounces the UI. |
| D2  | **Onboarding paths confined to base dirs.** `ONBOARD_BASE_DIRS` default `[~/dev, ~/deploy, ~/staging]`. Dir-browser and both add-paths must resolve (symlinks included) **under** one of these roots, else `422 path outside allowed roots`.                                                                                                                         | §5 `core/onboard_paths.py`; §9 onboarding validates before any clone/init.                                                                     |
| D3  | **First-run wizard → FULL in v1 (phase 5).** Token → first project → board provisioning → **PM2 bootstrap from the UI**. PM2 bootstrap is first-run-only (refuses once apps exist), confirm + CSRF + audit, runs as a job.                                                                                                                                           | §10 wizard; the chicken-and-egg of D1 is resolved because the allowlist is the static known-four set.                                          |
| D4  | **Redeploy target → prod + staging, via existing scripts.** prod → `scripts/deploy.sh`, staging → `scripts/deploy-staging.sh`. bosun **does not re-implement** the deploy steps/guards — it shells the audited scripts and streams their progress into the job record.                                                                                               | §8 redeploy job; honours deploy guardrails (only `main` served in prod).                                                                       |

---

## 3. Architecture overview

bosun adds **no new layer** and **no new third-party dependency**. It composes the existing
hexagonal stack: pure validators in `core/`, a jobs primitive + audit sink in `app/` (imperative
shell), and HTTP routes in `http/` registered on the **shared FastAPI `app`** via the exact
side-effect-import pattern tiller established.

```
web/ (KanbanMateUI panels)
   │ fetch /api/admin/* /api/ops/* /api/projects (POST/DELETE)
   ▼
http/  csrf_mw.py · ops_routes.py · admin_routes.py · projects_routes.py   ──▶ shared app (config_api.py)
   │            (register on `app` by side-effect import; reuse _auth_guard, _kanban_root, _auth_config)
   ▼
app/   ops.py (jobs primitive: detached runner) · audit.py (shared sink) · health_dashboard.py
   │            (imperative shell: subprocess pm2/git, fs writes)
   ▼
core/  pm2_allowlist.py · git_url.py · onboard_paths.py  (PURE — no I/O, validators only)
```

### 3.1 Why side-effect import (grounded)

`http/config_api.py` is **921 LOC** (`http/config_api.py:921`) — over the 800-LOC soft warning, just
under the 1000 hard ceiling. **bosun must NOT add endpoints there.** Instead it follows the chain
already in the tree: `config_api.py` imports `monitor_routes` for side-effect (`config_api.py:556`),
which imports `agent_terminal` for side-effect (`monitor_routes.py:353`), and `agent_terminal`
decorates the shared `app` it imports from `config_api` (`agent_terminal.py:19`, `agent_terminal.py:29`).
bosun's new modules register the same way. The shared helpers it reuses: `app` / `_auth_config()`
(`config_api.py:68`) / `_kanban_root()` (`config_api.py:108`) / `_load_registry` + `_projects_path`
(`config_api.py:137`).

### 3.2 Why an async jobs layer (Approach 2, validated)

**Redeploy self-restarts the config server** (`deploy.sh:54` restarts `kanban-km-config`). An
in-process HTTP request cannot outlive the very server handling it. The only shape that works: a
**detached** process (its own session/process group, so a `pm2 restart` of the config app does not
kill it) that writes a JSON status file under `<root>/ops/<id>.json`; the UI polls
`GET /api/ops/{id}` and reconnects after the bounce by polling `/api/health` until `version` flips.
Long ops (clone / `kanban init` / `pip`) also get real progress this way. Quick reads (health
dashboard, daemon status, version badge, PAUSE state) stay **synchronous** — no job overhead. The
job record IS the per-op audit trail, durable on disk.

---

## 4. Existing seams bosun reuses or extends (grounded)

| Concern              | Source of truth                                                                                                                                                                                                                                                                             | bosun's use                                                                                                                                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Auth (HTTP)          | `_auth_guard` `@app.middleware("http")` checks the **cookie only** (`config_api.py:84`, `:102`), exempts `_AUTH_OPEN_PATHS = {"/api/health","/api/login","/api/logout","/api/session"}` (`config_api.py:65`)                                                                                | All bosun `/api/admin/*`, `/api/ops/*` are auth-gated by this middleware unchanged.                                                                                                                        |
| Auth (tokens)        | `auth.py`: `COOKIE_NAME = "km_ui_session"` (`auth.py:31`), `make_token(login, secret, ttl, *, now)` HMAC-SHA256 (`auth.py:76`,`:93`), `verify_token(token, secret, *, now) -> str \| None` (`auth.py:97`), `AuthConfig.enabled = bool(password)` (`auth.py:52`)                             | Reused verbatim; CSRF is layered on top (§6), not a replacement.                                                                                                                                           |
| **CSRF**             | **NONE exists** — zero CSRF checks in `config_api.py` / `auth.py` / `agent_terminal.py`                                                                                                                                                                                                     | bosun adds an app-wide double-submit CSRF middleware (§6) — closes the gap for the _pre-existing_ write POSTs too.                                                                                         |
| Audit sink           | `agent_terminal._audit(login, issue, payload_summary)` appends to `<root>/control/audit.log`, ISO-8601 UTC, fail-soft (`agent_terminal.py:158`, `:174`–`:181`)                                                                                                                              | bosun extracts a generalised `app/audit.py append_audit(root, login, action, summary)` writing the same file/format; sync ops (PAUSE) use it. One audit story.                                             |
| Health endpoint      | `GET /api/health` returns `{"status":"ok","version": __version__}` (`config_api.py:241`,`:250`) — **unauthenticated** (in `_AUTH_OPEN_PATHS`)                                                                                                                                               | Kept as the simple liveness probe + reconnect signal. The **per-project dashboard is a NEW authed endpoint** `GET /api/admin/health` (see §7.1) — privileged data must not ride the public liveness route. |
| Projects registry    | `<root>/projects.json` keyed by `project_id`; `ProjectEntry` 13 fields (`cli/init.py:87`–`:156`); `_upsert_project` (`cli/init.py:316`); resolvers `resolve_by_project_id/repo/issue`, `enabled_entries` (`registry_resolve.py:73`–`:224`)                                                  | `GET /api/projects` (`config_api.py:639`) + `PATCH …/{id}` (`config_api.py:664`) already exist for _toggles_. bosun adds **create** + **delete** in a new module (not in the 921-LOC file).                |
| Onboarding primitive | `cli/init.py init(repo, *, root, clone, project_title, seeder, template_path, dev_repo_path, config_dir, ingress, ensure_clone) -> ProjectEntry` (`cli/init.py:343`–`:355`); writes `columns.yml`, `transitions.yml`, `projects.json`, `webhook_secret`                                     | "Add project" shells / calls `init` inside a job. `provision_board` (`app/board_provision.py:81`) + `import_board` (`app/board_import.py:18`) remain the board primitives the wizard reuses.               |
| PAUSE kill-switch    | sentinel `<root>/PAUSE`; `kill_switch_active()` = `(self.root / "PAUSE").exists()` (`adapters/store/fs_store.py:395`); read fresh each tick (`app/tick.py:541`); downgrades LAUNCH→BLOCK (`core/decide.py:128`–`:149`); holds agent intents (`app/intents.py:21`); **no HTTP toggle today** | bosun adds a **sync** `GET/POST /api/admin/pause` that reads / creates / removes `<root>/PAUSE`.                                                                                                           |
| Session secret       | `cli/config.py:40` `_ENV_SECRET = "KANBAN_MATE_UI_SESSION_SECRET"`; `cli/config.py:133` `secret = ui_env.get(_ENV_SECRET, "") or secrets.token_hex(32)` → **random per start** when unset; env overrides `.env` (`cli/config.py:79`)                                                        | Phase 2 **verifies + enforces** a persistent secret (§11).                                                                                                                                                 |
| Live-agent detection | LIVE = RUNNING **or** WAITING (`app/drain.py:109`); `Sessions` port `is_alive(name)` (`ports/workspace.py:317`); adapter `TmuxSessions.is_alive` (`adapters/workspace/sessions.py:236`)                                                                                                     | "remove project" refuses while a live agent exists (§9).                                                                                                                                                   |
| Deploy scripts       | `deploy.sh` guards main/clean/synced (`deploy.sh:28`,`:32`,`:38`), build (`:47`), `pip install -e .` (`:53`), `pm2 restart kanban kanban-km kanban-km-serve kanban-km-config` (`:54`); `deploy-staging.sh` clean-guard + `pm2 restart kanban-staging-config` (`deploy-staging.sh:38`)       | Redeploy jobs shell these (D4).                                                                                                                                                                            |
| PM2 app names        | `kanban-km`, `kanban-km-serve`, `kanban-km-config`, `kanban-staging-config`, `kanban-autodeploy` (`deploy.sh:54`, `deploy-staging.sh:38`, `autodeploy-poll.sh`)                                                                                                                             | The allowlist constant (§5).                                                                                                                                                                               |
| Version              | `__init__.py:11` `__version__ = "0.15.0"`                                                                                                                                                                                                                                                   | Version badge `local` side.                                                                                                                                                                                |

---

## 5. Pure validators (`core/` — no I/O)

These import nothing from `app`/`adapters`/`cli`/`daemon` and do no filesystem/network I/O. The
imperative shell does the I/O (resolve symlinks, run `pm2`) and then calls these for the decision.

### 5.1 `core/pm2_allowlist.py`

```python
PM2_ALLOWLIST: frozenset[str] = frozenset(
    {"kanban-km", "kanban-km-serve", "kanban-km-config", "kanban-staging-config"}
)
UI_APP_NAMES: frozenset[str] = frozenset({"kanban-km-config", "kanban-staging-config"})

def validate_daemon_action(app: str, action: str) -> str | None:
    """Return None if (app, action) is permitted, else a human-readable refusal reason.

    Enforces D1: app must be in PM2_ALLOWLIST; a standalone start/stop/restart of a UI app
    (UI_APP_NAMES) is refused — UI apps are only bounced by a redeploy job.
    """
```

`action ∈ {"start","stop","restart","status"}`. `status` is permitted on any allowlisted app
including UI apps; `stop`/`restart` on a UI app → refusal. Out-of-allowlist app → refusal.

### 5.2 `core/git_url.py`

```python
ALLOWED_GIT_HOSTS: frozenset[str] = frozenset({"github.com"})

def validate_git_url(url: str, *, allowed_hosts: frozenset[str] = ALLOWED_GIT_HOSTS) -> str | None:
    """Return None if url is a permitted clone source, else a refusal reason.

    Accepts only https://<host>/<owner>/<repo>(.git) where host ∈ allowed_hosts.
    Rejects file://, ssh://, git://, scp-style git@host:path, and any other scheme/host.
    Also rejects "."/".." path segments and an empty (post-`.git`) repo name, so the
    server-derived clone target cannot escape ONBOARD_BASE_DIRS (defense-in-depth with §5.3,
    which the detached runner re-checks against the resolved TARGET, not its parent).
    """
```

### 5.3 `core/onboard_paths.py`

```python
def is_within_base_dirs(resolved: PurePosixPath, resolved_bases: Sequence[PurePosixPath]) -> bool:
    """Pure containment check: True iff `resolved` equals or is under one of `resolved_bases`.

    The CALLER (app layer) does the I/O: expanduser + Path.resolve() (follows symlinks) on both
    the candidate and each ONBOARD_BASE_DIRS entry, then passes the resolved paths here.
    """
```

`ONBOARD_BASE_DIRS` default `["~/dev", "~/deploy", "~/staging"]` lives as a constant consumed by the
app layer (it expands `~`, which is environment I/O, so it is NOT a `core/` constant).

> **Layering note:** these three modules are import-direction-safe (downward only) and have no
> third-party imports. Verified pattern matches existing `core/` modules (e.g. `core/webhook_sig.py`).

---

## 6. CSRF (app-wide double-submit) — `http/csrf_mw.py`

Closes the pre-existing gap (no CSRF anywhere today) and protects bosun's writes.

- **Cookie:** a **non-HttpOnly** `km_csrf` cookie. The CSRF middleware mints it on any response that
  lacks it (random `secrets.token_urlsafe(32)`), `samesite="lax"`, `secure=_request_is_secure(...)`
  (`config_api.py:73`), `path="/"`. Non-HttpOnly so the SPA can read and echo it (double-submit needs
  no server-side state — the cookie value need only match the header).
- **Enforcement (auth-gated, 2.3 refinement):** for every **mutating** request
  (`POST`/`PATCH`/`PUT`/`DELETE`) under `/api/`, the middleware requires header `X-KM-CSRF` to equal
  the `km_csrf` cookie (constant-time compare); else **403**. `GET`/`HEAD`/`OPTIONS` exempt. Both
  `/api/login` AND `/api/logout` are exempt (the auth lifecycle: login has no prior cookie and only
  _sets_ the session; logout must never wedge on a missing/mismatched token). The session cookie
  alone is insufficient for a forged cross-site write because the attacker cannot read `km_csrf`
  (SOP) to populate the header. **Enforcement is gated on auth being ENABLED** (mirroring
  `_auth_guard`): CSRF only protects an _authenticated_ session, so when auth is disabled (open
  loopback dev — no session to forge against) enforcement is skipped entirely. The `km_csrf` cookie
  is **always** minted (regardless of auth state) so the SPA can read + echo it. This gating also
  keeps the pre-existing auth-off mutating-endpoint tests green (they would otherwise retroactively
  403).
- **Registration:** `@app.middleware("http")` in `http/csrf_mw.py`, imported for side-effect from
  the same chain as the other bosun modules. Starlette runs middlewares in reverse-registration
  order; CSRF is independent of `_auth_guard` (a request needs both a valid session cookie AND a
  matching CSRF header to mutate).
- **Retro-coverage:** because it is app-wide, it also protects the existing unprotected writes
  `POST /api/config` (`config_api.py:360`), `POST /api/board/provision` (`config_api.py:442`),
  `PATCH /api/projects/{id}` (`config_api.py:664`). The SPA `api.js` helper is updated once to attach
  `X-KM-CSRF` to all mutating calls.

**Frontend confirm UX:** destructive/privileged actions (daemon stop/restart, redeploy,
remove-project, PAUSE-on, wizard PM2 bootstrap) require an explicit confirm modal in the SPA before
the request is sent (reuse the existing dialog primitive, cf. `web/src/components/SyncBoardDialog.jsx`).

---

## 7. Read & control surface

> Naming: bosun's privileged routes live under `/api/admin/*` (authed dashboard/control) and
> `/api/ops/*` (jobs). Project create/delete extend the existing `/api/projects` resource.

### 7.1 Synchronous reads (no job)

| Verb · Path                                | Returns                                                                                                                                                                 | Notes                                                                                                                                                                                 |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/admin/health`                    | per-project rows: `{project_id, repo, daemon_alive, heartbeat_age_s, github_api_ok, board_ok, token_present}` + `{pause_active, session_secret_pinned, agents_waiting}` | Authed (NOT on `/api/health`). Reads heartbeat files + a cheap probe; reuses `app/health_reporter.py` data where available.                                                           |
| `GET /api/admin/version`                   | `{local, remote, update_available}`                                                                                                                                     | `local` = `__version__`/`webui/BUILD_COMMIT`; `remote` = `git ls-remote`/fetch `origin/main`. On fetch failure → `remote:"unknown", update_available:false` (degraded, never errors). |
| `GET /api/admin/pause`                     | `{active: bool}`                                                                                                                                                        | `(<root>/PAUSE).exists()`.                                                                                                                                                            |
| `GET /api/admin/daemon`                    | `[{app, status, pid, uptime_s, restarts}]` for allowlisted apps                                                                                                         | `pm2 jlist` parsed + filtered to `PM2_ALLOWLIST`.                                                                                                                                     |
| `GET /api/admin/daemon/{app}/logs?lines=N` | `{lines: [...]}` bounded tail (default 200, cap 1000)                                                                                                                   | `pm2 logs --nostream --lines N` (or read the pm2 log file). App must be allowlisted. Poll-based (no WS) for v1.                                                                       |
| `GET /api/admin/browse?path=…`             | `{path, entries:[{name,is_dir}]}`                                                                                                                                       | Path confined to `ONBOARD_BASE_DIRS` (§5.3); outside → 422.                                                                                                                           |

### 7.2 Daemon control (job + CSRF)

| Verb · Path                             | Effect                                                                                                                                                                                                                                  |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/admin/daemon/{app}/{action}` | `action ∈ {start,stop,restart}`. Validated by `core.pm2_allowlist.validate_daemon_action` (D1): out-of-allowlist → 422; standalone stop/restart of a UI app → 422. Spawns a **job** that runs `pm2 <action> <app>`; returns `{job_id}`. |

### 7.3 PAUSE toggle (sync write + CSRF + audit)

| Verb · Path                                   | Effect                                                                                                                                                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/admin/pause` body `{active: bool}` | `active:true` → create `<root>/PAUSE` (empty file); `active:false` → unlink it (idempotent). Appends to `<root>/control/audit.log` via `app/audit.py`. The daemon picks it up on its next tick (`app/tick.py:541`). |

---

## 8. Redeploy (job + CSRF) — `POST /api/admin/redeploy`

Body `{target: "prod" | "staging"}` → a **detached** job (D4, §3.2):

- `prod` → run `bash scripts/deploy.sh` from the prod clone (`~/deploy/kanban-mate`).
- `staging` → run `bash scripts/deploy-staging.sh` from the staging clone (`~/staging/kanban-mate`).

bosun **does not** re-implement the deploy steps — it shells the audited scripts and streams stdout
into the job record/log. The scripts already enforce the guards: `deploy.sh` refuses unless on clean
`main` synced with origin (`deploy.sh:28`,`:32`,`:38`); `pip install -e .` (`deploy.sh:53`) runs
**before** any `pm2 restart` (`deploy.sh:54`), so a `pip` failure under the scripts' `set -e` aborts
**before** the bounce → no half-deployed serve. **Self-restart:** `deploy.sh` restarts
`kanban-km-config` (the very server). The job is detached (own session via `start_new_session=True`),
so the `pm2 restart` of the config app does not kill it; it completes and writes `succeeded`. The UI
detects the bounce, then **polls `GET /api/health`** until `version` matches `origin/main` and
reconnects.

> Robustness note for the plan: confirm `deploy.sh`/`deploy-staging.sh` carry `set -euo pipefail` so
> a failed `pip` truly aborts before restart; if missing, that hardening is a one-line script edit
> (in-scope for phase 3 since redeploy correctness depends on it).

---

## 9. Project onboarding — `http/projects_routes.py`

New endpoints on the shared `app` (kept out of the 921-LOC `config_api.py`):

| Verb · Path                                                                                          | Effect                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/projects` body `{mode:"local"\|"clone", repo, path?, git_url?, project_title?, ingress?}` | **Job.** `mode:"local"` → register an existing clone at `path` (must pass §5.3). `mode:"clone"` → validate `git_url` (§5.2), `git clone` into a target under `ONBOARD_BASE_DIRS`, then call `cli.init.init(...)` (`cli/init.py:343`). Both paths end by `_upsert_project` writing `<root>/projects.json` (`cli/init.py:316`). The running daemon picks the new entry up on its next sweep (`registry_resolve.enabled_entries`, `registry_resolve.py:207`). |
| `DELETE /api/projects/{project_id}`                                                                  | **Sync + CSRF + audit.** Deregister: remove the entry from `<root>/projects.json` (the clone is **left on disk**). **Refused (409)** while the project has a **live agent** — LIVE = any ticket RUNNING/WAITING (`app/drain.py:109`) or a tmux session `Sessions.is_alive` true (`ports/workspace.py:317`).                                                                                                                                                |

The directory-browser (`GET /api/admin/browse`, §7.1) backs the "add from local folder" picker and
the clone-target chooser, both confined to `ONBOARD_BASE_DIRS`.

> Grounding note: `PATCH /api/projects/{id}` (toggles only, `config_api.py:664`) is untouched; bosun
> only **adds** create/delete. Delete is a _new_ capability (today removal is manual `projects.json`
> editing — `registry_resolve` has no delete).

---

## 10. First-run install wizard (phase 5) — `http/admin_routes.py` (wizard sub-routes)

FULL wizard (D3), each step a confirm+CSRF+audited call; the long steps are jobs:

1. **Token** — accept a GitHub PAT, write it to `<root>/token` (0600). Sync.
2. **First project** — same as `POST /api/projects` (job): clone/register + `kanban init`.
3. **Board provisioning** — `app/board_provision.provision_board` (`app/board_provision.py:81`) /
   `import_board` (`app/board_import.py:18`) as a job.
4. **PM2 bootstrap** — **first-run-only** job: refuses (409) if any allowlisted PM2 app already
   exists (`pm2 jlist`); otherwise shells a packaged **`scripts/bootstrap-pm2.sh`** (mirroring the
   D4 "reuse audited scripts" principle) that `pm2 start`s `kanban-km`, `kanban-km-serve`,
   `kanban-km-config` and `pm2 save`s. This is the highest-risk surface → ships last, most heavily
   acceptance-tested. The chicken-and-egg of D1 is benign: the allowlist is the _static known-four_
   set, so bootstrap creates exactly those names.

---

## 11. Jobs primitive — `app/ops.py` (+ hidden CLI runner)

### 11.1 Job record (`<root>/ops/<id>.json`)

```json
{
  "id": "20260621T153200-redeploy-ab12",
  "type": "redeploy|daemon|project_add|wizard_bootstrap",
  "actor": "operator-login",
  "args_summary": "target=prod",
  "state": "queued|running|succeeded|failed",
  "created_at": "ISO-8601Z",
  "started_at": "ISO-8601Z|null",
  "ended_at": "ISO-8601Z|null",
  "exit_code": 0,
  "stdout_tail": "…last ~4 KiB…",
  "error": "string|null"
}
```

This record IS the per-op audit trail (who/when/what/exit), durable on disk.

### 11.2 API

```python
def create_job(root, *, type, actor, argv, args_summary, cwd=None) -> str  # writes spec, spawns runner, returns id
def read_job(root, job_id) -> dict
def list_jobs(root, *, type=None, limit=50) -> list[dict]
def gc_jobs(root) -> None        # keep last 50 + prune > 14 days, fail-soft (mirrors cockpit result-GC)
def run_job(root, job_id) -> int # the runner body: mark running → exec argv → capture → mark succeeded/failed
```

### 11.3 Detached execution (the crux)

`create_job` writes the spec `state:"queued"`, then spawns
`Popen([sys.executable, "-m", "kanbanmate.cli.ops_exec", job_id, "--root", root],
start_new_session=True, stdout=<ops/<id>.log>, stderr=STDOUT)`. `start_new_session=True` puts the
runner in its **own session/process group**, so a `pm2 restart kanban-km-config` (redeploy's tail)
sends signals to the config app's group only — the runner **survives**. The runner (`run_job`)
flips the record to `running`, executes `argv`, tails stdout into the record, and writes
`succeeded`/`failed` with the exit code. A new config server (post-bounce) serves `GET /api/ops/{id}`
straight from the file. The runner is a **standalone `python -m` module** (`cli/ops_exec.py`), NOT a
command registered on the `kanban` Typer app (`cli/app.py`): the sibling-module pattern keeps
`cli/app.py` under the 1000-LOC hard ceiling and avoids the `__main__` double-import trap of
re-importing the `kanban` app module while it is already executing. The onboarding + provisioning
runners follow the same pattern — `cli/onboard_exec.py` (spawned from `http/projects_routes.py`) and
`cli/provision_exec.py` (spawned from `http/admin_routes.py`).

Read-time robustness (review-c3): `read_job` lazily reaps a record stuck `queued` past a 60 s spawn
deadline (the detached runner died before reaching `run_job` — a broken venv / ImportError / OOM) to
`failed`, and folds the durable `<id>.log` tail into `stdout_tail` when the record captured no output
of its own — so a pre-`run_job` crash surfaces the real spawn/import traceback rather than a bare
poller timeout.

### 11.4 Jobs HTTP — `http/ops_routes.py`

| Verb · Path                 | Returns                            |
| --------------------------- | ---------------------------------- |
| `GET /api/ops?type=&limit=` | `{jobs:[record,…]}` (newest first) |
| `GET /api/ops/{id}`         | one record (404 if unknown)        |

Jobs are **created only by the privileged endpoints** above (no generic `POST /api/ops`), so every
job's argv is server-constructed from validated inputs — never a client-supplied command.

---

## 12. Persistent session secret (phase-2 dependency)

`cli/config.py:133` falls back to `secrets.token_hex(32)` when `KANBAN_MATE_UI_SESSION_SECRET` is
unset → **random per start** → every restart/redeploy logs the operator out, defeating in-UI
redeploy. Phase 2:

- **Detect:** at `kanban config serve` startup, if auth is enabled (`AuthConfig.enabled`,
  `auth.py:52`) but the secret fell back to random, log a **fail-loud WARNING** (do not hard-fail —
  that would break dev) and surface it as `session_secret_pinned:false` in `GET /api/admin/health`.
- **Document:** operator sets `KANBAN_MATE_UI_SESSION_SECRET` in the UI `.env` (read at
  `cli/config.py:79`).
- **Regression test:** a restart with the secret pinned does NOT invalidate an existing token
  (`make_token`/`verify_token` round-trip across two `AuthConfig` instances built from the same
  pinned secret).

---

## 13. Security model (one model across #47 and bosun)

- **Auth:** reuse `_auth_guard` (session cookie) for all `/api/*`; in-handler check for any WS.
- **CSRF:** app-wide double-submit (§6) — also retro-protects the pre-existing write POSTs.
- **Confirm UX:** explicit confirm modal for restart, redeploy, remove-project, PAUSE-on, wizard
  bootstrap.
- **Allowlists + validators (pure `core/`):** PM2 allowlist (D1), git-URL validation (§5.2), path
  confinement to `ONBOARD_BASE_DIRS` (D2).
- **Audit:** each job record (`<root>/ops/<id>.json`) + sync ops append to
  `<root>/control/audit.log` via `app/audit.py` (same file/format as `agent_terminal._audit`,
  `agent_terminal.py:174`).
- **No new exposure:** server stays loopback behind Caddy; no new public port; no new third-party
  dependency (subprocess `pm2`/`git` + stdlib only; FastAPI/uvicorn already in the `[ui]` extra,
  `pyproject.toml`).

---

## 14. Phases (single feature; order = increasing risk)

1. **Jobs primitive + read-only health dashboard + version badge.**
   `core/` validators stubs as needed; `app/ops.py` + the standalone `cli/ops_exec.py` runner module
   (`python -m`, not a `cli/app.py` command — see §11.3) + `http/ops_routes.py`;
   `app/health_dashboard.py` + `GET /api/admin/health`, `GET /api/admin/version`. No writes → no CSRF
   yet. Lands value first.
2. **First writes: daemon control + PM2 logs + PAUSE toggle + CSRF middleware & confirm UX +
   persistent-secret enforcement.** `core/pm2_allowlist.py`; `http/csrf_mw.py`; `app/audit.py`;
   `GET /api/admin/daemon`, `POST …/{app}/{action}`, `GET …/{app}/logs`, `GET/POST /api/admin/pause`.
   §12.
3. **Redeploy (prod + staging).** `POST /api/admin/redeploy` detached jobs shelling
   `deploy.sh`/`deploy-staging.sh`; UI reconnect-on-bounce; verify scripts' `set -e` ordering.
4. **Project onboarding.** `core/git_url.py` + `core/onboard_paths.py`; `http/projects_routes.py`
   (`POST /api/projects`, `DELETE /api/projects/{id}`); `GET /api/admin/browse`; live-agent guard.
5. **Full first-run install wizard + docs + ACCEPTANCE.** wizard sub-routes + `scripts/bootstrap-pm2.sh`
   (first-run-only); operator docs; executable ACC-NN matrix.

UI work threads through every phase in `web/src/panels/` (extend the existing `DaemonPanel.jsx` and a
new admin/ops panel; reuse `api.js`, `SyncBoardDialog.jsx` for confirms).

---

## 15. Testing

- **`core/` validators** (pure, exhaustive): `pm2_allowlist` (each app × each action incl.
  UI-app-standalone-refusal + out-of-allowlist), `git_url` (https-github accept; file/ssh/git/scp
  reject), `onboard_paths` (under/equal/outside/symlink-escape). Real values, both sides non-trivial.
- **`app/ops.py`**: job lifecycle queued→running→succeeded/failed with an injected fast command;
  detachment (record readable after the spawner returns); `gc_jobs` retention (keep-50 / prune-14d).
- **`app/audit.py`**: appends the expected line shape to `<root>/control/audit.log`.
- **HTTP (FastAPI `TestClient`, `[ui]`+`[dev]` extras, `pyproject.toml`)**: auth-gating (401 without
  cookie), CSRF (403 on mutating call without/with-mismatched `X-KM-CSRF`; GET exempt), allowlist 422,
  path-confinement 422, git-URL 422, remove-project 409 with a stubbed live agent, session-secret
  round-trip across restart. Assert on parsed JSON, never Rich/ANSI substrings.
- **No new dependency** to declare; CI already installs `.[dev,ui,mcp]` (`.github/workflows/pr.yml`).

---

## 16. ACCEPTANCE (draft — formalised as executable ACC-NN during planning)

- **ACC-01** `GET /api/health` returns liveness+version (unchanged, unauthenticated).
- **ACC-02** `GET /api/admin/health` (authed) returns daemon/heartbeat/GitHub-API/board/token rows
  per project + `pause_active` + `session_secret_pinned`.
- **ACC-03** `POST /api/admin/daemon/kanban-km/restart` (CSRF) → job → `succeeded`; `pm2 jlist`
  shows it online.
- **ACC-04** Standalone restart/stop of `kanban-km-config` is **refused** (422); redeploy CAN bounce
  it and the UI reconnects.
- **ACC-05** Redeploy (prod) pulls main, installs, restarts; UI reconnects post-bounce; `__version__`
  matches `origin/main`. Redeploy (staging) drives `deploy-staging.sh`.
- **ACC-06** A `pip` failure aborts the redeploy **before** any restart (no half-deployed serve).
- **ACC-07** Add project from local folder / from git URL registers it in `projects.json`; daemon
  picks it up on its next sweep.
- **ACC-08** Remove project deregisters it (clone left on disk); refused (409) while it has a live
  agent.
- **ACC-09** PAUSE toggle creates/removes `<root>/PAUSE`; daemon stops/resumes launches accordingly.
- **ACC-10** Unauthenticated mutating request → 403 (the CSRF middleware runs outermost, so a
  no-session POST is refused by CSRF before the auth guard ever runs); the same request WITH a valid
  CSRF header but no session reaches the auth guard → 401; CSRF-less/mismatched mutating request →
  403; out-of-allowlist PM2 app → 422; onboarding path outside `ONBOARD_BASE_DIRS` → 422;
  non-allowlisted git URL → 422.
- **ACC-11** Session secret pinned: a restart does NOT log the operator out (regression for §12).
- **ACC-12** Wizard PM2 bootstrap runs first-run-only (409 once apps exist), confirm+CSRF+audited.

---

## 17. Live verification (post-merge, per operator rule)

After merge + deploy, verify on the live build (`km.iznogoudatall.xyz`): `/api/admin/health` returns
per-project rows; a `kanban-km` restart via the UI succeeds and `pm2 jlist` shows it back; a staging
redeploy completes and the UI reconnects; PAUSE toggle is observed by the daemon. Report
proven-live vs blocked-on-operator-infra vs in-flight.

## 18. Out of scope / future

Agent I/O (#47, merged) · multi-host control · token-rotation UI · backup/restore · WS-streamed PM2
logs (poll-based bounded tail in v1; WS noted as a later upgrade reusing tiller's pane WS).
