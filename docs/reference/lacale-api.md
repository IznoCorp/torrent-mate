# LaCale API Reference

Tracker: **LaCale** (private tracker, French/international content).
Base URL: `https://la-cale.space`
Auth: header `X-Api-Key: <key>` (recommended) or query `?apikey=<key>` (fallback).

Source material: TorrentMaker `docs/LaCale/api/` (`INDEX.md`, `search.md`, `meta.md`).
Phase 18 will implement `personalscraper/api/tracker/lacale.py` consuming this reference.

---

## Scope

`api-unify` Phase 18 only consumes **search** + **meta**. Upload (`upload.md`) is out of scope (auto-download / upload automation deferred to ROADMAP).

| Capability    | Endpoint                          | Used by                                     |
| ------------- | --------------------------------- | ------------------------------------------- |
| Search        | `GET /api/external`               | `LaCaleClient.search()` → `TrackerResult[]` |
| Categories    | `GET /api/external/meta`          | `LaCaleClient.get_categories()` → `dict`    |
| Torznab (n/a) | `GET /api/external/torznab/api`   | Not used — JSON endpoint preferred          |
| RSS (n/a)     | `GET /api/external/rss`           | Not used                                    |
| Download      | `GET /api/torrents/download/<ih>` | Out of scope — exposed via `download_url`   |

---

## Auth

| Mode          | Detail                                       |
| ------------- | -------------------------------------------- |
| Method        | API key, **header** `X-Api-Key: <key>`       |
| Fallback      | Query `?apikey=<key>` accepted               |
| Required cred | `LACALE_API_KEY` (single string, opaque)     |
| Format        | Opaque API key — bearer-style not required   |
| AuthMode      | `AuthMode.API_KEY_HEADER` (`api/_contracts`) |

Header path is preferred (URL strings are logged — query path leaks the key into HTTP access logs and shell history).

---

## Search endpoint

```
GET /api/external
X-Api-Key: <key>
```

### Parameters

| Param    | Required             | Description                                                            |
| -------- | -------------------- | ---------------------------------------------------------------------- |
| `apikey` | yes (or `X-Api-Key`) | API key                                                                |
| `q`      | no                   | Query string (max 200 chars; normalized: lowercased, accents stripped) |
| `tmdbId` | no                   | Exact TMDB ID match (alias: `tmdbid`)                                  |
| `cat`    | no (repeatable)      | Exact category slug (e.g. `films-hd`). Repeat for multi-filter         |

### Limits

- 20 results max, sorted by `pubDate` descending.
- Only approved torrents returned.
- Server-side cache: ~30s per (key, query, category) tuple.

### Response (captured live, see `_samples/lacale/search-inception.json`)

```json
[
  {
    "title": "Inception.2010.MULTi.VFF.1080p.HDLight.DTS.5.1.x264-PATOMiEL",
    "guid": "d7hai97v871c73dbcaq0",
    "size": 7549978849,
    "pubDate": "2026-04-17T21:41:56.126Z",
    "link": "https://la-cale.space/torrents/dhvr9hpmlflp",
    "downloadLink": "https://la-cale.space/api/download/c1a7d929f62919b72f58f08da62fc3e0e5ceb820?token=REDACTED_JWT",
    "category": "Films",
    "seeders": 0,
    "leechers": 0,
    "infoHash": "c1a7d929f62919b72f58f08da62fc3e0e5ceb820"
  }
]
```

#### Reality vs initial spec (captured 2026-05-07)

| Initial assumption                                       | Reality                                                                                                                                                                                                    |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `category` is the slug ("films-hd")                      | `category` is the **human label** ("Films", "Musique", "Séries TV"). The slug is **not** in search responses                                                                                               |
| `downloadLink` is `/api/torrents/download/<hash>`        | `downloadLink` is `/api/download/<infoHash>?token=<JWT>`. Token is a per-request signed JWT (sensitive)                                                                                                    |
| Freeleech encoded as `[FreeLeech]` title prefix          | **No** `[FreeLeech]` / `[SilverLeech]` prefixes observed in any captured sample. No JSON flag either. The title-prefix theory from TorrentMaker docs does not apply here — Phase 18 should drop this regex |
| `leechers` derived from response                         | `leechers` is a direct int field in JSON — no derivation needed                                                                                                                                            |
| `pubDate` ISO 8601 (date precision)                      | ISO 8601 with **milliseconds**: `2026-04-17T21:41:56.126Z`. Python `datetime.fromisoformat` (3.11+) handles `Z` only after manual replace; safer to swap `Z` → `+00:00` first                              |
| `guid` is the torrent slug or infohash                   | `guid` is a short opaque ID (~20 chars, sometimes a CUID like `cmjuy63yh002t01mvbcjehgax`). Use it as `tracker_id` only — do not mistake for `infoHash`                                                    |
| `meta` returns `{categories, tagGroups, ungroupedTags}`  | `/api/external/meta` returns **only** `{categories: [...]}`. No `tagGroups`, no `ungroupedTags` (those are upload-side concepts). Each category has `id`, `name`, `slug`, `icon`, `parentId`, `children`   |
| Auth error returns `{"error": "..."}` body with HTTP 401 | Confirmed exactly: `HTTP 401` + `{"error":"Invalid API key"}` (see `_samples/lacale/error-auth.json`)                                                                                                      |

### Field mapping → `TrackerResult`

| LaCale field   | `TrackerResult` field                              | Notes                                                                                                           |
| -------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| —              | `provider`                                         | Constant `"lacale"`                                                                                             |
| `guid`         | `tracker_id`                                       | Short opaque ID (~20 chars), stable per torrent. **Not** the infohash                                           |
| `title`        | `title`                                            | Used as input for `_parse_title()` derived fields                                                               |
| `size`         | `size` (`ByteSize`)                                | Bytes (raw int) → wrap with `ByteSize.parse(int)`                                                               |
| `seeders`      | `seeders`                                          | Direct int                                                                                                      |
| `leechers`     | `leechers`                                         | Direct int (live-confirmed; **not** title-derived)                                                              |
| `category`     | `category`                                         | Human label (e.g. `"Films"`, `"Musique"`). **Not** a slug — slug is meta-only                                   |
| `downloadLink` | `download_url`                                     | `/api/download/<infoHash>?token=<JWT>`. Treat token as sensitive (redact in logs/samples)                       |
| `infoHash`     | `info_hash`                                        | Lowercase 40-char hex                                                                                           |
| `link`         | `source_url`                                       | `https://la-cale.space/torrents/<short-id>`                                                                     |
| `pubDate`      | `upload_date`                                      | ISO 8601 with ms (`2026-04-17T21:41:56.126Z`). Replace trailing `Z` with `+00:00` then `datetime.fromisoformat` |
| _(derived)_    | `format`, `codec`, `source`, `resolution`, `audio` | Regex-extracted from `title`                                                                                    |
| _(absent)_     | `is_freeleech`                                     | **No signal observed** — neither title prefix nor JSON flag. Always `False` until LaCale exposes one            |
| _(absent)_     | `is_silverleech`                                   | Same — always `False`                                                                                           |

---

## Categories endpoint

```
GET /api/external/meta
X-Api-Key: <key>
```

Used by `LaCaleClient.get_categories()` to surface tracker taxonomy.

### Response shape (captured live, see `_samples/lacale/meta.json`)

```json
{
  "categories": [
    {
      "id": "cmjudvb9d0000oqrult6eafdv",
      "name": "Vidéo",
      "slug": "video",
      "icon": "Film",
      "parentId": null,
      "children": [
        {
          "id": "cmjoyv2cd00027eryreyk39gz",
          "name": "Films",
          "slug": "films",
          "icon": null,
          "parentId": "cmjudvb9d0000oqrult6eafdv",
          "children": null
        },
        {
          "id": "...",
          "name": "Spectacles & Concerts",
          "slug": "spectacles-concerts",
          "...": "..."
        },
        { "id": "...", "name": "Sports", "slug": "sports", "...": "..." },
        { "id": "...", "name": "Séries TV", "slug": "series", "...": "..." }
      ]
    },
    { "id": "...", "name": "Audio", "slug": "audio", "...": "..." },
    { "id": "...", "name": "Autres", "slug": "autres", "...": "..." }
  ]
}
```

`children` is `null` when a node has no sub-categories. Each node carries
`id` (CUID-ish opaque), `name` (human label), `slug` (URL-safe), `icon`
(Lucide icon name or `null`), `parentId` (top-level when `null`), `children`
(array or `null`).

### `get_categories()` contract (Phase 18)

Returns `dict[str, str]` — flat **slug → human label** mapping, walking
`categories` recursively (`children` array, ignoring `null`):

```python
{"video": "Vidéo", "films": "Films", "series": "Séries TV", "music": "Musique", ...}
```

---

## Title parsing

LaCale exposes quality markers (resolution, codec, source, audio) **inside
the torrent title** rather than as JSON columns. A captured title like:

```
Inception.2010.MULTi.VFF.DV.HDR.2160p.4KLight.DTS-HD.MA.5.1.H265-telemO
```

is regex-decomposed into the corresponding `TrackerResult` fields.

### Patterns

| Field        | Pattern (case-insensitive)                                         | Example match                    |
| ------------ | ------------------------------------------------------------------ | -------------------------------- |
| `resolution` | `\b(2160p\|1080p\|720p\|480p\|4k\|uhd)\b`                          | `2160p`                          |
| `codec`      | `\b(x265\|x264\|h\.?265\|h\.?264\|hevc\|av1\|xvid\|divx)\b`        | `x265`                           |
| `source`     | `\b(uhd\.bluray\|bluray\|brrip\|web-?dl\|webrip\|hdtv\|dvdrip)\b`  | `BluRay`                         |
| `audio`      | `\b(truehd\|atmos\|dts-?hd\|dts\|ddp?5\.1\|aac\|ac3\|flac\|mp3)\b` | `DTS-HD`                         |
| `format`     | trailing extension `\.(mkv\|mp4\|avi\|m4v\|wmv\|mov)$`             | (empty if no extension in title) |

### Free / silver leech

**No signal observed** in any captured sample — neither title prefix nor JSON
field. `is_freeleech` and `is_silverleech` are always `False` for LaCale.
The title-prefix theory inherited from TorrentMaker docs (`[FreeLeech]` /
`[SilverLeech]`) is not realized by this tracker; if the API ever exposes
freeleech flags, revisit by capturing fresh samples.

Helper signature:

```python
def _parse_title(title: str) -> dict[str, str | None]:
    """Extract resolution, codec, source, audio, format from title.

    Returns dict with the five quality keys; values are None when no pattern
    matches. is_freeleech / is_silverleech are NOT included — they have no
    signal in LaCale responses.
    """
```

---

## Rate limits & abuse policy

LaCale API documentation does not publish hard rate limits, but server-side caching (30s) implies the tracker tolerates polling. Defensive policy:

| Setting             | Value              | Rationale                                                        |
| ------------------- | ------------------ | ---------------------------------------------------------------- |
| `rps`               | `0.5` (1 req / 2s) | Below cache TTL — friendly to a tracker without published limits |
| `burst`             | `2`                | Allow short bursts for parallel category enumeration             |
| `retry_max`         | `2`                | Same as TMDB/TVDB — transient failures only                      |
| `circuit_threshold` | `3`                | Open circuit after 3 consecutive 5xx                             |

Tunable via `config/tracker.json5` per-provider override.

---

## Errors

LaCale returns standard HTTP status codes:

| Status        | Cause                    | Behavior                                |
| ------------- | ------------------------ | --------------------------------------- |
| `200`         | Success                  | Parse + return                          |
| `401` / `403` | Bad/missing API key      | Raise `ApiError` (auth) — no retry      |
| `429`         | Rate limit (if enforced) | Tenacity retry with backoff             |
| `5xx`         | Server error             | Tenacity retry; circuit opens at 3 hits |
| `200` `[]`    | Empty result             | Return empty list (not an error)        |

---

## Open decisions (Phase 17.6 user checkpoint)

The following defaults are baked into this doc and will drive Phase 18; flagged as **DECISION** for explicit user confirmation when Phase 18 starts. If left unchallenged at Phase 18 start, defaults stand.

1. **Title parsing strategy**: regex on `title` (no fallback to API fields — none are provided for codec/source/audio/resolution). Decision: **regex-based `_parse_title()`** as outlined above; freeleech/silverleech detection **dropped** (no signal in real responses).
2. **Category normalization**: `get_categories()` returns flat `slug → human label` map (e.g. `{"films": "Films", "music": "Musique", ...}`). Mapping `media_type` (`"movie"` / `"tv"`) → LaCale slug list happens at the registry level, not inside `LaCaleClient`. Search invocation passes the resolved slug(s) via the repeatable `cat` parameter.
3. **Default rate limit**: `rps=0.5`, `burst=2` (defensive). Override via `config/tracker.json5` `lacale.rate_limit` block.
4. **Sample fixtures**: live samples captured 2026-05-07 in `docs/reference/_samples/lacale/`:
   - `meta.json` — full categories tree (Vidéo/Audio/Autres top-level + nested)
   - `search-inception.json` — `?q=Inception` (14 items mixing Films + Musique)
   - `search-tmdb-inception.json` — `?tmdbId=27205` (Inception by TMDB id)
   - `search-empty.json` — empty result `[]`
   - `error-auth.json` — HTTP 401 + `{"error":"Invalid API key"}`
     API key + per-request JWT tokens redacted (`REDACTED_JWT` placeholder).

---

## Phase 18 implementation plan summary

```python
# personalscraper/api/tracker/lacale.py
class LaCaleClient:
    provider_name: str = "lacale"
    REQUIRED_CREDS: ClassVar[list[str]] = ["LACALE_API_KEY"]

    def __init__(self, transport: HttpTransport, api_key: str) -> None: ...

    def search(self, query: str, media_type: str = "movie",
               year: int | None = None) -> list[TrackerResult]: ...

    def get_categories(self) -> dict[str, str]: ...

    def _parse_title(self, title: str) -> dict[str, str | bool | None]: ...
```

LOC budget: ≤ 350 LOC (well under the 800 soft cap). If extraction needed, split into `_parsers.py` (title regex) + `lacale.py` (HTTP).
