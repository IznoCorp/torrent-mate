# DESIGN — tm-shell — TorrentMate UI S1: Shell + Auth + WebSocket foundation

**Feature**: TorrentMate web UI — wave S1 (shell + auth + WebSocket + headless serving)
**Ticket**: #158 (KanbanMate board, claimed)
**Codename**: `tm-shell` · **Branch**: `feat/tm-shell` · **Bump**: minor `0.39.0 → 0.40.0`
**Date**: 2026-07-04 · **Status**: draft (pending operator review)
**Depends on (shipped)**: EventBus (`core/event_bus.py`), envelope serializers, `AppContext`
composition root, `watch` daemon command pattern. No HTTP server exists today — S1 is net-new.

---

## 0. Cross-cutting brief — S1→S7 (operator-mandated, DO NOT FORGET)

These constraints bind **every** web-UI wave (S1–S7), not just S1. Recorded here and in
agent memory (`project_torrentmate_ui_epic_brief`) so later waves conform.

1. **Naming**: `personalscraper` is a **code name** (the engine/package). The app is
   **TorrentMate**; the frontend is referenced as **TorrentMateUI**. All UI branding says
   TorrentMate.
2. **Stack (frozen)**: FastAPI backend · React + Vite frontend · **TypeScript strict, zero
   `any`** · **shadcn/ui** + the provided design system (`docs/design/PersonalScraper Design
System.zip`) · **TanStack** Query / Table / Form / Virtual.
3. **PWA**: installable on **Android AND iOS**, **mobile-first** (desktop supported).
   Automatic version management: new deploy → all installed clients auto-detect, clear caches,
   and update. The app itself proposes installation.
4. **Events transport**: **Redis** (already running via Homebrew) bridges the in-process
   EventBus to the web process; WebSocket fans out to clients with replay-on-reconnect.
5. **Auth**: app login + JWT session cookie (HTTP-only). Guard on REST **and** WebSocket.
   Single user; multi-user out of scope but the seam stays open.
6. **Write authority**: any future write action (S2 start/kill…) goes through the **same
   `pipeline.lock`** as the Watcher — single trigger authority, EventBus stays observe-only.
7. **Deploy**: mirror **KanbanMate's model** — prod `tm.iznogoudatall.xyz` autodeploys on push
   to `main`; staging `tm-staging.iznogoudatall.xyz` autodeploys on push to `staging`; Caddy
   reverse-proxy blocks for both; PM2-managed processes; `BUILD_COMMIT` stamping.
8. **Front testing convention**: every front feature is exercised with the **`/chrome` MCP**
   (claude-in-chrome) in addition to unit tests.
9. **S1 lays the full foundation**: S2–S7 add endpoints + pages **on these rails only** —
   no per-wave re-architecture.

> Ticket hygiene: waves S2 (#181), S3 (#182), S4 (#183) and later S5–S7 tickets must be
> annotated with this brief once S1's spec is committed (see §13).

---

## 1. Context

- The engine is a **fully synchronous**, single-process-per-command Python 3.12 codebase
  (typer CLI). There is **no HTTP server, no async stack, no web dependency** today.
- The **EventBus** (`personalscraper/core/event_bus.py`) is in-process, sync, with envelope
  serializers (`event_to_envelope` / `event_from_envelope`) designed for cross-process
  consumers. `docs/reference/event-bus.md` §"Future evolution" already names the
  `WebSocketSubscriber` as "Phase 1 of the future Web UI".
- The pipeline (`run`), the Watcher (`watch`), and CLI jobs run in **separate processes**
  from any web server → events must cross process boundaries (hence Redis).
- `AppContext` (`core/app_context.py`) is the composition root and explicitly anticipates a
  "future Web UI boot". Boundary rule: only boundary modules receive the whole context.
- Deployment substrate on IznoServer: **PM2** + **Caddy** (`/opt/homebrew/etc/Caddyfile`),
  no Docker. Redis runs as `homebrew.mxcl.redis` (localhost:6379).
- A complete **design system** ships in `docs/design/PersonalScraper Design System.zip`:
  shadcn-compatible token layer (dark-first, amber-on-near-black, Geist/Geist Mono, Lucide),
  domain primitives (PipelineStepper, DiskUsageBar, LogLine, StatusDot, RatioGauge,
  StatPanel, TemperatureBadge, MediaPoster), a supervision-shell template, an adherence
  oxlint config, and logo assets. Copy rules: French-leading, monospaced numbers, emoji
  only for the 🔥🌤❄️⛔ cadence.

## 2. Goals (S1 scope)

1. **Headless serving**: a `personalscraper web` daemon command (uvicorn + FastAPI) serving
   the built TorrentMateUI SPA + REST API + WebSocket, PM2-managed, behind Caddy.
2. **Auth**: login screen → JWT session cookie; guard on all API routes and the WS handshake.
3. **Real-time channel**: EventBus → Redis → WebSocket relay with replay-on-reconnect,
   proven end-to-end with the existing event catalog.
4. **App shell**: mobile-first layout, navigation slots for S2–S7, login flow, dashboard
   home page proving each foundation (live event feed, health/version cards).
5. **PWA**: installable (Android + iOS), auto-update with cache busting across all installs.
6. **Typed contract**: Pydantic → OpenAPI → generated TS types → TanStack Query hooks;
   typed WS event union. Zero `any`.
7. **Deploy rails**: prod/staging clones, deploy scripts, autodeploy poller, Caddy blocks,
   CI jobs (front + back).

### Non-goals (deferred to their waves)

- Pipeline control actions (S2), maintenance dashboards (S3), config editor (S4),
  interactive scraping (S5), registry/health panel (S6), acquisition pages (S7).
- Multi-user, remote agent control, push notifications, offline data access (PWA caches the
  shell, not the data), i18n framework (copy is French-leading directly).

## 3. Architecture overview

```
┌─────────────── producer processes (unchanged, sync) ───────────────┐
│ personalscraper run / watch / grab / …                             │
│   EventBus ──> RedisEventPublisher (new subscriber, fail-soft)     │
│                   └── XADD envelope → Redis Stream                 │
└────────────────────────────────────────────────────────────────────┘
                                   │ Redis Stream `personalscraper:events`
                                   ▼ (MAXLEN ~10k, ids = replay cursor)
┌─────────────── web process — `personalscraper web` ────────────────┐
│ uvicorn (async)                                                    │
│  FastAPI app (personalscraper/web/)                                │
│   ├─ /api/auth/*  /api/health  /api/version   (REST, Pydantic)     │
│   ├─ /ws/events   (auth-guarded; tail stream → fan-out + replay)   │
│   └─ static: TorrentMateUI build (SPA fallback) + BUILD_COMMIT     │
└────────────────────────────────────────────────────────────────────┘
                                   ▲ Caddy: tm.iznogoudatall.xyz (prod :8710)
                                   ▲        tm-staging.iznogoudatall.xyz (staging :8711)
Clients: browser / installed PWA (Android, iOS, desktop)
```

Only the WS relay is async; REST handlers are plain `def` (FastAPI runs them in its
threadpool), calling the sync domain directly. The sync engine is never imported into async
code paths beyond that boundary.

## 4. Backend design

### 4.1 Package layout (new boundary package)

```
personalscraper/web/
  __init__.py
  app.py            # create_app(config, settings) → FastAPI (mounts routers + static)
  deps.py           # auth dependency, settings/config accessors
  auth/
    routes.py       # POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me
    tokens.py       # JWT encode/decode (PyJWT HS256, exp)
    passwords.py    # stdlib hashlib.scrypt hash/verify (format: scrypt$N$r$p$salt$hash)
  ws/
    relay.py        # Redis stream tail (redis.asyncio) + connection registry + fan-out
    routes.py       # GET /ws/events (handshake guard, replay from ?last_id=)
  routes/
    health.py       # GET /api/health (app up, redis reachable, db paths present)
    version.py      # GET /api/version ({version, build_commit})
  static.py         # SPA mount + index.html fallback; reads static/BUILD_COMMIT
  static/           # gitignored — Vite build output lands here (à la KanbanMate webui/)
personalscraper/commands/web.py        # typer: `web` (daemon) + `web set-password`
personalscraper/subscribers/redis_stream.py  # RedisEventPublisher (producer side)
```

Respect the module-size budget (≤800 LOC soft) — the split above keeps every file small.

### 4.2 `personalscraper web` command

- Patterned on `commands/watch.py` (daemon, SIGTERM/SIGINT graceful shutdown).
- Builds the context via `_build_app_context(config, settings)` (no torrent client),
  then `uvicorn.run(create_app(...), host=web.host, port=web.port)`.
- `personalscraper web set-password`: prompts for username/password, prints (and can write)
  the `.env` lines `WEB_PASSWORD_HASH=…` + a generated `WEB_JWT_SECRET` if absent.
- PM2 apps (added to `ecosystem.config.js` for the dev box; deploy clones get their own):
  `torrentmate-web` (autorestart, kill_timeout, PYTHONUNBUFFERED, like `watch`).

### 4.3 Config & secrets

- New overlay **`config/web.json5`** (+ `config.example/web.json5`), model
  `conf/models/web.py` (`extra='forbid'`):
  ```json5
  {
    web: {
      enabled: true,
      host: "127.0.0.1",
      port: 8710, // staging clone overrides to 8711 via local.json5
      username: "izno",
      redis_url: "redis://127.0.0.1:6379/0",
      stream_key: "personalscraper:events",
      stream_maxlen: 10000,
      session_ttl_hours: 720, // 30 days
      cookie_secure: true,
      dev_mode: false, // true = allow boot without a built SPA (Vite dev proxy)
    },
  }
  ```
- **Secrets** in `.env` via `Settings` (`personalscraper/config.py`): `WEB_PASSWORD_HASH`,
  `WEB_JWT_SECRET` (both added to `_SECRET_FIELDS` masking + `.env.example`).
- No new-schema migration concerns (<1.0.0 rule: config evolves with the code).

### 4.4 Auth

- `POST /api/auth/login {username, password}` → verify scrypt hash (constant-time compare)
  → JWT HS256 `{sub, iat, exp}` → **cookie `tm_session`**: `HttpOnly; SameSite=Strict;
Secure; Path=/`. Response 204. Wrong creds → 401 (+ small constant delay).
- `POST /api/auth/logout` → clears cookie. `GET /api/auth/me` → `{username}`.
- **Guard**: FastAPI dependency `require_session` on every `/api/*` router except
  login/health-of-login; WS handshake reads the same cookie, closes `4401` if invalid.
- CSRF posture: same-origin SPA + `SameSite=Strict` + JSON-only bodies. S2+ mutating routes
  will additionally require the `X-Requested-With: TorrentMateUI` header (rule recorded now).
- Seam for later: credential lookup + claims live behind `auth/tokens.py`/`passwords.py`
  helpers — multi-user would swap the lookup, not the guard.

### 4.5 Event relay — Redis **Streams** (operator: "Redis direct")

Pub/sub alone cannot replay; **Redis Streams** give both transport and the reconnect
cursor natively — this is the retained mechanism (still plain Redis).

- **Producer** (`subscribers/redis_stream.py`): `RedisEventPublisher(event_bus, web_config)`
  subscribes to base `Event`, serializes with `event_to_envelope`, and `XADD`s
  `{"envelope": json, "type": _type}` to `stream_key` with `MAXLEN ~ stream_maxlen`.
  - **Fail-soft contract** (same as Telegram): Redis down → warn once
    (`redis_publish_failed`), drop events, never break the pipeline.
  - **Fast-subscriber contract**: enqueue to an in-memory queue; a daemon worker thread
    performs the XADDs (the bus has no async offload — subscribers must be fast).
  - Wired in the same boundary sites that build other subscribers
    (`commands/pipeline.py`, `commands/watch.py`, acquisition jobs), gated on
    `config.web.enabled`.
- **Web side** (`ws/relay.py`): one `redis.asyncio` reader task per process
  (`XREAD BLOCK` from `$`), fanning out to all connected WebSockets. On client connect
  with `?last_id=<stream-id>`: `XRANGE (last_id, +]` replays missed entries first, then
  live. No client cursor → live-only from now.
- **WS message shape** (typed, mirrored in TS):
  `{"id": "<stream-id>", "type": "<EventClass>", "data": {…}}` plus
  `{"type": "ws.hello", "data": {build_commit}}` on connect and `{"type": "ws.ping"}`
  every 30 s (client replies `pong`; missed pings → reconnect with backoff).
- S1 proves the pipe with the existing catalog (pipeline lifecycle, indexer, acquire
  events…); S2–S7 subscribe to the types they need client-side.

### 4.6 REST contract conventions (binding for S2–S7)

- Every route: Pydantic request/response models → OpenAPI. **`make openapi`** exports
  `frontend/openapi.json` (committed); `openapi-typescript` generates
  `frontend/src/api/schema.d.ts`; CI fails on drift (regenerate + `git diff --exit-code`).
- Reads = `GET` (sync `def` handlers). Writes (S2+) = `POST` and **must acquire
  `pipeline.lock`** (single trigger authority) — recorded now, no write routes in S1.
- Errors: RFC-ish `{detail}` with proper status codes; 401 everywhere unauthenticated.

### 4.7 Static serving & build stamp

- Vite build output is written to `personalscraper/web/static/` (gitignored, emptyOutDir)
  by the deploy scripts; `BUILD_COMMIT` file stamped next to it (à la KanbanMate).
- FastAPI mounts `/assets`, serves `index.html` for any non-`/api`/`/ws` path (SPA
  fallback). `/api/version` returns `{version: personalscraper.__version__, build_commit}`.
- `personalscraper web` refuses to start (clear error) if `static/index.html` is missing
  and `web.dev_mode` is false — prevents serving a half-deployed app.

### 4.8 New dependencies

Runtime: `fastapi`, `uvicorn[standard]` (includes websockets), `redis`, `PyJWT`.
Dev: `httpx` (TestClient), `fakeredis` (streams-capable, for relay tests).
Password hashing uses **stdlib** `hashlib.scrypt` — no extra dep.

## 5. Frontend design — TorrentMateUI

### 5.1 Scaffold

- **`frontend/`** at repo root: Vite + React 19 + **TypeScript strict**. `tsconfig`:
  `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitReturns`,
  `noFallthroughCasesInSwitch`. ESLint (`typescript-eslint`): `no-explicit-any` +
  `no-unsafe-*` = **error**, `ban-ts-comment` (description required). Node 22.
- Tailwind v4 + **shadcn/ui** (New York, Neutral, CSS variables) + the DS token layer
  copied to `frontend/src/styles/ps/` (import once). DS adherence oxlint config wired
  into `npm run lint:ds`.
- Domain primitives ported from the DS specs (`.d.ts` + `.jsx` references) into
  `src/components/ds/`: S1 ports **StatusDot, LogLine, StatPanel** (used by the shell/
  dashboard); the rest (PipelineStepper, DiskUsageBar, RatioGauge, TemperatureBadge,
  MediaPoster) are ported by the waves that use them, following the same recipe.
- Lucide icons; Geist/Geist Mono per DS (vendored woff2 for offline PWA use).

### 5.2 App shell & navigation

- From the DS `templates/supervision-shell/`: **mobile-first** — bottom tab bar (< md),
  collapsible sidebar (≥ md); top bar with TorrentMate wordmark, **StatusDot** for WS
  connection state, user menu (logout).
- React Router: `/login` (public) + protected layout with routes `/` (dashboard) and
  declared-but-stubbed slots for S2–S7 (`/pipeline`, `/maintenance`, `/config`,
  `/scraping`, `/registry`, `/acquisition` → "à venir" placeholder pages so navigation
  and gating exist from day one).
- Copy French-leading, numbers `font-mono tabular-nums`, emoji only 🔥🌤❄️⛔.

### 5.3 Data layer

- **TanStack Query** client: typed `fetcher<Path>` built on the generated OpenAPI types;
  cookie auth (`credentials: 'include'`); global 401 handler → redirect `/login`.
- **`useEventStream`**: WebSocket hook — connects `/ws/events?last_id=<persisted>`,
  narrows messages through the shared **discriminated union** (`src/api/events.ts`,
  mirroring the Python catalog), persists last stream id (localStorage), reconnect with
  exponential backoff, exposes connection state for the StatusDot.
- Reference usages proving each foundation (dashboard page):
  - **TanStack Virtual**: live event feed (LogLine rows, 60 fps on long histories).
  - **TanStack Table**: recent-events table (typed columns, sort).
  - **TanStack Form**: the login form (+ zod validation adapter).

### 5.4 PWA (installable, auto-updating)

- `vite-plugin-pwa` (Workbox): manifest **TorrentMate** (name, theme `#0b0a08`-ish DS
  background, icons generated from DS `logo-icon.svg` incl. maskable + apple-touch),
  `registerType: 'autoUpdate'`, precache = app shell only; `/api` + `/ws` are
  NetworkOnly (never cached).
- **Update discipline** (all installs converge): SW update checks on load, on
  `visibilitychange`, and every 15 min; additionally `/api/version` is polled and compared
  to the baked `__BUILD_COMMIT__` — any mismatch forces `registration.update()`. New SW →
  `skipWaiting` + `clients.claim` + old caches deleted → toast « Nouvelle version
  installée — rechargement… » → auto reload. No stale clients.
- **Install proposal**: Android/desktop — capture `beforeinstallprompt`, surface an
  in-app « Installer TorrentMate » button/banner; iOS Safari — detect
  (`navigator.standalone === false` + iOS UA) and show the Partager → « Sur l'écran
  d'accueil » instruction sheet. Dismissals are remembered.

## 6. Deploy — prod/staging à la KanbanMate

- **Clones**: `~/deploy/torrentmate` (prod, tracks `main`) and `~/staging/torrentmate`
  (staging, tracks `staging`), each with its **own venv** (isolation from the dev editable
  install — avoids the stale-editable-finder incident class) and a symlinked `.env` →
  canonical. `PERSONALSCRAPER_CONFIG=/Users/izno/dev/PersonalScraper/config` in the PM2
  env so both serve the **real** config/data (KanbanMate "no test board" rule; S1 is
  read-only so staging against real data is safe).
- **`scripts/deploy.sh`** (prod): refuses unless clean `main` == `origin/main`; `cd
frontend && npm ci && npm run build` → `personalscraper/web/static/` + `BUILD_COMMIT`
  stamp; `pip install -e .`; `pm2 restart torrentmate-web`.
- **`scripts/deploy-staging.sh`**: same, but serves the staging clone's current branch
  (committed code only), restarts `torrentmate-web-staging` (port 8711).
- **`scripts/autodeploy-poll.sh`**: PM2 app `torrentmate-autodeploy` (60 s loop) — prod
  ⟵ `main` advanced → deploy.sh; staging ⟵ `staging` advanced → deploy-staging.sh.
- **Caddy** (`/opt/homebrew/etc/Caddyfile`, operator-applied):
  ```caddy
  https://tm.iznogoudatall.xyz {           # prod
      import tls_config
      reverse_proxy localhost:8710
  }
  https://tm-staging.iznogoudatall.xyz {   # staging
      import tls_config
      reverse_proxy localhost:8711
  }
  ```
  (WebSocket proxying is native in Caddy `reverse_proxy`.) DNS records for `tm` /
  `tm-staging` = operator step.
- A `staging` branch is created from `main` at feature completion.

## 7. CI additions

Extend `.github/workflows/ci.yml`:

- **`frontend` job** (node 22): `npm ci` → `tsc --noEmit` (strict gate) → `eslint`
  (no-any gate) + `lint:ds` → `vitest run` → `vite build` (build must pass).
- **OpenAPI drift check**: regenerate schema + `git diff --exit-code frontend/openapi.json
frontend/src/api/schema.d.ts`.
- Python jobs unchanged (web backend tests ride the existing `test` job; coverage gate 90%
  applies to `personalscraper/web/`).

## 8. Testing strategy

- **Backend (pytest)**: FastAPI `TestClient` — auth flow (login/logout/me, bad creds,
  cookie attributes), guard coverage on REST + WS handshake, health/version, static
  fallback; relay unit tests with `fakeredis` (XADD → fan-out, replay from `last_id`,
  MAXLEN); `RedisEventPublisher` fail-soft + envelope round-trip
  (`event_from_envelope(event_to_envelope(e))`). CLI tests patch `load_config`
  (CI has no `config/`).
- **Frontend (vitest + RTL)**: login form validation + 401 redirect, `useEventStream`
  (mock WS: hello/replay/reconnect/backoff), shell navigation + gating, update-toast logic.
- **`/chrome` MCP (convention)**: manual-but-scripted validation of each front feature —
  S1 checklist: login, live feed receiving a real event, install prompt visible, SW
  update toast on redeploy, mobile viewport layout.
- **E2E smoke (marked, local)**: boot `personalscraper web` against a temp config +
  fakeredis-backed stream, curl login → WS receives a published event.

## 9. Risks & mitigations

| Risk                                                                | Mitigation                                                                                                                                                          |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Redis down → no live events                                         | Producer fail-soft (never breaks pipeline); web `/api/health` reports `redis: down`; UI shows a degraded banner; WS stays connected (pings only).                   |
| iOS PWA limitations (no `beforeinstallprompt`, SW eviction)         | Dedicated iOS instruction sheet; app fully functional in browser tab; shell-only precache keeps storage tiny.                                                       |
| Async/sync mixing bugs                                              | Async confined to `ws/relay.py`; REST handlers are sync `def`; architecture test asserts no `personalscraper.web` import from engine packages (one-way dependency). |
| Deploy clone drift (stale editable installs — known incident class) | Per-clone venvs; `BUILD_COMMIT` + `/api/version` make "what is live" verifiable; deploy scripts refuse dirty/unsynced trees.                                        |
| Secrets exposure via public domain                                  | HTTPS-only (Caddy TLS), HttpOnly Secure cookies, constant-time verify + login delay, no user enumeration.                                                           |
| Coverage gate (90%) on new web code                                 | web/ designed for testability (pure helpers, DI via `create_app(config, settings)`); fakeredis + TestClient keep tests hermetic.                                    |

## 10. Suggested phase seams (input to the planner)

1. Backend skeleton: `web/` package, config/web.json5 + Settings fields, `create_app`,
   health/version, static serving, `web` command + PM2 (dev box).
2. Auth: passwords/tokens/guard/routes + `web set-password` + tests.
3. Event relay: `RedisEventPublisher` (+ producer wiring) → `ws/relay.py` + `/ws/events`
   (replay protocol) + tests.
4. Frontend scaffold: Vite/TS-strict/ESLint/shadcn/DS tokens/oxlint + typed API client
   (OpenAPI export + generation) + CI front job.
5. Shell + auth flow + dashboard (Query/Table/Form/Virtual references + `useEventStream`).
6. PWA: manifest/SW/auto-update/install prompts.
7. Deploy rails: scripts + autodeploy + Caddy + staging branch + `/chrome` validation +
   docs (`docs/reference/web-ui.md`, CLAUDE.md index row, README note).

## 11. Acceptance criteria (sketch — final ACC as executable commands per convention)

- `personalscraper web` boots; `curl --connect-timeout 10 --max-time 30 -s -o /dev/null
-w '%{http_code}' http://127.0.0.1:8710/api/health` → `401` unauthenticated; `200`
  with a valid session cookie.
- Login via curl returns `Set-Cookie: tm_session=…; HttpOnly; …SameSite=Strict`.
- A published test event (XADD) is received on an authenticated `/ws/events` connection;
  reconnecting with `last_id` replays it.
- `cd frontend && npx tsc --noEmit` → exit 0; ESLint reports zero `no-explicit-any`.
- `https://tm.iznogoudatall.xyz` serves the SPA with valid manifest + registered SW
  (validated via `/chrome` MCP); `https://tm-staging.iznogoudatall.xyz` serves the
  staging branch's `BUILD_COMMIT`.
- Push to `main` → prod redeploys (autodeploy log) and installed PWA shows the update
  toast + reloads onto the new `BUILD_COMMIT`.

## 12. Documentation deliverables

- `docs/reference/web-ui.md` — architecture, auth, WS protocol, deploy runbook, PWA notes.
- CLAUDE.md Reference-Index row ("Web UI / TorrentMate…" → that doc).
- `.env.example` + `config.example/web.json5` updated.

## 13. Ticket updates (operator-requested)

After this spec lands on the branch, annotate the wave tickets so the brief is durable on
the board: **#181 (S2), #182 (S3), #183 (S4)** and the S5/S6/S7 tickets (ids to look up on
the board) with: stack (FastAPI + React/TS-strict/shadcn/TanStack + DS), rails delivered by
S1 (typed REST convention, WS event stream + replay, auth guard, shell nav slot, PWA,
deploy model), and the invariants (writes via `pipeline.lock`, `/chrome` MCP testing,
TorrentMate naming).
