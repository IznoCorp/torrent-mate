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

### Response

```json
[
  {
    "title": "One.Piece.S01E01.1080p.Multi.MKV",
    "guid": "ckx9f3p5x0000abcd1234",
    "size": 2147483648,
    "pubDate": "2025-01-12T10:00:00.000Z",
    "link": "https://la-cale.space/torrents/ma-cargaison-abc123",
    "downloadLink": "https://la-cale.space/api/torrents/download/<infoHash>",
    "category": "Series TV",
    "seeders": 42,
    "leechers": 3,
    "infoHash": "abcdef..."
  }
]
```

### Field mapping → `TrackerResult`

| LaCale field   | `TrackerResult` field                              | Notes                                                                                                                     |
| -------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| —              | `provider`                                         | Constant `"lacale"`                                                                                                       |
| `guid`         | `tracker_id`                                       | Stable per torrent                                                                                                        |
| `title`        | `title`                                            | Used as input for `_parse_title()` derived fields                                                                         |
| `size`         | `size` (`ByteSize`)                                | Bytes (raw int) → wrap with `ByteSize.parse(int)`                                                                         |
| `seeders`      | `seeders`                                          | Direct int                                                                                                                |
| `leechers`     | `leechers`                                         | Direct int                                                                                                                |
| `category`     | `category`                                         | Display name (e.g. "Series TV") — slug is **not** in JSON                                                                 |
| `downloadLink` | `download_url`                                     | Direct                                                                                                                    |
| `infoHash`     | `info_hash`                                        | Lowercase hex                                                                                                             |
| `link`         | `source_url`                                       | Detail page URL                                                                                                           |
| `pubDate`      | `upload_date`                                      | ISO 8601 `YYYY-MM-DDThh:mm:ss.sssZ`, parse via `datetime.fromisoformat` (Python ≥3.11 strips `Z`)                         |
| _(derived)_    | `format`, `codec`, `source`, `resolution`, `audio` | Regex-extracted from `title` (see §Title parsing)                                                                         |
| _(absent)_     | `is_freeleech`                                     | LaCale signals freeleech via title prefix `[FreeLeech]` (per Phase 17.5 plan note); no JSON flag — see §Free/silver leech |
| _(absent)_     | `is_silverleech`                                   | Same — title-encoded                                                                                                      |

---

## Categories endpoint

```
GET /api/external/meta
X-Api-Key: <key>
```

Used by `LaCaleClient.get_categories()` to surface tracker taxonomy.

### Response shape

```json
{
  "categories": [
    {
      "id": "cat_video",
      "name": "Video",
      "slug": "video",
      "children": [
        { "id": "cat_films", "name": "Films", "slug": "films" },
        { "id": "cat_films_hd", "name": "Films HD", "slug": "films-hd" }
      ]
    }
  ],
  "tagGroups": [...],
  "ungroupedTags": []
}
```

### `get_categories()` contract (Phase 18)

Returns `dict[str, str]` — flat slug → display-name mapping, walking `categories` recursively (`children[]`):

```python
{"video": "Video", "films": "Films", "films-hd": "Films HD", ...}
```

`tagGroups` and `ungroupedTags` are upload-only and skipped here.

---

## Title parsing

LaCale stores most quality fields **inside the torrent title** rather than as JSON columns. A title like:

```
[FreeLeech] Inception.2010.2160p.UHD.BluRay.x265.HDR.TrueHD.7.1.Atmos-NCmt.mkv
```

must be regex-decomposed into the corresponding `TrackerResult` fields.

### Patterns (Phase 18 implementation)

| Field        | Regex (case-insensitive)                | Example match |
| ------------ | --------------------------------------- | ------------- | ------- | ------- | -------- | ------- | ---------- | ------------ | ------- | -------- |
| `resolution` | `\b(2160p                               | 1080p         | 720p    | 480p    | 4k       | uhd)\b` | `2160p`    |
| `codec`      | `\b(x265                                | x264          | h\.?265 | h\.?264 | hevc     | av1     | xvid       | divx)\b`     | `x265`  |
| `source`     | `\b(uhd\.bluray                         | bluray        | brrip   | web-?dl | webrip   | hdtv    | dvdrip)\b` | `UHD.BluRay` |
| `audio`      | `\b(truehd                              | atmos         | dts-hd  | dts     | ddp?5\.1 | aac     | ac3        | flac         | mp3)\b` | `TrueHD` |
| `format`     | file extension (`.mkv`, `.mp4`, `.avi`) | `mkv`         |

### Free/silver leech detection (title-encoded)

| Indicator               | Title token            | Maps to                                      |
| ----------------------- | ---------------------- | -------------------------------------------- |
| `is_freeleech = True`   | `[FreeLeech]` prefix   | drop token from title before further parsing |
| `is_silverleech = True` | `[SilverLeech]` prefix | drop token from title before further parsing |

Helper signature (Phase 18):

```python
def _parse_title(title: str) -> dict[str, str | bool | None]:
    """Extract resolution, codec, source, audio, format, and freeleech flags from title."""
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

1. **Title parsing strategy**: regex on `title` (no fallback to API fields — none are provided for codec/source/audio/resolution). Decision: **regex-based `_parse_title()`** as outlined above.
2. **Category normalization**: `get_categories()` returns flat `slug → name` map. Mapping `media_type` (`"movie"` / `"tv"`) → LaCale slug list happens at the registry level, not inside `LaCaleClient`. Search invocation passes the resolved slug(s) via the repeatable `cat` parameter.
3. **Default rate limit**: `rps=0.5`, `burst=2` (defensive). Override via `config/tracker.json5` `lacale.rate_limit` block.
4. **Sample fixtures — BLOCKED on real `LACALE_API_KEY`**: revisit attempt
   2026-05-07 with the BT tracker `LACALE_PASSKEY` rejected (HTTP 401 "Invalid
   API key") in both `X-Api-Key` header and `apikey=` query forms — the LaCale
   API key is **distinct** from the BitTorrent announce passkey. Phase 18 unit
   tests still rely on hand-crafted fixtures derived from the TorrentMaker
   docs (`docs/LaCale/api/`); endpoint shapes here are unverified against a
   live response. When a real `LACALE_API_KEY` is provided, capture
   `meta.json`, `search-inception.json`, `search-empty.json`, and an auth-error
   sample into `docs/reference/_samples/lacale/`, then re-validate the field
   mapping table against actual JSON.

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
