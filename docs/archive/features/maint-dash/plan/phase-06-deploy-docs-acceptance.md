# Phase 6 — Deploy Rails + Docs + ACCEPTANCE

## Gate

**Prerequisite — Phase 1–5 delivered**:

- All backend routes + models operational, `make test` green (all 6000+ tests pass).
- Frontend `/maintenance` page renders 4 panels + action catalog + forms + run output.
- `make openapi` regen committed, CI drift guard passes.
- `make lint` green (ruff + mypy + check_logging + check-module-size).
- `make check` green (lint + test + module-size + typed-api).
- Residual import grep clean (no references to deleted modules in `personalscraper/` or `tests/`).
- `python -c "import personalscraper"` smoke test passes.

**Produces**: mergeable branch. Post-merge: staging validated, docs updated, ACCEPTANCE exercised.

## Sub-phases

### 6.1 — Staging deploy + Chrome MCP E2E validation (`chore(maint-dash): staging E2E validation with Chrome MCP`)

**Steps** (no source code changes, operational validation):

1. Push `feat/maint-dash` to `staging` branch: `git push origin feat/maint-dash:staging --force-with-lease`
2. Wait for auto-deploy (PM2 `torrentmate-autodeploy` picks up staging push, same as S2).
3. Open `https://tm-staging.iznogoudatall.xyz/maintenance` in Chrome via MCP.
4. Validate panels render (no JS errors in console):
   - DisksPanel: all disks appear, space bars rendered, StatusDot colors correct.
   - LocksPanel: lock state shown, sentinel ages visible.
   - IndexHealthPanel: counts match `personalscraper library-status` numbers.
   - RunHistoryPanel: filter chips (Tout / Pipeline / Maintenance) work, rows render with kind/command.
5. Execute a RO action dry-run: click `library-status` → form opens → "Exécuter" → verify run spawns, live output streams in RunOutput panel, run appears in history with `kind='maintenance'`.
6. Execute a destructive flow: `library-clean` dry-run → success → Apply enabled → Apply → 202.
7. Verify 428: reload or change a field → Apply locked until fresh dry-run.
8. Verify 409: start a pipeline run, then attempt a maintenance write action → 409 toast.

**No local server on ports 8710/8711** (project rule).

### 6.2 — Documentation update (`docs(maint-dash): add S3 maintenance section to web-ui.md and maintenance.md`)

**Files:**

- Modify: `docs/reference/web-ui.md` (add §S3 section with route table, models, panel descriptions)
- Modify: `docs/reference/maintenance.md` (update with web-UI action catalog reference, link to registry, note on runner lifecycle)

**`docs/reference/web-ui.md` §S3**: document the `/maintenance` screen, the 6 routes (table format matching S1/S2 convention), panel descriptions referencing the DS components used, action catalog architecture (registry-driven forms, dry-run-first flow, runner lifecycle). Link to DESIGN §4 route contract.

**`docs/reference/maintenance.md`**: add a § on web-UI maintenance actions: how the registry maps CLI commands to web forms, how the runner spawns, how `pipeline_run` unifies pipeline + maintenance history. Link to `web-ui.md` §S3.

Update the reference index in CLAUDE.md root:

```markdown
| Maintenance ops — disk cleaning + targeted re-scrape repairs | `docs/reference/maintenance.md` |
```

→ add mention of web-UI actions and the runner.

### 6.3 — ACCEPTANCE.md with executable criteria (`test(maint-dash): add executable ACCEPTANCE criteria`)

**Files:**

- Create: `docs/features/maint-dash/ACCEPTANCE.md`

**Executable criteria** (each is a shell command with expected output; per project ACCEPTANCE convention):

```markdown
# ACCEPTANCE — S3 Maintenance Dashboard

## ACC-01 — Disks panel

curl -s --cookie "session=$(cat /tmp/tm_session)" \
https://tm-staging.iznogoudatall.xyz/api/maintenance/disks | jq '.disks[0].free_gb | type == "number"'

# Expected: true

## ACC-02 — Locks panel (idle)

curl -s --cookie "session=$(cat /tmp/tm_session)" \
https://tm-staging.iznogoudatall.xyz/api/maintenance/locks | jq '.pipeline_lock.held'

# Expected: false

## ACC-03 — Index health

curl -s --cookie "session=$(cat /tmp/tm_session)" \
https://tm-staging.iznogoudatall.xyz/api/maintenance/index-health | jq '.items > 0'

# Expected: true

## ACC-04 — Actions registry count

curl -s --cookie "session=$(cat /tmp/tm_session)" \
https://tm-staging.iznogoudatall.xyz/api/maintenance/actions | jq '.actions | length'

# Expected: 25

## ACC-05 — RO action run

RUN_UID=$(curl -s -X POST --cookie "session=$(cat /tmp/tm_session)" \
-H "X-Requested-With: TorrentMate" \
-H "Content-Type: application/json" \
-d '{"options":{},"dry_run":true}' \
https://tm-staging.iznogoudatall.xyz/api/maintenance/actions/library-status/run | jq -r '.run_uid')
curl -s --cookie "session=$(cat /tmp/tm_session)" \
  "https://tm-staging.iznogoudatall.xyz/api/pipeline/history/${RUN_UID}" | \
jq '.kind == "maintenance" and .command == "library-status"'

# Expected: true

## ACC-06 — Destructive 428 guard

curl -s -X POST --cookie "session=$(cat /tmp/tm_session)" \
-H "X-Requested-With: TorrentMate" \
-H "Content-Type: application/json" \
-d '{"options":{},"dry_run":false}' \
https://tm-staging.iznogoudatall.xyz/api/maintenance/actions/library-clean/run | jq -r '.detail'

# Expected: contains "428" or "dry.run"

## ACC-07 — Lock conflict 409

# (Requires a running pipeline — run it first, then:)

curl -s -o /dev/null -w "%{http_code}" -X POST --cookie "session=$(cat /tmp/tm_session)" \
-H "X-Requested-With: TorrentMate" \
-H "Content-Type: application/json" \
-d '{"options":{},"dry_run":true}' \
https://tm-staging.iznogoudatall.xyz/api/maintenance/actions/library-index/run

# Expected: 409

## ACC-08 — OpenAPI / type sync

make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts

# Expected: exit 0 (no drift)

## ACC-09 — Auth guard

curl -s -o /dev/null -w "%{http_code}" \
https://tm-staging.iznogoudatall.xyz/api/maintenance/disks

# Expected: 401
```

Each ACC-NN must be executable on staging post-merge. ACC-07 requires a running pipeline — note the precondition. ACC-06 uses `library-clean` which must have `dry_run='supported'` in the registry.
