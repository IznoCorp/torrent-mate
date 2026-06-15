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
│   ├── acquire/         # Acquisition lobe — 4-table SQLite store (RP3) + delete authority + event catalog (RP4)
│   │   ├── domain.py           # Frozen VOs: FollowedSeries, WantedItem, SeedObligation, RatioState
│   │   ├── events.py           # Event catalog (RP4): 10 frozen Event subclasses for Follow/Grab/Seed/Ratio
│   │   ├── store.py            # ConcreteAcquireStore — 4 sub-stores, lazy-open, lock-free reads;
│   │   │                         # _FollowSubStore: find_by_ref/list_active/list_all/set_active (Follow D1 CRUD)
│   │   ├── delete_authority.py # DeleteAuthority: DeletePermit + SeedObligationRecorder impl (fail-open)
│   │   ├── _factory.py         # build_acquire_context (fills store= + delete_authority=)
│   │   ├── _ports.py           # AcquireStore Protocol (extended in RP3);
│   │   │                         # FollowSubStore: add/get/find_by_ref/list_active/list_all/set_active (Follow D1)
│   │   ├── title_resolver.py  # Fail-soft series-title resolution (Follow D1) — calls provider_registry.chain(TvDetailsProvider), falls back to "tvdb:<id>"
│   │   ├── errors.py           # AcquireLockError, AcquireCorruptError, AcquireMigrationError
│   │   ├── context.py          # AcquireContext dataclass (per-invocation acquire service bundle)
│   │   ├── desired.py         # Resolution IntEnum, QualityProfile, SourceCriteria, JSON codecs (RP3a vocab)
│   │   ├── _dedup.py          # SearchOutcome, search_candidates seam, token-set normalizer, dedup()
│   │   ├── _filters.py        # Hard-filter stage: resolution floor (fail-open None) + anchored audio language regex
│   │   ├── orchestrator.py    # GrabOrchestrator — single-item §1 grab chain, failure taxonomy, event emission
│   │   ├── service.py         # AcquisitionService batch loop, GrabCore handle, RunSummary, attempts cap
│   │   ├── airing.py          # RP9 — stateless set-poll: poll_aired(series, registry, *, today) → list[AiredEpisode]; capability-only (no store/ownership/cadence); unblocks Follow D2
│   │   ├── cadence.py         # Follow D2 — Cadence/CadenceTier VOs + is_due_by_cadence/is_past_cutoff (pure, stdlib only)
│   │   └── migrations/         # SQL migration scripts for acquire.db
│   │   Import direction: downward only (api/, core/, conf/, events/); never triage packages.
│   │   (RP4) `subscribers/acquire.py` — muted AcquisitionTelegramSubscriber, gated by `acquire_notify_enabled`.
│   ├── ingest/          # qBittorrent → staging
│   ├── sorter/          # guessit + strategies → category folders
│   ├── commands/        # Typer command groups (pipeline, library, config, info, grab, follow)
│   │   ├── library/         # library-* sub-commands (scan, query, maintenance, audit, analyze)
│   │   ├── grab.py          # `personalscraper grab` — batch acquisition run (--dry-run, --limit)
│   │   ├── follow.py        # `personalscraper follow add/list/remove` — followed-series management (Follow D1)
│   ├── conf/            # Config loader, overlay merger, resolver, classifier, staging
│   │   ├── models/          # Pydantic sub-models (categories, disks, paths, preferences, etc.)
│   ├── info/            # info command implementation (run.py)
│   ├── api/             # Unified third-party API consumers (api-unify, 0.11.0)
│   │   ├── _contracts.py        # ApiError, AuthMode
│   │   ├── _activation.py       # ProviderActivation (cred presence check)
│   │   ├── _units.py            # ByteSize (parseable + comparable disk-size type)
│   │   ├── transport/           # HttpTransport + TransportPolicy + auth/retry/circuit/rate
│   │   ├── metadata/            # MetadataClient family — tmdb, tvdb, omdb, trakt, imdb, rotten_tomatoes
│   │   ├── torrent/             # TorrentClient family — qbittorrent, transmission
│   │   │   ├── _base.py              # TorrentItem, TorrentSource, TorrentLimits
│   │   │   ├── _contracts.py         # TorrentLister, TorrentInspector, TorrentController,
│   │   │   │                         # TorrentAdder, TorrentLimiter (Protocols)
│   │   │   ├── _factory.py           # build_client, build_active_torrent_client
│   │   │   ├── qbittorrent.py        # QBitClient (Adder + Limiter)
│   │   │   └── transmission.py       # TransmissionClient (Adder only)
│   │   ├── tracker/             # TrackerClient + ranking engine — lacale, c411
│   │   │   ├── _errors.py            # TrackerAuthError, TorrentFetchError (tracker-family errors)
│   │   │   └── _fetch.py             # fetch boundary (RP1a): TrackerResult → TorrentSource
│   │   │                             # via HttpTransport.get_bytes (dedicated download circuit, D3);
│   │   │                             # owns ALL TorrentFetchError surfacing; magnet bypasses network
│   │   └── notify/              # Notifier + HealthChecker — telegram, healthchecks
│   ├── core/            # Reusable cross-cutting infrastructure (post-api-unify)
│   │   ├── _contracts.py        # Core-layer primitive contracts: MediaType, ApiError, CircuitOpenError (re-exported from api/_contracts.py for backward compat)
│   │   ├── media_types.py       # Shared media-type constants: VIDEO_EXTENSIONS, FileType, is_trailer_filename (canonical home — promoted from sorter/file_type.py in arch-cleanup-2)
│   │   ├── circuit.py           # CircuitBreaker (reused by API transport + indexer disk breaker)
│   │   ├── http_helpers.py      # tenacity helpers (retry logger, retryable predicate)
│   │   ├── identity.py          # MediaRef — neutral provider-ID value object (tvdb primary)
│   │   ├── delete_permit.py     # DeletePermit + SeedObligationRecorder Protocols + AllowAllPermit
│   │   ├── ownership.py         # OwnershipChecker Protocol + NullOwnershipChecker (RP6)
│   │   ├── sqlite/              # Neutral SQLite machinery (event-free): open_db, db_lock,
│   │   │                        # apply_migrations, apply_pragmas, _fs_probe, errors.Sqlite*Error
│   │   ├── event_bus.py         # pub-sub EventBus (in-process, no business logic)
│   │   └── app_context.py       # per-invocation frozen service container (AppContext)
│   ├── scraper/         # NFO/artwork orchestration consuming api/metadata providers
│   │   ├── orchestrator.py      # Scraper composition and shared lifecycle
│   │   ├── movie_service.py     # movie scrape flow
│   │   ├── tv_service.py        # TV show/episode scrape flow
│   │   ├── nfo_generator.py     # NFO file writer (Kodi-compliant XML)
│   │   ├── artwork.py           # poster + background download (TMDB/TVDB)
│   │   ├── confidence.py        # fuzzy match confidence scoring
│   │   ├── mediainfo.py         # ffprobe wrapper + ISO 639-2 codec/lang mapping
│   │   ├── rename_service.py    # rename helpers
│   │   ├── existing_validator.py # existing NFO/artwork validation
│   │   ├── classifier.py        # media item classification adapter
│   │   ├── episode_manager.py   # episode renumber + phantom-season remap
│   │   ├── keywords_cache.py    # TMDB keyword lookup cache
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
│   │   ├── ownership.py         # is_owned SELECT-only predicate + IndexerOwnershipChecker adapter (RP6)
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
│   ├── insights/        # (new in 0.19.0) read-only analytics over the indexer DB: analytics, reporter, recommender, models
│   ├── maintenance/     # (new in 0.19.0) operator upkeep: disk_cleaner (FS deletes), rescraper (targeted re-scrape)
│   ├── verify/          # quality gate, fixer, genre categorization, reinforced checks, library_checks (validator re-home, new in 0.19.0)
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
- Media-type constants (`VIDEO_EXTENSIONS`, `FileType`, `is_trailer_filename`) — canonical home is `personalscraper/core/media_types.py` (promoted from `sorter/file_type.py` in arch-cleanup-2). `sorter/file_type.py` now contains only the detection functions (`detect_file_type`, `detect_dir_type`) and imports the shared constants from `core.media_types`.

## trailers/ Subsystem Notes

- `trailers/` is a first-class consumer of the indexer DB. The orchestrator calls
  `trailers.scanner.Scanner.scan_library(conn)` once per run, which queries
  `indexer.query.find_items_without_trailer(conn)` to detect items missing a
  `trailer_found` attribute. The on-disk media directory for each candidate
  is recovered from the `dispatch_path` flex attribute (written by both the
  dispatch layer and the indexer item stage
  `indexer/scanner/_modes/_item_stage.py:scan_and_stage_dir`). This avoids
  re-downloading trailers for shows already present in the permanent library
  (library-aware idempotence, DESIGN section 8 / §10.3). The previous TTL-cached
  filesystem walk was removed in the media-indexer feature.
- The new scraper modules (`json_ttl_cache`, `youtube_search`, `trailer_finder`,
  `ytdlp_downloader`, `trailers_cache`) are independent of the existing TMDB/TVDB scraper.

## `insights/` Package (new in 0.19.0)

Read-only analytics layer over the indexer DB — the SELECT-side re-home of the
former `library/analyzer.py` + `library/recommender.py` + `library/reporter.py`.
It never spawns ffprobe and never walks the filesystem: every metric is read
from the enrich-populated `media_stream` rows (so a prior
`library-index --mode enrich` is a precondition). Modules:

- `analytics.py` — `analyze(conn)` (DB aggregates) + `analyze_from_index(conn, …)`
  (stream-level codec / audio / subtitle analysis). Backs `library-analyze`.
- `reporter.py` — `generate_report()` / `format_report_text()`. Backs `library-report`.
- `recommender.py` — `generate_recommendations()`. Backs `library-recommend`.
- `models.py` — analysis + recommender dataclasses (`VideoInfo`,
  `MediaFileAnalysis`, `AnalysisResult`, `Recommendation`, etc.).

## `maintenance/` Package (new in 0.19.0)

Operator-upkeep package for filesystem and re-scrape maintenance — distinct from
`indexer/repair.py`, which is DB-only. Modules:

- `disk_cleaner.py` — `rmtree`-based deletion + NTFS ghost-dirent handling +
  outbox events. Backs `library-clean`.
- `rescraper.py` — targeted TMDB/TVDB re-scrapes (`rescrape_library`,
  `_detect_needs`). Backs `library-rescrape`.

The former `library/validator.py` (NFO / artwork / naming conformity) is
re-homed standalone as `verify/library_checks.py` (new in 0.19.0), backing
`library-validate` and registerable in the future Check plugin system.

## Key Dependencies (chosen after evaluation)

- `typer` — CLI framework (wraps Click, type hints = spec CLI, rich native, same CliRunner for tests)
- `qbittorrent-api` — qBit wrapper (prefer over raw requests — handles auth/CSRF/v5 compat)
- `guessit` — filename parsing (prefer over custom regex — 140+ services, edge cases)
- `ffprobe` (external ffmpeg tool, via subprocess) — streamdetails extraction in `scraper/mediainfo.py` (no extra Python package, but requires `ffmpeg` installed on the host). The indexer's enrich pass uses the `pymediainfo` package (`indexer/mediainfo.py`) instead.
- `rsync` (subprocess) — cross-filesystem transfers (prefer over shutil — resume, checksum, crash-safe)
- `pydantic-settings` — config (rewritten from scratch, NOT copied from TorrentMaker)
- `rapidfuzz` — fuzzy matching across sorter/scraper/dispatch (MIT license, C++ 5-100x faster than thefuzz)
- `tenacity` — API retry (exponential backoff, wait_exception for Retry-After, composable strategies)
- `rich` — CLI output (progress bars, tables, theming, auto TTY detection, pulled by Typer)
- `structlog` — structured logging (replaces custom JsonFormatter, context binding, dev/prod auto-switch)

## State ownership

The pipeline distinguishes 4 state domains. Each row names exactly one owner
(write authority). Multiple readers are allowed.

| State                               | Owned by                                          | Read by                                                                                                                                           | Storage                    |
| ----------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| Staging FS layout                   | `sort` + `dispatch`                               | `clean`, `scrape`, `cleanup`, `enforce`, `verify`                                                                                                 | `paths.staging_dir`        |
| Storage FS layout                   | `dispatch`                                        | `library-index`, `library-clean`, `library-reconcile`                                                                                             | `paths.disks[*]`           |
| Indexer BDD (`media_item`, ...)     | `library-index` (scanner + outbox drain)          | `library-doctor`, `library-search`, `library-show`, `library-reconcile`, `library-report`, `library-clean`, `library-validate`, `library-analyze` | `.data/library.db`         |
| Provider IDs (`canonical_provider`) | `library-init-canonical` + `library-backfill-ids` | `library-show`, NFO generator (scraper)                                                                                                           | indexer BDD                |
| Pipeline lock                       | `cli.acquire_lock`                                | all pipeline commands (`ingest`, `sort`, …, `dispatch`)                                                                                           | `pipeline.lock`            |
| Ingested torrents tracker           | `ingest`                                          | `ingest` only                                                                                                                                     | `ingested_torrents.json`   |
| EventBus events                     | each emitter                                      | subscribers (logging, Telegram, observability)                                                                                                    | in-process                 |
| Outbox (drain queue)                | `library-index` (write)                           | `library-repair` (read + drain), `library-doctor`                                                                                                 | indexer BDD `index_outbox` |

**Single-writer invariant (P27).** Every row above has exactly one owner. Two
writers to the same state is a race condition. The pipeline lock
(`cli.acquire_lock`) enforces process-level serialization for filesystem writes
— only one pipeline process may mutate staging or storage at a time. The indexer
BDD relies on SQLite WAL mode + `BEGIN IMMEDIATE` for transaction serialization
within a single process; concurrent writer processes are blocked by the pipeline
lock.

**BDD vs FS truth rule (DEV #3, pattern P26).** For a given assertion, exactly
one source is authoritative. The filesystem is truth for file existence and
contents; the BDD is truth for derived metadata (oshash, release_id binding,
scan_generation). Reconciliation always compares BDD to FS, never the reverse:
`library-reconcile` detects files that disappeared from disk and soft-deletes
their BDD rows, but never creates or mutates files based on BDD state.

## Lock order

Total lock order: `pipeline.lock` (outer) > `indexer_lock` > `acquire.db.lock` (leaf).
`acquire.db.lock` (`core/sqlite/_lock.py::db_lock`) is a **brief migration-only leaf** —
taken only around `open_db` + `apply_migrations` in `_ensure_open`, then released
immediately. Runtime writes use SQLite-native serialization via `BEGIN IMMEDIATE` +
`busy_timeout` (no `FileLock`); reads are lock-free (WAL). The store opens lazily:
commands that never touch acquire state open nothing and take no lock.

No `acquire.db` writer may acquire `pipeline.lock` or `indexer_lock` while holding
`acquire.db.lock`. `acquire.db` is a separate file from `library.db`, structurally
isolating the indexer scan's writer from the acquire writer.

See `docs/features/acquire-store/lock-order.md` for the full invariant, rules,
and implementation references.

## Module relationships

The pipeline is composed of 5 major subsystems. They share a thin core
(EventBus + AppContext + Config) and otherwise communicate via the BDD
and the filesystem.

```
[ commands/ ] -----invokes----> [ pipeline phases (ingest/sort/...) ]
     |                                          |
     +--invokes--> [ indexer/ (BDD-backed) ]    +--writes--> FS
                            |                                |
                            +--writes--> indexer BDD         |
                                                             v
                                                   [ scraper/ (NFO + artwork) ]
                                                             |
                                                             +--writes--> FS
```

- **commands/** (`personalscraper/commands/`) — CLI surface (Typer). Adapters
  into pipeline / indexer / scraper / trailers. The `commands/library/`
  sub-package hosts the `library-*` CLI commands (the standalone top-level
  `library/` package was removed in 0.19.0 — lib-fold). Stateless;
  per-invocation state lives in `state` dict + `ctx.obj` (AppContext).
- **pipeline/** (`ingest`, `sort`, `clean`, `scrape`, `cleanup`, `enforce`,
  `verify`, `dispatch`, `trailers`, `process`, `run`) — owns staging + storage
  FS layout. Each step produces a `StepReport`. The `run` orchestrator chains
  them sequentially.
- **indexer/** — SQLite-backed media index. Owns `.data/library.db` exclusively
  and backs every `library-*` command (`library-index`, `library-reconcile`,
  `library-repair`, `library-doctor`, `library-search`, `library-show`,
  `library-clean`). The former standalone top-level `library/` package was folded
  away in 0.19.0 (lib-fold): its NFO-driven `media_item` row construction now
  lives in `indexer/scanner/_modes/_item_stage.py` (pass 1 of
  `library-index --mode full`); its read-only analytics moved to `insights/`
  (`library-analyze`, `library-recommend`, `library-report`); its filesystem +
  re-scrape upkeep moved to `maintenance/` (`library-clean`, `library-rescrape`);
  and its NFO/artwork/naming validator moved to `verify/library_checks.py`
  (`library-validate`).
- **scraper/** (`personalscraper/scraper/`) — metadata (NFO) + artwork + trailer
  URL discovery. Owns NFO writes. Consumes provider APIs (TMDB / TVDB / OMDB /
  Trakt) via `api/metadata/`.
- **trailers/** (`personalscraper/trailers/`) — trailer discovery + download
  (YouTube via yt-dlp). Plex-conformant placement (movies flat, TV shows in
  `Trailers/` subfolder). Consumes the indexer BDD via `trailers.scanner`.

Cross-cutting:

- **core/event_bus.py** — pub-sub for events (no business logic). Process-scoped,
  one `EventBus` per `AppContext`.
- **core/app_context.py** — per-invocation service bundle (`config` +
  `settings` + `event_bus` + `provider_registry` + `torrent_client`).
  Frozen dataclass; see [AppContext Field Table](#appcontext-field-table).
- **conf/** — Pydantic config loader (`paths.json5`, `patterns.json5`,
  `indexer.json5`, `preferences.json5`). Read-only at runtime.
- **transports/** — `HttpTransport` + `TransportPolicy` (rate limit, retry,
  circuit breaker). Used by `api/` providers.

**Dependency direction.** Dependencies flow top-down: `commands/` calls into
`pipeline/`, `indexer/`, `insights/`, `maintenance/`, `scraper/`, and
`trailers/`. The pipeline composes `indexer/` and `scraper/` — the reverse never
happens (indexer and scraper modules never import from pipeline). `core/` and
`conf/` are the lowest layers and must not import from `api/`, `scraper/`,
`pipeline/`, `dispatch/`, `verify/`, `indexer/`, `insights/`, `maintenance/`, or
`trailers/` at runtime. `personalscraper.logger` is
allow-listed as a leaf utility. The `core/app_context.py` TYPE_CHECKING import of
`ProviderRegistry` is the documented AppContext boundary (tested separately).
This invariant is enforced by `tests/architecture/test_layering.py`
(arch-cleanup-2, Phase 2): the prior upward leaks — `core/circuit.py` importing
`api._contracts`, `conf/classifier.py` and `conf/models/api_config.py` importing
`api/` — were closed by promoting those contracts to `core/_contracts.py` and
`conf/models/_ranking.py`. Two upward imports survive as documented exceptions,
each carried by an inline `# layering: allow` marker honoured by the AST guard:
`conf/models/_ranking.py → api._units.ByteSize` (config-model byte-size parse)
and `conf/loader.py → indexer.db._apply_pragmas` (function-local orphan-check
import). `api/` is consumed by `scraper/` and `trailers/` but never by
`commands/` directly.

**`acquire/` import-direction invariant**: `acquire/` must import downward only
(`api/`, `core/`, `conf/`, `events/`). It must never import the triage packages
(`ingest`, `sort`, `sorter`, `process`, `scraper`, `dispatch`, `indexer`,
`enforce`, `verify`, `insights`, `maintenance`, `reports`, `trailers`,
`pipeline`, `pipeline_steps`, `commands`). Enforced by the AST layering guard
in `tests/architecture/test_layering.py`.

**Ownership boundary (RP6):** `acquire/` reads ownership via
`ctx.acquire.ownership` (a `core.ownership.OwnershipChecker`). It NEVER imports
`personalscraper.indexer`. The adapter (`IndexerOwnershipChecker`) lives in
`indexer/` and is wired at the composition root — same shape as the deletion
authority (`core.delete_permit`).

**Airing capability (RP9):** `acquire/airing.py` exposes `poll_aired(series, registry, *, today)` — a **stateless** free function (no `AcquireContext` field) that returns `list[AiredEpisode]` (see `acquire/domain.py`). It performs **zero** `store.wanted.*` writes, never calls `ownership.owns()`, and never reads `cadence_json` — surfacing aired episodes is RP9's sole responsibility; applying policy (wanted enqueue, ownership skip, cadence backoff) is Follow D2's job. Unblocks Follow D2 (calendar-first detection → wanted enqueue).

**Follow D2 (follow-detect):** Follow D2 is RP9's first consumer. The `follow detect` CLI (`commands/follow.py`) drives `poll_aired` over the active followed set, filters owned episodes (RP6 `ownership.owns`) and duplicates (`store.wanted.find`), then enqueues `WantedItem(kind='episode', status='pending')` and emits `WantedEnqueued`. Cadence policy lives in the pure `acquire/cadence.py` (imports `core`/stdlib only — never `store`, `indexer`, `scraper`, or the event bus); the cadence codecs and the `CadenceConfig`→`Cadence` bridge are in `acquire/desired.py`; the cadence-aware re-search gating (cutoff → `WantedAbandoned(reason='cutoff_reached')`) is in `AcquisitionService._process_item`.

## Provider Registry

Capability-keyed, circuit-aware metadata provider dispatch. Introduced in 0.16.0
(feat/registry). Replaces the historical hard-coded `self._tmdb` / `self._tvdb`
pattern with a configurable ordered registry per capability Protocol.

### Module layout

`personalscraper/api/metadata/registry/`:

- `__init__.py` — public `ProviderRegistry` class (chain / fan_out / locked / get / cross_ref / status / operations / providers_for / close) + data structures (Mode, ProviderMatch, LockedProvider, AttemptOutcome, ProviderStatus, ConfigIssue, FanOutResult, Named).
- `_errors.py` — exception hierarchy (RegistryError, RegistryConfigError, UnknownProviderError, ProviderExhausted, WrongSemanticBug).
- `_events.py` — five EventBus event dataclasses (ProviderFallbackTriggered, ProviderExhaustedEvent, LockedCapabilityUnresolved, RegistryFanOutCompleted, RegistryBootValidated).
- `_semantics.py` — capability→Mode mapping (CHAIN / FAN_OUT / LOCKED / DIRECT capability sets, CAPABILITY_KEYS, mode_for()).
- `_factory.py` — provider builders (TMDB, TVDB, IMDb, OMDb, Trakt, RottenTomatoes), `build_providers()`, `_eligible()`.
- `_validation.py` — boot validation: 6 ConfigIssue families aggregated (missing_credentials, protocol_mismatch, unknown_provider, empty_chain_section, locked_capability_orphan, idcrossref_cycle).

### Boot sequence (DESIGN §6.1)

`AppContext._build_app_context()` constructs the registry at the CLI/pipeline
boundary; the steps below all run inside `ProviderRegistry.__init__`
(`api/metadata/registry/__init__.py`), which `_build_app_context` triggers by
instantiating the registry:

1. Instantiate each provider listed in any `providers.json5` section.
2. Validate (aggregated): all 6 issue families collected; on any failure, `RegistryConfigError` raised AFTER cleanup of partially-built providers.
3. Build the per-capability index from the priority-ordered config.
4. Emit `RegistryBootValidated` on success (emitted from `ProviderRegistry.__init__`, not `_build_app_context`).

### Three operations

- `chain(capability)` — ordered list of eligible providers (CLOSED or HALF_OPEN). For chain capabilities (Searchable, MovieDetailsProvider, TvDetailsProvider, EpisodeFetcher).
- `fan_out(capability)` — all eligible providers, in config order. For aggregation capabilities (RatingProvider). Always emits `RegistryFanOutCompleted`.
- `locked(capability, match)` — provider bound to the match's id, with `IDCrossRef` escape for cross-provider id translation. For identity-locked capabilities (ArtworkProvider, KeywordProvider, VideoProvider, RecommendationProvider).

### Configuration

`config/providers.json5` (one overlay file in the Config bundle):

```json5
{
  providers: {
    Searchable: { tvdb: 1, tmdb: 2 },
    MovieDetailsProvider: { tmdb: 1, tvdb: 2 },
    // ... 11 capability sections total
  },
}
```

Lower priority number = higher precedence. `extra="forbid"` strict — unknown
sections rejected at boot.

### Introspection

`registry.status()` returns per-provider circuit state. Exposed via
`personalscraper info providers`.

### Registry events on the `Event` contract

The five provider-registry events (`ProviderFallbackTriggered`,
`ProviderExhaustedEvent`, `LockedCapabilityUnresolved`,
`RegistryFanOutCompleted`, `RegistryBootValidated`) are full `Event`
subclasses as of arch-cleanup-2 (v0.17.0). They are auto-registered in
`_EVENT_CLASS_REGISTRY`, envelope-round-trippable, and delivered to
base-`Event` subscribers. The event catalog count is 23.

### See also

- `docs/reference/scraping.md#capability-cookbook` — six worked examples,
  one per call shape (chain Searchable, chain MovieDetailsProvider,
  fan_out RatingProvider, locked, cross_ref, direct get).
- `docs/reference/indexer.md#registry-integration` — how `backfill_ids`
  composes `fan_out(RatingProvider)` with `chain(MovieDetailsProvider |
TvDetailsProvider)`.
- `docs/reference/external-ids-flow.md` — cross-provider id flow at the
  pipeline level.

## Torrent Client Boot-Wiring (torrent-write, v0.21.0)

The `torrent-write` feature promotes the active torrent client into
`AppContext`, validates it at boot (fail-fast) **for the commands that consume
it**, and defines two new capability Protocols. This mirrors the metadata
`ProviderRegistry` boot pattern but is simpler: a single client, not a
multi-provider registry.

### Torrent Family — Capability Table

The torrent family (`api/torrent/`) defines 7 atomic `@runtime_checkable`
Protocols in `_contracts.py`. The two new ones (`TorrentAdder`, `TorrentLimiter`)
were added in `torrent-write`; the five pre-existing ones were unchanged.

| Capability              | QBitClient | TransmissionClient | Protocol file         |
| ----------------------- | ---------- | ------------------ | --------------------- |
| `TorrentLister`         | ✓          | ✓                  | `_contracts.py` (pre) |
| `TorrentInspector`      | ✓          | ✓                  | `_contracts.py` (pre) |
| `AuthenticatedClient`   | ✓          | ✗                  | `_contracts.py` (pre) |
| `TorrentStateInspector` | ✓          | ✓                  | `_contracts.py` (pre) |
| `TorrentController`     | ✓          | ✓                  | `_contracts.py` (pre) |
| `TorrentAdder`          | ✓          | ✓                  | `_contracts.py` (new) |
| `TorrentLimiter`        | ✓          | ✗                  | `_contracts.py` (new) |

- **`TorrentAdder`**: `add(source, *, category, tags, paused, limits) → str` —
  returns the `info_hash` (D6). Composed by both clients.
- **`TorrentLimiter`**: `apply_limits(info_hash, limits) → None` — composed by
  qBittorrent only. Transmission lacks per-torrent ratio/bandwidth/seed-time RPC
  methods (D2). Passing `limits` to `TransmissionClient.add()` raises
  `UnsupportedCapabilityError` (D8).

### `AppContext` Field Table

`AppContext` is the frozen process-scoped service container
(`core/app_context.py`, line 37). The `torrent_client` field was added in
`torrent-write`.

| Field               | Type                                       | Description                                          |
| ------------------- | ------------------------------------------ | ---------------------------------------------------- |
| `config`            | `Config`                                   | Typed JSON5 configuration                            |
| `settings`          | `Settings`                                 | Pydantic env-var settings (API keys, paths)          |
| `event_bus`         | `EventBus`                                 | In-process pub-sub for cross-component events        |
| `provider_registry` | `ProviderRegistry`                         | Capability-keyed metadata provider dispatch          |
| `torrent_client`    | `QBitClient \| TransmissionClient \| None` | Active torrent client; `None` when unconfigured (D9) |

### Boot Sequence

`_build_app_context(config, settings, *, build_torrent_client=False)`
(`cli_helpers/__init__.py`) handles torrent client resolution after the metadata
`ProviderRegistry` is constructed. The build is **gated on `build_torrent_client`**:

1. **When `build_torrent_client` is True _and_ `config.torrent.active` is set**
   (non-empty string):
   - Calls `build_active_torrent_client(config.torrent)` from
     `api/torrent/_factory.py` to instantiate the client (a live network
     connect + login).
   - Asserts the result is `isinstance(raw_client, TorrentAdder)` — fails
     with `RegistryConfigError` (code `protocol_mismatch`, section `torrent`)
     if the client does not compose the adder capability (D3 fail-fast).
   - Stores the validated client in `torrent_client`.
2. **Otherwise** (`build_torrent_client` False, or `config.torrent.active`
   empty `""`):
   - `torrent_client` stays `None` — no boot error, no daemon contact.

**Who sets `build_torrent_client=True`:** only the commands that actually read
`ctx.torrent_client` — `run` (includes the ingest step), the standalone
`ingest` subcommand, and `torrents_list`. Read-only commands (`library *`,
`trailers`, `maintenance`, `info`) leave it `False` so they never connect or
log in to the torrent daemon at boot. This prevents a configured-but-unreachable
daemon (or a stale-credential login, which would write a 1-hour auth lockout
that blocks the next ingest) from breaking a command that has nothing to do with
torrents (review #1/#2/#5).

This replaces the previous lazy-per-step `build_active_torrent_client()` calls
in `ingest/ingest.py` and `commands/pipeline.py`, which now read
`ctx.torrent_client` directly.

## Anti-decisions (out of scope for 1.0)

These were considered and explicitly deferred past 1.0. Re-opening any of these
requires a new design document. Listed here so future contributors don't waste
time proposing what was already declined.

- **No microservices.** Single Python process. The pipeline runs end-to-end
  in-tree; the BDD is local SQLite. Splitting into services trades clarity for
  operability cost we don't yet have a reason to pay.
- **No network server / web UI _in 1.0_.** The CLI is the only interface for
  1.0 — no FastAPI, no Flask, no embedded server in-tree today. A Web Management
  UI is now a planned post-1.0 feature (see `ROADMAP.md` P2 — Web Management UI),
  with `arch-cleanup-2` landing the event-contract prerequisites first.
- **No authentication / multi-user.** Single operator on a single machine.
  Files inherit OS permissions; the BDD is owned by the running user.
- **No plugin loader.** Scrapers and torrent clients are configured via
  `config/*.json5`, not loaded from a plugin directory. Adding a provider =
  editing source.
- **No cloud / no remote storage.** Storage is local, directly-attached disks.
  Today that is NTFS via macFUSE (Apple Silicon); multi-filesystem support
  (APFS / HFS+ on AppleRAID / ext4 / exFAT) is a planned feature (see
  `ROADMAP.md` P2 — Multi-Filesystem Support). Backup is the operator's
  responsibility (rsync, snapshot, Backblaze, ...). No S3 / Glacier /
  cold-storage tier abstraction, and no network filesystems (NFS/SMB).
- **No web scraping fallback.** Metadata comes from typed provider APIs
  (TMDB / TVDB / OMDB / Trakt). MediaElch is the manual fallback when API
  matching fails — there is no HTML scraping codepath.

## Reference Documentation

Canonical provider/tool references (consolidated into `docs/reference/`):

- [`qbittorrent-api.md`](qbittorrent-api.md) — qBittorrent WebUI API + `qbittorrentapi` client: TorrentState enum, exceptions, pipeline patterns
- [`tmdb-api.md`](tmdb-api.md) — TMDB v3 API reference (auth, endpoints, response schemas, live-verified edge cases)
- [`tvdb-api.md`](tvdb-api.md) — TVDB v4 API reference (auth, endpoints, artwork/source types, live-verified edge cases)
- [`ffprobe-api.md`](ffprobe-api.md) — ffprobe streamdetails extraction, codec/language → Kodi mapping

Library deep-dives kept as archived legacy references (`docs/archive/legacy-alpha/`):

- `docs/archive/legacy-alpha/guessit-evaluation.md` — media-name parsing, real-world tests, regex comparison
- `docs/archive/legacy-alpha/rapidfuzz-reference.md` — fuzzy title matching, scorers, custom media processor
- `docs/archive/legacy-alpha/tenacity-reference.md` — API-call retry, backoff, TMDB/TVDB rate limits
- `docs/archive/legacy-alpha/rich-reference.md` — CLI output, progress bars, tables, theming
- `docs/archive/legacy-alpha/structlog-reference.md` — structured JSON logging, context binding, dev/prod auto-switch

## Versioning Hygiene

`git filter-repo` works on this repo but `.git/config` is read-only (macOS permissions) — remote removal error is cosmetic, re-add remote after if needed.
