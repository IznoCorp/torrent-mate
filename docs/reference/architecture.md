# Architecture Reference

Package layout, module map, pipeline versions, shared utilities, and key dependencies.

## Package

Package name: `personalscraper`. CLI entry point: `personalscraper <command>`.
V0-V14 implemented (ingest, sort, scrape, verify, dispatch, pipeline run + notifications, E2E tests, test audit, robustness, pipeline integrity, resilience, pipeline hardening, pipeline correctness, library maintenance).

## Workflow Pipeline

1. **Torrent download** — completed torrents land in `/Volumes/IznoServer SSD/torrents/complete`
2. **Initial sort (`torrent-sort`)** — files are deposited at the root of `A TRIER/`, then `torrent-sort` dispatches them into the correct subdirectories (001-MOVIES, 002-TVSHOWS, 004-AUDIO, etc.) based on file type detection
3. **Rename & clean** — strip release-group tags, codec info, resolution labels from filenames
4. **Scrape metadata** (`personalscraper scrape`) — automated via TMDB/TVDB APIs (V3), produces `.nfo` files and artwork. MediaElch can still be used manually as fallback.
5. **Move to storage** — files go to one of the 4 destination disks

### Automated Pipeline (`personalscraper run`)

Full pipeline (V9+V10+V13) executes 8 steps sequentially with idempotence (safe to re-run):

```
INGEST → SORT → [gate: 097-TEMP empty] → CLEAN (reclean+dedup) → SCRAPE → CLEANUP → ENFORCE → VERIFY → DISPATCH
```

- Steps 1-2 (ingest, sort) are critical — a crash aborts the pipeline
- Steps 3-5 (clean, scrape, cleanup) run with individual error isolation
- Step 6 (enforce) sanitizes filenames, validates structure, checks cross-step coherence
- Step 7 (verify) produces a dispatchable list; step 8 (dispatch) is skipped if verify fails

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
│   ├── enforce/         # V13: file sanitizer, structure validator, coherence checker
│   ├── library/         # V14: scan, clean, validate, analyze, recommend, report
│   ├── verify/          # V4+V9: quality gate, fixer, genre categorization, reinforced checks
│   ├── dispatch/        # V5: disk scanner, media index, rsync transfer + V8 rollback/fallback
│   ├── pipeline.py      # V9+V13: Sequential 8-step pipeline orchestrator
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
│   ├── dispatch/        # V5 unit tests
│   ├── enforce/         # V13 unit tests (file sanitizer, structure, coherence)
│   ├── library/         # V14 unit tests (scan, clean, validate, analyze, recommend, report)
│   └── resilience/      # V10 unit tests (idempotence, crash recovery)
├── assets/torrents/     # .torrent files for E2E tests (Jumanji, Malcolm)
│   └── expected/        # V7.x: Golden files (expected results per torrent)
├── docs/                # Planning docs per version
│   ├── v0-project-setup/ through v7-e2e-tests/  # V0-V7 (completed)
│   ├── v7x-test-audit/  # V7.x: Test audit + golden files (implemented)
│   ├── v8-robustness/   # V8: Robustness improvements (implemented)
│   ├── v9-pipeline-integrity/  # V9: Pipeline integrity (implemented)
│   ├── v10-pipeline-resilience/ # V10: Idempotence + crash recovery (implemented)
│   ├── v11-code-quality/  # V11: Code quality hardening (implemented)
│   ├── v12-pipeline-hardening/  # V12: 22 bugs fixed, NTFS safety (implemented)
│   └── v13-pipeline-correctness/ # V13: ENFORCE step, idempotence tests (implemented)
├── 099-SCRIPTS/         # Legacy scripts (.bak files, gitignored)
├── pyproject.toml       # Project config (PEP 621)
├── Makefile             # make test/lint/format/install-dev
├── MANUAL.md            # User manual (French) — shell commands, disk layout, naming
├── .env.example         # Config template
├── com.personalscraper.pipeline.plist  # launchd daily agent (3am)
└── logs/                # Structured JSON logs (gitignored)
```

Notes:
- Legacy scripts (099-SCRIPTS/) exist on disk but are gitignored. Contains 7 `.bak` Python scripts and a `plex/` subfolder. All replaced by PersonalScraper V0-V7.
- MediaElch is the external metadata scraper — Claude does not interact with it directly.

## Pipeline Versions

| Version | Name                 | Role                                                              | Phases |
| ------- | -------------------- | ----------------------------------------------------------------- | ------ |
| V0      | PROJECT SETUP        | pyproject.toml, CLI Typer, pydantic-settings, logger              | 4      |
| V1      | INGEST               | qBittorrent → A TRIER/ (copy if seeding, move if done)            | 5      |
| V2      | SORT+CLEAN           | guessit parsing + FileMate strategies → 001-MOVIES/, 002-TVSHOWS/ | 4      |
| V3      | SCRAPE               | TMDB/TVDB matching, NFO XML, artwork, episode rename              | 13     |
| V4      | VERIFY               | Quality gate: checker + fixer + genre categorization              | 4      |
| V5      | DISPATCH             | Move to Disk1-4 (replace movies, merge series)                    | 3      |
| V6      | LOG+NOTIFY           | JSON logging, Telegram notifications, launchd scheduling          | 3      |
| V7      | E2E TESTS            | Real torrent tests with safe cleanup markers                      | 5      |
| V7.x    | TEST AUDIT           | Golden files E2E, test reinforcement, coverage 79%→82%+           | 4      |
| V8      | ROBUSTNESS           | Circuit breaker, fuzzy guards, dispatch rollback, disk fallback   | 5      |
| V9      | PIPELINE INTEGRITY   | Sequential 7-step pipeline, reclean+dedup, verify reinforced      | 5      |
| V10     | PIPELINE RESILIENCE  | Idempotence, fast-skip, NFO validation, crash recovery, tests     | 5      |
| V11     | CODE QUALITY         | Error isolation, CLI UX, dead code, DRY extraction                | 4      |
| V12     | PIPELINE HARDENING   | NTFS-safe names, episode restructuring, crash recovery, 22 bugs   | 9      |
| V13     | PIPELINE CORRECTNESS | Idempotent fast-skip, ENFORCE step, E2E idempotence tests         | 5      |
| V14     | LIBRARY MAINTENANCE  | Library scan/clean/validate/analyze/recommend/report              | 9      |

## Shared Utilities (single source of truth)

- `genre_mapper` — lives in `personalscraper/genre_mapper.py` (package root); imported by V4-verify and V5-dispatch for genre→category mapping.
- `media_processor()` — lives in `personalscraper/text_utils.py`; imported by V2 matcher, V3 confidence, V5 media_index. NFD accent stripping for French titles.
- `sanitize_filename()` — lives in `personalscraper/text_utils.py`; strips `<>:"/\|?*` and normalizes U+00A0→space. Applied in `NamingPatterns.format()` (all artwork/NFO filenames) and in scraper `clean_name` (folder renames). TMDB titles often contain `:` (e.g. "Spirale : L'Héritage de Saw") and non-breaking spaces (French typography before `:`).
- `SortResult`, `StepReport`, `PipelineReport` — defined in `personalscraper/models.py` (V0+V6). Each `run_*()` converts internal results to `StepReport` before returning.
- TV show folders: V2 creates `Show Name/` (no year), V3 renames to `Show Name (Year)/` after API matching — V3 handles idempotent rename.

## Key Dependencies (chosen after evaluation)

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

## Reference Documentation

- `docs/qbittorrent-api-reference.md` — V1: TorrentState enum, exceptions, patterns pipeline
- `docs/guessit-evaluation.md` — V2: parsing noms media, tests réels, comparaison regex
- `docs/ffprobe-reference.md` — V3: extraction streamdetails, mapping codec/langue Kodi
- `docs/TMDB-API.md` — V3: référence API TMDB v3 vérifiée par tests live
- `docs/TVDB-API.md` — V3: référence API TVDB v4 vérifiée par tests live
- `docs/rapidfuzz-reference.md` — V3: fuzzy matching titres, scorers, media_processor custom
- `docs/tenacity-reference.md` — V3: retry API calls, backoff, rate limits TMDB/TVDB
- `docs/rich-reference.md` — V0: CLI output, progress bars, tables, theming
- `docs/structlog-reference.md` — V6: logging JSON structuré, context binding, switch dev/prod

## Versioning Hygiene

When inserting a new version between existing ones, update ALL references: H1 titles, commit prefixes (`vX.Y.Z:`), cross-version refs, sub-phase numbering, data flow diagrams.
`git filter-repo` works on this repo but `.git/config` is read-only (macOS permissions) — remote removal error is cosmetic, re-add remote after if needed.
