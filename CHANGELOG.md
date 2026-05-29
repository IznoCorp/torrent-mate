# Changelog

All notable changes to personalscraper are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.17.0] — 2026-05-29

### Added

- `core/_contracts.py`: canonical home for `CircuitOpenError`, `ApiError`, `MediaType`
  (re-exported from `api/_contracts.py` for backward compatibility).
- `conf/models/_ranking.py`: canonical home for `ThresholdEntry`, `RankingCriterion`,
  `RankingBonuses`, `RankingConfig` (re-exported from `api/tracker/_ranking.py`).
- `core/media_types.py`: canonical home for `VIDEO_EXTENSIONS`, `FileType`,
  `is_trailer_filename` (promoted from `sorter/file_type.py`).
- `schema_version: int = 1` field on the `Event` base class — threads through
  `event_to_envelope` / `event_from_envelope`.
- `tests/architecture/test_layering.py`: AST-based guard enforcing that `core/`
  and `conf/` do not import upward into `api/` or upper layers.
- `tests/architecture/test_event_schema_version.py`: invariant tests for `schema_version`.
- `tests/architecture/test_registry_events_contract.py`: invariant tests asserting all
  5 registry events subclass `Event` and are envelope-round-trippable.

### Changed

- 5 provider-registry events (`ProviderFallbackTriggered`, `ProviderExhaustedEvent`,
  `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated`)
  now subclass `Event` (`frozen=True, kw_only=True`); auto-registered in
  `_EVENT_CLASS_REGISTRY`; production event catalog grows from 18 to 23.
- `sorter/file_type.py` no longer exports shared constants — `detect_file_type` and
  `detect_dir_type` remain; 23 non-`sorter` import lines rewritten to `core.media_types`.
- `core/circuit.py` and `conf/classifier.py` import from `core._contracts` instead of
  `api._contracts`; `conf/models/api_config.py` imports from `conf/models/_ranking`.

### Fixed

- Removed `# type: ignore[arg-type]` suppression on registry event `emit()` call
  (`api/metadata/registry/__init__.py`) — no longer needed now that events subclass `Event`.

### Architecture

- Closes the P1 roadmap prerequisite for the Web Management UI, Watcher Service,
  and Web UI Registry Consumer items (see `ROADMAP.md` P2 entries).

## [0.16.0] — 2026-05-27

### Added

- **Provider Registry** (`personalscraper/api/metadata/registry/`): `ProviderRegistry`
  class with `chain`, `fan_out`, and `locked` operations. Config-driven provider
  ordering via `config/providers.json5`. Circuit-breaker aware. Boot-time validation
  with aggregated `RegistryConfigError`. EventBus events for all dispatch outcomes.
- `personalscraper info providers` CLI command: prints per-provider circuit state snapshot.
- `conf/models/providers.py`: `ProvidersConfig` Pydantic model.
- `config.example/providers.json5`: provider ordering template.
- `AppContext.provider_registry`: feature delivered at boundary, threaded through pipeline and CLI commands.

### Changed

- `scraper/orchestrator.py`, `movie_service.py`, `tv_service.py`: hardcoded
  `self._tmdb`/`self._tvdb` replaced by `registry.chain(...)`. No façade.
- `trailers/orchestrator.py`, `library/rescraper.py`, `commands/library/scan.py`:
  migrated to registry injection.
- All direct `TMDBClient`/`TVDBClient` consumer files now route through the registry
  (verified via ACC-02: `rg TMDBClient personalscraper/ | grep -v api/metadata/` returns no constructor calls).

### Internal

- Characterization tests (`tests/integration/scraper/test_legacy_fallback_snapshot.py`)
  lock in pre-refactor behavior as the equivalence anchor through Phase 1+2 migration.
- 15 HTTP-level integration tests (`tests/integration/api/metadata/registry/test_registry_http.py`)
  cover chain fallback, HALF_OPEN probe semantics, locked + IDCrossRef escape, fan_out partial.
- 40 unit tests (`tests/unit/api/metadata/registry/`) cover all 11 capability Protocols + boot validation.
- Event-bus required-signature contract preserved (no `EventBus | None` in registry public API).

### Phase 7 — Chain semantics in production

- `scraper/movie_service.py` and `scraper/tv_service.py` migrated from
  transitional `registry.get("tmdb")` direct access to
  `registry.chain(MovieDetailsProvider)` and `registry.chain(TvDetailsProvider)`
  per DESIGN §6.2.
- `ProviderFallbackTriggered` event emitted on every per-provider classified
  failure (circuit_open / network); `ProviderExhaustedEvent` emitted when every
  chain provider failed (commits `fba4f0b4`, `f3ce3c8c`).
- `fan_out()` return widened from raw list to `FanOutResult[C]` carrying
  `values` + `attempted` (commit `8900f7e1`) — synchronous callers gain
  provenance without subscribing to the bus.

### Phase 8 — Type design hardening

- `Mode` enum promoted to `StrEnum` (Python 3.12+; commit `9377a9e6`).
- Exhaustive `@overload` partition on `chain` / `fan_out` / `locked`: every
  capability has its own overload signature, narrowing the union return at
  type-check time.
- `LockedProvider[C]` preserves the capability type parameter end-to-end
  (Generic[C] retained through `_make_locked`).
- `RegistryProviderName` (semantic NewType over `str`) documented and used
  uniformly at every registry boundary as the canonical "provider name" type.

### Phase 9 — Test infrastructure cleanup

- `typed_settings_stub` fixture introduced for CLI tests (commit `153f7986`)
  — 79 call sites pivoted (commits `120281e8`, `6321c121`, `a937b5ef`,
  `a8535a00`). Replaces ad-hoc settings mocks with a single typed factory that
  composes correctly with the real `ProviderRegistry` boot.

### Phase 10 — `existing_validator` module-size extraction

- `personalscraper/scraper/existing_validator.py` split into three files
  (commit `9e14296a`): `existing_validator.py` orchestration, plus
  `existing_validator_drift.py` and `existing_validator_repair.py` for the
  two main branches. LOC dropped from 1125 → 702 (under the 800-LOC soft
  ceiling, well under the 1000-LOC hard ceiling).

### Phase 11 — Indexer backfill migrated to registry

- `personalscraper/indexer/backfill_ids.py` now receives
  `registry: ProviderRegistry` (commit `c463a330`) — no more typed-client
  extraction via `try/except UnknownProviderError`.
- Ratings aggregation routed through `registry.fan_out(RatingProvider)`;
  canonical details lookup routed through `registry.chain(MovieDetailsProvider)`
  / `registry.chain(TvDetailsProvider)` filtered to the canonical provider
  name.
- CLI `library backfill-ids` passes the registry instead of constructing typed
  clients (commit `c55ccfed`).
- Tests pivoted to registry-aware mocks (commits `1f94e50e`, `34c2ca84`).

### Phase 12 — Roadmap entries for deferrals

- ROADMAP P2/P3 entries added (commit `9ac85eee`) for the three deferrals
  noted during PR review: Web UI Registry Consumer, Active Health Scoring,
  and Hot-Swap Provider Configuration. No code change.

### Phase 13 — Pre-existing flaky-test audit (NO_OP)

- Cited flaky test was already absent from the suite; documented as NO_OP
  in the phase plan (commit `988ccb22`).

### Phase 14 — TVDB lazy bootstrap

- `TVDBClient.__init__` no longer performs the login HTTP call (commit
  `734046fc`). Authentication is deferred to the first capability call,
  letting `ProviderRegistry` boot succeed offline / in tests without an
  outbound TCP connection.

### Phase 15 — Autouse CLI fixture removed

- `_patch_provider_registry_for_cli_tests` autouse fixture removed (commit
  `ed71a98e`). CLI tests now boot the real `ProviderRegistry` on top of
  `typed_settings_stub` (Phase 9). Eliminates the last hidden monkey-patch
  divergence between test and production registry construction.

### Phase 16 — Chain exhaustion contract restored

- `ProviderExhausted` carries `last_exception` (commit `d3baa04b`). Chain
  exhaustion in `movie_service` and `tv_service` now raises
  `ProviderExhausted` (commits `ab32c3f2`, `903c7f51`) per DESIGN §6.2
  contract; callers catch and surface the exception's `last_exception` in
  `result.error` — ACC-13 (error-message preservation) anchor preserved.

### Phase 17 — Protocol `provider_id` widened to `int | str`

- `MovieDetailsProvider.get_movie` and `TvDetailsProvider.get_tv` widened
  to `provider_id: int | str` (commit `6c7b4cc8`). ACC-02 exemption count
  tightened from 6 to 4 remaining episode-specific cast sites (commit
  `a3db3132`).

### Phase 18 — Module-size hard-ceiling fixes

- `scraper/tv_service.py` split: chain helpers extracted to
  `tv_service_episodes.py` (commit `1cb8915c`).
- `indexer/backfill_ids.py` split: canonical-init helpers extracted to
  `backfill_ids_canonical.py` (commit `26b81908`).
- All registry-related modules now under the 800-LOC soft warning.
