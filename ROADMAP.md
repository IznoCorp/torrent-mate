# ROADMAP — PersonalScraper

> Future versions and ideas. Each item gets its own brainstorming session before implementation.

## Implemented

| Version | Name                 | Summary                                                  |
| ------- | -------------------- | -------------------------------------------------------- |
| V0      | PROJECT SETUP        | pyproject.toml, CLI Typer, pydantic-settings, logger     |
| V1      | INGEST               | qBittorrent → A TRIER/ (copy if seeding, move if done)   |
| V2      | SORT+CLEAN           | guessit parsing + FileMate strategies                    |
| V3      | SCRAPE               | TMDB/TVDB matching, NFO XML, artwork, episode rename     |
| V4      | VERIFY               | Quality gate: checker + fixer + genre categorization     |
| V5      | DISPATCH             | Move to Disk1-4 (replace movies, merge series)           |
| V6      | LOG+NOTIFY           | JSON logging, Telegram notifications, launchd scheduling |
| V7      | E2E TESTS            | Real torrent tests with safe cleanup markers             |
| V7.x    | TEST AUDIT           | Golden files E2E, test reinforcement                     |
| V8      | ROBUSTNESS           | Circuit breaker, fuzzy guards, dispatch rollback         |
| V9      | PIPELINE INTEGRITY   | Sequential 8-step pipeline, reclean+dedup                |
| V10     | PIPELINE RESILIENCE  | Idempotence, fast-skip, crash recovery                   |
| V11     | CODE QUALITY         | Error isolation, CLI UX, dead code, DRY extraction       |
| V12     | PIPELINE HARDENING   | 22 bugs fixed, NTFS safety, crash recovery               |
| V13     | PIPELINE CORRECTNESS | ENFORCE step, idempotence E2E tests                      |

## In Progress

| Version | Name                | Summary                                                        |
| ------- | ------------------- | -------------------------------------------------------------- |
| V14     | LIBRARY MAINTENANCE | Scan, clean, validate, analyze existing library across 4 disks |

## Future Ideas

### Auto-Download System

Automatic torrent download pipeline with tracker API integration.

- Define preferred format + fallback formats
- Series subscription list with cron-based new episode checks
- Search multiple trackers via their APIs with preference ordering
- Connect V14 recommendation list to auto-download for library renewal
- Override rules by criteria: studio, director, franchise, title, IMDB ID

**Depends on:** V14 (recommendation list format)

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

### Config System Overhaul

Migrate from flat `.env` / pydantic-settings to structured JSON config.

- Dedicated config directory (e.g. `.personalscraper/config/`)
- JSON files per topic: `encoding.json`, `audio.json`, `paths.json`, `patterns.json`, `disks.json`
- EVERYTHING configurable: directories, patterns, values, naming conventions, thresholds
- V14's `encoding_rules.json` is a prototype of this approach

### Decouple Staging from Project

Move staging directories out of the git project root.

- Staging path fully configurable (e.g. `/Volumes/IznoServer SSD/staging/`)
- Auto-create staging directory tree on first pipeline run if missing
- Currently staging dirs (001-MOVIES, 002-TVSHOWS, etc.) live inside the repo, mixing code and data
