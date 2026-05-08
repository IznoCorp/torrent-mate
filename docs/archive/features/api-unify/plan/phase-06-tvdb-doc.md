# Phase 6 — TVDB API Doc (interactive)

**Type**: doc
**Goal**: Verify and complete TVDB v4 API reference. Confirm token TTL handling decision (no runtime refresh).

## Gate (prereq)

Phase 5 complete. TMDB migration verified.

## Sub-phases

### 6.1 — Audit existing `docs/TVDB-API.md`

Read existing doc. Compare against `scraper/tvdb_client.py` endpoint usage:

```bash
rg "self\._get\(|/v4/|/login|/series|/movies|/artwork" personalscraper/scraper/tvdb_client.py
```

Coverage matrix: endpoints used vs documented.

### 6.2 — Real test calls

With `TVDB_API_KEY` from `.env`, perform:

- `POST /v4/login` (apikey + optional user PIN) → JWT bearer.
- `GET /v4/search?query=...&type=movie|series` → search results.
- `GET /v4/movies/{id}/extended` → movie details.
- `GET /v4/series/{id}/extended` → series details + seasons summary.
- `GET /v4/series/{id}/episodes/default?season=N&page=0` → episodes per season.
- `GET /v4/artwork/{id}` (if used).

Capture samples to `docs/reference/_samples/tvdb/*.json`.

### 6.3 — Token TTL verification

Decode the JWT (`exp` claim) — confirm TTL = 1 month (DESIGN §1.2 assumption).

If TTL is shorter than expected (< 1 day): re-open the design decision. Otherwise: confirm "bootstrap once at `__init__`, no runtime refresh" remains valid.

### 6.4 — Write `docs/reference/tvdb-api.md`

Sections:

- Auth: API key (`TVDB_API_KEY`) → POST `/v4/login` → JWT bearer (TTL = 1 month, **no runtime refresh required** per DESIGN §1.2).
- Endpoints (full list + parameters + response schema).
- Error format: TVDB v4 returns `{"status": "failure", "message": "..."}` — note this differs from TMDB's `status_code/status_message`.
- Language/translation handling: `nameTranslations`, `overviewTranslations` arrays of language codes; details endpoint returns base record + a `?language=fr` variant for translations.
- Image construction: TVDB v4 returns full URLs (no base+size assembly).
- Pagination: episodes paginated 100/page.
- Rate limits.

### 6.5 — Particularities checklist

Likely items:

- TVDB language codes are 3-letter (`fra`, `eng`, `spa`) — `_TVDB_LANG_MAP` migrates with TVDB.
- "season type" parameter: `default` vs `official` vs `dvd` vs `absolute`.
- Artwork types: `2` (poster), `3` (background), `7` (clear logo) etc. — numeric IDs.
- Some series have no episodes; some episodes have no `aired` date.
- Score is `score: int` (popularity rank, not user rating). User ratings live elsewhere.

Each: handle / ignore / out of scope.

### 6.6 — Interactive user checkpoint

> Doc complete: `docs/reference/tvdb-api.md`.
> Token TTL confirmed = <decoded value> → no runtime refresh.
> Particularities found: <list>
>
> Proposed implementation scope (Phase 7):
>
> - Endpoints to wire: <list>
> - Auth bootstrap: one-shot HttpTransport(NoAuth) → POST /v4/login → BearerAuth(jwt) for main client.
> - Out of scope: <list>
>
> Confirm or adjust before next phase?

### 6.7 — Phase 6 gate

```bash
ls docs/reference/tvdb-api.md
ls docs/reference/_samples/tvdb/
```

**Commit**: `docs(api-unify): phase 6 gate — tvdb api doc complete

User checkpoint captured:

- Token TTL: <value>
- <decisions>`
