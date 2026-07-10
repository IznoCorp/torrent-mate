# ACCEPTANCE — acq-watch (S7 Web UI: Acquisition + Watcher)

**Feature**: acq-watch | **Branch**: feat/acq-watch | **DESIGN**: DESIGN.md
**Executed on**: prod daemon (`http://localhost:8710`) for authenticated reads /
`http://localhost:8711` for staging read-only tests (ACC-03) /
`https://tm-staging.iznogoudatall.xyz` for staging write-block tests (ACC-04)
**Precondition**: the `personalscraper web` daemon must be running on the target
port with a real `acquire.db` in `.data/` (created by any prior acquisition
command: `personalscraper follow detect`, etc.).

Every criterion is an executable shell command with a documented expected output.
Run from the repo root. Uses `curl --connect-timeout 10 --max-time 30` on every
network call (project network-timeout rule). Mutating routes additionally require
`-H "X-Requested-With: TorrentMate"`.

---

## Prerequisites

```bash
# ACC-00 — Forge a session cookie for headless re-exercise.
# The web process validates JWT HS256 tokens signed with WEB_JWT_SECRET.
# We construct one directly (no login round-trip) so this ACC is fully
# automatable without interactive password entry.

python3 -c "
import jwt, time, os, sys
from pathlib import Path
# Read WEB_JWT_SECRET from .env (the dev checkout .env).
env_path = Path('.env')
if not env_path.exists():
    # Try the prod deploy clone's env.
    env_path = Path.home() / 'deploy/torrentmate/.env'
secret_line = None
for line in env_path.read_text().splitlines():
    if line.startswith('WEB_JWT_SECRET='):
        secret_line = line.split('=', 1)[1].strip()
        break
if not secret_line:
    print('ERROR: WEB_JWT_SECRET not found in .env', file=sys.stderr)
    sys.exit(1)
token = jwt.encode({'sub': 'izno', 'iat': int(time.time())}, secret_line, algorithm='HS256')
# jwt.encode returns str with PyJWT >= 2.0
print(token)
" > /tmp/tm_session

# Verify the cookie file is non-empty.
test -s /tmp/tm_session && echo "ACC-00 PASS: cookie forged" || echo "ACC-00 FAIL: empty cookie"
```

Expected: `ACC-00 PASS: cookie forged`

---

## ACC-01 — GET /api/acquisition/followed (authed, prod 8710)

```bash
curl -s --connect-timeout 10 --max-time 30 \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  http://localhost:8710/api/acquisition/followed | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert 'items' in data, 'missing items key'
assert isinstance(data['items'], list), 'items is not a list'
for item in data['items']:
    assert set(item.keys()) == {
        'id', 'title', 'media_ref', 'active', 'cadence',
        'added_at', 'wanted_pending', 'quality_profile',
    }, f'Key drift: {set(item.keys())}'
    assert isinstance(item['id'], int)
    assert isinstance(item['title'], str)
    assert isinstance(item['active'], bool)
    assert isinstance(item['added_at'], (int, float))
    assert isinstance(item['wanted_pending'], int)
    mr = item['media_ref']
    assert set(mr.keys()) == {'tvdb_id', 'tmdb_id', 'imdb_id'}, f'MediaRef keys: {set(mr.keys())}'
print('ACC-01 PASS: got', len(data['items']), 'followed items')
"
```

Expected: `ACC-01 PASS: got N followed items` (N ≥ 0).

---

## ACC-02 — GET /api/acquisition/followed (unauthenticated → 401)

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 \
  http://localhost:8710/api/acquisition/followed
```

Expected: `401`.

---

## ACC-03 — GET /api/acquisition/followed (staging → 200)

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  http://localhost:8711/api/acquisition/followed
```

Expected: `200` (reads are staging-allowed).

**(Skip if the staging daemon is not running on port 8711.)**

---

## ACC-04 — POST /api/acquisition/followed (staging → 403)

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d '{"tvdb_id": 88888, "title": "Staging Write Blocked"}' \
  http://localhost:8711/api/acquisition/followed
```

Expected: `403` (mutating routes are staging-guarded).

**(Skip if the staging daemon is not running on port 8711.)**

---

## ACC-05 — POST new follow → 201, presence, dedup 409

```bash
# Create a unique test show (use a high tvdb_id unlikely to collide).
TEST_TVDB_ID=999999
TEST_TITLE="ACC Test Show $(date +%s)"

# Create.
HTTP_CODE=$(curl -s -o /tmp/acc_05_response.json -w "%{http_code}" \
  --connect-timeout 10 --max-time 30 \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d "{\"tvdb_id\": $TEST_TVDB_ID, \"title\": \"$TEST_TITLE\"}" \
  http://localhost:8710/api/acquisition/followed)
echo "Create: HTTP $HTTP_CODE"
test "$HTTP_CODE" = "201" || { echo "ACC-05 FAIL: expected 201, got $HTTP_CODE"; exit 1; }

python3 -c "
import json
data = json.load(open('/tmp/acc_05_response.json'))
assert data['title'] == '$TEST_TITLE', f'Title mismatch: {data[\"title\"]}'
assert data['media_ref']['tvdb_id'] == $TEST_TVDB_ID
assert data['active'] is True
print('Created id:', data['id'])
"

# Verify presence in the followed list.
curl -s --connect-timeout 10 --max-time 30 \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  "http://localhost:8710/api/acquisition/followed?active=all" | python3 -c "
import json, sys
data = json.load(sys.stdin)
found = [i for i in data['items'] if i['title'] == '$TEST_TITLE']
assert len(found) == 1, f'Expected 1 item, got {len(found)}'
print('ACC-05a PASS: item present in list')
"

# Dedup → 409.
DUP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  --connect-timeout 10 --max-time 30 \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d "{\"tvdb_id\": $TEST_TVDB_ID, \"title\": \"Duplicate\"}" \
  http://localhost:8710/api/acquisition/followed)
echo "Dedup: HTTP $DUP_CODE"
test "$DUP_CODE" = "409" || { echo "ACC-05 FAIL: expected 409 for dup, got $DUP_CODE"; exit 1; }

echo "ACC-05 PASS"
```

Expected: `ACC-05 PASS` with intermediate `ACC-05a PASS: item present in list`.

---

## ACC-06 — DELETE → 204 + row active=0 in acquire.db

```bash
# Get the ID from ACC-05's created item.
FOLLOWED_ID=$(cat /tmp/acc_05_response.json | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "Unfollowing id=$FOLLOWED_ID"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  --connect-timeout 10 --max-time 30 \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -H "X-Requested-With: TorrentMate" \
  -X DELETE \
  "http://localhost:8710/api/acquisition/followed/$FOLLOWED_ID")
echo "DELETE: HTTP $HTTP_CODE"
test "$HTTP_CODE" = "204" || { echo "ACC-06 FAIL: expected 204, got $HTTP_CODE"; exit 1; }

# Verify active=0 in acquire.db.
python3 -c "
import sqlite3
from pathlib import Path

# Resolve acquire.db path.  The prod daemon uses PERSONALSCRAPER_CONFIG to
# locate config/, which sets data_dir.  Default is .data/ under the repo root.
# We try the prod deploy clone path first, then the dev checkout.
candidates = [
    Path.home() / 'deploy/torrentmate/.data/acquire.db',
    Path('.data/acquire.db'),
]
db_path = None
for p in candidates:
    if p.exists():
        db_path = p
        break
assert db_path is not None, 'acquire.db not found — is the daemon running?'
db = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
db.row_factory = sqlite3.Row
row = db.execute('SELECT active, title FROM followed_series WHERE id = ?', ($FOLLOWED_ID,)).fetchone()
db.close()
assert row is not None, f'Row {FOLLOWED_ID} not found'
assert row['active'] == 0, f'Expected active=0, got {row[\"active\"]}'
print(f'ACC-06 PASS: row {FOLLOWED_ID} soft-deleted (active=0, title={row[\"title\"]!r})')
"
```

Expected: `ACC-06 PASS: row <id> soft-deleted (active=0, title=...)`.

---

## ACC-07 — GET /api/acquisition/status (watcher fields)

```bash
curl -s --connect-timeout 10 --max-time 30 \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  http://localhost:8710/api/acquisition/status | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert 'last_successful_run_at' in data, 'missing last_successful_run_at'
assert 'watcher_enabled' in data, 'missing watcher_enabled'
assert 'recent_runs' in data, 'missing recent_runs'
assert isinstance(data['watcher_enabled'], bool), f'watcher_enabled must be bool, got {type(data[\"watcher_enabled\"]).__name__}'
assert isinstance(data['recent_runs'], list), 'recent_runs must be list'
# last_successful_run_at may be null if the watcher has never run.
if data['last_successful_run_at'] is not None:
    assert isinstance(data['last_successful_run_at'], (int, float)), \
        f'last_successful_run_at must be numeric, got {type(data[\"last_successful_run_at\"]).__name__}'
for run in data['recent_runs']:
    assert 'run_uid' in run
    assert 'started_at' in run
    assert 'outcome' in run
print('ACC-07 PASS: status shape ok, watcher_enabled =', data['watcher_enabled'])
"
```

Expected: `ACC-07 PASS: status shape ok, watcher_enabled = true/false`.

---

## ACC-08 — make check green

```bash
make check
```

Expected: exit code 0, all checks pass (lint, test, module-size, typed-api).
Summary line: `NNNN passed` with 0 failed/errors.

---

## ACC-09 — Frontend triple gate green

```bash
cd frontend && npm run lint && npm run typecheck && npx vitest run
```

Expected: all three commands exit 0 (0 lint errors, 0 type errors, 0 test failures).

---

## ACC-10 — OpenAPI drift clean

```bash
make openapi
git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
```

Expected: exit 0 (no uncommitted drift — regenerated files match committed).

---

## ACC-11 — Design gaps + feature map clean

```bash
python scripts/audit_design_coverage.py --strict 2>&1 | tail -5
python scripts/update_feature_map.py --check 2>&1 | tail -5
```

Expected: both exit 0. No `acq-watch.json` or `web-ui.json` must appear in
`tests/feature_map/` — the E2E test intentionally carries no `Design:` or
`Contract:` markers to avoid spurious feature-map entries.

---

## ACC-12 — Frontend /acquisition page renders (manual)

```bash
# Manual: open https://tm-staging.iznogoudatall.xyz/acquisition,
# verify the Followed tab renders (table of followed series or empty state),
# the nav entry "Acquisition" is active (Radar icon), switching to Wanted tab
# shows the wanted table, and the Watcher tab shows last run + enabled toggle.
# Cannot be fully automated without Playwright — the vitest suite covers
# the rendering logic (Phase 4).  This ACC documents the manual check.
echo "ACC-12: vérifier manuellement dans le navigateur"
```

**Status**: PENDING (manual in-browser check — not automatable without
Playwright, covered by vitest rendering tests from Phase 4).

---

## ACC-13 — PyJWT import available (forged-JWT prerequisite)

```bash
python3 -c "import jwt; print('PyJWT', jwt.__version__)"
```

Expected: `PyJWT <version>` — the `jwt` package must be installed for the
forged-JWT technique used in ACC-00.
