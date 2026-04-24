# Architecture Reference

Package layout, module map, shared utilities, and key dependencies.

## Package

Package name: `personalscraper`. CLI entry point: `personalscraper <command>`.

## Workflow Pipeline

1. **Torrent download** — completed torrents land in `/path/to/torrents/complete`
2. **Initial sort (`torrent-sort`)** — files are deposited at the root of `staging/`, then `torrent-sort` dispatches them into the correct subdirectories (001-MOVIES, 002-TVSHOWS, 004-AUDIO, etc.) based on file type detection
3. **Rename & clean** — strip release-group tags, codec info, resolution labels from filenames
4. **Scrape metadata** (`personalscraper scrape`) — automated via TMDB/TVDB APIs, produces `.nfo` files and artwork. MediaElch can still be used manually as fallback.
5. **Move to storage** — files go to one of the 4 destination disks

### Automated Pipeline (`personalscraper run`)

Full pipeline executes 8 steps sequentially with idempotence (safe to re-run):

```
INGEST → SORT → [gate: 097-TEMP empty] → CLEAN (reclean+dedup) → SCRAPE → CLEANUP → ENFORCE → VERIFY → DISPATCH
```

- Steps 1-2 (ingest, sort) are critical — a crash aborts the pipeline
- Steps 3-5 (clean, scrape, cleanup) run with individual error isolation
- Step 6 (enforce) sanitizes filenames, validates structure, checks cross-step coherence
- Step 7 (verify) produces a dispatchable list; step 8 (dispatch) is skipped if verify fails

## Directory Structure

```
staging/
├── 001-MOVIES/          # Films awaiting processing (one folder per movie with .mkv + artwork + .nfo)
├── 002-TVSHOWS/         # TV series awaiting processing (folder per show, Saison XX subfolders)
├── 003-EBOOKS/          # Ebooks staging (currently empty)
├── 004-AUDIO/           # Audiobooks staging
├── 005-APPS/            # Applications staging (currently empty)
├── 006-ANDROID/         # Android apps staging (currently empty)
├── 097-TEMP/            # Temporary workspace
├── 098-AUTRES/          # Miscellaneous
├── personalscraper/     # Python package
│   ├── ingest/          # qBittorrent → staging
│   ├── sorter/          # guessit + strategies → category folders
│   ├── scraper/         # TMDB/TVDB matching, NFO, artwork, episodes + circuit breaker
│   ├── process/         # reclean, dedup, cleanup (between sort and scrape)
│   ├── enforce/         # file sanitizer, structure validator, coherence checker
│   ├── library/         # scan, clean, validate, analyze, recommend, report
│   ├── verify/          # quality gate, fixer, genre categorization, reinforced checks
│   ├── dispatch/        # disk scanner, media index, rsync transfer + rollback/fallback
│   ├── pipeline.py      # sequential 8-step pipeline orchestrator
│   ├── cli.py           # Typer CLI entry point
│   ├── config.py        # pydantic-settings
│   ├── lock.py          # PID-based pipeline lock (configurable data_dir)
│   ├── logger.py        # structlog dual output (console + JSON)
│   ├── models.py        # StepReport, SortResult, PipelineReport
│   ├── text_utils.py    # media_processor, fuzzy_match_score (shared across modules)
│   ├── naming_patterns.py # NamingPatterns dataclass (shared across modules)
│   ├── notifier.py      # Telegram notifications
│   └── genre_mapper.py  # Genre → category mapping
├── tests/               # pytest tests (unit + E2E)
│   ├── e2e/             # Real torrent E2E (pytest -m e2e_torrent)
│   ├── ingest/          # ingest unit tests
│   ├── sorter/          # sorter unit tests
│   ├── scraper/         # scraper unit tests
│   ├── process/         # process unit tests (reclean, dedup, cleanup, run)
│   ├── verify/          # verify unit tests
│   ├── dispatch/        # dispatch unit tests
│   ├── enforce/         # enforce unit tests (file sanitizer, structure, coherence)
│   ├── library/         # library unit tests (scan, clean, validate, analyze, recommend, report)
│   └── resilience/      # resilience unit tests (idempotence, crash recovery)
├── assets/torrents/     # .torrent files for E2E tests (Jumanji, Malcolm)
│   └── expected/        # Golden files (expected results per torrent)
├── docs/                # Reference docs, feature plans, archive
├── 099-SCRIPTS/         # Legacy scripts (.bak files, gitignored)
├── pyproject.toml       # Project config (PEP 621)
├── Makefile             # make test/lint/format/install-dev
├── MANUAL.md            # User manual (French) — shell commands, disk layout, naming
├── .env.example         # Config template
├── com.personalscraper.pipeline.plist  # launchd daily agent (3am)
└── logs/                # Structured JSON logs (gitignored)
```

Notes:

- Legacy scripts (099-SCRIPTS/) exist on disk but are gitignored. Contains 7 `.bak` Python scripts and a `plex/` subfolder.
- MediaElch is the external metadata scraper — Claude does not interact with it directly.

## Shared Utilities (single source of truth)

- `classify()` — lives in `personalscraper/conf/classifier.py`; imported by verify and dispatch for genre/rule → category mapping (replaces the removed `genre_mapper` module).
- `media_processor()` — lives in `personalscraper/text_utils.py`; imported by sorter, scraper, and `personalscraper/dispatch/media_index.py`. NFD accent stripping for French titles.
- `sanitize_filename()` — lives in `personalscraper/text_utils.py`; strips `<>:"/\|?*` and normalizes U+00A0→space. Applied in `NamingPatterns.format()` (all artwork/NFO filenames) and in scraper `clean_name` (folder renames). TMDB titles often contain `:` (e.g. "Spirale : L'Héritage de Saw") and non-breaking spaces (French typography before `:`).
- `SortResult`, `StepReport`, `PipelineReport` — defined in `personalscraper/models.py`. Each `run_*()` converts internal results to `StepReport` before returning.
- TV show folders: sorter creates `Show Name/` (no year), scraper renames to `Show Name (Year)/` after API matching (idempotent rename).

## Key Dependencies (chosen after evaluation)

- `typer` — CLI framework (wraps Click, type hints = spec CLI, rich native, same CliRunner for tests)
- `qbittorrent-api` — qBit wrapper (prefer over raw requests — handles auth/CSRF/v5 compat)
- `guessit` — filename parsing (prefer over custom regex — 140+ services, edge cases)
- `ffprobe` (subprocess) — streamdetails extraction (prefer over pymediainfo — already installed, zero dep)
- `rsync` (subprocess) — cross-filesystem transfers (prefer over shutil — resume, checksum, crash-safe)
- `pydantic-settings` — config (rewritten from scratch, NOT copied from TorrentMaker)
- `rapidfuzz` — fuzzy matching across sorter/scraper/dispatch (MIT license, C++ 5-100x faster than thefuzz)
- `tenacity` — API retry (exponential backoff, wait_exception for Retry-After, composable strategies)
- `rich` — CLI output (progress bars, tables, theming, auto TTY detection, pulled by Typer)
- `structlog` — structured logging (replaces custom JsonFormatter, context binding, dev/prod auto-switch)

## Reference Documentation

- `docs/qbittorrent-api-reference.md` — TorrentState enum, exceptions, patterns pipeline
- `docs/guessit-evaluation.md` — parsing noms media, tests réels, comparaison regex
- `docs/ffprobe-reference.md` — extraction streamdetails, mapping codec/langue Kodi
- `docs/TMDB-API.md` — référence API TMDB v3 vérifiée par tests live
- `docs/TVDB-API.md` — référence API TVDB v4 vérifiée par tests live
- `docs/rapidfuzz-reference.md` — fuzzy matching titres, scorers, media_processor custom
- `docs/tenacity-reference.md` — retry API calls, backoff, rate limits TMDB/TVDB
- `docs/rich-reference.md` — CLI output, progress bars, tables, theming
- `docs/structlog-reference.md` — logging JSON structuré, context binding, switch dev/prod

## Versioning Hygiene

`git filter-repo` works on this repo but `.git/config` is read-only (macOS permissions) — remote removal error is cosmetic, re-add remote after if needed.
