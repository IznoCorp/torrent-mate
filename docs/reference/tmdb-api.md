# TMDB API — Reference

> The Movie Database API v3 — comprehensive reference for the
> `personalscraper/api/metadata/tmdb.py` provider (scrape step).
> Source: https://developer.themoviedb.org/docs/getting-started
> Last updated: 2026-06-01

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
  - [Movie Credits](#movie-credits)
  - [Movie Images](#movie-images)
  - [Movie External IDs](#movie-external-ids)
  - [Movie Videos](#movie-videos)
  - [Movie Keywords](#movie-keywords)
  - [Discover Movies](#discover-movies)
- [Endpoints — TV Shows](#endpoints--tv-shows)
  - [Search TV](#search-tv)
  - [TV Details](#tv-details)
  - [TV Aggregate Credits](#tv-aggregate-credits)
  - [TV Images](#tv-images)
  - [TV External IDs](#tv-external-ids)
  - [TV Videos](#tv-videos)
  - [TV Keywords](#tv-keywords)
- [Endpoints — Seasons](#endpoints--seasons)
  - [Season Details](#season-details)
  - [Season Images](#season-images)
  - [Season Videos](#season-videos)
- [Endpoints — Episodes](#endpoints--episodes)
  - [Episode Details](#episode-details)
  - [Episode Images](#episode-images)
- [Endpoints — Utilities](#endpoints--utilities)
  - [Configuration](#configuration)
  - [Find by External ID](#find-by-external-id)
  - [Search Multi](#search-multi)
  - [Genres (Movies)](#genres-movies)
  - [Genres (TV)](#genres-tv)
  - [Certifications](#certifications)
- [Certifications FR — Extraction](#certifications-fr--extraction)
- [Optimal Call Strategy](#optimal-call-strategy)
- [Response Schemas](#response-schemas)
- [Provider Implementation Notes](#provider-implementation-notes)
- [Particularities](#particularities)
- [Verified Edge Cases](#verified-edge-cases)
- [Daily ID Exports](#daily-id-exports)
- [Golden Test Samples](#golden-test-samples)

---

## Authentication

Two equivalent methods (same access level):

### Bearer Token (recommended)

```
Authorization: Bearer <TMDB_API_KEY>
```

The key is TMDB's **API Read Access Token** (v4), available at https://www.themoviedb.org/settings/api.
Works with all v3 endpoints. This is what `BearerAuth(token)` produces. The
pipeline stores it under the `TMDB_API_KEY` env var and consumes it as a Bearer
token (not a query-parameter API key).

### API Key (query parameter — legacy)

```
GET /3/movie/550?api_key=<TMDB_API_KEY>
```

Still supported for v3 but the Bearer approach is preferred as it works across v3 and v4.

### Credential in the pipeline

```
<project_root>/.env → TMDB_API_KEY=<your_read_access_token>
```

`PROVIDER_CREDS["tmdb"] = ["TMDB_API_KEY"]` in `personalscraper/api/_activation.py`.
`resolve_active()` disables the provider (and logs `provider_disabled`) if the
credential is missing while the toggle is enabled.

---

## Base URLs

| Purpose      | URL                             |
| ------------ | ------------------------------- |
| API v3       | `https://api.themoviedb.org/3`  |
| API v4       | `https://api.themoviedb.org/4/` |
| Images HTTP  | `http://image.tmdb.org/t/p/`    |
| Images HTTPS | `https://image.tmdb.org/t/p/`   |

`HttpTransport` policy uses `base_url = "https://api.themoviedb.org/3"`.
All responses are `application/json`.

---

## Rate Limiting

| Property        | Value                               |
| --------------- | ----------------------------------- |
| Approx. ceiling | ~40 requests/second (per IP)        |
| HTTP status     | 429                                 |
| TMDB error code | 25                                  |
| Header signal   | No `Retry-After` or `X-RateLimit-*` |

The limit is **not contractual** — it may change at any time. TMDB asks clients to "respect the 429."

> The legacy 40-requests-per-10-seconds limit was disabled on 2019-12-16. The
> current limit is looser but still present to prevent mass scraping.

`RetryPolicy(retryable_statuses=frozenset({429, 500, 502, 503, 504}))` handles this.

**Important**: `append_to_response` sub-requests do NOT count as separate calls for rate-limit purposes.

See also [Rate Limit Handling](#rate-limit-handling) under Provider Implementation Notes.

---

## Error Handling

### Response Format

TMDB returns a JSON body with two error fields:

```json
{
  "status_code": 7,
  "status_message": "Invalid API key: You must be granted a valid key.",
  "success": false
}
```

The HTTP status code reflects the error class (4xx/5xx). The `status_code` is
**TMDB-internal** — NOT the HTTP code. Always check both.

`ApiError` captures both: `http_status` = HTTP code, `provider_code` = `status_code`.

**Real example — resource not found** (HTTP 404):

```json
{
  "success": false,
  "status_code": 34,
  "status_message": "The resource you requested could not be found."
}
```

**Caution**: an empty search returns HTTP **200** with `results: []`, NOT a 404.
HTTP 404 is only returned for an invalid specific ID (e.g. `/movie/9999999`).
The code must check `len(results)`, not the HTTP status.

### Key Error Codes

| Code | HTTP | Meaning                                | Pipeline action                |
| ---- | ---- | -------------------------------------- | ------------------------------ |
| 3    | 401  | Authentication failed                  | Check config, abort            |
| 5    | 422  | Invalid parameters                     | Fix the request, log error     |
| 6    | 404  | Invalid ID                             | Skip, log warning              |
| 7    | 401  | Invalid API key                        | Check config, abort            |
| 9    | 503  | Service temporarily unavailable        | Retry with backoff             |
| 10   | 401  | Suspended API key                      | Check account, abort           |
| 11   | 500  | TMDB internal error                    | Retry with backoff             |
| 22   | 400  | Invalid page (max 500)                 | Cap at 500                     |
| 24   | 504  | Backend timeout                        | Retry with backoff             |
| 25   | 429  | Rate limit exceeded                    | Retry with exponential backoff |
| 27   | 400  | Too many `append_to_response` (max 20) | Reduce the count               |
| 34   | 404  | Resource not found                     | Skip, log "not found"          |
| 46   | 503  | API undergoing maintenance             | Retry later                    |

Full table: https://developer.themoviedb.org/docs/errors (47 codes).

### Retryable codes

HTTP `429`, `500`, `502`, `503`, `504` → retry with exponential backoff.

### Fatal codes

HTTP `401`, `403` → authentication problem, do not retry.

---

## Language & Region

### `language` parameter

- Format: ISO 639-1 + optional region (`fr-FR`, `en-US`, `pt-BR`, `de-DE`).
- Default: `en-US`.
- Controls translated fields: `title`, `overview`, `tagline`, genre names, episode names.
- If the requested language is unavailable, TMDB **falls back to the original
  language** (not English).
- Some fields are NEVER translated: `original_title`, `original_name`,
  `original_language`, person names (actors, directors), character names.

### `include_image_language`

Filters images returned in `images` by language:

```
include_image_language=fr,en,null
```

- `fr` — French images.
- `en` — English images.
- `null` = language-less images (logos, backgrounds without text).
- Order matters: first match wins. Recommended: `fr,en,null`.

> **⚠️ Important gotcha**: the `language` parameter also filters images. With
> `language=fr-FR` alone, only French images are returned (often very few). Use
> `include_image_language` to widen the set. See
> [Movie Images](#movie-images) for the verified impact table.

### Region

`region=FR` affects release date availability, certification, and watch provider data.

---

## Images

### URL Construction

```
{secure_base_url}{size}{file_path}
```

Example:

```
https://image.tmdb.org/t/p/w500/1E5baAaEse26fej7uHcjOgEE2t2.jpg
```

Where `size` is a width code (e.g. `w500`, `w1280`, `original`) and `file_path`
comes from the media object (e.g. `poster_path`, `backdrop_path`).

### Available Sizes by Type

| Image type   | Available sizes                                           |
| ------------ | --------------------------------------------------------- |
| **poster**   | `w92`, `w154`, `w185`, `w342`, `w500`, `w780`, `original` |
| **backdrop** | `w300`, `w780`, `w1280`, `original`                       |
| **logo**     | `w45`, `w92`, `w154`, `w185`, `w300`, `w500`, `original`  |
| **profile**  | `w45`, `w185`, `h632`, `original`                         |
| **still**    | `w92`, `w185`, `w300`, `original`                         |

- `w` = width constraint (height proportional).
- `h` = height constraint (width proportional).
- `original` = original resolution as uploaded.

### Image Types & Pipeline Sizes

The provider (`_tmdb_parsers.parse_artwork`) maps the separate arrays to
`ArtworkItem` at fixed sizes:

| Type     | Field           | Array       | Pipeline size | `ArtworkItem.type`    |
| -------- | --------------- | ----------- | ------------- | --------------------- |
| Backdrop | `backdrop_path` | `backdrops` | `w1280`       | `"backdrop"`          |
| Poster   | `poster_path`   | `posters`   | `w780`        | `"poster"`            |
| Logo     | `logo_path`     | `logos`     | `w500`        | `"landscape"`         |
| Still    | `still_path`    | `stills`    | `w300`        | (episode `still_url`) |
| Profile  | `profile_path`  | —           | `w185`        | (cast/crew profile)   |

Search result posters are built at `w500`; season-info posters at `w500`. When
`parse_artwork` receives a `season` argument, posters become
`ArtworkItem(type="season_poster")`. SVG logos: always use `original` (TMDB does
not resize SVGs).

### Image Object (common structure)

```json
{
  "file_path": "/pEoqbqtLc4CcwDUDqxmEDSWpWTZ.jpg",
  "aspect_ratio": 0.667,
  "width": 2000,
  "height": 3000,
  "iso_639_1": "fr",
  "iso_3166_1": "FR",
  "vote_average": 5.312,
  "vote_count": 3
}
```

- `iso_639_1` = `null` for language-less images (no embedded text) — the
  majority of backdrops.
- `iso_3166_1` = country code (present in real responses, absent from the
  official TMDB docs).

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

The provider merges these into a single `list[ArtworkItem]`, ordered
backdrops → posters → logos.

### Configuration Endpoint

`GET /3/configuration` returns the current `images.base_url`,
`images.secure_base_url`, and `images.*_sizes` arrays. This data rarely changes —
you can hardcode the `"https://image.tmdb.org/t/p/"` base after a one-time check
(`_tmdb_parsers.IMAGE_BASE`). TMDB recommends caching it and refreshing every few
days. See [Configuration](#configuration).

---

## append_to_response

Appends sub-resource data to a single API call, avoiding N+1 requests.

### Syntax

```
GET /3/movie/550?append_to_response=credits,images,external_ids&language=fr-FR
```

Each sub-resource appears as a top-level key in the response: `"videos": {...}`, `"images": {...}`.

### Supported endpoints

| Endpoint           | Supports `append_to_response` |
| ------------------ | ----------------------------- |
| Movie Details      | Yes (max 20)                  |
| TV Series Details  | Yes (max 20)                  |
| TV Season Details  | Yes (max 20)                  |
| TV Episode Details | Yes (max 20)                  |
| Person Details     | Yes (max 20)                  |
| Search (all)       | No                            |
| Find               | No                            |

### Key rules

1. **Max 20 items** per call (TMDB error code 27).
2. Each sub-request appears as a new JSON key in the response.
3. The `language` parameter applies to all sub-requests.
4. For images, use `include_image_language` in addition.
5. **Sub-requests do NOT count** as separate calls for rate limiting.
6. Response size can become large — only append what you need.

### Common values

| Value               | What it returns                             |
| ------------------- | ------------------------------------------- |
| `credits`           | Cast + crew (flat)                          |
| `aggregate_credits` | TV cast + crew grouped (`roles[]`/`jobs[]`) |
| `videos`            | Trailer/teaser/clip list                    |
| `images`            | Backdrops + posters + logos                 |
| `keywords`          | Keywords list                               |
| `external_ids`      | IMDb, TVDB, Wikidata, etc. IDs              |
| `release_dates`     | Release dates + certifications (movies)     |
| `content_ratings`   | Content ratings (TV)                        |
| `recommendations`   | Similar movies/shows                        |
| `similar`           | Similar (different algo)                    |
| `watch/providers`   | Streaming availability                      |

**Movies**: `credits`, `images`, `external_ids`, `videos`, `release_dates`,
`keywords`, `alternative_titles`, `translations`, `recommendations`, `similar`,
`reviews`, `watch/providers`.

**TV shows**: `aggregate_credits`, `credits`, `external_ids`, `images`,
`content_ratings`, `videos`, `keywords`, `alternative_titles`, `translations`,
`recommendations`, `similar`, `reviews`, `watch/providers`, `episode_groups`.

**Seasons / Episodes**: `images`, `credits`, `videos`, `translations`.

> **Provider note**: `TMDBClient.get_movie()` / `get_tv()` always use
> `append_to_response=videos,images,keywords,external_ids` plus
> `include_image_language={language},{fallback_language},en,null`. This packs
> details, artwork, videos, keywords, and external IDs into a single billable
> request.

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

The provider's `_search_paginated` walks pages up to `max_pages` (default 5 =
100 results), stopping early on an empty page or when `page >= total_pages`.

---

## Endpoints — Movies

### Search Movies

```
GET /3/search/movie
```

**Parameters**:

| Param                  | Type    | Required | Default | Description                                             |
| ---------------------- | ------- | -------- | ------- | ------------------------------------------------------- |
| `query`                | string  | **Yes**  | —       | Search term                                             |
| `language`             | string  | No       | `en-US` | Result language                                         |
| `page`                 | int     | No       | `1`     | Page (1–500)                                            |
| `year`                 | string  | No       | —       | Boosts relevance for this year (⚠️ NOT a strict filter) |
| `primary_release_year` | string  | No       | —       | Boosts relevance by primary release year                |
| `region`               | string  | No       | —       | ISO 3166-1 to filter local dates                        |
| `include_adult`        | boolean | No       | `false` | Include adult content                                   |

**Response** (paginated) — real example (`Le Comte de Monte-Cristo`, year=2024, language=fr-FR):

```json
{
  "page": 1,
  "total_pages": 1,
  "total_results": 3,
  "results": [
    {
      "id": 1084736,
      "title": "Le Comte de Monte-Cristo",
      "original_title": "Le Comte de Monte-Cristo",
      "original_language": "fr",
      "overview": "Victime d'un complot, le jeune Edmond Dantès est arrêté...",
      "release_date": "2024-06-28",
      "poster_path": "/oVOEhfRLPIuthVtV8x1yrjCcoFi.jpg",
      "backdrop_path": "/aswBReGLMBGBDrV2LZIIszCdSMZ.jpg",
      "genre_ids": [12, 18, 36],
      "popularity": 45.678,
      "vote_average": 8.1,
      "vote_count": 1800,
      "adult": false,
      "video": false
    }
  ]
}
```

> **⚠️ Verified edge case**: despite `year=2024`, the search also returns the
> 1975 and 1943 versions. The `year` parameter **boosts relevance** but does
> **NOT exclude** other years. The pipeline must filter client-side by
> `release_date` if a strict filter is required.

**Empty response** (no results) — HTTP 200, no error:

```json
{ "page": 1, "results": [], "total_pages": 1, "total_results": 0 }
```

> The code must check `len(results)`, not the HTTP status.

**Note**: `genre_ids` is an array of **integer** genre IDs — NOT objects with
names. Get genre names via `/3/genre/movie/list`.

### Movie Details

```
GET /3/movie/{movie_id}
```

**Parameters**:

| Param                    | In    | Type   | Required | Description                            |
| ------------------------ | ----- | ------ | -------- | -------------------------------------- |
| `movie_id`               | Path  | int    | **Yes**  | TMDB movie ID                          |
| `language`               | Query | string | No       | Default: `en-US`                       |
| `append_to_response`     | Query | string | No       | Comma-separated sub-resources (max 20) |
| `include_image_language` | Query | string | No       | Comma-separated ISO codes              |

**Response**:

```json
{
  "id": 550,
  "title": "Fight Club",
  "original_title": "Fight Club",
  "original_language": "en",
  "overview": "Synopsis...",
  "tagline": "Mischief. Mayhem. Soap.",
  "status": "Released",
  "release_date": "1999-10-15",
  "runtime": 139,
  "budget": 63000000,
  "revenue": 100853753,
  "popularity": 61.416,
  "vote_average": 8.433,
  "vote_count": 28894,
  "adult": false,
  "video": false,
  "imdb_id": "tt0137523",
  "homepage": "http://...",
  "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
  "backdrop_path": "/hZkgoQYus5dXo3H8T7Uef6DNknx.jpg",
  "origin_country": ["US"],

  "genres": [
    { "id": 18, "name": "Drama" },
    { "id": 53, "name": "Thriller" }
  ],

  "belongs_to_collection": null,

  "production_companies": [
    {
      "id": 508,
      "name": "Regency Enterprises",
      "logo_path": "/7PzJdsLGlR7oW4J0J5Xcd0pHGRg.png",
      "origin_country": "US"
    }
  ],

  "production_countries": [
    { "iso_3166_1": "US", "name": "United States of America" }
  ],

  "spoken_languages": [
    { "iso_639_1": "en", "english_name": "English", "name": "English" }
  ]
}
```

**Key fields for the pipeline**: `id`, `title`, `original_title`, `overview`,
`tagline`, `release_date`, `runtime`, `genres`, `imdb_id`, `poster_path`,
`backdrop_path`, `vote_average`, `vote_count`, `production_companies`,
`spoken_languages`.

**Particularity**: `runtime` is optional (null for unreleased or unprocessed
movies). `release_date` may be an empty string `""`.

### Movie Credits

```
GET /3/movie/{movie_id}/credits
```

**Parameters**:

| Param      | Type   | Required | Description      |
| ---------- | ------ | -------- | ---------------- |
| `movie_id` | int    | **Yes**  | TMDB movie ID    |
| `language` | string | No       | Default: `en-US` |

**Response**:

```json
{
  "id": 550,
  "cast": [
    {
      "id": 819,
      "name": "Edward Norton",
      "original_name": "Edward Norton",
      "character": "The Narrator",
      "order": 0,
      "profile_path": "/5XBzD5WuTyVQZeS4VI25z2moMeY.jpg",
      "gender": 2,
      "known_for_department": "Acting",
      "popularity": 26.99,
      "adult": false,
      "cast_id": 4,
      "credit_id": "52fe4250c3a36847f80149f3"
    }
  ],
  "crew": [
    {
      "id": 7467,
      "name": "David Fincher",
      "original_name": "David Fincher",
      "department": "Directing",
      "job": "Director",
      "profile_path": "/tpEczFclQZeKAiCeKZZ0adRvtfz.jpg",
      "gender": 2,
      "known_for_department": "Directing",
      "popularity": 18.45,
      "adult": false,
      "credit_id": "52fe4250c3a36847f8014a11"
    }
  ]
}
```

**`gender` values**: 0 = unspecified, 1 = female, 2 = male, 3 = non-binary.

> **Tip**: use `append_to_response=credits` on `/movie/{id}` to avoid a separate call.

### Movie Images

```
GET /3/movie/{movie_id}/images
```

**Parameters**:

| Param                    | Type   | Required | Description                             |
| ------------------------ | ------ | -------- | --------------------------------------- |
| `movie_id`               | int    | **Yes**  | TMDB movie ID                           |
| `language`               | string | No       | Filters by language (⚠️ restrictive)    |
| `include_image_language` | string | No       | Languages to include, e.g. `fr,en,null` |

**Response**:

```json
{
  "id": 550,
  "backdrops": [
    /* ImageObject[] */
  ],
  "logos": [
    /* ImageObject[] */
  ],
  "posters": [
    /* ImageObject[] */
  ]
}
```

Each array contains Image objects (see [Image Object](#image-object-common-structure)).

> **⚠️ Verified impact of the `include_image_language` gotcha** (movie ID 278,
> _The Shawshank Redemption_):
>
> | Method                                     | Posters  | Backdrops | Logos    |
> | ------------------------------------------ | -------- | --------- | -------- |
> | `language=fr-FR` only (TRAP)               | 15       | 2         | 6        |
> | `include_image_language=fr,en,null` (GOOD) | 73       | 62        | 14       |
> | **Ratio**                                  | **4.9×** | **31×**   | **2.3×** |
>
> Backdrops are the most affected because most of them carry no text
> (`iso_639_1: null`) and are therefore excluded by `language=fr-FR` alone.

### Movie External IDs

```
GET /3/movie/{movie_id}/external_ids
```

**Response**:

```json
{
  "id": 550,
  "imdb_id": "tt0137523",
  "wikidata_id": "Q190050",
  "facebook_id": "FightClub",
  "instagram_id": null,
  "twitter_id": null
}
```

> **Note**: movies have no `tvdb_id`. Use `/find/{imdb_id}` for the reverse
> cross-reference. The provider folds these IDs into `MediaDetails.external_ids`
> (key strips the `_id` suffix, e.g. `imdb`, `wikidata`).

### Movie Videos

```
GET /3/movie/{movie_id}/videos
```

**Parameters**:

| Param      | Type   | Required | Description         |
| ---------- | ------ | -------- | ------------------- |
| `language` | string | No       | Filter by ISO 639-1 |

**Response**: `{ "id": int, "results": [{ "id": str, "key": str, "site": str, "type": str, "official": bool, "size": int, "iso_639_1": str, ... }] }`.

`type` values: `Trailer`, `Teaser`, `Clip`, `Featurette`, `Behind the Scenes`,
`Bloopers`. The provider's `parse_video` normalizes `site` to `youtube`/`vimeo`
(defaulting to `youtube`) and `type` to `trailer`/`teaser`/`clip` (defaulting to
`trailer`).

### Movie Keywords

```
GET /3/movie/{movie_id}/keywords
```

**Response**: `{ "id": int, "keywords": [{ "id": int, "name": str }] }`.

Note the envelope is `keywords` (NOT `results`) — see the
[TV keywords inconsistency](#tv-keywords).

### Discover Movies

```
GET /3/discover/movie
```

Search by filters (no free text). Main parameters:

| Param                           | Type   | Description                       |
| ------------------------------- | ------ | --------------------------------- |
| `language`                      | string | Default: `en-US`                  |
| `page`                          | int    | Default: `1`                      |
| `sort_by`                       | string | Default: `popularity.desc`        |
| `year` / `primary_release_year` | int    | Release year                      |
| `primary_release_date.gte`      | date   | Min date (YYYY-MM-DD)             |
| `primary_release_date.lte`      | date   | Max date (YYYY-MM-DD)             |
| `with_genres`                   | string | Genre IDs (`,` = AND, `\|` = OR)  |
| `with_cast`                     | string | Person IDs (`,` = AND, `\|` = OR) |
| `with_original_language`        | string | ISO 639-1                         |
| `vote_average.gte`              | float  | Minimum rating                    |
| `vote_count.gte`                | float  | Minimum vote count                |
| `with_runtime.gte`              | int    | Min runtime (minutes)             |
| `with_runtime.lte`              | int    | Max runtime (minutes)             |
| `include_adult`                 | bool   | Default: `false`                  |

**Available sort orders**: `popularity.desc`, `popularity.asc`, `revenue.desc`,
`revenue.asc`, `primary_release_date.desc`, `primary_release_date.asc`,
`vote_average.desc`, `vote_average.asc`, `vote_count.desc`, `vote_count.asc`,
`original_title.asc`, `original_title.desc`, `title.asc`, `title.desc`.

**Response**: same paginated structure as Search Movies.

---

## Endpoints — TV Shows

### Search TV

```
GET /3/search/tv
```

**Parameters**:

| Param                 | Type    | Required | Default | Description              |
| --------------------- | ------- | -------- | ------- | ------------------------ |
| `query`               | string  | **Yes**  | —       | Search term              |
| `language`            | string  | No       | `en-US` | Result language          |
| `page`                | int     | No       | `1`     | Page (1–500)             |
| `first_air_date_year` | int     | No       | —       | Filter by first-air year |
| `year`                | int     | No       | —       | Filter by year (broader) |
| `include_adult`       | boolean | No       | `false` | Include adult content    |

The provider uses `first_air_date_year` (mapped from the `year` argument) for TV searches.

**Response** (paginated):

```json
{
  "page": 1,
  "total_pages": 1,
  "total_results": 5,
  "results": [
    {
      "id": 94997,
      "name": "Localized Title",
      "original_name": "Original Name",
      "original_language": "en",
      "overview": "Synopsis...",
      "first_air_date": "2022-03-30",
      "poster_path": "/abc.jpg",
      "backdrop_path": "/def.jpg",
      "genre_ids": [10765, 18],
      "origin_country": ["US"],
      "popularity": 789.12,
      "vote_average": 8.7,
      "vote_count": 4567,
      "adult": false
    }
  ]
}
```

> **Differences vs movies**: `name` instead of `title`, `original_name` instead
> of `original_title`, `first_air_date` instead of `release_date`, plus
> `origin_country`. `genre_ids` is still an array of int.

### TV Details

```
GET /3/tv/{series_id}
```

**Parameters**:

| Param                    | In    | Type   | Required | Description               |
| ------------------------ | ----- | ------ | -------- | ------------------------- |
| `series_id`              | Path  | int    | **Yes**  | TMDB series ID            |
| `language`               | Query | string | No       | Default: `en-US`          |
| `append_to_response`     | Query | string | No       | Sub-resources (max 20)    |
| `include_image_language` | Query | string | No       | Comma-separated ISO codes |

**Response**:

```json
{
  "id": 94997,
  "name": "House of the Dragon",
  "original_name": "House of the Dragon",
  "original_language": "en",
  "overview": "Synopsis...",
  "tagline": "...",
  "status": "Returning Series",
  "type": "Scripted",
  "in_production": true,
  "first_air_date": "2022-08-21",
  "last_air_date": "2024-08-04",
  "number_of_seasons": 2,
  "number_of_episodes": 18,
  "episode_run_time": [],
  "popularity": 789.12,
  "vote_average": 8.4,
  "vote_count": 4567,
  "adult": false,
  "homepage": "https://...",
  "poster_path": "/abc.jpg",
  "backdrop_path": "/def.jpg",
  "origin_country": ["US"],
  "languages": ["en"],

  "genres": [
    { "id": 10765, "name": "Sci-Fi & Fantasy" },
    { "id": 18, "name": "Drama" }
  ],

  "created_by": [
    {
      "id": 237053,
      "name": "Ryan Condal",
      "gender": 2,
      "profile_path": "/abc.jpg",
      "credit_id": "..."
    }
  ],

  "networks": [
    {
      "id": 49,
      "name": "HBO",
      "logo_path": "/tuomPhY2UtuPTqqFnKMVHo0WBfo.png",
      "origin_country": "US"
    }
  ],

  "production_companies": [
    /* ... */
  ],
  "production_countries": [
    /* ... */
  ],
  "spoken_languages": [
    /* ... */
  ],

  "seasons": [
    {
      "id": 134965,
      "name": "Season 1",
      "overview": "...",
      "air_date": "2022-08-21",
      "season_number": 1,
      "episode_count": 10,
      "poster_path": "/abc.jpg",
      "vote_average": 8.2
    },
    {
      "id": 368923,
      "name": "Season 2",
      "season_number": 2,
      "episode_count": 8,
      "poster_path": "/def.jpg"
    }
  ],

  "last_episode_to_air": {
    "id": 5261092,
    "name": "The Queen Who Ever Was",
    "air_date": "2024-08-04",
    "episode_number": 8,
    "season_number": 2,
    "episode_type": "finale",
    "runtime": 72,
    "still_path": "/abc.jpg",
    "vote_average": 7.3,
    "vote_count": 89
  },

  "next_episode_to_air": null
}
```

**`status` values**: `Returning Series`, `Ended`, `Canceled`, `In Production`, `Planned`.

**`type` values**: `Scripted`, `Reality`, `Documentary`, `Miniseries`, `News`, `Talk Show`.

**Key fields for the pipeline**: `id`, `name`, `original_name`, `overview`,
`first_air_date`, `number_of_seasons`, `genres`, `seasons[]` (to iterate),
`status`, `created_by`, `poster_path`, `backdrop_path`.

> **⚠️ `episode_run_time` is empty/unreliable** for recent shows. For runtime, use
> the per-episode `runtime` field in the season details (`/tv/{id}/season/{n}`).
> The provider derives `MediaDetails.runtime_minutes` from
> `max(episode_run_time)` when the array is non-empty, otherwise `None`.

### TV Aggregate Credits

```
GET /3/tv/{series_id}/aggregate_credits
```

**Parameters**:

| Param       | Type   | Required | Description      |
| ----------- | ------ | -------- | ---------------- |
| `series_id` | int    | **Yes**  | TMDB ID          |
| `language`  | string | No       | Default: `en-US` |

**Response**:

```json
{
  "id": 94997,
  "cast": [
    {
      "id": 123,
      "name": "Matt Smith",
      "original_name": "Matt Smith",
      "order": 0,
      "total_episode_count": 18,
      "popularity": 45.6,
      "profile_path": "/abc.jpg",
      "gender": 2,
      "known_for_department": "Acting",
      "adult": false,
      "roles": [
        {
          "credit_id": "...",
          "character": "Daemon Targaryen",
          "episode_count": 18
        }
      ]
    }
  ],
  "crew": [
    {
      "id": 456,
      "name": "Ryan Condal",
      "department": "Production",
      "total_episode_count": 18,
      "jobs": [
        {
          "credit_id": "...",
          "job": "Executive Producer",
          "episode_count": 18
        }
      ]
    }
  ]
}
```

> **Difference vs `/credits`**: aggregate credits use `roles[]` (cast) and
> `jobs[]` (crew), which group multiple appearances into a single person entry
> with per-role/per-job `episode_count`. Plain `/credits` duplicates the entries
> per episode and exposes flat `character`/`job` fields instead. Use
> `aggregate_credits` for TV shows so the same actor playing the same role across
> 18 episodes appears once.

### TV Images

```
GET /3/tv/{series_id}/images
```

**Parameters**:

| Param                    | Type   | Required | Description                          |
| ------------------------ | ------ | -------- | ------------------------------------ |
| `series_id`              | int    | **Yes**  | TMDB ID                              |
| `language`               | string | No       | Filters by language (⚠️ restrictive) |
| `include_image_language` | string | No       | Languages to include: `fr,en,null`   |

**Response**: same `{ backdrops, logos, posters }` shape as
[Movie Images](#movie-images). The same `include_image_language` gotcha applies.

### TV External IDs

```
GET /3/tv/{series_id}/external_ids
```

**Response**:

```json
{
  "id": 94997,
  "imdb_id": "tt11198330",
  "tvdb_id": 371572,
  "tvrage_id": null,
  "freebase_mid": null,
  "freebase_id": null,
  "wikidata_id": "Q104108270",
  "facebook_id": "HouseoftheDragon",
  "instagram_id": "houseofthedragonhbo",
  "twitter_id": "HouseofDragon"
}
```

> **Note**: `tvdb_id` is an **integer** (not a string), whereas `imdb_id` is a
> string with a `tt` prefix. The provider only folds **string-valued** external
> IDs into `MediaDetails.external_ids` (the integer `tvdb_id` is therefore not
> carried into that dict from TV details directly — cross-provider TVDB linkage
> flows through `scraper._xref`, see the external-ids-flow reference).

### TV Videos

```
GET /3/tv/{series_id}/videos
```

Same structure as movie videos. Filter by `language`.

### TV Keywords

```
GET /3/tv/{series_id}/keywords
```

**Response**: `{ "id": int, "results": [{ "id": int, "name": str }] }`.

> **⚠️ WARNING**: TV keywords use the envelope `results`, NOT `keywords`
> (different from movies!). This is a known inconsistency in TMDB's API. The
> provider's `parse_keywords` branches on `media_type` to read the correct key.

---

## Endpoints — Seasons

### Season Details

```
GET /3/tv/{series_id}/season/{season_number}
```

**Parameters**:

| Param                    | In    | Type   | Required | Description                  |
| ------------------------ | ----- | ------ | -------- | ---------------------------- |
| `series_id`              | Path  | int    | **Yes**  | TMDB series ID               |
| `season_number`          | Path  | int    | **Yes**  | Season number (0 = specials) |
| `language`               | Query | string | No       | Default: `en-US`             |
| `append_to_response`     | Query | string | No       | Sub-resources (max 20)       |
| `include_image_language` | Query | string | No       | Comma-separated ISO codes    |

**Response**:

```json
{
  "id": 134965,
  "_id": "62e...",
  "name": "Season 1",
  "overview": "Season synopsis...",
  "air_date": "2022-08-21",
  "season_number": 1,
  "poster_path": "/abc.jpg",
  "vote_average": 8.2,

  "episodes": [
    {
      "id": 1971015,
      "name": "The Heirs of the Dragon",
      "overview": "Episode synopsis...",
      "air_date": "2022-08-21",
      "episode_number": 1,
      "season_number": 1,
      "episode_type": "standard",
      "runtime": 66,
      "still_path": "/abc.jpg",
      "production_code": "",
      "show_id": 94997,
      "vote_average": 7.8,
      "vote_count": 156,

      "crew": [
        {
          "id": 123,
          "name": "Miguel Sapochnik",
          "department": "Directing",
          "job": "Director",
          "profile_path": "/abc.jpg"
        }
      ],

      "guest_stars": [
        {
          "id": 456,
          "name": "Actor Name",
          "character": "Character Name",
          "order": 0,
          "profile_path": "/def.jpg"
        }
      ]
    }
  ]
}
```

**⚠️ Key endpoint**: a single call per season returns **all episodes** with their
crew and guest stars. This is the most efficient method — one call per season
rather than one per episode. The provider's `get_tv_season` uses
`append_to_response=images` (adds `images: { posters: [...] }`).

**Particularity**: Season 0 = specials. `air_date` and `runtime` may be null for
unaired episodes. Season responses carry a MongoDB `_id` (string ObjectID)
unique to this endpoint.

### Season Images

```
GET /3/tv/{series_id}/season/{season_number}/images
```

**Response**:

```json
{
  "id": 134965,
  "posters": [
    /* ImageObject[] — posters only */
  ]
}
```

> Season images return only `posters` (no backdrops or logos).

### Season Videos

```
GET /3/tv/{series_id}/season/{season_number}/videos
```

**Parameters**:

| Param      | Type   | Required | Description         |
| ---------- | ------ | -------- | ------------------- |
| `language` | string | No       | Filter by ISO 639-1 |

Same structure as movie videos. Returns empty `results` for many older shows.
The provider exposes this via `fetch_tv_season_videos`.

---

## Endpoints — Episodes

### Episode Details

```
GET /3/tv/{series_id}/season/{season_number}/episode/{episode_number}
```

**Parameters**:

| Param                | In    | Type   | Required | Description            |
| -------------------- | ----- | ------ | -------- | ---------------------- |
| `series_id`          | Path  | int    | **Yes**  | TMDB series ID         |
| `season_number`      | Path  | int    | **Yes**  | Season number          |
| `episode_number`     | Path  | int    | **Yes**  | Episode number         |
| `language`           | Query | string | No       | Default: `en-US`       |
| `append_to_response` | Query | string | No       | Sub-resources (max 20) |

**Response**: same structure as an episode in the season response (see above).

> **Usage**: generally unnecessary if you already use the season endpoint. Useful
> only to fetch the details of one specific episode — including its
> `external_ids` sub-object (which the season-level fetch does NOT return). The
> provider's `parse_episode` reads `external_ids` (imdb_id, tvdb_id) when present.

### Episode Images

```
GET /3/tv/{series_id}/season/{season_number}/episode/{episode_number}/images
```

**Response**:

```json
{
  "id": 1971015,
  "stills": [
    /* ImageObject[] — stills only (landscape thumbnails) */
  ]
}
```

> Episode images return only `stills` (no posters or logos).

---

## Endpoints — Utilities

### Configuration

```
GET /3/configuration
```

Returns the base URLs for images and the available sizes. **Cache it** and
refresh every few days.

**Response**:

```json
{
  "images": {
    "base_url": "http://image.tmdb.org/t/p/",
    "secure_base_url": "https://image.tmdb.org/t/p/",
    "backdrop_sizes": ["w300", "w780", "w1280", "original"],
    "logo_sizes": ["w45", "w92", "w154", "w185", "w300", "w500", "original"],
    "poster_sizes": ["w92", "w154", "w185", "w342", "w500", "w780", "original"],
    "profile_sizes": ["w45", "w185", "h632", "original"],
    "still_sizes": ["w92", "w185", "w300", "original"]
  },
  "change_keys": [
    /* list of keys modifiable via /changes */
  ]
}
```

### Find by External ID

```
GET /3/find/{external_id}?external_source={source}
```

Finds TMDB content from an external ID (IMDb, TVDB, etc.).

| Param             | In    | Type   | Required | Description                        |
| ----------------- | ----- | ------ | -------- | ---------------------------------- |
| `external_id`     | Path  | string | **Yes**  | The external ID (e.g. `tt0137523`) |
| `external_source` | Query | string | **Yes**  | The ID source                      |
| `language`        | Query | string | No       | Default: `en-US`                   |

**Supported sources**: `imdb_id`, `tvdb_id`, `facebook_id`, `instagram_id`,
`tiktok_id`, `twitter_id`, `wikidata_id`, `youtube_id`.

**Response**:

```json
{
  "movie_results": [
    /* MovieObject[] */
  ],
  "tv_results": [
    /* TVObject[] */
  ],
  "person_results": [
    /* PersonObject[] */
  ],
  "tv_episode_results": [
    /* EpisodeObject[] */
  ],
  "tv_season_results": []
}
```

Only one array is non-empty depending on what the external ID references. The
response **always** contains all five arrays (even when empty).

> **Pipeline usage**: essential to cross-reference IMDb ↔ TMDB and TVDB ↔ TMDB in
> a single call.

### Search Multi

```
GET /3/search/multi
```

Unified search (movies + TV + people) in a single request.

| Param           | Type    | Required | Default | Description           |
| --------------- | ------- | -------- | ------- | --------------------- |
| `query`         | string  | **Yes**  | —       | Search term           |
| `language`      | string  | No       | `en-US` | Result language       |
| `page`          | int     | No       | `1`     | Page (1–500)          |
| `include_adult` | boolean | No       | `false` | Include adult content |

**Response**: paginated, with a `media_type` discriminator on every result:

- `"movie"` → standard movie fields.
- `"tv"` → standard TV fields.
- `"person"` → person fields + `known_for[]` (array of movies/shows).

> **⚠️ Always check `media_type`** to parse each result correctly — the field
> set differs per type.

### Genres (Movies)

```
GET /3/genre/movie/list?language=fr-FR
```

**~19 movie genres**:

| ID    | Name (fr)       |
| ----- | --------------- |
| 28    | Action          |
| 12    | Aventure        |
| 16    | Animation       |
| 35    | Comédie         |
| 80    | Crime           |
| 99    | Documentaire    |
| 18    | Drame           |
| 10751 | Familial        |
| 14    | Fantastique     |
| 36    | Histoire        |
| 27    | Horreur         |
| 10402 | Musique         |
| 9648  | Mystère         |
| 10749 | Romance         |
| 878   | Science-Fiction |
| 10770 | Téléfilm        |
| 53    | Thriller        |
| 10752 | Guerre          |
| 37    | Western         |

### Genres (TV)

```
GET /3/genre/tv/list?language=fr-FR
```

**~16 TV genres**:

| ID    | Name (fr)                 |
| ----- | ------------------------- |
| 10759 | Action & Adventure        |
| 16    | Animation                 |
| 35    | Comédie                   |
| 80    | Crime                     |
| 99    | Documentaire              |
| 18    | Drame                     |
| 10751 | Familial                  |
| 10762 | Kids                      |
| 9648  | Mystère                   |
| 10763 | News                      |
| 10764 | Reality                   |
| 10765 | Science-Fiction & Fantasy |
| 10766 | Soap                      |
| 10767 | Talk                      |
| 10768 | War & Politics            |
| 37    | Western                   |

> **⚠️ Genre IDs differ between movies and TV** for similar concepts (e.g. Action
> movie = `28`, Action TV = `10759`). Some IDs are shared (16, 35, 80, 99, 18,
> 10751, 9648, 37). The movie list has ~19 genres; the TV list has ~16. Resolve
> against the correct list for the media type.

### Certifications

```
GET /3/certification/movie/list
GET /3/certification/tv/list
```

**FR certifications (movies)**: `NR` (0), `TP` (1), `12` (2), `16` (3), `18` (4).

**FR certifications (TV)**: `NR`, `TP`, `10`, `12`, `16`, `18`.

The `order` field indicates severity (0 = unrated, higher = more restrictive).

---

## Certifications FR — Extraction

For **movies**, the certification lives inside `release_dates` (not a direct field):

```
GET /3/movie/{id}?append_to_response=release_dates
```

Extract the French certification:

```python
for entry in data["release_dates"]["results"]:
    if entry["iso_3166_1"] == "FR":
        for rd in entry["release_dates"]:
            if rd["type"] == 3 and rd["certification"]:  # 3 = theatrical
                return rd["certification"]  # e.g. "TP", "12", "16", "18"
```

**Release types** (`type`): 1=Premiere, 2=Theatrical (limited), 3=Theatrical,
4=Digital, 5=Physical, 6=TV.

> Only the theatrical release (type 3) usually carries the certification.
> Physical/TV releases often have an empty certification.

For **TV shows**, use `content_ratings`:

```
GET /3/tv/{id}?append_to_response=content_ratings
```

```python
for entry in data["content_ratings"]["results"]:
    if entry["iso_3166_1"] == "FR":
        return entry["rating"]  # e.g. "12", "16"
```

Simpler structure than movies (no nesting by release type).

---

## Optimal Call Strategy

### For a movie (1–2 calls)

```
1. GET /3/search/movie?query={title}&year={year}&language=fr-FR
   → Get the TMDB ID

2. GET /3/movie/{id}?language=fr-FR
     &append_to_response=credits,images,external_ids,release_dates
     &include_image_language=fr,en,null
   → Details + cast + images + IMDb IDs + classification
```

**Total: 2 calls** for all movie metadata.

> The pipeline's `TMDBClient.get_movie` uses
> `append_to_response=videos,images,keywords,external_ids` (videos + keywords
> instead of credits/release_dates) — adjust the appended sub-resources to what
> your consumer needs; the 2-call pattern holds either way.

### For a TV show (2 + N calls, N = number of seasons)

```
1. GET /3/search/tv?query={title}&first_air_date_year={year}&language=fr-FR
   → Get the TMDB ID

2. GET /3/tv/{id}?language=fr-FR
     &append_to_response=aggregate_credits,images,external_ids,content_ratings
     &include_image_language=fr,en,null
   → Details + cast + images + IMDb/TVDB IDs + classification

3. For each season:
   GET /3/tv/{id}/season/{n}?language=fr-FR&append_to_response=images
   → Episode list (titles, dates, crew) + season posters
```

**Total: 2 + N calls** (N = number of seasons) for all TV metadata.

### Concrete example: a show with 5 seasons

| Step | Call                                            | Data retrieved                |
| ---- | ----------------------------------------------- | ----------------------------- |
| 1    | `search/tv?query=...`                           | TMDB ID                       |
| 2    | `tv/{id}?append_to_response=...`                | Details + cast + images + IDs |
| 3–7  | `tv/{id}/season/1..5?append_to_response=images` | Episodes + season posters     |

**7 calls total** instead of potentially 50+ without `append_to_response`.

### Selecting the best image

Prioritize by language for relevance:

1. `fr` (or configured language) — localized image.
2. `en` — English fallback.
3. `null` — language-less image (no text).
4. Other languages.

Within the same language, sort by `vote_average` descending.

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
  },
  "external_ids": {
    "imdb_id": "tt0137523",
    "wikidata_id": "Q190050"
  }
}
```

### Movie Object (search/discover)

| Field               | Type        | Description           |
| ------------------- | ----------- | --------------------- |
| `id`                | int         | TMDB ID               |
| `title`             | string      | Localized title       |
| `original_title`    | string      | Original title        |
| `original_language` | string      | ISO 639-1             |
| `overview`          | string      | Localized synopsis    |
| `release_date`      | string      | YYYY-MM-DD            |
| `poster_path`       | string/null | Poster path           |
| `backdrop_path`     | string/null | Backdrop path         |
| `genre_ids`         | int[]       | Genre IDs             |
| `popularity`        | float       | Popularity score      |
| `vote_average`      | float       | Average rating (0–10) |
| `vote_count`        | int         | Vote count            |
| `adult`             | bool        | Adult content         |
| `video`             | bool        | Has video content     |

### TV Object (search)

| Field               | Type        | Description           |
| ------------------- | ----------- | --------------------- |
| `id`                | int         | TMDB ID               |
| `name`              | string      | Localized title       |
| `original_name`     | string      | Original title        |
| `original_language` | string      | ISO 639-1             |
| `overview`          | string      | Localized synopsis    |
| `first_air_date`    | string      | YYYY-MM-DD            |
| `poster_path`       | string/null | Poster path           |
| `backdrop_path`     | string/null | Backdrop path         |
| `genre_ids`         | int[]       | Genre IDs             |
| `origin_country`    | string[]    | ISO 3166-1            |
| `popularity`        | float       | Popularity score      |
| `vote_average`      | float       | Average rating (0–10) |
| `vote_count`        | int         | Vote count            |
| `adult`             | bool        | Adult content         |

### Image Object

| Field          | Type        | Description                        |
| -------------- | ----------- | ---------------------------------- |
| `file_path`    | string      | Relative path (append to base URL) |
| `aspect_ratio` | float       | Width/height ratio                 |
| `width`        | int         | Width in pixels                    |
| `height`       | int         | Height in pixels                   |
| `iso_639_1`    | string/null | Language (null = language-less)    |
| `iso_3166_1`   | string/null | Country code (real responses only) |
| `vote_average` | float       | Community rating                   |
| `vote_count`   | int         | Vote count                         |

### Cast Object (movie credits)

| Field                  | Type        | Description               |
| ---------------------- | ----------- | ------------------------- |
| `id`                   | int         | Person ID                 |
| `name`                 | string      | Name                      |
| `original_name`        | string      | Original name             |
| `character`            | string      | Character played          |
| `order`                | int         | Billing order (0 = first) |
| `profile_path`         | string/null | Profile photo             |
| `gender`               | int         | 0=?, 1=F, 2=M, 3=NB       |
| `known_for_department` | string      | Primary department        |
| `popularity`           | float       | Popularity score          |

### Crew Object (movie credits)

| Field          | Type        | Description                   |
| -------------- | ----------- | ----------------------------- |
| `id`           | int         | Person ID                     |
| `name`         | string      | Name                          |
| `department`   | string      | Department (e.g. "Directing") |
| `job`          | string      | Job (e.g. "Director")         |
| `profile_path` | string/null | Profile photo                 |

### Episode Object (in season response)

| Field            | Type        | Description                        |
| ---------------- | ----------- | ---------------------------------- |
| `id`             | int         | TMDB episode ID                    |
| `name`           | string      | Localized title                    |
| `overview`       | string      | Localized synopsis                 |
| `air_date`       | string      | YYYY-MM-DD                         |
| `episode_number` | int         | Episode number                     |
| `season_number`  | int         | Season number                      |
| `episode_type`   | string      | `standard`, `finale`, `mid_season` |
| `runtime`        | int         | Runtime in minutes                 |
| `still_path`     | string/null | Landscape thumbnail                |
| `vote_average`   | float       | Average rating                     |
| `vote_count`     | int         | Vote count                         |
| `crew`           | array       | Episode-specific crew              |
| `guest_stars`    | array       | Episode guest stars                |

---

## Provider Implementation Notes

### What TMDBClient implements

| Method                                        | Endpoint                                      | Returns              |
| --------------------------------------------- | --------------------------------------------- | -------------------- |
| `search()` / `search_movie()` / `search_tv()` | `/search/movie` or `/search/tv`               | `list[SearchResult]` |
| `get_details()` / `get_movie()` / `get_tv()`  | `/movie/{id}` or `/tv/{id}`                   | `MediaDetails`       |
| `get_artwork_urls()`                          | `/{type}/{id}/images`                         | `list[ArtworkItem]`  |
| `get_keywords()`                              | `/movie/{id}/keywords` or `/tv/{id}/keywords` | `list[str]`          |
| `get_videos()`                                | `/{type}/{id}/videos`                         | `list[Video]`        |
| `get_tv_season()` / `get_season()`            | `/tv/{id}/season/{n}`                         | `SeasonDetails`      |
| `get_episodes()`                              | `/tv/{id}/season/{n}` (episodes unwrapped)    | `list[EpisodeInfo]`  |
| `fetch_tv_season_videos()`                    | `/tv/{id}/season/{n}/videos`                  | `list[Video]`        |

`TMDBClient` composes the atomic capability protocols (`Searchable`,
`MovieDetailsProvider`, `TvDetailsProvider`, `EpisodeFetcher`, `ArtworkProvider`,
`KeywordProvider`, `VideoProvider`) from `api/metadata/_contracts.py`. It does
_not_ compose `IDValidator` (cross-provider ID validation flows through
`scraper._xref`) nor `RecommendationProvider` (no recommendations endpoint
wired in).

### TransportPolicy

Built by `TMDBClient.policy(api_key, circuit=...)`:

```python
TransportPolicy(
    provider_name=ProviderName.TMDB,
    base_url="https://api.themoviedb.org/3",
    auth=BearerAuth(api_key),
    timeout_seconds=10.0,
    retry=RetryPolicy(max_attempts=4),
    circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
    rate_limit=RateLimitPolicy(requests_per_second=40.0),
)
```

`RetryPolicy.retryable_statuses` includes `{429, 500, 502, 503, 504}`.

### Image URL building

```python
IMAGE_BASE = "https://image.tmdb.org/t/p/"

def _build_image_url(path: str | None, size: str) -> str:
    if not path:
        return ""
    return f"{IMAGE_BASE}{size}{path}"
```

### Rate Limit Handling

TMDB's ~40 req/s ceiling is approximate. The provider uses
`RateLimitPolicy(requests_per_second=40.0)` as a soft cap via the token-bucket
`RateLimiter`. Combined with `RetryPolicy` (retries on 429), the transport
handles throttling transparently.

TMDB error code 25 maps to HTTP 429 → `retryable_statuses` includes 429 →
tenacity retries with exponential backoff.

Circuit breaker opens after 5 consecutive failures (HTTP 5xx or connection
errors) and stays open for 5 minutes (`cooldown_seconds=300.0`).

### Fail-soft video fetch

`_fetch_videos` (used by `get_videos` / `fetch_tv_season_videos`) is best-effort:
any transport, circuit, parser, or unexpected error is logged at WARNING level on
the `api.tmdb` channel and converted to an empty list, so callers cannot
distinguish "TMDB down" from "no videos" without consulting the log.
`_fetch_videos_strict` propagates errors for callers that need them.

---

## Particularities

### 1. `release_date` may be empty string

For unreleased or upcoming movies, `release_date` is `""` (not null). Parse
defensively for `year`:

```python
year = int(d["release_date"][:4]) if d.get("release_date") else None
```

**Decision**: Handle — parse defensively, return `None` if empty. (Implemented in
`parse_search_result` / `parse_media_details`.)

### 2. `genre_ids` (int) vs `genres` (object)

Search returns `genre_ids: [18, 53]` (int array). Details returns
`genres: [{id: 18, name: "Drama"}]` (object array). The provider stores genre
names AND IDs in parallel (`MediaDetails.genres` + `MediaDetails.genre_ids`)
because classifier rules consume the IDs.

### 3. TV keywords envelope inconsistency

`/movie/{id}/keywords` returns `{"keywords": [...]}` while
`/tv/{id}/keywords` returns `{"results": [...]}`. `parse_keywords` branches on
`media_type` to read the correct key.

### 4. `episode_run_time` is an array

TV details returns `episode_run_time: [25, 30]` (array of ints), often empty for
recent shows. `parse_media_details` uses `max(episode_run_time)` when non-empty,
otherwise `None`. For reliable per-episode runtime, read the season details.

### 5. `runtime` can be null

Both movie and episode `runtime` fields may be `None`/null.
`MediaDetails.runtime_minutes` and `EpisodeInfo.runtime_minutes` are `int | None`.

### 6. Pagination ceiling (500 pages)

`total_pages` is capped at 500. Searches with >10,000 results cannot be fully
paginated. `_search_paginated` respects `max_pages` (default 5 = 100 results) to
avoid runaway pagination.

### 7. `append_to_response` sub-requests don't count toward rate limits

Fetching details with `append_to_response=videos,images,keywords,external_ids`
counts as 1 request, not 4. The provider always uses `append_to_response` when
fetching details.

### 8. Image language filtering

`include_image_language=fr,en,null` controls which language images are returned.
`null` includes images without language (backdrops, logos). Order matters: first
match wins. The provider builds
`include_image_language={language},{fallback_language},en,null`.

### 9. Season 0 = specials

TV shows have a season 0 containing specials, behind-the-scenes, etc.

### 10. `videos.results[].official` boolean

TMDB returns both official trailers and fan-uploaded content. `Video.official`
exposes the flag; the caller decides whether to filter.

### 11. TV `external_ids.tvdb_id` is an integer

Unlike `imdb_id` (string with `tt` prefix), `tvdb_id` is an integer. The provider
only folds string-valued external IDs from TV details into
`MediaDetails.external_ids`; TVDB cross-linkage flows through `scraper._xref`.

### 12. MongoDB `_id` in season responses

Season responses carry a `_id` (string ObjectID) field unique to the season
endpoint, absent from all other endpoints.

---

## Verified Edge Cases

Live tests against the real API (originally captured 2026-04-10; field shapes
re-confirmed against golden samples on 2026-05-04):

| #   | Behavior                               | Detail                                                                                                        |
| --- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 1   | `year` is not a strict filter          | Boosts relevance but returns results from other years. Filter client-side.                                    |
| 2   | Empty search = HTTP 200                | `{"results": [], "total_results": 0}` — not a 404. Check `len(results)`.                                      |
| 3   | Apostrophes/accents in the query       | Work with standard URL encoding (`%27`, `%C3%A9`).                                                            |
| 4   | `episode_run_time` is empty/deprecated | Empty array `[]` for recent shows. Use per-episode `runtime` in season details.                               |
| 5   | Image gotcha: 5× to 31× fewer          | Without `include_image_language`, backdrops are severely reduced (null = no text = excluded).                 |
| 6   | TV genres partially untranslated       | With `language=fr-FR`: "Kids", "News", "Reality", "Soap", "Talk", "War & Politics" stay in English.           |
| 7   | `Find` always returns 5 arrays         | `movie_results`, `tv_results`, `person_results`, `tv_episode_results`, `tv_season_results` — even when empty. |
| 8   | TV aggregate credits ≠ movie credits   | TV `aggregate_credits` uses `roles[]`/`jobs[]` (grouped multi-roles). Movie `credits` has flat fields.        |
| 9   | Movie vs TV certifications             | Movie: nested in `release_dates` → filter by `type==3`. TV: flat in `content_ratings`.                        |
| 10  | MongoDB `_id` in season response       | `_id` (string ObjectID) field unique to season responses, absent from other endpoints.                        |
| 11  | `Search multi`: `media_type` required  | Mixed results — always check `media_type` to parse correctly (different field sets).                          |
| 12  | `runtime` reliable per episode only    | The `runtime` in `/tv/{id}/season/{n}` → `episodes[]` is reliable (e.g. 41 min for Mandalorian S01E01).       |

---

## Daily ID Exports

TMDB provides daily exports of all IDs (no auth required):

```
https://files.tmdb.org/p/exports/movie_ids_MM_DD_YYYY.json.gz
https://files.tmdb.org/p/exports/tv_series_ids_MM_DD_YYYY.json.gz
https://files.tmdb.org/p/exports/person_ids_MM_DD_YYYY.json.gz
```

- Format: gzipped, line-delimited JSON (one JSON object per line, NOT an array).
- Fields: `id`, `original_title`/`original_name`, `popularity`, `adult`, `video`.
- Updated daily ~07:00 UTC, available ~08:00 UTC.
- Retained 3 months, then deleted.

---

## Golden Test Samples

Sample responses are captured in `docs/reference/_samples/tmdb/` for golden tests
in `_tmdb_parsers.py`:

- `search_movie.json` — `GET /3/search/movie?query=Fight+Club`
- `search_movie_en.json` — `GET /3/search/movie?query=Fight+Club&language=en-US`
- `search_movie_empty.json` — empty-result search (HTTP 200, `results: []`)
- `search_tv.json` — `GET /3/search/tv?query=Breaking+Bad`
- `movie_details.json` — `GET /3/movie/550?append_to_response=videos,images,keywords,external_ids`
- `movie_details_minimal.json` — minimal movie details (null/optional fields)
- `tv_details.json` — `GET /3/tv/1396?append_to_response=videos,images,keywords,external_ids`
- `season_details.json` — `GET /3/tv/1396/season/1`
- `movie_videos.json` — `GET /3/movie/550/videos`
- `tv_videos.json` — `GET /3/tv/1396/videos`
- `season_videos.json` — `GET /3/tv/1396/season/1/videos`
- `movie_keywords.json` — `GET /3/movie/550/keywords`
- `tv_keywords.json` — `GET /3/tv/1396/keywords`

Samples are captured via live API calls (requires `TMDB_API_KEY` in `.env`). Field
shapes are pinned by these samples per `_tmdb_parsers.py`.
</content>
</invoke>
