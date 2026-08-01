# Phase 5 — Web API (Season Grab Endpoint) + Frontend

## Gate

- [ ] `make lint` zero errors
- [ ] `make test` all pass (focus: API route tests, frontend vitest)
- [ ] `make openapi` regenerates + both files committed (check `git diff --stat`)
- [ ] `rg "seasons.*grab" --type py personalscraper/web/` confirms route present
- [ ] Frontend `npm run typecheck` passes
- [ ] Frontend `npm run lint` passes
- [ ] Test: `POST /api/acquisition/follows/{id}/seasons/{season}/grab` returns 403 on staging
- [ ] Test: duplicate season grab returns 409

## Sub-phase 5.1 — Season Grab API Endpoint

**Files**: `web/routes/acquisition.py`, `web/models/acquisition.py`

### Step 1: Add Pydantic models

In `web/models/acquisition.py`, add:

```python
class SeasonGrabResponse(BaseModel):
    """Response for a season grab request (R4)."""

    season_wanted_id: int
    season: int
    absorbed_count: int  # number of episode rows absorbed


class SeasonGrabError(BaseModel):
    """Error detail for season grab conflicts."""

    detail: str
```

### Step 2: Add the POST route

In `web/routes/acquisition.py`, add after existing mutating routes (after line 1192):

```python
@router.post(
    "/follows/{followed_id}/seasons/{season}/grab",
    status_code=201,
    response_model=SeasonGrabResponse,
    dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)],
)
def grab_season(
    request: Request,
    followed_id: int,
    season: int,
) -> SeasonGrabResponse:
    """Manually enqueue a season wanted for a followed series (R4).

    Creates a ``WantedItem(kind='season', season=N, episode=None)`` and
    absorbs every live episode wanted for that season (R5). Idempotent:
    returns the existing season row id if one already exists.

    Args:
        request: The incoming FastAPI request.
        followed_id: Rowid of the ``followed_series`` row.
        season: Season number (1-based).

    Returns:
        The created or existing season wanted with absorption count.

    Raises:
        HTTPException: 404 if the followed_id does not exist.
        HTTPException: 409 if a live season wanted already exists (idempotent
            — returns it rather than failing).
        HTTPException: 400 if season < 1.
    """
    if season < 1:
        raise HTTPException(status_code=400, detail="Season must be >= 1")

    config = request.app.state.config
    store = build_acquire_store(config.acquire)
    try:
        followed = store.follow.get(followed_id)
        if followed is None:
            raise HTTPException(status_code=404, detail="Followed series not found")
        if followed.kind != "show":
            raise HTTPException(
                status_code=400,
                detail="Season grab only applies to TV shows (kind='show')",
            )

        # Dedup: one live season wanted per follow+season
        existing = store.wanted.find(
            followed_id=followed_id, kind="season",
            season=season, episode=None,
        )
        if existing is not None:
            # Count already-absorbed episodes for a truthful response
            absorbed = _count_absorbed_for_season(store, followed_id, season)
            return SeasonGrabResponse(
                season_wanted_id=existing.id or 0,
                season=season,
                absorbed_count=absorbed,
            )

        assert followed.id is not None  # noqa: S101 — get() sets id
        now = int(time.time())

        # Enqueue the season wanted
        season_wid = store.wanted.add(
            WantedItem(
                media_ref=followed.media_ref,
                kind="season",
                status="pending",
                enqueued_at=now,
                followed_id=followed.id,
                season=season,
                episode=None,
            )
        )

        # Absorb live episode wanteds for this season
        absorbed_ids = _absorb_live_episodes_for_season(
            store, followed.id, season, season_wid,
        )

        return SeasonGrabResponse(
            season_wanted_id=season_wid,
            season=season,
            absorbed_count=len(absorbed_ids),
        )
    finally:
        store.close()


def _count_absorbed_for_season(
    store: "ConcreteAcquireStore", followed_id: int, season: int,
) -> int:
    """Count episode rows already absorbed for a season."""
    store.wanted._conn.row_factory = sqlite3.Row
    row = store.wanted._conn.execute(
        "SELECT COUNT(*) AS cnt FROM wanted "
        "WHERE followed_id IS ? AND kind = 'episode' "
        "AND season = ? AND status = 'absorbed'",
        (followed_id, season),
    ).fetchone()
    return int(row["cnt"]) if row else 0


def _absorb_live_episodes_for_season(
    store: "ConcreteAcquireStore",
    followed_id: int,
    season: int,
    season_wanted_id: int,
) -> list[int]:
    """Absorb all live episode wanted rows for a season (R5).

    Returns the list of rowids that were absorbed.
    """
    store.wanted._conn.row_factory = sqlite3.Row
    rows = store.wanted._conn.execute(
        "SELECT id FROM wanted "
        "WHERE followed_id IS ? AND kind = 'episode' "
        "AND season = ? AND status IN ('pending', 'searching', 'available')",
        (followed_id, season),
    ).fetchall()
    episode_ids = tuple(int(r["id"]) for r in rows)
    if episode_ids:
        store.wanted.absorb_episodes(season_wanted_id, episode_ids)
    return list(episode_ids)
```

### Step 3: Import the new model

In `web/routes/acquisition.py:85-86`, add `SeasonGrabResponse` to imports:

```python
from personalscraper.web.models.acquisition import (
    # ... existing imports ...
    SeasonGrabResponse,  # NEW
)
```

### Step 4: Tests

```python
# tests/web/routes/test_acquisition.py

def test_season_grab_creates_season_wanted():
    """POST /api/acquisition/follows/{id}/seasons/{N}/grab → 201 + season wanted."""
    # Setup: followed_id=1 (a show with 3 live episode wanteds in season 1)
    # POST
    # Assert: 201, season_wanted_id > 0, absorbed_count == 3


def test_season_grab_returns_existing_on_duplicate():
    """Second grab on same season → returns existing row (idempotent)."""
    # First POST → 201
    # Second POST → 200? Design says 409/no-op. The route returns
    # the existing row data without a separate HTTP status.
    # Assert: same season_wanted_id, absorbed_count == 3


def test_season_grab_403_on_staging():
    """Staging role → 403 Forbidden."""
    # POST with staging role cookie
    # Assert: 403


def test_season_grab_404_on_unknown_follow():
    """Unknown followed_id → 404."""
    # POST to /seasons/1/grab on id=9999
    # Assert: 404


def test_season_grab_400_on_movie_follow():
    """Movie follow (kind='movie') → 400."""
    # POST to a movie followed_id
    # Assert: 400
```

Run: `pytest tests/web/routes/test_acquisition.py -v -k "test_season_grab"`

### Step 5: Regenerate OpenAPI

```bash
make openapi
git add frontend/src/api/schema.d.ts  # if regenerated
git add docs/reference/openapi.json   # if regenerated
```

## Sub-phase 5.2 — Frontend: Per-season Button in Suivis

**Files**: `frontend/src/components/acquisition/CompletenessAccordion.tsx`, `frontend/src/components/acquisition/FollowedPanel.tsx`, `frontend/src/api/acquisition.ts`

### Step 1: Add API client function

In `frontend/src/api/acquisition.ts`:

```typescript
/** Response from POST /api/acquisition/follows/{id}/seasons/{season}/grab */
export interface SeasonGrabResponse {
  season_wanted_id: number;
  season: number;
  absorbed_count: number;
}

/** Manually enqueue a season wanted (R4). */
export async function grabSeason(
  followedId: number,
  season: number,
): Promise<SeasonGrabResponse> {
  const res = await fetch(
    `/api/acquisition/follows/${followedId}/seasons/${season}/grab`,
    { method: "POST", headers: XRW_HEADERS },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? res.statusText);
  }
  return res.json() as Promise<SeasonGrabResponse>;
}
```

### Step 2: Add per-season button in CompletenessAccordion

In `CompletenessAccordion.tsx`, each season row in the accordion gets a button:

```tsx
{
  /* Inside the season row, after the episode grid */
}
<div className="flex items-center gap-2">
  <Button
    variant="outline"
    size="sm"
    disabled={seasonHasLiveWanted || seasonAbsorbed || seasonFullyOwned}
    onClick={() => handleGrabSeason(followedId, seasonNum)}
  >
    <Download className="mr-1 h-4 w-4" />
    Récupérer la saison
  </Button>
</div>;
```

The disabled states:

- `seasonHasLiveWanted`: a live season wanted already exists for this season
- `seasonAbsorbed`: the season's episodes are all absorbed by a season wanted
- `seasonFullyOwned`: all episodes owned (per the completeness data)

### Step 3: Add absorbed state to the legend

In the component that renders the state legend (likely `FollowedPanel.tsx` or a shared `meta.tsx`), add:

```typescript
// In meta.ts (or similar shared constants file)
export const EPISODE_STATE_LABEL: Record<string, string> = {
  // ... existing ...
  absorbed: "Absorbé (saison)",
};

export const EPISODE_STATE_TONE: Record<string, string> = {
  // ... existing ...
  absorbed: "muted",
};
```

### Step 4: Season wanted row in File d'Acquisition

In `FileDAcquisitionPanel.tsx`, the `groupByTitleSeason` function already groups by season. Season wanted items (`kind="season"`) have `episode=None` — they should render as a special row:

```tsx
// In the episode list render, after the loop:
{
  episodes
    .filter((e) => e.kind === "season")
    .map((item) => (
      <div key={`season-${item.id}`} className="flex items-center gap-2 py-1">
        <Badge variant="outline">Saison {item.season}</Badge>
        <span className="text-sm text-muted-foreground">
          Saison {String(item.season).padStart(2, "0")}
        </span>
        <StatusBadge status={item.status} />
      </div>
    ));
}
```

### Step 5: Frontend tests (vitest)

```typescript
// frontend/src/components/acquisition/CompletenessAccordion.test.tsx
it("renders grab-season button for incomplete seasons", () => {
  // Render accordion with a season at 50% owned
  // Assert: "Récupérer la saison" button is visible and enabled
});

it("disables grab-season button when season fully owned", () => {
  // Render accordion with a season at 100% owned
  // Assert: button is disabled
});

it("disables grab-season button when season wanted exists", () => {
  // Render accordion with a live season wanted
  // Assert: button is disabled
});
```

```typescript
// frontend/src/components/acquisition/FileDAcquisitionPanel.test.tsx
it("renders season wanted rows with Saison label", () => {
  // Render with season-kind wanted items
  // Assert: "Saison NN" badge present
});

it("shows absorbed episodes with muted state", () => {
  // Render with absorbed episode items
  // Assert: "Absorbé (saison)" label visible, muted tone
});
```

Run: `cd frontend && npx vitest run`

## Commit

```bash
git add personalscraper/web/routes/acquisition.py personalscraper/web/models/acquisition.py \
        tests/web/routes/test_acquisition.py \
        frontend/src/api/acquisition.ts \
        frontend/src/components/acquisition/CompletenessAccordion.tsx \
        frontend/src/components/acquisition/FileDAcquisitionPanel.tsx \
        frontend/src/components/acquisition/FollowedPanel.tsx \
        frontend/src/api/schema.d.ts  # only if regenerated
git commit -m "feat(season-grab): POST /api/acquisition/follows/{id}/seasons/{season}/grab endpoint + per-season button in Suivis, season rows in File d'acquisition, absorbed state legend"
```
