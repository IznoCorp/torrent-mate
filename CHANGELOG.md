# Changelog

All notable changes to personalscraper are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **⚠️ FROZEN at 0.19.0 — read this first.**
>
> This file stopped being maintained after `0.19.0` (2026-06-01) while the code
> moved on to `0.49.x`. Rather than back-fill 30 minor versions from memory —
> **a false changelog is worse than an absent one** (constitution §méthode) —
> the authoritative history for `0.20.0` → the current version lives in:
>
> - the **git log** (`git log --oneline`), and
> - the **squash-merged pull requests** on GitHub, each carrying its
>   « déroulé de preuve daté » (constitution §10).
>
> Every PR bumps the version (§10-3, enforced by the CI `version-bump` job),
> so `git tag` / `personalscraper.__version__` + the PR that bumped it is the
> per-version record. This file **resumes at `1.0.0`** (the first production
> release), when the SemVer contract and a maintained changelog both begin.
>
> The entries below (`0.16.0`–`0.19.0`) are kept for their historical record.

## [0.19.0] — 2026-06-01

### Changed

- **Library / Indexer consolidation (lib-fold)**: the standalone top-level
  `library/` package was deleted and its responsibilities folded into the
  indexer, `insights/`, `maintenance/`, and `verify/`.
  - `library-index --mode full` is now **self-sufficient**: it runs the item
    stage (rich `media_item` rows) as pass 1, then the file walk as pass 2, in a
    single invocation. No prior `library-scan` step is required.
  - `library-scan` is now a **visible alias** of `library-index --mode full`
    (kept in `--help` for backwards compatibility; no longer exposes `--mode`).
  - **Single `media_item` creator**: both dispatch write paths now share the
    `_item_stage` primitives — `rebuild()` (auto-rebuild) delegates to
    `scan_and_stage_dir` (full rich rows: seasons + issues), and `add()`
    (per-dispatch) builds via `build_item_row` — eliminating the prior
    `canonical_provider=None` degradation on the dispatch path.
  - **Kind-deterministic canonical SSOT**: `canonical_provider` is derived from
    kind + provider IDs via `_canonical.derive_canonical_provider` (show → tvdb
    when a tvdb_id exists, movie → tmdb when a tmdb_id exists).
  - **Season-dir regex widened**: `naming_patterns.SEASON_DIR_RE` now matches the
    FR + EN + `Specials` union; new `season_number_from_dir()` helper added.
  - NFO helpers (`parse_title_year`, `extract_nfo_ids`, `extract_nfo_metadata`)
    moved to `personalscraper.nfo_utils`.
  - `write_json` / `read_json` moved to `personalscraper.io_utils`.
  - The redundant inline **ffprobe re-scan was dropped** from `library-analyze`
    and `library-recommend` — both now read enrich-populated `media_stream` rows
    from the indexer DB (`hdr_format` / `is_atmos` columns pre-existed and are
    populated by `library-index --mode enrich`). The `--from-index` flag is now
    accepted-but-ignored (the DB is always the sole source).
  - `library-doctor` / `library audit` now surface items without a valid NFO
    (the `nfo_missing` / `nfo_incomplete` `item_issue` rows) with a repair hint
    pointing at `library-rescrape --only nfo`.

### Added

- `personalscraper/insights/` — read-only analytics package over the indexer DB
  (`analytics.py`, `reporter.py`, `recommender.py`, `models.py`); backs
  `library-analyze`, `library-recommend`, and `library-report`.
- `personalscraper/maintenance/` — operator-upkeep package (`disk_cleaner.py`,
  `rescraper.py`); backs `library-clean` and `library-rescrape`.
- `personalscraper/verify/library_checks.py` — standalone re-home of the former
  `library/validator.py` (NFO / artwork / naming conformity), backing
  `library-validate`; registerable in the future Check plugin system.
- `personalscraper/naming_patterns.season_number_from_dir()` helper.

### Removed

- `personalscraper/library/` package (all modules) — responsibilities re-homed
  into `indexer/scanner/_modes/_item_stage*`, `insights/`, `maintenance/`, and
  `verify/library_checks.py`.

## [0.18.0] — 2026-05-29

### Added

- **Multi-filesystem support** (`FilesystemCapability` strategy table,
  `personalscraper/indexer/_fs_capability.py`): the pipeline now adapts rsync
  flags and indexer tier-1 drift behaviour per destination filesystem type.
  Supported keys: `ntfs_macfuse` (unchanged), `apfs`, `hfsplus`, `exfat`,
  `ext4` (data-only), and `unknown` (NTFS-safe restrictive fallback).
- `resolve_capability(path, fs_type_override)`
  (`personalscraper/indexer/_fs_capability.py`): a **single shared resolver**
  consumed by **both** the transfer layer (`dispatch.dispatcher.Dispatcher`)
  and the indexer scanner (`indexer/scanner/_scan_orchestrator.py`). This
  guarantees a disk's filesystem type is honoured uniformly end-to-end —
  transfer and scan can never diverge. An explicit `DiskConfig.fs_type`
  override beats `probe_mount` auto-detection.
- `FsProbe` (`personalscraper/indexer/_fs_probe.py`): single cached `mount`
  shell-out replacing three independent parsers (`db.py`,
  `scanner/_spotlight.py`, `scanner/__init__.py`). `canonical_fs_type` matches
  macFUSE/NTFS driver tokens by substring, fixing the `ufsd_NTFS` exact-token
  dead branch in `_spotlight.try_attach`.
- FS-aware tier-1 fingerprint helpers `normalize_tier1` and `round_mtime_ns`
  (`personalscraper/indexer/fingerprint.py`), consumed by the live scanner
  modes `scanner/_modes/incremental.py` and `scanner/_modes/quick.py`. On
  exFAT, ctime is dropped from the tier-1 tuple and mtime is floored to a
  2-second bucket; on HFS+, mtime is floored to a 1-second bucket. NTFS / APFS
  / ext4 keep the legacy `(size, mtime_ns, ctime_ns)` 3-tuple unchanged.
- FS-aware Merkle and dir-mtime **gating** layer: the Merkle root short-circuit,
  the `compute_merkle_delta` bulk-change freeze guard, and the dir-mtime subtree
  skip now bucket mtime per the disk capability
  (`_walker.py::_build_disk_fingerprints` / `_sample_fresh_fingerprints` and the
  dir-mtime compares in incremental / quick). On a coarse filesystem (HFS+ 1 s,
  exFAT 2 s) sub-bucket mtime jitter can no longer defeat the Merkle
  short-circuit nor spuriously trip the bulk-change freeze on a healthy disk;
  NTFS / APFS / ext4 (granularity 1) keep a byte-identical Merkle root.
- `DiskConfig.fs_type` optional override: escape hatch for unrecognised
  macFUSE driver tokens; falls back to the NTFS-safe `unknown` capability for
  any unrecognised value. The scanner override map is keyed on the **stable**
  `DiskConfig.id` (== the immutable `DiskRow.label`), not on the mutable
  `mount_path`, so a runtime remount can no longer drop the operator override.

### Changed (per-FS dispatch)

- Per-FS illegal-filename relaxation now applies **end-to-end**: the
  illegal-name gate in `dispatch/_movie.py` / `_tv.py` runs **after** the
  destination disk is resolved and uses that disk's
  `capability.illegal_name_regex`. A `:`-titled item is no longer skipped when
  the destination is a POSIX filesystem (APFS / HFS+ / exFAT / ext4, where the
  regex is `None`); on an NTFS / `unknown` destination it is still skipped.
- `multifs` pytest marker: capability / probe / argv / tier-1 / scan /
  diskconfig tests tagged; no real disks required (faked mount/stat fixtures).

### Fixed

- `_spotlight.try_attach` dead branch: `ufsd_NTFS` mounts were not recognised
  as macFUSE volumes due to exact-token vs substring asymmetry. Now fixed via
  substring matching in `canonical_fs_type`.

### Changed

- Probe timeout for the `db.py` pre-open check: 5 s → 10 s (single cached
  shell-out shared with the scanner modules). Intentional; documented in
  `docs/reference/storage.md`.
- `rsync()` and `rsync_merge()` in `dispatch/_transfer.py` now read flags from
  `FilesystemCapability.rsync_flags` (defaulting to `NTFS_MACFUSE`) instead of
  hardcoded literals. The NTFS argv is pinned byte-for-byte by a golden test
  (`tests/dispatch/test_transfer_argv.py`).

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
