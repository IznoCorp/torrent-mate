# Draupnirr API Reference

Tracker: **draupnirr.xyz** (private French tracker, multi-content; formerly Yggrasil).
Base URL: `https://draupnirr.xyz`
Client: **does not exist yet.** It is phase 2 of `docs/features/backend-bricks/trackers-t1/DESIGN.md`
(`personalscraper/api/tracker/draupnirr.py`, planned as a named config of the generic Torznab client
`api/tracker/torznab.py`, like `tr4ker`). Nothing in `personalscraper/` or `config*/` knows draupnirr today; this
document is the reference that phase builds from.
Source: the tracker's members' wiki, read 2026-10-04 (slugs `a-propos`, `api`, `clients-annonce`, `hit-and-run`,
`ratio-economie`, `regles-generales`, `creer-son-torrent`), plus the five redacted captures of
`docs/reference/_samples/draupnirr/` recorded the same day. Facts are paraphrased. Where the wiki and a capture
disagree, the capture wins; where only the wiki speaks, the fact is marked "wiki".

---

## Scope

draupnirr is natively Torznab, like tr4ker, and also serves a JSON API. The planned client will use only:

| Capability      | Endpoint                         | Used by (planned)                                      |
| --------------- | -------------------------------- | ------------------------------------------------------ |
| Search          | `GET /torznab/api?t=search`      | `DraupnirrClient.search()` → `list[TrackerResult]`     |
| Movie search    | `GET /torznab/api?t=movie`       | idem (`media_type="movie"`)                            |
| TV search       | `GET /torznab/api?t=tvsearch`    | idem (`media_type="tv"`)                               |
| Categories      | `GET /torznab/api?t=caps`        | `get_categories()`                                     |
| Grab            | `GET /torznab/download/{id}`     | the `enclosure` URL of each result, via `resolve_source` |
| Account stats   | `GET /api/me`                    | `account_stats()` (T-1, phase 5) — **no capture yet**  |

Everything else in the Endpoints section is **documented, not wired**.

---

## Auth

**One secret.** The passkey is the API key everywhere: Torznab, upload and JSON reads all accept it, and it is also
the last segment of the announce URL. There is no separate profile API key (unlike tr4ker). It is shown and rotated
on the profile page; a rotation kills the old value at once and every `.torrent` already downloaded must be fetched
again, since each one embeds the passkey.

| Item        | Value                                                                                    |
| ----------- | ---------------------------------------------------------------------------------------- |
| Env var     | `DRAUPNIRR_API_KEY` — the same value as `DRAUPNIRR_PASSKEY` (both names hold the one secret) |
| Other env   | `DRAUPNIRR_API_URL`, `DRAUPNIRR_ANNOUNCE_URL` (the operator's `.env`)                    |
| Activation  | `PROVIDER_CREDS["draupnirr"] = ["DRAUPNIRR_API_KEY"]` (planned)                          |
| Transport   | `ApiKeyAuth(key, param="apikey", location="query")` (planned)                            |

Accepted forms, per surface:

| Surface                | Query `?apikey=` | Header `X-Api-Key` | Form field `apikey` |
| ---------------------- | :--------------: | :----------------: | :-----------------: |
| Torznab (`/torznab/*`) | yes              | not documented     | —                   |
| JSON reads (`/api/*`)  | yes              | yes                | —                   |
| Upload (`POST /api/upload`) | —           | yes                | yes                 |

The planned client sends the query parameter, as for the other Torznab trackers.

A wrong key has two shapes (see Errors): the Torznab surface answers **HTTP 200** with an XML `<error code="100"/>`,
the JSON surface answers **401**. The Torznab one is captured; the JSON one is wiki-only.

---

## Endpoints

| Method + path                                  | Purpose                                                              | Status          |
| ---------------------------------------------- | -------------------------------------------------------------------- | --------------- |
| `GET /torznab/api?t=caps`                      | Capabilities and category tree                                       | **used**        |
| `GET /torznab/api?t=search\|tvsearch\|movie`   | Torznab search (`q`, `cat`, `limit` ≤ 100 default 50, `offset`)      | **used**        |
| `GET /torznab/api?t=music\|book`               | Torznab search, music / books                                        | not wired       |
| `GET /torznab/download/{id}?apikey=`           | Personalised `.torrent` (the item's `enclosure`)                     | **used**        |
| `GET /api/me`                                  | Account statistics — see below                                       | **used** (phase 5), no capture yet |
| `GET /api/me/missions`, `GET /api/me/badges`   | Missions and badges                                                  | documented, not wired |
| `GET /api/shop`                                | Credit shop                                                          | documented, not wired |
| `GET /api/categories`                          | `[{slug, name, requires_moderation}]` — the upload category slugs    | documented, not wired |
| `GET /api/torrents?q&category&limit&offset`    | JSON search (`limit` ≤ 100); entries carry `id`, `infohash`, `name`, `category`, `status`, `size_bytes`, `seeders`, `leechers`, `uploader` (nullable), `created_at`, `download_url` | documented, not wired |
| `GET /api/torrents/{sqid\|infohash}`           | One torrent: the summary plus `file_count`, `description`, `meta{tags, year, tmdb_id, tmdb_type, synopsis}`. 404 unknown, 422 malformed id | documented, not wired |
| `GET /api/torrents/{id\|infohash}/download?apikey=` | Personalised `.torrent`; 403 `ratio too low`, 403 `awaiting media verification` | documented, not wired |
| `POST /api/upload`                             | Multipart upload (`.torrent` ≤ 10 MB, category slug, nfo, mediainfo, `meta[...]`); 201 `{id, infohash, status approved\|pending, awaiting_validation}` | documented, not wired (K7) |

Notes:

- The torrent `id` is an **opaque sqid** (`afFcAL5twO` in the captures). Numeric ids are refused on purpose
  (anti-enumeration). An infohash (40 hex) is accepted wherever an id is.
- Moderated torrents never appear in Torznab results.
- **Prowlarr**: a "Generic Torznab" indexer, URL `https://draupnirr.xyz/torznab`, API path `/api`. The site states
  explicitly that it is **not** a Jackett indexer. The path the planned client uses is `/torznab/api`.

### `GET /api/me` — account statistics (T-1)

Answers the T-1 question of the DESIGN for draupnirr. Authenticated by `?apikey=` or `X-Api-Key`. All volumes are in
**bytes**.

| Field                | Meaning                                                                    |
| -------------------- | -------------------------------------------------------------------------- |
| `name`, `class`      | Account name and user class                                                |
| `credits`            | Credit balance (the site's "gouttes")                                      |
| `invites`            | Invitations left                                                           |
| `freeleech_until`    | End of a personal freeleech (purchased in the shop), when active           |
| `uploaded`           | Raw uploaded volume                                                        |
| `downloaded`         | Downloaded volume                                                          |
| `bonus_upload`       | Upload volume bought in the shop, counted in the ratio                     |
| `ratio`              | **`(uploaded + bonus_upload) / downloaded`**; `null` means infinite        |
| `seedtime_seconds`   | Cumulated seed time                                                        |
| `uploads_count`      | Torrents uploaded                                                          |
| `hnr_count`          | Torrents currently marked HIT AND RUN                                      |
| `badges[]`           | Badges held                                                                |

Two traps for the future `account_stats()`: the ratio is **not** `uploaded / downloaded` (it includes
`bonus_upload`), and `null` is a valid ratio meaning infinite — it must not be read as "unknown". The tracker's own
`ratio` is the figure to report; never recompute it locally. **No capture of this endpoint exists yet**; it is owed
at phase 5, so the field list above is the wiki's, unverified against a real answer.

---

## Search response

Standard Torznab RSS (`newznab:response offset= total=`), verified against `search-movie.xml` (3 items,
`t=movie&q=Inception`) and `search-tv.xml` (4 items, `t=tvsearch&q=The Office`).

| Field                                | Mapped to (planned)                                         |
| ------------------------------------ | ----------------------------------------------------------- |
| `<title>`                            | `title` (+ quality tokens by regex)                         |
| `<guid isPermaLink="false">`         | `tracker_id` — the text is `ygrasil-<infohash>` (see quirks) |
| `<size>` / `<enclosure length=>`     | `size`                                                      |
| `<enclosure url=>` / `<link>`        | `download_url` (carries the key)                            |
| `<comments>`                         | `source_url` (`https://draupnirr.xyz/torrents/{id}`)        |
| `<pubDate>`                          | `upload_date` (RFC 2822, `+0000`)                           |
| `torznab:attr[seeders]` / `[peers]`  | `seeders`, `leechers = max(0, peers − seeders)`             |
| `torznab:attr[downloadvolumefactor]` | `is_freeleech` (=0), `is_silverleech` (=0.5)                |
| `torznab:attr[category]`             | `category`                                                  |
| `torznab:attr[infohash]`             | `info_hash`                                                 |
| `torznab:attr[tmdbid]`               | `tmdb_id` → the TMDB identity hard-filter (anti-remake)     |

Also published and not read: `files`, `grabs`, `leechers`, `uploadvolumefactor` (`1` on every captured item),
`minimumseedtime`.

**Descriptor quirks — read from the captures** (the planned descriptor must set them from this, not guess):

| Quirk                   | Verdict | Evidence                                                                                          |
| ----------------------- | ------- | ------------------------------------------------------------------------------------------------- |
| `item_category_element` | `False` | Items carry no `<category>` element; categories are `torznab:attr name="category"`, repeated 2–3 times (e.g. `2040`, `2000`, `100002`: resolution sub-tag, root, site sub-category). |
| `guid_is_infohash`      | `False` | `<guid isPermaLink="false">ygrasil-b9e291bf…</guid>` — the infohash with a legacy `ygrasil-` prefix, not a raw hash. The raw hash is `torznab:attr name="infohash"`, present on all 7 captured items. |
| `tmdbid`                | partial | Present on 6 of 7 items; a result without it must fall back to the title parser, not be dropped. |
| `minimumratio`          | absent  | Never emitted in the captures (the wiki's enforcement is off, or not per-torrent).               |
| `minimumseedtime`       | `172800`| Every item: 172 800 s = 48 h, matching the HIT AND RUN rule below.                               |

Two behaviours worth knowing before writing tests: every captured item had `downloadvolumefactor` `0` (all
freeleech at capture time, a fact of that day, not a rule), and the `t=tvsearch&q=The Office` capture returned a
**film-category** item (`2040`) among series — the site classifies by its own taxonomy, so the category of a result
must come from its attrs, not be assumed from the search function used.

---

## Categories

Root ids from `caps.xml`: **2000** Films, **5000** Séries, 3000 Musique, 4000 Logiciels, 4050 Jeux, 7000 Livres,
8000 Autres. Sub-categories come in two families:

- **Resolution sub-tags** (standard Newznab ids): films `2030` SD / `2040` HD / `2045` UHD; series `5030` / `5040` /
  `5045`, plus `5060` Sport and `5070` Animation.
- **Site sub-categories**, ids from `100000` up, read from `t=caps` and not stable to hard-code. For the two roots the
  pipeline cares about: films `100002` Film, `100003` Documentaire, `100004` Animation, `100005` Concert / Spectacle,
  `100012` Film VO, `100043` Disques complets; series `100007` Série TV, `100008` Série animée, `100009` Émission,
  `100010` Séries › Sport, `100013` Série VO, `100044` Disques complets. (The labels are the site's French UI names.)

Search capabilities from `caps.xml`: `limit` max 100, default 50; `search` takes `q, cat`; `tvsearch` takes
`q, season, ep, imdbid, tmdbid`; `movie` takes `q, imdbid, tmdbid`; no `tvdbid`. The DESIGN keeps search by title
(an id search is out of scope), so `imdbid` / `tmdbid` stay unused.

---

## Rate limits

Published per surface (wiki); `429` means slow down.

| Surface                          | Limit                                               |
| -------------------------------- | --------------------------------------------------- |
| Torznab                          | 120 req/min per key                                 |
| JSON reads (`/api/*`)            | 120 req/min per key and 300 req/min per IP, the IP bucket **shared with Torznab** |
| Upload                           | 30 req/min per IP                                   |
| Announce                         | 60/min per key + IP                                 |

The planned client stays well under the Torznab figure with the defensive profile of the other trackers:

| Setting    | Value                       |
| ---------- | --------------------------- |
| Timeout    | 15 s                        |
| Retry      | 3 attempts                  |
| Circuit    | 5 failures / 300 s cooldown |
| Rate limit | 0.5 req/s (30/min)          |

---

## Errors

| Surface  | Wrong key                                                                                    | Evidence             |
| -------- | -------------------------------------------------------------------------------------------- | -------------------- |
| Torznab  | **HTTP 200**, body `<error code="100" description="Invalid API key"/>`                       | `error-auth.xml` (captured with a bad key on `t=tvsearch`) |
| JSON     | HTTP 401 `{"error":"invalid api key"}`                                                       | wiki                 |

The Torznab case is the one that bites: the status is 200, so a client that trusts the status reads an empty result.
The planned client must map a root `<error/>` with code `100` to `TrackerAuthError` (DESIGN § 3.1 makes the phase
prove it). The other Torznab code is `202` (unsupported function).

| Symptom                                   | Cause / fix                                                                    |
| ----------------------------------------- | ------------------------------------------------------------------------------ |
| Download 403 `ratio too low`              | Account ratio under the gate — see Economy. Not an API fault.                  |
| Download 403 `awaiting media verification`| The release is still waiting for the site's media bot. Retry later.            |
| `429`                                     | A bucket is exhausted; back off.                                               |
| `404` on `/api/torrents/{id}`             | Unknown torrent — which is also how the site tells you "safe to upload".       |
| `422` on `/api/torrents/{id}`             | Malformed id (a numeric id is refused).                                        |
| Old `.torrent` stops announcing           | The passkey was rotated; re-download.                                          |

**Announce refusals** come back as a bencoded failure reason: unknown key, account disabled, client not allowed,
ratio too low, release awaiting media verification.

---

## Economy

All from the wiki (`ratio-economie`, `hit-and-run`); nothing here is verified by a capture.

- **Ratio** = (uploaded + shop bonus) / downloaded. Transfer is counted at each announce (about every 5 minutes), at
  the source.
- **Floor 0.4**: under a ratio of 0.4 with more than **5 GB downloaded**, new downloads can be blocked — only **when
  enforcement is switched on**, which the wiki presents as a toggle, not a permanent state.
- **Credits ("gouttes")**: seeding earns about 0.5–3 per hour per torrent (more for big, rare — 3 seeders or fewer —
  or older, over 7 days, torrents; the top 10 earn the full rate, the rest decreasing); +25 per approved upload; missions
  add more.
- **Shop**: upload packs of +10 / +50 / +200 GB (they feed `bonus_upload`, hence the ratio), and personal freeleech
  for 24 h or 7 days.
- **Freeleech** spares the ratio but **not** the seed obligation.
- **HIT AND RUN**: after completing a torrent, seed **48 h cumulated** (not a window). A completed torrent with less
  than 48 h of seed **and** absent from the swarm for **7 days** is marked HIT AND RUN; it clears itself once
  re-seeded to 48 h. **No automatic sanction exists today**: staff can see the marks and say they may limit downloads
  later. Seed time is counted server-side.
- Own video uploads must keep seeding until the site's media bot verifies them; if nobody seeds, a mark follows the
  next day.
- **Ratio cheating** (modified clients) is a permanent ban; one account per person.

For the config's `economy` block (DESIGN T-4): `min_seed_time` = 48 h and a ratio floor of 0.4 are the wiki's figures;
`minimumseedtime` is also emitted per item (172 800 s in every capture), `minimumratio` is not.

---

## Cross-seed

- Every torrent on the site is **private** with the source tag **`DRAUPNIRR`**, so its infohash is its own: a torrent
  cross-seeded from another tracker is a new `.torrent` with this source tag, never the original file. The site
  welcomes cross-seeding, by "adoption" from a registered seedbox or by creating the `.torrent` by hand with source
  `DRAUPNIRR`. File layout is never renamed.
- **The release-name caveat.** For films and series the **published name is rewritten by the site's media bot** from
  the media's technical sheet (a canonical name), not taken from the torrent or folder name. The same release can
  therefore exist on draupnirr under a different name. The captures show names of very different styles for one work (`Inception.2010.HYBRID.VOSTFR.…-HiDt`, `Inception (2010) MULTi VFF … - QTZ.mkv`, `The Office US`), so
  no single scene-style name can be assumed.
- **What that means for TorrentMate.** The cross-seed engine searches each tracker **by release name**
  (`registry.search_candidates(item.name, media_type)`) and then verifies a candidate by fetching its `.torrent` and
  comparing the file layout. On draupnirr a name search can **miss an identical release**: a false negative that
  looks like "not on this tracker". The verification step is unaffected (layout is never renamed); only candidate
  discovery is. The info-hash shortcut does not help either: the hash differs per tracker, so
  `GET /api/torrents/{infohash}` cannot match another tracker's hash. Searching by `tmdbid` (6 of 7 captured items
  carry it) would be a way around, but the DESIGN keeps search by title, so for draupnirr the expectation is a lower
  cross-seed hit rate than on c411 / tr4ker, not an error to chase. Before an upload, the same lookup
  (`GET /api/torrents/{infohash}` → 404) is the site's dedup check.

---

## IRC announces

`irc.p2p-network.net:6697` (TLS), channel `#draupnirr-announces`, read by autobrr. Not used by TorrentMate.

---

## Not in this repo

- No secret of any kind: this document quotes **no** passkey, API key or announce URL carrying one.
- Samples: `docs/reference/_samples/draupnirr/` — `caps.xml`, `error-auth.xml`, `search-movie.xml`, `search-tv.xml`
  and the `index.json` listing request, status and auth of each; recorded 2026-10-04 by
  `scripts/capture-tracker-sample.py draupnirr`, every `apikey=` replaced by `REDACTED`. They are the fixtures the
  future `test_draupnirr_client.py` will parse and the evidence behind the quirk verdicts above.
- **Not captured yet**: `GET /api/me` (owed at phase 5 of the DESIGN) and every JSON endpoint other than that.
