# Phase 3 — Doc TMDB + TVDB

## Gate

**Prerequisites**: Phase 2 complete. `config.example/` files exist, `ProviderActivation` works.

## Goal

Verify and complete existing TMDB and TVDB API documentation. These files serve as reference for the migration phases (4-5).

## Sub-phases

### 3.1 — Verify/complete `docs/reference/tmdb-api.md`

Read `docs/TMDB-API.md` (existing). Create `docs/reference/tmdb-api.md` covering:

- All endpoints used by `TMDBClient`: `/search/movie`, `/search/tv`, `/movie/{id}`, `/tv/{id}`, `/tv/{id}/season/{n}`, `/movie/{id}/videos`, `/tv/{id}/videos`, `/movie/{id}/keywords`, `/tv/{id}/keywords`
- Authentication: Bearer token, where to get it
- Response formats with field tables per endpoint
- Rate limits: 50 req/s, pagination (20/page, max 500 pages)
- Error codes: TMDB internal status_code values (7=invalid key, 25=rate limit, 34=not found)
- Image URL construction: base URL + size + path
- `append_to_response` usage and `include_image_language`
- Language parameter behavior

```bash
# Check what already exists
cat docs/TMDB-API.md | head -5
```

**Commit**: `docs(api-unify): verify and complete TMDB API reference`

### 3.2 — Create `docs/reference/tvdb-api.md`

Read `docs/TVDB-API.md` (existing). Create `docs/reference/tvdb-api.md` covering:

- Auth: API key → login → Bearer token, token refresh (24h TTL)
- Endpoints: `/search`, `/series/{id}`, `/series/{id}/episodes`, `/movies/{id}`, `/artwork`
- Response formats
- Rate limits, quotas
- Language/translation handling

**Commit**: `docs(api-unify): verify and complete TVDB API reference`

### 3.3 — Phase 3 gate

```bash
make check
ls docs/reference/tmdb-api.md docs/reference/tvdb-api.md
```

**Commit**: `chore(api-unify): phase 3 gate — tmdb + tvdb docs done`
