# torr9 — Implementation Plan Index

**Feature**: torr9 (new tracker provider — JSON API with JWT login)
**Branch**: `feat/torr9`
**Design**: `docs/features/torr9/DESIGN.md`
**API ref**: `docs/reference/torr9-api.md`
**Golden fixtures**: `docs/reference/_samples/torr9/torr9_search.json`

---

## Phases

| #   | Phase                                                              | File                                                                                             | Status |
| --- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | ------ |
| 1   | Torr9Client + lazy JWT login + JSON search + golden tests          | [phase-01-client-login-jwt-golden.md](phase-01-client-login-jwt-golden.md)                       | [ ]    |
| 2   | Registry wiring + creds + config overlays + composition-root tests | [phase-02-registry-wiring-creds-config.md](phase-02-registry-wiring-creds-config.md)             | [ ]    |
| 3   | Capabilities composition + schema-drift + ACC gate                 | [phase-03-capabilities-schema-drift-acc-gate.md](phase-03-capabilities-schema-drift-acc-gate.md) | [ ]    |

---

## Key decisions captured in the plan

- **JWT auth lifecycle (RP7)**: `Torr9Client` caches the Bearer token lazily (first `search()` call) and re-logins exactly once on 401 mid-session. Login failure is always fail-loud (`ApiError`, never silent drop).
- **`policy()` takes no args**: Unlike `lacale`/`c411` where `policy(api_key)` takes a static key, torr9's `policy()` uses `NoAuth` (placeholder). The factory detects torr9 by name and calls `Torr9Client(transport, username=..., password=...)` directly (phase 2 factory branch).
- **`PROVIDER_CREDS["torr9"] = ["TORR9_USERNAME", "TORR9_PASSWORD"]`**: The DESIGN's ACC-3 lists `TORR9_API_KEY` — this is a typo in the DESIGN (the API contract requires username/password). Phase 3 ACC-3 re-exercise documents the correction.
- **`seeders=0, leechers=0`**: torr9 exposes no swarm health data (JSON or RSS). Ranking falls back to freeleech/size/recency. `seeders=None` was considered but `0` keeps the `TrackerResult.seeders: int` type signature clean.
- **`FreeleechAware` NOT implemented**: `is_freeleech` is a clean boolean already on each `TrackerResult` at search time — no separate re-check endpoint exists.
- **RSS freeleech radar (R1) is OUT OF SCOPE**: `TORR9_PASSKEY` is registered as an optional secret (non-gating) but no RSS feed reader is implemented in this feature. Deferred to ROADMAP R1.
- **`_CATEGORY_MAP` static**: `GET /api/v1/categories` was rate-limited (403) during prep. Seeded from golden fixture + RSS cross-reference (ids 5 = Séries TV, 51 = Films, etc.). Confirm and extend with a fresh token at implementation.

---

## Files created / modified

| File                                                     | Phase | Action                                                                           |
| -------------------------------------------------------- | ----- | -------------------------------------------------------------------------------- |
| `personalscraper/api/tracker/torr9.py`                   | 1     | **Create**                                                                       |
| `tests/unit/test_torr9_client.py`                        | 1     | **Create**                                                                       |
| `personalscraper/api/tracker/_factory.py`                | 2     | Modify — add `"torr9"` to `_TRACKER_CLASSES`, add multi-cred construction branch |
| `personalscraper/api/_activation.py`                     | 2     | Modify — `PROVIDER_CREDS["torr9"]`, `PROVIDER_OPTIONAL_SECRETS["torr9"]`         |
| `config/tracker.json5`                                   | 2     | Modify — torr9 provider block + priority                                         |
| `config.example/tracker.json5`                           | 2     | Modify — mirror torr9 entry                                                      |
| `tests/integration/api/tracker/test_composition_root.py` | 2     | Modify — torr9 missing-cred fail-loud tests                                      |
| `tests/unit/test_tracker_capabilities_composition.py`    | 3     | Modify — torr9 `isinstance` protocol tests                                       |
| `tests/unit/test_tracker_parser_schema_drift.py`         | 3     | Modify — torr9 schema-drift → `ApiError` + multi-tracker survival                |

---

## Deferred / out of scope

- **RSS freeleech radar (R1)**: `rss/freeleech` feed (passkey, `| FREELEECH` marker) — ROADMAP R1 follow-on. `TORR9_PASSKEY` is wired as an optional secret so R1 can consume it without a creds change.
- **`GET /api/v1/categories`**: Full live category map fetch — partial static `_CATEGORY_MAP` ships now; R1 or a follow-on can fetch and cache the full map.
- **Pagination**: `page` param supported by the API but not consumed in the initial search implementation (mirrors lacale/c411 which also return the first page).
- **`.torrent` file download fallback**: `torrent_file_url` is relative + auth-required; `magnet_link` is preferred and auth-free. Fallback deferred unless magnet proves insufficient in practice.
