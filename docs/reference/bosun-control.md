# Operator guide — in-UI control + onboarding (bosun)

How to control KanbanMate through KanbanMateUI (`https://km.iznogoudatall.xyz`) — the
admin dashboard, daemon control, PM2 bootstrap, project onboarding, and the first-run install
wizard. Every action described here is **authed** (session cookie from the UI login), **CSRF‑protected**
for mutating verbs, and **audited** (`<root>/audit.log`).

This guide assumes you have read the foundational operator rules:

- **[deployment.md](deployment.md)** — only `main` is ever served; `scripts/deploy.sh` is the
  sole sanctioned deploy path.
- **[repo-safety.md](repo-safety.md)** — always commit, never delete an unpushed/unmerged
  branch, and keep on-disk state backward‑compatible (so staging can share the prod root).

All routes live on the **authed `/api/admin/*`** prefix served by `kanban-km-config` (loopback
`127.0.0.1:8796`, fronted by Caddy at the `km` subdomain).

---

## 1. Pin the session secret — survive restarts

The UI login is configured through a gitignored `.env` file (see
`src/kanbanmate/cli/config.py:43`). The critical variable is:

```
KANBAN_MATE_UI_SESSION_SECRET=<a stable random string>
```

**Why.** Without it, the session secret is a random `secrets.token_hex(32)` generated on every
start — so a restart or redeploy **logs the operator out**, defeating in‑UI redeploy
(DESIGN §12). With a pinned secret, sessions survive across PM2 bounces and redeploys.

**How to set it.**

```bash
# 1. Generate a stable secret once.
openssl rand -hex 32

# 2. Put it in the production .env file (alongside login + password).
cat >> ~/deploy/kanban-mate/.env <<'EOF'
KANBAN_MATE_UI_SESSION_SECRET=<paste the hex string>
EOF

# 3. Redeploy so the new env is picked up.
cd ~/deploy/kanban-mate && ./scripts/deploy.sh
```

**Verify.** The health dashboard (`GET /api/admin/health`) includes a `session_secret_pinned`
boolean — it is rendered at the top of the KanbanMateUI dashboard (`src/kanbanmate/app/health_dashboard.py:64`).
When `true`, your session will survive the next restart. Also: `kanban config serve` prints a
warning at startup when auth is enabled but the secret is not pinned
(`src/kanbanmate/cli/config.py:138`).

> **Staging note.** The staging instance (`km-staging.iznogoudatall.xyz`) reads its own `.env`
> from `~/staging/kanban-mate/.env`. Pin the secret there too if you use staging regularly.

---

## 2. Health dashboard

`GET /api/admin/health` → a JSON payload with per‑project rows and global flags
(`src/kanbanmate/app/health_dashboard.py:47`). KanbanMateUI renders it as a table.

Each project row carries:

| Field | Meaning |
|---|---|
| `project_id` | The GitHub Projects v2 node id |
| `repo` | The `owner/name` registered for this project |
| `daemon_alive` | `true` if the heartbeat is fresher than 120 s |
| `heartbeat_age_s` | Seconds since the last heartbeat write |
| `github_api_ok` | `true` when the last tick completed and the circuit‑breaker is cold (zero consecutive failures) |
| `board_ok` | `true` when the last tick completed without raising |
| `token_present` | `true` when the GitHub token file exists for this project |

Global flags:

| Flag | Meaning |
|---|---|
| `pause_active` | The `PAUSE` kill‑switch sentinel exists → no agent launches |
| `session_secret_pinned` | `KANBAN_MATE_UI_SESSION_SECRET` is set in the environment → sessions survive restarts |
| `agents_waiting` | Total number of tickets across all projects whose persisted status is `"waiting"` (stuck or parked) |

> **How to read it.** If `daemon_alive` is `false` but `token_present` is `true`, the daemon
> may be hung or stopped. If `github_api_ok` is `false` but `board_ok` is `true`, the last tick
> succeeded but the circuit‑breaker has residual failures. If `agents_waiting` climbs, some
> ticket is parked in the WAITING column — check the board.

---

## 3. Daemon control — start / stop / restart

The daemon‑control surface is **allowlist‑guarded** (DESIGN §5.1). Four PM2 apps are
recognised (`src/kanbanmate/core/pm2_allowlist.py:11`):

| App name | What it runs |
|---|---|
| `kanban-km` | The main poll daemon (`kanban run`) |
| `kanban-km-serve` | The webhook receiver (`kanban serve`) |
| `kanban-km-config` | The KanbanMateUI config server (`kanban config serve`) |
| `kanban-staging-config` | The staging UI config server |

**List apps.** `GET /api/admin/daemon` → `{apps: [{app, status, pid, uptime_s, restarts}, …]}`.
Reads `pm2 jlist` and filters to the allowlist (`src/kanbanmate/http/admin_routes.py:81`).
Degrades gracefully when `pm2` is unavailable (returns an error string).

**Control an app.** `POST /api/admin/daemon/{app_name}/{action}` where action is one of
`start` / `stop` / `restart` / `status` (`src/kanbanmate/http/admin_routes.py:123`). This
spawns a **detached job** running `pm2 <action> <app_name>`. Returns `{job_id: <id>}`. The job
status is pollable from the UI.

**Refused actions.** A standalone `start` / `stop` / `restart` of a UI app
(`kanban-km-config` / `kanban-staging-config`) is **refused with 422**
(`src/kanbanmate/core/pm2_allowlist.py:33`). UI apps are only ever bounced as the tail of a
**redeploy job** (§6 below). This keeps the web SPA build ↔ server version in lockstep.

| Action | Allowed on | Refused on |
|---|---|---|
| `start` / `stop` / `restart` | `kanban-km`, `kanban-km-serve` | `kanban-km-config`, `kanban-staging-config` |
| `status` | Any allowlisted app | — |

---

## 4. Tail logs

`GET /api/admin/daemon/{app_name}/logs?lines=N` → `{lines: [str, …]}`
(`src/kanbanmate/http/admin_routes.py:141`).

Reads the last `N` lines of the PM2 log for the named app (piped from `pm2 logs --nostream
--lines N`). The app must be in `PM2_ALLOWLIST` (422 otherwise). `lines` is clamped to
[1, 1000]; default is 200.

**When to use it.** If the daemon is silent but a ticket is stuck WAITING, tail `kanban-km`
logs to see the most recent tick output. If the webhook receiver is returning 502, tail
`kanban-km-serve` logs.

---

## 5. PAUSE kill‑switch

The `PAUSE` kill‑switch stops **all agent launches** while leaving the daemon running — every
launch path (tick → decide → drain, reaper retry, agent‑authority intent drain) checks the
sentinel and short‑circuits (`src/kanbanmate/app/drain.py:86`, `src/kanbanmate/app/reaper.py:550`,
`src/kanbanmate/app/intents.py:168`, `src/kanbanmate/core/decide.py:133`).

**Read current state.** `GET /api/admin/pause` → `{active: bool}`
(`src/kanbanmate/http/admin_routes.py:189`).

**Toggle.** `POST /api/admin/pause` body `{active: true}` to engage, `{active: false}` to
release. Idempotent — creating an already‑existing sentinel or removing an absent one is a
no‑op. Every toggle is audited (`src/kanbanmate/http/admin_routes.py:195`).

**From the CLI** (outside the UI, equivalent):

```bash
kanban pause   # creates ~/.kanban-km/PAUSE
kanban resume  # removes ~/.kanban-km/PAUSE
```

**When to pause.** Before a risky maintenance operation (manual git surgery in the deploy
clone, a config migration, an npm install that might clobber). Agents that are already RUNNING
are left untouched — PAUSE prevents **new** launches and **retries**. Resume when done; the
next tick picks up any enqueued intents.

---

## 6. Redeploy prod / staging

`POST /api/admin/redeploy` body `{target: "prod"|"staging"}` spawns a detached job shelling
the audited deploy script (`scripts/deploy.sh` for prod, `scripts/deploy-staging.sh` for
staging — `src/kanbanmate/core/redeploy_target.py:14`).

The job runs in the correct clone directory (`~/deploy/kanban-mate` for prod,
`~/staging/kanban-mate` for staging — `src/kanbanmate/http/admin_routes.py:217`). Unknown
targets are refused with 422.

Returns `{job_id: <id>}`. The job is audited as `redeploy target=<X>`.

> **Important.** The deploy scripts themselves refuse to build unless the working tree is clean
> `main` (prod) or the target branch (staging). See [deployment.md](deployment.md) for the full
> guardrail explanation. If a redeploy job fails, check the job detail log in the UI or tail
> the autodeploy poller log.

**The autodeploy poller.** In production, a PM2‑supervised poller
`kanban-autodeploy` (`scripts/autodeploy-poll.sh`) auto‑redeploys on push to `main` (prod) or
`staging` (staging). The in‑UI redeploy is for the manual case — when the poller is stuck, or
you need immediate effect. See [deployment.md](deployment.md) for the autodeploy setup.

---

## 7. Onboard (add) / remove a project

### Add a project

`POST /api/projects` body `{mode: "local"|"clone", repo: "owner/name", ...}`
(`src/kanbanmate/http/projects_routes.py:55`). Spawns a detached job that:

- **`mode:local`** — registers an already‑cloned repo at a filesystem `path`.
- **`mode:clone`** — clones from a `git_url`, then registers it.

The `path` must be under an allowed root (`ONBOARD_BASE_DIRS`); the `git_url` must pass the
GitHub‑only URL allowlist (`src/kanbanmate/core/git_url.py`). Invalid values → 422.

Returns `{job_id: <id>}`. Once the job succeeds, the project appears in
`<root>/projects.json` and the daemon starts sweeping it.

The **first‑run install wizard** reuses this exact route for its step‑2 (token → first project).

### Browse directories (for local mode)

`GET /api/admin/browse?path=<dir>` → `{path, entries: [{name, is_dir}, …]}`
(`src/kanbanmate/http/admin_routes.py:163`). Lists a directory confined to
`ONBOARD_BASE_DIRS`. Refused with 422 outside the allowed roots. Used by the onboarding
folder‑picker in KanbanMateUI (DESIGN §9).

### Remove a project

`DELETE /api/projects/{project_id}` (`src/kanbanmate/http/projects_routes.py:102`).

- **409** if the project still has a live agent (RUNNING or WAITING ticket).
- **404** if the project id is not in the registry.
- **200** `{deleted: <id>}` on success. The clone directory is **left on disk** (safe default).

> The live‑agent guard prevents orphaning a running agent mid‑launch. If you need to remove a
> project with a stuck agent, cancel the ticket first (`kanban cancel <ticket>` from the CLI)
> or wait for the agent to complete, then retry the DELETE.

---

## 8. First‑run install wizard

The install wizard is exposed under `POST /api/admin/wizard/*` — a four‑step flow designed to
be run **once**, from an empty `~/.kanban-km/` root, through KanbanMateUI
(`src/kanbanmate/http/admin_routes.py:244` onward). The UI renders it as a stepper panel
(`web/src/panels/WizardPanel.jsx`).

### Step 1 — Token

`POST /api/admin/wizard/token` body `{token: "<GitHub PAT>"}`.

Writes `<root>/token` mode **0600** atomically (tmp + fsync + rename). Refused 422 on an empty
token. Audited.

### Step 2 — First project

`POST /api/admin/wizard/project` — identical body and behaviour as `POST /api/projects` (§7
above). Delegates to the same handler. Returns `{job_id}`.

### Step 3 — Board provisioning

`POST /api/admin/wizard/provision` body `{project: "<Project v2 node id>"}`.

Spawns a detached job that provisions the board's Status options (the standard KanbanMate
column vocabulary). The project id is **resolved against the runtime registry** server‑side —
an unknown id is refused with 404. Returns `{job_id}`.

### Step 4 — PM2 bootstrap

`POST /api/admin/wizard/bootstrap` — **first‑run‑only** (DESIGN §10).

Shells `scripts/bootstrap-pm2.sh`, which starts the three PM2 apps (`kanban-km`,
`kanban-km-serve`, `kanban-km-config`) plus `pm2 save`, all pointed at the runtime root
(see `scripts/bootstrap-pm2.sh`).

- **409** if any allowlisted PM2 app **already** exists (`pm2 jlist` intersection with
  `PM2_ALLOWLIST`). This enforces the first‑run‑only contract — the bootstrap cannot clobber
  a live running daemon.
- Returns `{job_id}` on success. Audited as `wizard_bootstrap first-run`.

The script itself is operator‑reviewed shell (`set -euo pipefail`, no `sudo`, no global
state); the route only shells it — never inlines the PM2 commands.

---

## 9. Quick reference — all admin endpoints

| Method | Path | What it does |
|---|---|---|
| `GET` | `/api/admin/health` | Per‑project rows + global flags |
| `GET` | `/api/admin/version` | Local `__version__` vs `origin/main` |
| `GET` | `/api/admin/daemon` | Allowlisted PM2 app statuses |
| `POST` | `/api/admin/daemon/{app}/{action}` | Spawn a `pm2 <action> <app>` job |
| `GET` | `/api/admin/daemon/{app}/logs?lines=N` | Tail the last N log lines |
| `GET` | `/api/admin/pause` | Is the PAUSE kill‑switch engaged? |
| `POST` | `/api/admin/pause` | Toggle the PAUSE sentinel |
| `POST` | `/api/admin/redeploy` | Spawn a deploy‑script job (prod/staging) |
| `GET` | `/api/admin/browse?path=…` | List a confined directory |
| `POST` | `/api/projects` | Add a project (local/clone) |
| `DELETE` | `/api/projects/{id}` | Remove a project (409 if live agent) |
| `POST` | `/api/admin/wizard/token` | Write the GitHub PAT (step 1) |
| `POST` | `/api/admin/wizard/project` | Add first project (step 2) |
| `POST` | `/api/admin/wizard/provision` | Provision board options (step 3) |
| `POST` | `/api/admin/wizard/bootstrap` | First‑run PM2 bootstrap (step 4) |

All mutating endpoints are **CSRF‑protected** (`csrf_mw`), **authed** (session cookie), and
**audited** to `<root>/audit.log`.

---

## 10. CLI equivalents (outside the UI)

For completeness — every in‑UI action has a CLI equivalent:

```bash
# Health dashboard
kanban state --root ~/.kanban-km

# Daemon status
pm2 jlist | jq '.[] | select(.name | startswith("kanban-km"))'

# PAUSE toggle
kanban pause   --root ~/.kanban-km
kanban resume  --root ~/.kanban-km

# Redeploy (manual, from the clone)
cd ~/deploy/kanban-mate && ./scripts/deploy.sh
cd ~/staging/kanban-mate && ./scripts/deploy-staging.sh

# Onboard a project
kanban init --root ~/.kanban-km   # from the cloned repo, after token + registry setup

# PM2 bootstrap (first-run only)
bash scripts/bootstrap-pm2.sh ~/.kanban-km
```
