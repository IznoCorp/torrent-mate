# S4 — Web UI Config Editor — DESIGN

**Codename**: `config-editor`
**Ticket**: #183 (`[S4] Web UI — éditeur de config`, wave 6, P2, depends on #158/S1 — shipped)
**Type**: feat — **SemVer**: minor, 0.42.0 → 0.43.0
**Date**: 2026-07-07

## 1. Goal

A visual, schema-validated editor for the `config/` JSON5 overlay files (plus a masked
`.env` secrets panel), served by the TorrentMate web UI at `/config`. Every save is
validated against the full Pydantic `Config` model **before** touching disk, written
atomically with a backup, and surfaced with honest apply semantics: engine consumers
(pipeline runs, maintenance actions, PM2 jobs) pick the new config up on their next
fresh process spawn — only the web daemon itself reads stale until restarted, which the
UI reports and can trigger explicitly.

## 2. Decisions (user-validated 2026-07-07)

| #   | Decision                                         | Choice                                                                                                                                                                                                                                                                |
| --- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Save semantics (the roadmap "reload sûr" caveat) | **Write-only + restart badge.** Validate + atomic write. No hot-reload of the web daemon's in-memory `Config`; no RP8 front-running. UI shows a "restart required" banner when the daemon's boot config is stale, plus an explicit "Restart web daemon" action (PM2). |
| D2  | Editor UX                                        | **Schema-driven forms** generated from `Config.model_json_schema()` (S3 `ActionForm` pattern generalized). Comment loss on rewritten files accepted (existing `init-config` precedent); only the file being saved is rewritten.                                       |
| D3  | Secrets                                          | **Included, masked.** `.env` panel via the existing `_write_env_keys` seam: write-only values, `is_set` indicator, never echoed back, always restart-flagged.                                                                                                         |
| D4  | Topology                                         | **Staging read-only + git assumed.** All write endpoints return 403 on the staging deployment (shared `PERSONALSCRAPER_CONFIG` with prod). Git diffs on the 5 tracked config files are accepted as an audit trail (manual commits).                                   |

Roadmap caveat resolution: S4 does **not** bound itself to providers config, and does
**not** build a reload seam. It chose the third honest option the code made available:
the per-process fresh-load model already gives next-run semantics to the whole engine,
so only web-daemon staleness needs handling — via restart, not reload. RP8 (wave 7)
remains untouched and un-front-run; the provider registry stays immutable.

## 3. Verified ground truth (exploration sweep 2026-07-07)

- Config = master `config.json5` + **18 overlays** (19 files; `docs/reference/config-overlay-layout.md` is stale at 16 — fixed by this feature). Each non-local overlay owns distinct top-level keys (`ConfigConflictError` otherwise); optional `local.json5` merges last, last-wins.
- Validation is Pydantic v2, `extra="forbid"`, field + cross-reference model validators. `Config.model_json_schema()` works out of the box (28 top-level properties, 59 `$defs`).
- `json5` lib is parse-only: comments are not preserved on rewrite. Precedent: `personalscraper/commands/init_config.py` already rewrites `paths.json5` via `json5.dumps` (non-atomic there; S4's write path is atomic).
- Web daemon loads config once at boot (`app.state.config`); AppContext is frozen; **zero reload mechanism exists** (no SIGHUP, immutable provider registry). Pipeline (S2) and maintenance (S3) runs are fresh subprocesses that re-read `config/` from disk.
- `loader._PROJECT_ROOT` is a mutable module global (single-threaded assumption stated in the loader) — unsafe to run `load_config_dir` for a _candidate_ config inside FastAPI's threadpool without a seam.
- Prod (`torrentmate-web`, port 8710) and staging (`torrentmate-web-staging`, `web --port 8711`) both point `PERSONALSCRAPER_CONFIG` at `/Users/izno/dev/PersonalScraper/config`. 5 files there are git-tracked (`config.json5`, `indexer.json5`, `tracker.json5`, `watch_seed.json5`, `web.json5`).
- Atomic-write utilities exist (`io_utils` tmp+`os.replace` patterns). `_write_env_keys()` in `personalscraper/commands/web.py` does an atomic, comment/order-preserving `.env` upsert.
- Frontend: `/config` route exists as `ComingSoon` (nav item disabled with S4 chip). Typed OpenAPI client (`schema.d.ts`), TanStack Query v5, shadcn/ui + DS components. No code-editor dep; `zod` and `@tanstack/react-form` are in deps but unused — S4 does not adopt them (see §6).

## 4. Backend

### 4.1 Validation seam (`personalscraper/conf/`)

- Promote `_PROJECT_ROOT` from module global to a `ContextVar` (the loader's own comment
  anticipates this). No behavior change for the CLI path — regression-covered.
- New pure entry point (name indicative):
  `validate_candidate(config_dir: Path, replaced: Mapping[str, dict]) -> tuple[Config, list[str]]`
  — reads the current overlay files, substitutes the candidate payload(s) in memory,
  runs the same merge + Pydantic build as `load_config_dir`, returns `(config, warnings)`
  or raises the same validation errors. Differences from the real loader: the
  library.db category-orphan check is skipped (no DB touch); filesystem probes that are
  genuine validation (WAL-safety of `db_path`) still run.

### 4.2 Routes — `personalscraper/web/routes/config.py` (S3 conventions: guarded router, `{detail}` errors)

| Route                          | Behavior                                                                                                                                                                                                                                                  |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/config/schema`       | `Config.model_json_schema()` + ownership map `{top_level_key → file}` (derived live from the overlays array) + restart-impact map. Static per boot.                                                                                                       |
| `GET /api/config/files`        | Per file: name, owned keys, `sha256`, mtime, size, `shadowed_keys` (keys overridden by `local.json5`).                                                                                                                                                    |
| `GET /api/config/files/{name}` | Parsed values (`json5.load`) + `sha256` + shadowed keys.                                                                                                                                                                                                  |
| `PUT /api/config/files/{name}` | Body `{values, base_sha256}`. Order: 403 if read-only role → 412 if `base_sha256` no longer matches the file bytes → validate candidate via §4.1 (422 with Pydantic `loc` paths on failure) → backup → atomic write → 200 `{warnings, restart_required}`. |
| `POST /api/config/validate`    | Same validation, no write. Used by the form's explicit "Valider" action.                                                                                                                                                                                  |
| `GET /api/config/status`       | `{role, read_only, restart_required, stale_files}` — sha256 of each file at daemon boot vs now.                                                                                                                                                           |
| `GET /api/config/secrets`      | Catalog from `.env.example` (key, description, `is_set`). **Values never returned.**                                                                                                                                                                      |
| `PUT /api/config/secrets`      | `{KEY: value, …}`, keys must be in the catalog allowlist. Upsert via the `.env` seam. Values never logged. Always `restart_required: true`.                                                                                                               |
| `POST /api/config/restart-web` | 202; spawns a detached `pm2 restart <name>` after a short delay so the response flushes. PM2 app name from `PERSONALSCRAPER_PM2_NAME` env; endpoint 404s (and the UI hides the button) when unset. 403 on staging.                                        |

Writes are additionally serialized in-process (lock) — the sha256 precondition covers
cross-process editors (vi, git).

### 4.3 Write path

- Backup first: `config/.backups/{name}.{utc-ts}.json5`, prune to last 10 per file
  (`.backups/` falls under the existing `config/` gitignore).
- Atomic write: tmp sibling + `os.replace` + fsync, `json5.dumps(values, indent=2)`
  prefixed with a generated header comment (`// Written by TorrentMate config editor
<UTC ts> — hand-written comments are not preserved.`).

### 4.4 Restart-impact classification

Static map, top-level key → `restart_required` (keys the web daemon itself consumes:
`web`, `paths`, `indexer` → true; engine-only keys → false, "effective next run").
Unknown keys default to `true` (fail-safe). An architecture test asserts every
`Config.model_fields` top-level key is classified — a new config section without a
classification fails the suite.

### 4.5 Role gating & secrets seam

- New env var `PERSONALSCRAPER_WEB_ROLE` (`prod` default; `staging` set in the staging
  block of `ecosystem.config.js`, whose "S1 is read-only → real data is safe" comment is
  updated — S4 enforces read-only via 403 instead of assumption).
- `_write_env_keys` moves out of `personalscraper/commands/web.py` into a shared module
  (e.g. `personalscraper/conf/envfile.py`); `web set-password` and the secrets route both use it.

## 5. Frontend (`/config`, replaces ComingSoon; nav item enabled)

- **Layout**: file list (grouped by domain, dirty + restart badges) + form panel.
  Read-only banner on staging; restart banner driven by `GET /api/config/status`.
- **SchemaForm renderer** (the core new component): walks the JSON Schema resolving
  `$defs`: string→`Input`, int/number→numeric `Input`, bool→`Switch`, enum→`Select`,
  `array<primitive>`→list editor, `array<object>` (disks, category_rules…)→card list
  add/remove, nested object→collapsible section, `dict<string, X>` (genre_mapping,
  staging_dirs…)→key/value rows. Non-renderable nodes fall back to a JSON textarea with
  a parse check. `local.json5` (free-form by design) renders entirely through the fallback.
- Light client-side hints from the schema (required/type/enum/pattern); authoritative
  validation is server-side — 422 `loc` paths map errors back to fields.
- Save: PUT with `base_sha256`; on 412, conflict dialog offering reload. Shadowed-key
  warning chip when `local.json5` overrides an edited key.
- Secrets tab: masked write-only inputs + `is_set` chips. Restart button behind a
  confirm dialog; the existing WS backoff + query retry absorb the restart gap.
- Data layer: existing typed `apiFetch` + TanStack Query conventions
  (`configKeys.*` tuples); no new frontend dependency.

## 6. Non-goals

- No hot-swap / reload of the running web daemon's `Config` (and no RP8 primitive).
- No comment preservation in rewritten JSON5 files.
- No new frontend deps (no CodeMirror/monaco raw-text mode; no zod / @tanstack/react-form adoption).
- No config migration tooling, no multi-user merge beyond the hash precondition.
- No editing of `config.example/` templates, `.env` keys outside the catalog, or files outside `config/`.

## 7. Testing

- **conf seam**: `validate_candidate` accept/reject/cross-ref cases, ContextVar isolation
  under concurrent validation, loader regression (CLI path unchanged).
- **envfile**: upsert preserves comments/order, atomic replace, `set-password` parity.
- **routes**: auth guard, staging 403s, 412 precondition, 422 error shape (`loc` paths),
  secrets never-echo (response + logs), backup+atomic write against a tmp config dir,
  restart endpoint with mocked spawn, restart-impact architecture test (§4.4).
  CI-safety: web route tests patch `load_config` / use tmp config dirs (no real `config/` in CI).
- **frontend**: SchemaForm renderer per field kind + nested structures, save/conflict/
  validation-error flows (vitest, existing patterns).
- **ACCEPTANCE**: executable `ACC-NN` shell criteria (curl with session cookie): reject an
  invalid write (422, file untouched), accept a valid write (backup exists, sha changes,
  status reports staleness), staging 403, secrets is_set flip without echo.

## 8. Deliverables checklist

- `personalscraper/conf/`: ContextVar seam, `validate_candidate`, `envfile.py`.
- `personalscraper/web/routes/config.py` + registry/impact map + tests.
- `frontend/`: SchemaForm + `/config` page + nav enable + tests.
- `make openapi` regenerated (`frontend/openapi.json` + `schema.d.ts` committed — CI drift guard).
- `ecosystem.config.js`: staging `PERSONALSCRAPER_WEB_ROLE`, prod `PERSONALSCRAPER_PM2_NAME`, comment update.
- Docs: `web-ui.md` S4 section; `config-overlay-layout.md` de-staled (18 overlays, watch_seed + web ownership rows); `commands.md` if any CLI surface changes.
- `docs/reference/runbook-post-merge.md` checklist entries (env vars on PM2 apps, restart).
