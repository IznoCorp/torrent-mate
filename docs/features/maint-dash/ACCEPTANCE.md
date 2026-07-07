# ACCEPTANCE — S3 Maintenance Dashboard

**Feature**: maint-dash (7-wave web-UI roadmap — S3, ticket #182)
**Staging base**: `https://tm-staging.iznogoudatall.xyz`
**Executed on**: staging (ACC-01..ACC-07, ACC-09) / local checkout (ACC-08)
**Precondition ACC-07**: a pipeline run must be active (start a `personalscraper run`
before exercising the lock-conflict criterion).

Every criterion is an executable shell command with a documented expected output.
Run from the repo root. Uses `curl --connect-timeout 10 --max-time 30` on every
network call (project network-timeout rule).

---

## Prerequisites

```bash
# Capture a session cookie from the staging instance into /tmp/tm_session.
# The login endpoint is POST /api/auth/login; on success it returns 204 with a
# Set-Cookie header holding the JWT token as tm_session (HttpOnly, SameSite=Strict).

read -s -p "Password: " PASS && echo
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -D - \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$TM_USERNAME\",\"password\":\"$PASS\"}" \
  https://tm-staging.iznogoudatall.xyz/api/auth/login \
  | grep -i 'set-cookie: tm_session=' | sed 's/.*tm_session=\([^;]*\).*/\1/' \
  > /tmp/tm_session
# Expected: /tmp/tm_session contains a non-empty JWT token string.
```

`$TM_USERNAME` is your configured web username (same as `config/web.json5` →
`username`). The cookie file is read by every ACC-NN below via
`--cookie "tm_session=$(cat /tmp/tm_session)"`.

---

## ACC-01 — Disks panel (staging)

```bash
curl --connect-timeout 10 --max-time 30 -s \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  https://tm-staging.iznogoudatall.xyz/api/maintenance/disks \
  | jq '.disks[0].free_gb | type == "number"'
# Expected: true
```

## ACC-02 — Locks panel idle (staging)

```bash
curl --connect-timeout 10 --max-time 30 -s \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  https://tm-staging.iznogoudatall.xyz/api/maintenance/locks \
  | jq '.pipeline_lock.held'
# Expected: false
```

## ACC-03 — Index health (staging)

```bash
curl --connect-timeout 10 --max-time 30 -s \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  https://tm-staging.iznogoudatall.xyz/api/maintenance/index-health \
  | jq '.items > 0'
# Expected: true
```

## ACC-04 — Actions registry count (staging)

```bash
curl --connect-timeout 10 --max-time 30 -s \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  https://tm-staging.iznogoudatall.xyz/api/maintenance/actions \
  | jq '.actions | length'
# Expected: 25
```

## ACC-05 — Read-only action run → maintenance history row (staging)

```bash
RUN_UID=$(curl --connect-timeout 10 --max-time 30 -s -X POST \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d '{"options":{},"dry_run":true}' \
  https://tm-staging.iznogoudatall.xyz/api/maintenance/actions/library-status/run \
  | jq -r '.run_uid')
curl --connect-timeout 10 --max-time 30 -s \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  "https://tm-staging.iznogoudatall.xyz/api/pipeline/history/${RUN_UID}" \
  | jq '.kind == "maintenance" and .command == "library-status"'
# Expected: true
```

## ACC-06 — Destructive 428 guard (staging)

```bash
curl --connect-timeout 10 --max-time 30 -s -X POST \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d '{"options":{},"dry_run":false}' \
  https://tm-staging.iznogoudatall.xyz/api/maintenance/actions/library-clean/run \
  | jq -r '.detail'
# Expected: contains "428" or "dry.run" (the server rejects destructive
# runs that were not preceded by a successful dry-run for the same action)
```

## ACC-07 — Lock conflict 409 (staging, requires running pipeline)

```bash
# Precondition: a pipeline run is active (start `personalscraper run` first).
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}" \
  -X POST \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d '{"options":{},"dry_run":true}' \
  https://tm-staging.iznogoudatall.xyz/api/maintenance/actions/library-index/run
# Expected: 409
```

## ACC-08 — OpenAPI / type sync (local)

```bash
make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
# Expected: exit 0 (no drift between backend routes and generated frontend types)
```

## ACC-09 — Auth guard (staging, unauthenticated)

```bash
curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}" \
  https://tm-staging.iznogoudatall.xyz/api/maintenance/disks
# Expected: 401
```
