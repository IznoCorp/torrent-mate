# Module Size Decomposition — Design

**Status**: Prepared (not yet implemented)
**Codename**: `module-split`
**Version bump**: 0.9.0 → 0.10.0 (minor — decomposes 4 modules, removes dead config fields, hardens the size guardrail)
**Design date**: 2026-05-03
**Trigger**: Open issues from arch-cleanup — `conf/models.py` at 1187 LOC exceeds the 1000-line hard ceiling that 0.10.0 will enforce, and 3 other modules are within range (`commands/library.py` 936, `dispatch/dispatcher.py` 899, `indexer/outbox.py` 898).

## 1. Goals & Non-goals

### 1.1 Goals

- **`conf/models.py`**: decompose into a `conf/models/` package with per-domain files, each ≤ 400 LOC. Clean up all dead Reserved fields (genuinely unconsumed config schema) and retag fields whose Reserved marker is wrong.
- **`commands/library.py`**: decompose into `commands/library/` package grouped by functional domain, each ≤ 220 LOC.
- **`dispatch/dispatcher.py`**: extract transfer helpers, movie dispatch, and TV dispatch into dedicated modules. Keep `Dispatcher` as a thin orchestrator (~200 LOC).
- **`indexer/outbox.py`**: decompose into `indexer/outbox/` package by pipeline phase (types, disk ops, apply ops, drain, publish).
- **`scripts/check-module-size.py`**: promote from advisory (exit 0 always) to hard block (exit 1 on REPORT ≥ 1000 LOC).
- **Zero backward compatibility**: no re-exports from old locations, no compat shims. All consumers update their imports.

### 1.2 Non-goals

- No logic changes — pure decomposition + dead field removal. Every split is behaviour-preserving.
- No new features, no new config fields, no new pipeline steps.
- No Generic `StepReport[TDetails]` migration — out of scope.
- No cross-step consolidation.

### 1.3 Success criteria

| Metric                 | Target                                                   |
| ---------------------- | -------------------------------------------------------- |
| `check-module-size.py` | exit 0, zero REPORT, zero WARN                           |
| Every new file         | ≤ 400 LOC (most ≤ 250)                                   |
| `make test`            | green, coverage delta ≥ 0                                |
| `make check`           | green (includes new hard-block size check)               |
| Reserved field cleanup | 20+ dead fields removed, zero config loading regressions |

---

## 2. File 1 — `conf/models.py` → `conf/models/` package

### 2.1 Target structure

```
conf/models/
├── __init__.py       # Package docstring only (no re-exports)
├── _base.py          # _StrictModel (~13 LOC)
├── categories.py     # CategoryConfig, CategoryRule, GenreMapping, AnimeRule (~120 LOC)
├── disks.py          # DiskConfig (~25 LOC after spotlight_enabled removal)
├── staging.py        # StagingDirConfig (~55 LOC)
├── paths.py          # PathConfig (~35 LOC)
├── preferences.py    # VideoPrefs, AudioPrefs, SubtitlePrefs, RuleCriteria,
                      # EncodingRule, LibraryPrefs (~150 LOC after cleanup)
├── fuzzy.py          # FuzzyMatchConfig (~40 LOC)
├── scraper.py        # ScraperConfig, IngestConfig (~35 LOC)
├── trailers.py       # TrailersCircuitBreakerConfig, TrailersCircuitBreakersConfig,
                      # TrailersFiltersConfig, TrailersYoutubeApiConfig,
                      # TrailersPlacementConfig, TrailersSeasonsConfig,
                      # TrailersStepConfig, TrailersPipelineConfig,
                      # TrailersLibraryCheckConfig, TrailersConfig (~330 LOC after cleanup)
├── indexer.py        # IndexerScanConfig, IndexerDriftConfig, IndexerSpotlightConfig,
                      # IndexerLogConfig, IndexerConfig (~120 LOC after cleanup)
└── config.py         # Config (top-level) + validators + helper methods (~200 LOC)
```

### 2.2 Reserved fields audit

Each field currently tagged `**Reserved.**` is verified with grep against all production code (`personalscraper/`).

#### 2.2.1 Fields to DELETE (genuinely dead — no runtime consumer)

| #   | Field                                     | Class                      | Verification                                                                                                                                                                        |
| --- | ----------------------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `spotlight_enabled`                       | `DiskConfig`               | Parameter passed to `try_attach()` comes from global `cfg.indexer.spotlight.use_when_available`, never from the per-disk field                                                      |
| 2   | `min_channels`                            | `AudioPrefs`               | 2 hits (model def + config example only)                                                                                                                                            |
| 3   | `preferred_codec`                         | `AudioPrefs`               | `VideoPrefs.preferred_codec` is consumed by recommender; `AudioPrefs.preferred_codec` is a different field, never read                                                              |
| 4   | `warn_if_missing`                         | `SubtitlePrefs`            | 2 hits (model def only)                                                                                                                                                             |
| 5   | `cache_ttl_days`                          | `TrailersYoutubeApiConfig` | `trailers_cache.py` hardcodes `_YOUTUBE_TTL_SECONDS = 7 * 24 * 3600`                                                                                                                |
| 6   | `default_search`                          | `TrailersYtdlpConfig`      | `youtube_search.py:287` hardcodes `"default_search": "ytsearch1"`                                                                                                                   |
| 7   | `bot_detected_max_consecutive_attempts`   | `TrailersConfig`           | 3 hits (model def + config example only)                                                                                                                                            |
| 8   | `language_fallback`                       | `TrailersSeasonsConfig`    | 6 hits (all model def, config example, or unrelated `language_fallback` in other classes)                                                                                           |
| 9   | `search_query_format`                     | `TrailersSeasonsConfig`    | `orchestrator.py:655` reads `config.trailers.search_query_format` (the show-level field, not this season-specific override)                                                         |
| 10  | `nightly_mode`                            | `IndexerScanConfig`        | 7 hits (model def + config example only; launchd plists hardcode the mode)                                                                                                          |
| 11  | `racy_window_seconds`                     | `IndexerScanConfig`        | 3 hits (model def only; `drift.reconcile_file` is test-only)                                                                                                                        |
| 12  | `sequential_read_hint`                    | `IndexerScanConfig`        | 3 hits (model def only; mmap hint is unconditional)                                                                                                                                 |
| 13  | `IndexerFingerprintConfig` (entire class) | —                          | `oshash` / `xxh3_partial` / `compute_xxh3_on_racy` — none of the 3 fields are read by any production code path; the runtime always computes both oshash and xxh3 unconditionally    |
| 14  | `IndexerMediainfoConfig` (entire class)   | —                          | All 5 fields (`library_path`, `extract_streams`, `min_size_mb`, `parse_speed`, `defer_to_enrich`) — `MediaInfoWrapper` is always instantiated with hardcoded values; no config read |
| 15  | `merkle_per_disk`                         | `IndexerDriftConfig`       | 4 hits (model def only)                                                                                                                                                             |
| 16  | `verify_disks_each_scan`                  | `IndexerDriftConfig`       | 3 hits (model def only)                                                                                                                                                             |
| 17  | `sentinel_filename`                       | `IndexerDriftConfig`       | 4 hits (model def only; runtime uses module constant `SENTINEL_FILENAME`)                                                                                                           |
| 18  | `probe_at_startup`                        | `IndexerSpotlightConfig`   | 4 hits (model def only; probe always runs)                                                                                                                                          |
| 19  | `IndexerRepairConfig` (entire class)      | —                          | Both fields (`queue_drain_on_scan_finish`, `max_repair_seconds_per_drain`) never read                                                                                               |
| 20  | `scan_event_retention_days`               | `IndexerLogConfig`         | 3 hits (model def only; no scan_event prune worker exists)                                                                                                                          |

**Total: ~20 fields removed across 7 classes, 3 entire classes deleted.**

#### 2.2.2 Fields to KEEP — remove Reserved tag (has a real consumer)

| #   | Field                 | Class                     | Consumer                                                                                                                                                                                                                                                                          |
| --- | --------------------- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `preferred_languages` | `SubtitlePrefs`           | `_required_subset_of_preferred` validator — real config guard: enforced that `required` ⊆ `preferred`. Remove `description="Reserved..."` and document as `"Ordered language preference list. Must be a superset of required_languages."`                                         |
| 2   | `movie_pattern`       | `TrailersPlacementConfig` | `_validate_placeholders` field validator — ensures pattern contains `{folder}`, `{name}`, `{ext}` and passes `str.format` smoke test. Real guard-rail. Remove `"Reserved"` from description, note `"Placeholder template for movie trailer filenames. Validated at config load."` |
| 3   | `tvshow_pattern`      | `TrailersPlacementConfig` | Same validator as `movie_pattern`. Remove `"Reserved"` tag, same treatment.                                                                                                                                                                                                       |

#### 2.2.3 Fields already correctly tagged — KEEP (genuinely consumed)

| #   | Field                                          | Class                    | Consumer                                                                                                                      |
| --- | ---------------------------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| 1   | `merkle_delta_freeze_threshold`                | `IndexerDriftConfig`     | Consumed by `indexer/cli.py` and `indexer/scanner/_modes.py`. Docstring already says "This field IS consumed". No change.     |
| 2   | `deleted_item_retention_days`                  | `IndexerLogConfig`       | Consumed by `library-repair`. Docstring already says "This field IS consumed". No change.                                     |
| 3   | `cache_ttl_days` on `TrailersYoutubeApiConfig` | —                        | DELETED (see 2.2.1 #5 above). Actually consumed by nothing.                                                                   |
| 4   | `use_when_available`                           | `IndexerSpotlightConfig` | **Consumed** by `indexer/cli.py:503` — docstring already accurate: `"Delegate change detection to Spotlight when available."` |
| 5   | `drop_indexes_during_full_scan`                | `IndexerScanConfig`      | **Consumed.** Docstring already accurate.                                                                                     |
| 6   | `paranoia_window_seconds`                      | `IndexerScanConfig`      | **Consumed** by quick-mode paranoia branch. Docstring says "Consumed".                                                        |

### 2.3 Import migration

Every consumer changes from:

```python
from personalscraper.conf.models import Config, DiskConfig, FuzzyMatchConfig, ...
```

to direct imports from the new module:

```python
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.fuzzy import FuzzyMatchConfig
```

Impact: ~90 import sites across ~45 production files and ~30 test files.

### 2.4 Config example update

`config.example/` files must be updated to remove deleted Reserved fields so `init-config` doesn't generate them. If a user has an existing `config.json5` with removed fields, `extra='forbid'` will cause a loud failure with the exact field name — they remove it and reload.

---

## 3. File 2 — `commands/library.py` → `commands/library/` package

### 3.1 Target structure

Suit le même pattern que `indexer/commands/` (scan.py, query.py, repair.py, diagnose.py) :

```
commands/library/
├── __init__.py       # Re-exports all 16 functions for convenience
├── scan.py           # library_scan, library_index (~137 LOC)
├── query.py          # library_status, library_search, library_show (~74 LOC)
├── maintenance.py    # library_verify, library_repair, library_clean, library_validate (~260 LOC)
├── audit.py          # library_ghost_audit, library_relink, library_reconcile (~220 LOC)
└── analyze.py        # library_analyze, library_recommend, library_report, library_rescrape (~377 LOC)
```

Tous les fichiers entre 74 et 377 LOC, bien sous le seuil de 700.

### 3.2 Regroupement fonctionnel

| Groupe      | Fichier          | Fonctions                                                            | LOC |
| ----------- | ---------------- | -------------------------------------------------------------------- | --- |
| Scan/Index  | `scan.py`        | library_scan, library_index                                          | 137 |
| Query       | `query.py`       | library_status, library_search, library_show                         | 74  |
| Maintenance | `maintenance.py` | library_verify, library_repair, library_clean, library_validate      | 260 |
| Audit       | `audit.py`       | library_ghost_audit, library_relink, library_reconcile               | 220 |
| Analyse     | `analyze.py`     | library_analyze, library_recommend, library_report, library_rescrape | 377 |

### 3.3 Wiring

`__init__.py` ré-exporte les 16 fonctions. Les décorateurs Typer (`@app.command()`) restent sur chaque fonction — le wiring est fait par l'appelant qui importe les fonctions et les attache au sous-app Typer, comme c'est déjà le cas dans `indexer/commands/`.

### 3.4 Import migration

Les imports existants de `personalscraper.commands.library import library_scan` continuent de fonctionner via le ré-export dans `__init__.py`. Les imports directs depuis les sous-modules (`from personalscraper.commands.library.scan import library_scan`) sont aussi possibles pour qui veut être explicite.

---

## 4. File 3 — `dispatch/dispatcher.py` → split

### 4.1 Target structure

```
dispatch/
├── dispatcher.py     # Dispatcher orchestrator (~200 LOC): __init__, process,
                      # _resolve_existing_on_filesystem, _cleanup_orphan_temps,
                      # _move_new (delegates to _transfer)
├── _types.py         # DispatchError, DispatchResult (~25 LOC, unchanged)
├── _transfer.py      # _force_rmtree, _rsync, _rsync_merge, _restore_merge_backup,
                      # _verify_transfer, _has_ntfs_illegal_names, _dir_size_gb (~170 LOC)
├── _movie.py         # dispatch_movie, _replace (~180 LOC)
└── _tv.py            # dispatch_tvshow, _merge, _purge_episode_conflicts (~280 LOC)
```

### 4.2 Extraction strategy

The extracted functions take the attributes they need as explicit parameters rather than accessing `self`:

```python
# dispatch/_transfer.py
def rsync(src: Path, dst: Path, *, dry_run: bool, console: Console) -> None: ...
def verify_transfer(src: Path, dst: Path, console: Console) -> None: ...
```

The `Dispatcher` methods become thin delegators:

```python
# dispatch/dispatcher.py
def _rsync(self, src: Path, dst: Path) -> None:
    return _transfer.rsync(src, dst, dry_run=self.dry_run, console=self.console)
```

If a function accesses too many `self` attributes (> 4), it's kept as a method and the class is split differently (e.g., mixin via composition). Final decision made at implementation time based on actual coupling.

### 4.3 Import migration

Internal to `dispatch/` only — no external consumers import `Dispatcher` internals directly (they import `run_dispatch` from `dispatch.run`). Verify with grep before finalizing.

---

## 5. File 4 — `indexer/outbox.py` → `indexer/outbox/` package

### 5.1 Target structure

```
indexer/outbox/
├── __init__.py       # Package docstring only
├── _types.py         # OutboxPayloadError, DrainStats (~25 LOC)
├── _disk.py          # _disk_is_mounted, _resolve_path_id, _ensure_path_id,
                      # disk_id_for_path (~120 LOC)
├── _apply.py         # _apply_move, _apply_nfo_write, _apply_artwork_write,
                      # _apply_trailer_download (~310 LOC)
├── _drain.py         # _dedup_key, _apply_row_with_retry, _replay_pending_ops,
                      # drain, drain_if_present (~380 LOC)
└── _publish.py       # publish_event (~80 LOC)
```

### 5.2 Extraction strategy

All functions are top-level — no class to break. Each function moves to its new module. Internal helpers (prefixed `_`) stay private to their module. Public functions (`drain`, `drain_if_present`, `publish_event`, `disk_id_for_path`) are imported by consumers from their new locations.

### 5.3 Import migration

Find all imports of `indexer.outbox` symbols and update. Likely consumers: `indexer/scanner/_modes/*.py`, `indexer/commands/*.py`, dispatch module.

---

## 6. Scraper mixins — mypy `attr-defined` fix

### 6.1 Problem

`Scraper` uses 4 mixins via multiple inheritance:

```python
class Scraper(ClassifierMixin, ExistingValidatorMixin, MovieServiceMixin, TvServiceMixin):
```

The mixins access 14 context attributes defined in `Scraper.__init__`:

| Category    | Attributes                                                                                                                                     |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Config      | `self.config`, `self.patterns`, `self.dry_run`                                                                                                 |
| Language    | `self._scraper_language`, `self._scraper_fallback_language`, `self._prefer_local_title`, `self._tvdb_language`, `self._tvdb_fallback_language` |
| API clients | `self._tmdb`, `self._tvdb`                                                                                                                     |
| Helpers     | `self._nfo`, `self._artwork`, `self._keywords_cache`, `self._needs_keywords`                                                                   |

They also call methods from each other via `self._classify_item(...)`, `self._repair_movie_dir(...)`, etc.

Mypy analyzes each mixin in isolation and sees 112 `attr-defined` errors because it cannot know what `self` will be at runtime.

### 6.2 Solution

Create `scraper/_context.py` with a `ScraperContext` Protocol declaring all shared attributes and cross-mixin methods:

```python
# scraper/_context.py
from typing import Protocol, TYPE_CHECKING
if TYPE_CHECKING:
    from personalscraper.conf.models import Config
    from personalscraper.config import Settings
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper._shared import ScrapeResult
    ...
```

```python
class ScraperContext(Protocol):
    """Protocol declaring every attribute a scraper mixin can read from self."""

    # --- public config attributes (set in Scraper.__init__) ---
    config: Config | None
    patterns: NamingPatterns
    dry_run: bool

    # --- language ---
    _scraper_language: str
    _scraper_fallback_language: str
    _prefer_local_title: bool
    _tvdb_language: str
    _tvdb_fallback_language: str

    # --- API clients ---
    _tmdb: TMDBClient
    _tvdb: TVDBClient

    # --- helpers ---
    _nfo: NFOGenerator
    _artwork: ArtworkDownloader
    _keywords_cache: KeywordsCache | None
    _needs_keywords: bool

    # --- cross-mixin methods ---
    def _classify_item(self, ...) -> str | None: ...
    def _resolve_title(self, ...) -> str: ...
    def _strip_trailing_year(self, ...) -> str: ...
    def _check_missing_movie_artwork(self, ...) -> list[str]: ...
    def _check_missing_tvshow_artwork(self, ...) -> list[str]: ...
    def _recover_movie_artwork(self, ...) -> None: ...
    def _recover_tvshow_artwork(self, ...) -> None: ...
    def _repair_movie_dir(self, ...) -> None: ...
    def _repair_tvshow_dir(self, ...) -> None: ...
    def _verify_existing_scrape(self, ...) -> bool: ...
    def _extract_tmdb_id_from_nfo(self, ...) -> str | None: ...
    def _download_episode_thumb(self, ...) -> None: ...
    def _generate_episode_nfos(self, ...) -> list[NfoResult]: ...
```

Each mixin method annotates `self`:

```python
class MovieServiceMixin:
    def scrape_movie(self: ScraperContext, movie_dir: Path) -> ScrapeResult:
        ...
```

### 6.4 God-method decomposition (opportunistic)

Three mixin methods exceed 200 lines and will benefit from extraction while we touch these files:

| Method               | Lines | File                    | Extraction targets                                                             |
| -------------------- | ----- | ----------------------- | ------------------------------------------------------------------------------ |
| `scrape_tvshow`      | 331   | `tv_service.py`         | Extract `_lookup_series()`, `_match_seasons()`, `_build_episode_map()`         |
| `_repair_tvshow_dir` | 289   | `existing_validator.py` | Extract `_repair_season_dir()`, `_repair_episode_files()`, `_repair_artwork()` |
| `scrape_movie`       | 220   | `movie_service.py`      | Extract `_match_movie_candidates()`, `_select_best_candidate()`                |

Extraction is **behaviour-preserving**: cut + paste + adjust indentation + add `self:` calls. Zero logic changes. Done in the same commit as the `ScraperContext` Protocol addition.

### 6.5 Impact

- New file: `scraper/_context.py` (~70 LOC, Protocol only)
- Each mixin method signature gets `self: ScraperContext` — purely static, no runtime effect
- God-methods decomposed into 8-10 smaller sub-methods
- Zero logic changes, zero test impact
- 112 mypy errors → 0

---

## 7. Hard-block size guardrail

`scripts/check-module-size.py` currently exits 0 always (advisory in 0.9.0). Bump to hard block:

- WARN (≥ 800 LOC): exit 0, message to stderr
- REPORT (≥ 1000 LOC): exit 1, message to stderr — **hard block** in `make check`
- Version bump from 0.9.0 advisory to 0.10.0 hard block

```bash
# In Makefile check target — already wired, no change needed
python3 scripts/check-module-size.py
```

The script already supports the right thresholds. The change is: when REPORT findings exist, exit 1 instead of 0. That's the only change to the script.

---

## 8. Order of operations

| Step | Task                                     | Rationale                                                                                 |
| ---- | ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| 1    | `conf/models.py` → package               | Most critical (REPORT). Highest blast radius on imports. Includes Reserved field cleanup. |
| 2    | `indexer/outbox.py` → package            | Clear phase-based structure, low coupling to other changes.                               |
| 3    | `dispatch/dispatcher.py` → split         | Internal to dispatch package, minimal external imports.                                   |
| 4    | `commands/library.py` → package          | Typer wiring is the most delicate; do after patterns are established.                     |
| 5    | Scraper mixins `ScraperContext` Protocol | Fix 112 mypy attr-defined errors. Purely additive, zero test impact.                      |
| 6    | `check-module-size.py` hard block        | Bump to exit 1 on REPORT. Must pass since all files are now decomposed.                   |

---

## 9. Risk register

| #   | Risk                                                                                        | Likelihood | Impact | Mitigation                                                                                                                             |
| --- | ------------------------------------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | Consumer of removed Reserved field in existing `config.json5` → `extra='forbid'` rejects it | Medium     | Medium | `init-config` regenerates clean config; manual config users see a loud error with the exact field name. Acceptable for pre-production. |
| R2  | Typer decorator wiring breaks after library split                                           | Medium     | Medium | `__init__.py` re-exports all 16 functions; test with `personalscraper library-index --help` before committing                          |
| R3  | Import cycle created by new module boundaries                                               | Low        | High   | `ruff check` + `python -c "import personalscraper"` after each step                                                                    |
| R4  | Coverage drop from tests importing old paths                                                | Medium     | Medium | Coverage report before/after each step; update test imports in same commit                                                             |
| R5  | Reserved field removal deletes a field that IS consumed but grep missed it                  | Low        | High   | `make test` runs all tests including E2E; any config loading failure will fail tests                                                   |
| R6  | `Dispatcher` method extraction breaks subtle `self` state coupling                          | Medium     | Medium | Read each method body before extracting; if > 4 `self` attribute accesses, keep as method                                              |
| R7  | `ScraperContext` Protocol misses an attribute → mypy errors persist                         | Low        | Medium | Grep `self\._*\w+` in all 4 mixins before finalizing the Protocol; verify with `make lint`                                             |
| R8  | God-method extraction breaks implicit closure over local vars                               | Medium     | Medium | Each extracted sub-method receives all needed vars as explicit parameters; review diff carefully                                       |

---

## 10. Documentation updates (exhaustive)

Every documentation file referencing a decomposed module must be updated in the same commit as the decomposition.

### 10.1 `docs/reference/architecture.md`

| Location              | Change                                                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Line 46: `commands/`  | Add `commands/library/` sub-package listing its 5 modules                                                                      |
| Line 47: `conf/`      | Add `conf/models/` sub-package listing its 11 domain files                                                                     |
| Line 97: `outbox.py`  | Replace with `outbox/` package tree (6 files: `_types.py`, `_disk.py`, `_apply.py`, `_drain.py`, `_publish.py`, `__init__.py`) |
| Line 123: `dispatch/` | Add new `_types.py`, `_transfer.py`, `_movie.py`, `_tv.py` files                                                               |
| Line 136: `models.py` | Clarify as `personalscraper/models.py` (StepReport, SortResult) — distinct from `conf/models/`                                 |

### 10.2 `docs/reference/indexer-json-shapes.md`

| Location                                            | Change                                                                                                |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Line 61: `` `personalscraper/indexer/outbox.py` ``  | Replace with `` `personalscraper/indexer/outbox/_apply.py` `` (or the appropriate specific submodule) |
| Line 119: `` `personalscraper/indexer/outbox.py` `` | Replace with `` `personalscraper/indexer/outbox/_drain.py` ``                                         |

### 10.3 `CLAUDE.md` (project root)

| Location                           | Change                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------- |
| Module-size rule (already present) | Verify thresholds are accurate (800 WARN, 1000 REPORT hard block in 0.10.0) |
| Reference Index table              | If any entry references the old module paths, update                        |

### 10.4 `docs/reference/indexer.md`

| Location                  | Change                      |
| ------------------------- | --------------------------- |
| Any `outbox.py` reference | Update to `outbox/` package |

### 10.5 `docs/superpowers/plans/2026-05-03-config-coherence-intervention.md`

**Do NOT update** — this is another agent's active plan. Merge conflict prevention: if this plan is modified, coordinate with the other agent.

### 10.6 Archive docs (`docs/archive/`)

**Do NOT update** — archive docs are historical snapshots. They intentionally reference the file structure at the time they were written. Updating them would destroy the historical record.

---

## 11. VERSION bump

0.9.0 → 0.10.0 (minor). Rationale: the hard-block size guardrail promotion is a behavioural change that downstream tooling (`make check` in CI) will feel. The Reserved field removal is a schema change (backward-incompatible for config files containing removed fields).
