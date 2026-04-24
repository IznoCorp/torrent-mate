# ROADMAP — PersonalScraper

> Future ideas. Each item gets its own brainstorming session before implementation.

## Future Ideas

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
- Depends on: `ext-staging` merged to `main`

### Config System Overhaul

Migrate from flat `.env` / pydantic-settings to structured JSON config.

- Dedicated config directory (e.g. `.personalscraper/config/`)
- JSON files per topic: `encoding.json`, `audio.json`, `paths.json`, `patterns.json`, `disks.json`
- EVERYTHING configurable: directories, patterns, values, naming conventions, thresholds
- The existing `encoding_rules.json` is a prototype of this approach

### Decouple Staging from Project

Move staging directories out of the git project root.

- Staging path fully configurable (e.g. `/Volumes/IznoServer SSD/staging/`)
- Auto-create staging directory tree on first pipeline run if missing
- Currently staging dirs (001-MOVIES, 002-TVSHOWS, etc.) live inside the repo, mixing code and data

### Test Realism Refactor

Reduce over-mocking in the heaviest test suites and add lightweight E2E coverage.

- Current hotspots: `test_dispatcher.py` (~37 `@patch`), `test_cli.py` (~66 `@patch`), `test_pipeline_integration.py` (~42 `@patch`)
- Goal: cut the patch count where mocks hide real integration bugs (rsync failures, filesystem edge cases, CLI → pipeline wiring)
- Add ~15 E2E tests using `tmp_path` + small real directories, mocking only external APIs (TMDB/TVDB/qBittorrent)
- Keep runtime within CI budget (<30s for unit + E2E combined)
- Pin the invariants uncovered by mocks so future regressions in rsync flags, lock handling, and JSON state are caught
- No changes to production code required beyond exposing seams if truly needed

**Preparation** (not yet implemented):

- Codename: `test-realism`
- Design: `docs/superpowers/roadmap/test-realism/specs/DESIGN.md`
- Plan: `docs/superpowers/roadmap/test-realism/plan/INDEX.md`
- Prepared on: 2026-04-23
- Target version bump: minor

### Library Indexer

Persistent index of the media library with cache or database backend.

- Index all media items across 4 disks (path, title, year, codec, size, NFO IDs, etc.)
- Cache/BDD layer to avoid full disk scans on every command (library scans are read-heavy but slow on USB)
- Scheduled nightly update (cron/launchd, 1x per night)
- Auto-refresh on path error detection (desync between index and filesystem = stale entry)
- Replaces ad-hoc JSON files (`library_scan.json`, `library_analysis.json`) with a single authoritative source
- Study `/Users/izno/dev/FileMate` for potential integration or shared architecture patterns

**Depends on:** Library maintenance commands (scan/analyze data model), Config System Overhaul (configurable paths)
