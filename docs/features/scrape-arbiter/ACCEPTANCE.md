# ACCEPTANCE — S5 Scrape Arbiter

**Feature**: scrape-arbiter (7-wave web-UI roadmap — S5, ticket #184)
**Executed on**: prod daemon (`http://localhost:8710`) for write tests /
`http://localhost:8711` for staging read-only tests (ACC-06)
**Precondition**: a pending `scrape_decision` row must exist in `library.db`
for ACC-02, ACC-04, and ACC-05 (either natural mid-band enqueue from a prior
pipeline run, or a hand-inserted row for isolated testing).

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

**Headless re-exercise**: if interactive password entry is not available, use
the forged-JWT technique: construct a valid JWT with `sub=<username>` signed
with the `WEB_JWT_SECRET` from `.env`, write it directly to `/tmp/tm_session`,
and skip the login curl above. The forged cookie is accepted identically by
`require_session` (`personalscraper/web/deps.py:124`).

---

## ACC-01 — Enqueue observed on dry-run (structural)

```bash
# Run a dry-run pipeline and count queued_for_decision items in the console output.
# The scrape step prints "[queued_for_decision] <item-name>" for each mid-band or
# ambiguous item that the decision-triage stage enqueues (status="queued_for_decision"
# on ItemProgressed events + console detail lines in scraper/run.py:372-373).
personalscraper run --dry-run 2>&1 | grep -c '\[queued_for_decision\]'
# Expected: count >= 0.  This is a structural check — the count is 0 when staging
# is empty or all items score outside the mid-band [0.5, 0.8).  The >= 1 variant is
# data-dependent: it passes only when staging holds at least one mid-band item.
```

**Status**: PENDING — `>= 0` is structural (always passes on valid pipeline);
`>= 1` is 🟡 DEFERRED (data-dependent — requires a mid-band item in staging, see
`docs/reference/feature-lifecycle.md` §3 deferred-criterion protocol).

---

## ACC-02 — CLI scrape-resolve happy path (local, requires pending row)

```bash
# Resolve a pending decision via the CLI.  Requires at least one pending
# scrape_decision row in library.db.  Find one with:
DECISION_ID=$(sqlite3 library.db \
  "SELECT id FROM scrape_decision WHERE status='pending' LIMIT 1")
STAGING_PATH=$(sqlite3 library.db \
  "SELECT staging_path FROM scrape_decision WHERE id=${DECISION_ID}")
MEDIA_KIND=$(sqlite3 library.db \
  "SELECT media_kind FROM scrape_decision WHERE id=${DECISION_ID}")

echo "Resolving decision ${DECISION_ID} at ${STAGING_PATH} (kind=${MEDIA_KIND})"

# Pick provider by media kind.
if [ "${MEDIA_KIND}" = "movie" ]; then
  PROVIDER="tmdb"
else
  PROVIDER="tvdb"
fi

# The provider_id must be chosen by the operator — extract one from candidates_json
# or supply a known valid ID.  For the purpose of this criterion, set PROVIDER_ID
# to a valid provider identifier for the item.
echo "Set PROVIDER_ID to a valid ${PROVIDER} id for this item, then run:"
echo "personalscraper scrape-resolve \"${STAGING_PATH}\" --provider ${PROVIDER} --id \${PROVIDER_ID}"

# After running with the correct ID:
# personalscraper scrape-resolve "${STAGING_PATH}" --provider "${PROVIDER}" --id "${PROVIDER_ID}"
# echo "Exit code: $?"
# Expected: exit 0, console shows "Successfully resolved decision <id> via <provider>:<id>."

# Verify the decision row is now 'resolved':
# sqlite3 library.db "SELECT status FROM scrape_decision WHERE id=${DECISION_ID}"
# Expected: resolved

# Verify NFO was written in the staging folder:
# ls "${STAGING_PATH}"/movie.nfo "${STAGING_PATH}"/tvshow.nfo 2>/dev/null
# Expected: at least one .nfo file exists
```

**Status**: PENDING — requires a pending `scrape_decision` row and a valid
provider ID for that item (operator-supplied at re-exercise time).

---

## ACC-03 — Pending list and count via authenticated curl (local)

```bash
# GET /api/decisions?status=pending returns a paginated list with pending_count.
RESP=$(curl --connect-timeout 10 --max-time 30 -s \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  "http://localhost:8710/api/decisions?status=pending&page=1&page_size=5")

echo "$RESP" | jq '{pending_count, total, page, page_size}'
# Expected: pending_count is an integer >= 0, total matches the status filter,
#   page=1, page_size=5.  items is an array of length <= 5.

# Verify the response schema fields exist:
echo "$RESP" | jq -e '.pending_count >= 0' \
  && echo "PASS: pending_count is a non-negative integer"
echo "$RESP" | jq -e '.items | type == "array"' \
  && echo "PASS: items is an array"
echo "$RESP" | jq -e '.total >= 0' \
  && echo "PASS: total is a non-negative integer"

# When a pending row exists, items[0] has the expected fields:
if echo "$RESP" | jq -e '.items | length > 0' 2>/dev/null; then
  echo "$RESP" | jq '.items[0] | {id, staging_path, media_kind, extracted_title, trigger, candidates_count, status}'
  echo "$RESP" | jq -e '.items[0].status == "pending"' \
    && echo "PASS: first item status is pending"
fi
# Expected: valid JSON response with DecisionsResponse schema fields.
#   When no pending rows exist: items=[], pending_count=0, total=0.
```

**Status**: PENDING

---

## ACC-04 — Web resolve returns 202 (prod, requires pending row + valid provider ID)

```bash
# POST /api/decisions/{id}/resolve launches a runner subprocess and returns 202
# with a run_uid.  Requires X-Requested-With: TorrentMate and a valid tm_session.
# This endpoint is guarded by require_not_staging — it MUST be exercised against
# the prod daemon on port 8710 (staging returns 403; see ACC-06).

# Find a pending decision:
DECISION_ID=$(sqlite3 library.db \
  "SELECT id FROM scrape_decision WHERE status='pending' LIMIT 1")

if [ -z "${DECISION_ID}" ]; then
  echo "SKIP: no pending decision row available"
  exit 0
fi

MEDIA_KIND=$(sqlite3 library.db \
  "SELECT media_kind FROM scrape_decision WHERE id=${DECISION_ID}")
echo "Decision ${DECISION_ID}: kind=${MEDIA_KIND}"

# Pick provider by media kind.
if [ "${MEDIA_KIND}" = "movie" ]; then
  PROVIDER="tmdb"
else
  PROVIDER="tvdb"
fi

# The provider_id must be chosen by the operator.  Set PROVIDER_ID to a valid
# identifier for this item, then run the resolve:
echo "Set PROVIDER_ID to a valid ${PROVIDER} id for decision ${DECISION_ID}, then run:"
echo "curl --connect-timeout 10 --max-time 30 -s -w \"\\n%{http_code}\" \\"
echo "  -X POST \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -H \"X-Requested-With: TorrentMate\" \\"
echo "  --cookie \"tm_session=\$(cat /tmp/tm_session)\" \\"
echo "  -d '{\"provider\":\"${PROVIDER}\",\"provider_id\":'\${PROVIDER_ID}'}' \\"
echo "  \"http://localhost:8710/api/decisions/${DECISION_ID}/resolve\""

# After running with the correct ID:
# RESP=$(curl --connect-timeout 10 --max-time 30 -s -w "\n%{http_code}" \
#   -X POST \
#   -H "Content-Type: application/json" \
#   -H "X-Requested-With: TorrentMate" \
#   --cookie "tm_session=$(cat /tmp/tm_session)" \
#   -d "{\"provider\":\"${PROVIDER}\",\"provider_id\":${PROVIDER_ID}}" \
#   "http://localhost:8710/api/decisions/${DECISION_ID}/resolve")
# HTTP_CODE=$(echo "$RESP" | tail -1)
# BODY=$(echo "$RESP" | sed '$d')
# echo "HTTP ${HTTP_CODE}"
# echo "$BODY" | jq '.'
# # Expected: HTTP 202, body = {"run_uid": "<32-char hex string>"}
# echo "$BODY" | jq -e '.run_uid | type == "string" and length == 32' \
#   && echo "PASS: run_uid is a 32-character hex string"
#
# # Verify a pipeline_run row was reserved:
# sqlite3 library.db \
#   "SELECT run_uid, action_key, status FROM pipeline_run WHERE run_uid='$(echo "$BODY" | jq -r '.run_uid')'"
# # Expected: one row with action_key='scrape-resolve', status='running'
```

**Status**: PENDING — requires a pending `scrape_decision` row and a valid
provider ID (operator-supplied at re-exercise time). The resolve endpoint
mutates state (spawns runner, marks decision resolved); re-exercise with a
prepared test row.

---

## ACC-05 — Search returns candidates (local, requires pending row)

```bash
# POST /api/decisions/{id}/search queries live providers for candidate matches.
# Read-only — no state change.  Requires X-Requested-With: TorrentMate.

# Find a pending decision:
DECISION_ID=$(sqlite3 library.db \
  "SELECT id FROM scrape_decision WHERE status='pending' LIMIT 1")

if [ -z "${DECISION_ID}" ]; then
  echo "SKIP: no pending decision row available"
  exit 0
fi

# Extract the title to search with (or override with a known-good title).
EXTRACTED_TITLE=$(sqlite3 library.db \
  "SELECT extracted_title FROM scrape_decision WHERE id=${DECISION_ID}")
echo "Decision ${DECISION_ID}: title='${EXTRACTED_TITLE}'"

# Search with the extracted title (or a known-good title for deterministic results).
SEARCH_TITLE="${EXTRACTED_TITLE:-Inception}"
RESP=$(curl --connect-timeout 10 --max-time 30 -s -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: TorrentMate" \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -d "{\"title\":\"${SEARCH_TITLE}\",\"year\":null}" \
  "http://localhost:8710/api/decisions/${DECISION_ID}/search")

HTTP_CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')
echo "HTTP ${HTTP_CODE}"
echo "$BODY" | jq '.candidates | length'
# Expected: HTTP 200, candidates is an array (length >= 0; typically >= 1 for
#   a well-known title like "Inception").

echo "$BODY" | jq -e '.candidates | type == "array"' \
  && echo "PASS: candidates is an array"

# When candidates are returned, verify the expected fields:
if echo "$BODY" | jq -e '.candidates | length > 0' 2>/dev/null; then
  echo "$BODY" | jq '.candidates[0] | {title, year, provider, provider_id, confidence}'
  echo "$BODY" | jq -e '.candidates[0].provider_id != null' \
    && echo "PASS: first candidate has a provider_id"
fi
# Expected: HTTP 200, valid SearchResponse with candidates array.
#   When no providers match: candidates=[], HTTP still 200.
```

**Status**: PENDING

---

## ACC-06 — Staging returns 403 on resolve and dismiss (local)

```bash
# Both POST /api/decisions/{id}/resolve and POST /api/decisions/{id}/dismiss
# are guarded by require_not_staging.  When PERSONALSCRAPER_WEB_ROLE=staging
# (port 8711), they MUST return 403 with detail "read-only".
# This criterion requires the staging daemon on port 8711.
# If tm-staging is not running locally, skip with a note.

DECISION_ID=1  # Any id works — the staging guard fires before the DB lookup.

# ── Test resolve on staging ──
RESOLVE_RESP=$(curl --connect-timeout 10 --max-time 30 -s -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: TorrentMate" \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  -d '{"provider":"tmdb","provider_id":550}' \
  "http://localhost:8711/api/decisions/${DECISION_ID}/resolve")
RESOLVE_CODE=$(echo "$RESOLVE_RESP" | tail -1)
RESOLVE_BODY=$(echo "$RESOLVE_RESP" | sed '$d')
echo "resolve HTTP ${RESOLVE_CODE}"
echo "$RESOLVE_BODY" | jq -r '.detail'

# Expected: HTTP 403, detail = "read-only"

# ── Test dismiss on staging ──
DISMISS_RESP=$(curl --connect-timeout 10 --max-time 30 -s -w "\n%{http_code}" \
  -X POST \
  -H "X-Requested-With: TorrentMate" \
  --cookie "tm_session=$(cat /tmp/tm_session)" \
  "http://localhost:8711/api/decisions/${DECISION_ID}/dismiss")
DISMISS_CODE=$(echo "$DISMISS_RESP" | tail -1)
DISMISS_BODY=$(echo "$DISMISS_RESP" | sed '$d')
echo "dismiss HTTP ${DISMISS_CODE}"
echo "$DISMISS_BODY" | jq -r '.detail'

# Expected: HTTP 403, detail = "read-only"

# (Skip if staging not running — the 403 is enforced by PERSONALSCRAPER_WEB_ROLE=staging
# in ecosystem.config.js.  Unit test coverage in test_scrape_arbiter_e2e.py and
# test_runner_lifecycle.py validates the guard independently of the live daemon.)
```

**Status**: PENDING — requires the staging daemon on port 8711.

---

## ACC-07 — Lock-held scrape-resolve exits 1 (local CLI)

```bash
# scrape-resolve self-acquires pipeline.lock via acquire_lock() (O_CREAT|O_EXCL).
# When the lock is already held, acquire_lock returns False and the command
# exits 1 with the message "Another instance is running. Exiting.".
# This is the R11 contract: scrape-resolve self-acquires, the web runner never
# pre-acquires, and a double-acquisition is rejected with exit 1.

# 1. Acquire the lock manually (simulate a concurrent pipeline or another resolve).
python3 -c "
from personalscraper.lock import acquire_lock
held = acquire_lock()
print('LOCK_HELD' if held else 'LOCK_NOT_HELD')
"
# Expected: LOCK_HELD

# 2. Run scrape-resolve — must fail with exit 1 because the lock is held.
# Use any valid staging path; the lock check happens before the DB lookup.
personalscraper scrape-resolve "/nonexistent/path" --provider tmdb --id 1
ACTUAL_EXIT=$?
echo "Exit code: ${ACTUAL_EXIT}"
# Expected: exit 1, console shows "Another instance is running. Exiting."

# 3. Release the lock.
python3 -c "
from personalscraper.lock import release_lock
release_lock()
print('LOCK_RELEASED')
"
# Expected: LOCK_RELEASED

# 4. Run scrape-resolve again — now the lock is free (still fails on the
#    nonexistent path, but with exit 2, not exit 1).
personalscraper scrape-resolve "/nonexistent/path" --provider tmdb --id 1
ACTUAL_EXIT2=$?
echo "Exit code: ${ACTUAL_EXIT2}"
# Expected: exit 2 (misconfiguration — no decision row for that path), NOT exit 1.
#   exit 2 proves the lock check passed and the command proceeded past it.

test ${ACTUAL_EXIT} -eq 1 && echo "PASS: lock held → exit 1"
test ${ACTUAL_EXIT2} -eq 2 && echo "PASS: lock released → exit 2 (past lock check)"
```

**Status**: PENDING
