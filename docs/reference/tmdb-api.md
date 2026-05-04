# TMDB API — Reference

> The Movie Database API v3 — reference for the `api/metadata/tmdb.py` provider.
> Source: https://developer.themoviedb.org/docs/getting-started
> Last updated: 2026-05-04

---

## Table of Contents

- [Authentication](#authentication)
- [Base URLs](#base-urls)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Language & Region](#language--region)
- [Images](#images)
- [append_to_response](#append_to_response)
- [Pagination](#pagination)
- [Endpoints — Movies](#endpoints--movies)
  - [Search Movies](#search-movies)
  - [Movie Details](#movie-details)
  - [Movie Videos](#movie-videos)
  - [Movie Keywords](#movie-keywords)
- [Endpoints — TV Shows](#endpoints--tv-shows)
  - [Search TV](#search-tv)
  - [TV Details](#tv-details)
  - [TV Videos](#tv-videos)
  - [TV Keywords](#tv-keywords)
- [Endpoints — Seasons](#endpoints--seasons)
  - [Season Details](#season-details)
  - [Season Videos](#season-videos)
- [Response Schemas](#response-schemas)
- [Provider Implementation Notes](#provider-implementation-notes)
- [Particularities](#particularities)

---

## Authentication

Two equivalent methods (same access level):

### Bearer Token (recommended)

```
Authorization: Bearer <TMDB_API_KEY>
```

The key is TMDB's **API Read Access Token** (v4), available at https://www.themoviedb.org/settings/api.
Works with all v3 endpoints. This is what `BearerAuth(token)` produces.

### API Key (query parameter — legacy)

```
GET /3/movie/550?api_key=<TMDB_API_KEY>
```

Still supported for v3 but the Bearer approach is preferred as it works across v3 and v4.

### Credential in the pipeline

```
.env → TMDB_API_KEY=<your_read_access_token>
```

`PROVIDER_CREDS["tmdb"] = ["TMDB_API_KEY"]` in `api/_activation.py`.

---

## Base URLs

| Purpose | URL                            |
| ------- | ------------------------------ |
| API v3  | `https://api.themoviedb.org/3` |
| Images  | `https://image.tmdb.org/t/p/`  |

`HttpTransport` policy uses `base_url = "https://api.themoviedb.org/3"`.

---

## Rate Limiting

| Property        | Value                               |
| --------------- | ----------------------------------- |
| Approx. ceiling | ~40 requests/second (per IP)        |
| HTTP status     | 429                                 |
| TMDB error code | 25                                  |
| Header signal   | No `Retry-After` or `X-RateLimit-*` |

The limit is **not contractual** — it may change at any time. TMDB asks clients to "respect the 429."

`RetryPolicy(retryable_statuses=frozenset({429, 500, 502, 503, 504}))` handles this.

**Important**: `append_to_response` sub-requests do NOT count as separate calls for rate-limit purposes.

---

## Error Handling

### Response Format

TMDB returns a JSON body with two error fields:

```json
{
  "status_code": 7,
  "status_message": "Invalid API key: You must be granted a valid key."
}
```

The HTTP status code reflects the error class (4xx/5xx). The `status_code` is **TMDB-internal** — NOT the HTTP code.

`ApiError` captures both: `http_status` = HTTP code, `provider_code` = `status_code`.

### Key Error Codes

| Code | HTTP | Meaning                    |
| ---- | ---- | -------------------------- |
| 3    | 401  | Authentication failed      |
| 7    | 401  | Invalid API key            |
| 10   | 401  | Suspended API key          |
| 22   | 400  | Invalid page (max 500)     |
| 25   | 429  | Rate limit exceeded        |
| 34   | 404  | Resource not found         |
| 46   | 503  | API undergoing maintenance |

Full table: https://developer.themoviedb.org/docs/errors (47 codes).

---

## Language & Region

### `language` parameter

- Format: ISO 639-1 + region (`fr-FR`, `en-US`).
- Controls translated fields: `title`, `overview`, `tagline`.
- If the requested language is unavailable, TMDB **falls back to the original language** (not English).
- Some fields are NEVER translated: `original_title`, `original_name`, `original_language`.

### `include_image_language`

Filters images returned in `images` by language:

```
include_image_language=fr,en,null
```

- `null` = language-less images (logos, backgrounds without text).
- Order matters: first match wins. Recommended: `fr,en,null`.

### Region

`region=FR` affects release date availability, certification, and watch provider data.

---

## Images

### URL Construction

```
https://image.tmdb.org/t/p/{size}{file_path}
```

Where `size` is a width code (e.g. `w500`, `w1280`, `original`) and `file_path` comes from the media object (e.g. `poster_path`, `backdrop_path`).

### Image Types & Recommended Sizes

| Type     | Field           | Pipeline size | Fallback   |
| -------- | --------------- | ------------- | ---------- |
| Poster   | `poster_path`   | `w780`        | `w500`     |
| Backdrop | `backdrop_path` | `w1280`       | `w780`     |
| Still    | `still_path`    | `w300`        | `w185`     |
| Logo     | `logo_path`     | `original`    | `original` |
| Profile  | `profile_path`  | `w185`        | `w92`      |

SVG logos: always use `original` size (TMDB does not resize SVGs).

### Response Structure

Images come in separate arrays:

```json
{
  "id": 550,
  "backdrops":  [{ "file_path": "...", "width": 1920, "height": 1080, "iso_639_1": null, ... }],
  "posters":    [{ "file_path": "...", "width": 1000, "height": 1500, "iso_639_1": "fr", ... }],
  "logos":      [{ "file_path": "...", "width": 800,  "height": 400,  "iso_639_1": null, ... }]
}
```

The provider must merge these into a single `list[ArtworkItem]` with correct `type` mapping:
`backdrops` → `"backdrop"`, `posters` → `"poster"`, `logos` → `"landscape"`.

Season posters use `season` field; other images leave it `None`.

### Configuration Endpoint

`GET /3/configuration` returns the current `images.base_url`, `images.secure_base_url`, and `images.*_sizes` arrays. This data rarely changes — you can hardcode the `"https://image.tmdb.org/t/p/"` base after a one-time check.

---

## append_to_response

Appends sub-resource data to a single API call, avoiding N+1 requests.

### Syntax

```
GET /3/movie/550?append_to_response=videos,images,keywords
```

Each sub-resource appears as a top-level key in the response: `"videos": {...}`, `"images": {...}`.

### Supported on

/movie/{id}, /tv/{id}, /tv/{id}/season/{n}, /person/{id}

### Commonly used values

| Value             | What it returns             |
| ----------------- | --------------------------- |
| `videos`          | Trailer/teaser/clip list    |
| `images`          | Backdrops + posters + logos |
| `keywords`        | Keywords list               |
| `external_ids`    | IMDb, Wikidata, etc. IDs    |
| `recommendations` | Similar movies/shows        |
| `similar`         | Similar (different algo)    |
| `watch/providers` | Streaming availability      |

### Limits

- Max 20 values per call (TMDB error code 27).
- Sub-requests do NOT count toward rate limits.
- Response size can become large — only append what you need.

---

## Pagination

Search results are paginated:

```json
{
  "page": 1,
  "results": [...],
  "total_pages": 500,
  "total_results": 12473
}
```

- 20 results per page.
- `total_pages` is **capped at 500** (TMDB error code 22 for page > 500).
- `total_results` is accurate even with the 500-page cap.
- Empty search: HTTP 200, `results: []`, `total_pages: 1`, `total_results: 0`.

---

## Endpoints — Movies

### Search Movies

```
GET /3/search/movie
```

**Parameters**:

| Param                  | Type   | Required | Description                |
| ---------------------- | ------ | -------- | -------------------------- |
| `query`                | string | Yes      | Search term                |
| `year`                 | int    | No       | Filter by release year     |
| `language`             | string | No       | Default: `en-US`           |
| `page`                 | int    | No       | Default: 1, max: 500       |
| `include_adult`        | bool   | No       | Default: false             |
| `region`               | string | No       | ISO 3166-1 (e.g. `FR`)     |
| `primary_release_year` | int    | No       | Exact primary release year |

**Response**: `SearchResult`-compatible. Fields: `id`, `title`, `overview`, `release_date`, `poster_path`, `backdrop_path`, `genre_ids` (list of int), `popularity`, `vote_average`, `original_language`, `adult`.

**Note**: `genre_ids` is an array of **integer** genre IDs — NOT objects with names. Get genre names via `/3/genre/movie/list`.

### Movie Details

```
GET /3/movie/{id}
```

**Parameters**:

| Param                    | Type   | Required | Description                   |
| ------------------------ | ------ | -------- | ----------------------------- |
| `language`               | string | No       | Default: `en-US`              |
| `append_to_response`     | string | No       | Comma-separated sub-resources |
| `include_image_language` | string | No       | Comma-separated ISO codes     |

**Response**: `MediaDetails`-compatible. Fields: `id`, `title`, `original_title`, `overview`, `release_date`, `runtime`, `genres` (array of `{id, name}` objects), `vote_average`, `vote_count`, `poster_path`, `backdrop_path`, `tagline`, `status`, `budget`, `revenue`, `spoken_languages`, `production_countries`, `production_companies`.

**Particularity**: `runtime` is optional (null for unreleased or unprocessed movies). `release_date` may be an empty string `""`.

### Movie Videos

```
GET /3/movie/{id}/videos
```

**Parameters**:

| Param      | Type   | Required | Description         |
| ---------- | ------ | -------- | ------------------- |
| `language` | string | No       | Filter by ISO 639-1 |

**Response**: `{ "id": int, "results": [{ "id": str, "key": str, "site": str, "type": str, "official": bool, "size": int, "iso_639_1": str, ... }] }`.

`type` values: `Trailer`, `Teaser`, `Clip`, `Featurette`, `Behind the Scenes`, `Bloopers`.

### Movie Keywords

```
GET /3/movie/{id}/keywords
```

**Response**: `{ "id": int, "keywords": [{ "id": int, "name": str }] }`.

Note the envelope is `keywords` (NOT `results`).

---

## Endpoints — TV Shows

### Search TV

```
GET /3/search/tv
```

**Parameters**: Same as `/search/movie` except `first_air_date_year` replaces `year`/`primary_release_year`.

**Response**: Same structure as movie search. `genre_ids` is array of int. `first_air_date` instead of `release_date`.

### TV Details

```
GET /3/tv/{id}
```

**Parameters**: Same as movie details (`language`, `append_to_response`, `include_image_language`).

**Response**: Fields: `id`, `name`, `original_name`, `overview`, `first_air_date`, `last_air_date`, `number_of_seasons`, `number_of_episodes`, `episode_run_time` (array of int, may be empty), `genres`, `vote_average`, `poster_path`, `backdrop_path`, `status`, `type`, `created_by`, `networks`, `seasons` (array of `{id, name, season_number, episode_count, poster_path}`).

**Particularity**: `episode_run_time` is an array — use the first value or derive from season/episode data. `runtime` in `MediaDetails` may be null for TV shows.

### TV Videos

```
GET /3/tv/{id}/videos
```

Same structure as movie videos. Filter by `language`.

### TV Keywords

```
GET /3/tv/{id}/keywords
```

**Response**: `{ "id": int, "results": [{ "id": int, "name": str }] }`.

**WARNING**: TV keywords uses the envelope `results`, NOT `keywords` (different from movies!). This is a known inconsistency in TMDB's API.

---

## Endpoints — Seasons

### Season Details

```
GET /3/tv/{id}/season/{season_number}
```

**Parameters**:

| Param                    | Type   | Required | Description               |
| ------------------------ | ------ | -------- | ------------------------- |
| `language`               | string | No       | Default: `en-US`          |
| `append_to_response`     | string | No       | Comma-separated           |
| `include_image_language` | string | No       | Comma-separated ISO codes |

**Response**: `SeasonDetails`-compatible. Fields: `id`, `name`, `overview`, `season_number`, `air_date`, `poster_path`, `episodes` (array of episode objects), `images` (if appended).

Episode object: `id`, `name`, `overview`, `air_date`, `episode_number`, `season_number`, `runtime`, `still_path`, `vote_average`, `vote_count`, `crew`, `guest_stars`.

**Particularity**: Season 0 = specials. `air_date` and `runtime` may be null for unaired episodes.

### Season Videos

```
GET /3/tv/{id}/season/{season_number}/videos
```

**Parameters**:

| Param      | Type   | Required | Description         |
| ---------- | ------ | -------- | ------------------- |
| `language` | string | No       | Filter by ISO 639-1 |

Same structure as movie videos. Returns empty `results` for many older shows.

---

## Response Schemas

### Search Response (movie & tv)

```json
{
  "page": 1,
  "results": [
    {
      "id": 550,
      "title": "Fight Club", // "name" for TV
      "overview": "...",
      "release_date": "1999-10-15", // "first_air_date" for TV
      "poster_path": "/path.jpg",
      "backdrop_path": "/path.jpg",
      "genre_ids": [18, 53],
      "original_language": "en",
      "original_title": "Fight Club", // "original_name" for TV
      "popularity": 73.0,
      "vote_average": 8.4,
      "vote_count": 27000,
      "adult": false
    }
  ],
  "total_pages": 1,
  "total_results": 1
}
```

### Movie Details Response (with append_to_response)

```json
{
  "id": 550,
  "title": "Fight Club",
  "original_title": "Fight Club",
  "overview": "A ticking-time-bomb insomniac...",
  "release_date": "1999-10-15",
  "runtime": 139,
  "genres": [
    { "id": 18, "name": "Drama" },
    { "id": 53, "name": "Thriller" }
  ],
  "vote_average": 8.435,
  "vote_count": 29588,
  "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
  "backdrop_path": "/hZkgoQYus5g3egHo5QGCfJXhFq2.jpg",
  "tagline": "Mischief. Mayhem. Soap.",
  "status": "Released",
  "original_language": "en",
  "spoken_languages": [{ "iso_639_1": "en", "name": "English" }],
  "videos": {
    "results": [
      {
        "id": "5c929d28c3a3680f3aac5566",
        "key": "SUXWAEX2jlg",
        "site": "YouTube",
        "type": "Trailer",
        "official": true,
        "size": 1080,
        "iso_639_1": "en"
      }
    ]
  },
  "images": {
    "backdrops": [
      { "file_path": "...", "width": 1920, "height": 1080, "iso_639_1": null }
    ],
    "posters": [
      { "file_path": "...", "width": 1000, "height": 1500, "iso_639_1": "en" }
    ],
    "logos": [
      { "file_path": "...", "width": 800, "height": 400, "iso_639_1": null }
    ]
  },
  "keywords": {
    "keywords": [
      { "id": 825, "name": "support group" },
      { "id": 9672, "name": "based on novel" }
    ]
  }
}
```

---

## Provider Implementation Notes

### What TMDBClient MUST implement

| Method               | Endpoint                                      | Returns              |
| -------------------- | --------------------------------------------- | -------------------- |
| `search()`           | `/search/movie` or `/search/tv`               | `list[SearchResult]` |
| `get_details()`      | `/movie/{id}` or `/tv/{id}`                   | `MediaDetails`       |
| `get_artwork_urls()` | From `append_to_response=images`              | `list[ArtworkItem]`  |
| `get_keywords()`     | `/movie/{id}/keywords` or `/tv/{id}/keywords` | `list[str]`          |
| `get_videos()`       | `/movie/{id}/videos` or `/tv/{id}/videos`     | `list[Video]`        |
| `get_season()`       | `/tv/{id}/season/{n}`                         | `SeasonDetails`      |

### TransportPolicy

```python
TransportPolicy(
    provider_name="TMDB",
    base_url="https://api.themoviedb.org/3",
    auth=BearerAuth(os.environ["TMDB_API_KEY"]),
    retry=RetryPolicy(
        max_attempts=4,
        initial_wait=0.5,
        max_wait=10.0,
        retryable_statuses=frozenset({429, 500, 502, 503, 504}),
    ),
    circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
    rate_limit=RateLimitPolicy(requests_per_second=40),
    extra_headers={"Accept": "application/json"},
    response_format="json",
)
```

### Image URL Building

```python
IMAGE_BASE = "https://image.tmdb.org/t/p/"

def build_image_url(path: str, size: str = "w780") -> str:
    if not path:
        return ""
    return f"{IMAGE_BASE}{size}{path}"
```

---

## Particularities

### 1. `release_date` may be empty string

For unreleased or upcoming movies, `release_date` is `""` (not null). Cast to `int | None` for `year`:

```python
year = int(d["release_date"][:4]) if d.get("release_date") else None
```

**Decision**: Handle — parse defensively, return `None` if empty.

### 2. `genre_ids` (int) vs `genres` (object)

Search returns `genre_ids: [18, 53]` (int array). Details returns `genres: [{id: 18, name: "Drama"}]` (object array). The provider must resolve IDs to names for `SearchResult` if genre names are needed, or leave as provider-specific IDs.

**Decision**: For search, store genre IDs in `external_ids` or leave `MediaDetails.genres` for the details call only. During migration Phase 5, if the existing pipeline resolves genre IDs from the cached genre list, preserve that behavior.

### 3. TV keywords envelope inconsistency

`/movie/{id}/keywords` returns `{"keywords": [...]}` while `/tv/{id}/keywords` returns `{"results": [...]}`. The provider must handle both.

**Decision**: Handle in the keyword extraction method — check both keys.

### 4. `episode_run_time` is an array

TV details returns `episode_run_time: [25, 30]` (array of ints). The pipeline currently uses `RuntimeExtractor` which handles this. For `MediaDetails.runtime_minutes`, use the most common value or the first entry.

**Decision**: Use `max()` or first entry. Leave `None` if array is empty.

### 5. `runtime` can be null

Both movie and episode `runtime` fields may be `None`/null. `MediaDetails.runtime_minutes` and `EpisodeInfo.runtime_minutes` are `int | None`.

**Decision**: Already handled via optional types in typed models.

### 6. Pagination ceiling (500 pages)

`total_pages` is capped at 500. Searches with >10,000 results cannot be fully paginated. The pipeline's `_search_paginated` respects `max_pages` to avoid infinite loops.

**Decision**: Migrate the `max_pages` parameter from current `tmdb_client.py`. Default to 5 pages (100 results) for pipeline use.

### 7. `append_to_response` sub-requests don't count toward rate limits

So fetching details with `append_to_response=videos,images,keywords` counts as 1 request, not 4.

**Decision**: Always use `append_to_response` when fetching details. This is how the current code works — preserve the pattern.

### 8. Image language filtering

`include_image_language=fr,en,null` controls which language images are returned. `null` includes images without language (backdrops, logos). Order matters: first match wins.

**Decision**: Use `include_image_language={language},{fallback_language},null` where values come from `MetadataConfig.defaults`.

### 9. Season 0 = specials

TV shows have a season 0 containing specials, behind-the-scenes, etc. The pipeline currently ignores season 0.

**Decision**: Out of scope for Phase 5 — preserve existing behavior (skip season 0).

### 10. `videos.results[].official` boolean

TMDB returns both official trailers and fan-uploaded content. Filter by `official=True` or keep both.

**Decision**: Keep both, expose `official` via `Video.official` field. The caller decides whether to filter.

---

## Rate Limit Handling

TMDB's ~40 req/s ceiling is approximate. The provider uses `RateLimitPolicy(requests_per_second=40)` as a soft cap via the token-bucket `RateLimiter`. Combined with `RetryPolicy` (retries on 429), the transport handles throttling transparently.

TMDB error code 25 maps to HTTP 429 → `retryable_statuses` includes 429 → tenacity retries with exponential backoff.

Circuit breaker opens after 5 consecutive failures (HTTP 5xx or connection errors) and stays open for 5 minutes.

---

## Golden Test Samples

Sample responses are captured in `docs/reference/_samples/tmdb/` for use in Phase 5 golden tests:

- `search_movie.json` — `GET /3/search/movie?query=Fight+Club`
- `search_tv.json` — `GET /3/search/tv?query=Breaking+Bad`
- `movie_details.json` — `GET /3/movie/550?append_to_response=videos,images,keywords`
- `tv_details.json` — `GET /3/tv/1396?append_to_response=videos,images,keywords`
- `season_details.json` — `GET /3/tv/1396/season/1`
- `movie_videos.json` — `GET /3/movie/550/videos`
- `tv_videos.json` — `GET /3/tv/1396/videos`

Samples are captured via live API calls (requires `TMDB_API_KEY` in `.env`).
