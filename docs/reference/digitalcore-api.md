# Digitalcore API Reference

Tracker: **digitalcore.club** (private English tracker, scene-oriented / 0-day, multi-content).
Base URL: `https://digitalcore.club` — official proxy: `https://prxy.digitalcore.club/`.
Client: **does not exist yet.** It is phase 4 of `docs/features/backend-bricks/trackers-t1/DESIGN.md`
(`personalscraper/api/tracker/digitalcore.py`, a small JSON client of its own over the shared `HttpTransport`, since
the tracker does not speak Torznab). Nothing in `personalscraper/` or `config*/` knows digitalcore today; this
document is the reference that phase builds from.
Source: the tracker's rules and FAQ, read 2026-10-04 (sections « Ratio Rules », « Hit and Run », « Api », « VPNs »,
« IRC »), plus the four redacted captures of `docs/reference/_samples/digitalcore/` recorded the same day. Facts are
paraphrased. Where the FAQ and a capture disagree, the capture wins; where only the FAQ speaks, the fact is marked
"FAQ".

The website is hosted in Russia and VPN addresses are often blocked: a refused connection with a correct key is more
likely the network than the key. The official proxy above exists for that case.

---

## Scope

The pipeline consumes the **JSON search** and the **`.torrent` download** only.

| Capability | Endpoint                                  | Used by (planned)                                         |
| ---------- | ----------------------------------------- | --------------------------------------------------------- |
| Search     | `GET /api/v1/torrents`                    | `DigitalCoreClient.search()` → `list[TrackerResult]`      |
| Download   | `GET /api/v1/torrents/download/{id}`      | `resolve_source()` for the grab and the cross-seed check  |
| Categories | none — a static table (§ Categories)      | `DigitalCoreClient.get_categories()`                      |

Everything else is **documented, not wired** (§ Endpoints). There is **no account-statistics endpoint** for a normal
key (§ Blocked), so the client does not claim `AccountStatsReadable` and the ratio is UNKNOWN in TorrentMate.

---

## Auth

Two secrets exist and they are **not** interchangeable.

| Secret               | Env var                | Role                                                                                       |
| -------------------- | ---------------------- | ------------------------------------------------------------------------------------------ |
| **API key**          | `DIGITALCORE_API_KEY`  | Authenticates API requests. **Gates activation.**                                          |
| **Announce passkey** | `DIGITALCORE_PASSKEY`  | Embedded in the `.torrent` files' announce; identifies the account. Authenticates nothing here. |

| Item       | Value                                                                              |
| ---------- | ---------------------------------------------------------------------------------- |
| Activation | `PROVIDER_CREDS["digitalcore"] = ["DIGITALCORE_API_KEY"]` (planned)                |
| Non-gating | `PROVIDER_OPTIONAL_SECRETS["digitalcore"] = ["DIGITALCORE_PASSKEY"]` (planned)     |
| Transport  | `ApiKeyAuth(key, param="X-API-KEY", location="header")` (planned)                  |

The key is created on the account page (« Settings → Security → Generate a new API Key »), which also shows « How to
use it ». The tracker accepts it in **three forms**:

| Form                        | Notes                                                                                     |
| --------------------------- | ----------------------------------------------------------------------------------------- |
| Header `X-API-KEY: <key>`   | **Used by the capture** and by the planned client. Keeps the key out of every URL.        |
| `Authorization: Bearer <key>` | Accepted (account page).                                                                |
| Query `?apikey=<key>`       | Accepted (account page); avoid — a URL ends up in logs and in `source_url`-like fields.   |

A wrong or missing key answers **HTTP 401** with a JSON string body (`error-auth.json`): « Authentication Required:
No valid API Key, Passkey, or Login Cookie found. » — a bare string, not an object, and the same message whichever
secret is missing.

**The announce host is NOT known yet.** The pages read do not print it, and the tracker rewrites `announce`, `source`
and `private` server-side on upload. `DIGITALCORE_ANNOUNCE_URL` stays empty in the operator's `.env` until a
downloaded `.torrent` shows the host. This document quotes no announce URL.

---

## Endpoints

| Method + path                                   | Purpose                                                                                  | Status                  |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------- |
| `GET /api/v1/torrents`                          | Listing and search (parameters below)                                                    | **used**, captured      |
| `GET /api/v1/torrents/download/{id}`            | The personalised `.torrent`, by the numeric `id` of a search row                          | **used**, not captured  |
| `POST /api/v1/torrents/upload`                  | Multipart upload: `file`, category id, `anonymousUpload`, `nfo`; optional `imdbId`, `mediainfo`, `othergenre`, `firstpic`, `reqid`, `p2p`, `unrar`, `language`, `section` (`new` \| `archive`). A duplicate answers **409** `{error: "Duplicate", torrent_id, …}` | documented, not wired (K7) |
| `GET /api/v1/moviedata/imdb/{tt}`               | Film data by IMDb id                                                                     | documented, not wired   |
| `GET /api/v1/moviedata/guess?name=`             | Film data guessed from a release name                                                    | documented, not wired   |
| `GET /api/v1/moviedata/search?search=`          | Film data by text                                                                        | documented, not wired   |
| `GET /api/v1/moviedata/{id}`                    | Film data by site id                                                                     | documented, not wired   |

### Search parameters (as captured)

```
GET /api/v1/torrents?limit=100&index=0&page=search&section=all&sort=d&order=desc&dead=false
                    &searchText=<query>&categories[]=<ids>
```

| Parameter        | Value in the capture | Meaning                                                              |
| ---------------- | -------------------- | -------------------------------------------------------------------- |
| `searchText`     | `Inception`, `The Office` | Free text (the DESIGN notes an IMDb id may be prefixed into it) |
| `categories[]`   | see § Categories     | Category ids                                                         |
| `limit`, `index` | `100`, `0`           | Page size and offset; the TV capture returned exactly 100 rows, so it was **cut by the limit** |
| `page`           | `search`             | Constant                                                             |
| `section`        | `all`                | `new` \| `archive` \| `all`; both occur in the rows                  |
| `sort`, `order`  | `d`, `desc`          | By date, newest first                                                |
| `dead`           | `false`              | Hide torrents with no seeder                                         |

The rate limit is **not published**; the planned client uses the defensive profile of the family (15 s timeout,
3 attempts, circuit 5 failures / 300 s, 0.5 req/s).

---

## Search response

A plain JSON **array**, one object per torrent (`search-movie.json`: 20 rows; `search-tv.json`: 100 rows). Fields of
a row, as captured:

| Field                         | Meaning / mapped to (planned)                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------------------------ |
| `id`                          | Numeric torrent id → `tracker_id`, and the `{id}` of the download path                           |
| `name`                        | The release name → `title` (the shared title parser reads quality tokens from it)                |
| `title`, `year`               | The work's title and year, as the site matched them (not the release name)                       |
| `category`                    | Category id (§ Categories)                                                                       |
| `size`                        | Bytes                                                                                            |
| `added`                       | `yyyy-MM-dd HH:mm:ss`, **no zone** → `upload_date` (zone assumed +02:00 by the DESIGN, unverified) |
| `seeders`, `leechers`, `times_completed` | Swarm counters                                                                |
| `frileech`                    | `1` = freeleech (34 of the 100 TV rows, 9 of the 20 movie rows) → `is_freeleech`                  |
| `imdbid2`                     | The `tt…` IMDb id; `imdbid` is the site's own numeric film id                                    |
| `type`, `numfiles`, `pack`    | `single` / `multi`, file count, pack flag (`pack` was `0` even in category 12 « PACKS » rows)     |
| `section`                     | `new` or `archive`                                                                               |
| `language`                    | Free text declared at upload (`english`, `polish`, `french`, …) or `null` — see § Language       |
| `cast`, `tagline`, `genres`, `rating`, `photo`, `firstpic` | Film metadata and artwork flags; unused                             |
| `p2p`, `unrar`, `3d`, `nuked`, `audioid`, `reqid`, `othergenre`, `preDate`, `comments` | Upload flags and counters; unused (`preDate` is `0000-00-00 00:00:00` when unset) |

**There is no info hash** in a row, and no download URL: the client builds the **relative** path
`/api/v1/torrents/download/{id}` itself (DESIGN § 3.3). With header auth an absolute URL read from a response would
send the key to whatever host it names.

---

## Categories

Ids from the FAQ. The planned client searches the film and series sets only.

| Group  | Ids                                                                                                              |
| ------ | ---------------------------------------------------------------------------------------------------------------- |
| Movies | 1 DVDR, 2 SD, 3 BluRay, 4 2160p, 5 720p, 6 1080p, 7 PACKS, 38 Bluray/UHD                                         |
| TV     | 8 720p, 9 1080p, 10 SD, 11 DVDR, 12 PACKS, 13 2160p, 14 BluRay, 15 SPORTS                                        |
| Other  | 17 Unknown; Apps 18 0DAY, 20 PC, 21 Mac, 33 Tutorials; Music 22 MP3, 23 FLAC, 24 MTV, 29 PACKS, 39 DVD, 40 Bluray; Games 25 PC, 26 Consoles, 27 Mac, 42 XXX, 43 ROMS; 28 Ebooks, 44 Audiobooks; XXX 30–37, 41 |

There is **no anime and no documentary class**, and no per-kind split: every film kind maps to the movie ids, every
series kind to the TV ids (DESIGN § 3.5).

### What `index.json` shows for `categories[]`

`index.json` records the request line of each capture. It prints the category filter as **one bracketed value**:
`categories[]=[1, 2, 3, 4, 5, 6, 7, 38]` (movies) and `categories[]=[8, 9, 10, 11, 12, 13, 14, 15]` (TV) — a single
`categories[]` parameter whose value is the string `[1, 2, …]`, not one `categories[]=1&categories[]=2…` pair per id.

Whether the tracker applied it is **not proven**. Every 200 answer is consistent with a filter that worked: the movie
rows carry only categories 4, 5, 6, 38 and the TV rows only 8, 9, 10, 12, 13 — none outside the requested sets. But a
text search for « Inception » or « The Office » would land mostly in those categories anyway, so the capture cannot
tell « applied » from « ignored ». Reported, not fixed: `scripts/capture-tracker-sample.py` is out of this document's
scope. Phase 4 should send one `categories[]` per id, as the DESIGN's request shape says, and test it against a
query that would otherwise match another category.

---

## Blocked for normal keys

The FAQ is explicit: a normal API key **cannot** reach torrent detail, comments, peers, the snatch log, **profile
data**, the mailbox, admin functions or edits.

Consequence, for the DESIGN's T-1: **no account-statistics endpoint exists for digitalcore.** The ratio, the volumes
and the Hit-and-Run count are UNKNOWN in TorrentMate (T-1 = A). The client does not claim `AccountStatsReadable`, and
the ratio is never computed locally or scraped from the site's pages unless the operator orders it for this tracker
(T-1 = B).

---

## Economy

All from the rules and the FAQ; nothing here is verified by a capture.

- **Ratio** = uploaded / downloaded. **Required ratio 0.5**: below it, the account enters a **5-day ratio watch**; if
  it is not back above 0.5 by then, leeching is revoked (the account stays enabled).
- **HIT AND RUN**: a torrent downloaded to **10 % or more** must be seeded **5 days** *or* until its ratio reaches
  **1:1**, whichever comes first. A torrent not announced for an hour during that period shows as a HIT AND RUN.
  **Freeleech is not exempt.** Only successful announces count; the site's timer is the source of truth.
- **To fix**: **10 days** to seed it back; after that, the mark can still be removed at a price (points, upload
  credit or a donation).
- **Sanctions**: **5** marks ⇒ a warning; **more** ⇒ a **download ban** until they are fixed. The removal list is
  cleaned periodically.

For the config's `economy` block (DESIGN T-4): `min_ratio` = 0.5, `min_seed_time` = 5 days, `hit_and_run_grace` = 10
days are the site's figures; the ratio target stays the operator's choice. These replace the older public hint
« ratio 1.0, seed 5 days » of the Jackett definition, which the site's own pages contradict.

Because TorrentMate cannot read this account's marks, the 5-day seed is a rule the engine must **respect by design**
(never remove a digitalcore torrent younger than 5 days or below 1:1), not a state it can check.

---

## Rules that affect grabbing

- **Cross-seed is explicitly allowed.** The tracker rewrites `announce`, `source` and `private` on upload, so a
  cross-seeded torrent is a new `.torrent` of the site's, never the original file. The DESIGN's cross-seed engine
  searches candidates by release name and verifies them by the downloaded `.torrent`'s file layout; with no info
  hash in the answer, that download is the only check, bounded by the engine's daily quota.
- **`.torrent` files are personal**: never shared, never re-hosted (debrid services included), and **no extra
  trackers, no DHT, no PEX** — a client adding one risks the account. One account per lifetime.
- **Scene-oriented**: English, 0-day, scene-style release names (`Title.Year.1080p.WEB-DL.DDP5.1.H.264-GROUP`).

### Language

« digitalcore n'est pas un tracker français » (the operator's word). Its releases **rarely carry French audio**:
French audio is **never assumed** from this tracker. The language is read from the **release name tags**
(`MULTi`, `FRENCH`, `VOSTFR`, `DUAL`, …) or from its **mediainfo**, as for any tracker. The row's `language` field
is free text declared by the uploader and was `null` on 12 of the 20 movie rows (`english` on the others); the
TV capture mixes `english`, `polish` and some `french` rows, so it is not a substitute for the name tags. The value
of this tracker for a French library is its VO and MULTI releases and its cross-seed.

---

## IRC announces

`irc.digitalcore.club`, TLS port 7000, channel `#announce` — read by autobrr. Not used by TorrentMate.

---

## Known errors

| Symptom                              | Cause / fix                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------ |
| `401`, « Authentication Required: … » | No valid key sent, or a wrong one. The JSON body is a bare string.                  |
| Connection refused / times out       | The site is hosted in Russia and blocks many VPN addresses; use the official proxy.  |
| `409` `{error: "Duplicate", …}`      | Upload only: the torrent already exists (`torrent_id` names it).                     |
| Downloads refused / leeching revoked | Ratio under 0.5 after the 5-day watch, or a download ban from HIT AND RUN marks.     |

---

## Not in this repo

- No secret of any kind: this document quotes **no** API key, passkey or announce URL.
- Samples: `docs/reference/_samples/digitalcore/` — `error-auth.json`, `search-movie.json`, `search-tv.json` and the
  `index.json` listing request, status and auth of each; recorded 2026-10-04 by
  `scripts/capture-tracker-sample.py digitalcore` with the key as header `X-API-KEY` (the key never appears in a
  URL, so nothing needed redacting there). They are the fixtures the future `test_digitalcore_client.py` will parse.
- **Not captured**: the download endpoint (a `.torrent`, so the announce host stays unknown), the empty answer, and
  every endpoint other than the search.
