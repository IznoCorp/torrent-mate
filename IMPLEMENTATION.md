# Implementation Progress — torr9

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Additional Tracker — torr9 (authenticated JSON search + freeleech RSS) (minor)
**Version bump**: 0.36.2 → 0.37.0
**Branch**: feat/torr9
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/209
**Design**: docs/features/torr9/DESIGN.md
**Master plan**: docs/features/torr9/plan/INDEX.md

## Phases

| #   | Phase                                                                                   | File                                           | Status |
| --- | --------------------------------------------------------------------------------------- | ---------------------------------------------- | ------ |
| 1   | Torr9Client + lazy JWT login + JSON search + golden tests                               | phase-01-client-login-jwt-golden.md            | [x]    |
| 2   | Registry wiring + creds + config overlays + composition-root tests                      | phase-02-registry-wiring-creds-config.md       | [x]    |
| 3   | FreeleechAware re-check + capabilities + schema-drift + ACC gate                        | phase-03-capabilities-schema-drift-acc-gate.md | [x]    |
| 4   | Productionize torr9 — enable + seeders enrich + multi-cred protocol + .torrent download | phase-04-productionize.md                      | [x]    |
| 5   | Fix search endpoint (CRITICAL: was hitting listing endpoint) + real shape + tmdb_id     | phase-05-fix-search-endpoint.md                | [ ]    |

## Review cycles

### Cycle 2 (PR #209) — phase-4 additions: understand workflow → implement → adversarial review → fix

Operator added 4 items to PR #209 (decisions 2026-06-19/20): enable torr9, top-K=10 seeders
enrichment (default on), generic `from_env` multi-cred protocol, real `.torrent` `/download`
fallback. Grounded by a live API probe + a 4-agent understand workflow (config/CI safety,
ranking-seeders necessity, download consumption, protocol design). Implemented in phase 4
(5 commits a3b028f8..a2a13a43), **live-re-reproduced end-to-end** against the real torr9 API
(search+enrich+get_details+`.torrent` download all confirmed). Adversarial review
(code-reviewer + silent-failure-hunter) found and I fixed (2 commits b0825326, 3802dce3):

- **CRITICAL** — enrichment loop caught only `ApiError`; a mid-enrichment `CircuitOpenError`
  (sibling of `ApiError`, threshold 5 / top_k 10 → reachable in one search) escaped and
  aborted the WHOLE multi-tracker search, discarding sibling results. Fixed: catch
  `CircuitOpenError` + `break` (fail-soft as documented). Regression test confirmed
  fails-before/passes-after.
- **MEDIUM** — empty `id` → malformed `/torrents//download`; now `download_url=None` (clean
  `TorrentFetchError`). **MEDIUM** — `transports()` `except Exception` narrowed to
  `(ApiError, CircuitOpenError, RequestException)` + `error_type` log.
  Verified: `make check` 7042 passed (0 failed), `make lint` green, 97 tracker tests, all
  phase-4 gate probes + live e2e pass. No remaining critical/major/medium → loop exits.
  Merge mode = **manual** → handoff to operator after CI green.

### Cycle 1 (PR #209) — adversarial review (code-reviewer + silent-failure-hunter + pr-test-analyzer)

**Retained findings → fix (user decisions 2026-06-19):**

- **MAJOR (test gaps):** factory torr9 _construction_ path untested (only the negative cred-gate is); second-consecutive-401 fail-loud untested for `search` + `is_freeleech`; `_login` Bearer-application unverified against a real session.
- **MEDIUM (architecture — user chose the thorough options):** `_login()` reached into the transport's private `_session` → **refactor to the TVDB lazy-transport pattern** (rebuild transport with `BearerAuth` in the policy, no private access). The `if name == "torr9"` factory literal → **generalize** to a `build_from_env` capability dispatch + add `ProviderName.TORR9`.
- **MEDIUM (doc/comment):** DESIGN §Approach still showed pre-build `policy(username,password)`/`__init__(transport)` signatures → reconcile to as-built; `torrent_file_url` "last resort" comment is rot (never implemented) + silent `download_url=None` with no log → fix comment + add warning.
- **MINOR:** untested `_parse_item`/`_parse_iso` None-branches.

**Ignored / deferred (noted, not fixed):** batch-atomic parse (one bad item aborts the torr9 batch) is by-design (anti-drift, matches lacale/c411); detail-endpoint `seeders`/`leechers` for ranking deferred (DESIGN). A full multi-cred _protocol_ (vs the `build_from_env` hook) remains a future framework item.

### Cycle 1 fix (commits efdb99f9..9fbb431d) + re-review CLEAN

torr9 auth rebuilt on the TVDB lazy-transport pattern (no private `_session` access); factory dispatches on the `build_from_env` capability (no name literal); `ProviderName.TORR9` added; gap tests added (second-401 fail-loud ×2 asserting `http_status==401`, factory-construction success asserting `isinstance(built, Torr9Client)` + `_username`, magnet/category None-branches); magnet comment-rot fixed + `torr9_missing_magnet` warning; DESIGN reconciled. Verified: 86 torr9 tests + `make check` 7021 passed (0 failed), `make lint` green, all 6 acceptance probes pass, no `ProviderName` ripple. No new critical/major/medium findings → review loop exits (Case A). Merge mode = **manual** → handoff to operator after CI green.

## Next action

All phases complete — run `/implement:feature-pr` (local gate → push → PR → CI → review).

> **FreeleechAware concern — RESOLVED (user decision 2026-06-19):** the DESIGN-vs-plan
> inconsistency flagged at phase 1 was decided by the user: **implement FreeleechAware**.
> A live probe confirmed torr9 exposes a real per-torrent detail endpoint
> (`GET /api/v1/torrents/{id}` → single torrent with `is_freeleech` + seeders/leechers),
> so `is_freeleech(torrent_id)` is a genuine pre-download re-check, NOT a vacuous stub.
> Phase 3 implements it; DESIGN + api-ref reconciled; ACC-8 added and passing. The class
> is now `Torr9Client(TorrentSearchable, CategoryListable, FreeleechAware)`. Detail-endpoint
> `seeders`/`leechers` for ranking is **deferred** (not in this feature).

> **Prep note (research 2026-06-19):** torr9 captured LIVE — it is a full search
> tracker via the **authenticated JSON API** (`POST /auth/login` → JWT;
> `GET /torrents?q=<query>` + Bearer → `{limit,page,torrents[]}`), NOT browse-only.
> Item carries `is_freeleech` (bool) + `magnet_link` (auth-free download); **no
> seeders**. Passkey RSS feeds (`freeleech`/`recent`) feed the radar R1. Dual auth:
> JWT (`TORR9_USERNAME`/`TORR9_PASSWORD`) + passkey (`TORR9_PASSKEY`), creds in
> `.env`. Reference: `docs/reference/torr9-api.md`. Golden fixtures:
> `docs/reference/_samples/torr9/`. The prepared plan was regenerated from the
> corrected (post-capture) design.
