# Phase 1 — Read Routes + Models

## Gate

- [ ] `make check` — lint + test + module-size + typed-api guardrails, zero errors
- [ ] `make openapi` — regenerate `frontend/openapi.json` + `frontend/src/api/schema.d.ts`
- [ ] Commit the regen files with `chore(acq-watch): phase 1 gate — read routes + models`
- [ ] Residual import grep: zero matches for any stale import paths

## Objectives

1. Wire a web-side `AcquireStore` read path — open the shared WAL `acquire.db` at
   `config.acquire.db_path`, read lock-free (no `BEGIN IMMEDIATE`, no `FileLock`,
   no detached runner, no event projection — unlike S6). Reads use the existing
   `ConcreteAcquireStore` via `store.follow.*`, `store.wanted.*`, `store.seed.*`,
   `store.ratio.*`, `store.watch.*`.

2. Expose four `GET` endpoints under `/api/acquisition/` — followed list, wanted
   queue (paginated), obligations panel, and watcher status.

3. Pydantic `response_model` on every route → OpenAPI gen → typed
   `frontend/src/api/schema.d.ts`.

4. Route tests: auth (401 without session), shape (response matches model),
   staging-allowed (200 on staging), fail-soft (empty lists/nulls on DB error,
   never 500), pagination (wanted endpoint).

## DESIGN gotchas (carry into every sub-phase)

- **DIRECT acquire.db read** — NOT an event projection. Open `ConcreteAcquireStore`
  at `config.acquire.db_path`, reads are lock-free (WAL). No `_write_tx` on reads.
  No detached runner. No event projection (unlike S6 registry → projection).
- **guarded_api mount** — the acquisition router is included in `guarded_api`
  (`APIRouter(dependencies=[Depends(require_session)])`) in `app.py`. Auth is
  inherited, never per-route `Depends(require_session)`.
- **Reads = no XRW + staging-allowed** — `GET` routes do NOT depend on
  `require_x_requested_with` or `require_not_staging`. They work on both prod
  and staging.
- **Epoch-float timestamps** — all timestamps are Unix-epoch `float` (matching
  the `acquire.db` schema: `added_at`, `enqueued_at`, `last_search_at`,
  `updated_at`, `last_successful_run_at`). Pydantic models use `float`.
- **Fail-soft reads** — a DB read error returns empty lists / nulls, never 500.
  Wrap each `store.*` call in try/except, log a warning, return the empty shape.
- **Reuse existing watcher route** — S7 does NOT add a new watcher route. The
  `/api/acquisition/status` endpoint surfaces `watcher_enabled` (from the
  `watcher.paused` sentinel) and `last_successful_run_at` (from
  `store.watch.get_last_successful_run_at()`). The toggle is the existing
  `POST /api/pipeline/watcher`. The `recent_runs` field queries `library.db`'s
  `pipeline_run` table filtered to `trigger='watcher'` — open a fresh read-only
  connection (same pattern as `pipeline_history`).
- **quality_profile_json is READ-ONLY** — surface it in the response but never
  expose an editor (RP3a deferred, backend doesn't consume it).

## Files to create

| File                                        | Purpose                                           |
| ------------------------------------------- | ------------------------------------------------- |
| `personalscraper/web/models/acquisition.py` | Pydantic response models for all 4 endpoints      |
| `personalscraper/web/routes/acquisition.py` | 4 `GET` endpoints with `AcquireStore` read wiring |

## Files to modify

| File                         | Change                                                              |
| ---------------------------- | ------------------------------------------------------------------- |
| `personalscraper/web/app.py` | Mount `acquisition_router` in `guarded_api` (after registry router) |

## Models to define (`personalscraper/web/models/acquisition.py`)

```python
"""Pydantic models for the acquisition API (acq-watch feature).

See docs/features/acq-watch/DESIGN.md §3.2–3.3 for the route contracts these
models serve.
"""

from __future__ import annotations

from pydantic import BaseModel


class MediaRefResponse(BaseModel):
    """Provider-ID key exposed in API responses (tvdb_id primary)."""
    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None


class FollowedSeriesItem(BaseModel):
    """A single followed series in the list response."""
    id: int
    title: str
    media_ref: MediaRefResponse
    active: bool
    cadence: dict | None = None          # parsed from cadence_json
    added_at: float                       # epoch seconds
    wanted_pending: int                   # COUNT from wanted table
    quality_profile: dict | None = None   # read-only, parsed from quality_profile_json


class FollowedResponse(BaseModel):
    """Response for GET /api/acquisition/followed."""
    items: list[FollowedSeriesItem]


class WantedItemResponse(BaseModel):
    """A single wanted item in the paginated list."""
    id: int
    title: str                          # joined from followed_series
    kind: str                           # "movie" | "episode"
    season: int | None = None
    episode: int | None = None
    status: str                         # "pending" | "searching" | "grabbed" | "done" | "abandoned"
    attempts: int
    enqueued_at: float                  # epoch seconds
    last_search_at: float | None = None # epoch seconds


class WantedResponse(BaseModel):
    """Paginated response for GET /api/acquisition/wanted."""
    items: list[WantedItemResponse]
    total: int
    page: int
    page_size: int


class ObligationItem(BaseModel):
    """A seed obligation with its current ratio state."""
    info_hash: str
    source_tracker: str
    dispatched_path: str | None = None
    min_seed_time_s: int
    min_ratio: float
    added_at: float                     # epoch seconds
    satisfied_at: float | None = None   # epoch seconds
    breached_at: float | None = None    # epoch seconds
    released_at: float | None = None    # epoch seconds
    # Joined from ratio_state (may be None if no ratio recorded)
    observed_ratio: float | None = None
    accumulated_seed_time_s: int | None = None
    hnr_count: int | None = None


class ObligationsResponse(BaseModel):
    """Response for GET /api/acquisition/obligations."""
    items: list[ObligationItem]


class RecentRun(BaseModel):
    """A recent watcher-triggered pipeline run summary."""
    run_uid: str
    started_at: float                   # epoch seconds
    ended_at: float | None = None       # epoch seconds
    outcome: str | None = None          # "success" | "error" | "killed" | None


class AcquisitionStatusResponse(BaseModel):
    """Response for GET /api/acquisition/status."""
    last_successful_run_at: float | None = None  # epoch seconds
    watcher_enabled: bool
    recent_runs: list[RecentRun] = []
```

## Routes to define (`personalscraper/web/routes/acquisition.py`)

```python
"""Acquisition REST routes (acq-watch feature).

Four GET endpoints under /api/acquisition/ exposing the followed-series list,
wanted queue, seed obligations, and watcher status.  Fed by direct reads of
the shared WAL acquire.db — NOT an event projection (unlike S6).

All routes are guarded by require_session inherited from the parent
guarded_api router (registration in app.py).  Auth dependencies are NOT
added per-route — the auth perimeter is a single dependency at registration
time, per docs/reference/web-ui.md §6 (the single authority for this
convention; R14/R24).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException, Query, Request

from personalscraper.acquire.store import ConcreteAcquireStore
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.web.models.acquisition import (
    AcquisitionStatusResponse,
    FollowedResponse,
    FollowedSeriesItem,
    MediaRefResponse,
    ObligationItem,
    ObligationsResponse,
    RecentRun,
    WantedItemResponse,
    WantedResponse,
)

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])
logger = get_logger(__name__)

_MAX_PAGE_SIZE = 200
_WATCHER_RECENT_RUNS = 10


def _get_acquire_store(request: Request) -> ConcreteAcquireStore:
    """Extract the configured AcquireStore from the application state.

    The store was built and stored on app.state at boot — same pattern as
    the registry projection.  Returning the raw ConcreteAcquireStore is
    DESIGN-CONFORM: S7 reads + writes acquire.db directly, via the store's
    lock-free reads and BEGIN IMMEDIATE writes.
    """
    return cast(ConcreteAcquireStore, request.app.state.acquire_store)


def _get_db_path(request: Request) -> Path:
    """Extract the resolved indexer database path (for pipeline_run queries)."""
    return cast(Path, request.app.state.config.indexer.db_path)
```

### GET /api/acquisition/followed

```
Query: active=all|active|inactive (default: active)
Response: FollowedResponse{items: FollowedSeriesItem[]}

For each followed_series row:
- Parse media_ref_json → MediaRefResponse
- Parse cadence_json → dict | None
- Parse quality_profile_json → dict | None
- Run a cheap SELECT COUNT(*) FROM wanted WHERE followed_id=? AND status IN ('pending','searching')
  for wanted_pending
- Filter by active flag based on query param
```

Fail-soft: wrap the entire handler in try/except — log warning, return
`FollowedResponse(items=[])`.

### GET /api/acquisition/wanted

```
Query: status=all|pending|searching|grabbed|done|abandoned (default: all)
       page=1 (default, >= 1)
       page_size=50 (default, clamped to [1, _MAX_PAGE_SIZE])
Response: WantedResponse{items, total, page, page_size}

Joins wanted ← followed_series ON followed_id to get title.
Orders by enqueued_at DESC.
```

Fail-soft: return `WantedResponse(items=[], total=0, page=page, page_size=page_size)`.

### GET /api/acquisition/obligations

```
Query: status=all|pending|breached|satisfied (default: all)
Response: ObligationsResponse{items: ObligationItem[]}

LEFT JOIN ratio_state ON seed_obligation.source_tracker = ratio_state.tracker_name
pending = satisfied_at IS NULL AND breached_at IS NULL
breached = breached_at IS NOT NULL
satisfied = satisfied_at IS NOT NULL
```

Fail-soft: return `ObligationsResponse(items=[])`.

### GET /api/acquisition/status

```
Response: AcquisitionStatusResponse{last_successful_run_at, watcher_enabled, recent_runs}

- last_successful_run_at: store.watch.get_last_successful_run_at() (float | None)
- watcher_enabled: not (data_dir / "watcher.paused").exists()
- recent_runs: last N pipeline_run rows WHERE trigger='watcher' from library.db,
  ordered by started_at DESC; same open-read pattern as pipeline_history (fresh
  sqlite3.connect with closing, apply_pragmas, row_factory=Row)
```

## Tests to add

| File                                             | Tests                                                      |
| ------------------------------------------------ | ---------------------------------------------------------- |
| `tests/unit/web/routes/test_acquisition_read.py` | 4 endpoint tests + auth + staging + fail-soft + pagination |

### Test structure (pytest + FastAPI TestClient)

Use the existing `TestClient` pattern from `tests/unit/web/` — create a test
app with a `ConcreteAcquireStore` pointing at a temp `acquire.db`, seed known
rows, and assert response shapes.

Key test cases:

1. **GET /api/acquisition/followed — authed, default (active only)**
   - Seed 2 active + 1 inactive FollowedSeries; assert 2 items returned, each
     has id/title/media_ref/active/cadence/added_at/wanted_pending/quality_profile.
   - Assert inactive item is NOT in the response.

2. **GET /api/acquisition/followed?active=all**
   - Assert all 3 items returned.

3. **GET /api/acquisition/followed — unauthenticated**
   - No `tm_session` cookie → 401.

4. **GET /api/acquisition/followed — staging allowed**
   - Set `PERSONALSCRAPER_WEB_ROLE=staging` → 200 (not 403), reads are staging-safe.

5. **GET /api/acquisition/wanted — paginated**
   - Seed 55 wanted items; request page=1, page_size=50 → assert items=50, total=55, page=1.
   - Request page=2, page_size=50 → assert items=5.

6. **GET /api/acquisition/wanted?status=pending**
   - Seed mixed statuses; assert only pending items returned.

7. **GET /api/acquisition/obligations — default (all)**
   - Seed 2 obligations + 1 ratio_state; assert LEFT JOIN populates observed_ratio.

8. **GET /api/acquisition/status**
   - Seed watch_state (last_successful_run_at); assert the value surfaces.
   - Assert watcher_enabled reflects the watcher.paused sentinel.
   - Seed pipeline_run rows with trigger='watcher'; assert recent_runs populated.

9. **Fail-soft: DB error**
   - Delete acquire.db mid-test → surface empty lists, NOT 500.

## app.py modification

After the registry router mount, add:

```python
from personalscraper.web.routes.acquisition import router as acquisition_router
guarded_api.include_router(acquisition_router)
```

Also add to `create_app`:

```python
from personalscraper.acquire.store import build_acquire_store
app.state.acquire_store = build_acquire_store(config.acquire)
```

The `AcquireStore` is lazy — building it opens nothing. The first read opens
the connection under the brief migration leaf lock, then stays open. No
lifetime `FileLock` is held; the `acquire.db.lock` is only the brief
open+migrate lock.
