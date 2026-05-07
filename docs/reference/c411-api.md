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

### Limits

- 5 min server-side cache (per `ArrStack.md`).
- ETag support for conditional requests.
- Recommended RSS sync interval: 15–60 min (informative — search calls are not RSS).

### Response — RSS-style XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <title>C411</title>
    <item>
      <title>Inception.2010.2160p.UHD.BluRay.x265.HDR.TrueHD-NCmt</title>
      <guid>https://c411.org/torrents/12345</guid>
      <link>https://c411.org/api/torrents/download/12345?apikey=...</link>
      <comments>https://c411.org/torrents/12345</comments>
      <pubDate>Sun, 12 Jan 2025 10:00:00 +0000</pubDate>
      <category>2000</category>
      <enclosure url="https://c411.org/api/torrents/download/12345?apikey=..."
                 length="2147483648"
                 type="application/x-bittorrent" />
      <torznab:attr name="seeders" value="42"/>
      <torznab:attr name="peers" value="45"/>
      <torznab:attr name="size" value="2147483648"/>
      <torznab:attr name="category" value="2000"/>
      <torznab:attr name="infohash" value="abcdef..."/>
      <torznab:attr name="downloadvolumefactor" value="0"/>
      <torznab:attr name="uploadvolumefactor" value="1"/>
    </item>
  </channel>
</rss>
```

Notes:

- `torznab:attr` repeated elements carry typed metadata. With `xmltodict`,
  repeated `<torznab:attr>` becomes a list of dicts each with `@name` and `@value`.
- `enclosure` carries the download URL and total size.
- `seeders` / `peers` come via `torznab:attr` (peers = seeders + leechers in Torznab spec; leechers = peers − seeders).
- `downloadvolumefactor=0` ⇒ **freeleech**. `downloadvolumefactor=0.5` ⇒ partial / silver-leech.
- `uploadvolumefactor=2` ⇒ double upload bonus (informative).

### Field mapping → `TrackerResult`

| C411 / Torznab field                         | `TrackerResult` field                              | Notes                                                                                        |
| -------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| —                                            | `provider`                                         | Constant `"c411"`                                                                            |
| `<guid>`                                     | `tracker_id`                                       | URL or numeric ID after stripping host/path                                                  |
| `<title>`                                    | `title`                                            | Used as input for `_parse_title()` (shared helper)                                           |
| `enclosure[@length]` or `torznab:attr[size]` | `size` (`ByteSize`)                                | Bytes (string in XML) → `ByteSize.parse(int(value))`                                         |
| `torznab:attr[seeders]`                      | `seeders`                                          | Direct int                                                                                   |
| `torznab:attr[peers] - seeders`              | `leechers`                                         | Torznab spec: peers = seeders + leechers                                                     |
| `torznab:attr[category]` or `<category>`     | `category`                                         | Newznab numeric ID — keep as-is (e.g. `"2000"`)                                              |
| `enclosure[@url]` or `<link>`                | `download_url`                                     | Direct                                                                                       |
| `torznab:attr[infohash]`                     | `info_hash`                                        | Lowercase hex                                                                                |
| `<comments>` or `<guid>`                     | `source_url`                                       | Detail page URL (prefer `comments` when present)                                             |
| `<pubDate>`                                  | `upload_date`                                      | RFC 2822 (`Sun, 12 Jan 2025 10:00:00 +0000`); parse with `email.utils.parsedate_to_datetime` |
| `torznab:attr[downloadvolumefactor]`         | `is_freeleech`                                     | `True` if `value == "0"`                                                                     |
| `torznab:attr[downloadvolumefactor]`         | `is_silverleech`                                   | `True` if `value == "0.5"`                                                                   |
| _(derived from title)_                       | `format`, `codec`, `source`, `resolution`, `audio` | Reuse LaCale's `_parse_title` (titles encode same fields)                                    |

---

## Categories endpoint (Torznab caps)

```
GET /api?t=caps&apikey=<key>
```

### Response shape

```xml
<caps>
  <server title="C411" />
  <searching>
    <search available="yes" supportedParams="q,cat,limit,offset,apikey,o" />
    <movie-search available="yes" supportedParams="q,imdbid,tmdbid,cat,limit,offset,apikey,o" />
    <tv-search available="yes" supportedParams="q,tvdbid,season,ep,cat,limit,offset,apikey,o" />
    ...
  </searching>
  <categories>
    <category id="2000" name="Movies">
      <subcat id="2060" name="Anime" />
      <subcat id="2070" name="Documentary" />
    </category>
    <category id="5000" name="TV">
      <subcat id="5070" name="Anime" />
    </category>
    ...
  </categories>
</caps>
```

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

3. **Category normalization**: `get_categories()` returns flat
   `numeric_id_str → display_name` map (matches LaCale shape modulo string-vs-slug).
   Mapping `media_type` → Newznab category ID happens at the registry level, not
   inside `C411Client.search()`. Search invocation passes the resolved category(ies)
   via the `cat` query parameter.

4. **Search endpoint selection**: `t=search` (general). The specialized `t=movie` /
   `t=tvsearch` endpoints offer ID-based search (`imdbid`, `tmdbid`, `tvdbid`) which
   the registry doesn't currently exploit. Phase 20 starts with `t=search` + `cat`
   filtering; `t=movie` / `t=tvsearch` lookup helpers can land in a follow-up if
   the indexer/orchestrator wants ID-based queries.

5. **Default rate limit**: `rps=0.5`, `burst=2` (defensive, same as LaCale).

6. **Sample fixtures**: not captured in Phase 19 (no `C411_API_KEY` in local `.env`).
   Phase 20 unit tests will rely on hand-crafted XML fixtures derived from the
   shapes documented here. If real samples become available later, they go in
   `docs/reference/_samples/c411/`.

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
