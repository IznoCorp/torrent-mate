# ACCEPTANCE — tm-shell — TorrentMate UI S1: Shell + Auth + WebSocket

**Feature**: TorrentMate web UI — wave S1
**Codename**: `tm-shell` · **Branch**: `feat/tm-shell`
**Design**: `docs/features/tm-shell/DESIGN.md`

> **Format rule** (see `docs/reference/feature-lifecycle.md` §2): every ACC-NN
> is an executable shell command with a documented expected output. Prose
> criteria are invalid.

---

### ACC-01 — Health endpoint public, version endpoint guarded

**Scope**: SH-01 (health public), SH-05 (auth guard perimeter)
**Precondition**: `personalscraper web` is running on `127.0.0.1:8710`.

```bash
# Health is PUBLIC — no auth required (DESIGN §4.4).
curl -s -o /dev/null -w '%{http_code}' \
  --connect-timeout 10 --max-time 30 \
  http://127.0.0.1:8710/api/health
# Expected: 200

# Version is GUARDED — unauthenticated → 401.
curl -s -o /dev/null -w '%{http_code}' \
  --connect-timeout 10 --max-time 30 \
  http://127.0.0.1:8710/api/version
# Expected: 401
```

**Status**: 🟡 DEFERRED — `/api/version` guarded path re-verified post-deploy (prod URL).
Local equivalent above is runnable now.

---

### ACC-02 — Login sets HttpOnly SameSite=Strict session cookie

**Scope**: SH-02 (auth cookie attributes)
**Precondition**: `personalscraper web` is running on `127.0.0.1:8710`.
**⚠ Rate limit**: login is capped at 5 failures per 60 s — do not run this
criterion in a loop or with wrong credentials.

```bash
# Login and capture the Set-Cookie header.
# Replace <password> with the real password set via `personalscraper web set-password`.
curl -s -o /dev/null -D - \
  --connect-timeout 10 --max-time 30 \
  -X POST http://127.0.0.1:8710/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"izno","password":"<password>"}' \
  | grep -i 'set-cookie:'
# Expected: a single line containing:
#   Set-Cookie: tm_session=<jwt>; HttpOnly; ... SameSite=strict; ...
# (HttpOnly, SameSite=strict, and Path=/ are present; Secure depends on cookie_secure config.)
```

**Status**: 🟡 DEFERRED — full cookie-attribute assertion re-verified post-deploy
(prod cookie_secure=true). Local equivalent (cookie_secure=false) is runnable now
and confirms HttpOnly + SameSite=strict + Path=/.

---

### ACC-03 — WebSocket receives events and replays on reconnect

**Scope**: SH-03 (WS event delivery), SH-04 (replay protocol)
**Precondition**: `personalscraper web` is running, Redis is available, and the
`tm_session` cookie from a successful login is available.

```bash
# The executable proof is the E2E smoke test (marked @pytest.mark.e2e).
# It boots the web server against a fakeredis-backed stream, logs in via
# TestClient, opens a WS connection, publishes an event via XADD, asserts
# it is received, then reconnects with ?last_id= and asserts replay.
cd /Users/izno/dev/PersonalScraper && \
  python -m pytest tests/e2e/test_web_smoke.py -m e2e -v
# Expected: passed (the test asserts all WS message shapes, replay, and the
# _ReplayGuard dedup behaviour).
```

**Status**: SHIPPED — E2E smoke test passes (tests/e2e/test_web_smoke.py).

---

### ACC-04 — Frontend typecheck and lint clean

**Scope**: SH-06 (TypeScript strict, zero `any`)
**Precondition**: Node 22 and `frontend/node_modules/` installed (`cd frontend && npm ci`).

```bash
cd /Users/izno/dev/PersonalScraper/frontend && npx tsc --noEmit
# Expected: exit code 0 (no type errors)

cd /Users/izno/dev/PersonalScraper/frontend && npm run lint
# Expected: exit code 0, output ends with "0 errors" or "0 problems", and
# no-explicit-any violations are counted as errors (not warnings).
```

**Status**: SHIPPED — CI frontend job enforces both gates (`tsc --noEmit` +
`eslint` with `no-explicit-any: error`).

---

### ACC-05 — PWA manifest and service worker served at static root

**Scope**: SH-07 (PWA shell assets)
**Precondition**: `personalscraper web` is running on `127.0.0.1:8710` with a
built SPA in `personalscraper/web/static/`.

```bash
# Manifest — must return 200 with the correct content type.
curl -s -o /dev/null -w '%{http_code} %{content_type}' \
  --connect-timeout 10 --max-time 30 \
  http://127.0.0.1:8710/manifest.webmanifest
# Expected: 200 application/manifest+json

# Service worker — must return 200 with a javascript content type.
curl -s -o /dev/null -w '%{http_code} %{content_type}' \
  --connect-timeout 10 --max-time 30 \
  http://127.0.0.1:8710/sw.js
# Expected: 200 (content_type is one of: application/javascript, text/javascript)
```

**Status**: 🟡 DEFERRED — full manifest icons + maskable validation deferred to
post-deploy `/chrome` MCP checklist. Local equivalent above confirms both files
are served with correct content types.

---

### ACC-06 — Push main → autodeploy → PWA update toast

**Scope**: SH-08 (autodeploy), SH-09 (PWA update convergence)
**Precondition**: deploy clones exist at `~/deploy/torrentmate` and
`~/staging/torrentmate` with their venvs; PM2 apps are defined;
`torrentmate-autodeploy` poller is running.

```bash
# Part A: deploy.sh stamps BUILD_COMMIT with the served SHA.
# After deploy.sh runs, BUILD_COMMIT must match the deployed commit.
grep -q "$(git -C ~/deploy/torrentmate rev-parse --short HEAD)" \
  ~/deploy/torrentmate/personalscraper/web/static/BUILD_COMMIT \
  && echo "match" || echo "MISMATCH"
# Expected: match

# Part B: /api/version build_commit matches git rev-parse --short HEAD
# on the prod clone (post-deploy).
curl -s --connect-timeout 10 --max-time 30 \
  -b "tm_session=<valid-session-token>" \
  http://127.0.0.1:8710/api/version | python3 -c "import sys,json; print(json.load(sys.stdin)['build_commit'])"
# Expected: the short SHA of the deployed commit on the prod clone's HEAD

# Part C: the PWA update-toast path is covered by frontend unit tests.
cd /Users/izno/dev/PersonalScraper/frontend && \
  npm run test -- --run usePwa 2>&1 | tail -3
# Expected: all tests pass (the suite covers needRefresh → toast →
# updateServiceWorker(true), version-poll-driven registration.update(),
# and equal-commit no-op).
```

**Status**: 🟡 DEFERRED — full push→autodeploy→toast end-to-end deferred to
post-deploy (requires prod URL + real PWA install on a device). Parts A and C
are runnable locally now; Part B requires a valid session cookie.

---

## `/chrome` MCP validation (Phase 8.4)

Recorded live against a real server (real config, real Redis, real `.env`
KanbanMate-aligned credentials) on `127.0.0.1:8710`, served build `cc9326ba`
(cookie_secure=false for http localhost; prod sits behind Caddy TLS).

| Check                                                                                         | Result                         |
| --------------------------------------------------------------------------------------------- | ------------------------------ |
| Login form renders (DS wordmark, FR copy, logo)                                               | ✅                             |
| Invalid credentials → « Identifiants invalides » (red, no enumeration)                        | ✅                             |
| Authenticated dashboard (health cards, version, feed)                                         | ✅ (via minted session cookie) |
| Health cards **green** — Redis en ligne + Base indexée (no false-alarm red while pending)     | ✅ (B8)                        |
| Version card `0.40.0` · `commit cc9326b` (monospace)                                          | ✅                             |
| Live feed receives real XADD events                                                           | ✅                             |
| Warning event → `WRN` + **static** amber dot (`ps-dot--warning`, never `running`)             | ✅ (B9)                        |
| Error event → `ERR` + red dot                                                                 | ✅                             |
| Neutral event → static `idle` dot                                                             | ✅                             |
| Envelope-only XADD resolves the real event type (not « unknown »)                             | ✅ (envelope `_type` fix)      |
| Service worker registers + **activated**, workbox precache, controller                        | ✅ (prompt-mode build)         |
| `/sw.js`, `/manifest.webmanifest` served at static root (correct mime)                        | ✅                             |
| Install banner « Installer TorrentMate » + dismiss persists across reload                     | ✅                             |
| Responsive: desktop sidebar `md:flex md:w-56` / mobile bottom-bar `md:hidden` + iOS safe-area | ✅ (breakpoint classes)        |
| User menu shows login `izno` + « Se déconnecter »                                             | ✅                             |
| Logout → cookie cleared → `/login?redirect=%2F`                                               | ✅                             |

Deferred to post-deploy (require the prod URL / a real device): manifest icon +
maskable rendering, the push→autodeploy→update-toast end-to-end, and iOS/iPadOS
add-to-home-screen sheet. See `docs/reference/runbook-post-merge.md` §7.

---

## Re-exercise Log

| Date       | Phase / Gate                      | ACC-01 | ACC-02 | ACC-03 | ACC-04 | ACC-05 | ACC-06                   | Operator           |
| ---------- | --------------------------------- | ------ | ------ | ------ | ------ | ------ | ------------------------ | ------------------ |
| 2026-07-05 | Phase 8.3                         | ✅     | ✅     | ✅     | ✅     | ✅     | 🟡                       | LounisBou          |
| 2026-07-05 | Phase 8.4 (guarantor re-exercise) | ✅     | ✅     | ✅     | ✅     | ✅     | 🟡 A+C local, B deferred | Claude (guarantor) |
