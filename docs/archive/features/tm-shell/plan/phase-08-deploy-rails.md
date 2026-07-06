# Phase 8 — Deploy rails (scripts, autodeploy, docs, staging)

## Gate

- All phases 1–7 complete: backend + frontend + auth + WS + PWA functional,
  all tests pass, CI green.
- `personalscraper/web/static/` is gitignored (Vite build output fills it).
- DNS records for `tm.iznogoudatall.xyz` and `tm-staging.iznogoudatall.xyz`
  point to IznoServer (operator pre-requisite; verify via `dig`).

## Sub-phases

### 8.1 — Deploy scripts (prod + staging)

**Commit**: `feat(tm-shell): add deploy scripts for prod and staging clones`

**Files**:

| Action | Path                        |
| ------ | --------------------------- |
| Create | `scripts/deploy.sh`         |
| Create | `scripts/deploy-staging.sh` |

**Work**:

1. `scripts/deploy.sh` — DESIGN §6:
   - Pre-flight: branch == `main`, working tree clean, HEAD == `origin/main`.
   - `cd frontend && npm ci && npm run build` → copies `dist/*` to
     `personalscraper/web/static/` + stamps `BUILD_COMMIT` (`git rev-parse
--short HEAD`).
   - In deploy clone (`~/deploy/torrentmate`): `git pull --ff-only origin
main`, `pip install -e ".[dev]"`, `pm2 restart torrentmate-web`.
   - Post: `curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w
'%{http_code}' https://tm.iznogoudatall.xyz/api/health` → 401 or 200 = OK.
2. `scripts/deploy-staging.sh` — same for `~/staging/torrentmate` clone,
   restarts `torrentmate-web-staging` (port 8711).
3. Both scripts are idempotent, refuse dirty/unsynced trees.

**Verification**: `bash -n scripts/deploy.sh scripts/deploy-staging.sh`.

### 8.2 — Autodeploy poller + Caddy blocks + PM2 entries

**Commit**: `feat(tm-shell): add autodeploy poller and Caddy reverse-proxy config`

**Files**:

| Action | Path                                      |
| ------ | ----------------------------------------- |
| Create | `scripts/autodeploy-poll.sh`              |
| Modify | `ecosystem.config.js`                     |
| Create | `docs/features/tm-shell/caddy-blocks.txt` |
| Modify | `scripts/deploy-staging.sh` (pre-fix)     |
| Modify | `personalscraper/commands/web.py`         |
| Modify | `tests/indexer/test_ecosystem.py`         |
| Modify | `tests/web/test_web_cli.py`               |

**Work**:

1. `scripts/autodeploy-poll.sh` — 60 s loop (mirrors KanbanMate):
   - `git fetch origin <branch>` (timeout-wrapped); if `main` advanced →
     `git pull --ff-only` → `./scripts/deploy.sh`; if `staging` advanced →
     `git reset --hard origin/staging` (the staging clone follows the remote
     staging branch, which may be rebased / force-pushed) → `./scripts/deploy-staging.sh`.
   - Timestamped French log lines each cycle; `--once` flag; `AUTODEPLOY_INTERVAL`
     env; per-cycle fail-soft (one failed pass never kills the loop).
2. `ecosystem.config.js` — add `torrentmate-web-staging` (`web --port 8711`,
   autorestart, kill_timeout 30000, cwd `~/staging/torrentmate`, own venv) +
   `torrentmate-autodeploy` (runs `autodeploy-poll.sh`, autorestart,
   interpreter `/bin/bash`, restart_delay 60000).
3. `caddy-blocks.txt` — Caddyfile snippet per DESIGN §6; operator applies
   to `/opt/homebrew/etc/Caddyfile` manually, then `caddy reload`.

**Plan corrections (applied in 8.2, orchestrator-approved):**

- **Staging baked-commit pre-fix** (carried from 8.1 review): `deploy-staging.sh`
  baked `TM_BUILD_COMMIT="$sha"` while stamping `"branch @ sha"`, so the PWA
  reported a perpetual phantom update. Now bakes the identical `"branch @ sha"`.
- **`web --host/--port` overrides** (the ONE sanctioned source change): the web
  command gained optional `--host`/`--port` typer options so the staging clone can
  bind 8711 while sharing the single config dir (where `web.port` stays 8710 for
  prod). Config-native `local.json5` was unusable because the config dir is shared
  between clones (`PERSONALSCRAPER_CONFIG` → the same real config). `tests/web/test_web_cli.py`
  gains one override test.
- **Prod PM2 entry repointed to the deploy clone**: `torrentmate-web` now runs from
  `~/deploy/torrentmate` with its own venv (`~/deploy/torrentmate-venv`) and
  `PERSONALSCRAPER_CONFIG` → the canonical config dir (DESIGN §6, per-clone isolation).
  The DEV checkout stays runnable ad hoc via `personalscraper web`. One
  `ecosystem.config.js` file drives all clones' web apps; the pyenv-run daemons/crons
  keep `cwd: __dirname`. `tests/indexer/test_ecosystem.py` is updated accordingly
  (expected-apps list + deploy-clone cwd / non-python-interpreter exclusions).

**Verification**: `node -e "require('./ecosystem.config.js')"` parses; `bash -n`
on `autodeploy-poll.sh` + both deploy scripts; `pytest tests/indexer/test_ecosystem.py
tests/web`; `make lint`.

### 8.3 — Documentation deliverables + final gate

**Commit**: `docs(tm-shell): add web UI reference doc, CLAUDE.md row, and ACCEPTANCE`

> **⚠ ACC-NN wording note**: ACCEPTANCE (8.3) must use DESIGN §11 corrected wording:
> `/api/health` → 200 public (DESIGN §4.4 exempts it from the auth guard);
> `/api/version` → 401 unauthenticated (the guarded-route example).
> Never claim 401 for health in any ACC criterion.

**Files**:

| Action | Path                                   |
| ------ | -------------------------------------- |
| Create | `docs/reference/web-ui.md`             |
| Modify | `CLAUDE.md`                            |
| Modify | `.env.example`                         |
| Modify | `config.example/web.json5`             |
| Modify | `docs/features/tm-shell/ACCEPTANCE.md` |

**Work**:

1. `docs/reference/web-ui.md` — DESIGN §12: architecture, auth, WS protocol
   (message shapes, replay), deploy runbook, PWA notes, local dev setup, and the
   REST contract conventions binding S2–S7 (typed Pydantic→OpenAPI; **writes =
   POST acquiring the same `pipeline.lock` as the Watcher** — single trigger
   authority, DESIGN §4.6; `X-Requested-With` header rule).
2. `CLAUDE.md` — add Reference Index row linking to `docs/reference/web-ui.md`.
3. `.env.example` + `config.example/web.json5` — ensure documented and complete.
4. `ACCEPTANCE.md` — executable `ACC-NN` criteria from DESIGN §11 (corrected wording:
   health is 200 public per DESIGN §4.4; 401 applies to guarded routes like
   `/api/version`, not health):
   - `ACC-01`: web health 200 public (DESIGN §4.4 exempts /api/health from auth guard);
     guarded route (/api/version) 401 → login → 200.
   - `ACC-02`: `Set-Cookie: tm_session` HttpOnly SameSite=Strict.
   - `ACC-03`: WS receives XADD event, replays on reconnect with `last_id`.
   - `ACC-04`: `npx tsc --noEmit` exit 0, zero `no-explicit-any` in ESLint.
   - `ACC-05`: manifest + SW served from prod URL.
   - `ACC-06`: push main → autodeploy → PWA update toast.

**Verification**: `make lint && make test` all pass; `grep web-ui.md CLAUDE.md`
returns the row.

### 8.4 — Staging branch + Chrome MCP validation

**Commit**: `chore(tm-shell): create staging branch and validate via Chrome MCP`

**Work** (no source files; operational steps):

1. Create `staging` branch from `main` after merge.
2. `/chrome MCP` validation checklist: login flow (valid + invalid), live feed
   receives real event, install prompt visible (Android Chrome), iOS instruction
   sheet (Safari), SW update toast on redeploy, mobile viewport layout, StatusDot
   reflects WS state. Record results in `ACCEPTANCE.md`.
3. Post-merge operator runbook: `docs/reference/runbook-post-merge.md`.

## Verification

```bash
make lint && make test                                   # all pass
bash -n scripts/deploy.sh scripts/deploy-staging.sh scripts/autodeploy-poll.sh
node -e "require('./ecosystem.config.js')"                # valid PM2
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}' \
  https://tm.iznogoudatall.xyz/api/health                 # 200 (public, DESIGN §4.4)
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}' \
  https://tm.iznogoudatall.xyz/api/version                # 401 (prod guard active)
```

**Operator steps** (not committed): apply Caddy blocks → `caddy reload`; create
deploy clones with venvs; `pm2 start ecosystem.config.js && pm2 save`; run
`/chrome MCP` checklist.
