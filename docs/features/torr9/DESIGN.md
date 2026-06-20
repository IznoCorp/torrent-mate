# Design — torr9 (Additional Tracker)

**Status**: prepared (ahead-of-time, uncommitted) — 2026-06-19
**Roadmap**: Vague 3 — "Additional Trackers — torr9" (premier nouveau tracker, après RP7 auth)
**Type**: minor (new tracker provider; no breaking change to the tracker framework)

## Problem / Goal

The acquisition stack ships two tracker providers — `lacale` (JSON API) and
`c411` (Torznab/Newznab RSS) — wired through the config-driven
`TrackerRegistry` (RP5a/tracker-wiring), gated by per-provider creds
(`PROVIDER_CREDS`), and ranked by the shared `_ranking.py`. The roadmap's first
acquisition-surface extension is a **third private tracker, `torr9`**, added on
the **existing** framework (RP2 per-tracker config + RP7 auth lifecycle) — no
framework change, just a new provider that composes the established capability
protocols.

**Goal**: a `Torr9Client` that searches torr9, parses results into
`TrackerResult`, exposes its category catalog, flags freeleech, and registers
itself in the registry under the same config + creds + ranking + economy
discipline as `c411`/`lacale`. Locked by golden-fixture tests (real captured
torr9 payloads), not synthetic stubs.

## API contract — CAPTURED (2026-06-19)

The torr9 API was captured live — full reference in
[`../../reference/torr9-api.md`](../../reference/torr9-api.md), real payloads in [`../../reference/_samples/torr9/`](../../reference/_samples/torr9/).
**torr9 is a full search tracker** via an authenticated JSON API (+ passkey RSS
feeds for the freeleech radar). Resolved facts:

| Fact            | Value                                                                                                                                                                                                                                                                                                                                              |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Base**        | `https://api.torr9.net/api/v1`                                                                                                                                                                                                                                                                                                                     |
| **Auth (DUAL)** | **JWT** for the JSON API: `POST /auth/login {username,password}` → `{token,user,message}` → `Authorization: Bearer <token>`. **Passkey** for RSS feeds + announce/download (`TORR9_PASSKEY`). Creds: `TORR9_USERNAME`, `TORR9_PASSWORD`, `TORR9_PASSKEY`.                                                                                          |
| **Search**      | `GET /torrents?q=<query>` + Bearer → JSON `{limit, page, torrents:[...]}`. Param is **`q`** (`search` ignored). Pagination via `page`. Sample: `../../reference/_samples/torr9/torr9_search.json`.                                                                                                                                                 |
| **Detail**      | `GET /torrents/{id}` + Bearer → JSON **single torrent** object (live-confirmed 2026-06-19). Carries `is_freeleech` AND — unlike search — `seeders`/`leechers`/`times_completed`/`views` + `category_name`. Backs the **FreeleechAware** pre-download re-check. Sample: `../../reference/_samples/torr9/torr9_detail.json`.                         |
| **Item (JSON)** | `id`, `title`, `description`(BBCode), `info_hash`, **`magnet_link`**, `torrent_file_url`(relative), **`file_size_bytes`**, `file_count`, `category_id`(numeric), `uploader_id`, `is_private`, **`is_freeleech`**(bool), `is_anon`, `is_exclu`, `tags[]`, `upload_date`(ISO), `status`.                                                             |
| **Download**    | **`magnet_link`** (direct, auth-free → Q4 magnet exception) PRIMARY. Fallback when magnet absent = the real `.torrent` endpoint `GET /api/v1/torrents/{id}/download` + Bearer → `200 application/x-bittorrent` (live-confirmed 2026-06-19). `torrent_file_url` is **DEAD** (404 at every host/auth, hash mismatch, absent from detail) — NOT used. |
| **Freeleech**   | structured boolean `is_freeleech` (search) + `\| FREELEECH` marker (RSS).                                                                                                                                                                                                                                                                          |
| **Auth errors** | login 401 "Identifiant ou mot de passe invalide"; JSON 401 "Missing authorization token"; 429/403 rate-limit. Token expiry → re-login (RP7).                                                                                                                                                                                                       |

**NOT exposed by SEARCH** (drives the design): the **search** payload carries **no
seeders/leechers** (neither the JSON list nor RSS), no IMDb/TMDb id, no structured
codec/resolution beyond `title`/`tags`. The **detail** endpoint (`GET /torrents/{id}`,
live-confirmed) _does_ carry `seeders`/`leechers`. Because `config/ranking.json5` sets
`min_seeders: 1`, every `seeders=0` search result is dropped before scoring — so torr9
would win **no grab** without enrichment. Therefore `search()` **enriches the top-K=10
results' seeders/leechers from the detail endpoint** (`TorrentDetailsProvider.get_details`,
ON by default, fail-soft per result; phase-04 operator decision 2026-06-19). The detail
endpoint also backs the `FreeleechAware.is_freeleech` pre-download re-check.

**Minor unknowns** (confirm at impl with a fresh token, low-rate):
**`category_id`→label map** — **RESOLVED (2026-06-20):** NO `/categories` endpoint
exists (404 on `/categories`, `/category`, `/torrents/categories`); the map is
built by correlating search `category_id` ↔ detail `category_name`, live-verified
for the active categories. JWT lifetime/refresh, pagination bound, 429/403 budget.

### Reference pattern

torr9's search is a **JSON API with JWT login** — closest to **lacale** (JSON +
`wrap_parser_drift`) but with a **login/token** auth step (not a static API key) →
the RP7 auth-lifecycle (re-login on 401). The **RSS feeds** (passkey, freeleech
radar) are a secondary surface. So `Torr9Client` ≈ lacale-shaped JSON parser +
a login/token transport + an optional RSS-feed reader for freeleech. Reuse
lacale's `wrap_parser_drift`; feed `title` to `guessit`/`_parse_title`;
prefer `magnet_link` for the grab.

## Approach

Mirror the proven provider pattern exactly — **no new framework code**:

1. **`personalscraper/api/tracker/torr9.py`** — `Torr9Client(TorrentSearchable, CategoryListable, FreeleechAware, TorrentDetailsProvider)`:
   - **Auth = login → Bearer JWT** (NOT a static api-key), built on the **TVDB
     lazy-transport pattern** (no private `_session` access). The client owns its
     transports: `_ensure_transport()` opens a one-shot `NoAuth` bootstrap
     transport (`_bootstrap_policy()`), POSTs `{username, password}` to
     `/api/v1/auth/login`, extracts the `token`, then builds and caches the authed
     main transport whose policy carries `BearerAuth(token)`. `policy(cls, token)`
     builds that authed `TransportPolicy` (base `…/api/v1`). Construction is
     network-free: bootstrap is deferred to first `_transport` access (no token at
     construct time), exactly like `TVDBClient`. **Re-login on 401** via
     `_authed_get` (drop the cached transport → next access rebuilds it via a fresh
     bootstrap → retry once; a second 401 fails loud, RP7 auth-lifecycle).
   - `__init__(self, *, username: str, password: str, event_bus: EventBus,
enrich_seeders=True, enrich_seeders_top_k=10)` — stores creds + event bus +
     enrich flags, leaves the transport lazy (`__transport = None`). Construction
     goes through the **uniform `from_env(cls, *, env, event_bus, required,
provider_cfg)`** classmethod — the `TrackerConstructible` capability
     implemented by EVERY tracker (lacale/c411 api-key shape; torr9 login shape).
     The factory dispatches through `from_env` uniformly (no provider-name
     literal, no `build_from_env` getattr-hook, no cred-style branch). torr9
     reads its enrich flags off `provider_cfg`.
   - `search(query, media_type=MOVIE, year=None) -> list[TrackerResult]` → ensure
     token → `GET /torrents?q=<query>` → parse `torrents[]` (wrapped in
     `wrap_parser_drift`). Pagination via `page` if needed.
   - `get_categories() -> dict[str, str]` from a static `_CATEGORY_MAP`
     (`category_id`→label; seed from the fixture, extend with `GET /categories`).
   - `_parse_item(json)` → `TrackerResult` (shared by BOTH search items AND
     `get_details`' detail item): `title`; size=`file_size_bytes`; `is_freeleech`
     (bool); **download = `magnet_link`** (auth-free) with a fallback to the real
     `.torrent` endpoint `/api/v1/torrents/{id}/download` when magnet absent (NOT
     the dead `torrent_file_url`); `info_hash`; category from `category_id` (search)
     ELSE `category_name` (detail); `upload_date`. seeders/leechers read from the
     item when present (`0` for search items, real values for detail items).
   - `is_freeleech(self, torrent_id) -> bool` (**FreeleechAware** capability,
     live-confirmed endpoint): ensure token → `GET /torrents/{id}` (re-login on 401)
     → return the fresh `is_freeleech` boolean from the single-torrent detail payload.
     A genuine pre-download re-check (not a stub) — torr9 _does_ expose a per-torrent
     detail endpoint, unlike c411/lacale.
   - `get_details(self, torrent_id) -> TrackerResult` (**TorrentDetailsProvider**
     capability): `GET /torrents/{id}` → `_parse_item` → real seeders/leechers.
     `search()` calls it on the top-K=10 results (default on; fail-soft per result)
     to enrich swarm health so the ranking `min_seeders` floor doesn't drop them.
   - `provider_name = ProviderName.TORR9.value` (`ProviderName.TORR9 = "torr9"`).
2. **`personalscraper/api/tracker/_factory.py`** — add
   `"torr9": "personalscraper.api.tracker.torr9:Torr9Client"` to `_TRACKER_CLASSES`.
   Construction dispatches **uniformly** through `TrackerConstructible.from_env`
   (every tracker implements it): the factory calls
   `cast("type[TrackerConstructible]", client_cls).from_env(env=…, event_bus=…,
required=…, provider_cfg=…)` with no provider-name literal, no `build_from_env`
   getattr-hook, and no cred-style branch. api-key trackers (lacale/c411) build a
   single-key transport inside their `from_env`; login-style torr9 self-builds its
   lazy authed transport. The `isinstance(client, TorrentSearchable)` check stays.
3. **`personalscraper/api/_activation.py`** — `PROVIDER_CREDS["torr9"] = ["TORR9_USERNAME", "TORR9_PASSWORD"]`;
   `PROVIDER_OPTIONAL_SECRETS["torr9"] = ["TORR9_PASSKEY"]` (only if torr9 needs a passkey).
4. **`config/tracker.json5`** — `torr9: { enabled: true, economy: { target_ratio, min_ratio, min_seed_time, hit_and_run_grace } }` (**ENABLED** in `config/`; creds in `.env`, verified — CI never loads this file) and `"torr9"` appended to `priority`. `config.example/tracker.json5` keeps the entry **disabled** as the all-disabled template.
5. **`config.example/tracker.json5`** — mirror the entry (overlay parity).
6. **Tests** (golden fixtures — mandatory, see Risks):
   - `tests/unit/test_torr9_client.py` — search parse from the **captured**
     `docs/reference/_samples/torr9/torr9_search.json`: asserts title /
     size(`file_size_bytes`) / `is_freeleech` / download(`magnet_link`) / category /
     `upload_date` on real JSON fields (mirror `test_lacale_client.py`);
     empty-result + malformed-payload paths; a bootstrap-login test (patches
     `HttpTransport` to verify the `/auth/login` POST + the authed main policy's
     `BearerAuth`) + re-login + second-401-fail-loud paths.
   - extend `tests/unit/test_tracker_parser_schema_drift.py` — torr9 survives a
     missing/renamed field via `wrap_parser_drift`.
   - extend `tests/unit/test_tracker_capabilities_composition.py` — `Torr9Client`
     is a `TorrentSearchable` + `CategoryListable` + `FreeleechAware` (the last via
     the live-confirmed `GET /torrents/{id}` detail re-check).
   - `tests/unit/test_torr9_client.py` — `is_freeleech(torrent_id)` golden test
     from the **captured** `docs/reference/_samples/torr9/torr9_detail.json`
     (re-check returns the detail payload's `is_freeleech`), plus a re-login-on-401 path.
   - extend `tests/integration/api/tracker/test_composition_root.py` — with
     `torr9.enabled=true` + `TORR9_USERNAME + TORR9_PASSWORD` set, `build_tracker_registry`
     includes torr9; with creds missing + enabled, boot validation reports the
     missing cred (fail-loud, like lacale/c411).

## Non-goals

- No change to the tracker capability protocols, `_ranking.py`, `_fetch.py`,
  `TrackerResult`, or `build_tracker_registry` logic. torr9 plugs in.
- No ratio/economy _engine_ work (that's Vague 5 Ratio C1) — torr9 only carries
  its `economy` config block (consumed later by Ratio).
- No new tracker auth _primitive_ — RP7 auth lifecycle is reused as-is.
- `lacale`/`c411` untouched.

## Risks

- **JWT auth lifecycle (RP7).** Unlike c411/lacale's static API key, torr9 search
  needs a **login → token**, and the token expires. Mitigation: login lazily, cache
  the token, **re-login on 401** ("Missing authorization token") — the RP7
  auth-freshness pattern. A `login()` failure (401 bad creds) must fail loud at
  boot validation, not silently drop torr9. Tests must NOT hit the live login
  (use fixtures + a mocked transport).
- **No seeders in SEARCH** — `_ranking.py` weights seeders AND `config/ranking.json5`
  sets `min_seeders: 1`, so every `seeders=0` torr9 search result is DROPPED before
  scoring → torr9 would win no grab. **Resolved (phase-04, operator decision):** the
  **detail** endpoint (`GET /torrents/{id}`) exposes real `seeders`/`leechers`, so
  `search()` enriches the **top-K=10** results' swarm health from it via
  `TorrentDetailsProvider.get_details` (ON by default; config flags
  `enrich_seeders` / `enrich_seeders_top_k` on `TrackerProviderConfig`). Enrichment is
  **fail-soft per result** — a detail error or circuit trip leaves that result at
  `seeders=0` but never aborts the search. The K bound caps the N+1 cost.
- **Vacuous parser tests** (project memory: DeepSeek-written parsers/API-wrappers
  pass `make check` while hiding real bugs). Mitigation: golden fixtures from the
  **real captured torr9 payloads** (`../../reference/_samples/torr9/`, passkey-redacted) + adversarial
  pr-review + re-reproduce the parse before merge. No synthetic-only fixtures.
- **Parser drift** — torr9 changing its payload shape. Mitigation:
  `wrap_parser_drift` + the schema-drift test.
- **Rate-limiting (429)** — torr9 throttles bursty access (hit during capture).
  Mitigation: `TransportPolicy` throttle; confirm the budget; tests use fixtures,
  not live calls.
- **Passkey is a secret** — `TORR9_PASSKEY` in `.env` only; redact in fixtures/docs
  (done). The passkey shared in chat during prep should be rotated.
- **Creds gating** — torr9 ships `enabled: true` in `config/` (phase-04; creds in
  `.env`, verified by a local registry boot). Enabling without
  `TORR9_USERNAME + TORR9_PASSWORD` fails loud at boot (parity with c411/lacale), not
  silently drop the tracker. CI is unaffected — it never loads `config/tracker.json5`
  (no tracked master `config.json5`). `config.example/` stays all-disabled.
- **Overlay drift** — `config/` vs `config.example/` (project memory): add the
  entry to **both**.

## ACCEPTANCE criteria (executable; SH-16)

ACC-1 — torr9 client module exists and composes the capabilities:

```bash
python -c "from personalscraper.api.tracker.torr9 import Torr9Client; from personalscraper.api.tracker._contracts import TorrentSearchable, CategoryListable; print(issubclass(Torr9Client, object) and hasattr(Torr9Client,'search') and hasattr(Torr9Client,'get_categories'))"
# Expected: True
```

ACC-2 — torr9 is registered in the factory client map:

```bash
python -c "from personalscraper.api.tracker._factory import _TRACKER_CLASSES; print('torr9' in _TRACKER_CLASSES)"
# Expected: True
```

ACC-3 — creds are gated:

```bash
python -c "from personalscraper.api._activation import PROVIDER_CREDS; print(PROVIDER_CREDS.get('torr9'))"
# Expected: ['TORR9_USERNAME', 'TORR9_PASSWORD']
```

ACC-4 — config carries torr9 (both overlays):

```bash
grep -c 'torr9' config/tracker.json5 config.example/tracker.json5
# Expected: each file ≥ 1
```

ACC-5 — golden-fixture parse test passes on a real captured payload:

```bash
python -m pytest tests/unit/test_torr9_client.py -q
# Expected: N passed, 0 failed (asserts title/size/seeders/freeleech on real fields)
```

ACC-6 — full suite green:

```bash
make test 2>&1 | tail -1
# Expected: "NNNN passed" with 0 failed / 0 errors
```

ACC-7 — boot validation fails loud when torr9 enabled without creds:

```bash
# with torr9.enabled=true and TORR9_USERNAME + TORR9_PASSWORD unset, build_tracker_registry must report the missing cred
python -m pytest tests/integration/api/tracker/test_composition_root.py -q -k torr9
# Expected: passed (the missing-cred fail-loud case is asserted)
```

ACC-8 — torr9 implements the FreeleechAware capability (pre-download re-check via
the live-confirmed `GET /torrents/{id}` detail endpoint):

```bash
python -c "from personalscraper.api.tracker.torr9 import Torr9Client; from personalscraper.api.tracker._contracts import FreeleechAware; t=Torr9Client(username='u', password='p', event_bus=__import__('unittest.mock',fromlist=['MagicMock']).MagicMock()); print(isinstance(t, FreeleechAware) and hasattr(Torr9Client,'is_freeleech'))"
# Expected: True
```

ACC-9 — torr9 enriches seeders via the TorrentDetailsProvider capability, default on
(top-K=10), config flags declared on the model:

```bash
python -c "from personalscraper.api.tracker.torr9 import Torr9Client; from personalscraper.api.tracker._contracts import TorrentDetailsProvider; print(issubclass(Torr9Client, TorrentDetailsProvider) and hasattr(Torr9Client,'get_details'))"
# Expected: True
python -c "from personalscraper.conf.models.api_config import TrackerProviderConfig; c=TrackerProviderConfig(); print(c.enrich_seeders, c.enrich_seeders_top_k)"
# Expected: True 10
```

ACC-10 — `.torrent` download fallback: when `magnet_link` is absent, `_parse_item`
emits the real `.torrent` endpoint `/api/v1/torrents/{id}/download` (NOT the dead
`torrent_file_url`):

```bash
python -m pytest tests/unit/test_torr9_client.py -q -k "download or magnet"
# Expected: passed (asserts download_url == /api/v1/torrents/{id}/download when magnet absent)
```
