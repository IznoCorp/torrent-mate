# TVDB API v4 — Reference

> TheTVDB API v4 — canonical reference for the `personalscraper/api/metadata/tvdb.py` provider (scrape step).
> Swagger UI: https://thetvdb.github.io/v4-api/
> Swagger spec: https://thetvdb.github.io/v4-api/swagger.yml
> GitHub: https://github.com/thetvdb/v4-api
> API version: 4.7.10 — TLS minimum: v1.2
> Last updated: 2026-06-01

---

## Table of Contents

- [Authentication](#authentication)
- [Base URLs](#base-urls)
- [Response Format](#response-format)
- [Error Format](#error-format)
- [Error Codes & Retry Strategy](#error-codes--retry-strategy)
- [Rate Limiting](#rate-limiting)
- [Language & Translations](#language--translations)
- [Images & Artwork](#images--artwork)
- [Artwork Types Catalogue](#artwork-types-catalogue)
- [Source / ID Types](#source--id-types)
- [Pagination](#pagination)
- [Season Types](#season-types)
- [Endpoints — Auth](#endpoints--auth)
- [Endpoints — Search](#endpoints--search)
- [Endpoints — Series](#endpoints--series)
- [Endpoints — Seasons](#endpoints--seasons)
- [Endpoints — Episodes](#endpoints--episodes)
- [Endpoints — Movies](#endpoints--movies)
- [Endpoints — People & Castmembers](#endpoints--people--castmembers)
- [Endpoints — Companies](#endpoints--companies)
- [Endpoints — Awards](#endpoints--awards)
- [Endpoints — Artwork](#endpoints--artwork)
- [Endpoints — Reference Data](#endpoints--reference-data)
- [Endpoints — Updates](#endpoints--updates)
- [Cross-Provider IDs (IMDB, TMDB)](#cross-provider-ids-imdb-tmdb)
- [Caching Strategy](#caching-strategy)
- [Optimal Call Strategy](#optimal-call-strategy)
- [Response Schemas](#response-schemas)
- [Provider Implementation Notes](#provider-implementation-notes)
- [Particularities](#particularities)
- [Edge Cases (live verification)](#edge-cases-live-verification)
- [Endpoint Inventory (appendix)](#endpoint-inventory-appendix)
- [Golden Test Samples](#golden-test-samples)

---

## Authentication

### Login Flow

TVDB v4 uses **JWT Bearer token** authentication. Unlike TMDB (direct API key in a
query parameter), TVDB requires a one-time login to obtain a token.

```
POST /login
```

**Request body**:

```json
{ "apikey": "<TVDB_API_KEY>" }
```

| Field    | Type   | Required        | Description                                                                |
| -------- | ------ | --------------- | -------------------------------------------------------------------------- |
| `apikey` | string | **Yes**         | TVDB API key                                                               |
| `pin`    | string | Depends on type | Required for "User Subscription" keys; omit for "Negotiated Contract" keys |

> **Two API key types**:
>
> - **Negotiated Contract** (free, < $50k revenue): send `{"apikey": "..."}` **without the `pin` field**. The pipeline's current key is this type.
> - **User Subscription**: each user subscribes ($11.99/year) and supplies their PIN → `{"apikey": "...", "pin": "..."}`. The PIN is found under Dashboard → Account → Subscription.
>
> If the API returns `"pin required"`, the key is a User Subscription key.

**Success response**:

```json
{
  "status": "success",
  "data": { "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." }
}
```

**Token TTL**: 30 days (confirmed from a real login — the `exp` claim decoded 2026-05-04 → 2026-06-04). **No runtime refresh needed.** There is no `refresh_token` endpoint. The pipeline process never runs for 30 days, so re-login at client init is sufficient. Re-authenticate via `POST /login` when the token expires (HTTP 401).

**Login error responses** (verified):

```json
// Missing PIN → HTTP 400
{"status": "failure", "message": "InvalidValueType: pin required", "data": null}

// Invalid PIN → HTTP 401
{"status": "failure", "message": "InvalidAPIKey: pin invalid", "data": null}

// Invalid API key → HTTP 401
{"status": "failure", "message": "InvalidAPIKey: apikey invalid", "data": null}
```

### Using the Token

```
Authorization: Bearer <token>
```

All subsequent requests include this header. If the token expires, the server returns
HTTP 401 — the client re-authenticates via `/login`.

### Credential in the Pipeline

```
.env → TVDB_API_KEY=<your_api_key>
```

`PROVIDER_CREDS["tvdb"] = ["TVDB_API_KEY"]` in `personalscraper/api/_activation.py`,
mirrored by `TVDBClient.REQUIRED_CREDS = ["TVDB_API_KEY"]`.

### API Plans

| Parent company revenue | Cost         | Key type            | PIN required |
| ---------------------- | ------------ | ------------------- | ------------ |
| < $50k/year            | **Free**     | User Subscription   | Yes          |
| $50k - $250k/year      | $1,000/year  | Negotiated Contract | No           |
| $250k - $1M/year       | $10,000/year | Negotiated Contract | No           |
| > $1M/year             | Quote        | Negotiated Contract | No           |

> **Attribution required**: unless specifically exempted, display a link to TheTVDB.com.

---

## Base URLs

| Purpose      | URL                                                      |
| ------------ | -------------------------------------------------------- |
| API v4       | `https://api4.thetvdb.com/v4`                            |
| Swagger UI   | `https://thetvdb.github.io/v4-api/`                      |
| Swagger YAML | `https://thetvdb.github.io/v4-api/swagger.yml`           |
| Image CDN    | `https://artworks.thetvdb.com/` (full URLs in responses) |

`HttpTransport` policy uses `base_url = "https://api4.thetvdb.com/v4"`.

---

## Response Format

### Success

All responses use a standardized envelope:

```json
{
  "status": "success",
  "data": { ... }    // or [...]
}
```

### Success with pagination

```json
{
  "status": "success",
  "data": [ ... ],
  "links": {
    "prev": "https://...",
    "self": "https://...",
    "next": "https://...",
    "total_items": 62,
    "page_size": 100
  }
}
```

**Key difference from TMDB**: TVDB wraps ALL responses in `data`. The provider must
unwrap `response["data"]` before passing to parsers (see `unwrap()` in
`_tvdb_parsers.py`). TMDB returns the raw object directly.

---

## Error Format

```json
{
  "status": "failure",
  "message": "InvalidAPIKey: apikey invalid",
  "data": null
}
```

**Key difference from TMDB**: TVDB uses `"status": "failure"` with a `message` string —
no separate `status_code`/`status_message` fields. The HTTP status code reflects the
error class.

### Two distinct error response shapes

The code must handle **both** shapes — do not rely on `status` being present in every
error response.

**Login errors** (HTTP 400/401 on `/login`) — include `status`, `message`, and `data`:

```json
{
  "status": "failure",
  "message": "InvalidValueType: pin required",
  "data": null
}
```

**General endpoint errors** (HTTP 401/404/405 on other endpoints) — minimal structure:

```json
{ "message": "Unauthorized" }
```

```json
{ "message": "Method Not Allowed" }
```

`ApiError` mapping in the provider:

```python
ApiError(
    provider="tvdb",
    http_status=resp.status_code,
    provider_code=0,           # TVDB has no numeric error codes
    message=data.get("message", resp.reason),
)
```

---

## Error Codes & Retry Strategy

### HTTP codes

| HTTP | Description                             | Pipeline action          |
| ---- | --------------------------------------- | ------------------------ |
| 200  | Success                                 | Parse `data`             |
| 304  | Not modified (with `If-Modified-Since`) | Use the cache            |
| 400  | Bad request / invalid parameters        | Fix the request          |
| 401  | Unauthorized (token invalid/expired)    | Re-login (`POST /login`) |
| 404  | Resource not found                      | Skip, log "not found"    |
| 405  | Method not allowed                      | Check the HTTP method    |
| 429  | Rate limit (inferred)                   | Retry with backoff       |

A 404 returns `{"status": "failure", "message": "NotFoundException: error fetching series", "data": null}` —
the message includes the exception type.

### Retry strategy (exponential backoff)

```
HTTP 401 → automatic re-login (token expired) → retry
HTTP 429 → exponential backoff → retry (max attempts)
HTTP 5xx → exponential backoff → retry (max attempts)
HTTP 400 → do NOT retry (parameter error)
HTTP 404 → do NOT retry (resource does not exist)
```

The provider's `RetryPolicy(max_attempts=4)` drives the backoff for retryable classes
via the shared `HttpTransport` / tenacity wiring (see
[Provider Implementation Notes](#provider-implementation-notes)).

---

## Rate Limiting

TVDB does **not** publish specific rate limits. No explicit thresholds appear in the
Swagger spec or the documentation. The API serves millions of calls per day across all
consumers; if a rate limit exists, HTTP **429** is the standard signal.

**Strategy**:

- Retry on HTTP 429 with exponential backoff (standard tenacity behavior).
- Cache reference data (artwork types, genres, languages) aggressively — see
  [Caching Strategy](#caching-strategy).
- Use `/updates` for bulk sync instead of polling individual records.

`RateLimitPolicy(requests_per_second=20)` — conservative soft cap in the provider policy.

---

## Language & Translations

### 3-character codes

TVDB uses **3-character** language codes (ISO 639-2/3), unlike TMDB's `fr-FR`/`en-US`:

| Language | TVDB  | TMDB    |
| -------- | ----- | ------- |
| French   | `fra` | `fr-FR` |
| English  | `eng` | `en-US` |
| Spanish  | `spa` | `es-ES` |
| German   | `deu` | `de-DE` |
| Japanese | `jpn` | `ja-JP` |
| Italian  | `ita` | `it-IT` |

Country codes are also 3-character (`usa`, `fra`, `jpn`, etc.).

### Language mapping in the pipeline

The pipeline uses 2-char codes internally. `map_language()` in `_tvdb_parsers.py` maps
them to TVDB's 3-char codes; 3-char inputs pass through unchanged; unknown codes fall
back to `"eng"`:

```python
_LANG_MAP = {
    "fr": "fra", "en": "eng", "es": "spa", "de": "deu",
    "it": "ita", "ja": "jpn", "ko": "kor", "pt": "por",
    "ru": "rus", "zh": "zho", "ar": "ara", "nl": "nld",
}
```

`TVDBClient` defaults to `language="fr-FR"` and stores both the original code and its
mapped 3-char form.

### Translation system

Each entity carries two arrays indicating which translations are available:

- `nameTranslations`: language codes that have a translated name.
- `overviewTranslations`: language codes that have a translated overview.

**Two ways to fetch translations:**

1. **Dedicated endpoint**: `GET /{entity}/{id}/translations/{language}` — returns the
   translated name and overview for one specific language.
2. **`meta` parameter**: `GET /{entity}/{id}/extended?meta=translations` — includes all
   translations in the extended response.

### Translation object

```json
{
  "language": "fra",
  "name": "Translated title",
  "overview": "Translated overview...",
  "aliases": ["Alias 1"],
  "isAlias": false,
  "isPrimary": false,
  "tagline": "Tagline (movies only)"
}
```

### Language parameter

Search supports `language=eng` to filter results by original language (3-char code):

```
GET /search?query=Breaking+Bad&type=series&language=fra
```

---

## Images & Artwork

### Image URLs

TVDB returns **full URLs** in responses (the `image` field). No base URL + size assembly
is needed (unlike TMDB).

```
https://artworks.thetvdb.com/banners/posters/81189-10.jpg
```

### Artwork arrays

Entities (series, movies, seasons, episodes) include an `artworks` array directly in
extended responses:

```json
{
  "artworks": [
    { "id": 123, "type": 2, "image": "https://artworks.thetvdb.com/..." },
    { "id": 124, "type": 3, "image": "https://artworks.thetvdb.com/..." }
  ]
}
```

The provider maps the numeric `type` ID → `ArtworkItem.type` string. **Important**:
episode images may be **4:3 or 16:9** — there is no guarantee which. Some entities have a
single artwork of a single type.

### How the provider maps artwork type IDs → `ArtworkItem.type`

The mapping below is what `parse_artworks()` / `parse_artwork()` in `_tvdb_parsers.py`
actually implement (confirmed against the live `/artwork/types` call). Type IDs not in
any set are ignored:

| `ArtworkItem.type`         | TVDB type IDs  | Notes                                              |
| -------------------------- | -------------- | -------------------------------------------------- |
| `poster` / `season_poster` | `2, 7, 14, 27` | → `season_poster` when a season number is supplied |
| `backdrop`                 | `3, 8, 15`     | series/season/movie backgrounds                    |
| `landscape`                | `23, 25`       | TVDB ClearLogo (series + movie)                    |

> TVDB has **no** native "landscape" or "discart" artwork type — those concepts belong
> to Kodi/MediaElch. The provider repurposes ClearLogo (`23`/`25`) as `landscape`, and
> `Background` (1920×1080) is the closest backdrop equivalent. The first parsed
> `backdrop` URL is used as the primary backdrop fallback (TVDB's top-level `image`
> field is the editor-pick poster, not a backdrop).

---

## Artwork Types Catalogue

```
GET /artwork/types
```

> **Critical endpoint**: artwork type IDs are **dynamic** and should be fetched at
> runtime, then cached (see [Caching Strategy](#caching-strategy)).

**Response**: `data` = array of `ArtworkType`:

```json
{
  "id": 2,
  "name": "Poster",
  "slug": "poster",
  "recordType": "series",
  "imageFormat": "jpg",
  "width": 680,
  "height": 1000,
  "thumbWidth": 170,
  "thumbHeight": 250
}
```

| Field         | Type   | Description                                    |
| ------------- | ------ | ---------------------------------------------- |
| `id`          | int    | Type ID (used to filter)                       |
| `name`        | string | Poster, Banner, Fanart, Clearlogo, etc.        |
| `slug`        | string | URL slug                                       |
| `recordType`  | string | Applicable entity: series, movie, season, etc. |
| `imageFormat` | string | Expected format: jpg, png                      |
| `width`       | int    | Expected width in pixels                       |
| `height`      | int    | Expected height in pixels                      |
| `thumbWidth`  | int    | Thumbnail width                                |
| `thumbHeight` | int    | Thumbnail height                               |

**27 artwork types** (verified via the live API):

| ID  | Name           | RecordType | Dimensions  |
| --- | -------------- | ---------- | ----------- |
| 1   | Banner         | series     | 758 × 140   |
| 2   | Poster         | series     | 680 × 1000  |
| 3   | Background     | series     | 1920 × 1080 |
| 5   | Icon           | series     | 1024 × 1024 |
| 6   | Banner         | season     | 758 × 140   |
| 7   | Poster         | season     | 680 × 1000  |
| 8   | Background     | season     | 1920 × 1080 |
| 10  | Icon           | season     | 1024 × 1024 |
| 11  | 16:9 Screencap | episode    | 640 × 360   |
| 12  | 4:3 Screencap  | episode    | 640 × 480   |
| 13  | Photo          | actor      | 300 × 450   |
| 14  | Poster         | movie      | 680 × 1000  |
| 15  | Background     | movie      | 1920 × 1080 |
| 16  | Banner         | movie      | 758 × 140   |
| 18  | Icon           | movie      | 1024 × 1024 |
| 19  | Icon           | company    | 512 × 512   |
| 20  | Cinemagraph    | series     | 1280 × 720  |
| 21  | Cinemagraph    | movie      | 1280 × 720  |
| 22  | ClearArt       | series     | 1000 × 562  |
| 23  | ClearLogo      | series     | 800 × 310   |
| 24  | ClearArt       | movie      | 1000 × 562  |
| 25  | ClearLogo      | movie      | 800 × 310   |
| 26  | Icon           | award      | 1024 × 1024 |
| 27  | Poster         | list       | 680 × 1000  |

> **Missing IDs**: 4, 9, 17 do not exist.
> **No "landscape" or "discart"** — these are Kodi/MediaElch concepts, not TVDB. The
> `Background` (1920×1080) is the closest equivalent to "landscape".
> **No ClearArt/ClearLogo for seasons** — only for series and movies.

**Types relevant to the pipeline** (cross-reference with the
[provider mapping](#how-the-provider-maps-artwork-type-ids--artworkitemtype) above):

| Pipeline usage             | Type ID | Name       |
| -------------------------- | ------- | ---------- |
| Series poster              | 2       | Poster     |
| Series background/backdrop | 3       | Background |
| Season poster              | 7       | Poster     |
| Movie poster               | 14      | Poster     |
| Movie background/backdrop  | 15      | Background |
| Series ClearLogo           | 23      | ClearLogo  |

### Artwork statuses

```
GET /artwork/statuses
```

---

## Source / ID Types

```
GET /sources/types
```

> **Path**: `/sources/types` (plural), not `/source/types`.

Returns the list of external ID sources, used to interpret the `type` field on
`RemoteID` objects. **28 source types** (verified):

| ID  | Name             | Slug             | Pipeline usage                 |
| --- | ---------------- | ---------------- | ------------------------------ |
| 2   | IMDB             | imdb             | **Cross-ref series/movies**    |
| 3   | TMS (Zap2It)     | zap2it           | —                              |
| 4   | Official Website | official-website | —                              |
| 10  | TheMovieDB.com   | tmdb             | **Cross-ref movies → TMDB**    |
| 12  | TheMovieDB.com   | tmdbtv           | **Cross-ref TV series → TMDB** |
| 15  | TheMovieDB.com   | tmdbperson       | Cross-ref people → TMDB        |
| 16  | IMDB             | imdbperson       | Cross-ref people → IMDB        |
| 18  | Wikidata         | wikidata         | —                              |
| 19  | TV Maze          | tvmaze           | —                              |
| 28  | TheMovieDB.com   | tmdbcollection   | Cross-ref collections → TMDB   |

> **TMDB has 4 distinct IDs** depending on the entity type: movies (10), TV series (12),
> people (15), collections (28). Use the right slug for cross-referencing.

---

## Pagination

- The `page` parameter is **0-based** (TMDB starts at 1).
- Page size is fixed by the API per endpoint (not client-configurable). Episodes are
  paginated at **100 per page**.
- The `links` object in the response provides navigation (`prev`, `self`, `next`,
  `total_items`, `page_size`).
- `/search` uses `offset` and `limit` instead of `page` (max 5,000 results).

Episode pagination example:

```
GET /series/{id}/episodes/default?season=1&page=0
```

```json
{
  "links": {
    "prev": null,
    "next": "/series/81189/episodes/default?season=1&page=1",
    "total_items": 62,
    "page_size": 100
  }
}
```

The provider iterates pages until `links.next` is null (see `get_series_episodes()`).
Search results are returned in a single response (no `page` iteration).

---

## Season Types

TVDB supports multiple episode ordering schemes via season types:

| Type        | Description                               | Common usage                      |
| ----------- | ----------------------------------------- | --------------------------------- |
| `default`   | Aired order                               | **Standard — pipeline uses this** |
| `official`  | Official order                            | Rarely different                  |
| `dvd`       | DVD order                                 | Sometimes different               |
| `absolute`  | Absolute numbering (all seasons combined) | **Anime**                         |
| `alternate` | Alternate order                           | Special cases                     |
| `regional`  | Regional order                            | Specific markets                  |

The season type is a **mandatory** path segment of the episodes endpoint:
`/series/{id}/episodes/{season-type}`. The series object includes `defaultSeasonType` and
a `seasonTypes` array.

**Pipeline decision**: always use `default` season type (aired order). The provider only
accesses aired-order episodes.

---

## Endpoints — Auth

### Login

```
POST /login
```

Request: `{"apikey": "<key>"}`
Response: `{"status": "success", "data": {"token": "<jwt>"}}`

---

## Endpoints — Search

### Global Search

```
GET /search
```

Searches series, movies, people, and companies. Limit: **5,000 results**.

| Param         | Type   | Required | Description                                     |
| ------------- | ------ | -------- | ----------------------------------------------- |
| `query`       | string | No\*     | Search term (includes translations and aliases) |
| `q`           | string | No       | Deprecated alias of `query`                     |
| `type`        | string | No       | `movie`, `series`, `person`, `company`          |
| `year`        | number | No       | Filter by year                                  |
| `company`     | string | No       | Company name                                    |
| `country`     | string | No       | 3-char country code                             |
| `director`    | string | No       | Director name                                   |
| `language`    | string | No       | 3-char language code                            |
| `primaryType` | string | No       | Company type (companies only)                   |
| `network`     | string | No       | Network name (TV only)                          |
| `remote_id`   | string | No       | Search by IMDB or EIDR ID                       |
| `offset`      | number | No       | Pagination offset                               |
| `limit`       | number | No       | Max number of results                           |

\* At least `query` or `remote_id` must be supplied.

**Response** (each item, search uses snake_case):

```json
{
  "objectID": "series-81189",
  "id": "81189",
  "tvdb_id": "81189",
  "type": "series",
  "name": "Breaking Bad",
  "slug": "breaking-bad",
  "status": "Ended",
  "year": "2008",
  "country": "usa",
  "network": "AMC",
  "primary_language": "eng",
  "overview": "...",
  "image_url": "https://artworks.thetvdb.com/...",
  "poster": "https://artworks.thetvdb.com/...",
  "thumbnail": "https://artworks.thetvdb.com/...",
  "first_air_time": "2008-01-20",
  "is_official": true,
  "remote_ids": [{ "id": "tt0903747", "type": 2, "sourceName": "IMDB" }],
  "aliases": ["..."],
  "genres": ["Drama", "Thriller"],
  "translations": { "fra": "Breaking Bad", "eng": "Breaking Bad" },
  "overviews": { "fra": "FR overview...", "eng": "EN overview..." }
}
```

**Key fields for the pipeline**: `tvdb_id`, `type`, `name`, `year`, `remote_ids` (for
IMDB/TMDB cross-references), `translations`, `overviews`. Search results include
`remote_ids` directly — no separate external-IDs call is needed. Movie search results use
`first_release` instead of `first_air_time`.

### Search by external ID

```
GET /search/remoteid/{remoteId}
```

Finds a TVDB entity from an IMDB or EIDR ID.

| Param      | In   | Type   | Required | Description                    |
| ---------- | ---- | ------ | -------- | ------------------------------ |
| `remoteId` | Path | string | **Yes**  | External ID (e.g. `tt0903747`) |

**Response**: array of matching entities (series, movie, person, episode).

> **Pipeline usage**: cross-reference IMDB → TVDB in a single call.

---

## Endpoints — Series

### Series Base

```
GET /series/{id}
```

Returns the basic `SeriesBaseRecord`. Rarely used — the pipeline typically uses
`extended`.

```json
{
  "id": 81189,
  "name": "Breaking Bad",
  "slug": "breaking-bad",
  "image": "https://artworks.thetvdb.com/banners/...",
  "firstAired": "2008-01-20",
  "lastAired": "2013-09-29",
  "nextAired": "",
  "score": 2538828,
  "status": { "id": 2, "name": "Ended" },
  "originalCountry": "usa",
  "originalLanguage": "eng",
  "year": "2008",
  "nameTranslations": ["eng", "fra", "deu", "spa"],
  "overviewTranslations": ["eng", "fra", "deu", "spa"],
  "aliases": [{ "language": "eng", "name": "Breaking Bad" }],
  "lastUpdated": "2024-03-15 12:00:00",
  "isOrderRandomized": false
}
```

### Series Extended

```
GET /series/{id}/extended
```

| Param   | In    | Type    | Description                                                            |
| ------- | ----- | ------- | ---------------------------------------------------------------------- |
| `meta`  | Query | string  | `translations` (include translations) or `episodes` (include episodes) |
| `short` | Query | boolean | `true` excludes characters, artworks, trailers (reduces payload)       |

Returns the full `SeriesExtendedRecord` — all base fields **plus** `genres`, `seasons[]`,
`artworks[]`, `characters[]`, `companies`, `contentRatings[]`, `remoteIds[]`, `trailers[]`,
`lists`, `awards`, `tagOptions`, `seasonTypes`, `defaultSeasonType`, `averageRuntime`,
`originalNetwork`, `latestNetwork`, `airsDays`, `airsTime`.

```json
{
  "data": {
    "id": 81189,
    "name": "Breaking Bad",
    "genres": [{ "id": 5, "name": "Drama", "slug": "drama" }],
    "seasons": [
      {
        "id": 27009,
        "seriesId": 81189,
        "number": 0,
        "name": "Specials",
        "image": "...",
        "year": "2009"
      },
      {
        "id": 27010,
        "seriesId": 81189,
        "number": 1,
        "name": "Season 1",
        "image": "...",
        "year": "2008"
      }
    ],
    "artworks": [
      {
        "id": 12345,
        "image": "https://...",
        "thumbnail": "https://..._t.jpg",
        "type": 2,
        "language": "eng",
        "score": 100150,
        "width": 680,
        "height": 1000,
        "includesText": true
      }
    ],
    "characters": [
      {
        "id": 67890,
        "name": "Walter White",
        "peopleId": 253341,
        "personName": "Bryan Cranston",
        "image": "...",
        "isFeatured": true,
        "type": 3,
        "sort": 0,
        "seriesId": 81189,
        "episodeId": null,
        "movieId": null
      }
    ],
    "contentRatings": [
      { "id": 245, "name": "TV-14", "country": "usa", "contentType": "series" }
    ],
    "remoteIds": [
      { "id": "tt0903747", "type": 2, "sourceName": "IMDB" },
      { "id": "18164", "type": 12, "sourceName": "TheMovieDB.com" }
    ],
    "trailers": [
      {
        "id": 1,
        "name": "Trailer",
        "url": "https://youtube.com/...",
        "language": "eng",
        "runtime": 120
      }
    ]
  }
}
```

**Key fields for the pipeline**: `id`, `name`, `genres`, `seasons[]`, `remoteIds[]` (for
IMDB/TMDB), `artworks[]`, `characters[]`, `contentRatings[]`, `firstAired`, `status`.

> **Important**: the `episodes` array in the extended response (when `meta=episodes`)
> contains ALL episodes across ALL seasons — not just one season. Use
> `GET /series/{id}/episodes/default?season=N` for per-season pagination instead.

### Series Translation

```
GET /series/{id}/translations/{language}
```

Returns `{"name": "...", "overview": "...", "language": "fra"}`.

### Series Artworks (standalone)

```
GET /series/{id}/artworks
```

| Param  | In    | Type   | Required | Description                              |
| ------ | ----- | ------ | -------- | ---------------------------------------- |
| `id`   | Path  | number | **Yes**  | TVDB ID                                  |
| `lang` | Query | string | No       | Filter by language (e.g. `eng`, `fra`)   |
| `type` | Query | int    | No       | Filter by artwork type ID (e.g. `1,2,3`) |

Returns the **full series object** (`SeriesExtendedRecord`) with the `artworks` array
filtered by the given criteria. Same shape as `/extended` but without episodes — more
efficient for artwork-only needs.

### Filter Series

```
GET /series/filter
```

| Param           | Type   | Required | Description                                |
| --------------- | ------ | -------- | ------------------------------------------ |
| `country`       | string | **Yes**  | 3-char country code (e.g. `usa`)           |
| `lang`          | string | **Yes**  | 3-char language code (e.g. `eng`)          |
| `company`       | number | No       | Production company ID                      |
| `contentRating` | number | No       | Content rating ID                          |
| `genre`         | number | No       | Genre ID (1-36)                            |
| `sort`          | string | No       | `score`, `firstAired`, `lastAired`, `name` |
| `sortType`      | string | No       | `asc`, `desc`                              |
| `status`        | number | No       | 1, 2, or 3                                 |
| `year`          | number | No       | Release year                               |

> **`country` and `lang` are mandatory.**

### Series Statuses

```
GET /series/statuses
```

Returns the possible statuses. No parameters.

### Next Aired

```
GET /series/{id}/nextAired
```

> The `nextAired` field in the base record is being **deprecated**; TVDB recommends this
> dedicated endpoint instead.

---

## Endpoints — Seasons

### Season Base

```
GET /seasons/{id}
```

**Response**: `data` = `SeasonBaseRecord`.

```json
{
  "id": 27010,
  "seriesId": 81189,
  "number": 1,
  "name": "Season 1",
  "image": "https://artworks.thetvdb.com/...",
  "imageType": 7,
  "year": "2008",
  "type": { "id": 1, "name": "Aired Order", "type": "official" },
  "nameTranslations": ["eng", "fra"],
  "overviewTranslations": ["eng", "fra"]
}
```

### Season Extended

```
GET /seasons/{id}/extended
```

Adds to the base record:

| Field          | Type                | Description                 |
| -------------- | ------------------- | --------------------------- |
| `artwork`      | ArtworkBaseRecord[] | Season artworks (singular!) |
| `episodes`     | EpisodeBaseRecord[] | All episodes in the season  |
| `trailers`     | Trailer[]           | Trailers                    |
| `translations` | Translation[]       | Full translations           |
| `tagOptions`   | TagOption[]         | Metadata                    |

> **Pipeline tip**: this endpoint returns all episodes + artworks of a season in a single
> call. Note: `SeasonExtended` uses `artwork` (singular), while `SeriesExtended` uses
> `artworks` (plural) — an API inconsistency.

### Season Translation

```
GET /seasons/{id}/translations/{language}
```

### Season Types (reference)

```
GET /seasons/types
```

Returns the list of available season types (see [Season Types](#season-types)).

---

## Endpoints — Episodes

### Episodes by Season (key endpoint)

```
GET /series/{id}/episodes/{season-type}
```

| Param           | In    | Type   | Required | Default | Description                                                       |
| --------------- | ----- | ------ | -------- | ------- | ----------------------------------------------------------------- |
| `id`            | Path  | number | **Yes**  | —       | TVDB series ID                                                    |
| `season-type`   | Path  | string | **Yes**  | —       | `default`, `official`, `dvd`, `absolute`, `alternate`, `regional` |
| `page`          | Query | int    | **Yes**  | `0`     | Page number (0-based)                                             |
| `season`        | Query | int    | No       | `0`     | Filter by season number                                           |
| `episodeNumber` | Query | int    | No       | `0`     | Filter by episode number (requires `season`)                      |
| `airDate`       | Query | string | No       | —       | Filter by air date (`yyyy-mm-dd`)                                 |

**Response**:

```json
{
  "status": "success",
  "data": {
    "series": {
      /* SeriesBaseRecord */
    },
    "episodes": [
      {
        "id": 349232,
        "seriesId": 81189,
        "name": "Pilot",
        "number": 1,
        "seasonNumber": 1,
        "seasonName": "Season 1",
        "absoluteNumber": 1,
        "aired": "2008-01-20",
        "runtime": 58,
        "image": "https://artworks.thetvdb.com/...",
        "imageType": 12,
        "overview": "High school chemistry teacher...",
        "finaleType": null,
        "isMovie": 0,
        "linkedMovie": null,
        "nameTranslations": ["eng", "fra"],
        "overviewTranslations": ["eng", "fra"],
        "year": "2008"
      }
    ]
  }
}
```

**Filter by season**: `GET /series/81189/episodes/default?season=1` returns only season 1
episodes. **`episodeNumber` cannot be used without `season`.** The response is paginated;
use `page=0`, `page=1`, etc.

### Episodes — Translated (per season)

```
GET /series/{id}/episodes/{season-type}/{lang}
```

| Param         | In    | Type   | Required | Description                       |
| ------------- | ----- | ------ | -------- | --------------------------------- |
| `id`          | Path  | number | **Yes**  | TVDB ID                           |
| `season-type` | Path  | string | **Yes**  | Season type                       |
| `lang`        | Path  | string | **Yes**  | 3-char language code (e.g. `fra`) |
| `page`        | Query | int    | **Yes**  | Page (0-based)                    |

Returns episodes with translated names/overviews. More efficient than fetching individual
episode translations. Note: without `?season=N` this returns ALL episodes (specials
included).

### Episode Base

```
GET /episodes/{id}
```

**Response**: `data` = `EpisodeBaseRecord` (same shape as the episode objects above, plus
`airsAfterSeason`, `airsBeforeEpisode`, `airsBeforeSeason` for positioning specials).

- `finaleType`: `null`, `"season"`, `"midseason"`, or `"series"`.
- Important fields for the pipeline: `name`, `number`, `seasonNumber`, `aired`, `runtime`,
  `overview`, `image`.

### Episode Extended

```
GET /episodes/{id}/extended
```

| Param  | In    | Type   | Required | Description                            |
| ------ | ----- | ------ | -------- | -------------------------------------- |
| `id`   | Path  | number | **Yes**  | TVDB ID                                |
| `meta` | Query | string | No       | `translations` to include translations |

Adds to the base record: `characters[]`, `companies[]`, `contentRatings[]`, `networks[]`,
`remoteIds[]`, `studios[]`, `productionCode`, `awards[]`, `nominations[]`, `trailers[]`,
`translations`, `tagOptions[]`.

### Episode Translation

```
GET /episodes/{id}/translations/{language}
```

**Response**: `data` = `Translation` (translated name and overview).

---

## Endpoints — Movies

TVDB also has a movie database (less complete than TMDB for films).

### Movie Base

```
GET /movies/{id}
```

**Response**: `data` = `MovieBaseRecord`.

```json
{
  "id": 12345,
  "name": "Movie Title",
  "slug": "movie-title",
  "image": "https://artworks.thetvdb.com/...",
  "year": "2024",
  "score": 5000,
  "runtime": 120,
  "status": { "id": 1, "name": "Released" },
  "aliases": [],
  "nameTranslations": ["eng", "fra"],
  "overviewTranslations": ["eng", "fra"],
  "lastUpdated": "..."
}
```

### Movie Extended

```
GET /movies/{id}/extended
```

| Param   | Type    | Required | Description                                    |
| ------- | ------- | -------- | ---------------------------------------------- |
| `meta`  | string  | No       | `translations` to include translations         |
| `short` | boolean | No       | `true` excludes characters, artworks, trailers |

Adds: `artworks`, `characters`, `companies`, `contentRatings`, `genres`, `remoteIds`,
`trailers`, `translations`, `releases`, `boxOffice`, `budget`, `first_release`, etc.

> **Field name**: TVDB movies use `first_release` for the release date (confirmed from
> the live API), not `release_date` (TMDB). The pipeline parser checks both.

### Filter Movies

```
GET /movies/filter
```

Same parameters as `/series/filter` (with `country` and `lang` **mandatory**), except:

- `sort`: `score`, `firstAired`, `name` (no `lastAired`).
- No `sortType`.

### Movie Translation

```
GET /movies/{id}/translations/{language}
```

### Movie Statuses

```
GET /movies/statuses
```

---

## Endpoints — People & Castmembers

### Person Base

```
GET /people/{id}
```

**Response**: `data` = `PeopleBaseRecord` (`id`, `name`, `image`, `score`, `aliases`,
`nameTranslations`, `overviewTranslations`).

### Person Extended

```
GET /people/{id}/extended
```

Adds: `biographies[]`, `birth`, `birthPlace`, `death`, `gender`, `characters[]`,
`remoteIds[]`, `awards[]`, `translations`.

### Person Translation

```
GET /people/{id}/translations/{language}
```

### People Types

```
GET /people/types
```

Returns the person types: Actor, Director, Writer, etc.

### Castmembers / Characters

```
GET /characters/{id}
```

A **Castmember** (TVDB `Character` record) ties a person to a role on a series, movie, or
episode. Characters are returned inline in the `characters[]` array of series/movie/episode
extended responses; the standalone endpoint fetches a single character record by ID.

`Character` fields:

| Field          | Type     | Description                  |
| -------------- | -------- | ---------------------------- |
| `id`           | int      | Character ID                 |
| `name`         | string   | Character name               |
| `peopleId`     | int      | Person ID                    |
| `personName`   | string   | Actor/actress name           |
| `personImgURL` | string   | Actor photo URL              |
| `image`        | string   | Character image              |
| `isFeatured`   | boolean  | Main character               |
| `type`         | int      | Type (actor, director, etc.) |
| `sort`         | int      | Display order                |
| `seriesId`     | int/null | Associated series            |
| `movieId`      | int/null | Associated movie             |
| `episodeId`    | int/null | Associated episode           |

> The pipeline does not currently fetch castmembers standalone — it reads the inline
> `characters[]` from extended series/movie responses. This endpoint is documented for
> completeness.

---

## Endpoints — Companies

```
GET /companies
GET /companies/{id}
GET /companies/types
```

- `GET /companies` — paginated list of all companies (`data` = `Company[]`, with `links`).
- `GET /companies/{id}` — a single `Company` record by ID.
- `GET /companies/types` — the company type catalogue (network, studio, production, etc.).

`Company` record (returned inline in series/movie extended responses under `companies`,
grouped by type, and by these endpoints):

| Field                | Type   | Description                              |
| -------------------- | ------ | ---------------------------------------- |
| `id`                 | int    | Company ID                               |
| `name`               | string | Company name                             |
| `slug`               | string | URL slug                                 |
| `country`            | string | 3-char country code                      |
| `primaryCompanyType` | int    | Company type ID (see `/companies/types`) |
| `activeDate`         | string | Active-from date                         |
| `inactiveDate`       | string | Active-until date                        |
| `companyType`        | object | `{ companyTypeId, companyTypeName }`     |
| `parentCompany`      | object | `{ id, name, relation }` when applicable |

> The series/movie extended response exposes companies under a `companies` object keyed by
> type (network, studio, production, distributor, special_effects). The pipeline reads
> these inline; the standalone `/companies` endpoints are documented for completeness.

---

## Endpoints — Awards

```
GET /awards
GET /awards/{id}
GET /awards/{id}/extended
GET /awards/categories/{id}
GET /awards/categories/{id}/extended
```

- `GET /awards` — the catalogue of award bodies (`data` = `AwardBaseRecord[]`).
- `GET /awards/{id}` — a single award (e.g. Emmy, Golden Globe).
- `GET /awards/{id}/extended` — adds categories and per-category nominees.
- `GET /awards/categories/{id}` / `.../extended` — a single award category and its
  nominees.

`AwardBaseRecord`:

| Field  | Type   | Description |
| ------ | ------ | ----------- |
| `id`   | int    | Award ID    |
| `name` | string | Award name  |

Award nominations appear inline on `EpisodeExtendedRecord` (`awards[]`, `nominations[]`)
and on `people`/`movie` extended records. Common award-type reference:

| Award ID (example) | Name            | Scope     |
| ------------------ | --------------- | --------- |
| 1                  | Emmy Awards     | TV        |
| 2                  | Golden Globe    | TV + film |
| 3                  | Academy Awards  | Film      |
| 4                  | BAFTA           | TV + film |
| 5                  | Critics' Choice | TV + film |

> Award IDs are catalogue values — fetch `/awards` at runtime rather than hardcoding them.
> The pipeline does not currently consume awards; this section is documented for
> completeness.

---

## Endpoints — Artwork

### Artwork by ID

```
GET /artwork/{id}
```

**Response**: `data` = `ArtworkBaseRecord`. Rarely needed — artwork data is included in
entity extended responses.

```json
{
  "id": 12345,
  "image": "https://artworks.thetvdb.com/banners/v4/series/81189/posters/5f148be2c4866.jpg",
  "thumbnail": "https://artworks.thetvdb.com/banners/v4/series/81189/posters/5f148be2c4866_t.jpg",
  "type": 2,
  "language": "eng",
  "score": 100150,
  "width": 680,
  "height": 1000,
  "includesText": true
}
```

### Artwork Extended

```
GET /artwork/{id}/extended
```

Adds: `thumbnailHeight`, `thumbnailWidth`, `updatedAt`, `status`, `tagOptions`,
`seriesId`, `seasonId`, `episodeId`, `movieId`, `peopleId`, `networkId`.

### Artwork Types & Statuses

See [Artwork Types Catalogue](#artwork-types-catalogue) for `GET /artwork/types` and
`GET /artwork/statuses`.

---

## Endpoints — Reference Data

| Endpoint           | Purpose                         | Cache        |
| ------------------ | ------------------------------- | ------------ |
| `/genres`          | Genre list                      | Weekly+      |
| `/genres/{id}`     | Single genre                    | Weekly+      |
| `/languages`       | Available languages             | Weekly+      |
| `/countries`       | Available countries             | Weekly+      |
| `/content/ratings` | Content ratings                 | Weekly+      |
| `/series/statuses` | Series statuses                 | Weekly+      |
| `/movies/statuses` | Movie statuses                  | Weekly+      |
| `/sources/types`   | External ID source types        | Weekly+      |
| `/updates`         | Changed records since timestamp | Do not cache |

### Genres

```
GET /genres
```

**Response**: array of `GenreBaseRecord` — `{ "id": 5, "name": "Drama", "slug": "drama" }`.

### Content Ratings

```
GET /content/ratings
```

```json
{
  "id": 245,
  "name": "TV-14",
  "description": "...",
  "country": "usa",
  "contentType": "series",
  "order": 4,
  "fullName": "TV-14"
}
```

### Languages

```
GET /languages
```

```json
[
  {
    "id": "fra",
    "name": "French",
    "nativeName": "Français",
    "shortCode": "fr"
  },
  { "id": "eng", "name": "English", "nativeName": "English", "shortCode": "en" }
]
```

> **`shortCode` is always `null`** in current responses. The `id` (3-char, e.g. `fra`) is
> the only reliable identifier. For TVDB→TMDB mapping, maintain a manual conversion table
> (`fra`→`fr-FR`, `eng`→`en-US`).

### Countries

```
GET /countries
```

```json
[
  { "id": "fra", "name": "France", "shortCode": "fr" },
  { "id": "usa", "name": "United States", "shortCode": "us" }
]
```

---

## Endpoints — Updates

```
GET /updates
```

Fetches entities changed since a given timestamp. Essential for keeping a cache fresh.

| Param    | Type   | Required | Description                                       |
| -------- | ------ | -------- | ------------------------------------------------- |
| `since`  | number | **Yes**  | Unix timestamp — only changes after this point    |
| `type`   | string | No       | Entity type (e.g. `series`, `episodes`, `movies`) |
| `action` | string | No       | `delete` or `update`                              |
| `page`   | number | No       | Pagination                                        |

**Response**: array of `EntityUpdate`.

```json
{
  "entityType": "series",
  "methodInt": 2,
  "method": "update",
  "recordId": 81189,
  "timeStamp": 1710504000,
  "seriesId": 81189,
  "mergeToId": null,
  "mergeToEntityType": null,
  "userId": 12345,
  "extraInfo": "..."
}
```

| `methodInt` | Meaning |
| ----------- | ------- |
| 1           | Create  |
| 2           | Update  |
| 3           | Delete  |

> **Merge handling**: when a duplicate is deleted, `mergeToId` and `mergeToEntityType`
> indicate which record the data was consolidated into.
> **Use `entityType`, not `recordType`** — `recordType` is always empty in `/updates`
> responses.

---

## Cross-Provider IDs (IMDB, TMDB)

### TVDB → IMDB/TMDB

Fetch the extended record and read `remoteIds[]`:

```
GET /series/{id}/extended
GET /movies/{id}/extended
```

Each `RemoteID` object:

```json
{ "id": "tt0903747", "type": 2, "sourceName": "IMDB" }
```

The `type` references the `SourceType` ID (see [Source / ID Types](#source--id-types)).

### IMDB → TVDB

```
GET /search/remoteid/{imdb_id}
```

Example: `GET /search/remoteid/tt0903747` → returns Breaking Bad.

### TMDB → TVDB

No direct endpoint. Use TMDB `/find/{tmdb_id}?external_source=tvdb_id` for the reverse
cross-reference, or search by name.

> **Pipeline ID-family discipline**: TVDB is the primary scrape source for TV; TMDB is
> info + fallback; IMDB is info only. The cross-provider ID flow lives in
> `personalscraper/scraper/_xref.py` — `TVDBClient` itself does not compose `IDValidator`.

---

## Caching Strategy

The following endpoints return data that changes rarely. **Cache for 1+ week** (the
reference-data endpoints in the table above already note this):

- `/artwork/types`
- `/artwork/statuses`
- `/content/ratings`
- `/countries`
- `/entities`
- `/genders`
- `/genres`
- `/inspiration/types`
- `/languages`
- `/movies/statuses`
- `/people/types`
- `/seasons/types`
- `/series/statuses`
- `/sources/types`

**Do not cache** `/updates` (it is the cache-invalidation source). The JWT token is cached
for the process lifetime (30-day TTL, re-login on 401).

There is no single TMDB-style `/configuration` endpoint — reference data is spread across
the endpoints above.

---

## Optimal Call Strategy

### For a TV series (scrape step)

```
1. POST /login
   → JWT token (cache for the process lifetime)

2. GET /search?query={title}&type=series&year={year}
   → TVDB ID + year + remote_ids in the results

3. GET /series/{id}/extended?short=true
   → Details + genres + seasons[] + remoteIds[] + contentRatings[]
   → (short=true excludes artworks/characters/trailers to reduce payload)

4. GET /series/{id}/artworks?type={poster_type_id},{background_type_id}
   → Artworks filtered by type (poster + background only)

5. For each season:
   GET /series/{id}/episodes/default?season={n}
   → Episode list (name, number, date, runtime, image, overview)

6. For French episode titles:
   GET /episodes/{id}/translations/fra
   → Translated name and overview
   (OR use GET /series/{id}/episodes/default/fra?page=0 for everything in one block)
```

### Total call count

| Step                 | Calls                              |
| -------------------- | ---------------------------------- |
| Login                | 1                                  |
| Search               | 1                                  |
| Series extended      | 1                                  |
| Filtered artworks    | 1                                  |
| Episodes per season  | N (= number of seasons)            |
| Episode translations | N (or 1 with the grouped endpoint) |
| **Total**            | **4 + 2N**                         |

For a 5-season series: **~14 calls**.

### Comparison with TMDB

| Operation              | TVDB         | TMDB                    |
| ---------------------- | ------------ | ----------------------- |
| Auth                   | 1 call/month | 0 (API key)             |
| Series search          | 1            | 1                       |
| Details + IDs + images | 2-3          | 1 (append_to_response)  |
| Episodes per season    | N            | N                       |
| Translations           | N or 1       | Included via `language` |
| **Total (5 seasons)**  | ~14          | ~7                      |

> TMDB is more economical thanks to `append_to_response`. But TVDB is the primary source
> for TV data because its series coverage is more complete.

---

## Response Schemas

### Search Result (series)

```json
{
  "tvdb_id": 81189,
  "id": "a1b2c3d4-...",
  "name": "Breaking Bad",
  "type": "series",
  "year": "2008",
  "overview": "Walter White, a New Mexico chemistry teacher...",
  "image_url": "https://artworks.thetvdb.com/banners/posters/81189-10.jpg",
  "thumbnail": "https://artworks.thetvdb.com/banners/v4/series/81189/posters/...",
  "translations": { "fra": "Breaking Bad", "eng": "Breaking Bad" },
  "remote_ids": [
    { "sourceId": 457, "id": "1396", "type": 2, "name": "TheMovieDB.com" },
    { "sourceId": 3, "id": "tt0903747", "type": 2, "name": "IMDB" }
  ],
  "primary_language": "eng",
  "first_air_time": "2008-01-20",
  "aliases": ["Breaking Bad: Ruptura Total"],
  "network": "AMC",
  "status": "Ended"
}
```

### Search Result (movie)

Same structure as series, but `type: "movie"` and `first_release` instead of
`first_air_time`.

### Episode

```json
{
  "id": 123456,
  "number": 1,
  "name": "Pilot",
  "runtime": 58,
  "aired": "2008-01-20",
  "image": "https://artworks.thetvdb.com/banners/v4/episode/...",
  "overview": "Walter White is diagnosed with terminal lung cancer...",
  "seasonNumber": 1,
  "absoluteNumber": 1,
  "isMovie": false,
  "finaleType": null,
  "nameTranslations": ["eng", "fra", "deu"],
  "overviewTranslations": ["eng", "fra"]
}
```

### Artwork Item (within entity)

```json
{
  "id": 12345,
  "type": 2,
  "image": "https://artworks.thetvdb.com/banners/posters/81189-10.jpg",
  "thumbnail": "https://artworks.thetvdb.com/banners/v4/series/81189/posters/...",
  "language": "eng",
  "season": null
}
```

### Field tables

#### SeriesBaseRecord

| Field                  | Type     | Description                          |
| ---------------------- | -------- | ------------------------------------ |
| `id`                   | int64    | TVDB ID                              |
| `name`                 | string   | Series name                          |
| `slug`                 | string   | URL identifier                       |
| `image`                | string   | Primary image URL                    |
| `firstAired`           | string   | First air date                       |
| `lastAired`            | string   | Last air date                        |
| `nextAired`            | string   | Next scheduled airing                |
| `score`                | number   | Popularity score (relative)          |
| `status`               | Status   | Status (Continuing, Ended, etc.)     |
| `originalCountry`      | string   | Country of origin (3 chars)          |
| `originalLanguage`     | string   | Original language (3 chars)          |
| `year`                 | string   | Release year                         |
| `nameTranslations`     | string[] | Languages with a translated name     |
| `overviewTranslations` | string[] | Languages with a translated overview |
| `aliases`              | Alias[]  | Alternative titles                   |
| `lastUpdated`          | string   | Last modification                    |
| `isOrderRandomized`    | boolean  | Episodes ordered randomly            |

#### EpisodeBaseRecord

| Field                  | Type        | Description                          |
| ---------------------- | ----------- | ------------------------------------ |
| `id`                   | int64       | TVDB ID                              |
| `seriesId`             | int64       | Parent series ID                     |
| `name`                 | string      | Episode title                        |
| `number`               | int         | Episode number within the season     |
| `seasonNumber`         | int         | Season number                        |
| `seasonName`           | string      | Season name                          |
| `absoluteNumber`       | int         | Absolute number (all seasons)        |
| `aired`                | string      | Air date                             |
| `runtime`              | int/null    | Duration in minutes                  |
| `image`                | string      | Image URL (still)                    |
| `imageType`            | int/null    | Image type                           |
| `overview`             | string      | Overview                             |
| `finaleType`           | string/null | `season`, `midseason`, `series`      |
| `isMovie`              | int64       | Whether linked to a movie            |
| `linkedMovie`          | int/null    | Associated movie ID                  |
| `airsAfterSeason`      | int/null    | Special: airs after this season      |
| `airsBeforeEpisode`    | int/null    | Special: airs before this episode    |
| `airsBeforeSeason`     | int/null    | Special: airs before this season     |
| `year`                 | string      | Year                                 |
| `nameTranslations`     | string[]    | Languages with a translated name     |
| `overviewTranslations` | string[]    | Languages with a translated overview |
| `lastUpdated`          | string      | Last modification                    |

#### SeasonBaseRecord

| Field                  | Type       | Description                          |
| ---------------------- | ---------- | ------------------------------------ |
| `id`                   | int        | TVDB ID                              |
| `seriesId`             | int64      | Parent series ID                     |
| `number`               | int64      | Season number (0 = specials)         |
| `name`                 | string     | Season name                          |
| `image`                | string     | Season poster URL                    |
| `imageType`            | int        | Image type                           |
| `year`                 | string     | Year                                 |
| `type`                 | SeasonType | Season type                          |
| `lastUpdated`          | string     | Last modification                    |
| `nameTranslations`     | string[]   | Languages with a translated name     |
| `overviewTranslations` | string[]   | Languages with a translated overview |

#### ArtworkBaseRecord

| Field          | Type    | Description                           |
| -------------- | ------- | ------------------------------------- |
| `id`           | int     | Artwork ID                            |
| `image`        | string  | Full image URL                        |
| `thumbnail`    | string  | Thumbnail URL                         |
| `type`         | int     | Type ID (references `/artwork/types`) |
| `language`     | string  | 3-char language code                  |
| `score`        | number  | Community score                       |
| `width`        | int     | Width in pixels                       |
| `height`       | int     | Height in pixels                      |
| `includesText` | boolean | Image contains embedded text          |

#### RemoteID

| Field        | Type   | Description                                         |
| ------------ | ------ | --------------------------------------------------- |
| `id`         | string | External ID value (e.g. `tt0903747`)                |
| `type`       | int    | Source type ID                                      |
| `sourceName` | string | Human-readable name (e.g. `IMDB`, `TheMovieDB.com`) |

#### Translation

| Field       | Type     | Description                |
| ----------- | -------- | -------------------------- |
| `language`  | string   | 3-char language code       |
| `name`      | string   | Translated name            |
| `overview`  | string   | Translated overview        |
| `aliases`   | string[] | Translated aliases         |
| `isAlias`   | boolean  | Is an alias                |
| `isPrimary` | boolean  | Is the primary translation |
| `tagline`   | string   | Tagline (movies only)      |

#### SearchResult (key fields)

| Field              | Type       | Description                                 |
| ------------------ | ---------- | ------------------------------------------- |
| `objectID`         | string     | Internal ID                                 |
| `tvdb_id`          | string     | TVDB ID                                     |
| `type`             | string     | `series`, `movie`, `person`, `company`      |
| `name`             | string     | Primary name                                |
| `slug`             | string     | URL slug                                    |
| `year`             | string     | Year                                        |
| `status`           | string     | Status                                      |
| `country`          | string     | Country of origin                           |
| `network`          | string     | Broadcast network                           |
| `primary_language` | string     | Primary language                            |
| `overview`         | string     | Overview                                    |
| `image_url`        | string     | Primary image URL                           |
| `poster`           | string     | Poster URL                                  |
| `first_air_time`   | string     | First air date                              |
| `is_official`      | boolean    | Official entry                              |
| `remote_ids`       | RemoteID[] | External IDs                                |
| `translations`     | object     | `{ "fra": "FR title", "eng": "..." }`       |
| `overviews`        | object     | `{ "fra": "FR overview...", "eng": "..." }` |
| `genres`           | string[]   | Genre names                                 |
| `aliases`          | string[]   | Alternative titles                          |

---

## Provider Implementation Notes

### Bootstrap flow (deferred login)

The bootstrap `POST /login` exchange is **deferred** to the first real HTTP call.
`__init__` is network-free (it only records credentials); the one-shot
`HttpTransport(NoAuth) → POST /login → JWT` runs lazily via the `_transport` property /
`_ensure_transport()`. This lets the registry construct the client (and unit tests
exercise it) without network access.

```python
# Phase 1: Bootstrap — one-shot HttpTransport with NoAuth → login (lazy, on first use)
bootstrap_policy = TransportPolicy(
    provider_name=TVDB_BOOTSTRAP,
    base_url="https://api4.thetvdb.com/v4",
    auth=NoAuth(),
    timeout_seconds=15.0,
    retry=RetryPolicy(max_attempts=4),
    circuit=circuit_policy,
    rate_limit=RateLimitPolicy(requests_per_second=20.0),
)
with HttpTransport(bootstrap_policy, event_bus=event_bus) as bootstrap:
    resp = bootstrap.post("/login", data={"apikey": api_key})
jwt = resp["data"]["token"]

# Phase 2: Main client — BearerAuth with JWT
main_policy = TVDBClient.policy(jwt, circuit=circuit_policy)
transport = HttpTransport(main_policy, event_bus=event_bus)
```

### TransportPolicy

```python
@classmethod
def policy(cls, jwt_token: str, *, circuit: CircuitPolicy | None = None) -> TransportPolicy:
    return TransportPolicy(
        provider_name=ProviderName.TVDB,
        base_url="https://api4.thetvdb.com/v4",
        auth=BearerAuth(jwt_token),
        timeout_seconds=15.0,
        retry=RetryPolicy(max_attempts=4),
        circuit=circuit if circuit is not None else CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
        rate_limit=RateLimitPolicy(requests_per_second=20.0),
    )
```

Module defaults: `_DEFAULT_CIRCUIT = CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0)`,
`_DEFAULT_RATE = RateLimitPolicy(requests_per_second=20.0)`, `_DEFAULT_RETRY = RetryPolicy(max_attempts=4)`.

### Capabilities composed by `TVDBClient`

`TVDBClient` composes the atomic capability Protocols from
`personalscraper/api/metadata/_contracts.py`:

| Method                                       | Endpoint                                     | Returns                     |
| -------------------------------------------- | -------------------------------------------- | --------------------------- |
| `search(title, year, media_type)`            | `GET /search`                                | `list[SearchResult]`        |
| `get_details(media_id, media_type)`          | `GET /{series\|movies}/{id}/extended`        | `MediaDetails`              |
| `get_tv(provider_id)`                        | alias of `get_series`                        | `MediaDetails`              |
| `get_movie(movie_id)`                        | `GET /movies/{id}/extended`                  | `MediaDetails`              |
| `get_artwork_urls(media_id, media_type)`     | From extended response `artworks`            | `list[ArtworkItem]`         |
| `get_episodes(series_id, season)`            | `GET /series/{id}/episodes/default`          | `list[EpisodeInfo]`         |
| `get_season(tv_id, season)`                  | `GET /series/{id}/episodes/default?season=N` | `SeasonDetails`             |
| `get_videos(media_id, media_type, language)` | From extended response `trailers`            | `list[Video]`               |
| `get_keywords(media_id, media_type)`         | Not supported by TVDB v4                     | `raise NotImplementedError` |
| `get_notations(media_id, media_type)`        | Not supported (score is popularity rank)     | `raise NotImplementedError` |

It does **not** compose `KeywordProvider` (no keywords endpoint) or `IDValidator`
(cross-provider ID validation flows through
`personalscraper/scraper/_xref.py`).

### Response unwrapping

Every TVDB response must be unwrapped via `unwrap()` in `_tvdb_parsers.py`. On
`status == "failure"` it raises `ApiError`:

```python
raw = self._transport.get(path, params=params)
data = unwrap(raw)  # strips the {"status": ..., "data": ...} envelope
```

### Image handling

TVDB returns full image URLs. No assembly is needed (unlike TMDB's
`base_url + size + path`):

```python
image_url = artwork["image"]   # TVDB: direct
```

---

## Particularities

### 1. TVDB wraps ALL responses in a `data` envelope

Every endpoint wraps the actual payload in `{"status": "success", "data": ...}`. The
provider MUST unwrap `response["data"]` before passing to parsers. TMDB returns the raw
object directly.

### 2. Language codes are 3-character

TVDB uses `fra`, `eng`, `spa` — not `fr-FR`, `en-US` like TMDB. The pipeline uses 2-char
codes internally and maps them via `map_language()` before each API call.

### 3. Token TTL = 30 days — no runtime refresh

JWT `exp` claim confirmed: 30 days from login. No `refresh_token` endpoint exists.
Re-authenticate via `/login` when the token expires (HTTP 401). The pipeline process never
runs 30 days, so this is effectively init-only (and the login is deferred to first use).

### 4. Artwork types are numeric IDs

TVDB uses integer type IDs, not string names like TMDB. The provider maps them to
`ArtworkItem.type` strings using the sets in `_tvdb_parsers.py` (posters `{2,7,14,27}`,
backgrounds `{3,8,15}`, ClearLogos `{23,25}`). IDs not in any set are ignored. The type
catalogue is dynamic — fetch `/artwork/types` at runtime and cache it.

### 5. Season types: `default` is the pipeline's choice

Multiple episode orderings exist (`default`, `official`, `dvd`, `absolute`, `alternate`,
`regional`). The pipeline always uses aired order (`default`).

### 6. `score` is an integer popularity rank, NOT a rating

TVDB `score` is an arbitrary integer for relative popularity. It is NOT comparable across
entity types (TVDB docs explicitly warn against this). The provider leaves `rating=None`
for TVDB — notations and ratings are TMDB/OMDB/Trakt territory.

### 7. Episodes include runtime per episode

TVDB episode objects have `runtime` (int, minutes) directly. Unlike TMDB, which puts
`episode_run_time` as an array on the series object. The parser sets
`EpisodeInfo.runtime_minutes = ep["runtime"] or None`.

### 8. `first_release` (not `release_date`)

TVDB movie objects use `first_release` for the release date (confirmed from the live API).
TMDB uses `release_date`. The parser checks both.

### 9. Episodes are paginated (100/page), search is NOT

Episodes use 0-based pagination with `links.next` for iteration. Search returns all
results in a single response (`offset`/`limit`, max 5,000). For series with >100 episodes
per season (anime, long-running shows), iterate pages until `links.next` is null.

### 10. `remote_ids` included in search results

TVDB search results include a `remote_ids` array with TMDB/IMDB cross-references. This
allows matching against TMDB data without an extra API call.

### 11. `get_notations` and `get_keywords` are NOT supported

TVDB has no keywords endpoint and no rating/notation system beyond the popularity `score`.
Both methods `raise NotImplementedError`; the pipeline falls back to TMDB for these
capabilities.

### 12. Series `extended` includes ALL episodes

With `meta=episodes`, the `/series/{id}/extended` response includes an `episodes` array
with ALL episodes across ALL seasons. For large series this is inefficient — use
`/series/{id}/episodes/default?season=N` for per-season fetching.

### 13. Read-only API

The TVDB v4 API is **read-only**. There is no endpoint to create or modify
series/movies/episodes (the `/user/favorites` POST is the only write, and is out of scope).

### 14. No `append_to_response`

Unlike TMDB, TVDB has no `append_to_response` mechanism. The `extended` endpoints with
`meta` and `short` are the closest equivalent.

### 15. `short=true` sets arrays to `null`

With `?short=true`, `artworks`, `characters`, `episodes` become `null` (not empty arrays).
Check with `is not None`.

### 16. Two distinct error response shapes

Login errors carry `{status, message, data}`; general endpoint errors carry `{message}`
only. See [Error Codes & Retry Strategy](#error-codes--retry-strategy).

### 17. Non-existent fields (live verification)

`audioLanguages`, `subtitleLanguages`, `spokenLanguages` do **not** exist in
`SeriesExtendedRecord` (tested on Breaking Bad). `studios` and `awards` exist only on
`EpisodeExtendedRecord`, not on `SeriesExtendedRecord`.

---

## Edge Cases (live verification)

| #   | Behavior                                             | Detail                                                                                                          |
| --- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 1   | PIN not required for Negotiated Contract keys        | `{"apikey": "..."}` is enough. Only User Subscription keys need a PIN.                                          |
| 2   | Two error response shapes                            | Login: `{status, message, data}`. Endpoints: `{message}` only. The code must handle both.                       |
| 3   | HTTP 405 on `GET /login`                             | Only POST is accepted. Returns `{"message": "Method Not Allowed"}`.                                             |
| 4   | Empty search = HTTP 200                              | `{"status":"success","data":[],"links":{...}}` — not a 404. Check `len(data)`.                                  |
| 5   | Search in snake_case, entities in camelCase          | `image_url`, `first_air_time`, `tvdb_id` (search) vs `imageUrl`, `firstAired` (entities). API inconsistency.    |
| 6   | `artwork` (singular) for seasons                     | `SeasonExtended` uses `artwork`, `SeriesExtended` uses `artworks` (plural). API inconsistency.                  |
| 7   | `short=true` sets arrays to `null`                   | `artworks`, `characters`, `episodes` become `null` (not empty arrays). Check with `is not None`.                |
| 8   | `audioLanguages` etc. do not exist                   | `audioLanguages`, `subtitleLanguages`, `spokenLanguages` absent from `SeriesExtendedRecord`.                    |
| 9   | Languages `shortCode` always null                    | The field exists on `/languages` but is `None` for every language. Do not use it for mapping.                   |
| 10  | 4 distinct TMDB IDs in source types                  | movies=10, TV series=12, people=15, collections=28. Use the right one for cross-referencing.                    |
| 11  | Translated episodes: all seasons by default          | `/series/{id}/episodes/default/fra` returns ALL episodes (specials included). Filter with `?season=N`.          |
| 12  | Updates: `entityType` not `recordType`               | `recordType` is always empty in `/updates` responses. Use `entityType` instead.                                 |
| 13  | 404 = `{status:"failure", message:"...", data:null}` | Includes the exception type: `"NotFoundException: error fetching series"`.                                      |
| 14  | Content ratings FR split by contentType              | "episode" and "movie" have separate FR ratings: TP, -10, -12, -16 (episodes) vs TP, -10, -12, -16, UR (movies). |
| 15  | No landscape/discart in TVDB                         | These are Kodi/MediaElch concepts. `Background` (1920×1080) is the closest equivalent.                          |
| 16  | `episodeNumber` requires `season`                    | On the episodes-by-season endpoint, `episodeNumber` cannot be used alone — it requires `season`.                |

---

## Endpoint Inventory (appendix)

Complete list of TVDB v4 endpoints (~67):

| Category        | Endpoints                                                                                                                                                                                                                                                                         |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Auth            | POST `/login`                                                                                                                                                                                                                                                                     |
| Artwork         | GET `/artwork/{id}`, `/artwork/{id}/extended`, `/artwork/statuses`, `/artwork/types`                                                                                                                                                                                              |
| Awards          | GET `/awards`, `/awards/{id}`, `/awards/{id}/extended`, `/awards/categories/{id}`, `/awards/categories/{id}/extended`                                                                                                                                                             |
| Characters      | GET `/characters/{id}`                                                                                                                                                                                                                                                            |
| Companies       | GET `/companies`, `/companies/{id}`, `/companies/types`                                                                                                                                                                                                                           |
| Content Ratings | GET `/content/ratings`                                                                                                                                                                                                                                                            |
| Countries       | GET `/countries`                                                                                                                                                                                                                                                                  |
| Entities        | GET `/entities`                                                                                                                                                                                                                                                                   |
| Episodes        | GET `/episodes`, `/episodes/{id}`, `/episodes/{id}/extended`, `/episodes/{id}/translations/{lang}`                                                                                                                                                                                |
| Genders         | GET `/genders`                                                                                                                                                                                                                                                                    |
| Genres          | GET `/genres`, `/genres/{id}`                                                                                                                                                                                                                                                     |
| Inspiration     | GET `/inspiration/types`                                                                                                                                                                                                                                                          |
| Languages       | GET `/languages`                                                                                                                                                                                                                                                                  |
| Lists           | GET `/lists`, `/lists/{id}`, `/lists/{id}/extended`, `/lists/{id}/translations/{lang}`, `/lists/slug/{slug}`                                                                                                                                                                      |
| Movies          | GET `/movies`, `/movies/{id}`, `/movies/{id}/extended`, `/movies/{id}/translations/{lang}`, `/movies/filter`, `/movies/slug/{slug}`, `/movies/statuses`                                                                                                                           |
| People          | GET `/people`, `/people/{id}`, `/people/{id}/extended`, `/people/{id}/translations/{lang}`, `/people/types`                                                                                                                                                                       |
| Search          | GET `/search`, `/search/remoteid/{remoteId}`                                                                                                                                                                                                                                      |
| Seasons         | GET `/seasons`, `/seasons/{id}`, `/seasons/{id}/extended`, `/seasons/{id}/translations/{lang}`, `/seasons/types`                                                                                                                                                                  |
| Series          | GET `/series`, `/series/{id}`, `/series/{id}/artworks`, `/series/{id}/extended`, `/series/{id}/episodes/{type}`, `/series/{id}/episodes/{type}/{lang}`, `/series/{id}/nextAired`, `/series/{id}/translations/{lang}`, `/series/filter`, `/series/slug/{slug}`, `/series/statuses` |
| Source Types    | GET `/sources/types`                                                                                                                                                                                                                                                              |
| Updates         | GET `/updates`                                                                                                                                                                                                                                                                    |
| User            | GET `/user`, `/user/{id}`, `/user/favorites`, POST `/user/favorites`                                                                                                                                                                                                              |

---

## Golden Test Samples

Sample responses captured in `docs/reference/_samples/tvdb/` for the provider's golden
tests (parsers in `_tvdb_parsers.py` are validated against them):

- `login.json` — `POST /login` response
- `search_series.json` — `GET /search?query=Breaking+Bad&type=series`
- `search_movie.json` — `GET /search?query=Fight+Club&type=movie`
- `series_extended.json` — `GET /series/81189/extended`
- `series_translation.json` — `GET /series/81189/translations/fra`
- `episodes_default.json` — `GET /series/81189/episodes/default?season=1`
- `episodes_translated.json` — `GET /series/81189/episodes/default/fra?season=1`
- `movie_extended.json` — `GET /movies/290/extended`
- `artwork_types.json` — `GET /artwork/types`
- `series_artworks.json` — `GET /series/81189/artworks`
- `search_empty.json` — Empty search result
