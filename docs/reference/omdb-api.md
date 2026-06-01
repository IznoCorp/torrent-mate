# OMDB API — Reference

> The Open Movie Database API — reference for the `api/metadata/omdb.py` provider.
> Source: https://www.omdbapi.com/
> Last updated: 2026-05-06

---

## Table of Contents

- [Authentication](#authentication)
- [Base URL](#base-url)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Query Forms](#query-forms)
- [Response Fields — Movie](#response-fields--movie)
- [Response Fields — Series](#response-fields--series)
- [Response Fields — Search](#response-fields--search)
- [Ratings Array](#ratings-array)
- [Particularities](#particularities)
- [Test Samples](#test-samples)

---

## Authentication

API key passed as **query parameter** `apikey=` on every request. Free tier: 1000 req/day.
No OAuth, no header auth, no session token.

To obtain a key: https://www.omdbapi.com/apikey.aspx (free, Patreon-backed).

Store key in `.env`:

```bash
OMDB_API_KEY=your_key_here
```

Implementation: `ApiKeyAuth(location="query", param_name="apikey")` wired into `HttpTransport`.

---

## Base URL

Single endpoint — no regional variants, no versioned path:

```
http://www.omdbapi.com/?apikey={KEY}&<query_params>
```

- HTTP only (no enforced HTTPS redirect as of 2026-05).
- All responses are `Content-Type: application/json; charset=utf-8`.
- Cloudflare CDN in front (`cf-cache-status` header present).

---

## Rate Limiting

- **1000 requests per day** on the free tier.
- No per-second rate limit documented or observed.
- `HttpTransport` with `max_requests_per_second=0` (disabled) is sufficient.
- Paid Patreon tiers exist for higher limits (not needed for this project's use case).

---

## Error Handling

**Critical particularity**: the API always returns HTTP 200. Errors are signaled in-band
via the `Response` field.

| `Response` | Meaning | Shape                                       |
| ---------- | ------- | ------------------------------------------- |
| `"True"`   | Success | Full data payload                           |
| `"False"`  | Error   | `{"Response":"False", "Error":"<message>"}` |

Known error messages:

- `"Movie not found!"` — title/ID search returned no match.
- `"Error getting data."` — invalid or unknown IMDb ID.
- `"Too many results."` — search too broad (rare).

**Design decision**: `Response: "False"` MUST be converted to
`ApiError(http_status=200, message=Error_string)` before control returns to the caller.
No `None`-returning — callers already handle `ApiError`.

---

## Query Forms

### By IMDb ID (`i`)

Fetches a single movie or series by IMDb ID.

```
?apikey=X&i=tt1375666
```

Most precise lookup — use when IMDb ID is known.

### By Title (`t`)

Fetches a single result by title string.

```
?apikey=X&t=Inception
?apikey=X&t=Inception&y=2010
?apikey=X&t=Breaking+Bad&type=series
```

Optional parameters:

| Param  | Values                       | Effect                   |
| ------ | ---------------------------- | ------------------------ |
| `y`    | year (e.g. `2010`)           | Restrict to release year |
| `type` | `movie`, `series`, `episode` | Restrict to content type |

### Search (`s`)

Multi-result title search, paginated.

```
?apikey=X&s=Star+Wars
?apikey=X&s=Star+Wars&page=2
?apikey=X&s=Star+Wars&type=movie&y=1977
```

Returns `Search[]` array + `totalResults` string. 10 results per page.
Supports `type` and `y` filters.

---

## Response Fields — Movie

All fields are strings unless noted. Fields absent for some titles are `"N/A"`.

| Field        | Example                                                  | Notes                               |
| ------------ | -------------------------------------------------------- | ----------------------------------- |
| `Title`      | `"Inception"`                                            |                                     |
| `Year`       | `"2010"`                                                 | See [Year formats](#year-formats)   |
| `Rated`      | `"PG-13"`                                                | MPAA rating                         |
| `Released`   | `"16 Jul 2010"`                                          | `DD Mon YYYY` format                |
| `Runtime`    | `"148 min"`                                              | Parse int from prefix               |
| `Genre`      | `"Action, Adventure, Sci-Fi"`                            | Comma-separated                     |
| `Director`   | `"Christopher Nolan"`                                    |                                     |
| `Writer`     | `"Christopher Nolan"`                                    |                                     |
| `Actors`     | `"Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page"` | Comma-separated                     |
| `Plot`       | `"A thief who steals..."`                                | Full synopsis                       |
| `Language`   | `"English, Japanese, French"`                            | Comma-separated                     |
| `Country`    | `"United Kingdom, United States"`                        | Comma-separated                     |
| `Awards`     | `"Won 4 Oscars. 160 wins & 220 nominations total"`       | Free text                           |
| `Poster`     | `"https://m.media-amazon.com/..."`                       | URL or `"N/A"`                      |
| `Ratings`    | `[{Source, Value}, ...]`                                 | See [Ratings Array](#ratings-array) |
| `Metascore`  | `"74"`                                                   | String int or `"N/A"`               |
| `imdbRating` | `"8.8"`                                                  | String float                        |
| `imdbVotes`  | `"2,811,614"`                                            | Formatted with commas               |
| `imdbID`     | `"tt1375666"`                                            |                                     |
| `Type`       | `"movie"`                                                |                                     |
| `DVD`        | `"N/A"`                                                  | DVD release date                    |
| `BoxOffice`  | `"$292,587,330"`                                         |                                     |
| `Production` | `"N/A"`                                                  |                                     |
| `Website`    | `"N/A"`                                                  |                                     |
| `Response`   | `"True"`                                                 | Always `"True"` on success          |

---

## Response Fields — Series

Same base fields as Movie, plus:

| Field          | Example                    | Notes                             |
| -------------- | -------------------------- | --------------------------------- |
| `totalSeasons` | `"5"`                      | String int                        |
| `Year`         | `"2008–2013"` or `"1989–"` | See [Year formats](#year-formats) |

`Type` is `"series"`. No episode-level detail available (OMDB limitation).

---

## Response Fields — Search

| Field          | Example                                      | Notes                  |
| -------------- | -------------------------------------------- | ---------------------- |
| `Search`       | `[{Title, Year, imdbID, Type, Poster}, ...]` | Array, max 10 per page |
| `totalResults` | `"980"`                                      | String int             |
| `Response`     | `"True"`                                     |                        |

Search result items:

| Field    | Example                                | Notes               |
| -------- | -------------------------------------- | ------------------- |
| `Title`  | `"Star Wars: Episode IV - A New Hope"` |                     |
| `Year`   | `"1977"`                               |                     |
| `imdbID` | `"tt0076759"`                          |                     |
| `Type`   | `"movie"`                              | `movie` or `series` |
| `Poster` | `"https://m.media-amazon.com/..."`     | URL or `"N/A"`      |

---

## Ratings Array

`Ratings` is an array of 2–3 entries, one per source. Present on `?i=` and `?t=` lookups.
Absent from `?s=` search results.

```json
[
  { "Source": "Internet Movie Database", "Value": "8.8/10" },
  { "Source": "Rotten Tomatoes", "Value": "87%" },
  { "Source": "Metacritic", "Value": "74/100" }
]
```

**Value parsing** (per source):

| Source                    | Format     | Normalize to 0–10             |
| ------------------------- | ---------- | ----------------------------- |
| `Internet Movie Database` | `"8.8/10"` | Already 0–10, parse left side |
| `Rotten Tomatoes`         | `"87%"`    | `/ 10` (e.g. 87 → 8.7)        |
| `Metacritic`              | `"74/100"` | `/ 10` (e.g. 74 → 7.4)        |

Sources are **not guaranteed** — some titles may have only 2 entries (e.g. Breaking Bad
has only IMDb + RT, no Metacritic).

Rotten Tomatoes source label changed from `"Rotten Tomatoes"` to
`"Rotten Tomatoes"` across titles — identical.

---

## Particularities

### Year formats

| Format        | Example       | Meaning                      |
| ------------- | ------------- | ---------------------------- |
| `"YYYY"`      | `"2010"`      | Single year (movie, one-off) |
| `"YYYY–"`     | `"1989–"`     | TV series still running      |
| `"YYYY–YYYY"` | `"2008–2013"` | TV series ended              |

Implementation: parse first integer, ignore range. The `Year` field on our typed models
is `Optional[int]`.

### Runtime parsing

Always `"NNN min"` string. Parse leading integer. TV series return per-episode runtime.

### `"N/A"` sentinel

Many optional fields return `"N/A"` literal. Map to `None` in typed models. Affects:
`Poster`, `DVD`, `BoxOffice`, `Production`, `Website`, `Metascore`, `Director` (series),
`totalSeasons` (movies).

### IMDb ID format

Always `tt` prefix + 7–8 digits. Use as-is for cross-referencing with Trakt/TMDB.

### No recommendations

OMDB has no recommendation/related endpoint. `get_recommendations()` returns `[]`.

### No episode data

OMDB can look up episodes individually by title + season/episode, but has no bulk
episode listing. TV episode scraping stays with TMDB/TVDB.

### No artwork beyond poster

OMDB returns only `Poster` URL. Backdrop/fanart remain sourced from TMDB.

---

## Test Samples

7 captured API responses in `docs/reference/_samples/omdb/`:

| File                        | Query                            | Type             |
| --------------------------- | -------------------------------- | ---------------- |
| `title-inception-2010.json` | `?t=Inception&y=2010&type=movie` | Movie detail     |
| `imdb-tt1375666.json`       | `?i=tt1375666`                   | IMDb ID lookup   |
| `search-star-wars.json`     | `?s=Star+Wars&page=1`            | Multi-search     |
| `series-breaking-bad.json`  | `?t=Breaking+Bad&type=series`    | TV ended         |
| `series-simpsons.json`      | `?t=The+Simpsons&type=series`    | TV ongoing       |
| `not-found.json`            | `?t=asdfghqwerty12345`           | Error: not found |
| `bad-id.json`               | `?i=tt0000000`                   | Error: bad ID    |
