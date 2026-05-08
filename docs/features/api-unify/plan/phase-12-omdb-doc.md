# Phase 12 — OMDB API Doc (interactive)

**Type**: doc
**Goal**: Study OMDB, write reference doc, surface particularities (single-endpoint API, query auth).

## Gate (prereq)

Phase 11 complete. Transport stable, query-param auth tested.

## Sub-phases

### 12.1 — Study OMDB

Source: <https://www.omdbapi.com/>. Single endpoint API: `https://www.omdbapi.com/`.

Query forms:

- `?apikey=X&t=Title&y=2024&type=movie` — title search.
- `?apikey=X&i=tt1234567` — IMDB ID lookup.
- `?apikey=X&s=Title&page=1` — multi-result search.

Free tier: 1000 req/day. Returns JSON.

### 12.2 — Real test calls

With `OMDB_API_KEY` from `.env`:

- Title search "Inception" with year 2010 → full `Ratings[]` array.
- IMDB lookup `tt1375666`.
- Multi-search "Star Wars" → paginated.

Capture samples to `docs/reference/_samples/omdb/`.

### 12.3 — Write `docs/reference/omdb-api.md`

Sections:

- Auth: API key as **query parameter** (`apikey=`). Validates the new `ApiKeyAuth(location="query")` path in `HttpTransport`.
- Single endpoint, multiple query forms.
- Response: `Response: "True" | "False"`. On `False`, `Error: "Movie not found!"`.
- Field tables: Title, Year, Rated, Released, Runtime, Genre, Director, Writer, Actors, Plot, Language, Country, Awards, Poster, **Ratings[]** (Source + Value), Metascore, imdbRating, imdbVotes, imdbID, Type, totalSeasons (TV).
- `Ratings[]` shape: `[{"Source": "Internet Movie Database", "Value": "8.8/10"}, {"Source": "Rotten Tomatoes", "Value": "87%"}, {"Source": "Metacritic", "Value": "74/100"}]`.
- Rate limits: 1000/day free, no rps limit documented.
- Limitations: no TV episode-level detail, no artwork beyond poster URL, no recommendations endpoint.

### 12.4 — Particularities checklist

- `Year` field can be `"2024"` or `"2024–"` (TV ongoing) or `"2024–2026"` (TV ended).
- `Runtime` is `"148 min"` string (parse to int).
- `Ratings[].Value` is unparsed string (`"8.8/10"`, `"87%"`, `"74/100"`) — needs per-source parser.
- `Response: "False"` returns 200 OK + `Error` message (NOT a 4xx). `HttpTransport` must NOT treat it as success and downstream must check `Response`. Decision: treat `Response: "False"` as `ApiError(http_status=200, message=Error_string)`.
- Poster URL may be `"N/A"` literal — sentinel.
- No native recommendations — `get_recommendations()` returns `[]`.

### 12.5 — Interactive user checkpoint

> Doc complete: `docs/reference/omdb-api.md`.
> Particularities found: <list>
>
> Implementation decisions to confirm:
>
> - "Response: False" handling: convert to ApiError with http_status=200? Or return None from get_details?
> - Ratings[] parsing: per-source parser (IMDB → /10, RT → %, Metacritic → /100). Confirm output Notations.score is normalized 0–10 or kept per-source?
> - Year range handling: parse first int, ignore range.
>
> Proposed scope (Phase 13):
>
> - search(), get_details(), get_notations() returning IMDB + RT + Metacritic.
> - Out of scope: get_artwork_urls (poster only, returned in MediaDetails.images), recommendations.
>
> Confirm before next phase?

### 12.6 — Phase 12 gate

```bash
ls docs/reference/omdb-api.md
ls docs/reference/_samples/omdb/
```

**Commit**: `docs(api-unify): phase 12 gate — omdb api doc complete

User checkpoint captured:

- Response:False handling: <decision>
- Ratings normalization: <decision>`
