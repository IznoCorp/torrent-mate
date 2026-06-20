# torr9 — Tracker API Reference

> Captured live 2026-06-19 (real payloads under `fixtures/`). **All credentials
> are secrets** — `.env` only (`TORR9_USERNAME`, `TORR9_PASSWORD`, `TORR9_PASSKEY`);
> never committed. Examples use placeholders. When `torr9` ships, this file moves
> to `docs/reference/torr9-api.md`.

## Overview

torr9 (`https://torr9.net` — a **Next.js SPA**; API `https://api.torr9.net/api/v1`)
is a French private tracker. It is a **full search tracker** via an
**authenticated JSON API**, plus **passkey-based RSS browse feeds** (recent /
freeleech / per-category). Cloudflare-fronted, **rate-limited** (HTTP 429/403
under bursty access — back off).

> ⚠️ Correction (prep note): an earlier capture using only the passkey saw the RSS
> feeds (browse-only) and wrongly concluded "no search". The search lives on the
> **JWT-authenticated JSON API**, not the RSS — this is how Radarr/Sonarr-style
> clients use it.

## Authentication — DUAL

torr9 has two independent credentials for two surfaces:

| Surface                                 | Credential        | Use                                    |
| --------------------------------------- | ----------------- | -------------------------------------- |
| **JSON API** (search, torrent metadata) | **JWT** via login | `Authorization: Bearer <token>`        |
| **RSS feeds + announce/download**       | **passkey**       | `?passkey=<TORR9_PASSKEY>` query param |

### JWT login (for search)

```
POST /api/v1/auth/login
Content-Type: application/json
{ "username": "<TORR9_USERNAME>", "password": "<TORR9_PASSWORD>" }

→ 200 { "token": "<JWT>", "user": {...}, "message": "..." }
→ 400 { "error": "Validation failed", ... }            (missing/empty fields)
→ 401 { "error": "Identifiant ou mot de passe invalide" }  (bad credentials)
→ 403 Forbidden                                        (rate-limited)
```

Use the returned `token` as `Authorization: Bearer <token>` on JSON API calls.
Token expiry / 401 mid-session → **re-login** (RP7 auth-lifecycle: the 401 is
observable and routable). Creds: `TORR9_USERNAME` + `TORR9_PASSWORD`.

### Passkey (for feeds + download)

`TORR9_PASSKEY` (32-hex). Used on RSS feeds and embedded in the announce URL
(`TORR9_ANNOUNCE_URL = https://tracker.torr9.net/announce/{TORR9_PASSKEY}`) and
the RSS `.torrent` download URLs.

## Search (JSON API)

> ⚠️ **CRITICAL — endpoint correction (2026-06-20).** Search is
> **`GET /api/v1/torrents/search?q=`** — the real, q-filtering search endpoint.
> An earlier integration used `GET /api/v1/torrents?q=` (the **listing/recent**
> endpoint), which **IGNORES `q`** and returns a static recent feed regardless of
> the query — so every search returned the same recent torrents. Root cause: the
> wrong endpoint. The fix is one line (`/torrents` → `/torrents/search`).
> Filtering works with just `Accept: application/json` + Bearer (no browser
> headers needed): Batman→Batman, Inception→Inception, nonsense→0 results.

```
GET /api/v1/torrents/search?q=<url-encoded-query>
Authorization: Bearer <token>

→ 200 { "count": 25, "current_page": 1, "limit": 25, "query": "Inception",
        "total_count": 44, "total_pages": 2, "filters": {…},
        "torrents": [ {item}, ... ] }
→ 401 { "error": "Missing authorization token" }   (no/invalid Bearer)
```

- **Query param is `q`** (confirmed). `?search=` is **ignored** (returns 0).
- **Envelope**: `count` / `current_page` / `limit` / `query` / `total_count` /
  `total_pages`, plus `filters` (`{category, max_age_days, search_in, tag, uploader}`).
  Items are still under `torrents` (extraction unchanged from the listing shape).
- **Pagination**: `limit` + `current_page` / `total_pages` (request `&page=N` for
  more; default page 1, limit 25).
- Real sample: `_samples/torr9/torr9_search.json` (`?q=Inception`, uploader redacted).

### Endpoint catalog (from the SPA JS bundle, 2026-06-20)

| Use                | Endpoint                                     | Notes                                                |
| ------------------ | -------------------------------------------- | ---------------------------------------------------- |
| list / recent feed | `GET /torrents`                              | **IGNORES `q`** — NOT search (history: wrong ep)     |
| recent             | `GET /torrents/recent`                       | recent feed                                          |
| **search**         | `GET /torrents/search?q=`                    | **the real q-filtering search** ✓                    |
| details            | `GET /torrents/{id}`                         | single object, carries `magnet_link` + swarm         |
| download           | `GET /torrents/{id}/download`                | authed `.torrent` bytes (`application/x-bittorrent`) |
| comments           | `GET /torrents/{id}/comments`                | —                                                    |
| check-duplicate    | `GET /torrents/check-duplicate`              | —                                                    |
| exclus             | `GET /torrents/exclus?days=`                 | —                                                    |
| featured search    | `GET /torrents/featured/search?query=&type=` | —                                                    |
| rss recent         | `GET /rss/recent?passkey=`                   | passkey browse feed                                  |

### Torrent item schema (`/torrents/search`, real capture)

```json
{
  "id": 13750,
  "title": "Inception 2010 BluRay 2160p HDR Hybrid DoVi x265 10bit MULTI VFF 5.1 DTS HDMA-telemO",
  "info_hash": "cc32af3a46e54c48ded0c74ee2a9e798d70834ea",
  "file_size_bytes": 13832185317,                            // exact bytes
  "file_count": 1,
  "upload_date": "2026-02-05T06:56:23.80812Z",               // ISO-8601
  "is_freeleech": false,                                     // structured boolean ✓
  "tags": ["2160p","x265","HDR","DoVi","BluRay","DTS", …],   // quality tags
  "category_name": "Films",                                  // human label (NO category_id)
  "category_icon": "Films",
  "parent_category_name": "Films",
  "uploader_name": "redacted",
  "seeders": 49,                                             // real swarm ✓
  "leechers": 0,                                             // real swarm ✓
  "times_completed": 109,
  "comment_count": 0,
  "tmdb_id": 27205,                                          // 0 means "none"
  "is_exclu": false,
  "status": null
  // NOTE: NO magnet_link, NO category_id, NO description in the search shape.
}
```

| `TrackerResult` field  | Source                                                                       |
| ---------------------- | ---------------------------------------------------------------------------- |
| title                  | `title`                                                                      |
| size (bytes)           | `file_size_bytes`                                                            |
| `is_freeleech`         | `is_freeleech` (clean boolean — no text parsing)                             |
| download               | `/api/v1/torrents/{id}/download` (no magnet in search; see §Download)        |
| upload_date            | `upload_date` (ISO)                                                          |
| category               | `category_name` label directly (no `category_id` in search; see §Categories) |
| info hash / tracker id | `info_hash` / `id`                                                           |
| **seeders / leechers** | **`seeders` / `leechers`** — the SEARCH endpoint exposes real swarm health ✓ |
| `tmdb_id`              | `tmdb_id` (int; `0`/absent → `None`)                                         |

## Download

- **Search items carry NO `magnet_link`** → download is the authed `.torrent`
  endpoint **`GET /api/v1/torrents/{id}/download`** (Bearer, returns
  `application/x-bittorrent` bytes — live-confirmed 200). Fetched via the
  provider's authed transport.
- The **detail** endpoint (`GET /torrents/{id}`) **does** carry `magnet_link`
  (auth-free, ROADMAP Q4 "magnet exception") — preferred when a result is built
  from a detail payload.
- `torrent_file_url` is **DEAD** (404 at every host/auth, hash mismatch, absent
  from the detail payload) and is **NOT consumed**.

## Detail (JSON API) — per-torrent re-check

```
GET /api/v1/torrents/{id}
Authorization: Bearer <token>
```

Live-confirmed 2026-06-19. Returns a **single torrent** object (NOT a list/wrapper).
Carries the same swarm/category fields as the `/torrents/search` item
(`seeders`, `leechers`, `times_completed`, `category_name`, …) **plus**
`magnet_link` (auth-free) and uploader stats. Sample:
`_samples/torr9/torr9_detail.json` (uploader private stats zeroed, avatar
redacted — no passkey/token present).

Backs the **`FreeleechAware.is_freeleech(torrent_id)`** pre-download re-check:
ensure token → `GET /torrents/{id}` (re-login on 401) → return the fresh
`is_freeleech` boolean. Since `/torrents/search` already carries real
`seeders`/`leechers`, the detail-based swarm re-check is an **optional opt-in
re-check** (`enrich_seeders`, default **OFF**), not a necessity.

`GET /torrent/{id}` (singular) returns **404** — the path is **plural** `torrents`.

## RSS feeds (passkey) — for the freeleech radar

Still useful alongside search: `rss/recent`, `rss/freeleech` (channel "Torr9 -
Torrents Freeleech"; items mark `| FREELEECH` in `<description>`), `rss/<category>`.
RSS 2.0, `?passkey=<TORR9_PASSKEY>`, `&limit=N`. These feed the **freeleech radar
(R1)** / recent-harvest / Watcher. Sample: `fixtures/torr9_recent.xml`,
`fixtures/torr9_freeleech.xml`. (The RSS item schema — title/link/description/
pubDate/category/enclosure — is the browse view; the **JSON API is authoritative
for search + the structured fields** like `is_freeleech`.)

## Categories

The `/torrents/search` and `/torrents/{id}` payloads carry a human
**`category_name`** label directly (consumed straight onto `TrackerResult`).
The numeric **`category_id`** appears only in the **listing** (`/torrents`)
shape — so the `_CATEGORY_MAP` (id → label) below is now only a **fallback**
for that listing shape, not the primary path.

torr9 exposes **NO `/categories` endpoint** (404 confirmed on `/categories`,
`/category`, `/torrents/categories` on 2026-06-20). The `?category_id=` search
filter is **ignored**. The id→label fallback map is built empirically by
correlating the listing payload's `category_id` with the search/detail
`category_name`:

| `category_id` | Label          | Parent      | Source                          |
| ------------: | -------------- | ----------- | ------------------------------- |
|             5 | Séries TV      | Séries      | Live-verified 2026-06-20        |
|             6 | Emission TV    | Séries      | Live-verified 2026-06-20        |
|            16 | BD             | Livres      | Live-verified 2026-06-20        |
|            23 | Microsoft      | Jeux-vidéos | Live-verified 2026-06-20        |
|            51 | Films          | Films       | Live-verified 2026-06-20        |
|            65 | Livres Audios  | Livres      | Live-verified 2026-06-20        |
|             2 | Films          | —           | 2026-06-19 prep only (inferred) |
|             9 | Films          | —           | 2026-06-19 prep only (inferred) |
|            46 | Séries Animées | —           | 2026-06-19 prep only (inferred) |
|            53 | Anime          | —           | 2026-06-19 prep only (inferred) |
|            54 | TV Programs    | —           | 2026-06-19 prep only (inferred) |

> On 2026-06-20 the search `q` param was observed returning a recent-only
> default set (degraded), so a full category enumeration was not possible —
> re-run the search↔detail correlation when `q` filtering is healthy to
> extend the map.

## Fit with personalscraper

- **`Torr9Client` IS a `TorrentSearchable`** — `search(query, media_type, year)`:
  login → `GET /torrents/search?q=` (the real search endpoint, NOT `/torrents?q=`)
  → parse `torrents[]` → `TrackerResult[]`. Mirrors the c411/lacale role; auth
  differs (JWT vs API-key) → RP7 auth lifecycle.
- **Dual auth** in `policy()` / client: JWT (login, `TORR9_USERNAME`/`PASSWORD`)
  for search; passkey (`TORR9_PASSKEY`) for the RSS freeleech radar + download
  fallback.
- **Download** — search items carry no magnet → the authed `.torrent`
  `/torrents/{id}/download` endpoint; detail items carry the auth-free magnet.
- **Freeleech** is a structured boolean in search (`is_freeleech`) and a `| FREELEECH`
  marker in the RSS — both feed `TrackerResult.is_freeleech`.
- **`Torr9Client` IS a `FreeleechAware`** — `is_freeleech(torrent_id)` re-checks via
  the `GET /torrents/{id}` detail endpoint (live-confirmed). A real pre-download
  re-check, unlike c411/lacale which have no detail endpoint.
- **Real seeders in SEARCH** — `_ranking.py` weights seeders; the
  `/torrents/search` payload carries real `seeders`/`leechers`, so torr9 results
  are ranking-ready. The detail-based swarm re-check (`enrich_seeders`) is an
  **optional opt-in** (default OFF), not a necessity.
- **`tmdb_id` in SEARCH** — search items carry `tmdb_id`, surfaced on
  `TrackerResult.tmdb_id` (`0`/absent → `None`).
- **Freeleech radar (R1)** — the `rss/freeleech` feed is exactly the "freeleech window
  enumeration" the ROADMAP Q3/R1 wants.

## Open items (confirm at impl)

1. `category_id` → label map (`GET /categories` with fresh token). _Detail responses
   carry `category_name` directly, which partially covers this._
2. JWT lifetime / refresh mechanism (token expiry handling).
3. Pagination upper bound + per-category search params (`?category_id=` ?).

**Resolved (live 2026-06-19):** the per-torrent **detail** endpoint
`GET /torrents/{id}` exists and exposes `is_freeleech` + `seeders`/`leechers` —
backs the `FreeleechAware` re-check (see §Detail). 4. Rate-limit budget (429/403 thresholds) → `TransportPolicy` throttle. 5. `torrent_file_url` absolute form + auth (only if magnet is ever insufficient).
