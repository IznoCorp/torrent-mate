# trackers-t1 — three more tracker providers: v3x.club, draupnirr.xyz, digitalcore.club · DESIGN

A backend BRICK, drawn before the operator's « Go, design prêt » because nothing the maquette may still move shapes
it: a tracker provider is a protocol client behind the capability protocols `api/tracker/_contracts.py` already
declares. **Written 2026-10-01, on `main` at `fe3d2b012`. Nothing under `personalscraper/` or `config*/` was touched
to write it; no tracker was called — every fact below is public documentation or this repository.**

---

## 0. His words, and the rows this brick serves

- 2026-09-29 16:58 (`docs/features/maquette-l16bis/DESIGN.md` T1): « le but est d'en ajouter … notamment v3x.club et
  draupnirr.xyz, mais aussi digitalcore.club ».
- 2026-10-01 (the backend-bricks order): « on peut préparer déjà certains briques, SSO Plex, FCM, nouveaux tracker à
  ajouter, ... tout ce qui sera néccéssaire à la refonte et ne sera pas affecté par mes changements/adaptations/ajouts
  sur le design. »

| Brief row | What it asks | What this brick gives it |
| --- | --- | --- |
| `backend-brief.md` § 1.3 « three more trackers » (engine, § 18, L16-bis T1) | `v3x.club`, `draupnirr.xyz`, `digitalcore.club` as providers (search, grab, ratio, cross-seed), each with the `c411` block | three clients, registered like `c411` / `tr4ker`, with the `enabled` / `cross_seed` / `economy` block (§ 3) |
| § 2.3 `api/tracker/*` — adapt | « three more providers (T1) » | the same family, no new protocol layer; one new capability (account statistics, § 3.4) |
| § 6 K5 | `readTrackers`: « the ratio the TRACKER recognises » (NE-DOIT-PAS-1) | the provider-side read of that ratio, where the tracker publishes it (§ 3.4, T-1 = A) — UNKNOWN where it does not |
| § 6 K6 | the cross-seed engine attempts every eligible switched-on tracker | three more eligible trackers; the engine itself is K6's |

The maquette already draws the three as « composed » rows of the Trackers page (L16-bis § 4.3: `v3x.club` active,
`draupnirr.xyz` off by the operator, `digitalcore.club` off by failure). Their rows become real when K5 serves
`readTrackers`; this brick makes the providers exist behind it.

---

## 1. What exists today (measured)

| Fact | Command |
| --- | --- |
| Two tracker providers, both thin named configs of the generic Torznab client: `c411.py` (71 lines), `tr4ker.py` (104 lines); the protocol lives once in `torznab.py` (571 lines) | `wc -l personalscraper/api/tracker/*.py` |
| Adding a Torznab tracker = one `TorznabDescriptor` + one thin class + a `ProviderName` member + a `PROVIDER_CREDS` entry + one line in `_TRACKER_CLASSES` (`tr4ker.py` docstring, « DESIGN §3 D1 ») | `sed -n 1,40p personalscraper/api/tracker/tr4ker.py` |
| The capability protocols: `TorrentSearchable.search(query, media_type, year)`, `CategoryListable.get_categories()`, `FreeleechAware`, `TorrentDetailsProvider`, `TrackerConstructible.from_env(...)` — **no account / ratio capability** | `grep -n "class .*Protocol" personalscraper/api/tracker/_contracts.py` |
| Per-tracker config `TrackerProviderConfig {enabled, economy: TrackerEconomyConfig \| None, cross_seed}`; `economy = {target_ratio, min_ratio, min_seed_time, hit_and_run_grace}` — « the `c411` block » | `grep -n "class TrackerProviderConfig" -A14 personalscraper/conf/models/api_config.py` |
| **`ratio_state` has a reader and an upsert but NO caller writes it**: the ratio « the tracker recognises » is read from no tracker today, c411 and tr4ker included | `rg -n "ratio\.upsert\|RatioState\(" --type py personalscraper` → only `_store_rows.py:183` (the row mapper) |
| The grab and the cross-seed verification both download a `.torrent` through `resolve_source(result, transports)` → `HttpTransport.get_bytes(url)`, which uses an ABSOLUTE url verbatim and joins a relative one onto `base_url` | `sed -n 229,295p personalscraper/api/tracker/_fetch.py`; `grep -n "D10" personalscraper/api/transport/_http.py` |
| `ApiKeyAuth` sends a key as a query parameter OR a header (`location: "header" \| "query"`) | `sed -n 36,60p personalscraper/api/transport/_auth.py` |
| The cross-seed engine searches candidates BY RELEASE NAME on every managed tracker (`registry.search_candidates(item.name, media_type)`, D7) and verifies a candidate by fetching its `.torrent` and comparing the file layout | `sed -n 231,236p personalscraper/acquire/cross_seed.py` |
| Unit tests read recorded captures from `docs/reference/_samples/<tracker>/` (keys redacted); no live call in the suite | `grep -n _SAMPLES tests/unit/test_tr4ker_client.py`; `ls docs/reference/_samples/` |

### 1.1 What the three trackers are — public sources only

Sources: the Jackett definitions `v3x.yml`, `draupnirr.yml`, `digitalcore-api.yml`
(`https://raw.githubusercontent.com/Jackett/Jackett/master/src/Jackett.Common/Definitions/<name>.yml`), the same files in
`Prowlarr/Indexers` (`definitions/v11/`), autobrr's `digitalcore.yaml`, cross-seed.org's `basics/options.md`, and
each site's public landing page fetched once (no sign-in). CONFIRMED = read in one of those; UNKNOWN = not public.

| | **v3x.club** | **draupnirr.xyz** (formerly Yggrasil) | **digitalcore.club** |
| --- | --- | --- | --- |
| Platform | custom (Next.js front), API on `api.v3x.club`; French, private | Laravel application, French, « semi-private » (Jackett) | custom JSON API (« rartracker api v1 »), Nuxt front; English, scene / 0-day, private |
| Protocol | JSON: `GET https://api.v3x.club/indexer/search` | **native Torznab**: `GET https://draupnirr.xyz/torznab/api?t=search\|tvsearch\|movie` (+ `t=caps`) | JSON: `GET https://digitalcore.club/api/v1/torrents` |
| Auth | `apikey=` query parameter; a bad key → 401 | `apikey=` query parameter; a bad key → **HTTP 200** with Torznab `<error code="100"/>` | **header** `X-API-KEY` |
| Search parameters | `q`, `cat` (`2000,5000`), `tmdbid`, `season`, `ep`, `freeleech=0\|1`, `limit=100` | `q`, `cat`, `imdbid`, `tmdbid`, `limit` (no `tvdbid`) | `searchText` (an IMDb id is prefixed into it), `categories[]=…`, `limit`, `index`, `page=search`, `section=all`, `sort`, `order`, `dead`, … |
| Result fields | JSON `results[]`: `category`, `title`, `details`, `download`, **`infohash`**, `tmdbid`, `pubdate` (ISO 8601 UTC, per the 2026-10-04 capture), `size`, `seeders`, `leechers`, `grabs`, `downloadvolumefactor`, `uploadvolumefactor` | Torznab item: `title`, `comments`, `enclosure@url`, `pubDate`, `size`, `files`, `grabs`; attrs `category`, `imdb`, `tmdbid`, `seeders`, `leechers`, `downloadvolumefactor`, `uploadvolumefactor`, `minimumseedtime`, `minimumratio`; **`infohash` published** as a `torznab:attr` (2026-10-04 capture; `minimumratio` not seen in it) | JSON array: `id`, `category`, `name`, `size`, `added` (`yyyy-MM-dd HH:mm:ss`, zone assumed +02:00), `seeders`, `leechers`, `times_completed`, `frileech` (1 = freeleech), `imdbid2`, `year`, `pack`, …; **no infohash** |
| Grab | the `download` URL the API returns (shape UNKNOWN) | the `enclosure` URL `/torznab/download/{sqid}?apikey=…` (carries the key; 2026-10-04 capture) | `GET /api/v1/torrents/download/{id}` with the `X-API-KEY` header (CONFIRMED) |
| Categories | 2000 Films, 5000 Séries (no anime, no documentary class) | 2000 Films (2030 SD, 2040 HD, 2045 UHD); 5000 Séries (5030/5040/5045, 5060 Sport, 5070 Animation) | Movies 1, 2, 3, 4, 5, 6, 7, 38; TV 8, 9, 10, 11, 12, 13, 14, 15 (no anime, no documentary) |
| Rate | Jackett `requestDelay: 2` | **120 requests / minute / key** (definition comment) | UNKNOWN |
| Site rules in the definition | Jackett's `minimumratio 0.8`, superseded by the members' wiki (read 2026-10-04): aim ≥ 1, floor 0.5 (warning 0.7), HIT AND RUN 48 h in 14 d (§ 5) | members' wiki (read 2026-10-04): ratio floor 0.4 beyond 5 GB downloaded when enforcement is on; HIT AND RUN 48 h cumulated, marked after 7 days absent, no automatic sanction today; `minimumseedtime` 172 800 s per item in the capture (`draupnirr-api.md`) | members' rules and FAQ (read 2026-10-04): required ratio 0.5 with a 5-day watch; HIT AND RUN 5 days or 1:1 after ≥ 10 % downloaded, freeleech not exempt, 10 days to fix, 5 ⇒ warning, more ⇒ download ban (`digitalcore-api.md`); the Jackett definition's « ratio 1.0, seed 5 days » is superseded; an account idle 90 days is disabled |
| The secret | an API key, « Réglages → Intégrations », **scoped** (« needs the torznab scope ») | the API key IS the personal announce key (« Profil → Paramètres ») | an API key, « Settings → Security → Generate a new API Key »; a separate passkey (IRC / RSS) |
| Account statistics (ratio, volumes) | `GET https://api.v3x.club/api/me`, any key scope, Bearer (T-1, § 5) | `GET https://draupnirr.xyz/api/me`, `?apikey=` or `X-Api-Key`, bytes, ratio includes `bonus_upload` (T-1, § 5) | **none for a normal key** — profile data is blocked (FAQ, read 2026-10-04) ⇒ ratio UNKNOWN (T-1 = A, § 5) |
| Upload API | UNKNOWN | UNKNOWN | UNKNOWN |
| Cross-seed (cross-seed.org) | through a Torznab proxy (Jackett / Prowlarr) | its own Torznab URL; **the site's bot rewrites published film / series names**, so a search by release name can miss an identical release (`draupnirr-api.md`) | through a Torznab proxy |

---

## 2. The boundary

### 2.1 What this brick builds NOW

1. **`draupnirr`** — a Torznab tracker, so a thin named class exactly like `tr4ker`: one `TorznabDescriptor`, one
   class, zero protocol logic. Its two dialect flags (`item_category_element`, `guid_is_infohash`) and its
   `search_categories` are set FROM A CAPTURE, never guessed (the `tr4ker` precedent: « inventing Newznab ids without
   a capture is exactly the kind of guess that silently returns nothing »).
2. **`v3x`** and **`digitalcore`** — two JSON clients. Neither speaks Torznab, so each is a small client of its own
   over the shared `HttpTransport` (retry, circuit, rate limit, auth — nothing re-implemented), composing
   `TorrentSearchable` and `CategoryListable` and producing the same `TrackerResult`. The Torznab generic is not
   bent to parse JSON: a second dialect family would turn its descriptor into a protocol switch.
3. **Registration**: three `ProviderName` members (`V3X = "v3x"`, `DRAUPNIRR = "draupnirr"`, `DIGITALCORE =
   "digitalcore"`), three `PROVIDER_CREDS` entries, three `_TRACKER_CLASSES` lines, three blocks in
   `config.example/tracker.json5` (`enabled: false`, `cross_seed: false`, the `economy` block commented — the `c411`
   block), the three names LAST in the example's `priority` (T-4 = A).
4. **Grab and cross-seed work through the EXISTING paths** — `resolve_source` downloads each result's `.torrent`
   through the tracker's own transport; the cross-seed engine searches by release name and verifies by layout. No
   change to `acquire/`.
5. **One new capability, declared once for every tracker**: `AccountStatsReadable.account_stats() ->
   TrackerAccountStats` (§ 3.4) — the ratio and volumes AS THE TRACKER RECOGNISES THEM. It is implemented by a client
   only where the tracker publishes them (T-1 = A: he finds the endpoint, signed in); a client that cannot does NOT claim it, and the composition
   tests assert that. Nothing computes a ratio locally in its place (NE-DOIT-PAS-1).
6. **Three reference documents** `docs/reference/{v3x,draupnirr,digitalcore}-api.md` in the shape of `tr4ker-api.md`,
   and the redacted captures under `docs/reference/_samples/<tracker>/`.

### 2.2 What it leaves to its lot, after the « Go »

| Left | To | Why it is not this brick's |
| --- | --- | --- |
| `readTrackers` (the row's fields, health, trend, the « accepte les uploads » switch) and where `account_stats()` is polled and stored (`ratio_state`'s writer, its cadence) | K5 | the read-model and its cadence are shaped by the contract the maquette may still move |
| the failure-driven `disabled {by, reason, since}` (T2) and its event E7 | K5 | a state the Trackers page draws |
| `economy.alert_threshold` and the push alert | K5 + `fcm-push` | the trigger is K5's (brief § 1.3) |
| the cross-seed engine attempting EVERY tracker, the per-pair state, exclusions | K6 | `CrossSeedService` re-architecture |
| torrent creation and per-tracker publish (`uploadCrossSeed`, `accepts_uploads`) | K7 | no upload API is public for any of the three (§ 1.1); K7 asks it per tracker |
| the ranking's ratio term (`previewRanking.trackerRatioState`) | K3 | the ranking reads K5's state |
| search by provider id (`tmdbid` on v3x / draupnirr, `imdbid` on draupnirr / digitalcore) | not planned | `TorrentSearchable` searches by title, as for `c411` / `tr4ker`; an id search is a change of the protocol for every tracker, and nobody asked it |

---

## 3. Modules and signatures

### 3.1 `personalscraper/api/tracker/draupnirr.py`

```python
DRAUPNIRR_DESCRIPTOR = TorznabDescriptor(
    provider=ProviderName.DRAUPNIRR,
    display_name="Draupnirr",
    base_url="https://draupnirr.xyz",
    api_path="/torznab/api",
    item_category_element=<from the capture>,
    guid_is_infohash=<from the capture>,
    search_categories=<from caps, else {}>,
    rate_limit=RateLimitPolicy(requests_per_second=0.5),  # under its published 120 / min / key
)


class DraupnirrClient(TorznabClient):
    DESCRIPTOR: ClassVar[TorznabDescriptor] = DRAUPNIRR_DESCRIPTOR
    provider_name: str = ProviderName.DRAUPNIRR.value
    REQUIRED_CREDS: ClassVar[list[str]] = ["DRAUPNIRR_API_KEY"]
```

**One protocol fact the generic must already honour, checked against the capture**: a bad key answers HTTP **200**
with `<error code="100"/>`, where C411 answers 401. `torznab.py` maps a root `<error/>` document to an error; the
phase proves it maps code 100 to `TrackerAuthError` (the auth taxon T2 will read), not to an empty result. If it does
not, the fix is in `torznab.py` for every dialect, with its regression test.

`DRAUPNIRR_API_KEY` is the announce key (the site says so): the same secret identifies the account in every
`.torrent`, so the enclosure URL carrying it is redacted in logs as C411's is (`c411.py`: « `enclosure[@url]` embeds
the apikey inline (sensitive — redact in logs) »), and the capture files carry it redacted.

### 3.2 `personalscraper/api/tracker/v3x.py`

```python
V3X_BASE_URL = "https://api.v3x.club"
V3X_SEARCH_PATH = "/indexer/search"
#: MediaType → the ``cat`` value sent; v3x has no anime / documentary class.
V3X_CATEGORIES: Mapping[MediaType, str] = {
    MediaType.MOVIE: "2000",
    MediaType.TV: "5000",
    # every other kind maps through its film / series nature (§ 3.5)
}


class V3xClient:
    """v3x.club over its JSON indexer API. Composes TorrentSearchable, CategoryListable."""

    provider_name: str = ProviderName.V3X.value
    REQUIRED_CREDS: ClassVar[list[str]] = ["V3X_API_KEY"]

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy: ...
        # ApiKeyAuth(api_key, param="apikey", location="query"), response_format="json",
        # timeout 15 s, RetryPolicy(max_attempts=3), CircuitPolicy(5, 300 s),
        # RateLimitPolicy(requests_per_second=0.5)  — its 2 s request delay

    @classmethod
    def from_env(cls, *, env: Mapping[str, str], event_bus: EventBus,
                 required: list[str], provider_cfg: TrackerProviderConfig) -> Self: ...

    def __init__(self, transport: HttpTransport) -> None: ...

    def search(self, query: str, media_type: MediaType = MediaType.MOVIE,
               year: int | None = None) -> list[TrackerResult]: ...
        # GET /indexer/search?q=<query [+ year]>&cat=<V3X_CATEGORIES>&limit=100
        # → wrap_parser_drift(provider, lambda: [_parse_result(r) for r in body["results"]])

    def get_categories(self) -> dict[str, str]: ...   # the static map — no caps document is public

    @property
    def _open_transport(self) -> HttpTransport: ...   # the registry seam, as TorznabClient


def _parse_result(row: Mapping[str, Any]) -> TrackerResult: ...
    # tracker_id ← details' id; title; size; seeders; leechers; info_hash ← infohash (lower-cased);
    # download_url ← download; source_url ← details; upload_date ← pubdate (ISO 8601 UTC);
    # is_freeleech ← downloadvolumefactor == 0; is_silverleech ← == 0.5; tmdb_id ← tmdbid;
    # format / codec / source / resolution / language ← the shared title parser (as torznab.py)
```

### 3.3 `personalscraper/api/tracker/digitalcore.py`

```python
DIGITALCORE_BASE_URL = "https://digitalcore.club"
DIGITALCORE_SEARCH_PATH = "/api/v1/torrents"
DIGITALCORE_DOWNLOAD_PATH = "/api/v1/torrents/download/{id}"
DIGITALCORE_CATEGORIES: Mapping[MediaType, tuple[int, ...]] = {
    MediaType.MOVIE: (1, 2, 3, 4, 5, 6, 7, 38),
    MediaType.TV: (8, 9, 10, 11, 12, 13, 14, 15),
}


class DigitalCoreClient:
    """digitalcore.club over its JSON API v1. Composes TorrentSearchable, CategoryListable."""

    provider_name: str = ProviderName.DIGITALCORE.value
    REQUIRED_CREDS: ClassVar[list[str]] = ["DIGITALCORE_API_KEY"]

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy: ...
        # ApiKeyAuth(api_key, param="X-API-KEY", location="header"), response_format="json",
        # the defensive profile (15 s, 3 attempts, 5 / 300 s circuit, 0.5 rps — its rate is unpublished)

    @classmethod
    def from_env(cls, *, env, event_bus, required, provider_cfg) -> Self: ...
    def __init__(self, transport: HttpTransport) -> None: ...
    def search(self, query: str, media_type: MediaType = MediaType.MOVIE,
               year: int | None = None) -> list[TrackerResult]: ...
        # GET /api/v1/torrents?searchText=<query [+ year]>&categories[]=…&limit=100&index=0
        #     &page=search&section=all&sort=d&order=desc&dead=false
    def get_categories(self) -> dict[str, str]: ...
    @property
    def _open_transport(self) -> HttpTransport: ...


def _parse_result(row: Mapping[str, Any]) -> TrackerResult: ...
    # tracker_id ← id; title ← name; size; seeders; leechers; info_hash ← None (not published);
    # download_url ← DIGITALCORE_DOWNLOAD_PATH.format(id=…)  — a RELATIVE path, see below;
    # source_url ← f"{BASE}/torrent/{id}/"; upload_date ← added (zone from the capture);
    # is_freeleech ← frileech == 1
```

**A header-auth client never carries an absolute download URL.** `HttpTransport.get_bytes` uses an absolute URL
verbatim with the transport's auth attached; with header auth, an absolute URL from a response body would send
`X-API-KEY` to whatever host it names. `DigitalCoreClient` therefore builds the RELATIVE download path itself, which
`get_bytes` joins onto `base_url`. A unit test asserts every `download_url` it produces is relative.

**No info hash in digitalcore's answer**: the grab's hash cross-check (`resolve_source(..., cross_check=True)`)
has nothing to compare and is a no-op, as for any result without one; the hash comes from the downloaded file. The
cross-seed engine already verifies every candidate by its downloaded `.torrent`, so cross-seed works unchanged — at
the cost of one `.torrent` download per candidate, bounded by the engine's existing daily quota.

### 3.4 The account statistics capability — `api/tracker/_contracts.py` and `_base.py`

```python
@dataclass(frozen=True)
class TrackerAccountStats:
    """The account's standing AS THE TRACKER RECOGNISES IT (NE-DOIT-PAS-1) — never computed locally.

    Attributes:
        provider: The tracker's wire name.
        uploaded: Total uploaded, as the tracker counts it.
        downloaded: Total downloaded, as the tracker counts it.
        ratio: The tracker's own ratio figure; ``None`` when it publishes volumes but no ratio
            (then K5 derives nothing either: an absent figure stays absent).
        bonus: The tracker's bonus points / credits, when published.
        observed_at: When the tracker answered (epoch seconds).
    """
    provider: str
    uploaded: ByteSize
    downloaded: ByteSize
    ratio: float | None
    bonus: float | None
    observed_at: float


@runtime_checkable
class AccountStatsReadable(Protocol):
    """Capability — read the account's standing from the tracker itself."""

    def account_stats(self) -> TrackerAccountStats: ...
```

Raises the family's existing errors (`TrackerAuthError` on 401/403, `ApiError` otherwise, `CircuitOpenError`). A
client composes it only on a documented endpoint (T-1 = A); without one, K5 shows that tracker's ratio as UNKNOWN.

### 3.5 Kinds a tracker has no class for

The registry searches with `MediaType` values; the library has five film and five series categories (CLAUDE.md
« Move rules »). None of the three trackers has an anime or a documentary class. Each client maps a kind by its
nature — every film kind to its film classes, every series kind to its series classes — exactly as `c411` /
`tr4ker` narrow by `t=movie` / `t=tvsearch` alone. The mapping lives in each client's category table and is tested
for every `MediaType` member.

### 3.6 Secrets and activation

| Tracker | `PROVIDER_CREDS` (gates activation) | `PROVIDER_OPTIONAL_SECRETS` |
| --- | --- | --- |
| `v3x` | `V3X_API_KEY` | — |
| `draupnirr` | `DRAUPNIRR_API_KEY` (the announce key) | — |
| `digitalcore` | `DIGITALCORE_API_KEY` | `DIGITALCORE_PASSKEY` (announce / RSS; authenticates nothing here) |

A tracker without its key never activates (`resolve_active`), so shipping the three providers changes nothing on
any environment until the operator writes the key and sets `enabled: true` — and on preprod, cross-seed stays off by
its overlay (§ 5 Q4).

---

## 4. Tests

**Unit, on recorded captures only** — never a live call in the suite:

- per client, the files `docs/reference/_samples/<tracker>/`: a movie search, a TV search, an empty answer, an auth
  failure, and for `draupnirr` the `caps` document. Keys and passkeys REDACTED in the files (the `tr4ker` rule).
- `test_draupnirr_client.py` — the `tr4ker` suite's shape: identity and endpoint, the key as `apikey=`, the dialect
  flags equal the capture's facts, no invented category, the defensive transport, `from_env` without network, the
  `<error code="100"/>` at HTTP 200 → `TrackerAuthError`.
- `test_v3x_client.py`, `test_digitalcore_client.py` — the request each search sends (path, params; the header for
  digitalcore and NO key in the URL), every field of `TrackerResult` from the capture, `wrap_parser_drift` on a
  mutated payload, 401 / 403 → `TrackerAuthError`, every `MediaType` mapped (§ 3.5), digitalcore's `download_url`
  relative for every result.
- the composition tests: each new client composes `TorrentSearchable` and `CategoryListable`, and does NOT claim
  `FreeleechAware`, `TorrentDetailsProvider`, or `AccountStatsReadable` unless T-1 gave it an endpoint.
- the factory: `_TRACKER_CLASSES` resolves the three; `resolve_active` gates each on its key; the example config
  loads (`TrackerConfig` validates `priority` against `providers`).
- `resolve_source` over a fake transport per tracker: a digitalcore result downloads from the relative path; a
  v3x result from its returned URL.

**Manual E2E, by the operator's hand** (an account is needed — no agent holds a key): per tracker, once, after its
phase merges — the key in `.env`, `enabled: true` in his overlay, then `personalscraper cross-seed --hash <H>` on a
torrent he knows that tracker carries, read for one `search` per tracker and a verified or reasoned candidate.

---

## 5. DECIDED — his rulings of 2026-10-01 (decision round 4)

**T-1 = A — the ratio « the tracker recognises », for the three (and, already today, for c411 and tr4ker).** No public
source shows an account-statistics endpoint for any of the three; `ratio_state` has no writer today for c411 and
tr4ker either (§ 1). § 18 requires the TRACKER's figure (NE-DOIT-PAS-1). He looks, on each site signed in, for an API
offering the account's statistics (v3x's « Réglages → Intégrations » lists key SCOPES: a stats scope would be it) and
gives the endpoint or its doc page; each found endpoint becomes that client's `account_stats()` (phase 5). **Where
none exists, the tracker's ratio shows UNKNOWN** — never a locally computed figure, and never a scraped profile page
unless he orders it for a named tracker (§ 18 point 4: never mistreat a tracker).

**T-1 answered for v3x (members' wiki, read 2026-10-04):** `GET https://api.v3x.club/api/me`, a key of **any** scope,
`Authorization: Bearer <key>`; volumes in **bytes**; fields `{username, uploaded, downloaded, ratio, buffer,
bonusPoints, freeleechTokens, invitesLeft, seeding, leeching, hitAndRun}` — the ratio the tracker recognises. v3x's
client therefore composes `AccountStatsReadable` in phase 5. No capture of `/api/me` exists yet (owed at phase 3, in
`scripts/capture-tracker-sample.py`); `docs/reference/v3x-api.md` carries the detail.

**T-1 answered for draupnirr (members' wiki, read 2026-10-04):** `GET https://draupnirr.xyz/api/me`, the passkey as
`?apikey=` **or** header `X-Api-Key`; volumes in **bytes**; fields `{name, class, credits, invites, freeleech_until,
uploaded, downloaded, bonus_upload, ratio, seedtime_seconds, uploads_count, hnr_count, badges[]}`. The `ratio` is
`(uploaded + bonus_upload) / downloaded` — the one the tracker recognises, not `uploaded / downloaded` — and `null`
means infinite, not unknown. draupnirr's client therefore composes `AccountStatsReadable` in phase 5. No capture of
`/api/me` exists yet (owed at that phase); `docs/reference/draupnirr-api.md` carries the detail.

**T-1 answered for digitalcore (members' rules and FAQ, read 2026-10-04): no endpoint.** A normal API key is
explicitly blocked from torrent detail, comments, peers, the snatch log, **profile data**, the mailbox, admin and
edits, so no account-statistics endpoint exists for it. The ratio, the volumes and the HIT AND RUN count are
**UNKNOWN** in TorrentMate (T-1 = A): `DigitalCoreClient` does NOT claim `AccountStatsReadable`, and phase 5 skips
it. Reading the site's profile page would be T-1 = B, only if he orders it for this tracker.
`docs/reference/digitalcore-api.md` carries the detail.

**T-2 — The accounts and the keys he must provide — stays his hand** (none is assumed):

| Tracker | Account | Secret to create | Where (public definitions) |
| --- | --- | --- | --- |
| v3x.club | his | API key with the `torznab` scope (no extra scope: `/api/me` takes any scope) | Réglages → Intégrations |
| draupnirr.xyz | his | none to create: the announce key is the API key | Profil → Paramètres |
| digitalcore.club | his | API key (and the passkey, optional) | Settings → Security → Generate a new API Key |

He confirms he holds an account on each; the secrets go to `.env` by his hand (`V3X_API_KEY`, `DRAUPNIRR_API_KEY`,
`DIGITALCORE_API_KEY`), never through an agent.

**T-3 = B — he captures the fixtures himself**: `! python scripts/capture-tracker-sample.py <tracker>` reads the key
from `.env`, calls caps / one movie search / one TV search / one bad-key call, REDACTS every key and passkey, and
writes `docs/reference/_samples/<tracker>/`; a session reads only the redacted files. No key ever enters an agent's
context; the script is reused for any later tracker.

**T-4 = A — the example config ships the three LAST in `priority`, their `economy` commented.** The `economy` block's
`min_ratio` / `min_seed_time` are the site's rules, which only he reads signed in; he fills each from the site and
moves ranks in Réglages. Public hints, for him: digitalcore required ratio 0.5 and HIT AND RUN 5 days or 1:1 after ≥ 10 % downloaded, 10 days to fix (members' rules and FAQ, 2026-10-04), v3x ratio ≥ 1 aimed, floor 0.5 (warning 0.7), HIT AND RUN 48 h
within 14 days (members' wiki, 2026-10-04), draupnirr ratio floor 0.4 beyond 5 GB downloaded (while enforcement is on) and HIT AND RUN 48 h cumulated (members' wiki, 2026-10-04; `minimumseedtime` 172 800 s per item in the capture);
digitalcore is an English scene tracker with no French class — its value for a French library is MULTI / VO releases
and cross-seed. The operator's word: « digitalcore n'est pas un tracker français » — its releases rarely carry French
audio, so grab and ranking never assume French audio from this tracker; the language is read from the release-name
tags or its mediainfo, as for any tracker.

---

## 6. Phases

Each phase lands one tracker whole (client, registration, example block, reference doc, captures, tests); 2–4 are
independent once 1 has landed the shared pieces.

| Phase | What | Done when | Proving command |
| --- | --- | --- | --- |
| 1 | **The shared pieces**: `TrackerAccountStats` + `AccountStatsReadable` in `_contracts.py` / `_base.py`, exported; the composition tests extended (no client claims it yet); `scripts/capture-tracker-sample.py` (T-3 B) with its redaction tested on a fake answer | the protocol is importable, no existing client claims it, the capture script redacts a planted key in every output file | `pytest tests/unit/test_tracker_capabilities_composition.py tests/unit/test_capture_tracker_sample.py -q` |
| 2 | **draupnirr** — descriptor + thin class from the capture, `ProviderName`, creds, factory, example block, `draupnirr-api.md`; the HTTP-200 `<error code="100"/>` → `TrackerAuthError` proved (fixed in `torznab.py` if not) | its suite green on the captures; the example config loads; the generic's dialect tests still green | `pytest tests/unit/test_draupnirr_client.py tests/unit/test_torznab_client.py -q` |
| 3 | **v3x** — `V3xClient`, registration, example block, `v3x-api.md` | its suite green; every `MediaType` mapped; `resolve_source` downloads from the returned URL | `pytest tests/unit/test_v3x_client.py -q` |
| 4 | **digitalcore** — `DigitalCoreClient` (header auth, relative download path), registration, example block, `digitalcore-api.md` | its suite green; no key in any request URL; every `download_url` relative | `pytest tests/unit/test_digitalcore_client.py -q` |
| 5 | **account statistics**, per tracker T-1 found an endpoint for: `account_stats()` on that client, from a capture | each implementing client's stats parsed from its capture; the others still do not claim it | `pytest tests/unit -k account_stats -q` |
| — | **The operator's E2E** (§ 4), per tracker after its phase | one search and one verified-or-reasoned cross-seed candidate per tracker, in his hands | `personalscraper cross-seed --hash <H>` |

Gate per phase: `make lint`; pytest of the touched modules (CLAUDE.md « Gates »). Phase 5 waits T-1; phases 2–4 wait
T-2's keys for their capture (T-3).
