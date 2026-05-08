# TVDB API v4 — Reference

> TheTVDB API v4 — reference for the `api/metadata/tvdb.py` provider.
> Swagger docs: https://thetvdb.github.io/v4-api/
> Swagger spec: https://thetvdb.github.io/v4-api/swagger.yml
> GitHub: https://github.com/thetvdb/v4-api
> Current version: 4.7.10 (2024-05-11)
> Last updated: 2026-05-04

---

## Table of Contents

- [Authentication](#authentication)
- [Base URLs](#base-urls)
- [Response Format](#response-format)
- [Error Format](#error-format)
- [Rate Limiting](#rate-limiting)
- [Language & Translations](#language--translations)
- [Images & Artwork](#images--artwork)
- [Pagination](#pagination)
- [Season Types](#season-types)
- [Endpoints — Auth](#endpoints--auth)
- [Endpoints — Search](#endpoints--search)
- [Endpoints — Series](#endpoints--series)
- [Endpoints — Movies](#endpoints--movies)
- [Endpoints — Episodes](#endpoints--episodes)
- [Endpoints — Artwork](#endpoints--artwork)
- [Endpoints — Reference Data](#endpoints--reference-data)
- [Response Schemas](#response-schemas)
- [Provider Implementation Notes](#provider-implementation-notes)
- [Particularities](#particularities)

---

## Authentication

### Login Flow

TVDB v4 uses **JWT Bearer token** authentication. Unlike TMDB (direct API key), TVDB requires a one-time login to obtain a token.

```
POST /login
```

**Request**:

```json
{ "apikey": "<TVDB_API_KEY>" }
```

For "Negotiated Contract" keys (no PIN). If using a "User Subscription" key (requires $12/year subscription), add `"pin": "<subscriber_pin>"`.

**Response**:

```json
{
  "status": "success",
  "data": { "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." }
}
```

**Token TTL**: 30 days (confirmed from real login — `exp` claim decoded 2026-05-04 → 2026-06-04). **No runtime refresh needed.** The pipeline process never runs for 30 days. Re-login at client init is sufficient.

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

All subsequent requests include this header. If the token expires, the server returns HTTP 401 — the client re-authenticates via `/login`.

### Credential in the Pipeline

```
.env → TVDB_API_KEY=<your_api_key>
```

`PROVIDER_CREDS["tvdb"] = ["TVDB_API_KEY"]` in `api/_activation.py`.

### API Plans

| Revenue           | Cost         | Key Type            | PIN Required |
| ----------------- | ------------ | ------------------- | ------------ |
| < $50k/year       | Free         | Negotiated Contract | No           |
| $50k - $250k/year | $1,000/year  | Negotiated Contract | No           |
| $250k - $1M/year  | $10,000/year | Negotiated Contract | No           |
| > $1M/year        | Quote        | Negotiated Contract | No           |

Attribution to TheTVDB.com required unless exempted.

---

## Base URLs

| Purpose   | URL                                                      |
| --------- | -------------------------------------------------------- |
| API v4    | `https://api4.thetvdb.com/v4`                            |
| Swagger   | `https://thetvdb.github.io/v4-api/`                      |
| Image CDN | `https://artworks.thetvdb.com/` (full URLs in responses) |

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

Pagination adds a `links` object:

```json
{
  "status": "success",
  "data": [...],
  "links": {
    "prev": "...",
    "next": "...",
    "total_items": 62,
    "page_size": 100
  }
}
```

**Key difference from TMDB**: TVDB wraps ALL responses in `data`. The provider must unwrap `response["data"]` before passing to parsers. TMDB returns the raw object directly.

---

## Error Format

```json
{
  "status": "failure",
  "message": "InvalidAPIKey: apikey invalid",
  "data": null
}
```

**Key difference from TMDB**: TVDB uses `"status": "failure"` with a `message` string — no separate `status_code`/`status_message` fields. The HTTP status code reflects the error class.

`ApiError` mapping:

```python
ApiError(
    provider="tvdb",
    http_status=resp.status_code,
    provider_code=0,           # TVDB has no numeric error codes
    message=data.get("message", resp.reason),
)
```

---

## Rate Limiting

TVDB does **not** publish specific rate limits. No explicit thresholds in the Swagger spec.

**Strategy**:

- Retry on HTTP 429 with exponential backoff (standard tenacity behavior)
- Cache reference data (artwork types, genres, languages) aggressively
- Use `/updates` endpoint for bulk sync instead of polling individual records

`RateLimitPolicy(requests_per_second=20)` — conservative soft cap.

---

## Language & Translations

TVDB uses **3-character** language codes (`fra`, `eng`, `spa`), unlike TMDB's 2-char `fr-FR`.

### Language Mapping

The pipeline uses 2-char codes internally. A mapping is required:

```python
LANG_MAP = {
    "fr": "fra", "en": "eng", "es": "spa", "de": "deu",
    "it": "ita", "ja": "jpn", "ko": "kor", "pt": "por",
    "ru": "rus", "zh": "zho", "ar": "ara", "nl": "nld",
}
```

### Translation Fields

Entity objects contain inline translation arrays:

- `nameTranslations`: list of language codes where a name translation exists
- `overviewTranslations`: list of language codes where an overview translation exists

To get a translated name/overview, the provider fetches the entity translation endpoint:

```
GET /series/{id}/translations/{lang}
```

Returns `{"data": {"name": "...", "overview": "...", "language": "fra"}}`.

### Language Parameter

Search supports `language=eng` to filter results by original language (3-char code):

```
GET /search?query=Breaking+Bad&type=series&language=fra
```

---

## Images & Artwork

### Image URLs

TVDB returns **full URLs** in responses (`image` field). No base URL + size assembly needed (unlike TMDB).

```
https://artworks.thetvdb.com/banners/posters/81189-10.jpg
```

### Artwork Types (numeric IDs)

24 artwork types from `GET /artwork/types` (confirmed from live API):

| ID  | Name          | Pipeline Usage                        |
| --- | ------------- | ------------------------------------- |
| 1   | Banner        | Ignore                                |
| 2   | Poster        | → `ArtworkItem(type="poster")`        |
| 3   | Background    | → `ArtworkItem(type="backdrop")`      |
| 5   | Icon          | Ignore                                |
| 7   | Clear Logo    | → `ArtworkItem(type="landscape")`     |
| 15  | Season Poster | → `ArtworkItem(type="season_poster")` |

**Important**: Episode images may be **4:3 or 16:9** — no guarantee which. Some entities have a single artwork of a single type.

### Artwork Arrays

Entities (series, movies, seasons, episodes) include an `artworks` array directly in extended responses:

```json
{
  "artworks": [
    { "id": 123, "type": 2, "image": "https://artworks.thetvdb.com/..." },
    { "id": 124, "type": 3, "image": "https://artworks.thetvdb.com/..." }
  ]
}
```

The provider maps `type` numeric ID → `ArtworkItem.type` string.

---

## Pagination

Episodes are paginated at **100 per page**, 0-based:

```
GET /series/{id}/episodes/default?season=1&page=0
```

Response includes `links`:

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

Search results are NOT paginated — all results returned in a single response.

---

## Season Types

TVDB supports multiple episode ordering schemes via season types:

| Type       | Description                                   |
| ---------- | --------------------------------------------- |
| `default`  | Aired order (most common, pipeline uses this) |
| `official` | Official order                                |
| `dvd`      | DVD order                                     |
| `absolute` | Absolute numbering (anime-style)              |

Series object includes `defaultSeasonType` and `seasonTypes` array.

**Pipeline decision**: Always use `default` season type. The pipeline only accesses aired-order episodes.

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

**Parameters**:

| Param      | Type   | Required | Description                                      |
| ---------- | ------ | -------- | ------------------------------------------------ |
| `query`    | string | Yes      | Search term                                      |
| `type`     | string | No       | `series` or `movie`                              |
| `language` | string | No       | Filter by original language (3-char, e.g. `fra`) |

**Response**: `{"status": "success", "data": [...]}`

Each item: `tvdb_id`, `id` (UUID), `name`, `type`, `year`, `overview`, `image_url` (thumbnail), `translations` (dict), `remote_ids`, `primary_language`, `first_air_time`.

**Key difference**: Search results include `remote_ids` (IMDB, TMDB cross-references) directly — no need for a separate external IDs endpoint.

---

## Endpoints — Series

### Series Base

```
GET /series/{id}
```

Returns basic series record. Rarely used — pipeline typically uses `extended`.

### Series Extended

```
GET /series/{id}/extended
```

**Parameters**:

| Param   | Type | Description                            |
| ------- | ---- | -------------------------------------- |
| `short` | bool | Reduce payload size (omit some fields) |
| `meta` | string | No | `translations` or `episodes` — include extra data |

**Response**: Full series object. When `meta=episodes`, returns `episodes` array., `artworks`, `seasons`, `seasonTypes`, `trailers`, `characters`, `companies`, `genres`, `remoteIds`, `nameTranslations`, `overviewTranslations`, `score`, `averageRuntime`, `firstAired`, `lastAired`, `status`.

**Important**: The `episodes` array in the extended response contains ALL episodes across ALL seasons — not just one season. Use `GET /series/{id}/episodes/default` for per-season pagination.

### Series Translation

```
GET /series/{id}/translations/{lang}
```

Returns `{"name": "...", "overview": "...", "language": "fra"}`.

### Series Artworks (standalone)

```
GET /series/{id}/artworks
```

**Parameters**: `lang` (string, optional — filter by language, e.g. `fra`), `type` (int, optional — filter by artwork type ID, e.g. `2` for posters).

Returns the **full series object** including the `artworks` array filtered by the given criteria. Same as `/extended` but without `episodes`. For artwork-only needs, more efficient than `/extended`.

---

## Endpoints — Movies

### Movie Base

```
GET /movies/{id}
```

### Movie Extended

```
GET /movies/{id}/extended
```

**Parameters**: `short` (bool, optional), `meta` (string, optional: `translations`).

Returns full movie object: `runtime`, `score`, `remoteIds`, `genres`, `artworks`, `trailers`, `first_release` (note: `first_release`, not `release_date` — different field name from TMDB), `budget`, `boxOffice`, `characters`.

### Movie Translation

```
GET /movies/{id}/translations/{lang}
```

---

## Endpoints — Episodes

### Episodes — Default Season Order

```
GET /series/{id}/episodes/default
```

**Parameters**:

| Param    | Type | Required | Description                         |
| -------- | ---- | -------- | ----------------------------------- |
| `season` | int  | Yes      | Season number (1-indexed)           |
| `page`   | int  | No       | Page number (0-based, 100 per page) |

**Response**: `{"status": "success", "data": {"series": {...}, "episodes": [...]}}`

Episode fields: `id`, `number`, `name`, `runtime`, `aired`, `image`, `overview`, `seasonNumber`, `absoluteNumber`, `nameTranslations`, `overviewTranslations`, `isMovie`, `finaleType`.

### Episodes — Translated (per season)

```
GET /series/{id}/episodes/default/{lang}
```

Returns the full series object with translated episode names/overviews in the `episodes` array. More efficient than fetching individual episode translations.

---

## Endpoints — Artwork

### Artwork Types

```
GET /artwork/types
```

Returns 24 artwork type records: `id`, `name`, `slug`. Cacheable for days/weeks.

### Artwork by ID

```
GET /artwork/{id}
```

Rarely needed — artwork data is included in entity extended responses.

---

## Endpoints — Reference Data

| Endpoint           | Purpose                         | Cache        |
| ------------------ | ------------------------------- | ------------ |
| `/genres`          | Genre list                      | Weekly+      |
| `/languages`       | Available languages             | Weekly+      |
| `/countries`       | Available countries             | Weekly+      |
| `/content/ratings` | Content ratings                 | Weekly+      |
| `/series/statuses` | Series statuses                 | Weekly+      |
| `/movies/statuses` | Movie statuses                  | Weekly+      |
| `/updates`         | Changed records since timestamp | Do not cache |

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
  "translations": {"fra": "Breaking Bad", "eng": "Breaking Bad", ...},
  "remote_ids": [
    {"sourceId": 457, "id": "1396", "type": 2, "name": "TheMovieDB.com"},
    {"sourceId": 3, "id": "tt0903747", "type": 2, "name": "IMDB"}
  ],
  "primary_language": "eng",
  "first_air_time": "2008-01-20",
  "aliases": ["Breaking Bad: Ruptura Total"],
  "network": "AMC",
  "status": "Ended"
}
```

### Search Result (movie)

Same structure as series, but `type: "movie"` and `first_release` instead of `first_air_time`.

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

---

## Provider Implementation Notes

### Bootstrap Flow

```python
# Phase 1: Bootstrap — one-shot HttpTransport with NoAuth → login
bootstrap_policy = TransportPolicy(
    provider_name="TVDB-login",
    base_url="https://api4.thetvdb.com/v4",
    auth=NoAuth(),
)
with HttpTransport(bootstrap_policy) as transport:
    login_resp = transport.post("/login", data={"apikey": api_key})
token = login_resp["data"]["token"]

# Phase 2: Main client — BearerAuth with JWT
policy = TVDBClient.policy(token)
transport = HttpTransport(policy)
client = TVDBClient(transport=transport, language="fra")
```

### TransportPolicy

```python
@classmethod
def policy(cls, jwt_token: str, *, circuit: CircuitPolicy | None = None) -> TransportPolicy:
    return TransportPolicy(
        provider_name="TVDB",
        base_url="https://api4.thetvdb.com/v4",
        auth=BearerAuth(jwt_token),
        timeout_seconds=15.0,
        retry=RetryPolicy(max_attempts=4),
        circuit=circuit or CircuitPolicy(failure_threshold=5, cooldown_seconds=300),
        rate_limit=RateLimitPolicy(requests_per_second=20),
    )
```

### What TVDBClient MUST Implement

| Method                                       | Endpoint                                     | Returns                     |
| -------------------------------------------- | -------------------------------------------- | --------------------------- |
| `search(title, year, media_type)`            | `GET /search`                                | `list[SearchResult]`        |
| `get_details(media_id, media_type)`          | `GET /{media_type}/{id}/extended`            | `MediaDetails`              |
| `get_artwork_urls(media_id, media_type)`     | From extended response                       | `list[ArtworkItem]`         |
| `get_season(tv_id, season)`                  | `GET /series/{id}/episodes/default?season=N` | `SeasonDetails`             |
| `get_keywords(media_id, media_type)`         | Not supported by TVDB v4                     | `raise NotImplementedError` |
| `get_videos(media_id, media_type, language)` | From extended response `trailers`            | `list[Video]`               |
| `get_notations(media_id, media_type)`        | Not supported (score is popularity rank)     | `raise NotImplementedError` |

### Response Unwrapping

Every TVDB response must be unwrapped:

```python
raw = self._transport.get(path, params=params)
data = raw["data"]  # TVDB wraps everything in data envelope
```

### Image Handling

TVDB returns full image URLs. No assembly needed (unlike TMDB's `base_url + size + path`):

```python
# TVDB: direct
image_url = artwork["image"]

# TMDB: assembly
image_url = f"{IMAGE_BASE}w780{path}"
```

---

## Particularities

### 1. TVDB wraps ALL responses in `data` envelope

Every endpoint wraps the actual payload in `{"status": "success", "data": ...}`. The provider MUST unwrap `response["data"]` before passing to parsers. TMDB returns the raw object directly.

**Decision**: Handle — unwrap in the provider, pass unwrapped data to parsers.

### 2. Language codes are 3-character

TVDB uses `fra`, `eng`, `spa` — NOT `fr-FR`, `en-US` like TMDB. The pipeline uses 2-char codes internally.

**Decision**: Handle — migrate `_TVDB_LANG_MAP` from current `tvdb_client.py`. Map 2-char pipeline codes → 3-char TVDB codes before each API call.

### 3. Token TTL = 30 days — no runtime refresh

JWT `exp` claim confirmed: 30 days from login. No `refresh_token` endpoint exists. Re-authenticate via `/login` when token expires (HTTP 401).

**Decision**: Handle — bootstrap login at `TVDBClient.__init__`. If 401 received, re-login and retry once. The pipeline process never runs 30 days, so this is effectively init-only.

### 4. Artwork types are numeric IDs

TVDB uses integer type IDs (2=Poster, 3=Background, 7=Clear Logo), not string names like TMDB.

**Decision**: Handle — map numeric IDs to `ArtworkItem.type` strings using a hardcoded mapping (confirmed from `/artwork/types` live call). Unknown IDs → `"backdrop"` as fallback.

### 5. Season types: `default` is the pipeline's choice

Multiple episode orderings exist (`default`, `official`, `dvd`, `absolute`). The pipeline always uses aired order.

**Decision**: Handle — always call `/series/{id}/episodes/default?season=N`. No configuration needed.

### 6. `score` is an integer popularity rank, NOT a rating

TVDB `score` is an arbitrary integer for relative popularity (e.g., Breaking Bad = 3434). It is NOT comparable across entity types (TVDB docs explicitly warn against this).

**Decision**: Ignore for `MediaDetails.rating` — leave `rating=None` for TVDB. Notations and ratings are TMDB/OMDB/Trakt territory.

### 7. Episodes include runtime per episode

TVDB episode objects have `runtime` (int, minutes) directly. Unlike TMDB which puts `episode_run_time` as an array on the series object.

**Decision**: Handle — `EpisodeInfo.runtime_minutes = ep["runtime"] or None`.

### 8. `first_release` (not `release_date`)

TVDB movie objects use `first_release` for the release date (confirmed from live API). TMDB uses `release_date`.

**Decision**: Handle — parser checks both `first_release` (TVDB-style) and `release_date` (TMDB-style for consistency).

### 9. Episodes paginated (100/page), search is NOT

Episodes use 0-based pagination with `links.next` for iteration. Search returns all results in a single response.

**Decision**: Handle — for series with >100 episodes per season (anime, long-running shows), iterate pages until `links.next` is null.

### 10. `remoteIds` included in search results

TVDB search results include `remote_ids` array with TMDB/IMDB cross-references. This allows matching against TMDB data without an extra API call.

**Decision**: Handle — expose via `SearchResult` or `MediaDetails.external_ids`. The existing pipeline uses this to cross-reference with TMDB.

### 11. `get_notations` and `get_keywords` are NOT supported

TVDB has no keywords endpoint and no rating/notation system beyond the popularity `score`.

**Decision**: `get_keywords()` and `get_notations()` → `raise NotImplementedError`. The pipeline falls back to TMDB for these capabilities.

### 12. Series `extended` includes ALL episodes

The `/series/{id}/extended` response includes an `episodes` array with ALL episodes across ALL seasons. For large series, this is inefficient.

**Decision**: Use `/series/{id}/episodes/default?season=N` for per-season fetching. Use `/extended` only when the full series overview (without episode details) is needed.

---

## Golden Test Samples

Sample responses captured in `docs/reference/_samples/tvdb/` for Phase 7 golden tests:

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
