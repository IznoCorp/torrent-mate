# Trakt API — Reference

> Trakt.tv API v2 — reference for the `api/metadata/trakt.py` provider.
> Source: https://trakt.docs.apiary.io/
> Last updated: 2026-05-06

---

## Table of Contents

- [Authentication](#authentication)
- [Base URL](#base-url)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [IDs and Slugs](#ids-and-slugs)
- [Endpoints — Search](#endpoints--search)
- [Endpoints — Movie Details](#endpoints--movie-details)
- [Endpoints — Ratings](#endpoints--ratings)
- [Endpoints — Related](#endpoints--related)
- [Endpoints — Trending](#endpoints--trending)
- [Endpoints — TV Shows](#endpoints--tv-shows)
- [Image URLs](#image-urls)
- [Particularities](#particularities)
- [Test Samples](#test-samples)

---

## Authentication

App-only auth via **two headers** on every request:

| Header              | Value                                   |
| ------------------- | --------------------------------------- |
| `trakt-api-key`     | Client ID (from Trakt app registration) |
| `trakt-api-version` | `2`                                     |

No query-param auth. No Bearer token. OAuth user tokens are out of scope (only needed
for user-specific endpoints: watchlist, history, check-in).

Store key in `.env`:

```bash
TRAKT_CLIENT_ID=your_client_id_here
```

Implementation note: `ApiKeyAuth` handles the `trakt-api-key` header via
`ApiKeyAuth(key, param="trakt-api-key", location="header")`. The `trakt-api-version: 2`
header requires a second mechanism (either a `TraktAuth` subclass or an
`extra_headers` field on `TransportPolicy` — see Phase 15 for resolution).

---

## Base URL

```
https://api.trakt.tv
```

All endpoints are under this base. SSL-only (HTTP redirects to HTTPS).

---

## Rate Limiting

Trakt documents no hard rate limit but recommends throttling. Conservative
default:

```
RateLimitPolicy(requests_per_second=5)
```

Response headers include rate info (observe and adjust).

---

## Error Handling

Trakt returns standard HTTP status codes. No in-band error signaling (unlike OMDB).

| Status | Meaning                 |
| ------ | ----------------------- |
| 200    | Success                 |
| 401    | Bad or missing API key  |
| 404    | Unknown movie/show/slug |
| 429    | Rate limited (rare)     |

`HttpTransport` already handles non-2xx → `ApiError`.

---

## IDs and Slugs

Trakt accepts any of these interchangeably in URL paths:

| ID type          | Example          | Format                                          |
| ---------------- | ---------------- | ----------------------------------------------- |
| Trakt numeric ID | `16662`          | Integer                                         |
| Slug             | `inception-2010` | `title-year`, lowercase, special chars stripped |
| IMDb ID          | `tt1375666`      | Standard `tt` prefix                            |

Every response includes an `ids` object:

```json
{
  "trakt": 16662,
  "slug": "inception-2010",
  "imdb": "tt1375666",
  "tmdb": 27205,
  "tvdb": 81189,
  "plex": { "guid": "...", "slug": "inception" }
}
```

`trakt`, `slug`, `imdb`, and `tmdb` are always present for movies. `tvdb` is present
for TV shows only. `plex` is Trakt-specific.

---

## Endpoints — Search

### Movie search

```
GET /search/movie?query=Inception&year=2010
GET /search/movie?query=Inception
```

Returns an array of `{score, type, movie: {...}}` objects.

| Field            | Type      | Notes                                 |
| ---------------- | --------- | ------------------------------------- |
| `score`          | float     | Match relevance (very high precision) |
| `type`           | `"movie"` |                                       |
| `movie.title`    | str       |                                       |
| `movie.year`     | int       |                                       |
| `movie.ids`      | object    | See [IDs and Slugs](#ids-and-slugs)   |
| `movie.overview` | str       | Always present in search results      |
| `movie.runtime`  | int       | Minutes                               |
| `movie.genres`   | list[str] | Lowercase                             |
| `movie.rating`   | float     | 0-10                                  |
| `movie.votes`    | int       |                                       |
| `movie.trailer`  | str       | YouTube URL, may be empty             |
| `movie.images`   | object    | See [Image URLs](#image-urls)         |

### TV show search

```
GET /search/show?query=Breaking+Bad&year=2008
```

Same structure but `type: "show"` and sub-object is `show` instead of `movie`.
TV shows include a `tvdb` key in `ids` and a `status` field (`"ended"`, `"returning series"`).

---

## Endpoints — Movie Details

```
GET /movies/{id}?extended=full
GET /movies/inception-2010?extended=full
```

Returns a single movie object. `extended=full` unlocks: `overview`, `runtime`,
`tagline`, `homepage`, `genres`, `subgenres`, `languages`, `images`, `colors`,
`certification`, `comment_count`, `original_title`, `available_translations`.

Without `extended=full`, only: `title`, `year`, `ids`.

| Field            | Type      | Notes                                 |
| ---------------- | --------- | ------------------------------------- |
| `title`          | str       |                                       |
| `year`           | int       |                                       |
| `ids`            | object    | See [IDs and Slugs](#ids-and-slugs)   |
| `overview`       | str       | Requires `extended=full`              |
| `runtime`        | int       | Minutes, requires `extended=full`     |
| `genres`         | list[str] | Lowercase, requires `extended=full`   |
| `subgenres`      | list[str] | Requires `extended=full`              |
| `rating`         | float     | 0-10                                  |
| `votes`          | int       |                                       |
| `trailer`        | str       | YouTube URL                           |
| `homepage`       | str       | Official site URL                     |
| `tagline`        | str       |                                       |
| `status`         | str       | `"released"`, `"in production"`, etc. |
| `country`        | str       | ISO 3166-1 alpha-2                    |
| `language`       | str       | Primary language                      |
| `languages`      | list[str] | All available languages               |
| `released`       | str       | `YYYY-MM-DD`                          |
| `certification`  | str       | `"PG-13"`, `"NR"`, etc.               |
| `original_title` | str       |                                       |
| `images`         | object    | See [Image URLs](#image-urls)         |
| `comment_count`  | int       |                                       |

---

## Endpoints — Ratings

```
GET /movies/{id}/ratings
GET /shows/{id}/ratings
```

Returns:

```json
{
  "rating": 8.62414,
  "votes": 86023,
  "distribution": {"1": 377, "2": 205, ..., "10": 27790}
}
```

| Field          | Type           | Notes                                         |
| -------------- | -------------- | --------------------------------------------- |
| `rating`       | float          | 0-10, already normalized                      |
| `votes`        | int            |                                               |
| `distribution` | dict[str, int] | 1-10 histogram — out of scope for `Notations` |

---

## Endpoints — Related

```
GET /movies/{id}/related
GET /shows/{id}/related
```

Returns a flat array of movie/show objects (same shape as details, with full fields
when the item is well-known). Max ~20 items. No wrapper (unlike search/trending).

Implementation: maps to `get_recommendations()` returning `list[Recommendation]`.

---

## Endpoints — Trending

```
GET /movies/trending?limit=10
GET /shows/trending?limit=10
```

Returns array of `{watchers, movie: {...}}` objects.

| Field         | Type   | Notes                               |
| ------------- | ------ | ----------------------------------- |
| `watchers`    | int    | Current active watchers             |
| `movie.ids`   | object | See [IDs and Slugs](#ids-and-slugs) |
| `movie.title` | str    |                                     |
| `movie.year`  | int    |                                     |

Movie sub-objects in trending are **thin** — only `ids`, `title`, `year`. For full
details, call `/movies/{id}?extended=full`.

Implementation: out of scope for Phase 15 core; can be added as a bonus endpoint.

---

## Image URLs

Trakt returns relative image paths:

```
media.trakt.tv/images/movies/000/016/662/posters/medium/1fb1d284b7.jpg.webp
```

Build full URL with `https://` prefix. No size variant parameter — Trakt returns
the `medium` size path directly.

Available image types (from details with `extended=full`):

| Key        | Type                      | ArtworkItem.type                                       |
| ---------- | ------------------------- | ------------------------------------------------------ |
| `poster`   | Vertical poster           | `poster`                                               |
| `fanart`   | Backdrop/background       | `backdrop`                                             |
| `banner`   | Wide banner               | `banner` (not in ArtworkItem type — map to `backdrop`) |
| `logo`     | Title logo                | Skip (no match in ArtworkItem model)                   |
| `thumb`    | Small thumbnail           | Skip                                                   |
| `clearart` | Transparent character art | Skip                                                   |

Each image key is a list of URLs (typically 1 entry).

---

## Particularities

### Dual-header app-only auth (by design)

Trakt's app-only auth uses two headers on every request: `trakt-api-key`
(the Client ID) and `trakt-api-version: 2`. This is intentional, not an
inconsistency — both headers are mandatory for the public, app-authenticated
surface this provider consumes: `search`, movie/show `details`, `ratings`,
`related`, and `trending`. None of those require a user context.

User-specific OAuth endpoints (watchlist, history, check-in,
`/recommendations`) need a per-user Bearer token and are deliberately **out
of scope** — the provider never sends an `Authorization` header.

### Response wrapper varies by endpoint

| Endpoint               | Wrapper                              |
| ---------------------- | ------------------------------------ |
| `/search/{type}`       | `[{score, type, movie/show: {...}}]` |
| `/{type}/trending`     | `[{watchers, movie/show: {...}}]`    |
| `/{type}/{id}`         | Flat object                          |
| `/{type}/{id}/related` | Flat array of objects                |
| `/{type}/{id}/ratings` | Flat object                          |

Each endpoint needs its own response parser.

### `extended=full` is essential

Without it, movie/show details return only `title`, `year`, `ids`. Always pass
`?extended=full` on detail calls.

### TV show `status` field

Values: `"ended"`, `"returning series"`, `"canceled"`, `"in production"`.
Analogous to OMDB's `Year` range parsing — use `status == "ended"` to know
if the year range is closed.

### `related` vs `recommendations`

- `/related` — public, no OAuth needed → maps to `get_recommendations()`.
- `/recommendations` — requires OAuth user token → out of scope.

### Rating is already 0-10

Unlike OMDB (string parsing), Trakt ratings are native floats. No parsing needed.

### No `Response` field

Trakt uses HTTP status codes exclusively. No in-band error signaling.

---

## Test Samples

6 captured API responses in `docs/reference/_samples/trakt/`:

| File                           | Endpoint                                    | Type           |
| ------------------------------ | ------------------------------------------- | -------------- |
| `search-inception.json`        | `/search/movie?query=Inception&year=2010`   | Movie search   |
| `movie-details-inception.json` | `/movies/inception-2010?extended=full`      | Movie detail   |
| `movie-ratings-inception.json` | `/movies/inception-2010/ratings`            | Ratings        |
| `movie-related-inception.json` | `/movies/inception-2010/related`            | Related movies |
| `movies-trending.json`         | `/movies/trending?limit=10`                 | Trending       |
| `search-breaking-bad.json`     | `/search/show?query=Breaking+Bad&year=2008` | TV search      |
