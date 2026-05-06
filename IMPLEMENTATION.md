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
| 13  | OMDB implementation                | impl  | [phase-13-omdb-impl.md](docs/features/api-unify/plan/phase-13-omdb-impl.md)                               | [ ]    |
| 14  | Trakt API doc                      | doc   | [phase-14-trakt-doc.md](docs/features/api-unify/plan/phase-14-trakt-doc.md)                               | [ ]    |
| 15  | Trakt implementation               | impl  | [phase-15-trakt-impl.md](docs/features/api-unify/plan/phase-15-trakt-impl.md)                             | [ ]    |
| 16  | Tracker base + ranking engine      | infra | [phase-16-tracker-base-ranking.md](docs/features/api-unify/plan/phase-16-tracker-base-ranking.md)         | [ ]    |
| 17  | LaCale API doc                     | doc   | [phase-17-lacale-doc.md](docs/features/api-unify/plan/phase-17-lacale-doc.md)                             | [ ]    |
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
| —         | **Phase 9 gate**                                  | _(next)_  |

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

Phase 12 complete. **Run `/implement:phase` to start Phase 13** (OMDB implementation).

Pre-phase-8 checklist:

1. Verify `make check` exits 0 (currently green).
2. Confirm `python -c "import personalscraper"` works.
