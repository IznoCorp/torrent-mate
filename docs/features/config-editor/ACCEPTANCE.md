# ACCEPTANCE — S4 Config Editor

**Feature**: config-editor (7-wave web-UI roadmap — S4, ticket #183)
**Executed on**: local daemon (`http://localhost:8710`) for prod write tests /
`http://localhost:8711` for staging read-only test (ACC-03)
**Precondition ACC-07**: the daemon must have `PERSONALSCRAPER_PM2_NAME` set in its
environment (PM2-managed prod instance).

Every criterion is an executable shell command with a documented expected output.
Run from the repo root. Uses `curl --connect-timeout 10 --max-time 30` on every
network call (project network-timeout rule). Mutating endpoints require
`-H "X-Requested-With: TorrentMate"`.

---

## Prerequisites

```bash
# ACC-00 — Capture a session cookie from the local daemon into /tmp/tm_session.
# The login endpoint is POST /api/auth/login; on success it returns 204 with a
# Set-Cookie header holding the JWT token as tm_session (HttpOnly, SameSite=Strict).
# WEB creds live in config/web.json5 (username) + .env (WEB_PASSWORD_HASH).
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

`$TM_USERNAME` (or the literal `izno`) is your configured web username (same as
`config/web.json5` → `username`). The cookie file is read by every ACC-NN below
via `--cookie "tm_session=$(cat /tmp/tm_session)"`.

---

## ACC-01 — Reject invalid write (local, 422 + file untouched)

```bash
FILE="web.json5"
# Capture current sha256 from GET.
SHA_BEFORE=$(
  curl --connect-timeout 10 --max-time 30 -s \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    "http://localhost:8710/api/config/files/${FILE}" \
  | jq -r '.sha256'
)
# Send a PUT with a deliberate type error: "web" expects an object, not a string.
HTTP_CODE=$(
  curl --connect-timeout 10 --max-time 30 -s -o /tmp/acc01_body.json -w "%{http_code}" \
    -X PUT \
    -H "Content-Type: application/json" \
    -H "X-Requested-With: TorrentMate" \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    -d "{\"values\":{\"web\":\"not_an_object\"},\"base_sha256\":\"${SHA_BEFORE}\"}" \
    "http://localhost:8710/api/config/files/${FILE}"
)
echo "HTTP ${HTTP_CODE}"
cat /tmp/acc01_body.json | jq '.detail[0] | {loc, msg, type}'
# Capture current sha256 from GET again — must be unchanged.
SHA_AFTER=$(
  curl --connect-timeout 10 --max-time 30 -s \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    "http://localhost:8710/api/config/files/${FILE}" \
  | jq -r '.sha256'
)
test "${SHA_BEFORE}" = "${SHA_AFTER}" && echo "PASS: file untouched"
# Expected:
#   HTTP 422
#   detail[0] contains {loc: [...], msg: "...", type: "..."}
#   SHA_BEFORE == SHA_AFTER (file untouched on disk)
```

## ACC-02 — Accept valid write, backup exists, staleness reported (local)

```bash
FILE="web.json5"
# Read current values + sha256.
GET_OUT=$(
  curl --connect-timeout 10 --max-time 30 -s \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    "http://localhost:8710/api/config/files/${FILE}"
)
SHA_BEFORE=$(echo "$GET_OUT" | jq -r '.sha256')
VALUES=$(echo "$GET_OUT" | jq -c '.values')

# Write the SAME values back with the correct base_sha256.
# This is a value-identical write — only the header comment changes.
RESP=$(
  curl --connect-timeout 10 --max-time 30 -s -w "\n%{http_code}" \
    -X PUT \
    -H "Content-Type: application/json" \
    -H "X-Requested-With: TorrentMate" \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    -d "{\"values\":${VALUES},\"base_sha256\":\"${SHA_BEFORE}\"}" \
    "http://localhost:8710/api/config/files/${FILE}"
)
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')
echo "HTTP ${HTTP_CODE}"
echo "$BODY" | jq '.'
# Expected: HTTP 200, body contains {"warnings":[...],"restart_required":...}

# Verify backup was created.
BACKUP_COUNT=$(
  ls "config/.backups/${FILE}".* 2>/dev/null | wc -l | tr -d ' '
)
echo "Backups: ${BACKUP_COUNT}"
# Expected: BACKUP_COUNT >= 1 (a new backup was created)

# Verify sha256 changed (header comment differs).
SHA_AFTER=$(
  curl --connect-timeout 10 --max-time 30 -s \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    "http://localhost:8710/api/config/files/${FILE}" \
  | jq -r '.sha256'
)
test "${SHA_BEFORE}" != "${SHA_AFTER}" && echo "PASS: sha256 changed (header comment)"
# Expected: SHA_BEFORE != SHA_AFTER

# Verify status endpoint reports the file as stale.
STATUS=$(
  curl --connect-timeout 10 --max-time 30 -s \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    "http://localhost:8710/api/config/status"
)
echo "$STATUS" | jq '{restart_required, stale_files}'
echo "$STATUS" | jq -e '.stale_files | contains(["'"${FILE}"'"])' \
  && echo "PASS: ${FILE} listed in stale_files"
# Expected: restart_required=true, stale_files includes "web.json5"
```

## ACC-03 — Staging read-only (local, 403 on write)

```bash
# This criterion requires the staging daemon on port 8711.
# If tm-staging is not running locally, skip with a note.
FILE="paths.json5"
HTTP_CODE=$(
  curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w "%{http_code}" \
    -X PUT \
    -H "Content-Type: application/json" \
    -H "X-Requested-With: TorrentMate" \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    -d '{"values":{"paths":{"staging_dir":"/tmp/test","data_dir":"/tmp/data"}},"base_sha256":""}' \
    "http://localhost:8711/api/config/files/${FILE}"
)
echo "HTTP ${HTTP_CODE}"
curl --connect-timeout 10 --max-time 30 -s \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  "http://localhost:8711/api/config/files/${FILE}" \
  | jq -r '.detail'
# Expected: HTTP 403, detail = "read-only"
# (Skip if staging not running — the 403 is enforced by PERSONALSCRAPER_WEB_ROLE=staging
# in ecosystem.config.js.  Unit test coverage in test_config_routes_write.py
# TestPutFileEndpoint.test_403_staging_role.)
```

## ACC-04 — 412 stale precondition (local)

```bash
FILE="web.json5"
# Use 64-char all-zero sha256 — guaranteed to mismatch.
ZERO_SHA="0000000000000000000000000000000000000000000000000000000000000000"
RESP=$(
  curl --connect-timeout 10 --max-time 30 -s -w "\n%{http_code}" \
    -X PUT \
    -H "Content-Type: application/json" \
    -H "X-Requested-With: TorrentMate" \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    -d "{\"values\":{},\"base_sha256\":\"${ZERO_SHA}\"}" \
    "http://localhost:8710/api/config/files/${FILE}"
)
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')
echo "HTTP ${HTTP_CODE}"
echo "$BODY" | jq -r '.detail'
# Expected: HTTP 412, detail contains "file modified since last read" or
#   equivalent stale-precondition message
```

## ACC-05 — Secrets: is_set flip without echo (local)

```bash
# GET secrets — verify no value field exists anywhere.
SECRETS=$(
  curl --connect-timeout 10 --max-time 30 -s \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    "http://localhost:8710/api/config/secrets"
)
echo "$SECRETS" | jq '.secrets[0] | keys'
echo "$SECRETS" | jq -e '[.secrets[].key] | length > 0' \
  && echo "PASS: secrets catalog non-empty"
# Expected: each entry has ONLY key, description, is_set fields.
#   No "value" key anywhere in the response.
# Verify no "value" key in the whole body:
echo "$SECRETS" | jq -e 'any(.. | objects; has("value")) | not' \
  && echo "PASS: no 'value' field anywhere in response"

# PUT with an UNKNOWN key → 422, value must NOT be echoed.
SECRET_VAL="do_not_echo_me_test_2026"
HTTP_CODE=$(
  curl --connect-timeout 10 --max-time 30 -s -o /tmp/acc05_body.json -w "%{http_code}" \
    -X PUT \
    -H "Content-Type: application/json" \
    -H "X-Requested-With: TorrentMate" \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    -d "{\"UNKNOWN_NONEXISTENT_KEY\":\"${SECRET_VAL}\"}" \
    "http://localhost:8710/api/config/secrets"
)
echo "HTTP ${HTTP_CODE}"
jq '.detail' /tmp/acc05_body.json
grep -q "${SECRET_VAL}" /tmp/acc05_body.json && echo "FAIL: secret value echoed!" || echo "PASS: value not echoed"
# Expected: HTTP 422, body.detail.unknown_keys contains "UNKNOWN_NONEXISTENT_KEY",
#   body text does NOT contain "do_not_echo_me_test_2026"
```

## ACC-06 — Schema endpoint: ownership completeness (local)

```bash
OWNERSHIP_COUNT=$(
  curl --connect-timeout 10 --max-time 30 -s \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    "http://localhost:8710/api/config/schema" \
  | jq '.ownership | keys | length'
)
echo "Ownership keys: ${OWNERSHIP_COUNT}"
test "${OWNERSHIP_COUNT}" -eq 28 && echo "PASS" || echo "FAIL: expected 28"
# Expected: 28 (every Config.model_fields key has an owner file)
```

## ACC-07 — Restart endpoint schedules restart (local, operator-supervised)

```bash
# This criterion requires PERSONALSCRAPER_PM2_NAME to be set on the daemon.
# The daemon restarts ~0.5s after the POST — the UI reconnects automatically.
RESP=$(
  curl --connect-timeout 10 --max-time 30 -s -w "\n%{http_code}" \
    -X POST \
    -H "X-Requested-With: TorrentMate" \
    --cookie "tm_session=$(cat /tmp/tm_session)" \
    "http://localhost:8710/api/config/restart-web"
)
HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')
echo "HTTP ${HTTP_CODE}"
echo "$BODY" | jq '.'
# Expected when PM2_NAME is configured: HTTP 202, body = {"status":"scheduled"}
# When PM2_NAME is NOT set: HTTP 404, body.detail = "restart not configured"
# (The daemon restarts ~0.5s after the 202 response — the UI WebSocket
# reconnects automatically.  Operator-supervised: watch pm2 logs.)
```

## ACC-08 — Restart-impact architecture guard (local, CI-independent)

```bash
python -m pytest tests/web/test_config_restart_impact.py -q
# Expected: 7 passed in ...s (all tests pass)
# This validates that every Config.model_fields key is classified in
# RESTART_IMPACT and that the fail-safe default (True for unknown keys) works.
```
