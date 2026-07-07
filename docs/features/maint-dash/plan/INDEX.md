# S3 Maintenance Dashboard — Implementation Plan

> **Target**: TorrentMate web UI S3 (`maint-dash`, ticket #182)
> **SemVer**: bump 0.41.0 → **0.42.0** (minor, `feat`)
> **Codename**: `maint-dash`
> **DESIGN**: `docs/features/maint-dash/DESIGN.md`
> **Base branch**: `feat/maint-dash`
> **Baseline SHA**: `b47bd9eb7`

## Global Constraints (from DESIGN §0)

- **Single trigger authority**: every write action through `pipeline.lock` (same as Watcher + S2).
- **Sync handlers**: new routes are sync `def` on FastAPI threadpool; panel GETs use WAL read-only SQLite.
- **Auth + CSRF**: all `/api/*` under `require_session`; POST mutating routes require `X-Requested-With: TorrentMate` header.
- **DS-strict frontend**: shadcn + TanStack + domain primitives; zero raw hex/px; FR copy; machine tokens EN.
- **Pre-1.0**: no back-compat burden — `pipeline_run` evolves in-place via additive migration 012.
- **Typed contract**: Pydantic response models → `make openapi` → committed `frontend/openapi.json` + `schema.d.ts` (CI drift guard).
- **Commit format**: `type(maint-dash): description` (Conventional Commits, codename scope).
- **\_run_uid-is-None test bugs**: S2 tests assert `run_uid` on `StatusResponse` but factory uses `None` — don't paper over those pre-existing test bugs, keep the `StatusResponse` extension additive.
- **Staging validation only**: never run a local server on ports 8710/8711 (S2 rule).

## Key Codebase Ground Truth (verified against HEAD)

| Item                   | Path                                                                                                      | Confirmed                                                                                                                                           |
| ---------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Last indexer migration | `personalscraper/indexer/migrations/011_pipeline_run.sql`                                                 | 011, next = 012 ✓                                                                                                                                   |
| `pipeline_run` columns | `run_uid, trigger, dry_run, started_at, ended_at, outcome, steps_json, error, pid`                        | 9 cols                                                                                                                                              |
| Library CLI count      | `@app.command` registrations in `personalscraper/commands/library/*.py`                                   | **25** commands incl. `library-scan` + `library-backfill-ids` (`__all__` is stale at 23 — do NOT use it as ground truth; DESIGN §4.1 updated to 25) |
| Disk scanner           | `personalscraper/dispatch/disk_scanner.py` → `DiskStatus(is_mounted, free_space_gb)`                      | ✓                                                                                                                                                   |
| Guarded API mount      | `personalscraper/web/app.py:114-123` — `guarded_api = APIRouter(dependencies=[Depends(require_session)])` | ✓                                                                                                                                                   |
| S2 history route       | `personalscraper/web/routes/pipeline.py` — `GET /api/pipeline/history` + `/history/{run_uid}`             | ✓                                                                                                                                                   |
| S2 models              | `personalscraper/web/models/pipeline.py` — `RunSummary`, `RunDetail`, `PipelineOutcome`                   | ✓                                                                                                                                                   |
| Frontend router        | `frontend/src/router.tsx:48-50` — `/maintenance` → `ComingSoon` stub                                      | ✓                                                                                                                                                   |
| DS components          | `frontend/src/components/ds/` — `StatPanel`, `StatusDot`, `LogLine`                                       | ✓                                                                                                                                                   |

## Phases

| #   | Phase                      | File                                                                     | Sub-phases | Status |
| --- | -------------------------- | ------------------------------------------------------------------------ | ---------- | ------ |
| 1   | DB + Registry              | [phase-01-db-registry.md](phase-01-db-registry.md)                       | 3          | [ ]    |
| 2   | Panels Backend             | [phase-02-panels-backend.md](phase-02-panels-backend.md)                 | 3          | [ ]    |
| 3   | Actions Backend            | [phase-03-actions-backend.md](phase-03-actions-backend.md)               | 4          | [ ]    |
| 4   | History Unification        | [phase-04-history-unification.md](phase-04-history-unification.md)       | 3          | [ ]    |
| 5   | Frontend                   | [phase-05-frontend.md](phase-05-frontend.md)                             | 4          | [ ]    |
| 6   | Deploy + Docs + ACCEPTANCE | [phase-06-deploy-docs-acceptance.md](phase-06-deploy-docs-acceptance.md) | 3          | [ ]    |

## Implementation Flow

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
(DB+Reg)    (Panels)    (Actions)   (History)   (Frontend)  (Ship)
```

Each phase opens with a **Gate** section listing what the prior phase must produce. Phases 2 and 3 are independent once Phase 1 is done (they touch disjoint files), but the DESIGN lists them in dependency order: history unification (Phase 4) reuses model extensions from panels (Phase 2) and action records from Phase 3.
