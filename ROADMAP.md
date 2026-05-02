# ROADMAP — PersonalScraper

> Future ideas. Each item gets its own brainstorming session before implementation.

## Future Ideas

### Architectural Consolidation

Internal-quality phase: shrink god modules, formalize pipeline interfaces, retire legacy compatibility paths, realign documentation. Triggered by static analysis showing several modules >1200 LOC and an implicit contract via the catch-all `StepReport`.

- **God-module decomposition**: split `personalscraper/cli.py` (~1648 LOC), `personalscraper/scraper/scraper.py` (~2159 LOC), `personalscraper/indexer/scanner/_modes.py` (~1900 LOC), `personalscraper/indexer/cli.py` (~1389 LOC) into cohesive submodules; CLI becomes pure Typer wiring delegating to `commands/{pipeline,library,config,info,diagnose}.py`.
- **Pipeline interface formalization**: introduce a `PipelineStep` Protocol (or Command object) so step orchestration no longer depends on concrete signatures; reduce reliance on `step_overrides` for testability.
- **`StepReport` typing**: replace the catch-all model with `StepReport[TDetails]` (or a per-step report family) with documented contracts of which fields each step consumes/produces.
- **Legacy cleanup**: decide the fate of `library-scan` vs `library-index`, drop the JSON `media_index.json` path, finish v1→v2 config migration, remove deprecated flags.
- **Documentation realignment**: pipeline step count (8 vs 9), `trailers` step semantics, `verify --fix` status, current indexer usage — all surface mismatches in inline comments and `docs/reference/`.
- **Complexity guardrail**: add a soft size/complexity rule (e.g., warn at 700 LOC, block at 1000 LOC) for new modules under `indexer/`, `scraper/`, `trailers/`.

**Out of scope (this phase)**: any new pipeline feature, indexer mode, or scraper provider — pure consolidation.

**Preparation** (not yet implemented):

- Codename: `arch-cleanup`
- Design: `docs/superpowers/roadmap/arch-cleanup/specs/DESIGN.md`
- Plan: `docs/superpowers/roadmap/arch-cleanup/plan/INDEX.md`
- Implementation draft: `docs/superpowers/roadmap/arch-cleanup/IMPLEMENTATION.md.draft`
- Prepared on: 2026-05-02
- Target version bump: 0.8.0 → 0.9.0 (minor)

### Web Management UI

Web-based graphical interface to pilot and supervise the whole project from a browser.

- **Pipeline control**: start / pause / resume / kill each step (`ingest`, `sort`, `process`, `dispatch`), view live logs, step status, and per-run history
- **Configuration editor**: visual editor for `config.json5` (paths, categories, disks, thresholds, patterns) with schema validation and safe reload — no shell required
- **Maintenance dashboard**: disk usage / free space per disk, orphan files (`_tmp_ingest_*`, `_tmp_dispatch_*`), stale locks, library index health, pipeline-runs history
- **Interactive scraping**: front-end for the manual-decision points currently handled via MediaElch / CLI prompts — ambiguous TMDB/TVDB matches, multi-result picks, low-fuzzy-score arbitration, manual override of detected title/year/season
- **Future-ready**: UI shell designed to host pages for upcoming roadmap items, notably:
  - **Auto-Download System** — tracker search, format preferences, subscription list CRUD, override rules editor
  - **Watcher Service** — live watcher status, trigger history
  - **Library Indexer** — browse/search indexed media, trigger re-scan, view stale entries
  - **YoutubeTrailerScraper Integration** — missing-trailer queue, per-item scrape trigger
- **Architecture pointers** (to decide during brainstorm): FastAPI / Flask + HTMX vs. SPA (Vue/React) + REST/WebSocket; auth (local-only vs. basic auth); reverse-proxy friendly (sub-path deploy behind `iznogoudatall.xyz`)
- **Out of scope (v1)**: multi-user, remote-agent control, mobile-specific UX

### Auto-Download System

Automatic torrent download pipeline with tracker API integration.

- Define preferred format + fallback formats
- Series subscription list with cron-based new episode checks
- Search multiple trackers via their APIs with preference ordering
- Connect the library recommendation list to auto-download for library renewal
- Override rules by criteria: studio, director, franchise, title, IMDB ID

### Watcher Service

Replace cron-based pipeline trigger with a real-time watcher service.

- Service that watches either qBittorrent state or the `complete/` directory
- Triggers `personalscraper run` automatically on new downloads
- More responsive than the current 3am daily cron

### YoutubeTrailerScraper Integration

Integrate existing trailer scraping tool into the pipeline.

- Existing dev at `/opt/YoutubeTrailerScraper/`
- Scrapes missing trailers for movies and series from YouTube
- Add as optional pipeline step or standalone command

**Preparation** (not yet implemented):

- Codename: `trailer`
- Design: `docs/superpowers/roadmap/trailer/specs/DESIGN.md`
- Plan: `docs/superpowers/roadmap/trailer/plan/INDEX.md`
- Prepared on: 2026-04-23
- Target version bump: 0.4.0 → 0.5.0 (minor)

### Config System Overhaul

Migrate from flat `.env` / pydantic-settings to structured JSON config.

- Dedicated config directory (e.g. `.personalscraper/config/`)
- JSON files per topic: `encoding.json`, `audio.json`, `paths.json`, `patterns.json`, `disks.json`
- EVERYTHING configurable: directories, patterns, values, naming conventions, thresholds
- The existing `encoding_rules.json` is a prototype of this approach

### Third-Party API Consumer Unification

Unify all external API integrations behind a single client abstraction so new providers plug in without touching the rest of the codebase. Today each provider is wired ad hoc (`scraper/tmdb_client.py`, `scraper/tvdb_client.py`, `scraper/imdb_client.py`, `qbit/qbittorrent_client.py`) and shares no contract — adding a new tracker means re-inventing retry, auth, rate-limiting, and result normalisation each time.

**Goals**

- One `ApiClient` base contract per family (metadata / torrent client / tracker) with shared retry, throttle, auth-renewal, structured logging, and a typed response model.
- Provider-specific subclasses implement only the differential surface (endpoint paths, response parsing, auth flow).
- Integration test fixtures shared across providers (golden response files, replay harness).

**Activation via credentials**

- Each provider declares its credential shape in config: API key, or login/password, depending on the provider.
- A provider is **active** as soon as its credentials are supplied; absent credentials = provider disabled, no boolean toggle to maintain.

**Torrent-client selection**

- All active torrent clients (qBittorrent, Transmission) coexist in the codebase.
- A dedicated config field designates the **single** client used by the pipeline — only one can be active in the download path at a time, even when multiple are credentialed.

**Preference / priority system**

- Lower number = higher priority across all priority configurations.
- **Per-use-case provider priority**: priorities are defined per use case, not per family, so the same provider can rank differently depending on what is being fetched.
  - Movie scraping
  - Series scraping
  - Episode scraping
  - Recommendations
  - Torrent retrieval from trackers
- Preferences extracted from existing code into the new config layer (e.g. current series-scraping order: TVDB > TMDB → encoded as `series_scraping: { tvdb: 1, tmdb: 2 }`).
- **Torrent-result priority** (separate, second-stage ranking): once trackers have returned candidates, a per-criterion priority list orders them by format, encoding type, torrent size, and any additional torrent attributes the user wants to weight.

**Provider matrix**

| Family                    | Existing                            | To add                                    |
| ------------------------- | ----------------------------------- | ----------------------------------------- |
| Metadata scraping         | TMDB, TVDB, IMDB                    | SensCritique (notations, in particular)   |
| Recommendations           | —                                   | SensCritique + IMDB                       |
| Torrent client            | qBittorrent (via `qbittorrent-api`) | Transmission (via `transmission-rpc`)     |
| Tracker search + download | —                                   | LaCale, C411, torr9.net, digitalcore.club |

**Workflow once unified**

1. Recommender pulls cross-provider notations (SensCritique + IMDB) → priority list.
2. Auto-Download System feeds priority list to the tracker layer; tracker abstraction queries every enabled tracker, ranks results, picks best match.
3. Selected torrent is sent to the configured torrent-client provider (qBittorrent or Transmission).
4. Existing pipeline picks up the completed download via the watcher service.

**Depends on:** Auto-Download System (consumer of the tracker layer), Watcher Service (downstream trigger).

### Library Indexer

Persistent index of the media library with cache or database backend.

- Index all media items across 4 disks (path, title, year, codec, size, NFO IDs, etc.)
- Cache/BDD layer to avoid full disk scans on every command (library scans are read-heavy but slow on USB)
- Scheduled nightly update (cron/launchd, 1x per night)
- Auto-refresh on path error detection (desync between index and filesystem = stale entry)
- Replaces ad-hoc JSON files (`library_scan.json`, `library_analysis.json`) with a single authoritative source
- Study the companion `FileMate` tool for potential integration or shared architecture patterns

**Depends on:** Library maintenance commands (scan/analyze data model), Config System Overhaul (configurable paths)
