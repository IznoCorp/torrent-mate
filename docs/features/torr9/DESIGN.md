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

| Fact            | Value                                                                                                                                                                                                                                                                                  |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Base**        | `https://api.torr9.net/api/v1`                                                                                                                                                                                                                                                         |
| **Auth (DUAL)** | **JWT** for the JSON API: `POST /auth/login {username,password}` → `{token,user,message}` → `Authorization: Bearer <token>`. **Passkey** for RSS feeds + announce/download (`TORR9_PASSKEY`). Creds: `TORR9_USERNAME`, `TORR9_PASSWORD`, `TORR9_PASSKEY`.                              |
| **Search**      | `GET /torrents?q=<query>` + Bearer → JSON `{limit, page, torrents:[...]}`. Param is **`q`** (`search` ignored). Pagination via `page`. Sample: `../../reference/_samples/torr9/torr9_search.json`.                                                                                     |
| **Item (JSON)** | `id`, `title`, `description`(BBCode), `info_hash`, **`magnet_link`**, `torrent_file_url`(relative), **`file_size_bytes`**, `file_count`, `category_id`(numeric), `uploader_id`, `is_private`, **`is_freeleech`**(bool), `is_anon`, `is_exclu`, `tags[]`, `upload_date`(ISO), `status`. |
| **Download**    | **`magnet_link`** (direct, auth-free → Q4 magnet exception). `torrent_file_url` = relative, needs base+auth (fallback).                                                                                                                                                                |
| **Freeleech**   | structured boolean `is_freeleech` (search) + `\| FREELEECH` marker (RSS).                                                                                                                                                                                                              |
| **Auth errors** | login 401 "Identifiant ou mot de passe invalide"; JSON 401 "Missing authorization token"; 429/403 rate-limit. Token expiry → re-login (RP7).                                                                                                                                           |

**NOT exposed** (drives the design): **no seeders/leechers** (neither JSON nor RSS),
no IMDb/TMDb id, no structured codec/resolution beyond `title`/`tags`.

**Minor unknowns** (confirm at impl with a fresh token, low-rate): `category_id`→label
map (`GET /categories`), JWT lifetime/refresh, pagination bound, 429/403 budget.

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

1. **`personalscraper/api/tracker/torr9.py`** — `Torr9Client(TorrentSearchable, FreeleechAware)`:
   - **Auth = login → Bearer JWT** (NOT a static api-key): `_login()` POSTs
     `{username, password}` to `/auth/login`, caches the returned `token`, injects
     `Authorization: Bearer <token>`. **Re-login on 401** (token expiry, RP7
     auth-lifecycle). `policy(cls, username, password)` builds the `TransportPolicy`
     (base `…/api/v1`); the Bearer is applied lazily after login.
   - `__init__(self, transport: HttpTransport)`.
   - `search(query, media_type=MOVIE, year=None) -> list[TrackerResult]` → ensure
     token → `GET /torrents?q=<query>` → parse `torrents[]` (wrapped in
     `wrap_parser_drift`). Pagination via `page` if needed.
   - `get_categories() -> dict[str, str]` from a static `_CATEGORY_MAP`
     (`category_id`→label; seed from the fixture, extend with `GET /categories`).
   - `_parse_item(json)` → `TrackerResult`: `title`; size=`file_size_bytes`;
     `is_freeleech` (bool); **download = `magnet_link`** (auth-free); `info_hash`;
     category from `category_id`; `upload_date`. **`seeders=None`** (not exposed).
   - `provider_name = "torr9"`.
2. **`personalscraper/api/tracker/_factory.py`** — add
   `"torr9": "personalscraper.api.tracker.torr9:Torr9Client"` to `_TRACKER_CLASSES`.
3. **`personalscraper/api/_activation.py`** — `PROVIDER_CREDS["torr9"] = ["TORR9_USERNAME", "TORR9_PASSWORD"]`;
   `PROVIDER_OPTIONAL_SECRETS["torr9"] = ["TORR9_PASSKEY"]` (only if torr9 needs a passkey).
4. **`config/tracker.json5`** — add `torr9: { enabled: false, economy: { target_ratio, min_ratio, min_seed_time, hit_and_run_grace } }` (default **disabled** until creds are set) and append `"torr9"` to `priority`.
5. **`config.example/tracker.json5`** — mirror the entry (overlay parity).
6. **Tests** (golden fixtures — mandatory, see Risks):
   - `tests/unit/test_torr9_client.py` — search parse from the **captured**
     `docs/reference/_samples/torr9/torr9_search.json`: asserts title /
     size(`file_size_bytes`) / `is_freeleech` / download(`magnet_link`) / category /
     `upload_date` on real JSON fields (mirror `test_lacale_client.py`);
     empty-result + malformed-payload paths; a mocked-login test (re-login on 401).
   - extend `tests/unit/test_tracker_parser_schema_drift.py` — torr9 survives a
     missing/renamed field via `wrap_parser_drift`.
   - extend `tests/unit/test_tracker_capabilities_composition.py` — `Torr9Client`
     is a `TorrentSearchable` + `CategoryListable` (+ `FreeleechAware`).
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
- **No seeders exposed** — `_ranking.py` weights seeders; torr9 results carry none
  (neither JSON nor RSS) → they rank on freeleech/size/recency only. Mitigation:
  set `seeders=None`/0 and confirm the merged ranking doesn't unfairly sink torr9
  (special-case missing-seeders if needed). Do NOT N+1 detail-fetch for seeders
  unless ranking proves it necessary.
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
- **Creds gating** — torr9 ships `enabled: false`; enabling without
  `TORR9_USERNAME + TORR9_PASSWORD` must fail-loud at boot (parity with c411/lacale), not silently
  drop the tracker.
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
