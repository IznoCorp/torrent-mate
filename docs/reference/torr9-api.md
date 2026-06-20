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

```
GET /api/v1/torrents?q=<url-encoded-query>
Authorization: Bearer <token>

→ 200 { "limit": 20, "page": 1, "torrents": [ {item}, ... ] }
→ 401 { "error": "Missing authorization token" }   (no/invalid Bearer)
```

- **Query param is `q`** (confirmed). `?search=` is **ignored** (returns 0).
- **Pagination**: `limit` + `page` (request `&page=N` for more; default page 1, limit 20).
- Real sample: `fixtures/torr9_search.json`.

### Torrent item schema (real capture)

```json
{
  "id": 305292,
  "title": "Oasis.2026.S01.MULTi.AD.1080p.NF.WEB.X264-THESYNDiCATE",
  "description": "[center]…[/center]",                       // BBCode
  "info_hash": "d5638677f9986adc3ea155e7b753c36321cc30af",
  "magnet_link": "magnet:?xt=urn:btih:d563…&dn=…",           // direct magnet (no passkey)
  "torrent_file_url": "uploads/torrents/<info_hash>.torrent", // relative; needs base + auth
  "file_size_bytes": 20827331134,                            // exact bytes
  "file_count": 8,
  "category_id": 5,                                          // numeric (see §Categories)
  "uploader_id": 69602,
  "is_private": true,
  "is_freeleech": false,                                     // structured boolean ✓
  "is_anon": false,
  "is_exclu": false,
  "tags": ["1080p","FHD","WEB","H264","x264","FRENCH", …],   // quality tags
  "upload_date": "2026-06-19T13:29:19.797357Z",              // ISO-8601
  "status": "active"
}
```

| `TrackerResult` field  | Source                                                                                                                                |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| title                  | `title`                                                                                                                               |
| size (bytes)           | `file_size_bytes`                                                                                                                     |
| `is_freeleech`         | `is_freeleech` (clean boolean — no text parsing)                                                                                      |
| download               | `magnet_link` (preferred, auth-free) or `torrent_file_url` (base + auth)                                                              |
| upload_date            | `upload_date` (ISO)                                                                                                                   |
| category               | mapped from `category_id` (§Categories)                                                                                               |
| info hash / tracker id | `info_hash` / `id`                                                                                                                    |
| **seeders / leechers** | **NOT in SEARCH** — torr9's search payload exposes no swarm health (the **detail** endpoint `GET /torrents/{id}` _does_; see §Detail) |

## Download

- **Preferred: `magnet_link`** — direct magnet, **no passkey/auth** (matches the
  ROADMAP Q4 "magnet exception"). Hand straight to qBittorrent.
- `torrent_file_url` is a **relative** path; absolute `.torrent` needs the base +
  auth (passkey or token) — only if a `.torrent` file is specifically required.

## Detail (JSON API) — per-torrent re-check

```
GET /api/v1/torrents/{id}
Authorization: Bearer <token>
```

Live-confirmed 2026-06-19. Returns a **single torrent** object (NOT a list/wrapper).
Superset of the search item: same `id` / `title` / `info_hash` / `magnet_link` /
`file_size_bytes` / `is_freeleech` / `tags` / `upload_date`, **plus** fields the
search omits — `seeders`, `leechers`, `times_completed`, `views`, `age`,
`category_name`, and uploader stats. Sample: `_samples/torr9/torr9_detail.json`
(uploader private stats zeroed, avatar redacted — no passkey/token present).

Backs the **`FreeleechAware.is_freeleech(torrent_id)`** pre-download re-check:
ensure token → `GET /torrents/{id}` (re-login on 401) → return the fresh
`is_freeleech` boolean. The `seeders`/`leechers` here would also let a future
ranking improvement N+1-fetch swarm health, but that is **deferred** (not in this
feature; see DESIGN Risk "No seeders in SEARCH").

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

`category_id` is **numeric**. torr9 exposes **NO `/categories` endpoint**
(404 confirmed on `/categories`, `/category`, `/torrents/categories` on
2026-06-20). The `?category_id=` search filter is **ignored** (returns the
same default set regardless). The id→label map is built empirically by
correlating the search payload's `category_id` with the detail payload's
`category_name` (`GET /torrents/{id}`):

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
  login → `GET /torrents?q=` → parse `torrents[]` → `TrackerResult[]`. Mirrors the
  c411/lacale role; auth differs (JWT vs API-key) → RP7 auth lifecycle.
- **Dual auth** in `policy()` / client: JWT (login, `TORR9_USERNAME`/`PASSWORD`)
  for search; passkey (`TORR9_PASSKEY`) for the RSS freeleech radar + download
  fallback.
- **Magnet-first download** (auth-free) — clean for the grab core.
- **Freeleech** is a structured boolean in search (`is_freeleech`) and a `| FREELEECH`
  marker in the RSS — both feed `TrackerResult.is_freeleech`.
- **`Torr9Client` IS a `FreeleechAware`** — `is_freeleech(torrent_id)` re-checks via
  the `GET /torrents/{id}` detail endpoint (live-confirmed). A real pre-download
  re-check, unlike c411/lacale which have no detail endpoint.
- **No seeders in SEARCH** — `_ranking.py` weights seeders; torr9 _search_ results
  carry none → rank on freeleech / size / recency. The detail endpoint has them, but
  populating ranking seeders via N+1 detail-fetch is **deferred**.
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
