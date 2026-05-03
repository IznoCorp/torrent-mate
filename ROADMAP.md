# ROADMAP — PersonalScraper

> Future ideas. Each item gets its own brainstorming session before implementation.

## Future Ideas

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

### YoutubeTrailerScraper Integration ✅ (completed — v0.5.0)

Trailer scraping is integrated into the pipeline as step 8 (trailers).

- yt-dlp based download with configurable format selectors
- State tracking per media item (pending/downloaded/skipped)
- CLI: `personalscraper trailers scan|download|verify|purge`
- Pipeline integration: `personalscraper run` (trailers step, skippable via `--skip-trailers`)
- Archived feature docs: `docs/archive/features/trailer/`

### Config System Overhaul ✅ (completed — v0.9.0)

Config is now a directory of JSON5 files with overlay merge.

- Split layout: `config.json5` (master + overlays) + per-topic files (paths, disks, categories, patterns, encoding, scraper, trailers, indexer, thresholds)
- `personalscraper init-config` creates `config/` from `config.example/` template
- Optional `local.json5` for machine-specific overrides with last-wins semantics
- All paths, staging layout, thresholds, and preferences live in `config/` — `.env` is credentials only

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

### Library Indexer ✅ (completed — v0.7.0+)

SQLite-based media index with scanner, query engine, and drift reconciliation.

- SQLite database at `config/indexer.db_path` (default `.data/library.db`)
- Scanner modes: `quick`, `incremental`, `enrich`, `full`, `verify` + `backfill`
- CLI: `personalscraper library-index|library-search|library-verify|library-repair|library-reconcile`
- Outbox writethrough for dispatch, trailer state tracking, repair queue
- Launchd agents for nightly quick scan + periodic enrich
- Replaced ad-hoc `library_scan.json` / `library_analysis.json` files
- Archived feature docs: `docs/archive/features/media-indexer/`
