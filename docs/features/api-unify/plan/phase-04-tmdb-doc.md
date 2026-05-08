# Phase 4 — TMDB API Doc (interactive)

**Type**: doc
**Goal**: Verify and complete TMDB API reference. Surface particularities to user before code is written.

## Gate (prereq)

Phase 3 complete. `api/metadata/_base.py` exists.

## Sub-phases

### 4.1 — Audit existing `docs/TMDB-API.md`

Read the existing doc. Compare against current `scraper/tmdb_client.py` endpoint usage:

```bash
rg "self\._get\(|/3/" personalscraper/scraper/tmdb_client.py
```

Build a coverage matrix: endpoints used in code vs documented in `docs/TMDB-API.md`. Flag gaps.

### 4.2 — Real test calls

Using `TMDB_API_KEY` from `.env`, hit each endpoint actually used by the migration target:

- `GET /3/search/movie`
- `GET /3/search/tv`
- `GET /3/movie/{id}` (with `append_to_response=keywords,images,videos`)
- `GET /3/tv/{id}`
- `GET /3/tv/{id}/season/{n}`
- `GET /3/movie/{id}/videos`
- `GET /3/tv/{id}/videos`
- `GET /3/movie/{id}/keywords`
- `GET /3/tv/{id}/keywords`

Capture sample responses to `docs/reference/_samples/tmdb/*.json` for golden tests in Phase 5.

### 4.3 — Write `docs/reference/tmdb-api.md`

Sections:

- Authentication: Bearer token (v4 read access token), where to obtain.
- Rate limits: 50 req/s (per IP).
- Endpoints used (full list with parameters + response schema).
- Error format: `{"status_code": 7, "status_message": "Invalid API key"}` etc.
- Image construction: `https://image.tmdb.org/t/p/{size}{path}` with size taxonomy.
- `append_to_response` mechanics + `include_image_language=fr,en,null`.
- Language fallback behavior (when `language=fr-FR` returns empty `overview`, fallback strategy).
- Pagination: 20 results/page, `total_pages` capped at 500.
- TMDB-internal `status_code` table (7=invalid key, 25=rate limit, 34=not found).

### 4.4 — Particularities checklist (interactive checkpoint)

Write a `## Particularities` section listing surfaced quirks. Examples likely:

- `release_date` may be empty string for unreleased movies.
- `runtime` is null for some TV shows.
- `videos.results[].official` boolean — official trailers vs fan content.
- `images` includes 3 separate arrays (`backdrops`, `posters`, `logos`).
- `genre_ids` (array of int) in search results vs `genres` (array of obj) in details.
- TV show "season 0" = specials.
- Translations endpoint exists but may not be needed (current code uses fallback_language only).

Each particularity needs an explicit decision: **handle / ignore / out of scope**.

### 4.5 — Interactive user checkpoint

Present to user:

> Doc complete: `docs/reference/tmdb-api.md`.
> Particularities found:
>
> - <list from 4.4>
>
> Proposed implementation scope (Phase 5):
>
> - Endpoints to wire: <list>
> - Typed models impact: <delta vs SearchResult/MediaDetails/...>
> - Out of scope: <list, e.g., translations, alternative_titles>
>
> Confirm or adjust before next phase?

**No code is written** until the user replies. Capture the user's decisions in the commit body.

### 4.6 — Phase 4 gate

```bash
ls docs/reference/tmdb-api.md
ls docs/reference/_samples/tmdb/
```

**Commit**: `docs(api-unify): phase 4 gate — tmdb api doc complete

User checkpoint captured:

- <decisions>`
