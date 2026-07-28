# Tr4ker API Reference

Tracker: **TR4KER** (private French tracker, multi-content).
Base URL: `https://tr4ker.net`
Client: `personalscraper/api/tracker/tr4ker.py` — a **named config of the generic
Torznab client** (`api/tracker/torznab.py`), not a bespoke implementation. See
`c411-api.md` for the first config of that same engine.
Source material: the tracker's own wiki pages (Prowlarr/Radarr/Sonarr, cross-seed,
RSS, community + upload rules, naming conventions), distilled here. **The raw
capture is deliberately not kept in the repo: it contained a live passkey.**

---

## Scope

The pipeline consumes the **Torznab search** endpoint only.

| Capability   | Endpoint                      | Used by                                         |
| ------------ | ----------------------------- | ----------------------------------------------- |
| Search       | `GET /api/torznab?t=search`   | `Tr4kerClient.search()` → `list[TrackerResult]` |
| Movie search | `GET /api/torznab?t=movie`    | idem (`media_type="movie"`)                     |
| TV search    | `GET /api/torznab?t=tvsearch` | idem (`media_type="tv"`)                        |
| Categories   | `GET /api/torznab?t=caps`     | `Tr4kerClient.get_categories()` → `dict`        |
| Cross-seed   | `GET /api/torznab/all`        | **documented, NOT wired** (see below)           |
| RSS feeds    | `GET /api/rss?passkey=…`      | **documented, NOT wired** (freeleech radar R1)  |

---

## Auth

Tr4ker is natively Torznab, so the search API authenticates with a key in the
**query string**, never a header.

| Item             | Value                                                            |
| ---------------- | ---------------------------------------------------------------- |
| Method           | `apikey=<secret>` query parameter (`AuthMode.API_KEY_QUERY`)     |
| Env var (gating) | `TR4KER_PASSKEY` — the single secret, per this host's convention |
| Activation       | `PROVIDER_CREDS["tr4ker"] = ["TR4KER_PASSKEY"]`                  |
| Transport        | `ApiKeyAuth(key, param="apikey", location="query")`              |

**One variable, two upstream notions — read this before debugging a 401/100.**
The tracker's own documentation distinguishes two secrets:

- the **profile API key** (Mon compte → Paramètres), which its wiki says Torznab
  search wants;
- the **announce passkey**, which authenticates the RSS feeds.

This codebase follows the operator convention of a single `<TRACKER>_PASSKEY`
variable per tracker and sends whatever it holds as `apikey=`. If a live search
ever answers

```xml
<error code="100" description="Invalid API Key"/>
```

the fix is to put the **profile API key** into `TR4KER_PASSKEY` — not to add a
second environment variable. `TR4KER_USERNAME` / `TR4KER_PASSWORD` in the
operator `.env` are leftovers from a decommissioned login-style tracker and are
read by no code.

---

## Endpoints

```
GET /api/torznab?t=search&q=<query>&apikey=<secret>
GET /api/torznab?t=movie&q=<query>&apikey=<secret>
GET /api/torznab?t=tvsearch&q=<query>&apikey=<secret>
GET /api/torznab?t=caps&apikey=<secret>
```

| API path           | Purpose                                                                     |
| ------------------ | --------------------------------------------------------------------------- |
| `/api/torznab`     | Search — the path this client uses.                                         |
| `/api`             | Zero-config alias (Prowlarr's default). Serves the same Torznab document.   |
| `/api/torznab/all` | Full catalog **including 0-seeder torrents** — cross-seed matching surface. |

The upstream page is internally inconsistent about `/api/torznab`: a table row
labels it "déprécié pour Prowlarr / Radarr / Sonarr" while the summary line and
the troubleshooting section both tell you to use exactly that path (or the `/api`
alias). Both work; switching the client is a one-field change
(`TR4KER_DESCRIPTOR.api_path`).

`/api/torznab/all` is **documented but not wired**: the existing cross-seed
service is untouched by this feature. Wiring it would mean a second descriptor
(or a per-capability path) — deliberately out of scope.

---

## Search response

Standard Torznab RSS. What the generic parser reads:

| Field                                | Mapped to                                               |
| ------------------------------------ | ------------------------------------------------------- |
| `<title>`                            | `title` (+ quality tokens by regex)                     |
| `<guid>`                             | `tracker_id`, and `info_hash` fallback                  |
| `<size>`                             | `size`                                                  |
| `<enclosure url= length=>`           | `download_url`, size fallback                           |
| `<comments>` / `<link>`              | `source_url`                                            |
| `<pubDate>`                          | `upload_date` (RFC 2822)                                |
| `torznab:attr[seeders]` / `[peers]`  | `seeders`, `leechers = max(0, p − s)`                   |
| `torznab:attr[downloadvolumefactor]` | `is_freeleech` (=0), `is_silverleech` (=0.5)            |
| `torznab:attr[category]`             | `category`                                              |
| `torznab:attr[infohash]`             | `info_hash`                                             |
| `torznab:attr[tmdbid]`               | `tmdb_id` → the TMDB identity hard-filter (anti-remake) |

No per-torrent detail endpoint exists (Torznab has none), hence the client
implements neither `TorrentDetailsProvider` nor `FreeleechAware`: the freeleech
state is the one captured at search time.

**Descriptor quirks, unverified until the first real search**:
`item_category_element=False` and `guid_is_infohash=True` carry the Torznab norm
(what C411 does). If a live capture shows `<category>` elements or a URL-shaped
`<guid>`, flip the flag in `TR4KER_DESCRIPTOR` — the parser needs no change.

---

## Rate limits

The tracker publishes no numeric quota, only a qualitative rule: stay reasonable
on concurrent requests, and a burst may return a temporary error ("retry after a
few seconds"). The client therefore reuses C411's defensive profile:

| Setting    | Value                       |
| ---------- | --------------------------- |
| Timeout    | 15 s                        |
| Retry      | 3 attempts                  |
| Circuit    | 5 failures / 300 s cooldown |
| Rate limit | 0.5 req/s                   |

---

## RSS feeds (not wired — freeleech radar R1)

```
GET /api/rss?passkey=<passkey>                 # 100 latest torrents
GET /api/rss?passkey=<passkey>&freeleech=1     # freeleech only
GET /api/rss?passkey=<passkey>&cat=<slug>      # one category
```

Each feed returns the **100 most recent** entries and authenticates with the
**announce passkey** (not the API key). This is the surface a future freeleech
radar (R1, ticket #168) would poll.

### Category slugs (RSS side only)

These slugs belong to the RSS API. They are **not** Torznab `cat=` values, so
`TR4KER_DESCRIPTOR.search_categories` is deliberately empty — no caps document
has been captured yet, and inventing Newznab ids would silently return nothing.

| Group         | Slugs                                                                                                                            |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Films         | `films`, `films-film`, `films-animation`, `films-documentaire`, `films-concert`, `films-spectacle`, `films-sport`, `films-video` |
| Séries        | `series`, `series-tv`, `series-emission`, `series-animees`, `series-manga`, `series-sport`                                       |
| Audio         | `audio`, `audio-musique`, `audio-podcast`                                                                                        |
| Livres        | `livres`, `livres-livre`, `livres-audio`, `livres-bd`, `livres-manga`, `livres-presse`, `livres-jdr`, `livres-autres`            |
| Applications  | `applications`, `apps-windows`, `apps-linux`, `apps-macos`, `apps-android`, `apps-autres`                                        |
| Jeux vidéo    | `jeux-video`, `jeux-pc`, `jeux-linux`, `jeux-macos`, `jeux-xbox`, `jeux-nintendo`, `jeux-playstation`                            |
| Émulation     | `emulation`, `emulation-rom`, `emulation-emulateurs`                                                                             |
| Impression 3D | `impression-3d`, `3d-personnages`, `3d-objets`, `3d-pack`                                                                        |
| Formations    | `formations`, `formations-video`, `formations-audio`, `formations-papier`                                                        |
| Divers        | `nulled`, `nulled-wordpress`, `nulled-scripts`, `nulled-divers`, `autres`                                                        |
| Adulte        | `porno`, `porno-films`, `porno-images`, `porno-jeux`, `porno-ebooks`, `porno-hentai`, `porno-fansites`                           |

---

## Cross-seed (documented, not wired)

The tracker recommends its full catalog endpoint for cross-seed tooling, because
it includes 0-seeder torrents and therefore maximises matches:

```
https://tr4ker.net/api/torznab/all?apikey=<secret>
```

Either pointed at directly by `cross-seed`, or added to Prowlarr as a "Generic
Torznab" indexer with API path `/api/torznab/all`. Matching is byte-exact: a
different encode, team or re-mux is a different file and cannot cross-seed.
`personalscraper`'s own cross-seed service does **not** use this endpoint today.

---

## Operational rules that affect grabbing

Distilled from the community/upload pages — the parts that change what the
pipeline can expect to find or do:

- **Ratio gate**: a ratio that is too low makes the tracker refuse downloads,
  including those issued by an automation stack. A grab failing with an auth-ish
  error while the key is valid is worth checking against the account ratio.
- **Freeleech**: purchasable per-account with site credits (earned by seed time,
  filling requests, badges), on top of per-torrent freeleech. Freeleech is
  exposed on search results through `downloadvolumefactor`.
- **Ratio-cheating** (fake upload clients) is a permanent-ban offence, detected
  automatically — never point a modified client at this tracker.
- **One account per person**; multi-account detection closes every linked
  account and blocks the IP.
- **Archives (ZIP/RAR/7z) are forbidden** for uploads, so grabbed releases should
  normally arrive as plain folders/files (the pipeline's RAR extraction stays
  useful for other sources).
- **Episode-by-episode uploads of an already-finished season are forbidden** —
  expect season packs for completed seasons, per-episode releases only for
  airing ones.
- **Forbidden sources**: CAM, TELESYNC, HDTS, watermarked releases; accepted
  containers MKV/MP4/AVI/ISO (Blu-Ray only), codecs x264/x265/AV1.

### Release naming (matters for title parsing + ranking)

Movies (also documentaries, animation, concerts, shows, sport):

```
Title.Year.[Edition].Language.[CustomFormats].Resolution.[Source].[BitDepth].[3D].[HDR].AudioCodec.Channels.VideoCodec-[Group]
The.Dark.Knight.2008.MULTi.VFF.1080p.Bluray.10bits.HDR10.TrueHD.Atmos.7.1.x265-TR4KER
```

Series (TV, animated, manga):

```
Show.Name.SxxExx.[Episode.Title].[Edition].Language.Resolution.[Source].VideoCodec-[Group]
Breaking.Bad.S01E01.FRENCH.1080p.WEB.DL.x264-GRP
```

- `SxxExx` is always zero-padded to two digits; `S01E01E02` for multi-episodes,
  `S01` for a full season, `Complete` for a finished show.
- TV shows / dailies: `Show.Name.YYYY.MM.DD.[Guest].Language.Resolution.Source.VideoCodec.Group`.
- Sport: `League.YYYY.MM.DD.Event.Name.Language.Resolution.Source.VideoCodec.Group`.
- Language tokens: `FRENCH`, `TRUEFRENCH`, `MULTi(.VFF/.VFQ/.VOF/.VFI)`, `VOSTFR`,
  `VF`, `VO`, `ENGLISH` — the audio hard-filter parses these from the title.
- Resolutions `8K`/`4K`/`2160p`/`1080p`/`720p`/`576p`/`480p`/`SD`; codecs
  `x265`/`H265`/`x264`/`H264`/`AV1`/`XviD`/`VC.1`/`VP9`/`MPEG2`; HDR tokens
  `DV`, `HDR10`, `HDR10+`, `HLG`; bit depth `10bits`/`12bits`.
- Content with **no French audio and no French subtitles** goes to the VO
  category with the same naming rules.

---

## Known errors

| Symptom                          | Cause / fix                                                                           |
| -------------------------------- | ------------------------------------------------------------------------------------- |
| `<error code="100" …>`           | Wrong secret — see the auth note above (profile API key vs passkey).                  |
| "Doctype unexpected"             | The API path is wrong (a normal HTML page was fetched). Use `/api/torznab` or `/api`. |
| Connection fails, key is correct | ISP DNS blocking the API host — switching resolvers usually fixes it.                 |
| Whitespace around the key        | A leading/trailing space in the env var silently breaks auth.                         |
| Downloads refused                | Account ratio too low (tracker-side gate, not an API error).                          |
| `410` via Prowlarr               | Wrong indexer id in the Prowlarr URL (Prowlarr is usually plain `http://`).           |

---

## Not in this repo

- No secret of any kind: this document quotes **no** passkey, API key or account
  identifier. The raw wiki capture that did was deleted with the feature.
- No sample capture yet: `docs/reference/_samples/tr4ker/` does not exist until a
  real controlled search is run (feature acceptance criterion ACC-03). The unit
  tests therefore exercise the Tr4ker client against the C411 Torznab capture —
  same protocol, different tracker — rather than a fabricated sample.
