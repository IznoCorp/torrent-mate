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

### Library Indexer

Persistent index of the media library with cache or database backend.

- Index all media items across 4 disks (path, title, year, codec, size, NFO IDs, etc.)
- Cache/BDD layer to avoid full disk scans on every command (library scans are read-heavy but slow on USB)
- Scheduled nightly update (cron/launchd, 1x per night)
- Auto-refresh on path error detection (desync between index and filesystem = stale entry)
- Replaces ad-hoc JSON files (`library_scan.json`, `library_analysis.json`) with a single authoritative source
- Study the companion `FileMate` tool for potential integration or shared architecture patterns

**Depends on:** Library maintenance commands (scan/analyze data model), Config System Overhaul (configurable paths)
