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
| 21  | Notify base + Telegram doc         | mixed | [phase-21-notify-base-telegram-doc.md](docs/features/api-unify/plan/phase-21-notify-base-telegram-doc.md) | [ ]    |
| 22  | Telegram migration                 | impl  | [phase-22-telegram-impl.md](docs/features/api-unify/plan/phase-22-telegram-impl.md)                       | [ ]    |
| 23  | Healthchecks API doc               | doc   | [phase-23-healthchecks-doc.md](docs/features/api-unify/plan/phase-23-healthchecks-doc.md)                 | [ ]    |
| 24  | Healthchecks migration             | impl  | [phase-24-healthchecks-impl.md](docs/features/api-unify/plan/phase-24-healthchecks-impl.md)               | [ ]    |
| 25  | Final cleanup + ROADMAP            | infra | [phase-25-final-cleanup.md](docs/features/api-unify/plan/phase-25-final-cleanup.md)                       | [ ]    |

## Quality gate (every commit)

```bash
make check
python3 scripts/check-module-size.py
```

A commit is acceptable when `make lint test` exits 0, the size script exits 0, no new file > 1000 LOC, and coverage delta ≥ 0.

**Note**: `make lint` was first wired with ruff only; mypy was added in `8e0892d` (post-phase-7 corrective). All future phase gates MUST run the full `make check` (lint+test+module-size+typed-api) per CLAUDE.md "Phase Gate Checklist".

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
| —     | Archive arch-cleanup, bump 0.11.0 | `58e24ec`                                             | Branch creation |
| —     | Initial implementation plan       | `9ff0756`                                             | Plan generated  |
| —     | Design refinements                | `4281bbb`, `d9d57c8`, `e3db15b`, `1557825`, `59a9a54` | DESIGN v1 → v5  |

### Phase 1 — Foundation + transport

| Sub-phase | Description                                  | SHA       |
| --------- | -------------------------------------------- | --------- |
| 1.1       | `api/_contracts.py` (AuthMode, ApiError)     | `a917434` |
| 1.2       | `api/_units.py` (ByteSize) + tests           | `ea14032` |
| 1.3       | `api/transport/_policy.py`                   | `9ad2759` |
| 1.4       | `api/transport/_auth.py` + tests             | `d81e2b1` |
| 1.5       | `api/transport/_rate.py` (RateLimiter)       | `229bf62` |
| 1.6       | `git mv` circuit breaker → `core/circuit.py` | `fc52ec9` |
| 1.7       | Add `xmltodict` dependency                   | `e78817d` |
| 1.8       | `api/transport/_http.py` (HttpTransport)     | `082b85c` |
| 1.9       | `scripts/check-typed-api.py` guardrail       | `47f9eeb` |
| 1.10      | TransportPolicy reference test               | `8c6e990` |
| 1.11      | **Phase 1 gate**                             | `c0cb871` |

### Phase 2 — Config infra + activation

| Sub-phase | Description                                                                                                              | SHA       |
| --------- | ------------------------------------------------------------------------------------------------------------------------ | --------- |
| 2.1       | Pydantic api config models + `tracker/_ranking.py` (advance-shipped — needed by `config/ranking.json5` Pydantic loading) | `4232634` |
| 2.2       | `api/_activation.py` ProviderActivation                                                                                  | `620df02` |
| 2.3       | 5 `config.example/*.json5` templates                                                                                     | `d6ca061` |
| 2.4       | Wire api config into `Config` + init-config                                                                              | `10459bf` |
| 2.5       | **Phase 2 gate**                                                                                                         | `850b918` |

### Phase 3 — Metadata family base

| Sub-phase | Description                                         | SHA       |
| --------- | --------------------------------------------------- | --------- |
| 3.1       | `api/metadata/_base.py` (Protocol + 8 typed models) | `b6053c8` |
| 3.2       | `tests/unit/test_api_metadata_base.py`              | `b64084d` |
| 3.3       | **Phase 3 gate**                                    | `b67e8b6` |

### Phase 4 — TMDB API doc

| Sub-phase | Description                                                                   | SHA       |
| --------- | ----------------------------------------------------------------------------- | --------- |
| 4.1       | **Phase 4 gate** (doc): `docs/reference/tmdb-api.md`                          | `262fae0` |
| 4.2       | Mark phase 4 complete                                                         | `a24354d` |
| 4.3       | TMDB API golden test samples (13 endpoints — deferred at gate, captured next) | `857a630` |
| 4.4       | Phase 5 plan iteration with phase 4 learnings                                 | `818a81a` |

> **Audit note**: gate `262fae0` predated the golden samples (`857a630`) — minor ordering drift, samples were explicitly deferred in the gate body.

### Phase 5 — TMDB migration

| Sub-phase | Description                                                       | SHA       |
| --------- | ----------------------------------------------------------------- | --------- |
| 5.1       | TMDB response parsers + golden tests                              | `d83a84d` |
| 5.2       | Migrate TMDB client → `api/metadata/tmdb.py`                      | `0e3908c` |
| 5.3       | Rewire 9 prod + 3 test consumers; delete `scraper/tmdb_client.py` | `487c597` |
| 5.4       | mypy: `dict[str, Any]` → `dict[str, object]`                      | `5fc98ce` |
| 5.5       | **Phase 5 gate**                                                  | `c860c00` |

> **Audit note**: a silent regression slipped through — `_fetch_videos_strict` was dropped in 5.2 and only restored at `8e0892d` (post-phase-7). Detected because mypy was not yet wired into `make lint`.

### Phase 6 — TVDB API doc

| Sub-phase | Description                                                                         | SHA       |
| --------- | ----------------------------------------------------------------------------------- | --------- |
| 6.1       | **Phase 6 gate** (doc): `docs/reference/tvdb-api.md` + 11 samples + user checkpoint | `a4e54df` |
| 6.2       | Mark phase 6 complete                                                               | `47748c9` |

### Phase 7 — TVDB migration

| Sub-phase | Description                                                                                                               | SHA       |
| --------- | ------------------------------------------------------------------------------------------------------------------------- | --------- |
| 7.1       | TVDB response parsers + golden tests                                                                                      | `2c139b5` |
| 7.2       | Migrate TVDB client → `api/metadata/tvdb.py`                                                                              | `32302d2` |
| 7.3       | Move tenacity helpers → `core/http_helpers.py`; delete old TVDB client + `scraper/providers.py` + `scraper/http_retry.py` | `6dbc7fe` |
| 7.4       | **Phase 7 gate** (premature — see corrective sub-phases below)                                                            | `7e93f17` |
| 7.5       | Corrective: restore `_fetch_videos_strict`, **wire mypy into `make lint`**, fix typed model consumers (20+ mypy errors)   | `8e0892d` |
| 7.6       | Corrective: fix test infrastructure for typed API changes                                                                 | `ef5de81` |
| 7.7       | Corrective: fix line-too-long ruff violations                                                                             | `c4f8f7d` |
| 7.8       | Corrective: fix all remaining test failures, full suite green                                                             | `0bc3b87` |

> **Audit note**: gate `7e93f17` was structurally invalid — `make lint` was missing mypy (since phase 1) so 20+ type errors went unnoticed; tests were broken. The four corrective sub-phases (7.5–7.8) closed the gap. Phase gate checklist now codified in `CLAUDE.md` (commit `e6cc0ac`) to prevent repeats.

### Phase 8 — Torrent base + qBittorrent doc

| Sub-phase | Description                                                   | SHA       |
| --------- | ------------------------------------------------------------- | --------- |
| 8.1       | `api/torrent/_base.py` — TorrentItem + TorrentClient Protocol | `9b416ee` |
| 8.2       | `api/torrent/_factory.py` — active client resolver + tests    | `8f026c3` |
| 8.3–8.6   | Audit qBit usage + API doc + particularities                  | `a00dae9` |
| 8.4–8.5   | Real test calls (qBit 5.0.4) + doc rewrite from official spec | `586cbb5` |
| —         | Phase 9 plan adaptation from real API findings                | `281cada` |
| —         | **Phase 8 gate**                                              | `f9bfb6b` |

### Phase 9 — qBittorrent migration

| Sub-phase | Description                                       | SHA       |
| --------- | ------------------------------------------------- | --------- |
| 9.1       | `api/torrent/qbittorrent.py` + tests              | `0d6abdd` |
| 9.2       | Wire factory (verification — already wired)       | `5e9ab07` |
| 9.3       | Delete old module + update consumers + test paths | `56052a7` |
| 9.4       | **Phase 9 gate**                                  | `b3c51df` |

### Phase 10 — Transmission API doc

| Sub-phase | Description                                                      | SHA       |
| --------- | ---------------------------------------------------------------- | --------- |
| 10.1      | `docs/reference/transmission-api.md` from official RPC spec      | `f6932d1` |
| 10.2      | **Phase 10 gate** — option A confirmed (HttpTransport pre-check) | `503fc9a` |

### Phase 11 — Transmission implementation

| Sub-phase | Description                                                                                                                            | SHA       |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 11.1      | `chore(api-unify): add transmission-rpc dependency`                                                                                    | `b922555` |
| 11.2      | `api/torrent/transmission.py` + factory wiring (pre-check moved from `__init__` to `build_client()` factory — cleaner than plan §11.2) | `b987c81` |
| 11.3      | Update factory test for transmission resolution                                                                                        | `88acd62` |
| 11.4      | **Phase 11 gate**                                                                                                                      | `aab22b1` |

> **Audit note**: dedicated `tests/unit/test_transmission_client.py` was missing (Plan §11.4 required it). Backfilled in the post-phase-15 corrective sub-phase (see "Cross-cutting infrastructure" below).

### Phase 12 — OMDB API doc

| Sub-phase | Description                                                                               | SHA       |
| --------- | ----------------------------------------------------------------------------------------- | --------- |
| 12.1      | `chore: add network timeout safety guardrails` (curl `--connect-timeout` block_curl hook) | `460b567` |
| 12.2      | **Phase 12 gate** — `docs/reference/omdb-api.md` + samples + user checkpoint captured     | `74deaff` |

> **Audit note**: `460b567` is a cross-cutting safety hook landing during Phase 12 (omdbapi.com hung 11+ hours during doc study — see hook docstring). Co-shipped with the gate commit.

### Phase 13 — OMDB implementation

| Sub-phase | Description                                             | SHA       |
| --------- | ------------------------------------------------------- | --------- |
| 13.1      | `api/metadata/omdb.py` (354 LOC, well under 800 budget) | `c7f06e0` |
| 13.2      | `tests/unit/test_omdb_client.py` (26 tests)             | `12e5187` |
| 13.3      | **Phase 13 gate**                                       | `dd1968c` |

### Phase 14 — Trakt API doc

| Sub-phase | Description                                                                     | SHA       |
| --------- | ------------------------------------------------------------------------------- | --------- |
| 14.1      | **Phase 14 gate** — `docs/reference/trakt-api.md` + 4 samples + user checkpoint | `a358c9b` |

### Phase 15 — Trakt implementation

| Sub-phase | Description                                  | SHA       |
| --------- | -------------------------------------------- | --------- |
| 15.1      | `api/metadata/trakt.py` (367 LOC) + 11 tests | `4080f39` |
| 15.2      | Ruff formatting fixup on torrent modules     | `dab7086` |
| 15.3      | **Phase 15 gate**                            | `378601f` |

### Phase 16 — Tracker base + ranking engine

| Sub-phase | Description                                                     | SHA       |
| --------- | --------------------------------------------------------------- | --------- |
| 16.1      | `api/tracker/_base.py` — TrackerResult + TrackerClient Protocol | `f196966` |
| 16.2      | `api/tracker/_ranking.py` — `rank()` engine                     | `a10238d` |
| 16.3      | `api/tracker/_registry.py` — TrackerRegistry                    | `7a54dcd` |
| 16.4      | Ranking engine + ThresholdEntry tests (15 tests)                | `ee5b453` |
| 16.5      | **Phase 16 gate**                                               | `5cac242` |

### Phase 17 — LaCale API doc

| Sub-phase | Description                                                                       | SHA       |
| --------- | --------------------------------------------------------------------------------- | --------- |
| 17.1–17.5 | `docs/reference/lacale-api.md` from TorrentMaker source (search + meta endpoints) | `305625a` |
| 17.6      | User checkpoint baked into doc as "Open decisions" (defaults stand for Phase 18)  | `305625a` |
| 17.7      | **Phase 17 gate** (single-commit phase)                                           | `305625a` |

### Phase 18 — LaCale implementation

| Sub-phase | Description                                                                | SHA       |
| --------- | -------------------------------------------------------------------------- | --------- |
| 18.1      | `api/tracker/lacale.py` — LaCaleClient + policy + `_parse_title` (221 LOC) | `60a2023` |
| 18.2      | `tests/unit/test_lacale_client.py` (17 tests)                              | `7b78698` |
| 18.3      | **Phase 18 gate**                                                          | `1d66213` |

### Phase 19 — C411 API doc

| Sub-phase | Description                                                         | SHA       |
| --------- | ------------------------------------------------------------------- | --------- |
| 19.1–19.5 | `docs/reference/c411-api.md` from TorrentMaker source (Torznab/XML) | `bf8e748` |
| 19.6      | User checkpoint baked into doc as "Open decisions" (defaults stand) | `bf8e748` |
| 19.7      | **Phase 19 gate** (single-commit phase)                             | `bf8e748` |

### Phase 17/18/19/20 revisit — real API samples (2026-05-07)

User-driven revisit: capture real API responses, store as samples, reconcile docs + tests against reality.

| Step                                                                                             | SHA       |
| ------------------------------------------------------------------------------------------------ | --------- |
| C411 samples (caps, search, tvsearch, movie, empty, error-auth) + doc reconciliation             | `a5c1cd4` |
| LaCale rebuild (5 samples + impl rewrite + tests against real fixtures + qbit passkey redaction) | `256c6b9` |

Major drifts captured:

- **C411**: `<guid>` is the 40-char infohash (not a URL); `<size>` element duplicates `enclosure[@length]` and `torznab:attr[size]`; caps does NOT advertise `cat` (narrowing via `t=movie`/`t=tvsearch` only); `category[@name]` is the Newznab class, `[@description]` is the human label; subcat `@id` collides across parents; `enclosure[@url]` embeds the apikey; `peers == seeders` when no leechers (clamp).
- **LaCale**: `category` is the human label, **not** a slug; `downloadLink` is `/api/download/<infoHash>?token=<JWT>` (per-request signed JWT, sensitive); `guid` is a short opaque ID, distinct from `infoHash`; `pubDate` carries milliseconds; `leechers` is exposed directly; meta returns ONLY `{categories: [...]}` (no `tagGroups`/`ungroupedTags`); **no freeleech indicator exists** (neither title prefix nor JSON flag) — `is_freeleech`/`is_silverleech` hardcoded `False`.
- **LACALE_API_KEY ≠ LACALE_PASSKEY**: separate secrets; the BT announce passkey is rejected by the API.
- **Side fix**: redact LaCale passkey + C411 passkey leaked into `docs/reference/_samples/qbittorrent/torrents-info-{all,completed}.json` (introduced in `586cbb5`). Current snapshot only — history rewrite deferred to user.

### Phase 20 — C411 implementation

| Sub-phase | Description                                                      | SHA             |
| --------- | ---------------------------------------------------------------- | --------------- |
| 20.1      | `api/tracker/c411.py` — Torznab XML client (263 LOC)             | `8ce5856`       |
| 20.2      | `tests/unit/test_c411_client.py` (18 tests against real samples) | `8a31437`       |
| 20.3      | **Phase 20 gate**                                                | _(this commit)_ |

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
| `e6cc0ac` | docs: phase gate checklist in CLAUDE.md                            |
| `4e362d9` | chore: `make gate` target with secret scan + residual import audit |
| `6e84624` | chore: pre-push hook with gitleaks                                 |
| `328bd22` | perf: scope gitleaks to source dirs only                           |

## Known debt & deferred decisions

- **`TMDBClient.circuit` property** (`api/metadata/tmdb.py:87-90`) exposes private `self._transport._circuit` — pragmatic for legacy `circuit_breaker_threshold` config compat, used by `scraper/orchestrator.py:138,211` and `tests/scraper/test_scraper.py:1188-1273`. Tests assign directly to `circuit` (`# type: ignore[misc]`). Encapsulation refactor deferred until a 3rd metadata client lands (OMDB or Trakt) so the abstraction has more than 2 use cases.
- **Test layout**: DESIGN §12 R14 referenced `tests/api/`. Reality: `tests/unit/test_api_*.py` + `tests/integration/test_transport_policy.py`. Naming preserves discoverability — accepted deviation.
- **Asymmetric client construction**: `TMDBClient(transport, ...)` vs `TVDBClient(api_key, ...)`. The TVDB shape is forced by bootstrap login. A future factory layer (Phase 8 torrent factory groundwork) will need to handle both.
- **`tracker/_ranking.py` advance-shipped in Phase 2**: justified by Pydantic config validation; documented in DESIGN.md §10 (phase ordering rationale). Phase 16 still owns `_base.py` + `_registry.py` + `rank()` function.

## Next action

Phase 20 complete. **Run `/implement:phase` to start Phase 21** (Notify base + Telegram doc).

Pre-phase-8 checklist:

1. Verify `make check` exits 0 (currently green).
2. Confirm `python -c "import personalscraper"` works.
