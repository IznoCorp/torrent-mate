# Implementation Progress — api-unify

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `api-unify`
**Feature**: Third-Party API Consumer Unification (minor)
**Bump**: 0.10.0 → 0.11.0
**Branch**: feat/api-unify
**Design**: docs/features/api-unify/DESIGN.md (v2)
**Master plan**: docs/features/api-unify/plan/INDEX.md
**PR**: _(created after last phase)_
**PR merge**: manual

## Phases

| #   | Phase                              | Type  | File                                                                                                      | Status |
| --- | ---------------------------------- | ----- | --------------------------------------------------------------------------------------------------------- | ------ |
| 1   | Foundation — contracts + transport | infra | [phase-01-foundation-transport.md](docs/features/api-unify/plan/phase-01-foundation-transport.md)         | [x]    |
| 2   | Config infra + activation          | infra | [phase-02-config-activation.md](docs/features/api-unify/plan/phase-02-config-activation.md)               | [x]    |
| 3   | Metadata family base               | infra | [phase-03-metadata-base.md](docs/features/api-unify/plan/phase-03-metadata-base.md)                       | [x]    |
| 4   | TMDB API doc                       | doc   | [phase-04-tmdb-doc.md](docs/features/api-unify/plan/phase-04-tmdb-doc.md)                                 | [x]    |
| 5   | TMDB migration                     | impl  | [phase-05-tmdb-impl.md](docs/features/api-unify/plan/phase-05-tmdb-impl.md)                               | [x]    |
| 6   | TVDB API doc                       | doc   | [phase-06-tvdb-doc.md](docs/features/api-unify/plan/phase-06-tvdb-doc.md)                                 | [x]    |
| 7   | TVDB migration                     | impl  | [phase-07-tvdb-impl.md](docs/features/api-unify/plan/phase-07-tvdb-impl.md)                               | [x]    |
| 8   | Torrent base + qBittorrent doc     | mixed | [phase-08-torrent-base-qbit-doc.md](docs/features/api-unify/plan/phase-08-torrent-base-qbit-doc.md)       | [x]    |
| 9   | qBittorrent migration              | impl  | [phase-09-qbit-impl.md](docs/features/api-unify/plan/phase-09-qbit-impl.md)                               | [x]    |
| 10  | Transmission API doc               | doc   | [phase-10-transmission-doc.md](docs/features/api-unify/plan/phase-10-transmission-doc.md)                 | [x]    |
| 11  | Transmission implementation        | impl  | [phase-11-transmission-impl.md](docs/features/api-unify/plan/phase-11-transmission-impl.md)               | [x]    |
| 12  | OMDB API doc                       | doc   | [phase-12-omdb-doc.md](docs/features/api-unify/plan/phase-12-omdb-doc.md)                                 | [x]    |
| 13  | OMDB implementation                | impl  | [phase-13-omdb-impl.md](docs/features/api-unify/plan/phase-13-omdb-impl.md)                               | [x]    |
| 14  | Trakt API doc                      | doc   | [phase-14-trakt-doc.md](docs/features/api-unify/plan/phase-14-trakt-doc.md)                               | [x]    |
| 15  | Trakt implementation               | impl  | [phase-15-trakt-impl.md](docs/features/api-unify/plan/phase-15-trakt-impl.md)                             | [x]    |
| 16  | Tracker base + ranking engine      | infra | [phase-16-tracker-base-ranking.md](docs/features/api-unify/plan/phase-16-tracker-base-ranking.md)         | [x]    |
| 17  | LaCale API doc                     | doc   | [phase-17-lacale-doc.md](docs/features/api-unify/plan/phase-17-lacale-doc.md)                             | [x]    |
| 18  | LaCale implementation              | impl  | [phase-18-lacale-impl.md](docs/features/api-unify/plan/phase-18-lacale-impl.md)                           | [x]    |
| 19  | C411 API doc                       | doc   | [phase-19-c411-doc.md](docs/features/api-unify/plan/phase-19-c411-doc.md)                                 | [x]    |
| 20  | C411 implementation                | impl  | [phase-20-c411-impl.md](docs/features/api-unify/plan/phase-20-c411-impl.md)                               | [x]    |
| 21  | Notify base + Telegram doc         | mixed | [phase-21-notify-base-telegram-doc.md](docs/features/api-unify/plan/phase-21-notify-base-telegram-doc.md) | [x]    |
| 22  | Telegram migration                 | impl  | [phase-22-telegram-impl.md](docs/features/api-unify/plan/phase-22-telegram-impl.md)                       | [x]    |
| 23  | Healthchecks API doc               | doc   | [phase-23-healthchecks-doc.md](docs/features/api-unify/plan/phase-23-healthchecks-doc.md)                 | [x]    |
| 24  | Healthchecks migration             | impl  | [phase-24-healthchecks-impl.md](docs/features/api-unify/plan/phase-24-healthchecks-impl.md)               | [x]    |
| 25  | Final cleanup + ROADMAP            | infra | [phase-25-final-cleanup.md](docs/features/api-unify/plan/phase-25-final-cleanup.md)                       | [x]    |

## Quality gate (every commit)

```bash
make check
python3 scripts/check-module-size.py
```

A commit is acceptable when `make lint test` exits 0, the size script exits 0, no new file > 1000 LOC, and coverage delta ≥ 0.

**Note**: `make lint` was first wired with ruff only; mypy was added in `b953547` (post-phase-7 corrective). All future phase gates MUST run the full `make check` (lint+test+module-size+typed-api) per CLAUDE.md "Phase Gate Checklist".

## Conventional Commits scope

All commits use scope `api-unify`:

- `feat(api-unify): ...`
- `refactor(api-unify): ...`
- `docs(api-unify): ...`
- `test(api-unify): ...`
- `chore(api-unify): ...`

## Sub-phase → SHA mapping

### Pre-phase setup

| Phase | Sub-phase                         | SHA                                                   | Notes           |
| ----- | --------------------------------- | ----------------------------------------------------- | --------------- |
| —     | Archive arch-cleanup, bump 0.11.0 | `c5e12fe`                                             | Branch creation |
| —     | Initial implementation plan       | `00b6d15`                                             | Plan generated  |
| —     | Design refinements                | `5ec1c21`, `f359ebf`, `67e784a`, `d12601a`, `fddb7d3` | DESIGN v1 → v5  |

### Phase 1 — Foundation + transport

| Sub-phase | Description                                  | SHA       |
| --------- | -------------------------------------------- | --------- |
| 1.1       | `api/_contracts.py` (AuthMode, ApiError)     | `f9c4c92` |
| 1.2       | `api/_units.py` (ByteSize) + tests           | `23b1603` |
| 1.3       | `api/transport/_policy.py`                   | `5e31ef9` |
| 1.4       | `api/transport/_auth.py` + tests             | `27d987c` |
| 1.5       | `api/transport/_rate.py` (RateLimiter)       | `37d3f8b` |
| 1.6       | `git mv` circuit breaker → `core/circuit.py` | `8bcfbf5` |
| 1.7       | Add `xmltodict` dependency                   | `97feff2` |
| 1.8       | `api/transport/_http.py` (HttpTransport)     | `c393fdc` |
| 1.9       | `scripts/check-typed-api.py` guardrail       | `7730416` |
| 1.10      | TransportPolicy reference test               | `4bdb360` |
| 1.11      | **Phase 1 gate**                             | `1e09c92` |

### Phase 2 — Config infra + activation

| Sub-phase | Description                                                                                                              | SHA       |
| --------- | ------------------------------------------------------------------------------------------------------------------------ | --------- |
| 2.1       | Pydantic api config models + `tracker/_ranking.py` (advance-shipped — needed by `config/ranking.json5` Pydantic loading) | `ef38678` |
| 2.2       | `api/_activation.py` ProviderActivation                                                                                  | `4344391` |
| 2.3       | 5 `config.example/*.json5` templates                                                                                     | `ef9b585` |
| 2.4       | Wire api config into `Config` + init-config                                                                              | `715fd7c` |
| 2.5       | **Phase 2 gate**                                                                                                         | `39f9291` |

### Phase 3 — Metadata family base

| Sub-phase | Description                                         | SHA       |
| --------- | --------------------------------------------------- | --------- |
| 3.1       | `api/metadata/_base.py` (Protocol + 8 typed models) | `6ad30a4` |
| 3.2       | `tests/unit/test_api_metadata_base.py`              | `3f5ec2f` |
| 3.3       | **Phase 3 gate**                                    | `07cda53` |

### Phase 4 — TMDB API doc

| Sub-phase | Description                                                                   | SHA       |
| --------- | ----------------------------------------------------------------------------- | --------- |
| 4.1       | **Phase 4 gate** (doc): `docs/reference/tmdb-api.md`                          | `a1ae95a` |
| 4.2       | Mark phase 4 complete                                                         | `8f13d2e` |
| 4.3       | TMDB API golden test samples (13 endpoints — deferred at gate, captured next) | `23b0fda` |
| 4.4       | Phase 5 plan iteration with phase 4 learnings                                 | `5eefc51` |

> **Audit note**: gate `a1ae95a` predated the golden samples (`23b0fda`) — minor ordering drift, samples were explicitly deferred in the gate body.

### Phase 5 — TMDB migration

| Sub-phase | Description                                                       | SHA       |
| --------- | ----------------------------------------------------------------- | --------- |
| 5.1       | TMDB response parsers + golden tests                              | `2c4713a` |
| 5.2       | Migrate TMDB client → `api/metadata/tmdb.py`                      | `d452cba` |
| 5.3       | Rewire 9 prod + 3 test consumers; delete `scraper/tmdb_client.py` | `21bfc83` |
| 5.4       | mypy: `dict[str, Any]` → `dict[str, object]`                      | `0a3cdf1` |
| 5.5       | **Phase 5 gate**                                                  | `f704cf0` |

> **Audit note**: a silent regression slipped through — `_fetch_videos_strict` was dropped in 5.2 and only restored at `b953547` (post-phase-7). Detected because mypy was not yet wired into `make lint`.

### Phase 6 — TVDB API doc

| Sub-phase | Description                                                                         | SHA       |
| --------- | ----------------------------------------------------------------------------------- | --------- |
| 6.1       | **Phase 6 gate** (doc): `docs/reference/tvdb-api.md` + 11 samples + user checkpoint | `92950f7` |
| 6.2       | Mark phase 6 complete                                                               | `c7ee87f` |

### Phase 7 — TVDB migration

| Sub-phase | Description                                                                                                               | SHA       |
| --------- | ------------------------------------------------------------------------------------------------------------------------- | --------- |
| 7.1       | TVDB response parsers + golden tests                                                                                      | `f889700` |
| 7.2       | Migrate TVDB client → `api/metadata/tvdb.py`                                                                              | `eaee7e7` |
| 7.3       | Move tenacity helpers → `core/http_helpers.py`; delete old TVDB client + `scraper/providers.py` + `scraper/http_retry.py` | `8035be3` |
| 7.4       | **Phase 7 gate** (premature — see corrective sub-phases below)                                                            | `1bf4ed1` |
| 7.5       | Corrective: restore `_fetch_videos_strict`, **wire mypy into `make lint`**, fix typed model consumers (20+ mypy errors)   | `b953547` |
| 7.6       | Corrective: fix test infrastructure for typed API changes                                                                 | `1338930` |
| 7.7       | Corrective: fix line-too-long ruff violations                                                                             | `a2d3798` |
| 7.8       | Corrective: fix all remaining test failures, full suite green                                                             | `2023ebe` |

> **Audit note**: gate `1bf4ed1` was structurally invalid — `make lint` was missing mypy (since phase 1) so 20+ type errors went unnoticed; tests were broken. The four corrective sub-phases (7.5–7.8) closed the gap. Phase gate checklist now codified in `CLAUDE.md` (commit `5928b1b`) to prevent repeats.

### Phase 8 — Torrent base + qBittorrent doc

| Sub-phase | Description                                                   | SHA       |
| --------- | ------------------------------------------------------------- | --------- |
| 8.1       | `api/torrent/_base.py` — TorrentItem + TorrentClient Protocol | `27e6956` |
| 8.2       | `api/torrent/_factory.py` — active client resolver + tests    | `8d1ceab` |
| 8.3–8.6   | Audit qBit usage + API doc + particularities                  | `fa8b506` |
| 8.4–8.5   | Real test calls (qBit 5.0.4) + doc rewrite from official spec | `e6d208d` |
| —         | Phase 9 plan adaptation from real API findings                | `396a361` |
| —         | **Phase 8 gate**                                              | `988e224` |

### Phase 9 — qBittorrent migration

| Sub-phase | Description                                       | SHA       |
| --------- | ------------------------------------------------- | --------- |
| 9.1       | `api/torrent/qbittorrent.py` + tests              | `816e3d0` |
| 9.2       | Wire factory (verification — already wired)       | `62b6baa` |
| 9.3       | Delete old module + update consumers + test paths | `6a491f6` |
| 9.4       | **Phase 9 gate**                                  | `1b6d3e8` |

### Phase 10 — Transmission API doc

| Sub-phase | Description                                                      | SHA       |
| --------- | ---------------------------------------------------------------- | --------- |
| 10.1      | `docs/reference/transmission-api.md` from official RPC spec      | `f5aadd9` |
| 10.2      | **Phase 10 gate** — option A confirmed (HttpTransport pre-check) | `69a9a61` |

### Phase 11 — Transmission implementation

| Sub-phase | Description                                                                                                                            | SHA       |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 11.1      | `chore(api-unify): add transmission-rpc dependency`                                                                                    | `9c1a762` |
| 11.2      | `api/torrent/transmission.py` + factory wiring (pre-check moved from `__init__` to `build_client()` factory — cleaner than plan §11.2) | `b119cd5` |
| 11.3      | Update factory test for transmission resolution                                                                                        | `be46779` |
| 11.4      | **Phase 11 gate**                                                                                                                      | `375d06f` |

> **Audit note**: dedicated `tests/unit/test_transmission_client.py` was missing (Plan §11.4 required it). Backfilled in the post-phase-15 corrective sub-phase (see "Cross-cutting infrastructure" below).

### Phase 12 — OMDB API doc

| Sub-phase | Description                                                                               | SHA       |
| --------- | ----------------------------------------------------------------------------------------- | --------- |
| 12.1      | `chore: add network timeout safety guardrails` (curl `--connect-timeout` block_curl hook) | `d44ec08` |
| 12.2      | **Phase 12 gate** — `docs/reference/omdb-api.md` + samples + user checkpoint captured     | `c217a23` |

> **Audit note**: `d44ec08` is a cross-cutting safety hook landing during Phase 12 (omdbapi.com hung 11+ hours during doc study — see hook docstring). Co-shipped with the gate commit.

### Phase 13 — OMDB implementation

| Sub-phase | Description                                             | SHA       |
| --------- | ------------------------------------------------------- | --------- |
| 13.1      | `api/metadata/omdb.py` (354 LOC, well under 800 budget) | `652b493` |
| 13.2      | `tests/unit/test_omdb_client.py` (26 tests)             | `0de0f64` |
| 13.3      | **Phase 13 gate**                                       | `33e100a` |

### Phase 14 — Trakt API doc

| Sub-phase | Description                                                                     | SHA       |
| --------- | ------------------------------------------------------------------------------- | --------- |
| 14.1      | **Phase 14 gate** — `docs/reference/trakt-api.md` + 4 samples + user checkpoint | `b3e32fe` |

### Phase 15 — Trakt implementation

| Sub-phase | Description                                  | SHA       |
| --------- | -------------------------------------------- | --------- |
| 15.1      | `api/metadata/trakt.py` (367 LOC) + 11 tests | `8877e70` |
| 15.2      | Ruff formatting fixup on torrent modules     | `d755a3f` |
| 15.3      | **Phase 15 gate**                            | `a4e214e` |

### Phase 16 — Tracker base + ranking engine

| Sub-phase | Description                                                     | SHA       |
| --------- | --------------------------------------------------------------- | --------- |
| 16.1      | `api/tracker/_base.py` — TrackerResult + TrackerClient Protocol | `8a79c35` |
| 16.2      | `api/tracker/_ranking.py` — `rank()` engine                     | `94beb18` |
| 16.3      | `api/tracker/_registry.py` — TrackerRegistry                    | `24ba226` |
| 16.4      | Ranking engine + ThresholdEntry tests (15 tests)                | `663a538` |
| 16.5      | **Phase 16 gate**                                               | `4d8d16e` |

### Phase 17 — LaCale API doc

| Sub-phase | Description                                                                       | SHA       |
| --------- | --------------------------------------------------------------------------------- | --------- |
| 17.1–17.5 | `docs/reference/lacale-api.md` from TorrentMaker source (search + meta endpoints) | `b912b42` |
| 17.6      | User checkpoint baked into doc as "Open decisions" (defaults stand for Phase 18)  | `b912b42` |
| 17.7      | **Phase 17 gate** (single-commit phase)                                           | `b912b42` |

### Phase 18 — LaCale implementation

| Sub-phase | Description                                                                | SHA       |
| --------- | -------------------------------------------------------------------------- | --------- |
| 18.1      | `api/tracker/lacale.py` — LaCaleClient + policy + `_parse_title` (221 LOC) | `8e8fde4` |
| 18.2      | `tests/unit/test_lacale_client.py` (17 tests)                              | `ff8fbe7` |
| 18.3      | **Phase 18 gate**                                                          | `6e0be02` |

### Phase 19 — C411 API doc

| Sub-phase | Description                                                         | SHA       |
| --------- | ------------------------------------------------------------------- | --------- |
| 19.1–19.5 | `docs/reference/c411-api.md` from TorrentMaker source (Torznab/XML) | `9f9c9f5` |
| 19.6      | User checkpoint baked into doc as "Open decisions" (defaults stand) | `9f9c9f5` |
| 19.7      | **Phase 19 gate** (single-commit phase)                             | `9f9c9f5` |

### Phase 17/18/19/20 revisit — real API samples (2026-05-07)

User-driven revisit: capture real API responses, store as samples, reconcile docs + tests against reality.

| Step                                                                                             | SHA       |
| ------------------------------------------------------------------------------------------------ | --------- |
| C411 samples (caps, search, tvsearch, movie, empty, error-auth) + doc reconciliation             | `064bd87` |
| LaCale rebuild (5 samples + impl rewrite + tests against real fixtures + qbit passkey redaction) | `6ebba20` |

Major drifts captured:

- **C411**: `<guid>` is the 40-char infohash (not a URL); `<size>` element duplicates `enclosure[@length]` and `torznab:attr[size]`; caps does NOT advertise `cat` (narrowing via `t=movie`/`t=tvsearch` only); `category[@name]` is the Newznab class, `[@description]` is the human label; subcat `@id` collides across parents; `enclosure[@url]` embeds the apikey; `peers == seeders` when no leechers (clamp).
- **LaCale**: `category` is the human label, **not** a slug; `downloadLink` is `/api/download/<infoHash>?token=<JWT>` (per-request signed JWT, sensitive); `guid` is a short opaque ID, distinct from `infoHash`; `pubDate` carries milliseconds; `leechers` is exposed directly; meta returns ONLY `{categories: [...]}` (no `tagGroups`/`ungroupedTags`); **no freeleech indicator exists** (neither title prefix nor JSON flag) — `is_freeleech`/`is_silverleech` hardcoded `False`.
- **LACALE_API_KEY ≠ LACALE_PASSKEY**: separate secrets; the BT announce passkey is rejected by the API.
- **Side fix**: redact LaCale passkey + C411 passkey leaked into `docs/reference/_samples/qbittorrent/torrents-info-{all,completed}.json` (introduced in `e6d208d`). Current snapshot only — history rewrite deferred to user.

### Phase 20 — C411 implementation

| Sub-phase | Description                                                      | SHA       |
| --------- | ---------------------------------------------------------------- | --------- |
| 20.1      | `api/tracker/c411.py` — Torznab XML client (263 LOC)             | `6ecb26a` |
| 20.2      | `tests/unit/test_c411_client.py` (18 tests against real samples) | `c272985` |
| 20.3      | **Phase 20 gate**                                                | `c7fbf12` |

### Phase 21 — Notify base + Telegram doc

| Sub-phase | Description                                                                                  | SHA             |
| --------- | -------------------------------------------------------------------------------------------- | --------------- |
| 21.1      | `api/notify/_base.py` — Notifier + HealthChecker Protocols (DESIGN §7.1)                     | `b2fe5fd`       |
| 21.2–21.5 | `docs/reference/telegram-api.md` + 5 real samples (success, malformed HTML, 401, 400, getMe) | `abbb5ab`       |
| 21.6      | User checkpoint — defaults stand (see "Open decisions for Phase 22" in doc)                  | _(in doc)_      |
| 21.7      | **Phase 21 gate**                                                                            | _(this commit)_ |

> **Phase 21 user checkpoint decisions** (defaults from `telegram-api.md` §"Open decisions"):
> token-in-URL with `auth = NoAuth()`; `ok:false` → fail-soft (`send()` returns `False`); no
> chunking (YAGNI, reports < 4096 chars today); `parse_mode="HTML"` default; default
> `RetryPolicy` (5xx + 429 only); `max_requests_per_second = 1.0`; healthchecks half stays in
> `notifier.py` until Phase 24 — only the Telegram half is migrated in Phase 22.

### Phase 22 — Telegram migration

| Sub-phase | Description                                                                                          | SHA             |
| --------- | ---------------------------------------------------------------------------------------------------- | --------------- |
| 22.1      | `api/notify/telegram.py` — `TelegramNotifier` on `HttpTransport` + `_chunk()` (193 LOC)              | `3c7a4af`       |
| 22.2      | Rewire consumer (`commands/pipeline.py`); trim `notifier.py` to healthchecks only; update test stubs | `6084abd`       |
| 22.3      | `tests/unit/test_telegram_notifier.py` (20 tests: policy, send, chunking, fail-soft, is_configured)  | `7fac2fd`       |
| 22.4      | **Phase 22 gate**                                                                                    | _(this commit)_ |

> **Phase 22 deviation from plan**: chunking was implemented despite the doc saying "do NOT
> add chunking (YAGNI)". Plan §22.1 still mandated `_chunk()` and §22.3 mandated a chunking
> test, so the implementation supports chunking but the production reports remain well under
> the 4096-char cap. Net: harmless, plan-compliant, and ready if a future report grows.

### Phase 23 — Healthchecks API doc

| Sub-phase | Description                                                                              | SHA             |
| --------- | ---------------------------------------------------------------------------------------- | --------------- |
| 23.1–23.4 | `docs/reference/healthchecks-api.md` from official ping protocol (lifecycle, plain-text) | _(this commit)_ |
| 23.5      | User checkpoint — defaults stand (Option A: `response_format="text"` via HttpTransport)  | _(in doc)_      |
| 23.6      | **Phase 23 gate** (single-commit phase)                                                  | _(this commit)_ |

> **Phase 23 user checkpoint decisions** (defaults from `healthchecks-api.md` §"Open decisions"):
> Option A (plain-text via `TransportPolicy.response_format="text"`); `base_url` = env var
> verbatim with `/start`/`/fail` as path suffixes; fail-soft `None`-returning Protocol;
> `RateLimitPolicy(0.0)` (disabled, 2 pings/run); default `RetryPolicy`; `notifier.py` deleted
> in Phase 24.
>
> **Sample limitation**: `200 OK` and `404 (not found)` not captured — public hc-ping.com
> will not respond `OK` without a registered UUID and the project's real URL is a secret. The
> single `400 invalid url format` sample is sufficient to validate the parser path.

### Phase 24 — Healthchecks migration

| Sub-phase | Description                                                                                                                   | SHA             |
| --------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------- |
| 24.1      | `api/notify/healthchecks.py` — `HealthcheckClient` with `response_format="text"` (133 LOC)                                    | `1c00df5`       |
| 24.2      | Rewire `commands/pipeline.py` (start/end pings via client); delete `personalscraper/notifier.py` and `tests/test_notifier.py` | `283c3d9`       |
| 24.3      | `tests/unit/test_healthcheck_client.py` (15 tests: policy, lifecycle, fail-soft, is_configured)                               | `987c6fe`       |
| 24.4      | **Phase 24 gate**                                                                                                             | _(this commit)_ |

> **Phase 24 deviation from plan**: `REQUIRED_CREDS` aligns with the existing config field
> `Settings.healthcheck_url` (env var `HEALTHCHECK_URL`) — not `HEALTHCHECK_PING_URL` as the
> plan's pseudo-code suggested. Keeps the env contract stable for users who already have a
> `HEALTHCHECK_URL` set; renaming would have been a silent breakage. Plan was a forward-design
> sketch, not the contract.

### Phase 25 — Final cleanup + ROADMAP

| Sub-phase | Description                                                                                                                                           | SHA             |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| 25.1–25.3 | Residual audits: 7 deleted modules absent, 0 `TMDBError`/`TVDBError` refs, 0 dead config refs (docstring scrubs only)                                 | `3ae1ca4`       |
| 25.4–25.5 | `architecture.md` (api/+core/ subtree), `CLAUDE.md` ref index (5 new rows), `ROADMAP.md` (P0 marked done, P3 trackers added, completed entry written) | `c267076`       |
| 25.6      | Version verified: `personalscraper.__version__ == "0.11.0"` ✓                                                                                         | _(verified)_    |
| 25.7      | Smoke checks: `import personalscraper`, `core.circuit`, `core.http_helpers` all OK                                                                    | _(verified)_    |
| 25.8      | **Phase 25 gate (FINAL)**                                                                                                                             | _(this commit)_ |

> **Final feature summary**:
>
> - **2786 tests pass** (started at 2768 pre-phase-21).
> - **7 modules deleted**: `tmdb_client.py`, `tvdb_client.py`, `circuit_breaker.py`,
>   `http_retry.py`, `providers.py`, `qbit_client.py`, `notifier.py`.
> - **10 reference docs** under `docs/reference/<provider>-api.md` with real samples in
>   `_samples/<provider>/`.
> - **5 config files** in `config.example/` (`metadata`, `torrent`, `tracker`, `ranking`,
>   `notify`).
> - **All 5 family Protocols** live: `MetadataClient`, `TorrentClient`, `TrackerClient`,
>   `Notifier`, `HealthChecker`.

### Post-phase-15 corrective gate (audit cleanup)

Triggered by audit dated 2026-05-07 — 4 issues surfaced:

1. **Trakt creds inconsistency** — `_activation.py` required `[CLIENT_ID, CLIENT_SECRET]` but `TraktClient.REQUIRED_CREDS = [CLIENT_ID]` only. Trakt app-only auth needs only CLIENT_ID; CLIENT_SECRET is OAuth-only (out of scope per DESIGN §1.2 + Phase 14 doc decision). DESIGN §8.7 + `_activation.py` aligned to single-cred. Test `test_multiple_required_missing` re-purposed to `telegram` (still has 2 creds).
2. **`make test` parallel pollution** — `pytest -v -n auto` produced flaky 0–9 failures from `tests/scraper/test_ytdlp_downloader.py::TestCookieConfig`. Root cause: `CookieConfig.from_env()` calls `get_settings()` (`@lru_cache`), so tests sharing an xdist worker saw a Settings cached from a prior test's monkeypatched env. Fix: autouse fixture in `TestCookieConfig` clearing `get_settings.cache_clear()` before each test. Verified stable across 4 consecutive `pytest -n auto` runs.
3. **`scripts/check-typed-api.py` exit 1** — script naively flagged `dict[str, Any]` in private parsers (`_parse_*`) and local variable annotations inside public files (omdb.py, trakt.py). DESIGN §13.3 only forbids it in **public API surface**. Refined script to flag only on `def <public_name>(...)` signature lines (multi-line signatures handled).
4. **Missing `tests/unit/test_transmission_client.py`** — Plan §11.4 demanded TorrentItem mapping + status enum + factory pre-check tests. Backfilled with 25 tests covering single/multi-file content_path, SEEDING vs SEED_PENDING filtering, CSRF 409 tolerance, 401/500 abort.

### Documented design drifts (deliberate, kept)

| DESIGN ref | Original spec                                  | Reality + rationale                                                                                                                                                                                      |
| ---------- | ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §4.1       | `get_notations() -> Notations \| None`         | Implemented as `list[Notations] \| None`. OMDB returns 3 sources at once (IMDB + RT + Metacritic) — list is the only honest shape. Trakt/TVDB return single-source list with len 1.                      |
| §5.1       | `TorrentItem.content_path: Path`               | `Path \| None`. Transmission may have no `download_dir` until torrent fully renamed (Phase 10 doc §10.4). qBit also surfaces empty `content_path` for incomplete torrents.                               |
| §8.7       | `trakt: [CLIENT_ID, CLIENT_SECRET]`            | `trakt: [CLIENT_ID]`. App-only auth (search/details/ratings/related/trending) — CLIENT_SECRET is OAuth user-flow only (out of scope per §1.2).                                                           |
| Plan §11.2 | Pre-check inside `TransmissionClient.__init__` | Pre-check moved to `build_client()` factory. Cleaner separation: client takes pure credentials, factory owns reachability check. Same observability via dedicated `transmission-precheck` provider name. |

### Cross-cutting infrastructure (post-phase-7)

These commits live on `feat/api-unify` and stay on the branch (decision: kept inline; no `chore/dev-infra` split). They formalize the gate hygiene that the phase 7 incident exposed.

| SHA       | Subject                                                            |
| --------- | ------------------------------------------------------------------ |
| `5928b1b` | docs: phase gate checklist in CLAUDE.md                            |
| `cde2d81` | chore: `make gate` target with secret scan + residual import audit |
| `2d5a715` | chore: pre-push hook with gitleaks                                 |
| `52817a1` | perf: scope gitleaks to source dirs only                           |

## Known debt & deferred decisions

- **`TMDBClient.circuit` property** (`api/metadata/tmdb.py:87-90`) exposes private `self._transport._circuit` — pragmatic for legacy `circuit_breaker_threshold` config compat, used by `scraper/orchestrator.py:138,211` and `tests/scraper/test_scraper.py:1188-1273`. Tests assign directly to `circuit` (`# type: ignore[misc]`). Encapsulation refactor deferred until a 3rd metadata client lands (OMDB or Trakt) so the abstraction has more than 2 use cases.
- **Test layout**: DESIGN §12 R14 referenced `tests/api/`. Reality: `tests/unit/test_api_*.py` + `tests/integration/test_transport_policy.py`. Naming preserves discoverability — accepted deviation.
- **Asymmetric client construction**: `TMDBClient(transport, ...)` vs `TVDBClient(api_key, ...)`. The TVDB shape is forced by bootstrap login. A future factory layer (Phase 8 torrent factory groundwork) will need to handle both.
- **`tracker/_ranking.py` advance-shipped in Phase 2**: justified by Pydantic config validation; documented in DESIGN.md §10 (phase ordering rationale). Phase 16 still owns `_base.py` + `_registry.py` + `rank()` function.

## Next action

**All 25 phases complete.** Feature ready for PR — run `/implement:feature-pr` to push the
branch, open the PR against `main`, and poll CI to green.
