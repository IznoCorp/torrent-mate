# DESIGN — S3 Maintenance dashboard (`maint-dash`)

**Wave**: TorrentMate web UI **S3** · **Ticket**: #182 · **Bump**: 0.41.0 → **0.42.0** (minor, `feat`)
**Builds on**: S1 (`tm-shell`) — FastAPI `personalscraper/web/`, JWT-cookie auth, Redis-Streams→WebSocket
live event relay, DS-aligned React shell — and S2 (`pipe-control`) — subprocess spawn +
`pipeline.lock` coordination, `pipeline_run` history table (migration 011), run status/history routes,
live log streaming over the S1 relay.

---

## 0. Cross-cutting rules (inherited from S1/S2, non-negotiable)

- **Single trigger authority**: every write action goes through the SAME `pipeline.lock` as the
  Watcher and S2 controls. No parallel writer. EventBus stays observe-only.
- **Sync engine, async only at the WS relay**: new routes are sync `def` handlers on the FastAPI
  threadpool; panel GETs use WAL-safe read-only SQLite connections (S2 §4 pattern).
- **Auth + CSRF**: all `/api/*` under `require_session`; every mutating POST carries the
  `X-Requested-With: TorrentMate` header guard.
- **DS-strict frontend**: shadcn + TanStack + domain primitives only; zero raw hex/px; FR-leading
  copy; machine tokens EN.
- **Pre-1.0**: no back-compat / migration-script burden — `pipeline_run` schema evolves in place
  (additive migration 012), S2 endpoints change semantics freely.
- **Typed contract pipeline**: Pydantic response models → `make openapi` → committed
  `frontend/openapi.json` + `schema.d.ts` (CI drift guard).

## 1. Overview & scope

The `/maintenance` screen (replaces the S1 « À venir » stub) is the operator's **health &
maintenance deck** for the library:

- **4 monitoring panels** (read-only, fast, no lock):
  1. **Disks** — per configured disk: mounted, free/total space, usage.
  2. **Locks & tmp orphans** — `pipeline.lock` state (held / stale = PID dead), `pipeline.pause`
     and `watcher.paused` sentinels with age, plus a **bounded** filesystem sweep for temporary
     prefixes (`_tmp_dispatch_*`, `_tmp_ingest_*`) on staging + disk roots.
  3. **Index health** — cheap SQL aggregates over `library.db` (counts, NFO status, repair queue,
     outbox lag, last scan run, soft-deleted, canonical NULLs).
  4. **Run history** — the S2 history table, **unified**: pipeline runs _and_ maintenance action
     runs in one filterable list.
- **Actions catalog** — ALL `library-*` CLI commands (25 at time of writing) exposed as web
  actions through a **typed backend registry** (curated options per command — no free-form flags).
  Write/long-running actions spawn as detached subprocesses recorded in `pipeline_run`
  (`kind='maintenance'`), same rails as S2.
- **Dry-run-first, backend-enforced**: destructive applies require a fresh successful dry-run with
  identical options (HTTP `428` otherwise). The UI mirrors the flow (Apply unlocked by a fresh
  dry-run).

Out of panel scope by design (they are _actions_, not panels): deep orphan analysis
(`library-clean` dry-run — full library walk, too slow for a dashboard GET) and deep index
diagnosis (`library-doctor`, 10 checks).

## 2. Architecture

```
            ┌───────────────────── /maintenance screen (React, DS) ─────────────────────┐
            │  DisksPanel  LocksPanel  IndexHealthPanel  RunHistory (S2 reuse + kind)   │
            │  ActionCatalog (grouped) → ActionForm (generated) → RunOutput (WS live)   │
            └──────┬────────────────────▲───────────────────▲──────────────▲────────────┘
   POST action/run │            GET panels│        WS (S1 relay)│           │ GET history?kind=
            ┌──────▼────────────────────┴────────────────────┴──────────────┴────────────┐
            │ FastAPI personalscraper/web/routes/maintenance.py (sync, guarded)           │
            │ disks · locks · index-health · actions · actions/{id}/run                   │
            │ + routes/pipeline.py: history gains ?kind= filter                           │
            └──┬──────────────────────┬──────────────────────────────┬────────────────────┘
     spawn     │              registry │ validate options              │ SELECT (WAL ro)
            ┌──▼───────────────────┐ ┌─▼──────────────────────────┐ ┌──▼──────────────────┐
            │ runner (python -m    │ │ web/maintenance/registry.py│ │ indexer DB           │
            │ …maintenance.runner) │ │ 25 typed action entries    │ │ pipeline_run (+kind, │
            │ row lifecycle + CLI  │ └────────────────────────────┘ │  command, options,   │
            │ subprocess + stdout  │                                │  output_tail) mig.012│
            │ → Redis stream       │                                └──────────────────────┘
            └──────────────────────┘
```

## 3. Engine / DB changes

### 3.1 `pipeline_run` extension (indexer migration 012 — additive)

| Column         | Type                               | Semantics                                                  |
| -------------- | ---------------------------------- | ---------------------------------------------------------- |
| `kind`         | `TEXT NOT NULL DEFAULT 'pipeline'` | `'pipeline'` (S2 runs) or `'maintenance'` (S3 actions)     |
| `command`      | `TEXT NULL`                        | action id, e.g. `library-clean` (NULL for pipeline runs)   |
| `options_json` | `TEXT NULL`                        | canonical JSON (sorted keys) of the validated options      |
| `output_tail`  | `TEXT NULL`                        | last ≤ 64 KiB of captured stdout+stderr (maintenance runs) |

Existing S2 columns (`run_uid`, `trigger`, `dry_run`, `started_at`, `ended_at`, `outcome`,
`steps_json`, `error`, `pid`) are reused as-is; `steps_json` stays NULL for maintenance runs.
Dry-run-first lookups compare `options_json` string equality (canonical serialization makes
equality reliable) — no extra hash column.

### 3.2 Maintenance runner — `personalscraper/web/maintenance/runner.py`

A thin generic wrapper executed as `python -m personalscraper.web.maintenance.runner`, spawned
detached by the POST handler (S2 spawn pattern: `subprocess.Popen(..., start_new_session=True)`,
`PERSONALSCRAPER_RUN_UID` env). It owns the run row lifecycle so the 25 CLI commands stay
**untouched**:

1. Insert `pipeline_run` row (`kind='maintenance'`, `command`, `options_json`, `dry_run`,
   `outcome='running'`, own `pid`).
2. Exec the real CLI (`personalscraper library-X …` args built from validated options) as a child
   subprocess, line-buffered.
3. Stream each stdout/stderr line to the Redis stream consumed by the S1→WS relay (same envelope
   as S2 live logs, tagged `run_uid`; exact envelope aligned with S2 relay code at implementation).
4. On exit: finalize row — `outcome='success'|'error'` from exit code, `ended_at`, `error` (tail of
   stderr on failure), `output_tail` (last ≤ 64 KiB combined).

Fail-soft: history/Redis write errors never abort the underlying command (S2 contract).

## 4. Backend — registry + routes (contracts)

### 4.1 Registry — `personalscraper/web/maintenance/registry.py`

One typed entry per command (Pydantic, serialized verbatim by `GET /actions`):

```python
class ActionOption(BaseModel):
    name: str                      # CLI option, e.g. "disk"
    type: Literal["str", "int", "bool", "enum"]
    enum_values: list[str] | None = None
    default: str | int | bool | None = None
    required: bool = False
    label: str                     # UI label (FR)
    help: str                      # UI helper text (FR)

class MaintenanceAction(BaseModel):
    id: str                        # "library-clean"
    title: str                     # FR display title
    description: str               # FR one-liner
    category: Literal["query", "scan", "repair", "clean", "analyze", "fix"]
    risk: Literal["ro", "write", "destructive"]
    long_running: bool
    dry_run: Literal["unsupported", "supported"]   # supported ⇒ UI/backends drive the flow
    options: list[ActionOption]
```

Initial classification (**to be re-verified command-by-command against the CLI signatures during
phase 1** — the CLI is ground truth, the table below is the design intent):

| risk                                                | commands                                                                                                                                                                                                            |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ro`                                                | library-status, library-search, library-show, library-analyze, library-recommend, library-report, library-doctor, library-ghost-audit                                                                               |
| `write` (DB-state)                                  | library-index, library-scan, library-init-canonical, library-backfill-ids, library-verify, library-repair, library-reconcile, library-relink, library-gc, library-fix-canonical-provider, library-fix-season-counts |
| `destructive` (deletes/rewrites user files or rows) | library-clean, library-validate (apply), library-rescrape, library-fix-nfo, library-fix-orphan-files, library-dedup-titles                                                                                          |

Curated options per command = the high-value targeting flags only (`--disk`, `--category`,
`--mode`, `--budget`, `--only`, `--scope`, `--limit`, query strings…) + the dry-run/apply toggle
where the CLI supports it. Interactive/plumbing flags (`--config`, `--db`, `--wait-for-lock`,
`--confirm-bulk-change`) are NOT exposed.

### 4.2 Routes — `personalscraper/web/routes/maintenance.py` (mounted in `guarded_api`)

| Method | Path                                             | Response model             | Semantics                                                                                                                                                                                                                                                                                     |
| ------ | ------------------------------------------------ | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/api/maintenance/disks`                         | `DisksResponse`            | Per disk (from `dispatch/disk_scanner.py`): `{id, label, mounted, free_gb, total_gb, used_pct}`                                                                                                                                                                                               |
| GET    | `/api/maintenance/locks`                         | `LocksResponse`            | `pipeline_lock: {held, pid, pid_alive, stale, age_s}` (stale = lock file present + PID dead), `pause: {present, age_s}`, `watcher_paused: {present, age_s}`, `tmp_orphans: [{path, prefix, age_s}]` from a bounded shallow sweep (staging category dirs + disk roots, depth ≤ 2, capped list) |
| GET    | `/api/maintenance/index-health`                  | `IndexHealthResponse`      | Cheap SELECTs: `{items, movies, shows, files, size_gb, nfo: {valid, invalid, missing}, repair_queue: {pending, oldest_age_s}, outbox: {pending, oldest_age_s}, last_scan: {run_uid?, mode, status, started_at, ended_at, stuck}, soft_deleted, canonical_null}`                               |
| GET    | `/api/maintenance/actions`                       | `ActionsResponse`          | The full registry (drives UI form generation)                                                                                                                                                                                                                                                 |
| POST   | `/api/maintenance/actions/{action_id}/run`       | `202 RunSpawned {run_uid}` | Body `{options: {…}, dry_run: bool}` — validate against registry, enforce rules below, spawn runner                                                                                                                                                                                           |
| GET    | `/api/pipeline/history` (S2, extended)           | `HistoryResponse`          | Gains `?kind=pipeline\|maintenance\|all` (default `all`); `RunSummary` gains `kind`, `command`                                                                                                                                                                                                |
| GET    | `/api/pipeline/history/{run_uid}` (S2, extended) | `RunDetail`                | Gains `kind`, `command`, `options_json`, `output_tail`                                                                                                                                                                                                                                        |

**POST error contract** (all `{"detail": …}`):

- `404` unknown `action_id`.
- `422` options failing registry validation (unknown key, bad enum, missing required).
- `409` write/destructive action while `pipeline.lock` is held, or another maintenance run is
  active (single concurrent maintenance run; RO actions bypass both checks).
- `428` destructive apply (`dry_run=false`) without a **fresh matching dry-run**: a
  `pipeline_run` row with `kind='maintenance'`, same `command`, same canonical `options_json`
  (ignoring the dry-run flag itself), `dry_run=1`, `outcome='success'`, `ended_at` within
  **30 minutes**. `detail` says which precondition failed.

Write/destructive actions hold `pipeline.lock` for their whole subprocess lifetime (acquired by
the CLI command itself where it already does; the runner acquires it otherwise — resolved
per-command in phase 1 against CLI ground truth, with the invariant: **no write action runs
without the lock**).

## 5. Frontend — `/maintenance` (replaces the « À venir » stub)

- **`pages/Maintenance.tsx`** — responsive grid, mobile-first:
  - `DisksPanel` — one card per disk (`StatPanel` + capacity bar), `StatusDot` unmounted/low-space.
  - `LocksPanel` — lock/sentinel states with age (stale lock highlighted `fail`), tmp-orphan list.
  - `IndexHealthPanel` — headline counts + `StatusDot` per sub-check (repair backlog, outbox lag,
    stuck scan); deep-links to the `library-doctor` action.
  - `RunHistoryPanel` — S2 history table component reused with `kind` filter chips
    (Tout / Pipeline / Maintenance) + `command` column for maintenance rows.
- **`ActionCatalog`** — actions grouped by `category`, badges for risk (`ro`/`write`/`destructive`)
  and long-running; opens **`ActionForm`**.
- **`ActionForm`** — generated from the registry entry (field renderers per option type:
  enum→Select, bool→Switch, int→Input, str→Input). Dry-run-first UX for `destructive`:
  **Dry-run** primary button; **Apply** disabled until a fresh successful dry-run with the current
  form values exists (mirrors the backend `428`; a `428` response re-locks the button and explains).
- **`RunOutput`** — live output for the spawned run: WS feed filtered on `run_uid` (S2 hook
  reuse), fallback to `output_tail` from run detail after completion.
- Panels via TanStack Query (`refetchInterval` ~10 s for locks, ~60 s for disks/index-health);
  actions via mutations; typed `apiFetch` on the regenerated `schema.d.ts`.

## 6. Testing

- **Unit**: registry integrity (25 entries, ids unique, options well-formed — a test asserting the
  registry covers exactly the CLI's registered `library-*` commands, so a future 25th command
  fails loudly); options validation; canonical `options_json` serialization; dry-run-first
  precondition query (fresh/stale/mismatched); lock rules; runner row lifecycle (mock subprocess).
- **Route tests**: FastAPI TestClient on all 5 maintenance routes + extended history routes —
  wrapped in `patch('personalscraper.conf.loader.load_config', …)` (CI has no `config/`).
- **Migration test**: 011→012 upgrade keeps S2 rows readable (`kind='pipeline'` default).
- **Frontend**: type-checks against regenerated `schema.d.ts`; manual E2E on staging via Chrome
  MCP (panels render, dry-run→apply flow, 428/409 surfaced).
- Every bug found during implementation gets a reproducing regression test (project rule).

## 7. Deploy / CI

- `make openapi` regen + commit `frontend/openapi.json` + `schema.d.ts` in the same phase as any
  route/model change (CI drift guard).
- Staging validation on `tm-staging.iznogoudatall.xyz` (push `staging`) before merge; **never** a
  local server on ports 8710/8711.
- Post-merge: prod auto-deploys from `main`; runbook-post-merge checklist (DB migration 012 runs
  lazily on first web start; no config keys added).

## 8. Non-goals (deferred)

- Scheduled/auto-remediation maintenance (cron-style) — operator-triggered only.
- Action queueing — concurrent conflicts are rejected (`409`), never queued.
- Bespoke per-command UIs beyond generated forms.
- Config editing (S4), insights/analytics visualizations beyond the health panel.
- Deep orphan/doctor results as _panels_ (they run as actions with history).

## 9. Phases (for the plan)

1. **DB + registry** — migration 012, registry module + models, canonical serialization.
2. **Panels backend** — disks / locks / index-health routes + tests.
3. **Actions backend** — actions listing, POST run (validation, 409/428 rules), runner, live
   output relay + tests.
4. **History unification** — S2 history/status extensions (`kind`, `command`) + tests.
5. **Frontend** — Maintenance page: 4 panels + catalog + generated forms + dry-run flow + run
   output; `make openapi` regen.
6. **Deploy rails + docs + ACCEPTANCE** — staging E2E, `docs/reference/web-ui.md` §S3 +
   `maintenance.md` update, executable ACC-NN.

## 10. ACCEPTANCE (sketch — executable ACC-NN, finalized in phase 6)

- ACC-01 `curl … GET /api/maintenance/disks` → 200, `.disks[0].free_gb` numeric.
- ACC-02 `curl … GET /api/maintenance/locks` → 200, `.pipeline_lock.held == false` (idle).
- ACC-03 `curl … GET /api/maintenance/index-health` → 200, `.items > 0`.
- ACC-04 `curl … GET /api/maintenance/actions | jq '.actions | length'` → 25.
- ACC-05 `curl … POST /api/maintenance/actions/library-status/run` → 202 + history row
  `kind='maintenance'`, `command='library-status'`, outcome success.
- ACC-06 destructive apply without prior dry-run → 428; after dry-run → 202.
- ACC-07 write action while `pipeline.lock` held → 409.
- ACC-08 `make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts`.
- ACC-09 unauthenticated GET `/api/maintenance/disks` → 401.
