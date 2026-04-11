# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a **media triage staging area** ("A TRIER" = "to sort"). Downloaded media files land here, get renamed, cleaned of junk files/folders, scraped for metadata (using MediaElch), then moved to permanent storage on one of 4 disks.

## Package

Package name: `personalscraper`. CLI entry point: `personalscraper <command>`.
Will replace `torrent-sort` and `099-SCRIPTS/` after V0 implementation.

## Commit Convention

- Format: `vX.Y.Z: Description` (X=version, Y=phase, Z=sub-phase)
- NEVER include `Co-Authored-By`, Claude, Anthropic, or AI references in commits
- A PreToolUse hook (`block_ai_attribution.py`) enforces this — commit will be blocked

## Code Conventions

- **Google-style docstrings** mandatory on all modules, classes, functions, and methods
- Docstrings include: description, `Args:`, `Returns:`, `Raises:` (as applicable)
- **Inline comments** for non-trivial logic explaining the "why" (not the "what")
- Docstring/comment language: **English**

## Implementation Workflow

ALL planning (brainstorming → design → plan) must be complete for ALL versions before ANY code is written.
Use `/model-version` for planning, `/implement-version` to start coding (blocks if planning incomplete).
Coherence check between every phase — verify interfaces match design before continuing.

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
| V0      | PROJECT SETUP | pyproject.toml, CLI Typer, pydantic-settings, logger              | 4      |
| V1      | INGEST        | qBittorrent → A TRIER/ (copy if seeding, move if done)            | 5      |
| V2      | SORT+CLEAN    | guessit parsing + FileMate strategies → 001-MOVIES/, 002-TVSHOWS/ | 4      |
| V3      | SCRAPE        | TMDB/TVDB matching, NFO XML, artwork, episode rename              | 13     |
| V4      | VERIFY        | Quality gate: checker + fixer + genre categorization              | 4      |
| V5      | DISPATCH      | Move to Disk1-4 (replace movies, merge series)                    | 3      |
| V6      | LOG+NOTIFY    | JSON logging, Telegram notifications, launchd scheduling          | 3      |
| V7      | E2E TESTS     | Real torrent tests with safe cleanup markers                      | 5      |

### Reference Documentation

- `docs/qbittorrent-api-reference.md` — V1: TorrentState enum, exceptions, patterns pipeline
- `docs/guessit-evaluation.md` — V2: parsing noms media, tests réels, comparaison regex
- `docs/ffprobe-reference.md` — V3: extraction streamdetails, mapping codec/langue Kodi
- `docs/TMDB-API.md` — V3: référence API TMDB v3 vérifiée par tests live
- `docs/TVDB-API.md` — V3: référence API TVDB v4 vérifiée par tests live
- `docs/rapidfuzz-reference.md` — V3: fuzzy matching titres, scorers, media_processor custom
- `docs/tenacity-reference.md` — V3: retry API calls, backoff, rate limits TMDB/TVDB
- `docs/rich-reference.md` — V0: CLI output, progress bars, tables, theming
- `docs/structlog-reference.md` — V6: logging JSON structuré, context binding, switch dev/prod

### Key Dependencies (chosen after evaluation)

- `typer` — V0 CLI (wraps Click, type hints = spec CLI, rich native, same CliRunner for tests)
- `qbittorrent-api` — V1 wrapper qBit (prefer over raw requests — handles auth/CSRF/v5 compat)
- `guessit` — V2 filename parsing (prefer over custom regex — 140+ services, edge cases)
- `ffprobe` (subprocess) — V3 streamdetails (prefer over pymediainfo — already installed, zero dep)
- `rsync` (subprocess) — V5 cross-filesystem transfers (prefer over shutil — resume, checksum, crash-safe)
- `pydantic-settings` — V0 config (rewritten from scratch, NOT copied from TorrentMaker)
- `rapidfuzz` — V2+V3+V5 fuzzy matching (MIT license, C++ 5-100x faster than thefuzz, unified across all versions)
- `tenacity` — V3 API retry (exponential backoff, wait_exception for Retry-After, composable strategies)
- `rich` — V0 CLI output (progress bars, tables, theming, auto TTY detection, pulled by Typer)
- `structlog` — V6 structured logging (replaces custom JsonFormatter, context binding, dev/prod auto-switch)

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
├── personalscraper/     # Python package (V0+)
├── tests/               # pytest tests
├── pyproject.toml       # Project config (PEP 621)
├── Makefile             # make test/lint/format/install-dev
├── .env.example         # Config template
└── logs/                # Structured JSON logs (gitignored)
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

### 099-SCRIPTS/ — archived (V0 phase 4)

Legacy scripts archived to `~/dev/099-SCRIPTS-archive/` and removed from repo.
Useful patterns were extracted into V1-V3 designs.

## Language

The user communicates in **French**. Code comments are a mix of French and English. Respond in French when the user writes in French.

## Important Notes

- FileMate's directory name mappings (001-MOVIES, 002-TVSHOWS, etc.) are defined in `~/dev/FileMate/.env` — update there if folder naming changes.
- Paths contain spaces (`/Volumes/IznoServer SSD/A TRIER/`) — always quote paths in shell commands.
- Legacy scripts (099-SCRIPTS/) archived to `~/dev/099-SCRIPTS-archive/` — no longer in repo.
- MediaElch is the external metadata scraper — Claude does not interact with it directly.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails, use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`
- ffprobe returns ISO 639-2/B language codes (`fre`), Kodi NFO expects 639-2/T (`fra`) — always convert via `LANG_B_TO_T` mapping (20 codes differ)
- TVDB API v4 is free for personal use (< 50k$ revenue) but requires application + attribution
- TVDB API v4 has two key types: "Negotiated Contract" (free, no PIN needed) and "User Subscription" (requires PIN). Pipeline uses Negotiated Contract — login with `{"apikey": "..."}` only, no `pin` field.
- TVDB uses 3-char language codes (`fra`, `eng`), TMDB uses `fr-FR`/`en-US` — always convert between the two systems
- TMDB `year` search parameter is NOT a strict filter — it boosts relevance but returns other years too. Always validate client-side.
- TMDB images: ALWAYS use `include_image_language=fr,en,null` — without it, 5x-31x fewer images are returned (backdrops especially)
- TVDB artwork has no "landscape" type — use "Background" (type 3 for series, 15 for movies, 1920×1080)
- TVDB source type IDs for TMDB cross-ref: 10=movies, 12=TV series, 15=people, 28=collections — use the right one
- Never include API keys in documentation or brainstorming files — use `.env` references only
- When inserting a new version between existing ones, update ALL references: H1 titles, commit prefixes (`vX.Y.Z:`), cross-version refs, sub-phase numbering, data flow diagrams
- `git filter-repo` works on this repo but `.git/config` is read-only (macOS permissions) — remote removal error is cosmetic, re-add remote after if needed
- Genre mapper lives in `personalscraper/genre_mapper.py` (package root) and is imported by V4-verify and V5-dispatch — single source of truth for genre→category mapping
- `media_processor()` lives in `personalscraper/text_utils.py` (shared) — imported by V2 matcher, V3 confidence, V5 media_index. NFD accent stripping for French titles.
- `SortResult` and `StepReport` are defined in `personalscraper/models.py` (V0) — each `run_*()` converts internal results to `StepReport` before returning
- TV show folders: V2 creates `Show Name/` (no year), V3 renames to `Show Name (Year)/` after API matching — V3 handles idempotent rename
- Disk space threshold: `free_space_gb >= max(min_free_gb, item_size_gb * 1.5)` — unified formula across V5
- Video extensions handled: `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.mpg`, `.mpeg`, `.m4v`, `.webm`, `.ts`
- rapidfuzz `default_process` does NOT strip accents — use `media_processor` from `personalscraper/text_utils.py` with NFD decomposition for French titles
- rapidfuzz v3.0+ has NO automatic preprocessing — always pass `processor=media_processor` or scores will be wrong
- rapidfuzz `WRatio` is the recommended scorer for media titles (balances exact match with tolerance for extra tokens)
- tenacity `@retry` without args retries FOREVER with NO delay — always specify `stop` and `wait`
- tenacity `reraise=True` recommended — otherwise exceptions are wrapped in `RetryError`
- structlog `ProcessorFormatter.wrap_for_formatter` MUST be the last structlog processor — JSONRenderer goes in ProcessorFormatter, not in structlog.configure
- structlog `cache_logger_on_first_use=True` makes configure() calls after first log silently ignored — configure early
- rich `Console(quiet=True)` suppresses all output natively — no need for `if not quiet:` checks
- rich markup in log messages: keep `markup=False` on RichHandler to avoid `[brackets]` being interpreted as tags
