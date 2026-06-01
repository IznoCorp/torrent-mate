# C411 API Reference

Tracker: **C411** (private French tracker, multi-content).
Base URL: `https://c411.org`
Source material: TorrentMaker `docs/C411/api/` (`INDEX.md`, `Reference.md`, `ArrStack.md`, `upload.md`).
Phase 20 will implement `personalscraper/api/tracker/c411.py` consuming this reference.

---

## Scope

`api-unify` Phase 20 only consumes the **Torznab/Newznab search** endpoint.
Upload (`upload.md`) is out of scope (auto-download / upload deferred to ROADMAP).

| Capability | Endpoint                      | Used by                                       |
| ---------- | ----------------------------- | --------------------------------------------- |
| Search     | `GET /api?t=search` (Torznab) | `C411Client.search()` → `list[TrackerResult]` |
| Categories | `GET /api?t=caps` (Torznab)   | `C411Client.get_categories()` → `dict`        |
| RSS sync   | `GET /api?t=tvsearch` etc.    | Not used (search covers it)                   |
| Upload     | `POST /api/torrents`          | Out of scope                                  |

---

## API style

**Torznab/Newznab** (XML/RSS) — same protocol Prowlarr/Sonarr/Radarr/Jackett speak.

| Tooling stack          | URL                    | Notes                                                      |
| ---------------------- | ---------------------- | ---------------------------------------------------------- |
| Prowlarr/Sonarr/Radarr | `https://c411.org`     | Indexer URL **without** `/api` — they append it themselves |
| Jackett                | `https://c411.org/api` | URL **with** `/api`                                        |

For our `HttpTransport`-based client, we use the explicit endpoint path
(`/api?t=...`) because we drive it directly, not through Prowlarr/Jackett.

---

## Auth

| Mode             | Detail                                                               |
| ---------------- | -------------------------------------------------------------------- |
| Method (Torznab) | API key as query parameter `apikey=<key>`                            |
| Method (upload)  | `Authorization: Bearer <key>` header (out of scope)                  |
| Required cred    | `C411_API_KEY` (single string, opaque)                               |
| AuthMode         | `AuthMode.API_KEY_QUERY` for the Torznab path (matches OMDB pattern) |

The Torznab spec mandates `apikey` in query parameters — it is not a header
parameter for indexer APIs. This is the only auth path we use.

---

## Search endpoint (Torznab)

```
GET /api?t=search&q=<query>&apikey=<key>
GET /api?t=movie&q=<query>&apikey=<key>          (movie scope)
GET /api?t=tvsearch&q=<query>&apikey=<key>       (tv scope)
```

### Parameters

| Param    | Required | Description                                                    |
| -------- | -------- | -------------------------------------------------------------- |
| `apikey` | yes      | API key                                                        |
| `t`      | yes      | One of: `caps`, `search`, `movie`, `tvsearch`, `music`, `book` |
| `q`      | no       | Query string                                                   |
| `cat`    | no       | Newznab category numeric ID (comma-separated for multi)        |
| `imdbid` | no       | IMDb ID (without "tt" prefix)                                  |
| `tmdbid` | no       | TMDB ID                                                        |
| `tvdbid` | no       | TVDB ID                                                        |
| `season` | no       | Season number (`tvsearch`)                                     |
| `ep`     | no       | Episode number (`tvsearch`)                                    |
| `limit`  | no       | Max results                                                    |
| `offset` | no       | Pagination offset                                              |

> **Finality note — no `cat` narrowing (live caps confirmed).** C411's Torznab
> `caps` does **not** advertise `cat` in `supportedParams` for any of
> `search` / `movie-search` / `tv-search`, so the indexer does not honor a `cat`
> filter. Media-type routing is done at the **endpoint** level — `t=movie` for
> movies, `t=tvsearch` for TV — never via `cat`. `api/tracker/c411.py` therefore
> never sends `cat`; it picks the endpoint from `media_type` and falls back to
> `t=search` for everything else. ID-based narrowing (`imdbid` / `tmdbid` /
> `tvdbid`) remains available on the movie/tv endpoints. This is settled — no
> behavioral change is pending.

### Limits

- 5 min server-side cache (per `ArrStack.md`).
- ETag support for conditional requests.
- Recommended RSS sync interval: 15–60 min (informative — search calls are not RSS).

### Response — RSS-style XML (captured live, see `_samples/c411/search-inception.xml`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <title>Torrent C411</title>
    <description>Private Torrent Tracker - RSS Feed</description>
    <link>https://c411.org</link>
    <language>fr-fr</language>
    <lastBuildDate>Thu, 07 May 2026 14:43:49 GMT</lastBuildDate>
    <item>
      <title>Inception.2010.MULTi.VFF.2160p.BluRay.4KLight.HDR.10bit.DTS.5.1.x265-QTZ</title>
      <guid>b08b70d0855318efa71aeccce0ae42b3e4493113</guid>
      <link>https://c411.org/torrents/b08b70d0855318efa71aeccce0ae42b3e4493113</link>
      <comments>https://c411.org/torrents/b08b70d0855318efa71aeccce0ae42b3e4493113</comments>
      <pubDate>Tue, 13 Jan 2026 13:35:54 +0000</pubDate>
      <size>7396633907</size>
      <description></description>
      <enclosure url="https://c411.org/api?t=get&amp;id=...&amp;apikey=REDACTED"
                 length="7396633907" type="application/x-bittorrent" />
      <torznab:attr name="category" value="2030" />
      <torznab:attr name="size" value="7396633907" />
      <torznab:attr name="seeders" value="141" />
      <torznab:attr name="peers" value="141" />
      <torznab:attr name="grabs" value="1" />
      <torznab:attr name="infohash" value="b08b70d0855318efa71aeccce0ae42b3e4493113" />
      <torznab:attr name="imdbid" value="tt1375666" />
      <torznab:attr name="tmdbid" value="27205" />
      <torznab:attr name="downloadvolumefactor" value="1" />
      <torznab:attr name="uploadvolumefactor" value="1" />
    </item>
  </channel>
</rss>
```

#### Reality vs initial spec (captured 2026-05-07)

| Initial assumption                                | Reality                                                                                                                                                              |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `<guid>` is the torrent detail URL                | `<guid>` is the **infohash** (40-char hex). Same value also in `torznab:attr name="infohash"`                                                                        |
| `<category>` element on each item                 | **No** `<category>` element on items — only `torznab:attr name="category"`                                                                                           |
| Item has only `enclosure[@length]`                | Item has both `<size>` element (top-level) **and** `enclosure[@length]` (and `torznab:attr[size]`) — three duplicates                                                |
| Empty result is `<channel/>` empty                | Empty result is `<channel>` containing only metadata (`title`, `description`, `link`, `language`, `lastBuildDate`) — no `<item>` elements                            |
| Categories `name` field is "Movies" / "TV"        | `category[@name]` is the Newznab class label ("Movies", "TV", "Console" …); the human label is in `category[@description]` (e.g. "Films & Vidéos"). Same for subcats |
| `enclosure[@url]` is a clean download URL         | URL contains the apikey inline (`?t=get&id=...&apikey=...`). **Sensitive** — must be redacted in logs and samples                                                    |
| `peers = seeders + leechers`                      | In samples, `peers == seeders` always when there are no leechers. Treat `leechers = max(0, peers - seeders)`                                                         |
| Search response uses `<error>` body for auth fail | Auth failure returns **HTTP 401** with body `<error code="100" description="Invalid API Key"/>` (see `_samples/c411/error-auth.xml`)                                 |

#### Notes

- `torznab:attr` repeated elements carry typed metadata. With `xmltodict`,
  repeated `<torznab:attr>` becomes a list of dicts each with `@name` and `@value`.
  When only one attr is present (rare), it is a single dict — clients must coerce.
- `enclosure` carries the download URL and total size — **but the URL contains
  the apikey** as a query parameter. Treat it as sensitive (redact before logging).
- `seeders` and `peers` come via `torznab:attr`. `leechers` is derived: `max(0, peers - seeders)`.
- `downloadvolumefactor=0` ⇒ **freeleech**. `downloadvolumefactor=0.5` ⇒ silver-leech (partial).
  `uploadvolumefactor=2` ⇒ double upload bonus (informative, not stored on `TrackerResult`).
- C411 also surfaces `imdbid` and `tmdbid` as `torznab:attr` — useful for cross-referencing
  with metadata providers, but `TrackerResult` has no field for these (extension deferred).

### Field mapping → `TrackerResult`

| C411 / Torznab field                         | `TrackerResult` field                              | Notes                                                                                                        |
| -------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| —                                            | `provider`                                         | Constant `"c411"`                                                                                            |
| `<guid>`                                     | `tracker_id`                                       | **40-char infohash** (confirmed live). Equal to `torznab:attr[infohash]` and to the path segment in `<link>` |
| `<title>`                                    | `title`                                            | Used as input for `_parse_title()` (shared helper)                                                           |
| `enclosure[@length]` or `torznab:attr[size]` | `size` (`ByteSize`)                                | Bytes (string in XML) → `ByteSize.parse(int(value))`                                                         |
| `torznab:attr[seeders]`                      | `seeders`                                          | Direct int                                                                                                   |
| `max(0, peers - seeders)`                    | `leechers`                                         | C411 emits `peers == seeders` when no leechers; clamp to 0                                                   |
| `torznab:attr[category]`                     | `category`                                         | Newznab numeric ID — keep as-is (e.g. `"2030"`). No item-level `<category>` element exists                   |
| `enclosure[@url]` or `<link>`                | `download_url`                                     | Direct                                                                                                       |
| `torznab:attr[infohash]`                     | `info_hash`                                        | Lowercase hex                                                                                                |
| `<comments>` or `<guid>`                     | `source_url`                                       | Detail page URL (prefer `comments` when present)                                                             |
| `<pubDate>`                                  | `upload_date`                                      | RFC 2822 (`Sun, 12 Jan 2025 10:00:00 +0000`); parse with `email.utils.parsedate_to_datetime`                 |
| `torznab:attr[downloadvolumefactor]`         | `is_freeleech`                                     | `True` if `value == "0"`                                                                                     |
| `torznab:attr[downloadvolumefactor]`         | `is_silverleech`                                   | `True` if `value == "0.5"`                                                                                   |
| _(derived from title)_                       | `format`, `codec`, `source`, `resolution`, `audio` | Reuse LaCale's `_parse_title` (titles encode same fields)                                                    |

---

## Categories endpoint (Torznab caps)

```
GET /api?t=caps&apikey=<key>
```

### Response shape (captured live, see `_samples/c411/caps.xml`)

```xml
<caps>
  <server version="1.0" title="Torrent C411" strapline="Private Torrent Tracker"
          email="" url="https://c411.org" />
  <limits max="100" default="25" />
  <retention days="3650" />
  <registration available="no" open="no" />
  <searching>
    <search available="yes" supportedParams="q" />
    <tv-search available="yes" supportedParams="q,season,ep,tmdbid,imdbid" />
    <movie-search available="yes" supportedParams="q,imdbid,tmdbid" />
    <audio-search available="yes" supportedParams="q" />
    <book-search available="yes" supportedParams="q" />
  </searching>
  <categories>
    <category id="2000" name="Movies" description="Films &amp; Vidéos">
      <subcat id="2060" name="Movies/Anime" description="Animation" />
      <subcat id="5070" name="TV/Anime" description="Animation Série" />
      <subcat id="2030" name="Movies/Foreign" description="Film" />
      <subcat id="5000" name="TV" description="Série TV" />
      <!-- … 12 subcats total under id=2000 (see sample file) … -->
    </category>
    <category id="7000" name="Books" description="Ebook">…</category>
    <category id="3000" name="Audio" description="Audio">…</category>
    <category id="4000" name="PC" description="Applications">…</category>
    <category id="1000" name="Console" description="Jeux Vidéo">…</category>
    <category id="6000" name="XXX" description="XXX">…</category>
    <!-- … and Emulation, GPS, Nulled, "Imprimante 3D" -->
  </categories>
  <tags>
    <tag name="freeleech" description="Freeleech torrents" />
  </tags>
</caps>
```

#### Reality vs initial spec (captured 2026-05-07)

| Initial assumption                         | Reality                                                                                                                                                                                                                                                                                   |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Searching `supportedParams` includes `cat` | C411 caps **does NOT advertise `cat`** for any of `search`/`movie-search`/`tv-search`. Category narrowing is not honored — Phase 20 must not pass `cat`. ID-based narrowing uses `imdbid`/`tmdbid` (and `tvdbid` for tv-search) only                                                      |
| `category[@name]` is the human label       | `category[@name]` is the Newznab class label ("Movies", "TV", "Console", "PC", "Books", "Audio", "XXX", "Other/Misc"). The human label is in `category[@description]`                                                                                                                     |
| Subcat IDs are unique per parent           | Many subcats share a Newznab `id` across categories (e.g. multiple `id="4050"`, multiple `id="3030"`) because Newznab IDs are a fixed taxonomy and several native C411 subcats map to the same Newznab class. Treat the `(parent, description)` pair as the canonical key, not `id` alone |
| One server-side limit field                | `<limits max="100" default="25" />` — pagination caps for `limit` query param. Retention is 3650 days                                                                                                                                                                                     |
| No tags surface                            | `<tags><tag name="freeleech"/></tags>` — a top-level tag taxonomy. Currently only `freeleech`. Items don't carry tags directly in samples — only via `downloadvolumefactor`                                                                                                               |

### Newznab category map (per `ArrStack.md`)

| Newznab ID | Category       | Internal `media_type` mapping |
| ---------- | -------------- | ----------------------------- |
| 2000       | Films          | `movie`                       |
| 2060       | Anime (Films)  | `movie`                       |
| 2070       | Documentaires  | `movie`                       |
| 5000       | Series TV      | `tv`                          |
| 5070       | Anime (Series) | `tv`                          |
| 3010       | Musique        | (not mapped — future)         |
| 3030       | Livres Audio   | (not mapped — future)         |
| 7020       | eBooks         | (not mapped — future)         |
| 7030       | Comics/Manga   | (not mapped — future)         |
| 4000       | Applications   | (not mapped)                  |
| 4050       | Jeux PC        | (not mapped)                  |

`get_categories()` flattens the caps tree to `id (str) → name (str)` (numeric IDs
preserved as strings for consistency with the LaCale shape).

---

## Native categories vs Torznab

C411's native upload API uses different category IDs (`Reference.md`: 1=Films & Videos,
2=Ebook, 3=Audio…) than the Torznab IDs (2000=Movies, 5000=TV). For Phase 20 search
we use **only the Torznab IDs** — no need to thread native upload categories through
search code.

---

## Rate limits & abuse policy

C411 API documentation does not publish hard rate limits. The 5-min server-side
cache on Torznab feeds and the Prowlarr-recommended 15-60 min RSS interval imply
the tracker is not hostile to polling. Defensive policy:

| Setting             | Value | Rationale                                                 |
| ------------------- | ----- | --------------------------------------------------------- |
| `rps`               | `0.5` | Same as LaCale — 1 req per 2s comfortably under cache TTL |
| `burst`             | `2`   | Allow short bursts when iterating categories              |
| `retry_max`         | `2`   | Transient failures only                                   |
| `circuit_threshold` | `3`   | Open circuit after 3 consecutive 5xx                      |

Tunable via `config/tracker.json5` per-provider override.

---

## Errors

C411 Torznab errors follow the Newznab convention — XML body with an `<error>` element:

```xml
<error code="100" description="Invalid API Key" />
```

| HTTP / Newznab code | Cause                          | Behavior                                                      |
| ------------------- | ------------------------------ | ------------------------------------------------------------- |
| `200` + `<rss>`     | Success                        | Parse + return                                                |
| `200` + `<error>`   | API error (auth, rate, syntax) | Raise `ApiError`; no retry on auth/syntax, retry on transient |
| `429`               | Rate limit                     | Tenacity retry with backoff                                   |
| `5xx`               | Server error                   | Tenacity retry; circuit opens at 3 hits                       |

The `<error>` body wins over HTTP status: a `200` response containing `<error>`
is still an error and must raise `ApiError(provider="c411", http_status=200, message=description)`.

---

## Open decisions (Phase 19.6 user checkpoint)

The following defaults are baked into this doc and will drive Phase 20; flagged as
**DECISION** for explicit user confirmation when Phase 20 starts. If left unchallenged
at Phase 20 start, defaults stand.

1. **Transport option**: Use **Option A** — `HttpTransport(response_format="xml")` with
   `xmltodict` (already a Phase 1 dependency). The shared XML pipeline handles parsing;
   the C411 client only navigates the resulting dict tree. Rationale: zero new infra,
   identical retry/circuit/rate-limit story across providers, no raw `requests` calls.

   Option B (raw passthrough) is rejected — there is no documented C411 quirk that
   requires bypassing the XML transport. If one surfaces during implementation, we
   revisit.

2. **Title parsing**: Reuse `LaCaleClient._parse_title` — both trackers encode quality
   markers (resolution, codec, source, audio, format) inside the torrent title with
   the same conventions. Phase 20 extracts `_parse_title` to a shared helper or
   imports it directly from `lacale.py` (decision: **import directly** from
   `personalscraper.api.tracker.lacale` to avoid premature abstraction; promote to a
   shared `_title_parser.py` only if a third tracker reuses it).

3. **Category normalization**: `get_categories()` returns a flat
   `description (slug) → human label` map. Because Newznab `id` collides across native
   subcats (multiple subcats map to e.g. `4050`), keying by `id` alone loses
   information. Phase 20 keys the dict by the `description` attribute (the actual
   French native label, unique within parent) and surfaces the Newznab class via
   a parallel `_id_for(slug) -> str` lookup. Confirm key strategy on first review.
4. **`cat` parameter REMOVED**: live caps confirms C411 does not advertise `cat`
   in `supportedParams`. Phase 20 will **not** send `cat=` — narrowing to a media
   type relies on `t=movie` / `t=tvsearch` only, or post-filter on `category`
   torznab attr. The earlier "registry passes resolved slug via cat" decision is
   void.
5. **Search endpoint selection**: use `t=search` for free-text queries and
   `t=movie` / `t=tvsearch` when `media_type` is supplied (the latter accept
   `imdbid`/`tmdbid`/`tvdbid` for ID-based lookups in a follow-up). Phase 20
   wires a `media_type → endpoint` decision at the top of `search()`.
6. **Default rate limit**: `rps=0.5`, `burst=2` (defensive, same as LaCale).
7. **Sample fixtures**: live samples captured 2026-05-07 in
   `docs/reference/_samples/c411/`:
   - `caps.xml` — Torznab capabilities + categories
   - `search-inception.xml` — `t=search&q=Inception` (multiple items, all VFF/Multi quality variants)
   - `search-empty.xml` — `t=search&q=zzzz_no_match_xyz` (channel with no items)
   - `tvsearch.xml` — `t=tvsearch&q=Breaking%20Bad`
   - `movie-imdbid.xml` — `t=movie&imdbid=tt1375666`
   - `error-auth.xml` — HTTP 401 + `<error code="100" description="Invalid API Key"/>`
     API keys redacted (`apikey=REDACTED_API_KEY` placeholder).

---

## Phase 20 implementation plan summary

```python
# personalscraper/api/tracker/c411.py
from personalscraper.api.tracker.lacale import LaCaleClient  # for _parse_title reuse

class C411Client:
    provider_name: str = "c411"
    REQUIRED_CREDS: ClassVar[list[str]] = ["C411_API_KEY"]

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy:
        return TransportPolicy(
            provider_name="c411",
            base_url="https://c411.org",
            auth=ApiKeyAuth(api_key, param="apikey", location="query"),
            timeout_seconds=15,
            response_format="xml",
            ...
        )

    def search(self, query, media_type="movie", year=None) -> list[TrackerResult]:
        params = {"t": "search", "q": query}
        if year is not None:
            params["q"] = f"{query} {year}"
        data = self._transport.get(path="/api", params=params)
        return self._parse_rss(data)

    def get_categories(self) -> dict[str, str]:
        data = self._transport.get(path="/api", params={"t": "caps"})
        return self._flatten_caps(data)
```

LOC budget: ≤ 350 LOC. If XML parsing logic grows beyond ~150 LOC, extract to
`_c411_parsers.py`.
