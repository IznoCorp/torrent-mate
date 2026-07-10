# Phase 04 — Integration Gates + Docs + Acceptance

## Gate

- [ ] Phase 03 merged — `/config` page functional, nav enabled, API client hooks in place
- [ ] `make test` green on current HEAD
- [ ] `make lint` green on current HEAD

## Goal

Final integration: regenerate OpenAPI types, update PM2 ecosystem config, de-stale reference docs, write executable ACCEPTANCE criteria, and pass the full quality gate.

## Sub-phases

### 4.1 — OpenAPI regeneration

**Files**:

- Regenerate: `frontend/openapi.json` — `make openapi` (or `python -m personalscraper.web.openapi`)
- Regenerate: `frontend/src/api/schema.d.ts` — auto-generated from openapi.json
- Verify: `git diff --stat` shows only these 2 files changed (plus any intentional route docstring updates from Phase 2)

**Command**:

```bash
make openapi
git add frontend/openapi.json frontend/src/api/schema.d.ts
```

**CI safety**: the frontend CI job runs `git diff --exit-code` on these files — regenerating and committing them here prevents a CI red on the PR.

**Commit**: `chore(config-editor): regenerate OpenAPI schema for config routes`

### 4.2 — Ecosystem config env vars (`ecosystem.config.js`)

**Files**:

- Modify: `ecosystem.config.js` (repo root — `/Users/izno/dev/PersonalScraper/ecosystem.config.js`; the torrentmate-web blocks live here, NOT in `~/dev/ecosystem.config.js`)

**Changes**:

1. **Staging block** (`torrentmate-web-staging`):

   ```js
   env: {
     PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
     PERSONALSCRAPER_WEB_ROLE: "staging",   // NEW — S4 enforced 403 on writes
     // ... existing env vars ...
   }
   ```

   Update the existing comment `// S1 is read-only → real data is safe` to:
   `// S4 enforced read-only via PERSONALSCRAPER_WEB_ROLE=staging → 403 on config writes`

2. **Prod block** (`torrentmate-web`):
   ```js
   env: {
     PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
     PERSONALSCRAPER_PM2_NAME: "torrentmate-web",  // NEW — restart-web target
     // ... existing env vars ...
   }
   ```

**Commit**: `chore(config-editor): add PERSONALSCRAPER_WEB_ROLE and PM2_NAME to ecosystem`

### 4.3 — Docs updates

**Files**:

- Modify: `docs/reference/web-ui.md` — add S4 section after S3 maint-dash section
- Modify: `docs/reference/config-overlay-layout.md` — de-stale:
  - Overlays count: 16 → 18 (add `watch_seed.json5`, `web.json5` to the listing; `acquire.json5` is already documented at line 89)
  - Key ownership table: add rows for `watch_seed` → `watch_seed.json5`, `web` → `web.json5`
  - Update text references: "16 overlays" → "18 overlays", "17 config files" → "19 config files"
- Modify: `docs/reference/runbook-post-merge.md` — add entries:
  - "After S4 deploy: ensure `PERSONALSCRAPER_WEB_ROLE=staging` set on staging PM2 app"
  - "After S4 deploy: ensure `PERSONALSCRAPER_PM2_NAME=torrentmate-web` set on prod PM2 app"
  - "After S4 deploy: `pm2 restart torrentmate-web && pm2 restart torrentmate-web-staging`"

**Commit**: `docs(config-editor): add S4 section to web-ui, de-stale config-overlay-layout, update runbook`

### 4.4 — Executable ACCEPTANCE criteria

**Files**:

- Create: `docs/features/config-editor/ACCEPTANCE.md`

**Format** (per `docs/reference/feature-lifecycle.md` — every criterion is an executable shell command with documented expected output):

````markdown
# Config Editor — ACCEPTANCE

## ACC-01: Reject invalid config write

```bash
curl -s -X PUT "http://localhost:8710/api/config/files/paths.json5" \
  -H "Content-Type: application/json" \
  -H "X-Requested-With: TorrentMate" \
  -b tm_session=$SESSION \
  -d '{"values":{"staging_dir":"not/a/valid/paths/config"},"base_sha256":"0000"}'
# Expected: 422, detail contains Pydantic loc paths, file untouched (sha256 unchanged)
```
````

## ACC-02: Accept valid write, backup exists

````bash
# Read current values, modify one field, PUT back with correct sha256
# Expected: 200, .backups/paths.json5.{ts}.json5 exists, sha256 changed

## ACC-03: Staging 403 on write
```bash
curl -s -X PUT "http://localhost:8711/api/config/files/paths.json5" ...
# Expected: 403, body {"detail":"read-only"}
````

## ACC-04: 412 on stale base_sha256

# Expected: 412, body {"detail":"file modified since last read"}

## ACC-05: Secrets is_set flip without echo

# PUT a secret value → GET secrets → is_set=true for that key, value absent

# Expected: 200 on PUT, secrets response has no value field, is_set toggled

## ACC-06: Status reports staleness after write

# GET status before write → restart_required=false, stale_files=[]

# PUT a file → GET status → restart_required=true, stale_files includes file

# Expected: status diff as described

## ACC-07: Restart endpoint schedules restart

# POST /api/config/restart-web

# Expected: 202, body {"status":"scheduled"}

````

**Commit**: `test(config-editor): add executable ACCEPTANCE shell criteria`

### 4.5 — Full quality gate

**Commands** (run sequentially, all must pass):
```bash
make lint          # ruff + mypy + check_logging — zero errors
make test          # all tests pass (compare count vs baseline; 0 failed/errors)
make check         # lint + test + module-size + typed-api guardrails
python -c "import personalscraper"  # smoke test
````

**Additional checks**:

- [ ] `rg "from personalscraper.commands.web import _write_env_keys" -t py personalscraper/` returns zero (old import path cleaned)
- [ ] `rg "_write_env_keys" -t py personalscraper/` returns only `envfile.py` definition + `commands/web.py` import from new location
- [ ] `rg "ComingSoon.*Configuration\|config.*ComingSoon" -g '*.tsx' frontend/src/` returns zero (stub replaced)
- [ ] `git status` — only planned files modified; no accidental edits
- [ ] Restart-impact architecture test passes: every `Config.model_fields` key is in `RESTART_IMPACT`

**Phase gate commit**: `chore(config-editor): phase 4 gate — integration, docs, acceptance`

## Post-phase: PR ready

After Phase 4 gate passes:

- All 4 phases complete → proceed to `/implement:feature-pr` (auto-invoked)
- PR body must reference DESIGN.md and this plan directory
- CI must be green before `/implement:pr-review`
