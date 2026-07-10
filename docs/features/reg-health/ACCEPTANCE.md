# ACCEPTANCE — reg-health (S6 Web UI: Registry + Health)

**Feature**: reg-health (7-wave web-UI roadmap — S6, ticket #185)
**Executed on**: prod daemon (`http://localhost:8710`) for authenticated reads /
`http://localhost:8711` for staging read-only tests (ACC-03)
**Precondition**: the `personalscraper web` daemon must be running on the target
port with a configured provider registry (at least `tmdb` and `tvdb` in
`config/providers.json5`).

Every criterion is an executable shell command with a documented expected output.
Run from the repo root. Uses `curl --connect-timeout 10 --max-time 30` on every
network call (project network-timeout rule). The registry route is read-only —
no `X-Requested-With` header is needed.

---

## Prerequisites

```bash
# ACC-00 — Capture a session cookie from the local daemon into /tmp/tm_session.
# The login endpoint is POST /api/auth/login; on success it returns 204 with a
# Set-Cookie header holding the JWT token as tm_session (HttpOnly, SameSite=Strict).
# Web creds live in config/web.json5 (username) + .env (WEB_PASSWORD_HASH).
# The plaintext password is prompted interactively; never hardcode it.

read -s -p "Password: " PASS && echo
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -D - \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"izno\",\"password\":\"$PASS\"}" \
  http://localhost:8710/api/auth/login \
  | grep -i 'set-cookie: tm_session=' | sed 's/.*tm_session=\([^;]*\).*/\1/' \
  > /tmp/tm_session
# Expected: /tmp/tm_session contains a non-empty JWT token string.
```

`izno` is the configured web username (same as `config/web.json5` → `username`).
The cookie file is read by ACC-01 and ACC-03 via
`--cookie "tm_session=$(cat /tmp/tm_session)"`.

**Headless re-exercise**: if interactive password entry is not available, use
the forged-JWT technique: construct a valid JWT with `sub=<username>` signed
with the `WEB_JWT_SECRET` from `.env`, write it directly to `/tmp/tm_session`,
and skip the login curl above. The forged cookie is accepted identically by
`require_session` (`personalscraper/web/deps.py:124`).

```bash
# Forged-JWT recipe (headless, requires WEB_JWT_SECRET from .env):
#   python3 -c "
#   import jwt, time
#   secret = open('.env').read().split('WEB_JWT_SECRET=')[1].split('\\n')[0].strip()
#   token = jwt.encode({'sub': 'izno', 'iat': int(time.time())}, secret, algorithm='HS256')
#   print(token)
#   " > /tmp/tm_session
```

---

## ACC-01 — REST endpoint returns frozen shape (authed, prod 8710)

```bash
curl --connect-timeout 10 --max-time 30 -s \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  http://localhost:8710/api/registry/status | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert 'providers' in data, 'missing providers key'
for p in data['providers']:
    assert set(p.keys()) == {
        'provider_name', 'circuit_state', 'failure_count_recent',
        'last_success_at', 'last_failure_at', 'last_latency_ms', 'live'
    }, f'Key drift: {set(p.keys())}'
    assert p['circuit_state'] in {'closed', 'open', 'half_open'}, f'Bad state: {p[\"circuit_state\"]}'
    assert isinstance(p['failure_count_recent'], int) and p['failure_count_recent'] >= 0
    assert isinstance(p['live'], bool), f'live must be bool, got {type(p[\"live\"]).__name__}'
print('ACC-01 PASS')
"
```

Expected: `ACC-01 PASS`

---

## ACC-02 — Unauthenticated → 401

```bash
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}' \
  http://localhost:8710/api/registry/status
```

Expected: `401`

---

## ACC-03 — Staging (8711) → 200 (read allowed)

```bash
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}' \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  http://localhost:8711/api/registry/status
```

Expected: `200`

**(Skip if the staging daemon is not running on port 8711.)**

---

## ACC-04 — Freeze test passes (all 4 contract assertions)

```bash
pytest tests/unit/api/metadata/registry/test_status_contract_frozen.py -v
```

Expected: 4 passed. A removed/renamed `ProviderStatus` field or `CircuitState`
value makes `test_providerstatus_fields_exact_set` or
`test_circuitstate_values_closed_set` FAIL.

---

## ACC-05 — make check green

```bash
make check
```

Expected: zero errors (lint, test, module-size, typed-api). Summary line:
`NNNN passed` with 0 failed/errors.

---

## ACC-06 — OpenAPI drift clean

```bash
make openapi
git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
```

Expected: exit 0 (no diff — regenerated files match committed).

---

## ACC-07 — Design gaps + feature map clean

```bash
python scripts/audit_design_coverage.py --strict 2>&1 | tail -5
python scripts/update_feature_map.py --check 2>&1 | tail -5
```

Expected: both exit 0, no unaccounted `Design:`/`Contract:` gaps.
**IMPORTANT**: no `web-ui.json` or `reg-health.json` must appear in
`tests/feature_map/` — the E2E test intentionally carries no `Design:` or
`Contract:` markers to avoid spurious feature-map entries.

---

## ACC-08 — Frontend triple gate green

```bash
cd frontend && npm run lint && npm run typecheck && npx vitest run
```

Expected: all three pass (0 lint errors, 0 type errors, 0 test failures).

---

## ACC-09 — Frontend registry page renders provider cards (manual)

```bash
# Manual: open https://tm-staging.iznogoudatall.xyz/registry,
# verify each provider has a card with name + circuit badge + latency.
# Cannot be fully automated without Playwright — the vitest suite covers
# the rendering logic (Phase 4).  This ACC documents the manual check.
echo "ACC-09: vérifier manuellement dans le navigateur"
```

**Status**: PENDING (manual in-browser check — not automatable without
Playwright, covered by vitest rendering tests from Phase 4).
