# ROADMAP — PersonalScraper

> Future ideas. Each item gets its own brainstorming session before implementation.
> Priority scale: **P1** (high — unblocks major features, do next) → **P3** (stretch — nice to have, no urgency).
> Shipped work is **not** tracked here — see `CHANGELOG.md` and `docs/archive/features/`.

---

## P1 — High Priority (do next, unblocks major features)

### P1 — Architecture Cleanup Round 2 (`arch-cleanup-2`)

> **Status: implemented (v0.17.0) — shipped pending merge.** All four goals below
> are delivered on `feat/arch-cleanup-2`; the entry is kept here until the PR merges.
> Design: `docs/features/arch-cleanup-2/DESIGN.md`. Source analysis: `docs/analysis/05-architecture-improvement-roadmap.md`.

The original `arch-cleanup` (v0.9.0) decomposed the god-modules. This second round fixes the
architectural defects that block the web-facing roadmap (Web UI / Watcher / Auto-Download) and
collapses residual horizontal coupling. The code is structurally healthier than the older
ROADMAP/`architecture.md` claimed — these are targeted, low-risk enablers, not a rewrite.

**Goals**

- Bring the 5 registry events (`ProviderFallbackTriggered`, `ProviderExhaustedEvent`, `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated`) onto the base `Event` contract so they round-trip through envelope serialization and reach base-`Event` subscribers.
- Add a `schema_version` field to the `Event` envelope before the first cross-process consumer (Web UI / Watcher) exists.
- Fix the dependency-direction leak: `core/` and `conf/` import upward into `api/` + the logger, inverting the documented acyclic direction.
- Promote `sorter.file_type.VIDEO_EXTENSIONS` / `FileType` to a neutral home — it is imported by 11 non-`sorter` subpackages across 23 import lines; this turns `sorter` back into a pure pipeline step.

**Non-goals**

- The heavy library/indexer fold (separate `lib-fold` entry).
- A full DI framework (see P3 DI Container).

### P1 — Library / Indexer Consolidation (`lib-fold`)

> Design: `docs/features/lib-fold/DESIGN.md` _(to be written)_. Source analysis: `docs/analysis/01-library-indexer-consolidation.md`.

**Premise correction (verified 2026-05-28):** `library/scanner.py` does **not** duplicate the
indexer walk — `scan_library()` walks only at media-directory granularity, then delegates the
recursive file walk to `indexer.scanner.scan(mode=ScanMode.full)` (`library/scanner.py:38-39,997`).
The real consolidation problem is narrower and concrete:

- **Two `media_item` writers** that must be reconciled: `library/scanner.py:691` (`_item_repo.upsert` — rich rows with seasons/episodes/`canonical_provider`) and `dispatch/media_index.py` (`MediaIndex.rebuild` — minimal cache rows, `canonical_provider=None`, auto-rebuilt on empty DB).
- **Two MediaInfo backends**: ffprobe in `library/analyzer.py` vs pymediainfo in `indexer/scanner/_modes/enrich.py`, both persisting to `media_stream` (a documented HDR/Atmos fidelity gap exists between them).
- **Divergent season-directory regexes** duplicated across `indexer/` + `trailers/` instead of a single `naming_patterns` SSOT.
- **`canonical_provider` extraction** duplicated between `library/scanner.py` and the indexer backfill path (guards the 194-show regression).

Actual `library/` package (8 modules): `analyzer.py`, `disk_cleaner.py`, `models.py`,
`recommender.py`, `reporter.py`, `rescraper.py`, `scanner.py`, `validator.py`.

**Goals**

- Fold rich `media_item`/`season`/`episode` creation into a unified indexer scan stage; reconcile the `dispatch/media_index.py` minimal-row writer.
- Merge `library/analyzer.py` (ffprobe) into `enrich.py` — resolve the HDR/Atmos gap or accept it explicitly (no migration script; evolve in place).
- Move `library/recommender.py` + `library/reporter.py` into a read-only `insights/` package over the indexer DB.
- Re-home `library/validator.py` as a `verify/` check plugin — **not inline** into `verify/checker.py` (already 713 non-blank LOC, near the 800 advisory ceiling).
- Re-home `library/disk_cleaner.py` (filesystem `rmtree`) into a new `maintenance/` module — **not** `indexer/repair.py` (which is DB-only).
- Remove the `library/` package once all consumers are migrated (residual-import grep gate).

**Non-goals**

- Removing any CLI commands — `library-index`, `library-search`, `library-report`, etc. keep working from new locations.
- Changing the indexer schema.

---

## P2 — Medium Priority (important but not blocking)

### P2 — Web Management UI

Web-based graphical interface to pilot and supervise the whole project from a browser.

- **Pipeline control**: start / pause / resume / kill each step (`ingest`, `sort`, `process`, `dispatch`), view live logs, step status, and per-run history.
- **Configuration editor**: visual editor for `config/` (paths, categories, disks, thresholds, patterns) with schema validation and safe reload — no shell required.
- **Maintenance dashboard**: disk usage / free space per disk, orphan files (`_tmp_ingest_*`, `_tmp_dispatch_*`), stale locks, library index health, pipeline-runs history.
- **Interactive scraping**: front-end for the manual-decision points currently handled via MediaElch / CLI prompts — ambiguous TMDB/TVDB matches, multi-result picks, low-fuzzy-score arbitration, manual override of detected title/year/season.
- **Future-ready**: UI shell designed to host pages for upcoming roadmap items, notably:
  - **Auto-Download System** — tracker search, format preferences, subscription list CRUD, override rules editor
  - **Watcher Service** — live watcher status, trigger history
  - **Library Indexer** — browse/search indexed media, trigger re-scan, view stale entries
  - **YoutubeTrailerScraper Integration** — missing-trailer queue, per-item scrape trigger
- **Architecture pointers** (to decide during brainstorm): FastAPI / Flask + HTMX vs. SPA (Vue/React) + REST/WebSocket; auth (local-only vs. basic auth); reverse-proxy friendly (sub-path deploy behind `iznogoudatall.xyz`).
- **Out of scope (v1)**: multi-user, remote-agent control, mobile-specific UX.

**Depends on:** Pipeline Observer Protocol (shipped v0.13.0), Event Bus (shipped v0.14.0), Third-Party API Consumer Unification (shipped v0.11.0). Prerequisite: `arch-cleanup-2` (Event contract + envelope `schema_version`) — implemented v0.17.0, shipped pending merge.

### P2 — Auto-Download System

Automatic torrent download pipeline with tracker API integration.

- Define preferred format + fallback formats.
- Series subscription list with cron-based new episode checks.
- Search multiple trackers via their APIs with preference ordering.
- Connect the library recommendation list to auto-download for library renewal.
- Override rules by criteria: studio, director, franchise, title, IMDB ID.

**Depends on:** Third-Party API Consumer Unification (shipped v0.11.0), Provider Registry (shipped v0.16.0).

### P2 — Watcher Service

Replace cron-based pipeline trigger with a real-time watcher service.

- Service that watches either qBittorrent state or the `complete/` directory.
- Triggers `personalscraper run` automatically on new downloads.
- More responsive than the current 3am daily cron.

**Depends on:** Event Bus (shipped v0.14.0), Pipeline Observer Protocol (shipped v0.13.0). Prerequisite: `arch-cleanup-2` (cross-process event envelope) — implemented v0.17.0, shipped pending merge.

### P2 — Verify Checker Plugin System

`verify/checker.py` (822 LOC, 713 non-blank) is a monolithic file containing all pre-dispatch validation checks. Adding a new check (e.g., a new media type, a new quality rule) requires modifying the file directly. A plugin architecture makes checks independently testable, extensible, and discoverable by the Web UI. This is also the landing zone for `library/validator.py` (see `lib-fold`).

**Goals**

- `Check` Protocol: `severity: Severity`, `category: str`, `check(item: Path, config: Config) -> CheckResult`.
- `CheckRegistry` — checks auto-register via a decorator or entry point.
- Each existing check group (NFO validity, artwork presence, naming conventions, stream details, genre categorization, file size, the Phase 30 `no_duplicate_videos` movie check) becomes its own plugin file under `verify/checks/`.
- Web UI can list available checks, run them individually, and display per-check results.
- CLI gets `personalscraper verify --check nfo_validity` granular invocation.

**Non-goals**

- Changing existing check logic beyond the extraction itself.

### P2 — Reverse Episode Lookup (Standalone)

Find SXXEXX for episodes missing season/episode numbers via reverse scraping on TVDB (TMDB/other fallback). Standalone command invoked manually when needed.

- **Input**: a video file named without SXXEXX (e.g. `The Return of the King.mkv`).
- **Reverse lookup**: clean the filename → search the episode name in TVDB (within the already-identified series) → retrieve `airedSeason` and `airedEpisodeNumber`.
- **Cascading fallback**: TVDB in scraping language → TVDB in fallback language → TMDB → other scrapers.
- **Output**: rename the file to `SXXEXX - Episode Name.ext` so it flows through the standard pipeline.
- **CLI**: `personalscraper resolve-episodes <path>` — standalone, not integrated into the automated pipeline.
- **Codebase**: inspired by the `TVDBNameToNum.py.bak` script (interactive TVDB v3 interface, name cleaning/normalization, fuzzy matching).

**Depends on:** Provider Registry (shipped v0.16.0) for clean provider fallback.

### P2 — Multi-Filesystem Support (`multi-filesystem`)

> Design: `docs/features/multi-filesystem/DESIGN.md` _(to be written)_. Source analysis: `docs/analysis/04-filesystem-decoupling-macfuse-ntfs.md`.

Today NTFS-via-macFUSE behaviour is hardcoded in the transfer layer and filesystem-type
detection is duplicated across three independent `mount`-parsers. The next storage target is
**HFS+ on AppleRAID** (native macOS, full POSIX perms, no macFUSE), and the goal is to support
every mainstream filesystem (APFS, HFS+, ext4, exFAT, NTFS) without losing current behaviour.

**Goals**

- Consolidate the three `mount`-parsers (`indexer/db.py`, `indexer/scanner/_spotlight.py`, `indexer/scanner/__init__.py`) into one cached `FsProbe`.
- Introduce a `FilesystemCapability` table (rsync flags, atomic-rename support, mtime/ctime reliability, case-sensitivity, xattr/AppleDouble handling) keyed off detected FS type; the NTFS entry stays byte-identical to today.
- Make `dispatch/_transfer.py` (`rsync()` + `rsync_merge()` currently share byte-identical hardcoded NTFS flags) and the indexer tier-1 drift detector consume the capability table.
- Fix the latent dead-branch bug in `_spotlight.try_attach` (`fs_type == "macfuse"` never matches real `ufsd_NTFS` mounts; `db.py` uses substring matching and is correct — the asymmetry is the root cause).

**Non-goals**

- Changing the indexer schema beyond additive capability metadata.
- Network filesystems (NFS/SMB).

### P2 — Web UI Registry Consumer

**Source**: registry feature DESIGN §11 deferral (recorded in Phase 12 of the registry feature).

**Goal**: Expose ProviderRegistry status + operations to the Web Management UI (P2 above). Surface live provider eligibility, circuit state, fallback history, fan_out attempted lists.

**Dependencies**:

- Web Management UI scaffolding (P2 above).
- `registry.status()` + `registry.operations()` (shipped v0.16.0 — Provider Registry feature).
- Prerequisite: `arch-cleanup-2` (registry events on the base `Event` contract for WebSocket streaming) — implemented v0.17.0, shipped pending merge.

**Scope**:

- WebSocket subscription to `ProviderFallbackTriggered`, `ProviderExhaustedEvent`, `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated` events.
- REST endpoint `GET /api/registry/status` returning the dict from `registry.status()`.
- REST endpoint `GET /api/registry/operations` returning the dict from `registry.operations()`.
- UI panel: per-provider circuit state, per-capability priority chain, fan_out latency aggregates.

**Non-goals**:

- Hot-swap (separate ROADMAP entry — see P3 Hot-Swap).
- Provider configuration editing via UI (config file is source-of-truth; UI is read-only).

**Estimated effort**: 1 sprint (5 days) after Web Management UI scaffolding lands.

---

## P3 — Stretch (nice to have, lower urgency)

### P3 — Tech-Debt Round 2 (`tech-debt-2`)

> Design: `docs/features/tech-debt-2/DESIGN.md` _(to be written)_. Source analysis: `docs/analysis/03-god-modules-debt-audit.md` + a forthcoming broad debt sweep.

**Status correction (verified 2026-05-28, HEAD `79b345d8`):** the god-module "crisis" the older
ROADMAP described **no longer exists**. `python3 scripts/check-module-size.py` exits **0** (no
hard-block breach); only **two** files exceed the 800 non-blank soft-warn ceiling:
`scraper/movie_service.py` (**954** non-blank — grew from 927 via the Phase 30 orphan-unlink fix,
now 46 lines from the 1000 hard ceiling) and `library/scanner.py` (**855** non-blank, removed by
`lib-fold`). The previously-listed offenders are all under ceiling now: `indexer/scanner/__init__.py`
621, `trailers/state.py` 767, `trailers/cli.py` 698, `indexer/db.py` 588. `scraper/tmdb_client.py`
no longer exists (split into `api/metadata/tmdb.py` + `api/metadata/_tmdb_parsers.py`).

**Real blind spot:** `check-module-size.py` excludes **all** `__init__.py` files (line 22/37),
hiding two facade modules carrying heavy logic: `api/metadata/registry/__init__.py` (689 non-blank —
the largest module by this metric) and `indexer/scanner/__init__.py` (621). The guardrail policy is
the decision to make.

**Goals**

- Extract `scraper/movie_service.py` along its dedup/rename/orphan-unlink seam to get it back under 800 and away from the hard ceiling.
- Decide and implement the `__init__.py` guardrail policy (count facade modules, or enforce re-exports-only).
- Run a broad debt sweep (dead code, `TODO`/`FIXME`/`HACK`, `type: ignore` / `pragma: no cover` debt, broad `except`, magic values, test skips / `xfail` / `skip_audit` expiries) and fold the actionable items into the design.

**Non-goals**

- Behaviour changes during extraction — structural moves only.

### P3 — LLM Pipeline Assistant (idée, gardée pour la fin)

Connecter un LLM (local et/ou distant) comme assistant d'arbitrage pour les
points du pipeline qui requièrent aujourd'hui une décision humaine (matches
ambigus TMDB/TVDB, post-mortem d'erreurs, détection d'incohérences). L'IA
s'imprègne de la médiathèque existante et apprend des corrections utilisateur
via RAG — jamais de fine-tuning, jamais autonome, toujours en validation.
Principe directeur : feature volontairement simple à implémenter.

Vision et questions ouvertes (document vivant, pas de plan technique) :
`docs/superpowers/roadmap/llm-assistant/brainstorming.md`

**Brainstorming déjà entamé** (2026-05-11/12) : principes directeurs posés,
cas d'usage cadrés (pipeline + médiathèque), stack pressenti identifié
(MCP server + sqlite-vec + Ollama + Open WebUI compatible), 3 questions
ouvertes restantes (log de corrections, indexation initiale, confidentialité
backend distant). Reprendre la prochaine session via `/brainstorming` sur ce
document — pas besoin de repartir de zéro.

### P3 — Dependency Injection Container

Components directly instantiate their dependencies (e.g., `Scraper.__init__` creates its own `TMDBClient`, `TVDBClient`, `NFOGenerator`, `ArtworkDownloader`). This makes testing harder (requires monkeypatching) and blocks the Web UI from swapping real implementations for mocks. May be partly absorbed by `arch-cleanup-2` if a `ServiceContainer` lands there first.

**Goals**

- Lightweight DI container (no framework — a simple `AppContext` dataclass or `ServiceContainer` with factory functions).
- All domain services accept their dependencies via `__init__`, never create them internally.
- CLI wiring creates the production container; tests create a test container; Web UI creates a headless container.

**Non-goals**

- Runtime service hot-swap.
- Full-blown DI framework (no `dependency-injector`, no decorator-based injection).

### P3 — Additional Trackers (torr9 + digitalcore)

Implement `api/tracker/torr9.py` and `api/tracker/digitalcore.py` following the
`TrackerClient` Protocol established in 0.11.0. Study each tracker's API
(Torznab/RSS/REST), capture real-response samples, write reference docs in
`docs/reference/torr9-api.md` and `docs/reference/digitalcore-api.md`, then
implement using the unified `HttpTransport` infrastructure.

**Goals**

- Two new `TrackerClient` providers, plug-compatible with the existing
  `TrackerRegistry` and `rank()` engine.
- Reference docs + sample fixtures so future updates can replay against
  captured responses.
- Activation through the existing `ProviderActivation` mechanism — no new
  config schema.

**Non-goals**

- New ranking criteria (the engine landed in 0.11.0 already supports
  arbitrary providers).
- Auto-Download System integration — that lands in its own P2 feature.

**Depends on**: Third-Party API Consumer Unification (shipped v0.11.0).

### P3 — Active Health Scoring (Registry)

**Source**: registry feature DESIGN §11 deferral (recorded in Phase 12 of the registry feature).

**Goal**: Move from passive circuit breaker (per-call failure threshold) to active health scoring (periodic ping + rolling window + provider de-prioritization).

**Dependencies**:

- Provider Registry framework (shipped v0.16.0).
- ProviderObserver protocol (already defined for circuit transitions).

**Scope**:

- New `ProviderHealthMonitor` running as a background AppContext-scoped task.
- Each provider exposes `health_check() -> bool` (cheap synthetic call).
- Rolling window of last N health checks, exponentially-weighted moving average.
- `chain()` consults health score: providers below threshold are skipped (not removed — re-attempted on next health window).
- `registry.status()` includes per-provider health score.

**Non-goals**:

- Active load balancing.
- Per-region provider routing.

**Risk**: health_check budget for each provider must be defined to avoid quota burn.

**Estimated effort**: 1 sprint (5 days).

### P3 — Hot-Swap Provider Configuration

**Source**: registry feature DESIGN §11 deferral (recorded in Phase 12 of the registry feature).

**Goal**: Reload `ProvidersConfig` on SIGHUP or config-file change without restarting the process. Currently registry is constructed once at AppContext init; config changes require restart.

**Dependencies**:

- Provider Registry framework (shipped v0.16.0).
- `validate_config()` (shipped v0.16.0, used at boot — re-usable for hot reload).

**Scope**:

- File-watcher on `config/providers.json5` (using `watchdog` or polling).
- On change: call `validate_config()` → if PASS, atomically swap `ProviderRegistry._index` + `_priority_for_chain` + `_circuit_breakers`.
- Drain in-flight calls before swap (5 s grace period).
- Emit new event `RegistryHotSwapped(...)` with diff summary.

**Non-goals**:

- Hot-swap of provider IMPLEMENTATIONS (only config). Adding a new provider class still requires restart.
- Distributed config (single-process only).

**Risk**: Race conditions on circuit breaker state during swap. Mitigate with explicit drain protocol.

**Estimated effort**: 2 sprints (10 days).
