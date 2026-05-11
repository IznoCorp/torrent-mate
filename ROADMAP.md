# ROADMAP — PersonalScraper

> Future ideas. Each item gets its own brainstorming session before implementation.
> Priority scale: **P0** (critical — blocks other items & must be next) → **P3** (stretch — nice to have, no urgency).

---

## P0 — Critical Path (do next, unblocks multiple downstream items)

> _All P0 items completed in 0.11.0. See "Completed" section for the api-unify summary._

---

## P1 — High Priority (next after P0, unblocks major features)

### P1 — Pipeline Observer Protocol (Headless Mode)

`pipeline.py` is directly coupled to `rich.Console` — it creates a console internally and passes it to every step via `StepContext`. This makes the pipeline impossible to drive from anything other than a TTY: no Web UI, no watcher service, no headless cron mode with programmatic status polling.

**Blocked by this refactor**: Web Management UI (needs headless pipeline), Watcher Service (needs programmatic trigger), Auto-Download (needs pipeline status from a non-interactive context).

**Goals**

- Define a `PipelineObserver` Protocol with callbacks: `on_step_start(step_name)`, `on_step_end(step_name, report)`, `on_error(step_name, error)`, `on_progress(step_name, item, status)`.
- The `rich.Console` rendering becomes **one** observer among others (the default when running interactively).
- Web UI registers a WebSocket observer; the watcher registers a minimal logging observer; tests register a collecting observer.
- `Pipeline.__init__` accepts `observers: Sequence[PipelineObserver] | None`, keeping backward compatibility.
- `StepContext` drops the `console: Console` field in favor of `observers` — steps notify observers instead of printing.

**Non-goals**

- Async pipeline execution (deferred to Watcher Service).
- Real-time step output streaming for the CLI (already works via rich, stays unchanged).

### P1 — Event Bus

No event/signal system exists today. The pipeline runs as a linear sequence with zero hooks for external code to react to: step transitions, item completion, errors, circuit-breaker trips, disk-full conditions, dispatch decisions — all are invisible outside the pipeline process.

**Blocked by this refactor**: Watcher Service (needs "download complete" → trigger), Web UI (needs real-time progress streaming), Auto-Download (needs "recommendation list updated" → search).

**Goals**

- Minimal pub/sub event bus (`EventBus` class with `subscribe(event_type, callback)` and `emit(event)`).
- Typed event dataclasses: `StepStarted`, `StepCompleted`, `StepErrored`, `ItemDispatched`, `CircuitBreakerOpened`, `DiskFullWarning`, `TrailerDownloaded`, `LibraryScanCompleted`.
- Events are fire-and-forget (synchronous by default, async variant deferred).
- CLI `--verbose` flag subscribes a debug event logger.
- Zero overhead when no subscribers are registered (fast-path).

**Non-goals**

- Persistent event log / event sourcing.
- Cross-process events (needed later for Watcher Service, but out of scope for v1).
- Retry/replay semantics.

**In progress** (feat/event-bus, version 0.14.0):

- Codename: `event-bus`
- SemVer bump: minor (Y+1)
- Design: `docs/features/event-bus/DESIGN.md`
- Plan: `docs/features/event-bus/plan/INDEX.md` (5 phases, 42 sub-phases)
- Activated on: 2026-05-11

### P1 — Provider Registry (Scraper Orchestrator Decoupling)

`scraper/orchestrator.py` hardcodes `self._tmdb` and `self._tvdb` with ad-hoc fallback logic ("if TMDB circuit open, skip" — line 151; "if both circuits open, skip" — line 224). Adding a new metadata provider (IMDB, SensCritique from the ROADMAP matrix) requires modifying the orchestrator directly.

**Blocked by this refactor**: Third-Party API Consumer Unification (the unified clients need a registry to plug into), provider matrix expansion.

**Goals**

- `ProviderRegistry` class mapping provider name → `MetadataProvider` instance, ordered by per-use-case priority from config.
- Orchestrator iterates over the ordered registry instead of referencing `self._tmdb` / `self._tvdb` directly.
- Circuit-breaker awareness: the registry skips providers whose circuit is open, tries next in priority order.
- Config-driven: `series_scraping: { tvdb: 1, tmdb: 2, imdb: 3 }` → orchestrator picks TVDB first, falls back to TMDB, then IMDB.

**Non-goals**

- Runtime provider hot-swap.
- Provider health scoring beyond the existing circuit breaker.

### P1 — Library / Indexer Consolidation

Two scanner subsystems coexist: `library/scanner.py` (726 LOC) and `indexer/scanner/` (4000+ LOC). The library scanner walks disks and writes results to the indexer DB — duplicating walk logic that the indexer scanner already has. The `library/` module totals 4565 LOC with significant overlap against `indexer/` (scanner, analyzer vs enrich mode, validator vs verify, cleaner vs dedup).

This is the largest remaining source of architectural dual-mental-model complexity, a direct remnant noted in the arch-cleanup DESIGN (§4 — "dual mental models that have accumulated: library-scan, media_index.json").

**Goals**

- Deprecate `library/scanner.py` — its functionality is subsumed by `indexer/scanner` (full mode + quick mode).
- Merge `library/analyzer.py` (ffprobe deep scan) into `indexer/scanner/_modes/enrich.py` as an optional enrich sub-step.
- Move `library/recommender.py` and `library/reporter.py` to a new `insights/` package — a read-only query layer on top of the indexer DB.
- Move `library/validator.py` checks into `verify/checker.py` or the verify check plugin system (see P2).
- Move `library/disk_cleaner.py` into `process/` or `indexer/repair.py`.
- Remove the `library/` package entirely once all consumers are migrated.

**Non-goals**

- Removing any CLI commands — `library-index`, `library-search`, `library-report`, etc. keep working, they just import from the new locations.
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

**Depends on:** Pipeline Observer Protocol (P1), Event Bus (P1), Third-Party API Consumer Unification (P0).

### P2 — Auto-Download System

Automatic torrent download pipeline with tracker API integration.

- Define preferred format + fallback formats.
- Series subscription list with cron-based new episode checks.
- Search multiple trackers via their APIs with preference ordering.
- Connect the library recommendation list to auto-download for library renewal.
- Override rules by criteria: studio, director, franchise, title, IMDB ID.

**Depends on:** Third-Party API Consumer Unification (P0), Provider Registry (P1).

### P2 — Watcher Service

Replace cron-based pipeline trigger with a real-time watcher service.

- Service that watches either qBittorrent state or the `complete/` directory.
- Triggers `personalscraper run` automatically on new downloads.
- More responsive than the current 3am daily cron.

**Depends on:** Event Bus (P1), Pipeline Observer Protocol (P1).

### P2 — Verify Checker Plugin System

`verify/checker.py` (621 LOC) is a monolithic file containing all pre-dispatch validation checks. Adding a new check (e.g., a new media type, a new quality rule) requires modifying the file directly. A plugin architecture makes checks independently testable, extensible, and discoverable by the Web UI.

**Goals**

- `Check` Protocol: `severity: Severity`, `category: str`, `check(item: Path, config: Config) -> CheckResult`.
- `CheckRegistry` — checks auto-register via a decorator or entry point.
- Each existing check group (NFO validity, artwork presence, naming conventions, stream details, genre categorization, file size) becomes its own plugin file under `verify/checks/`.
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

**Depends on:** Provider Registry (P1) for clean provider fallback.

---

## P3 — Stretch (nice to have, lower urgency)

### P3 — LLM Pipeline Assistant (idée, gardée pour la fin)

Connecter un LLM (local et/ou distant) comme assistant d'arbitrage pour les
points du pipeline qui requièrent aujourd'hui une décision humaine (matches
ambigus TMDB/TVDB, post-mortem d'erreurs, détection d'incohérences). L'IA
s'imprègne de la médiathèque existante et apprend des corrections utilisateur
via RAG — jamais de fine-tuning, jamais autonome, toujours en validation.
Principe directeur : feature volontairement simple à implémenter.

Vision et questions ouvertes (document vivant, pas de plan technique) :
`docs/superpowers/roadmap/llm-assistant/brainstorming.md`

### P3 — God-Module Splits (Residual from arch-cleanup)

The arch-cleanup feature completed major decomposition (CLI, scraper, indexer CLI, config models, dispatch), but four modules remain above the 800 LOC advisory ceiling:

| Module                        | LOC  | Issue                                                                                                                                          |
| ----------------------------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `indexer/scanner/__init__.py` | 1056 | `scan()`, `filter_disks()`, `_finalize_disk_after_walk()` + 15 helpers in one file. `_modes/` split was done but the orchestrator core wasn't. |
| `trailers/state.py`           | 950  | JSON state store mixing CRUD, `fcntl` locking, retry policy, GC, atomic writes, and composite-key queries in a single module.                  |
| `trailers/cli.py`             | 752  | Trailer CLI commands live outside the `commands/` pattern adopted by the rest of the project.                                                  |
| `indexer/db.py`               | 604  | Connection management, WAL PRAGMAs, file locking, migration runner, disk-full guard, and corrupt DB recovery — 6 concerns in one file.         |

**Goals**

- `indexer/scanner/__init__.py` → extract `_orchestrator.py` (scan + filter_disks) + `_finalize.py` (post-walk helpers). Target: `__init__.py` ≤ 300 LOC (re-exports only).
- `trailers/state.py` → split into `trailers/state/_store.py` (CRUD), `trailers/state/_lock.py` (fcntl), `trailers/state/_policy.py` (retry rules), `trailers/state/_gc.py` (orphan purge). Target: no file ≥ 500 LOC.
- `trailers/cli.py` → move to `commands/trailers/` following the `commands/library/` pattern (scan.py, download.py, verify.py, purge.py).
- `indexer/db.py` → extract `_migrations.py` (apply + snapshot), `_disk_guard.py` (disk-full detection + corrupt DB quarantine). Target: db.py ≤ 250 LOC (connection + lock only).

**Non-goals**

- Logic changes during extraction — behaviour-preserving moves only (same approach as arch-cleanup phases 2–5).
- No new abstractions — these are purely structural splits.

**Also monitor (700–800 LOC, below advisory ceiling but above DESIGN target of 700):**

| Module                          | LOC | Risk                                                                                         |
| ------------------------------- | --- | -------------------------------------------------------------------------------------------- |
| `scraper/tmdb_client.py`        | 770 | API client with retry, pagination, circuit breaker — natural growth as TMDB surface expands. |
| `scraper/existing_validator.py` | 765 | Re-validation of already-scraped folders — 7 check categories with nested helpers.           |
| `scraper/tv_service.py`         | 735 | TVDB season/episode resolution — multi-season loop + episode-level NFO logic.                |
| `scraper/nfo_generator.py`      | 718 | NFO XML generation for movies + TV shows — template per media type + artwork references.     |

These modules are below the 0.9.0 advisory ceiling (800 LOC) but above the
decomposition target (≤700 LOC). They will need attention before the 0.10.0
hard block if the ceiling is lowered.

### P3 — Dependency Injection Container

Components directly instantiate their dependencies (e.g., `Scraper.__init__` creates its own `TMDBClient`, `TVDBClient`, `NFOGenerator`, `ArtworkDownloader`). This makes testing harder (requires monkeypatching) and blocks the Web UI from swapping real implementations for mocks.

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

**Depends on**: Third-Party API Consumer Unification (P0) — completed in 0.11.0.

---

## ✅ Completed

### YoutubeTrailerScraper Integration (v0.5.0)

Trailer scraping is integrated into the pipeline as step 8 (trailers).

- yt-dlp based download with configurable format selectors
- State tracking per media item (pending/downloaded/skipped)
- CLI: `personalscraper trailers scan|download|verify|purge`
- Pipeline integration: `personalscraper run` (trailers step, skippable via `--skip-trailers`)
- Archived feature docs: `docs/archive/features/trailer/`

### Config System Overhaul (v0.9.0)

Config is now a directory of JSON5 files with overlay merge.

- Split layout: `config.json5` (master + overlays) + per-topic files (paths, disks, categories, patterns, encoding, scraper, trailers, indexer, thresholds)
- `personalscraper init-config` creates `config/` from `config.example/` template
- Optional `local.json5` for machine-specific overrides with last-wins semantics
- All paths, staging layout, thresholds, and preferences live in `config/` — `.env` is credentials only

### Library Indexer (v0.7.0+)

SQLite-based media index with scanner, query engine, and drift reconciliation.

- SQLite database at `config/indexer.db_path` (default `.data/library.db`)
- Scanner modes: `quick`, `incremental`, `enrich`, `full`, `verify` + `backfill`
- CLI: `personalscraper library-index|library-search|library-verify|library-repair|library-reconcile`
- Outbox writethrough for dispatch, trailer state tracking, repair queue
- Launchd agents for nightly quick scan + periodic enrich
- Replaced ad-hoc `library_scan.json` / `library_analysis.json` files
- Archived feature docs: `docs/archive/features/media-indexer/`

### Third-Party API Consumer Unification (v0.11.0 — api-unify)

All external API consumers run on a unified HttpTransport with declarative
TransportPolicy, bringing retry, circuit breaker, rate limiting, auth, and
typed responses under one contract.

- **Family Protocols**: `MetadataClient`, `TorrentClient`, `TrackerClient`,
  `Notifier`, `HealthChecker` (in `api/{metadata,torrent,tracker,notify}/_base.py`).
- **Shared transport**: `HttpTransport` consumes a `TransportPolicy` —
  every provider declares its retry, circuit, rate-limit, and auth strategy
  via dataclass; transport enforces them uniformly.
- **Reusable infrastructure**: `core/circuit.py` (CircuitBreaker reused by
  indexer disk breaker), `core/http_helpers.py` (tenacity retry helpers).
- **10 providers migrated**: TMDB, TVDB, OMDB, Trakt (metadata);
  qBittorrent, Transmission (torrent client); LaCale, C411 (trackers);
  Telegram (notify); healthchecks.io (health).
- **7 modules deleted**: `tmdb_client.py`, `tvdb_client.py`,
  `circuit_breaker.py`, `http_retry.py`, `qbit_client.py`, `notifier.py`,
  `scraper/providers.py`.
- **10 reference docs** with real captured samples in
  `docs/reference/_samples/<provider>/`.
- **5 new config files**: `metadata.json5`, `torrent.json5`, `tracker.json5`,
  `ranking.json5`, `notify.json5`.
- **Activation via creds**: each provider declares `REQUIRED_CREDS`;
  presence in `.env` enables the provider, absence disables it silently.
- **Per-use-case provider priority + tracker ranking engine** with
  `ThresholdEntry` config models.
- **Phase gate hygiene**: full `make check` (lint+test+module-size+typed-api)
  - secret scan + residual-import audit codified in CLAUDE.md.
- Design doc: `docs/features/api-unify/DESIGN.md`

### Architectural Cleanup (v0.9.0 — arch-cleanup)

Decomposition of 4 god modules, `PipelineStep` Protocol, typed `StepReport` payloads, legacy deprecation, and complexity guardrail.

- **CLI decomposition**: `cli.py` 1648 → 106 LOC; commands split into `commands/pipeline.py`, `commands/library/`, `commands/config.py`, `commands/info.py`
- **Indexer CLI decomposition**: `indexer/cli.py` 1389 → 30 LOC; commands split into `indexer/commands/scan.py`, `query.py`, `repair.py`, `diagnose.py`
- **Scanner modes split**: `_modes.py` 1900 → `_modes/` package (full, quick, incremental, enrich, verify, backfill — each ≤ 700 LOC)
- **Scraper decomposition**: `scraper.py` 2159 → orchestrator (267 LOC) + 5 services (movie, tv, rename, existing_validator, classifier)
- **Config models split**: `conf/models.py` 1451 → `conf/models/` package (config, categories, disks, paths, staging, scraper, trailers, indexer, fuzzy, preferences)
- **Dispatch decomposition**: `dispatcher.py` 797 → `_movie.py`, `_tv.py`, `_transfer.py`, `_types.py`
- **PipelineStep Protocol**: declared in `pipeline_protocol.py`; all 9 steps adapted; `DEFAULT_STEPS` registry in `pipeline_steps.py`
- **StepReport Tier A**: typed `*Details` dataclasses for all 9 steps in `reports/`; `STEP_REPORT_CONTRACT` registry
- **Complexity guardrail**: `scripts/check-module-size.py` wired into `make check` (advisory in 0.9.0, hard block in 0.10.0)
- **Module size ceiling**: soft warning at 800 LOC, hard ceiling 1000 LOC
- Design doc: `docs/features/arch-cleanup/DESIGN.md`
