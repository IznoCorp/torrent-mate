# Phase 7 — Doc OMDB + Trakt

## Gate

**Prerequisites**: Phase 6 complete. All migrations done, `api/` foundation stable.

## Goal

Study OMDB and Trakt APIs. Write comprehensive reference docs before any implementation.

## Sub-phases

### 7.1 — Study OMDB API → `docs/reference/omdb-api.md`

Study https://www.omdbapi.com/ (REST, API key in query param).

Document:

- Endpoints: `?apikey=&t=` (title search), `?apikey=&i=` (IMDB ID lookup), `?apikey=&s=` (search)
- Response format: JSON with `Response: "True"/"False"`
- Fields: Title, Year, Rated, Released, Runtime, Genre, Director, Writer, Actors, Plot, Language, Country, Awards, Poster, Ratings[] (Source + Value), Metascore, imdbRating, imdbVotes, imdbID, Type, DVD, BoxOffice, Production, Website
- Rate limits: 1000/day free tier
- Auth: API key as query param `apikey=`
- Limitations: no TV season/episode-level detail, no artwork beyond poster URL, search is fuzzy by default

Make real test calls with a valid API key to verify field availability.

**Commit**: `docs(api-unify): add OMDB API reference`

### 7.2 — Study Trakt API → `docs/reference/trakt-api.md`

Study https://trakt.docs.apiary.io/ (REST, OAuth 2.0 / Bearer).

Document:

- Endpoints: `/movies/trending`, `/shows/trending`, `/movies/{id}/ratings`, `/shows/{id}/ratings`, `/recommendations/movies`, `/recommendations/shows`, `/search/movie,show`
- Auth: `trakt-api-key` header + OAuth user token for user-specific endpoints
- Response formats
- Rate limits
- Fields relevant for notations and recommendations

Make real test calls with a valid API key.

**Commit**: `docs(api-unify): add Trakt API reference`

### 7.3 — Phase 7 gate

```bash
ls docs/reference/omdb-api.md docs/reference/trakt-api.md
make check
```

**Commit**: `chore(api-unify): phase 7 gate — omdb + trakt docs done`
