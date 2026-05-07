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
| 18  | LaCale implementation              | impl  | [phase-18-lacale-impl.md](docs/features/api-unify/plan/phase-18-lacale-impl.md)                           | [ ]    |
| 19  | C411 API doc                       | doc   | [phase-19-c411-doc.md](docs/features/api-unify/plan/phase-19-c411-doc.md)                                 | [ ]    |
| 20  | C411 implementation                | impl  | [phase-20-c411-impl.md](docs/features/api-unify/plan/phase-20-c411-impl.md)                               | [ ]    |
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

**Note**: `make lint` was first wired with ruff only; mypy was added in `e91265e` (post-phase-7 corrective). All future phase gates MUST run the full `make check` (lint+test+module-size+typed-api) per CLAUDE.md "Phase Gate Checklist".

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
| —     | Archive arch-cleanup, bump 0.11.0 | `b41a231`                                             | Branch creation |
| —     | Initial implementation plan       | `0744a6b`                                             | Plan generated  |
| —     | Design refinements                | `7e2a6c0`, `252388a`, `25ca9db`, `394cadb`, `7ea2875` | DESIGN v1 → v5  |

### Phase 1 — Foundation + transport

| Sub-phase | Description                                  | SHA       |
| --------- | -------------------------------------------- | --------- |
| 1.1       | `api/_contracts.py` (AuthMode, ApiError)     | `9c753d7` |
| 1.2       | `api/_units.py` (ByteSize) + tests           | `ffaa911` |
| 1.3       | `api/transport/_policy.py`                   | `da47d2d` |
| 1.4       | `api/transport/_auth.py` + tests             | `3460dfc` |
| 1.5       | `api/transport/_rate.py` (RateLimiter)       | `1c99db3` |
| 1.6       | `git mv` circuit breaker → `core/circuit.py` | `706407d` |
| 1.7       | Add `xmltodict` dependency                   | `422c8dd` |
| 1.8       | `api/transport/_http.py` (HttpTransport)     | `dad27c1` |
| 1.9       | `scripts/check-typed-api.py` guardrail       | `c4009e9` |
| 1.10      | TransportPolicy reference test               | `58779f3` |
| 1.11      | **Phase 1 gate**                             | `744568f` |

### Phase 2 — Config infra + activation

| Sub-phase | Description                                                                                                              | SHA       |
| --------- | ------------------------------------------------------------------------------------------------------------------------ | --------- |
| 2.1       | Pydantic api config models + `tracker/_ranking.py` (advance-shipped — needed by `config/ranking.json5` Pydantic loading) | `0119e16` |
| 2.2       | `api/_activation.py` ProviderActivation                                                                                  | `fb30c58` |
| 2.3       | 5 `config.example/*.json5` templates                                                                                     | `2fd6cd5` |
| 2.4       | Wire api config into `Config` + init-config                                                                              | `9066b08` |
| 2.5       | **Phase 2 gate**                                                                                                         | `a102f74` |

### Phase 3 — Metadata family base

| Sub-phase | Description                                         | SHA       |
| --------- | --------------------------------------------------- | --------- |
| 3.1       | `api/metadata/_base.py` (Protocol + 8 typed models) | `c0d3d66` |
| 3.2       | `tests/unit/test_api_metadata_base.py`              | `0a366bb` |
| 3.3       | **Phase 3 gate**                                    | `e051d2f` |

### Phase 4 — TMDB API doc

| Sub-phase | Description                                                                   | SHA       |
| --------- | ----------------------------------------------------------------------------- | --------- |
| 4.1       | **Phase 4 gate** (doc): `docs/reference/tmdb-api.md`                          | `e92b76b` |
| 4.2       | Mark phase 4 complete                                                         | `8314a32` |
| 4.3       | TMDB API golden test samples (13 endpoints — deferred at gate, captured next) | `e57413b` |
| 4.4       | Phase 5 plan iteration with phase 4 learnings                                 | `c0e40d5` |

> **Audit note**: gate `e92b76b` predated the golden samples (`e57413b`) — minor ordering drift, samples were explicitly deferred in the gate body.

### Phase 5 — TMDB migration

| Sub-phase | Description                                                       | SHA       |
| --------- | ----------------------------------------------------------------- | --------- |
| 5.1       | TMDB response parsers + golden tests                              | `0d4e9e2` |
| 5.2       | Migrate TMDB client → `api/metadata/tmdb.py`                      | `789abae` |
| 5.3       | Rewire 9 prod + 3 test consumers; delete `scraper/tmdb_client.py` | `96b95c6` |
| 5.4       | mypy: `dict[str, Any]` → `dict[str, object]`                      | `b59e05b` |
| 5.5       | **Phase 5 gate**                                                  | `ffda816` |

> **Audit note**: a silent regression slipped through — `_fetch_videos_strict` was dropped in 5.2 and only restored at `e91265e` (post-phase-7). Detected because mypy was not yet wired into `make lint`.

### Phase 6 — TVDB API doc

| Sub-phase | Description                                                                         | SHA       |
| --------- | ----------------------------------------------------------------------------------- | --------- |
| 6.1       | **Phase 6 gate** (doc): `docs/reference/tvdb-api.md` + 11 samples + user checkpoint | `3b685b5` |
| 6.2       | Mark phase 6 complete                                                               | `fc40da5` |

### Phase 7 — TVDB migration

| Sub-phase | Description                                                                                                               | SHA       |
| --------- | ------------------------------------------------------------------------------------------------------------------------- | --------- |
| 7.1       | TVDB response parsers + golden tests                                                                                      | `436aea6` |
| 7.2       | Migrate TVDB client → `api/metadata/tvdb.py`                                                                              | `1ba7076` |
| 7.3       | Move tenacity helpers → `core/http_helpers.py`; delete old TVDB client + `scraper/providers.py` + `scraper/http_retry.py` | `f251fe7` |
| 7.4       | **Phase 7 gate** (premature — see corrective sub-phases below)                                                            | `a93b286` |
| 7.5       | Corrective: restore `_fetch_videos_strict`, **wire mypy into `make lint`**, fix typed model consumers (20+ mypy errors)   | `e91265e` |
| 7.6       | Corrective: fix test infrastructure for typed API changes                                                                 | `2776b2f` |
| 7.7       | Corrective: fix line-too-long ruff violations                                                                             | `5ece33a` |
| 7.8       | Corrective: fix all remaining test failures, full suite green                                                             | `39e2bf8` |

> **Audit note**: gate `a93b286` was structurally invalid — `make lint` was missing mypy (since phase 1) so 20+ type errors went unnoticed; tests were broken. The four corrective sub-phases (7.5–7.8) closed the gap. Phase gate checklist now codified in `CLAUDE.md` (commit `8398570`) to prevent repeats.

### Phase 8 — Torrent base + qBittorrent doc

| Sub-phase | Description                                                   | SHA       |
| --------- | ------------------------------------------------------------- | --------- |
| 8.1       | `api/torrent/_base.py` — TorrentItem + TorrentClient Protocol | `1a0ef30` |
| 8.2       | `api/torrent/_factory.py` — active client resolver + tests    | `ee960e6` |
| 8.3–8.6   | Audit qBit usage + API doc + particularities                  | `851e48c` |
| 8.4–8.5   | Real test calls (qBit 5.0.4) + doc rewrite from official spec | `31b832f` |
| —         | Phase 9 plan adaptation from real API findings                | `957076a` |
| —         | **Phase 8 gate**                                              | `c53eae3` |

### Phase 9 — qBittorrent migration

| Sub-phase | Description                                       | SHA       |
| --------- | ------------------------------------------------- | --------- |
| 9.1       | `api/torrent/qbittorrent.py` + tests              | `d3b8085` |
| 9.2       | Wire factory (verification — already wired)       | `51bc81c` |
| 9.3       | Delete old module + update consumers + test paths | `ebcc84c` |
| 9.4       | **Phase 9 gate**                                  | `e9d2d78` |

### Phase 10 — Transmission API doc

| Sub-phase | Description                                                      | SHA       |
| --------- | ---------------------------------------------------------------- | --------- |
| 10.1      | `docs/reference/transmission-api.md` from official RPC spec      | `f0f0edc` |
| 10.2      | **Phase 10 gate** — option A confirmed (HttpTransport pre-check) | `78ce2af` |

### Phase 11 — Transmission implementation

| Sub-phase | Description                                                                                                                            | SHA       |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 11.1      | `chore(api-unify): add transmission-rpc dependency`                                                                                    | `e263fcf` |
| 11.2      | `api/torrent/transmission.py` + factory wiring (pre-check moved from `__init__` to `build_client()` factory — cleaner than plan §11.2) | `895ef24` |
| 11.3      | Update factory test for transmission resolution                                                                                        | `4eda132` |
| 11.4      | **Phase 11 gate**                                                                                                                      | `6efd66b` |

> **Audit note**: dedicated `tests/unit/test_transmission_client.py` was missing (Plan §11.4 required it). Backfilled in the post-phase-15 corrective sub-phase (see "Cross-cutting infrastructure" below).

### Phase 12 — OMDB API doc

| Sub-phase | Description                                                                               | SHA       |
| --------- | ----------------------------------------------------------------------------------------- | --------- |
| 12.1      | `chore: add network timeout safety guardrails` (curl `--connect-timeout` block_curl hook) | `d118952` |
| 12.2      | **Phase 12 gate** — `docs/reference/omdb-api.md` + samples + user checkpoint captured     | `2481d9a` |

> **Audit note**: `d118952` is a cross-cutting safety hook landing during Phase 12 (omdbapi.com hung 11+ hours during doc study — see hook docstring). Co-shipped with the gate commit.

### Phase 13 — OMDB implementation

| Sub-phase | Description                                             | SHA       |
| --------- | ------------------------------------------------------- | --------- |
| 13.1      | `api/metadata/omdb.py` (354 LOC, well under 800 budget) | `967e4c4` |
| 13.2      | `tests/unit/test_omdb_client.py` (26 tests)             | `a36c440` |
| 13.3      | **Phase 13 gate**                                       | `c08ffa3` |

### Phase 14 — Trakt API doc

| Sub-phase | Description                                                                     | SHA       |
| --------- | ------------------------------------------------------------------------------- | --------- |
| 14.1      | **Phase 14 gate** — `docs/reference/trakt-api.md` + 4 samples + user checkpoint | `7f554e4` |

### Phase 15 — Trakt implementation

| Sub-phase | Description                                  | SHA       |
| --------- | -------------------------------------------- | --------- |
| 15.1      | `api/metadata/trakt.py` (367 LOC) + 11 tests | `18a0cab` |
| 15.2      | Ruff formatting fixup on torrent modules     | `734f806` |
| 15.3      | **Phase 15 gate**                            | `15cb47e` |

### Phase 16 — Tracker base + ranking engine

| Sub-phase | Description                                                     | SHA       |
| --------- | --------------------------------------------------------------- | --------- |
| 16.1      | `api/tracker/_base.py` — TrackerResult + TrackerClient Protocol | `2f1c9cc` |
| 16.2      | `api/tracker/_ranking.py` — `rank()` engine                     | `b2862ba` |
| 16.3      | `api/tracker/_registry.py` — TrackerRegistry                    | `4f79402` |
| 16.4      | Ranking engine + ThresholdEntry tests (15 tests)                | `b7e982f` |
| 16.5      | **Phase 16 gate**                                               | `54f29a3` |

### Phase 17 — LaCale API doc

| Sub-phase | Description                                                                       | SHA       |
| --------- | --------------------------------------------------------------------------------- | --------- |
| 17.1–17.5 | `docs/reference/lacale-api.md` from TorrentMaker source (search + meta endpoints) | `403d145` |
| 17.6      | User checkpoint baked into doc as "Open decisions" (defaults stand for Phase 18)  | `403d145` |
| 17.7      | **Phase 17 gate** (single-commit phase)                                           | `403d145` |

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
| `8398570` | docs: phase gate checklist in CLAUDE.md                            |
| `711c04f` | chore: `make gate` target with secret scan + residual import audit |
| `4fe69b9` | chore: pre-push hook with gitleaks                                 |
| `2da7b55` | perf: scope gitleaks to source dirs only                           |

## Known debt & deferred decisions

- **`TMDBClient.circuit` property** (`api/metadata/tmdb.py:87-90`) exposes private `self._transport._circuit` — pragmatic for legacy `circuit_breaker_threshold` config compat, used by `scraper/orchestrator.py:138,211` and `tests/scraper/test_scraper.py:1188-1273`. Tests assign directly to `circuit` (`# type: ignore[misc]`). Encapsulation refactor deferred until a 3rd metadata client lands (OMDB or Trakt) so the abstraction has more than 2 use cases.
- **Test layout**: DESIGN §12 R14 referenced `tests/api/`. Reality: `tests/unit/test_api_*.py` + `tests/integration/test_transport_policy.py`. Naming preserves discoverability — accepted deviation.
- **Asymmetric client construction**: `TMDBClient(transport, ...)` vs `TVDBClient(api_key, ...)`. The TVDB shape is forced by bootstrap login. A future factory layer (Phase 8 torrent factory groundwork) will need to handle both.
- **`tracker/_ranking.py` advance-shipped in Phase 2**: justified by Pydantic config validation; documented in DESIGN.md §10 (phase ordering rationale). Phase 16 still owns `_base.py` + `_registry.py` + `rank()` function.

## Next action

Phase 17 complete. **Run `/implement:phase` to start Phase 18** (LaCale implementation).

Pre-phase-8 checklist:

1. Verify `make check` exits 0 (currently green).
2. Confirm `python -c "import personalscraper"` works.
