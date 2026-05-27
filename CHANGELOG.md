# Changelog

All notable changes to personalscraper are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
