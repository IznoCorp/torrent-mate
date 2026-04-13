# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a **media triage staging area** ("A TRIER" = "to sort"). Downloaded media files land here, get renamed, cleaned of junk files/folders, scraped for metadata (via TMDB/TVDB APIs, with MediaElch as manual fallback), then moved to permanent storage on one of 4 disks.

## Package

Package name: `personalscraper`. CLI entry point: `personalscraper <command>`.
V0-V10 implemented (ingest, sort, scrape, verify, dispatch, pipeline run + notifications, E2E tests, test audit, robustness, pipeline integrity, resilience).

## Commit Convention

- Format: `vX.Y.Z: Description` (X=version, Y=phase, Z=sub-phase)
- NEVER include `Co-Authored-By`, Claude, Anthropic, or AI references in commits
- A PreToolUse hook (`block_ai_attribution.py`) enforces this — commit will be blocked

## Pipeline Monitoring Rules

When running `personalscraper run` or any long-running command with user observation:

1. **NEVER run in background** — foreground only, timeout=600000. A hook (`block_background_pipeline.py`) enforces this.
2. **Create TODO tasks BEFORE launching** — categories: bugs, incohérences, améliorations. Update in real-time.
3. **Show output after each step** — read and display incrementally, don't wait for the end.
4. **Kill on 2 identical consecutive errors** — systemic failure = STOP immediately, don't keep trying.
5. **State limitations upfront** — if you can't guarantee something, say so BEFORE agreeing.
6. **After kill: check filesystem** — orphans, lock files, temp dirs. Clean or report what can't be cleaned.

Alternative: run steps individually (`personalscraper ingest`, then `personalscraper sort`, etc.) to maintain control between steps. Use `-v` only for debugging a specific step (generates 100x more output).

## Code Conventions

- **Google-style docstrings** mandatory on all modules, classes, functions, and methods
- Docstrings include: description, `Args:`, `Returns:`, `Raises:` (as applicable)
- **Inline comments** for non-trivial logic explaining the "why" (not the "what")
- Docstring/comment language: **English**

## Implementation Workflow

ALL planning (brainstorming → design → plan) must be complete for ALL versions before ANY code is written.
Use `/model-version` for planning, `/implement-version` to start coding (blocks if planning incomplete).
Coherence check between every phase — verify interfaces match design before continuing.

### Per sub-phase discipline

- **Commit** after every sub-phase (`vX.Y.Z: Description`)
- **Update progress** (IMPLEMENTATION.md + plan/INDEX.md) after every sub-phase — never batch
- **Check context** after every sub-phase — if ≥80% full, compact before continuing

### Continuous flow

- **Never ask for confirmation** to continue between sub-phases, phases, or versions
- **Always continue automatically** — phase done → next phase, version done → next version
- **Only stop** if: a blocking error requires a user decision, or context needs compaction
- Do NOT ask "On continue ?", "Shall I proceed?", or present options to continue — just do it

## Commands

```bash
# PersonalScraper CLI (V0+)
personalscraper ingest              # Ingest completed torrents from qBittorrent
personalscraper ingest --dry-run    # Preview without moving
personalscraper sort                # Sort media files into category folders (V2)
personalscraper scrape              # Scrape metadata from TMDB/TVDB (V3)
personalscraper verify              # Quality check before dispatch (V4)
personalscraper dispatch            # Move to storage disks (V5)
personalscraper process             # Reclean + dedup + scrape + cleanup (V9)
personalscraper run                 # Full pipeline (V6+V9)
personalscraper run --dry-run       # Preview full pipeline

# Alias
media-ingest                        # → personalscraper ingest

# Sort new downloads into category folders (legacy, replaced by `personalscraper sort` in V2)
torrent-sort
torrent-sort --dry-run

# Check disk space (for choosing target disk)
df -h /Volumes/Disk{1,2,3,4}

# Scheduling (launchd)
# Install: cp com.personalscraper.pipeline.plist ~/Library/LaunchAgents/
# Load:    launchctl load ~/Library/LaunchAgents/com.personalscraper.pipeline.plist
# Unload:  launchctl unload ~/Library/LaunchAgents/com.personalscraper.pipeline.plist
# Manual:  launchctl start com.personalscraper.pipeline
# Status:  launchctl list | grep personalscraper
```

## Workflow Pipeline

1. **Torrent download** — completed torrents land in `/Volumes/IznoServer SSD/torrents/complete`
2. **Initial sort (`torrent-sort`)** — files are deposited at the root of `A TRIER/`, then `torrent-sort` dispatches them into the correct subdirectories (001-MOVIES, 002-TVSHOWS, 004-AUDIO, etc.) based on file type detection
3. **Rename & clean** — strip release-group tags, codec info, resolution labels from filenames
4. **Scrape metadata** (`personalscraper scrape`) — automated via TMDB/TVDB APIs (V3), produces `.nfo` files and artwork. MediaElch can still be used manually as fallback.
5. **Move to storage** — files go to one of the 4 destination disks

### Automated pipeline (`personalscraper run`)

The full automated pipeline (V9+V10) executes 7 steps sequentially with idempotence (safe to re-run):

```
INGEST → SORT → [gate: 097-TEMP empty] → CLEAN (reclean+dedup) → SCRAPE → CLEANUP → VERIFY → DISPATCH
```

- Steps 1-2 (ingest, sort) are critical — a crash aborts the pipeline
- Steps 3-5 (clean, scrape, cleanup) run with individual error isolation
- Step 6 (verify) produces a dispatchable list; step 7 (dispatch) is skipped if verify fails

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

All 4 disks are **NTFS** formatted, mounted via **macFUSE** (ntfstool driver) over USB.

| Disk  | Mount                 | Filesystem | Categories                                                                                                                                    |
| ----- | --------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Disk1 | /Volumes/Disk1/medias | NTFS       | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk2 | /Volumes/Disk2/medias | NTFS       | series, series animes                                                                                                                         |
| Disk3 | /Volumes/Disk3/medias | NTFS       | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk4 | /Volumes/Disk4/medias | NTFS       | films, films animations, series, series animations, series documentaires, emissions                                                           |

### NTFS via macFUSE constraints

- **No Unix permissions** — `chmod`, `chown`, `chgrp` are no-ops or fail with EPERM. All files appear as `rwxrwxrwx` owned by the mounting user.
- **rsync must use `--no-perms --no-owner --no-group`** — `rsync -a` (which includes `-pgo`) fails with `Operation not permitted` on set times/permissions. The dispatcher uses `-a --no-perms --no-owner --no-group` to work around this.
- **Mount flags**: `macfuse, local, synchronous, noatime, nobrowse` — `synchronous` means every write is committed immediately (slower but safer for USB).
- **`_force_rmtree` limitation** — `os.chmod()` before retry has no effect on NTFS. Deletion failures on `.actors/` or `.DS_Store` are NTFS metadata issues, not permission issues.

## Move Rules

- **Movies** (films, animations, documentaires, spectacles, theatre): if a folder with the same name already exists on a disk, **replace it** with the new version from A TRIER.
- **TV Shows** (series, animations, documentaires): if a folder already exists, **merge** new episode files into it, replacing any that already exist.
- **New media** (no existing folder on any disk): move to the **disk with the most free space**.

## Pipeline Automation

All versions (V0–V10) are implemented. Documentation and plans live in `docs/`:

- `docs/IMPLEMENTATION.md` — Master tracker with progress and links
- `docs/v0-project-setup/` through `docs/v10-pipeline-resilience/` — Per-version brainstorming, design, and phased plans
- Workflow: brainstorming → design → plan (INDEX + phases) → implementation (commit per sub-phase)

### Pipeline Versions

| Version | Name                | Role                                                              | Phases |
| ------- | ------------------- | ----------------------------------------------------------------- | ------ |
| V0      | PROJECT SETUP       | pyproject.toml, CLI Typer, pydantic-settings, logger              | 4      |
| V1      | INGEST              | qBittorrent → A TRIER/ (copy if seeding, move if done)            | 5      |
| V2      | SORT+CLEAN          | guessit parsing + FileMate strategies → 001-MOVIES/, 002-TVSHOWS/ | 4      |
| V3      | SCRAPE              | TMDB/TVDB matching, NFO XML, artwork, episode rename              | 13     |
| V4      | VERIFY              | Quality gate: checker + fixer + genre categorization              | 4      |
| V5      | DISPATCH            | Move to Disk1-4 (replace movies, merge series)                    | 3      |
| V6      | LOG+NOTIFY          | JSON logging, Telegram notifications, launchd scheduling          | 3      |
| V7      | E2E TESTS           | Real torrent tests with safe cleanup markers                      | 5      |
| V7.x    | TEST AUDIT          | Golden files E2E, test reinforcement, coverage 79%→82%+           | 4      |
| V8      | ROBUSTNESS          | Circuit breaker, fuzzy guards, dispatch rollback, disk fallback   | 5      |
| V9      | PIPELINE INTEGRITY  | Sequential 7-step pipeline, reclean+dedup, verify reinforced      | 5      |
| V10     | PIPELINE RESILIENCE | Idempotence, fast-skip, NFO validation, crash recovery, tests     | 5      |

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
├── personalscraper/     # Python package
│   ├── ingest/          # V1: qBittorrent → staging
│   ├── sorter/          # V2: guessit + strategies → category folders
│   ├── scraper/         # V3: TMDB/TVDB matching, NFO, artwork, episodes + V8 circuit breaker
│   ├── process/         # V9: reclean, dedup, cleanup (between sort and scrape)
│   ├── verify/          # V4+V9: quality gate, fixer, genre categorization, reinforced checks
│   ├── dispatch/        # V5: disk scanner, media index, rsync transfer + V8 rollback/fallback
│   ├── pipeline.py      # V9: Sequential 7-step pipeline orchestrator
│   ├── cli.py           # Typer CLI entry point
│   ├── config.py        # pydantic-settings
│   ├── lock.py          # PID-based pipeline lock (configurable data_dir)
│   ├── logger.py        # structlog dual output (console + JSON)
│   ├── models.py        # StepReport, SortResult, PipelineReport
│   ├── text_utils.py    # media_processor, fuzzy_match_score (shared V2/V3/V5)
│   ├── naming_patterns.py # NamingPatterns dataclass (shared V3/V4/V5)
│   ├── notifier.py      # V6: Telegram notifications
│   └── genre_mapper.py  # Genre → category mapping (V4+V5)
├── tests/               # pytest tests (unit + E2E)
│   ├── e2e/             # Real torrent E2E (pytest -m e2e_torrent)
│   ├── ingest/          # V1 unit tests
│   ├── sorter/          # V2 unit tests
│   ├── scraper/         # V3 unit tests
│   ├── process/         # V9 unit tests (reclean, dedup, cleanup, run)
│   ├── verify/          # V4 unit tests
│   └── dispatch/        # V5 unit tests
├── assets/torrents/     # .torrent files for E2E tests (Jumanji, Malcolm)
│   └── expected/        # V7.x: Golden files (expected results per torrent)
├── docs/                # Planning docs per version
│   ├── v0-project-setup/ through v7-e2e-tests/  # V0-V7 (completed)
│   ├── v7x-test-audit/  # V7.x: Test audit + golden files (implemented)
│   ├── v8-robustness/   # V8: Robustness improvements (implemented)
│   ├── v9-pipeline-integrity/  # V9: Pipeline integrity (implemented)
│   └── v10-pipeline-resilience/ # V10: Idempotence + crash recovery (implemented)
├── 099-SCRIPTS/         # Legacy scripts (.bak files, gitignored)
├── pyproject.toml       # Project config (PEP 621)
├── Makefile             # make test/lint/format/install-dev
├── MANUAL.md            # User manual (French) — shell commands, disk layout, naming
├── .env.example         # Config template
├── com.personalscraper.pipeline.plist  # launchd daily agent (3am)
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

## Testing

```bash
# Unit tests (~6s)
make test                           # or: python -m pytest -v
python -m pytest tests/ -x -q       # stop on first failure

# E2E tests (real torrents — manual only, requires qBittorrent running)
python -m pytest -m e2e_torrent -v -s   # 3 pipeline tests (movie, tvshow, mixed CLI)

# Roundtrip E2E tests (scrape accuracy — requires TMDB/TVDB API keys)
python -m pytest -m roundtrip -v -s     # 2 tests (movie + tvshow roundtrip matching)

# Lint + format
make lint                           # ruff check
make format                         # ruff format + fix
```

E2E tests use `.torrent` files from `assets/torrents/`. Dispatch always runs in dry-run mode — storage disks are never modified. All staging artifacts and qBit test torrents are cleaned up after each test.

Golden files in `assets/torrents/expected/` add exact validation on top of smoke tests — NFO invariants, artwork existence, directory structure, and dispatch expectations. E2E tests auto-match torrents to golden files via fuzzy matching; if no golden file exists, only smoke tests run.

## Language

The user communicates in **French**. Code comments are a mix of French and English. Respond in French when the user writes in French.

## Important Notes

- FileMate's directory name mappings (001-MOVIES, 002-TVSHOWS, etc.) are defined in `~/dev/FileMate/.env` — update there if folder naming changes.
- Paths contain spaces (`/Volumes/IznoServer SSD/A TRIER/`) — always quote paths in shell commands.
- Legacy scripts (099-SCRIPTS/) exist on disk but are gitignored. Contains 7 `.bak` Python scripts and a `plex/` subfolder. All replaced by PersonalScraper V0-V7.
- MediaElch is the external metadata scraper — Claude does not interact with it directly.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails, use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`
- ffprobe returns ISO 639-2/B language codes (`fre`), Kodi NFO expects 639-2/T (`fra`) — always convert via `ISO_639_2_B_TO_T` mapping in `mediainfo.py` (20 codes differ)
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
- `sanitize_filename()` lives in `personalscraper/text_utils.py` (shared) — strips `<>:"/\|?*` and normalizes U+00A0→space. Applied in `NamingPatterns.format()` (all artwork/NFO filenames) and in scraper `clean_name` (folder renames). TMDB titles often contain `:` (e.g. "Spirale : L'Héritage de Saw") and non-breaking spaces (French typography convention before `:`).
- `SortResult`, `StepReport`, and `PipelineReport` are defined in `personalscraper/models.py` (V0+V6) — each `run_*()` converts internal results to `StepReport` before returning
- TV show folders: V2 creates `Show Name/` (no year), V3 renames to `Show Name (Year)/` after API matching — V3 handles idempotent rename
- Disk space threshold: `free_space_gb >= max(min_free_gb, item_size_gb * 1.5)` — unified formula across V5
- Video extensions handled: `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.mpg`, `.mpeg`, `.m4v`, `.webm`, `.ts`, `.m2ts`, `.mts`, `.3gp`, `.vob`, `.ogv`, `.rmvb`
- Circuit breaker sits ABOVE tenacity: tenacity retries transient errors (429, single timeout), circuit breaker detects sustained outages (5 consecutive 5xx/timeout/connection → OPEN for 5 min). Only counts 5xx/timeout/connection — NOT 429 (tenacity) or 4xx (client errors)
- Circuit breaker `guard()` method centralizes the check-then-raise pattern — clients call `self._circuit.guard()` instead of manually checking `can_proceed()` + constructing `CircuitOpenError`
- `fuzzy_match_score()` in `text_utils.py` provides 3 anti-false-positive guards for fuzzy matching: year (±1), length ratio (≥0.67), adaptive threshold (≤10 chars → 95%, >10 → 90%). Used by V2 matcher and V5 media_index
- Dispatch rsync uses `-a --no-perms --no-owner --no-group` — NTFS via macFUSE does not support Unix permissions, plain `-a` (which includes `-pgo`) fails with EPERM on all 4 disks
- Dispatch `_move_new()` uses staging→commit: rsync to `_tmp_dispatch_{name}`, then atomic `os.rename`. Crash leaves only tmp dir (cleaned on next run)
- Dispatch `_merge()` uses rsync `--backup --backup-dir=.merge_backup/` for rollback. On failure, `_restore_merge_backup()` restores per-file (continues on individual errors)
- Dispatch standalone (`personalscraper dispatch`) auto-runs verify first to get the dispatchable item list — there is no separate staging_dir scan mode
- `choose_disk(allow_create_category=True)` for new items: falls back to any disk with space if no disk has the category. Logs WARNING for overflow (category not in disk config)
- E2E timeout: `ceil(GB) × 3 min, minimum 10 min` — prevents tests from hanging on stalled torrents
- rapidfuzz `default_process` does NOT strip accents — use `media_processor` from `personalscraper/text_utils.py` with NFD decomposition for French titles
- rapidfuzz v3.0+ has NO automatic preprocessing — always pass `processor=media_processor` or scores will be wrong
- rapidfuzz `WRatio` is the recommended scorer for media titles (balances exact match with tolerance for extra tokens)
- tenacity `@retry` without args retries FOREVER with NO delay — always specify `stop` and `wait`
- tenacity `reraise=True` recommended — otherwise exceptions are wrapped in `RetryError`
- structlog `ProcessorFormatter.wrap_for_formatter` MUST be the last structlog processor — JSONRenderer goes in ProcessorFormatter, not in structlog.configure
- structlog `cache_logger_on_first_use=True` makes configure() calls after first log silently ignored — configure early
- rich `Console(quiet=True)` suppresses all output natively — no need for `if not quiet:` checks
- rich markup in log messages: keep `markup=False` on RichHandler to avoid `[brackets]` being interpreted as tags
- Verify `nfo_ids` check requires at least one of TMDB or IMDB (not both). Missing one is WARNING, missing both is ERROR. Some recent films (e.g. "Libre antenne") have TMDB but no IMDB yet.
- `_is_nfo_complete()` in `scraper.py` validates NFO has parsable XML + at least one `<uniqueid>` with non-empty text — used for fast-skip and corrupt NFO detection
- Scrape fast-skip: `_all_nfos_valid()` checks all movie/show dirs before starting — if all have valid NFOs, the entire scrape step is skipped
- Artwork recovery: if NFO is valid but artwork is missing, scraper extracts TMDB ID from the NFO and re-downloads artwork without re-scraping
- Clean fast-skip: `_has_polluted_folders()` scans category dirs — if no polluted names found, skip reclean+dedup entirely
- All 7 pipeline steps are idempotent: re-running the pipeline produces no changes if everything is already processed
