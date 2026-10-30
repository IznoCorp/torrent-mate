# V3x API Reference

Tracker: **v3x.club** (private French tracker, multi-content).
Site: `https://v3x.club` — API: `https://api.v3x.club`.
Client: **does not exist yet.** `personalscraper/api/tracker/v3x.py` (`V3xClient`) is
trackers-t1 phase 3 (`docs/features/backend-bricks/trackers-t1/DESIGN.md` § 3.2, § 6). This
document is the reference that client is built from; nothing here describes shipped code.
Source: the tracker's members' wiki, read 2026-10-04 (slugs cited per section), plus one
redacted capture of the search endpoint recorded the same day
(`docs/reference/_samples/v3x/`). Shape follows `tr4ker-api.md`; the economy section
follows `c411-api.md`.

**Capture gaps.** `GET /api/me` has **no capture yet** — the wiki's example is the only
evidence of its shape. Owed: a `me` call in `scripts/capture-tracker-sample.py`, added at
phase 3. The wiki documents Torznab, not the `/indexer/search` path the capture script
calls; that path is known from the capture alone.

---

## Scope

| Capability               | Endpoint                                         | Used by                                                  |
| ------------------------ | ------------------------------------------------ | -------------------------------------------------------- |
| Search (JSON)            | `GET /indexer/search`                            | **planned** `V3xClient.search()` → `list[TrackerResult]` |
| Account stats            | `GET /api/me`                                    | **planned** `V3xClient.account_stats()` (phase 5)        |
| `.torrent` download      | `GET /torrents/<id>/download` (Bearer)           | **planned**, through `resolve_source` (see Download)     |
| Torznab search           | `GET /torznab/api?t=search\|movie\|tvsearch`     | documented, not wired                                    |
| Categories tree          | `GET /api/categories`                            | documented, not wired                                    |
| Exists by info-hash      | `GET /api/torrents/exists?infohash=<hex>`        | documented, not wired                                    |
| Check a `.torrent`       | `POST /api/torrents/check`                       | documented, not wired                                    |
| Upload, drafts, NFO fix  | `POST /api/torrents`, `/api/drafts…`, …          | documented, not wired (the pipeline never uploads)       |

---

## Hosts

| Role              | URL                                          | Note                                                           |
| ----------------- | -------------------------------------------- | -------------------------------------------------------------- |
| Site              | `https://v3x.club`                           | Fallback site domain `v3x.tw` (redirects to `v3x.club` today). |
| API               | `https://api.v3x.club`                       |                                                                |
| Announce          | `https://announce.v3x.club/announce/<passkey>` | Carries the passkey — never written in any file.             |
| Announce, reserve | `https://tk.v3x.tw/announce/<passkey>`       | Same tracker, same passkey, same stats.                        |

Every `.torrent` generated since 2026-08-20 carries both announce routes, so a client
keeps seeding if one host is unreachable. (wiki: `plan-de-secours`, `passkey-announce`)

---

## Auth

Two secrets exist and they are **not** interchangeable.

| Secret               | Env var         | Role                                                                                                     |
| -------------------- | --------------- | -------------------------------------------------------------------------------------------------------- |
| **Scoped API key**   | `V3X_API_KEY`   | Authenticates API calls (search, `/api/me`, download). **Gates activation** of the planned client.       |
| **Announce passkey** | `V3X_PASSKEY`   | Embedded in `.torrent` files and announce URLs; identifies the account to the tracker. Never authenticates the API. |

- API keys are created in « Réglages ▸ Intégrations » (« Clés API à droits limités »; one
  wiki page says « Réglages ▸ API »). A key is shown once and is revocable.
- Three scopes: `torznab` (search and read), `upload`, `drafts`.
- `Authorization: Bearer <key>` works for **every** scope and is the recommended form.
  `?apikey=<key>` is accepted **only** for the `torznab` scope. `X-Api-Key` and an
  `apikey` header are **not read**. (wiki: `api`, `api-upload`)
- The passkey lives in « Réglages ▸ Connexion au tracker » and can be regenerated;
  regenerating invalidates every `.torrent` already downloaded. Seeding from several
  machines with one's own passkey is allowed (upload is counted per machine); sharing a
  passkey with another person is a ban offence. (wiki: `passkey-announce`)
- `GET /api/me` accepts a key of **any** scope, so no scope beyond `torznab` is needed to
  read account stats.

Capture facts (2026-10-04): `/indexer/search` took the key as `?apikey=`; a bad key (or one
without the `torznab` scope) returned **HTTP 401** with the JSON body
`{"error":"Invalid API Key or missing 'torznab' scope"}` (`_samples/v3x/error-auth.json`).

---

## Search — `GET /indexer/search`

Known from the capture only (the wiki does not document this path).

```
GET https://api.v3x.club/indexer/search?q=<query>&cat=<2000|5000>&limit=100&apikey=<key>
```

Response: JSON `{"results": [ … ]}`, one object per torrent. Fields seen on every item of
`search-movie.json` (12 items) and `search-tv.json` (17 items):

| Field                  | Meaning / observed value                                                              |
| ---------------------- | ------------------------------------------------------------------------------------- |
| `title`                | Release name, kept as released (not normalised: `Inception.{2010}.MULTi…`, `The Office`). |
| `details`              | `https://v3x.club/torrents/<uuid>` — the torrent's page; the id is a UUID.            |
| `download`             | `https://api.v3x.club/torznab/download?id=<uuid>&apikey=<key>` — **carries the key** (redacted in the capture). |
| `size`                 | Bytes, integer.                                                                       |
| `seeders`, `leechers`, `grabs` | Integers.                                                                     |
| `infohash`             | 40-char lowercase hex.                                                                |
| `category`             | Newznab family: `2000` / `5000` in the capture.                                       |
| `pubdate`              | **ISO 8601 UTC with milliseconds** (`2026-10-03T08:18:36.751Z`).                      |
| `tmdbid`               | TMDB id; present on every item.                                                       |
| `tvdbid`               | TVDB id or `null` (always `null` on movies; `null` on one TV item whose `tmdbid` differs from the show's). |
| `language`             | A label, not a title token: `Multi (FR inclus)` or `VOSTFR` in the capture.           |
| `downloadvolumefactor` | `1` (counted) or `0` (freeleech). `0` seen on two full-series packs.                  |
| `uploadvolumefactor`   | `1` on every item.                                                                    |

Observations that bear on the client:

- The `download` URL embeds the API key, so a client must treat it as sensitive (redact in
  logs) and never persist it.
- `tmdbid` is not always the show's: an item titled `The Office` carries `tmdbid` 573134,
  and the UK version (`tmdbid` 2996) also answers the query.
  The TMDB identity hard-filter is therefore needed on this tracker too.
- Full-series packs (`iNTEGRALE`) coexist with per-season torrents (see Catalogue).
- The `cat` filter accepted a single family per call in the capture; combining families
  (`2000,5000`) was not exercised.

The wiki's Torznab API (below) also exposes `tmdbid` / `tvdbid` search parameters; the
planned client searches by title as `c411` / `tr4ker` do (DESIGN § 2.2).

### Torznab (documented, not wired)

```
GET https://api.v3x.club/torznab/api?apikey=<key>&t=search|movie|tvsearch[&cat=…]
```

RSS 2.0. `t=movie` and `t=tvsearch` accept `tmdbid`; `t=tvsearch` also `tvdbid` (resolved
through TMDB; both ids are exposed per result). In Prowlarr the Generic Torznab URL is
`https://api.v3x.club/torznab` **without** `/api`. v3x is an official indexer in Jackett
(≥ v0.24.2434) and Prowlarr. (wiki: `torznab-categories-rss`, `prowlarr-v3x`,
`jackett-v3x-custom`)

---

## Account stats — `GET /api/me`

**Answers DESIGN T-1 for v3x.** Any key scope, `Authorization: Bearer <key>`:

```
GET https://api.v3x.club/api/me
```

Wiki example shape (no capture yet):

```
{ username, uploaded, downloaded, ratio, buffer, bonusPoints,
  freeleechTokens, invitesLeft, seeding, leeching, hitAndRun }
```

Volumes (`uploaded`, `downloaded`, `buffer`) are in **bytes**. `ratio` is the figure the
tracker recognises, which is what the Trackers page needs (NE-DOIT-PAS-1: never a locally
computed figure). `hitAndRun` is the account's unresolved H&R state — its exact type
(count or list) is not shown by the wiki example and must be read from the capture.
(wiki: `api`)

---

## Download

Two routes exist:

| Route                                                             | Auth             | Source             |
| ----------------------------------------------------------------- | ---------------- | ------------------ |
| `GET https://api.v3x.club/torrents/<id>/download`                 | Bearer           | wiki `api`         |
| `GET https://api.v3x.club/torznab/download?id=<id>&apikey=<key>`  | query `apikey`   | the search capture |

Both return a personalised `.torrent` (the passkey is embedded). `<id>` is the UUID that
ends the `details` URL. The planned client uses the Bearer route so the key stays out of
URLs; the search result's own `download` URL is the one the capture proves to exist.
Neither route has a downloaded-file capture yet.

---

## Categories

Newznab families only:

| Id   | Family   |
| ---- | -------- |
| 1000 | Console  |
| 2000 | Movies   |
| 3000 | Audio    |
| 4000 | PC       |
| 5000 | TV       |
| 7000 | Books    |
| 8000 | Other    |

There is **no anime and no documentary family**: the planned client maps every film kind to
`2000` and every series kind to `5000` (DESIGN § 3.5). `GET /api/categories` returns the
full tree `{categories:[{id, name, slug, subcategories:[{id, name, slug}]}]}` (documented,
not wired). (wiki: `torznab-categories-rss`, `api-upload`)

---

## Rate limits

Counted **per API key**, not per IP, for key-authenticated calls. Over quota the tracker
answers **HTTP 429** with a `Retry-After` header. (wiki: `rate-limit`)

| Surface                            | Limit             |
| ---------------------------------- | ----------------- |
| Torznab search + `.torrent` download | 200 req / 10 s  |
| General API                        | 200 req / min     |
| Login                              | 10 / min          |
| Announce                           | unlimited         |

Whether `/indexer/search` counts as Torznab or as general API is not stated by the wiki.
The planned client's 0.5 req/s profile (DESIGN § 3.2) stays far below both quotas.

---

## Economy

Everything below is the wiki's rule, not something the API returns, except the account
figures `/api/me` publishes. (wiki: `ratio-seedtime`, `comprendre-le-ratio`,
`hit-and-run`, `points-bonus-detaille`)

- **Ratio** = uploaded / downloaded; **buffer** = uploaded − downloaded. A new account
  gets a 150 GiB upload credit. The wiki advises **aiming for a ratio ≥ 1**.
- **Ratio floor**: a warning banner and notification at ratio **0.7**; below **0.5** AND
  more than 50 GiB downloaded, new downloads are refused except freeleech. The block lifts
  by itself once the ratio is back above 0.5. No ban.
- **Freeleech**: the download is not counted. Every torrent ≥ 100 GiB is permanently
  freeleech; staff and uploader boosts add more. Exposed on search as
  `downloadvolumefactor: 0`.
- **HIT AND RUN — exists on v3x** (unlike c411): every completed download must be seeded
  **≥ 48 h cumulated within 14 days** of completion.
  - Freeleech changes nothing; a partial seed does not count.
  - **Exempt**: own uploads, and cross-seeds (0 bytes received).
  - **Exempt members**: ≥ 1 TiB uploaded **and** a real ratio ≥ 1.
  - After 14 days short of 48 h the torrent is marked H&R and a notification is sent.
  - **≥ 3 unresolved H&R ⇒ all new downloads blocked, freeleech included.**
  - Fix: keep seeding to 48 h (clears by itself) or buy back with 5 000 tokens (1 per 30
    days).
  - Tracked only for torrents taken from **2026-09-11**.
- **Bonus points** accrue per hour and per seeded torrent:
  `0.7 × max(log2(1 + size_GiB), 0.5) × 1 / (1 + log2(1 + seeders) / 2)`, capped at
  15 / h / torrent, with a loyalty multiplier ×1.15 after 7 days and ×1.30 after 30 days
  seeded on that torrent. They buy upload credit, personal freeleech and invites (10 000).
- Jackett's public `minimumratio 0.8` is superseded by the wiki above (aim ≥ 1, floor 0.5,
  warning 0.7).

For the `economy` config block: `target_ratio` ≥ 1, `min_ratio` 0.5 (warning level 0.7),
`min_seed_time` 48 h, `hit_and_run_grace` 14 days. The operator fills it in his overlay.

---

## Cross-seed

Allowed and encouraged. (wiki: `cross-seed`, `cross-seed-autobrr`)

- v3x **never renames a release**, so the same release name means the same files.
- Each private tracker injects its own `source` field, so the info-hash differs per
  tracker: matching is by name and file layout, not by hash. This is the engine's existing
  method (it searches candidates by release name and verifies the downloaded layout).
- The page `https://v3x.club/cross-seed` matches pasted hashes or names and returns a
  `.zip` of `.torrent` files (a human tool, not wired).
- A cross-seed receives 0 bytes, so it is **H&R-exempt** and costs no ratio.
- There is no IRC announce channel; autobrr works from the Torznab feed (a 1-minute poll
  is acceptable).

---

## Client rules

- **DHT, PeX and LSD must be OFF** — private-tracker rule number one. Torrents are private,
  with source tag `V3X`. (wiki: `configurer-qbittorrent`)
- Never expose a passkey: announce URLs and the `download` URL with its `apikey=` are
  secrets (redact in logs, none in any file).

---

## Catalogue and naming (bears on grab and cross-seed)

(wiki: `catalogue-v3x`, `nommer-release`, `regles-films-videos`)

- Duplicates are refused by info-hash **and** by content, yet **several encodes of one
  title coexist** (the Inception capture shows 1080p x264, HEVC, 2160p remux, 4KLight…).
- Release names are kept as released (scene-name fidelity); the capture confirms mixed
  styles (`Inception.{2010}.MULTi…`, `Inception (2010) Blu-ray…`).
- Series: **one episode or one full season per torrent, never mixed** — except the
  `iNTEGRALE` full-series packs seen in the TV capture, which the grab must size before
  committing (e.g. 213 GB).
- A **language tag is mandatory**: `MULTI`, `VFF`, `VFQ`, `VOSTFR`, `VO`. The search
  result also gives a `language` label.
- `AI.UPSCALED` marks upscaled releases.
- Refused sources: CAM, TS, TC, HDCAM, anything below 480p, and DDL or public-tracker rips.

---

## Known errors

| Symptom                                                   | Cause / fix                                                                   |
| --------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 401 `{"error":"Invalid API Key or missing 'torznab' scope"}` | Wrong key, revoked key, or a key without the `torznab` scope.              |
| Key accepted as Bearer but rejected as `?apikey=`         | The key has a scope other than `torznab`: query auth is torznab-only.         |
| `X-Api-Key` header ignored                                | Not read by v3x — use Bearer.                                                 |
| 429 + `Retry-After`                                       | Per-key quota exceeded; wait the stated delay.                                |
| Downloads refused                                         | Ratio floor (< 0.5 and > 50 GiB downloaded) or ≥ 3 unresolved H&R (tracker-side gate, not an API error). |
| Old `.torrent` stops announcing                           | The passkey was regenerated.                                                  |
| Upload errors (wiki) — JSON `{"error":"<code>"}`          | `validation`, `invalid_category`, `rights_not_declared`, `mediainfo_required`, `ddl_source`, `review_quota` (429), `file_too_large` (413, > 32 MiB), 401 unauthenticated, 403 wrong scope; 409 `duplicate` / `duplicate_content`. Documented only — the pipeline never uploads. |

---

## Not in this repo

- No secret of any kind: this document quotes no API key, passkey or announce URL carrying
  one. Examples use `<key>` / `<passkey>`.
- Samples: `docs/reference/_samples/v3x/` — `search-movie.json` (`q=Inception&cat=2000`, 12
  items), `search-tv.json` (`q=The Office&cat=5000`, 17 items), `error-auth.json` (bad key,
  401) and `index.json` (the requests). Recorded 2026-10-04 with
  `scripts/capture-tracker-sample.py v3x`; every `apikey=` is `REDACTED`. Not yet
  captured: `/api/me`, a `.torrent` download.
