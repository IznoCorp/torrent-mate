# Phase 14 — Trakt API Doc (interactive)

**Type**: doc
**Goal**: Study Trakt API, write reference doc, surface OAuth/header particularities.

## Gate (prereq)

Phase 13 complete.

## Sub-phases

### 14.1 — Study Trakt

Source: <https://trakt.docs.apiary.io/>. REST API at `https://api.trakt.tv`.

Auth modes:

- **App-only** (Trakt API key in header): `trakt-api-key: <CLIENT_ID>` + `trakt-api-version: 2`. Sufficient for public data (search, ratings, trending, recommendations on a media item).
- **OAuth user token**: required only for user-specific endpoints (watchlist, history). Out of scope for this feature.

### 14.2 — Real test calls

With `TRAKT_CLIENT_ID` from `.env`:

- `GET /search/movie?query=Inception&year=2010` (header auth).
- `GET /movies/inception-2010/ratings` → `{"rating": 8.5, "votes": 12345, "distribution": {...}}`.
- `GET /movies/trending?limit=10`.
- `GET /movies/inception-2010/related` → recommendations.

Capture samples to `docs/reference/_samples/trakt/`.

### 14.3 — Write `docs/reference/trakt-api.md`

Sections:

- Auth: app-only via two headers (`trakt-api-key`, `trakt-api-version: 2`). OAuth out of scope.
- Required content type: `Content-Type: application/json` for POST.
- Trakt slug IDs vs IMDB IDs vs Trakt numeric IDs (`/movies/{trakt-id|imdb-id|slug}`).
- Endpoints: `/search/{type}`, `/movies/{id}`, `/movies/{id}/ratings`, `/movies/{id}/related`, `/movies/trending`, `/shows/...` (parallel).
- Response shapes per endpoint.
- Rate limit: documented as no hard limit but recommends throttling — set `RateLimitPolicy(requests_per_second=5)` defensively.
- Pagination: `X-Pagination-Page`, `X-Pagination-Limit`, `X-Pagination-Page-Count`, `X-Pagination-Item-Count` response headers.

### 14.4 — Particularities checklist

- Slug IDs (`inception-2010`) are used in URL paths — Trakt accepts numeric ID, IMDB ID, or slug interchangeably.
- `extended=full` query parameter unlocks more fields (overview, runtime, country).
- Trending endpoint returns `[{"watchers": N, "movie": {...}}]` (wrapper differs from search).
- Ratings: `distribution` is a 1–10 histogram dict — out of scope for `Notations` model (just store score + votes).
- Recommendations endpoint is `/related` (NOT `/recommendations` which requires OAuth).

### 14.5 — Interactive user checkpoint

> Doc complete: `docs/reference/trakt-api.md`.
> Particularities found: <list>
>
> Implementation decisions to confirm:
>
> - ID resolution: accept any of (slug, imdb_id, trakt_id) in get_details? Or normalize to one?
> - extended=full default? Higher payload but richer data.
> - Default rps for RateLimitPolicy: 5? (defensive)
>
> Proposed scope (Phase 15):
>
> - search(), get_details(), get_notations(), get_recommendations() (via /related), get_trending().
> - Out of scope: OAuth user endpoints (watchlist/history).
>
> Confirm before next phase?

### 14.6 — Phase 14 gate

```bash
ls docs/reference/trakt-api.md
ls docs/reference/_samples/trakt/
```

**Commit**: `docs(api-unify): phase 14 gate — trakt api doc complete

User checkpoint captured: <decisions>`
