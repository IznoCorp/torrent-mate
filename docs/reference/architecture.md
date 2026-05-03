# Architecture Reference

Package layout, module map, shared utilities, and key dependencies.

## Package

Package name: `personalscraper`. CLI entry point: `personalscraper <command>`.

## Workflow Pipeline

1. **Torrent download** — completed torrents land in `/path/to/torrents/complete`
2. **Initial sort** — files are deposited at the root of `staging/`, then `personalscraper sort` dispatches them into the correct subdirectories (001-MOVIES, 002-TVSHOWS, etc.) based on file type detection
3. **Rename & clean** — strip release-group tags, codec info, resolution labels from filenames
4. **Scrape metadata** (`personalscraper scrape`) — automated via TMDB/TVDB APIs, produces `.nfo` files and artwork. MediaElch can still be used manually as fallback.
5. **Move to storage** — files go to one of the 4 destination disks

### Automated Pipeline (`personalscraper run`)

Full pipeline executes 9 steps sequentially with idempotence (safe to re-run):

```
INGEST → SORT → [gate: 097-TEMP empty] → CLEAN (reclean+dedup) → SCRAPE → CLEANUP → ENFORCE → VERIFY → TRAILERS → DISPATCH
```

- Steps 1-2 (ingest, sort) are critical — a crash aborts the pipeline
- Steps 3-5 (clean, scrape, cleanup) run with individual error isolation
- Step 6 (enforce) sanitizes filenames, validates structure, checks cross-step coherence
- Step 7 (verify) produces a dispatchable list; step 9 (dispatch) is skipped if verify fails
- Step 8 (trailers) blocks on error -- trailer errors abort the pipeline. Enabled by default.

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
│   ├── commands/        # Typer command groups (pipeline, library, config, info)
│   │   ├── library/         # library-* sub-commands (scan, query, maintenance, audit, analyze)
│   ├── conf/            # Config loader, overlay merger, resolver, classifier, staging
│   │   ├── models/          # Pydantic sub-models (categories, disks, paths, preferences, etc.)
│   ├── info/            # info command implementation (run.py)
│   ├── scraper/         # TMDB/TVDB matching, NFO, artwork, episodes + circuit breaker
│   │   ├── orchestrator.py      # Scraper composition and shared lifecycle
│   │   ├── movie_service.py     # movie scrape flow
│   │   ├── tv_service.py        # TV show/episode scrape flow
│   │   ├── tmdb_client.py       # TMDB API v3 client (Bearer token auth)
│   │   ├── tvdb_client.py       # TVDB API v4 client (Negotiated Contract auth)
│   │   ├── nfo_generator.py     # NFO file writer (Kodi-compliant XML)
│   │   ├── artwork.py           # poster + background download (TMDB/TVDB)
│   │   ├── confidence.py        # fuzzy match confidence scoring
│   │   ├── mediainfo.py         # ffprobe wrapper + ISO 639-2 codec/lang mapping
│   │   ├── circuit_breaker.py   # TMDB/TVDB circuit breaker (5 failures → 5 min open)
│   │   ├── rename_service.py    # rename helpers
│   │   ├── existing_validator.py # existing NFO/artwork validation
│   │   ├── classifier.py        # media item classification adapter
│   │   ├── episode_manager.py   # episode renumber + phantom-season remap
│   │   ├── http_retry.py        # tenacity retry logger builder
│   │   ├── keywords_cache.py    # TMDB keyword lookup cache
│   │   ├── providers.py         # API provider enum + routing helpers
│   │   ├── run.py               # scrape step entry point
│   │   ├── scraper.py           # legacy scraper compositor (post-decomposition thin wrapper)
│   │   ├── _shared.py           # internal shared helpers
│   │   ├── json_ttl_cache.py    # JSON-backed TTL cache for YouTube search results
│   │   ├── youtube_search.py    # YouTube Data API v3 quota-aware search
│   │   ├── trailer_finder.py    # Two-tier TMDB/YouTube trailer URL discovery
│   │   ├── ytdlp_downloader.py  # yt-dlp wrapper with retry and cookie support
│   │   └── trailers_cache.py    # Per-media trailer URL TTL cache
│   ├── process/         # reclean, dedup, cleanup (between sort and scrape)
│   ├── enforce/         # file sanitizer, structure validator, coherence checker
│   ├── indexer/         # SQLite-backed media index — scan, drift, repair, query, outbox
│   │   ├── __init__.py
│   │   ├── db.py                # connection, WAL PRAGMAs, lock, migrations applier
│   │   ├── schema.py            # frozen dataclass row types + Pydantic JSON-column models
│   │   ├── scanner/             # scan engine (os.scandir + ThreadPool, modes, checkpoint)
│   │   │   ├── _modes/          # ScanMode enum + full/quick/incremental/enrich/verify/backfill handlers
│   │   │   ├── _walker.py       # recursive dir walker + dir-mtime skip
│   │   │   ├── _db_writes.py    # batch upserts into media_file + path tables
│   │   │   ├── _checkpoint.py   # crash-resume checkpoint read/write
│   │   │   ├── _concurrency.py  # ThreadPoolExecutor wiring
│   │   │   ├── _exclusions.py   # junk-file patterns, sentinel checks
│   │   │   ├── _spotlight.py    # macOS Spotlight availability probe
│   │   │   ├── _index_ddl.py    # per-scan WAL index creation
│   │   │   ├── _shutdown.py     # SIGTERM handler + budget guard
│   │   │   └── _types.py        # internal ScanContext / FileVisit types
│   │   ├── drift.py             # racy-mtime rule, N-strikes soft-delete, rename detection
│   │   ├── fingerprint.py       # OSHash + xxh3_64 partial + racy detection
│   │   ├── mediainfo.py         # pymediainfo wrapper, normalised stream extraction
│   │   ├── merkle.py            # per-disk Merkle root + mountpoint sentinel guard
│   │   ├── repair.py            # repair queue worker + budget drain
│   │   ├── outbox/              # outbox drainer + write-through (apply, drain, publish, disk)
│   │   ├── query.py             # flex-attr query parser (FIELD_REGISTRY, execute())
│   │   ├── cli.py               # compatibility registration for library commands
│   │   ├── commands/            # indexer CLI command implementations
│   │   ├── config.py            # IndexerConfig pydantic submodel
│   │   ├── breaker.py           # per-disk circuit breaker
│   │   ├── _container_fastpath.py # container format fast path (MKV/MP4)
│   │   ├── reconcile.py         # drift reconciliation engine
│   │   ├── release_linker.py    # release-to-item linker
│   │   ├── _macos_io.py         # macOS-specific I/O helpers (diskutil, volume UUID)
│   │   ├── _throttle.py         # token-bucket I/O rate limiter
│   │   ├── migrations/          # numbered .sql files + applier
│   │   │   ├── 001_init.sql
│   │   │   ├── 002_nullable_release_id_oshash.sql
│   │   │   ├── 003_repair_queue_pending_dedup.sql
│   │   │   └── 004_extend_media_stream.sql
│   │   └── repos/               # one Repository class per entity group
│   │       ├── disk_repo.py     # disk + path tables
│   │       ├── item_repo.py     # media_item + item_attribute (flex attrs)
│   │       ├── release_repo.py  # media_release
│   │       ├── file_repo.py     # media_file + media_stream
│   │       ├── tv_repo.py       # season + episode
│   │       ├── log_repo.py      # scan_run + scan_event + deleted_item
│   │       └── outbox_repo.py   # index_outbox + pending_op + repair_queue
│   ├── library/         # scan, clean, validate, analyze, recommend, report
│   ├── verify/          # quality gate, fixer, genre categorization, reinforced checks
│   ├── dispatch/        # disk scanner, media index, transfer helpers, movie/tv dispatch
│   ├── pipeline.py      # sequential 9-step pipeline orchestrator
│   ├── pipeline_protocol.py # PipelineStep protocol + StepContext
│   ├── pipeline_steps.py # default step registry + legacy override shim
│   ├── reports/         # typed StepReport.details_payload contracts
│   ├── cli.py           # Typer CLI entry point
│   ├── cli_app.py       # Typer app instance
│   ├── cli_state.py     # CLI state management
│   ├── cli_helpers.py   # CLI helper utilities
│   ├── io_utils.py      # I/O helper functions
│   ├── config.py        # pydantic-settings
│   ├── lock.py          # PID-based pipeline lock (configurable data_dir)
│   ├── logger.py        # structlog dual output (console + JSON)
│   ├── models.py        # StepReport, SortResult, PipelineReport
│   ├── text_utils.py    # media_processor, fuzzy_match_score (shared across modules)
│   ├── naming_patterns.py # NamingPatterns dataclass (shared across modules)
│   ├── nfo_utils.py     # NFO parsing helpers (is_nfo_complete, etc.)
│   ├── notifier.py      # Telegram notifications
├── tests/               # pytest tests (unit + E2E)
│   ├── commands/        # CLI command tests
│   ├── e2e/             # Real torrent E2E (pytest -m e2e_torrent); indexer E2E scenarios
│   ├── fixtures/        # Shared test fixtures + config
│   ├── indexer/         # indexer unit + property tests (db, schema, repos, scanner, drift, query, CLI, plists)
│   ├── info/            # info command tests
│   ├── reports/         # StepReport payload tests
│   ├── scripts/         # script-level tests
│   ├── tools/           # tool-level tests
│   ├── integration/     # cross-module integration tests (outbox write-through, dispatch merge/replace/new)
│   ├── conf/            # config-overhaul unit tests (loader, overlay, migration, classifier)
│   ├── ingest/          # ingest unit tests
│   ├── sorter/          # sorter unit tests
│   ├── scraper/         # scraper unit tests
│   ├── process/         # process unit tests (reclean, dedup, cleanup, run)
│   ├── verify/          # verify unit tests
│   ├── dispatch/        # dispatch unit tests
│   ├── enforce/         # enforce unit tests (file sanitizer, structure, coherence)
│   ├── library/         # library unit tests (scan, clean, validate, analyze, recommend, report)
│   ├── trailers/        # trailers unit tests (orchestrator, scanner, state, placement, CLI)
│   └── resilience/      # resilience unit tests (idempotence, crash recovery)
├── assets/torrents/     # .torrent files for E2E tests (Jumanji, Malcolm)
│   └── expected/        # Golden files (expected results per torrent)
├── docs/                # Reference docs, feature plans, archive
├── pyproject.toml       # Project config (PEP 621)
├── Makefile             # make test/lint/format/install-dev
├── MANUAL.md            # User manual (French) — shell commands, disk layout, naming
├── .env.example         # Config template
├── com.personalscraper.pipeline.plist.template  # launchd daily agent (3am)
└── logs/                # Structured JSON logs (gitignored)
```

Notes:

- MediaElch is the external metadata scraper — Claude does not interact with it directly.

## Shared Utilities (single source of truth)

- `classify()` — lives in `personalscraper/conf/classifier.py`; imported by verify and dispatch for genre/rule → category mapping (replaces the removed `genre_mapper` module).
- `media_processor()` — lives in `personalscraper/text_utils.py`; imported by sorter and scraper. NFD accent stripping for French titles.
- `sanitize_filename()` — lives in `personalscraper/text_utils.py`; strips `<>:"/\|?*` and normalizes U+00A0→space. Applied in `NamingPatterns.format()` (all artwork/NFO filenames) and in scraper `clean_name` (folder renames). TMDB titles often contain `:` (e.g. "Spirale : L'Héritage de Saw") and non-breaking spaces (French typography before `:`).
- `SortResult`, `StepReport`, `PipelineReport` — defined in `personalscraper/models.py`. Each `run_*()` converts internal results to `StepReport` before returning; `personalscraper/reports/` defines typed `details_payload` contracts for each pipeline step.
- TV show folders: sorter creates `Show Name/` (no year), scraper renames to `Show Name (Year)/` after API matching (idempotent rename).

## trailers/ Subsystem Notes

- `trailers/` is a first-class consumer of the indexer DB. The orchestrator calls
  `trailers.scanner.Scanner.scan_library(conn)` once per run, which queries
  `indexer.query.find_items_without_trailer(conn)` to detect items missing a
  `trailer_found` attribute. The on-disk media directory for each candidate
  is recovered from the `dispatch_path` flex attribute (written by both the
  dispatch layer and `library.scanner.scan_library`). This avoids
  re-downloading trailers for shows already present in the permanent library
  (library-aware idempotence, DESIGN section 8 / §10.3). The previous TTL-cached
  walk via `library.scanner.scan_library()` was removed in the media-indexer
  feature.
- The new scraper modules (`json_ttl_cache`, `youtube_search`, `trailer_finder`,
  `ytdlp_downloader`, `trailers_cache`) are independent of the existing TMDB/TVDB scraper.

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
