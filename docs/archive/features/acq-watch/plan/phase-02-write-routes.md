# Phase 2 — Write Routes

## Gate

- [ ] `make check` — lint + test + module-size + typed-api guardrails, zero errors
- [ ] `make openapi` — regenerate `frontend/openapi.json` + `frontend/src/api/schema.d.ts`
- [ ] Commit the regen files with `chore(acq-watch): phase 2 gate — write routes`
- [ ] Residual import grep: zero matches for any stale import paths

## Objectives

1. Add `POST /api/acquisition/followed` — create (or reactivate) a followed series
   via direct `store.follow` write.

2. Add `PATCH /api/acquisition/followed/{id}` — update active flag or cadence
   via `store.follow.set_active` + direct `cadence_json` update.

3. Add `DELETE /api/acquisition/followed/{id}` — soft-unfollow via
   `store.follow.set_active(False)`.

4. All mutating routes: `require_not_staging` (staging → 403) +
   `require_x_requested_with` (CSRF → 400). Auth inherited from `guarded_api`.

5. Route tests: staging-guard, XRW-guard, dedup/reactivate, 409/404/422,
   cadence validation, mutation-checked guards (test the guard raises, not
   just the response status — the `require_not_staging` and
   `require_x_requested_with` dependencies must be called).

## DESIGN gotchas (carry into every sub-phase)

- **DIRECT acquire.db write** — via `store.follow.*` which internally uses
  `_write_tx` (BEGIN IMMEDIATE + busy_timeout=5000). The web process writes
  directly to the shared WAL `acquire.db`, serialized by SQLite's write lock —
  exactly like the pipeline/watcher. NO detached runner, NO event projection.
- **No web-side event emission** — follow writes do NOT emit `SeriesFollowed` /
  `SeriesUnfollowed` from the web process (deferred). The acting client
  re-fetches on the mutation response. The pipeline reads fresh DB at detect
  time. Cross-client live update is a follow-up.
- **Cadence editable, quality_profile_json READ-ONLY** — `PATCH` accepts
  `cadence` (validated, written to `cadence_json`). `quality_profile_json` is
  NEVER accepted in a write body — editing it would front-run an unshipped
  backend capability (RP3a). Surfaces read-only in Phase 1 responses.
- **Watcher control: reuse existing route** — S7 does NOT add a new watcher
  write route. The Acquisition page calls `POST /api/pipeline/watcher` (the
  pipeline watcher toggle). No new code needed for this in the backend.
- **Epoch-float timestamps** — `added_at` is set to `time.time()` at
  creation time, stored as-is in the DB (real/float column, matches schema).

## Files to modify

| File                                        | Change                                                                      |
| ------------------------------------------- | --------------------------------------------------------------------------- |
| `personalscraper/web/models/acquisition.py` | Add request models (CreateFollowRequest, UpdateFollowRequest, CadenceShape) |
| `personalscraper/web/routes/acquisition.py` | Add 3 mutating endpoints (POST/PATCH/DELETE)                                |

## Request models to add (`personalscraper/web/models/acquisition.py`)

```python
from pydantic import BaseModel, field_validator, model_validator


class CreateFollowRequest(BaseModel):
    """Request body for POST /api/acquisition/followed.

    At least one provider ID is required (422 otherwise).  title is optional
    — when omitted the backend auto-resolves it from the provider (Phase 1
    reads surface whatever was stored).  In S7 the web form will always
    send a title, but the route accepts None for programmatic clients.
    """
    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    title: str | None = None

    @model_validator(mode="after")
    def _at_least_one_id(self) -> CreateFollowRequest:
        if self.tvdb_id is None and self.tmdb_id is None and self.imdb_id is None:
            raise ValueError("At least one provider ID (tvdb_id, tmdb_id, or imdb_id) is required")
        return self


class CadenceShape(BaseModel):
    """Per-series search cadence override (editable).

    The shape mirrors what the backend effective_cadence resolver consumes
    from cadence_json.  The PATCH endpoint validates incoming cadence
    against this schema before writing to cadence_json.
    """
    interval_minutes: int
    # Future RP9/D2 fields added here (e.g. per-season windows).
    # For S7, interval_minutes is the only active field.


class UpdateFollowRequest(BaseModel):
    """Request body for PATCH /api/acquisition/followed/{id}.

    Every field is optional — only the provided fields are updated.
    cadence is validated against CadenceShape before writing to cadence_json.
    quality_profile_json is intentionally ABSENT (RP3a deferred — do NOT
    expose an editor until the backend consumes it).
    """
    active: bool | None = None
    cadence: CadenceShape | None = None
```

## Routes to add (`personalscraper/web/routes/acquisition.py`)

### POST /api/acquisition/followed

```
Body: CreateFollowRequest{tvdb_id?, tmdb_id?, imdb_id?, title?}
Response: 201 FollowedSeriesItem
Errors: 400 (missing XRW), 403 (staging), 409 (already active), 422 (no provider ID)

Logic:
1. Build a MediaRef from the provided IDs.
2. Call store.follow.find_by_ref(media_ref):
   - Found + active=True → 409 Conflict ("Already followed")
   - Found + active=False → reactivate: store.follow.set_active(id, True),
     return the reactivated item (store.follow.get(id)) with 201
   - Not found → create: build FollowedSeries(media_ref, title or "",
     added_at=time.time(), active=True), store.follow.add(series),
     get the new row by id, return 201
3. title auto-resolution from the provider is a follow-up (RP9/D2);
   for S7 the web client sends the title.
```

### PATCH /api/acquisition/followed/{id}

```
Path: {id} int (followed_series rowid)
Body: UpdateFollowRequest{active?, cadence?}
Response: 200 FollowedSeriesItem
Errors: 400 (missing XRW), 403 (staging), 404 (unknown id)

Logic:
1. store.follow.get(id) → None → 404
2. If active is provided: store.follow.set_active(id, active)
3. If cadence is provided: validate against CadenceShape (Pydantic does this
   automatically), then write json.dumps(cadence.model_dump()) to
   cadence_json via a direct UPDATE inside _write_tx:
   conn.execute("UPDATE followed_series SET cadence_json = ? WHERE id = ?",
                (json.dumps(cadence_dict), id))
4. Return store.follow.get(id) as FollowedSeriesItem
```

### DELETE /api/acquisition/followed/{id}

```
Path: {id} int (followed_series rowid)
Response: 204 No Content
Errors: 400 (missing XRW), 403 (staging), 404 (unknown id)

Logic:
1. store.follow.get(id) → None → 404
2. store.follow.set_active(id, False)  -- soft unfollow
3. Return 204
```

## Tests to add

| File                                              | Tests                                                            |
| ------------------------------------------------- | ---------------------------------------------------------------- |
| `tests/unit/web/routes/test_acquisition_write.py` | 3 endpoint tests + guards + dedup/409 + 404 + cadence validation |

### Key test cases

1. **POST /api/acquisition/followed — success (201)**
   - Send `{tvdb_id: 123, title: "Test Show"}` with XRW header.
   - Assert 201, response has id/title/media_ref/active=True.
   - Assert row exists in acquire.db with active=1.

2. **POST /api/acquisition/followed — dedup: reactivate (201)**
   - Pre-seed an inactive row with the same tvdb_id.
   - Assert 201, the existing row is now active=1 (reactivated, not duplicated).

3. **POST /api/acquisition/followed — dedup: conflict (409)**
   - Pre-seed an active row. Send same tvdb_id again.
   - Assert 409, detail mentions "already followed".

4. **POST /api/acquisition/followed — missing XRW (400)**
   - Send without `X-Requested-With` header → 400.

5. **POST /api/acquisition/followed — staging (403)**
   - Set `PERSONALSCRAPER_WEB_ROLE=staging` → 403 (read-only).

6. **POST /api/acquisition/followed — no provider ID (422)**
   - Send `{title: "No ID"}` → 422 (Pydantic validation error).

7. **PATCH /api/acquisition/followed/{id} — update cadence (200)**
   - Seed a row, PATCH `{cadence: {interval_minutes: 120}}`.
   - Assert 200, cadence_json in DB is `{"interval_minutes": 120}`.

8. **PATCH /api/acquisition/followed/{id} — toggle active (200)**
   - Seed an active row, PATCH `{active: false}`.
   - Assert 200, active=False in DB and response.

9. **PATCH /api/acquisition/followed/{id} — not found (404)**

10. **DELETE /api/acquisition/followed/{id} — soft unfollow (204)**
    - Seed an active row, DELETE.
    - Assert 204, row still exists with active=0 (soft delete).

11. **DELETE /api/acquisition/followed/{id} — not found (404)**

12. **Mutation-checked guards** — use `pytest.raises(HTTPException)` or
    `override_dependency` to verify that `require_not_staging` and
    `require_x_requested_with` actually raise, not just that the response
    status is correct.

13. **POST /api/acquisition/followed — title optional**
    - Send `{tvdb_id: 456}` with no title.
    - Assert 201, title is empty string or None in response.

## Cadence write helper

The `_write_tx` context manager is private to `acquire/store.py`. For the
`PATCH` cadence update, add a method to `_FollowSubStore` or write a small
inline helper in the route that opens its own `BEGIN IMMEDIATE` on the
store's connection. The cleanest approach: add a `set_cadence` method to
`_FollowSubStore`:

```python
# In personalscraper/acquire/store.py, _FollowSubStore class:
def set_cadence(self, followed_id: int, cadence_json: str | None) -> None:
    """Update the cadence_json column for a followed series.

    Args:
        followed_id: Rowid of the followed_series row.
        cadence_json: The serialized cadence dict, or None to clear.
    """
    with _write_tx(self._conn):
        self._conn.execute(
            "UPDATE followed_series SET cadence_json = ? WHERE id = ?",
            (cadence_json, followed_id),
        )
```

Export `set_cadence` as a public method. The PATCH route calls it with
`json.dumps(cadence.model_dump())` (or `None` to clear).

Alternatively, keep the route self-contained: access `store._conn` directly
from `_get_acquire_store(request)._conn` (the connection is accessible
post-`_ensure_open()`). But the store-method approach is cleaner and
consistent with `set_active`.

## Design note — no detached runner

Unlike S6 (which needed a detached runner for registry health writes), S7
writes directly via the store's `_write_tx` in the request thread. The
request handler holds the write lock only for the duration of the single
`BEGIN IMMEDIATE ... COMMIT` block (microseconds). This is safe because:

- WAL mode allows concurrent reads during the write.
- `busy_timeout=5000` ensures the writer waits (doesn't fail) if another
  writer (pipeline/watcher) holds the lock.
- No long-lived lock — the `_write_tx` context manager commits immediately
  on success, rolls back on error.
