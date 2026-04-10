# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a **media triage staging area** ("A TRIER" = "to sort"). Downloaded media files land here, get renamed, cleaned of junk files/folders, scraped for metadata (using MediaElch), then moved to permanent storage on one of 4 disks.

## Commands

```bash
# Sort new downloads into category folders
torrent-sort
torrent-sort --dry-run          # Preview without moving
torrent-sort --verbose --clean  # Sort + delete leftovers

# Clean empty media folders across all disks
python3 099-SCRIPTS/plex/cleanFileSystem.py --dry-run
python3 099-SCRIPTS/plex/cleanFileSystem.py

# Check disk space (for choosing target disk)
df -h /Volumes/Disk{1,2,3,4}
```

## Workflow Pipeline

1. **Torrent download** — completed torrents land in `/Volumes/IznoServer SSD/torrents/complete`
2. **Initial sort (`torrent-sort`)** — files are deposited at the root of `A TRIER/`, then `torrent-sort` dispatches them into the correct subdirectories (001-MOVIES, 002-TVSHOWS, 004-AUDIO, etc.) based on file type detection
3. **Rename & clean** — strip release-group tags, codec info, resolution labels from filenames
4. **Scrape metadata** — done via MediaElch (external GUI app), produces `.nfo` files and artwork (poster, fanart, banner, clearlogo, etc.)
5. **Move to storage** — files go to one of the 4 destination disks

### torrent-sort command

Shell alias:

```bash
torrent-sort
# Resolves to: python ~/dev/FileMate/main.py "/Volumes/IznoServer SSD/A TRIER" --verbose --sort
```

Runs **FileMate** (`~/dev/FileMate/`) — detects file types and moves them into the matching numbered folder.
Directory name mappings are configured in `~/dev/FileMate/.env`.
Supports `--dry-run` and `--clean` (delete leftovers after sorting) flags.

## Storage Disks

| Disk  | Mount                 | Categories                                                                                                                                    |
| ----- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Disk1 | /Volumes/Disk1/medias | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk2 | /Volumes/Disk2/medias | series, series animes                                                                                                                         |
| Disk3 | /Volumes/Disk3/medias | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk4 | /Volumes/Disk4/medias | films, films animations, series, series animations, series documentaires, emissions                                                           |

## Move Rules

- **Movies** (films, animations, documentaires, spectacles, theatre): if a folder with the same name already exists on a disk, **replace it** with the new version from A TRIER.
- **TV Shows** (series, animations, documentaires): if a folder already exists, **merge** new episode files into it, replacing any that already exist.
- **New media** (no existing folder on any disk): move to the **disk with the most free space**.

## Pipeline Automation (in progress)

Documentation and implementation plans live in `docs/`:

- `docs/IMPLEMENTATION.md` — Master tracker with progress and links
- `docs/v0-project-setup/` through `docs/v7-e2e-tests/` — Per-version brainstorming, design, and phased plans
- Workflow: brainstorming → design → plan (INDEX + phases) → implementation (commit per sub-phase)

### Pipeline Versions

| Version | Name          | Role                                                              | Phases |
| ------- | ------------- | ----------------------------------------------------------------- | ------ |
| V0      | PROJECT SETUP | pyproject.toml, CLI Click, pydantic-settings, logger              | 4      |
| V1      | INGEST        | qBittorrent → A TRIER/ (copy if seeding, move if done)            | 5      |
| V2      | SORT+CLEAN    | guessit parsing + FileMate strategies → 001-MOVIES/, 002-TVSHOWS/ | 4      |
| V3      | SCRAPE        | TMDB/TVDB matching, NFO XML, artwork, episode rename              | 13     |
| V4      | VERIFY        | Quality gate: checker + fixer + genre categorization              | 4      |
| V5      | DISPATCH      | Move to Disk1-4 (replace movies, merge series)                    | 3      |
| V6      | LOG+NOTIFY    | JSON logging, Telegram notifications, cron setup                  | 3      |
| V7      | E2E TESTS     | Real torrent tests with safe cleanup markers                      | 5      |

### Reference Documentation

- `docs/qbittorrent-api-reference.md` — V1: TorrentState enum, exceptions, patterns pipeline
- `docs/guessit-evaluation.md` — V2: parsing noms media, tests réels, comparaison regex
- `docs/ffprobe-reference.md` — V3: extraction streamdetails, mapping codec/langue Kodi
- `docs/TMDB-API.md` — V3: référence API TMDB v3 vérifiée par tests live
- `docs/TVDB-API.md` — V3: référence API TVDB v4 vérifiée par tests live

### Key Dependencies (chosen after evaluation)

- `qbittorrent-api` — V1 wrapper qBit (prefer over raw requests — handles auth/CSRF/v5 compat)
- `guessit` — V2 filename parsing (prefer over custom regex — 140+ services, edge cases)
- `ffprobe` (subprocess) — V3 streamdetails (prefer over pymediainfo — already installed, zero dep)
- `pydantic-settings` — V0 config (rewritten from scratch, NOT copied from TorrentMaker)

## Directory Structure

```
A TRIER/
├── 001-MOVIES/          # Films awaiting processing (one folder per movie with .mkv + artwork + .nfo)
├── 002-TVSHOWS/         # TV series awaiting processing (folder per show, Saison XX subfolders)
├── 003-EBOOKS/          # Ebooks staging (currently empty)
├── 004-AUDIO/           # Audiobooks staging
├── 005-APPS/            # Applications staging (currently empty)
├── 006-ANDROID/         # Android apps staging (currently empty)
├── 097-TEMP/            # Temporary workspace
├── 098-AUTRES/          # Miscellaneous
└── 099-SCRIPTS/         # Utility scripts (Python)
    ├── PackUnpack.py    # Flatten nested folders + clean filenames (unpack/pack)
    ├── Unpack.py        # Unpack-only variant
    ├── TVDBNameToNum.py # Interactive TVDB episode matcher/renamer (CLI, uses tvdb_api v3)
    ├── EpisodesTVDBNamer.py
    ├── videoCutter.py / videoMerger.py
    ├── SensCritiqueScrapper.py
    └── plex/            # Plex-oriented maintenance scripts
        ├── cleanFileSystem.py   # Remove empty media folders across all disks
        ├── trailerScraper.py    # Auto-download trailers from YouTube
        ├── fileSystem.py        # Shared filesystem utilities (getSubFolders, getEmptyFolders, etc.)
        ├── decorators.py        # @timeit and @cacheit decorators (file-based cache)
        ├── youtubeScraper.py    # YouTube search & download wrapper
        ├── senscritique.py      # SensCritique scraper
        └── contents.json        # Cached media index
```

## Naming Conventions

### Movie folders

```
Title (Year)/
  Title.mkv
  Title.nfo
  Title-poster.jpg
  Title-fanart.jpg
  Title-banner.jpg
  Title-clearlogo.png
  Title-clearart.png
  Title-discart.png
  Title-landscape.jpg
  .actors/           # Actor thumbnail images
```

### TV Show folders

```
Show Name (Year)/
  tvshow.nfo
  poster.jpg, fanart.jpg, banner.jpg, clearlogo.png, etc.
  season01-poster.jpg
  .actors/
  Saison 01/
    S01E01 - Episode Title.mkv
    S01E01 - Episode Title.nfo
    S01E01 - Episode Title-thumb.jpg
  Saison 02/
    ...
```

Season folders use French naming: `Saison 01`, `Saison 02`, etc.
Episode files follow the pattern: `S{nn}E{nn} - {Episode Title}.{ext}`

## Scripts

### torrent-sort (FileMate) — current

Primary sorting tool. See [torrent-sort command](#torrent-sort-command) above.

### 099-SCRIPTS/ — legacy, will be archived by V0 phase 4

Contains legacy Python scripts (PackUnpack, TVDBNameToNum, cleanFileSystem, trailerScraper).
All are hardcoded to Windows paths or use deprecated APIs (tvdb_api v3).
Useful patterns have been extracted into the V1-V3 designs. Will be moved to `~/dev/099-SCRIPTS-archive/`.

## Language

The user communicates in **French**. Code comments are a mix of French and English. Respond in French when the user writes in French.

## Important Notes

- FileMate's directory name mappings (001-MOVIES, 002-TVSHOWS, etc.) are defined in `~/dev/FileMate/.env` — update there if folder naming changes.
- Paths contain spaces (`/Volumes/IznoServer SSD/A TRIER/`) — always quote paths in shell commands.
- Some scripts still reference Windows paths (`N:/A TRIER/`) — these are legacy and need updating for the macOS environment.
- The `plex/` scripts reference disk paths as `/Volumes/DISK1/` (uppercase) but actual mounts are `/Volumes/Disk1/` (mixed case) — be aware of case sensitivity.
- MediaElch is the external metadata scraper — Claude does not interact with it directly.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails, use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`
- ffprobe returns ISO 639-2/B language codes (`fre`), Kodi NFO expects 639-2/T (`fra`) — always convert via `LANG_B_TO_T` mapping (20 codes differ)
- TVDB API v4 is free for personal use (< 50k$ revenue) but requires application + attribution
- Never include API keys in documentation or brainstorming files — use `.env` references only
- Video extensions handled: `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.mpg`, `.mpeg`, `.m4v`, `.webm`, `.ts`
