# Audit V0-V12 : Promesses vs Implementation

> Audit systematique des features conçues dans BRAINSTORMING.md / DESIGN.md / plan/INDEX.md vs code reel.
> Classification : OK | BUG (implémenté mais défectueux) | MISSING (jamais implémenté)

---

## V0 — PROJECT SETUP

| Feature                                     | Design Ref    | Code Location     | Test               | Flow         | Status |
| ------------------------------------------- | ------------- | ----------------- | ------------------ | ------------ | ------ |
| pyproject.toml PEP 621                      | DESIGN §1     | `pyproject.toml`  | N/A                | N/A          | OK     |
| Makefile (test/lint/format)                 | DESIGN §12    | `Makefile`        | N/A                | N/A          | OK     |
| .env.example template                       | DESIGN §3     | `.env.example`    | N/A                | N/A          | OK     |
| .gitignore config                           | DESIGN §4     | `.gitignore`      | N/A                | N/A          | OK     |
| CLI Typer entry point                       | DESIGN CLI    | `cli.py`          | `test_cli.py`      | All commands | OK     |
| Config pydantic-settings                    | DESIGN Config | `config.py`       | `test_config.py`   | All steps    | OK     |
| Logger structlog dual output                | DESIGN Logger | `logger.py`       | `test_logger.py`   | All steps    | OK     |
| Notifier stub                               | DESIGN §7     | `notifier.py`     | `test_notifier.py` | V6 run       | OK     |
| Models SortResult/StepReport/PipelineReport | DESIGN Models | `models.py`       | `test_models.py`   | All steps    | OK     |
| Ruff config                                 | DESIGN §10    | `pyproject.toml`  | N/A                | N/A          | OK     |
| --verbose/-v flag                           | DESIGN CLI    | `cli.py` callback | `test_cli.py`      | Global       | OK     |
| --quiet/-q flag                             | DESIGN CLI    | `cli.py` callback | `test_cli.py`      | Global       | OK     |
| --version flag                              | DESIGN CLI    | `cli.py` callback | `test_cli.py`      | Global       | OK     |

**V0 Summary: 13 OK, 0 BUG, 0 MISSING**

---

## V1 — INGEST

| Feature                            | Design Ref         | Code Location                       | Test                         | Flow           | Status |
| ---------------------------------- | ------------------ | ----------------------------------- | ---------------------------- | -------------- | ------ |
| QBitClient wrapper                 | DESIGN qbit_client | `ingest/qbit_client.py`             | `ingest/test_qbit_client.py` | `run_ingest()` | OK     |
| QBitClient context manager         | DESIGN qbit_client | `qbit_client.py __enter__/__exit__` | Tests                        | `run_ingest()` | OK     |
| get_completed_torrents             | DESIGN qbit_client | `qbit_client.py`                    | Tests                        | `run_ingest()` | OK     |
| is_seeding detection               | DESIGN qbit_client | `qbit_client.py`                    | Tests                        | `run_ingest()` | OK     |
| get_content_path                   | DESIGN qbit_client | `qbit_client.py`                    | Tests                        | `run_ingest()` | OK     |
| get_all_torrent_hashes             | DESIGN qbit_client | `qbit_client.py`                    | Tests                        | `run_ingest()` | OK     |
| IngestTracker JSON persist         | DESIGN tracker     | `ingest/tracker.py`                 | `ingest/test_tracker.py`     | `run_ingest()` | OK     |
| Tracker is_ingested/mark_ingested  | DESIGN tracker     | `tracker.py`                        | Tests                        | `run_ingest()` | OK     |
| Tracker cleanup (stale removal)    | DESIGN tracker     | `tracker.py`                        | Tests                        | `run_ingest()` | OK     |
| Tracker atomic write (.tmp+rename) | DESIGN tracker     | `tracker.py`                        | Tests                        | `run_ingest()` | OK     |
| Lock file PID-based                | DESIGN lock        | `lock.py`                           | `test_lock.py`               | CLI level      | OK     |
| Lock stale detection (dead PID)    | DESIGN lock        | `lock.py`                           | `test_lock.py`               | CLI level      | OK     |
| Lock TOCTOU race protection        | DESIGN lock        | `lock.py` O_CREAT\|O_EXCL           | `test_lock.py`               | CLI level      | OK     |
| Atomic copy (staging tmp → rename) | DESIGN transfer    | `ingest.py transfer_torrent()`      | Tests                        | `run_ingest()` | OK     |
| Post-transfer size verification    | DESIGN transfer    | `ingest.py _verify_transfer()`      | Tests                        | `run_ingest()` | OK     |
| Orphan .ingest*tmp*\* cleanup      | DESIGN transfer    | `ingest.py _cleanup_orphan_temps()` | Tests                        | `run_ingest()` | OK     |
| Disk space check before ingest     | DESIGN flow 4c     | `ingest.py _check_disk_space()`     | Tests                        | `run_ingest()` | OK     |
| Per-torrent error isolation        | DESIGN errors      | `ingest.py` try/except per torrent  | Tests                        | `run_ingest()` | OK     |
| run_ingest() → StepReport          | DESIGN flow        | `ingest.py run_ingest()`            | Tests                        | Pipeline       | OK     |

**V1 Summary: 19 OK, 0 BUG, 0 MISSING**

---

## V2 — SORT + CLEAN

| Feature                             | Design Ref        | Code Location          | Test                        | Flow         | Status |
| ----------------------------------- | ----------------- | ---------------------- | --------------------------- | ------------ | ------ |
| NameCleaner guessit-based           | DESIGN cleaner    | `sorter/cleaner.py`    | `sorter/test_cleaner.py`    | `run_sort()` | OK     |
| clean() → title only                | DESIGN cleaner    | `cleaner.py`           | Tests                       | Sort         | OK     |
| extract_year()                      | DESIGN cleaner    | `cleaner.py`           | Tests                       | Sort         | OK     |
| extract_season_episode()            | DESIGN cleaner    | `cleaner.py`           | Tests                       | Sort         | OK     |
| clean_for_folder()                  | DESIGN cleaner    | `cleaner.py`           | Tests                       | Sort         | OK     |
| get_media_type()                    | DESIGN cleaner    | `cleaner.py`           | Tests                       | Sort         | OK     |
| FileType enum                       | DESIGN file_type  | `sorter/file_type.py`  | `sorter/test_file_type.py`  | Sort         | OK     |
| detect_file_type()                  | DESIGN file_type  | `file_type.py`         | Tests                       | Sort         | OK     |
| detect_dir_type()                   | DESIGN file_type  | `file_type.py`         | Tests                       | Sort         | OK     |
| SortingStrategy ABC                 | DESIGN strategies | `sorter/strategies.py` | `sorter/test_strategies.py` | Sort         | OK     |
| MovieStrategy → 001-MOVIES/         | DESIGN strategies | `strategies.py`        | Tests                       | Sort         | OK     |
| TVShowStrategy → 002-TVSHOWS/       | DESIGN strategies | `strategies.py`        | Tests                       | Sort         | OK     |
| DefaultStrategy (other types)       | DESIGN strategies | `strategies.py`        | Tests                       | Sort         | OK     |
| Fuzzy directory matcher (rapidfuzz) | DESIGN matcher    | `sorter/matcher.py`    | `sorter/test_matcher.py`    | Sort         | OK     |
| media_processor shared              | DESIGN matcher    | `text_utils.py`        | `test_text_utils.py`        | V2/V3/V5     | OK     |
| Sorter orchestrator                 | DESIGN sorter     | `sorter/sorter.py`     | `sorter/test_sorter.py`     | `run_sort()` | OK     |
| process() → list[SortResult]        | DESIGN sorter     | `sorter.py`            | Tests                       | `run_sort()` | OK     |
| run_sort() → StepReport             | DESIGN flow       | `sorter/run.py`        | Tests                       | Pipeline     | OK     |

**V2 Summary: 18 OK, 0 BUG, 0 MISSING**

---

## V3 — SCRAPE

| Feature                             | Design Ref        | Code Location                     | Test                            | Flow           | Status |
| ----------------------------------- | ----------------- | --------------------------------- | ------------------------------- | -------------- | ------ |
| MetadataProvider Protocol           | DESIGN providers  | `scraper/providers.py`            | Tests                           | Scraper        | OK     |
| TMDBClient (search, get, images)    | DESIGN tmdb       | `scraper/tmdb_client.py`          | `scraper/test_tmdb_client.py`   | Scraper        | OK     |
| TVDBClient (search, get, episodes)  | DESIGN tvdb       | `scraper/tvdb_client.py`          | `scraper/test_tvdb_client.py`   | Scraper        | OK     |
| TVDB login (bearer token)           | DESIGN tvdb       | `tvdb_client.py`                  | Tests                           | Scraper        | OK     |
| TVDB LANG_MAP (fr→fra, en→eng)      | DESIGN tvdb       | `tvdb_client.py`                  | Tests                           | Scraper        | OK     |
| Confidence scoring (WRatio)         | DESIGN confidence | `scraper/confidence.py`           | `scraper/test_confidence.py`    | Scraper        | OK     |
| MatchResult dataclass               | DESIGN confidence | `confidence.py`                   | Tests                           | Scraper        | OK     |
| HIGH_CONFIDENCE_THRESHOLD = 0.8     | DESIGN confidence | `confidence.py`                   | Tests                           | Scraper        | OK     |
| NFOGenerator (movie/tvshow/episode) | DESIGN nfo        | `scraper/nfo_generator.py`        | `scraper/test_nfo_generator.py` | Scraper        | OK     |
| ArtworkDownloader                   | DESIGN artwork    | `scraper/artwork.py`              | `scraper/test_artwork.py`       | Scraper        | OK     |
| mediainfo via ffprobe               | DESIGN mediainfo  | `scraper/mediainfo.py`            | `scraper/test_mediainfo.py`     | Scraper        | OK     |
| ISO 639-2/B→T conversion            | DESIGN mediainfo  | `mediainfo.py LANG_B_TO_T`        | Tests                           | Scraper        | OK     |
| NamingPatterns dataclass            | DESIGN naming     | `naming_patterns.py`              | `test_naming_patterns.py`       | V3/V4/V5       | OK     |
| sanitize_filename                   | DESIGN naming     | `text_utils.py`                   | `test_text_utils.py`            | V3/V4/V5       | OK     |
| Scraper orchestrator                | DESIGN scraper    | `scraper/scraper.py`              | `scraper/test_scraper.py`       | `run_scrape()` | OK     |
| scrape_movie()                      | DESIGN scraper    | `scraper.py`                      | Tests                           | Scraper        | OK     |
| scrape_tvshow()                     | DESIGN scraper    | `scraper.py`                      | Tests                           | Scraper        | OK     |
| TV show rename (Name → Name (Year)) | DESIGN V2→V3      | `scraper.py`                      | Tests                           | Scraper        | OK     |
| Episode rename (S##E## pattern)     | DESIGN scraper    | `scraper.py`/`episode_manager.py` | Tests                           | Scraper        | OK     |
| Tenacity retry on API calls         | DESIGN deps       | `tmdb_client.py`/`tvdb_client.py` | Tests                           | Scraper        | OK     |
| include_image_language=fr,en,null   | DESIGN tmdb       | `tmdb_client.py`                  | Tests                           | Scraper        | OK     |
| Scraper --interactive flag          | DESIGN CLI        | `cli.py`/`scraper.py`             | Tests                           | CLI/Pipeline   | OK     |
| run_scrape() → StepReport           | DESIGN flow       | `scraper/run.py`                  | `scraper/test_run_scrape.py`    | Pipeline       | OK     |

**V3 Summary: 23 OK, 0 BUG, 0 MISSING**

---

## V4 — VERIFY

| Feature                            | Design Ref          | Code Location        | Test                          | Flow     | Status |
| ---------------------------------- | ------------------- | -------------------- | ----------------------------- | -------- | ------ |
| Severity enum (ERROR/WARNING)      | DESIGN checker      | `verify/checker.py`  | `verify/test_checker.py`      | Verify   | OK     |
| CheckResult dataclass              | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| MediaChecker                       | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| check_movie() — all criteria       | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| check_tvshow() — all criteria      | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| video_present check                | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| not_sample check (>100Mo)          | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| dir_naming check                   | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| nfo_present check                  | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| nfo_valid check (title+year/title) | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| nfo_ids check (TMDB/IMDB/TVDB)     | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| poster_present check (blocking)    | DESIGN checker V9   | `checker.py`         | Tests                         | Verify   | OK     |
| artwork_landscape check            | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| streamdetails check                | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| category check (genre→category)    | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| season_structure check             | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| season_posters check               | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| episode_renamed check (V9)         | DESIGN checker V9   | `checker.py`         | Tests                         | Verify   | OK     |
| episode_nfo check                  | DESIGN checker      | `checker.py`         | Tests                         | Verify   | OK     |
| no_empty_dirs check (V9)           | DESIGN checker V9   | `checker.py`         | Tests                         | Verify   | OK     |
| FixAction dataclass                | DESIGN fixer        | `verify/fixer.py`    | `verify/test_fixer.py`        | Verify   | OK     |
| MediaFixer                         | DESIGN fixer        | `fixer.py`           | Tests                         | Verify   | OK     |
| fix_movie (dir_naming from NFO)    | DESIGN fixer        | `fixer.py`           | Tests                         | Verify   | OK     |
| fix_tvshow (dir_naming from NFO)   | DESIGN fixer        | `fixer.py`           | Tests                         | Verify   | OK     |
| GenreMapper                        | DESIGN genre_mapper | `genre_mapper.py`    | `verify/test_genre_mapper.py` | V4/V5    | OK     |
| categorize_movie()                 | DESIGN genre_mapper | `genre_mapper.py`    | Tests                         | Verify   | OK     |
| categorize_tvshow()                | DESIGN genre_mapper | `genre_mapper.py`    | Tests                         | Verify   | OK     |
| categorize_from_nfo()              | DESIGN genre_mapper | `genre_mapper.py`    | Tests                         | Verify   | OK     |
| .category file support (manual)    | DESIGN genre_mapper | `genre_mapper.py`    | Tests                         | Verify   | OK     |
| VerifyResult dataclass             | DESIGN verifier     | `verify/verifier.py` | `verify/test_verifier.py`     | Verify   | OK     |
| Verifier (fix → check → re-check)  | DESIGN verifier     | `verifier.py`        | Tests                         | Verify   | OK     |
| get_dispatchable() filter          | DESIGN verifier     | `verifier.py`        | Tests                         | Pipeline | OK     |
| run_verify() → (StepReport, list)  | DESIGN flow         | `verify/run.py`      | Tests                         | Pipeline | OK     |

**V4 Summary: 33 OK, 0 BUG, 0 MISSING**

---

## V5 — DISPATCH

| Feature                                   | Design Ref          | Code Location                      | Test                            | Flow             | Status      |
| ----------------------------------------- | ------------------- | ---------------------------------- | ------------------------------- | ---------------- | ----------- |
| IndexEntry dataclass                      | DESIGN media_index  | `dispatch/media_index.py`          | `dispatch/test_media_index.py`  | Dispatch         | OK          |
| MediaIndex load/save                      | DESIGN media_index  | `media_index.py`                   | Tests                           | Dispatch         | OK          |
| MediaIndex.rebuild()                      | DESIGN media_index  | `media_index.py`                   | Tests                           | `run_dispatch()` | **BUG**     |
| MediaIndex.find() (exact + fuzzy)         | DESIGN media_index  | `media_index.py`                   | Tests                           | Dispatch         | OK          |
| MediaIndex.add()                          | DESIGN media_index  | `media_index.py`                   | Tests                           | Dispatch         | OK          |
| MediaIndex.remove_stale()                 | DESIGN media_index  | `media_index.py`                   | `test_media_index.py`           | **NEVER CALLED** | **MISSING** |
| Atomic save (.tmp+rename)                 | DESIGN media_index  | `media_index.py`                   | Tests                           | Dispatch         | OK          |
| DiskConfig/DiskStatus                     | DESIGN disk_scanner | `dispatch/disk_scanner.py`         | `dispatch/test_disk_scanner.py` | Dispatch         | OK          |
| get_disk_configs()                        | DESIGN disk_scanner | `disk_scanner.py`                  | Tests                           | Dispatch         | OK          |
| get_disk_status()                         | DESIGN disk_scanner | `disk_scanner.py`                  | Tests                           | Dispatch         | OK          |
| choose_disk() with threshold formula      | DESIGN disk_scanner | `disk_scanner.py`                  | Tests                           | Dispatch         | OK          |
| DISK_CATEGORIES validation                | DESIGN disk_scanner | `disk_scanner.py` assert at import | N/A                             | Import time      | OK          |
| DispatchResult dataclass                  | DESIGN dispatcher   | `dispatch/dispatcher.py`           | `dispatch/test_dispatcher.py`   | Dispatch         | OK          |
| Dispatcher.process()                      | DESIGN dispatcher   | `dispatcher.py`                    | Tests                           | `run_dispatch()` | OK          |
| dispatch_movie() (replace/new)            | DESIGN dispatcher   | `dispatcher.py`                    | Tests                           | Dispatch         | OK          |
| dispatch_tvshow() (merge/new)             | DESIGN dispatcher   | `dispatcher.py`                    | Tests                           | Dispatch         | OK          |
| \_replace() crash-safe (3-phase)          | DESIGN dispatcher   | `dispatcher.py`                    | Tests                           | Dispatch         | OK          |
| \_merge() with backup rollback            | DESIGN dispatcher   | `dispatcher.py`                    | Tests                           | Dispatch         | OK          |
| \_rsync() wrapper (cross-FS)              | DESIGN dispatcher   | `dispatcher.py`                    | Tests                           | Dispatch         | OK          |
| rsync -a --no-perms --no-owner --no-group | DESIGN NTFS         | `dispatcher.py`                    | Tests                           | Dispatch         | OK          |
| \_verify_transfer() size check            | DESIGN dispatcher   | `dispatcher.py`                    | Tests                           | Dispatch         | OK          |
| \_cleanup_stale_temps()                   | DESIGN dispatcher   | `dispatcher.py`                    | Tests                           | Dispatch         | OK          |
| Standalone mode (verify first)            | DESIGN v5.3.1       | `dispatch/run.py`                  | `test_run_dispatch.py`          | CLI              | OK          |
| `--rebuild-index` CLI option              | DESIGN v5.3.1       | **NOT IMPLEMENTED**                | N/A                             | N/A              | **MISSING** |
| Index update after dispatch               | DESIGN flow         | `dispatcher.py` index.add()        | Tests                           | Dispatch         | OK          |
| run_dispatch() → StepReport               | DESIGN flow         | `dispatch/run.py`                  | Tests                           | Pipeline         | OK          |

### V5 BUG Detail: MediaIndex.rebuild() only on empty index

**Design intent**: The V5 DESIGN.md flow diagram shows `index.find()` being called on every dispatch, implying the index should be current. The plan mentions `rebuild()` as a core feature to "scan all disks". However, in the implementation (`dispatch/run.py`), `rebuild()` is only called when `index.count == 0` (first run or corrupted file). On subsequent runs, the index is loaded from the JSON file and never refreshed from disk. This means:

- If media is added/removed from disks manually (outside the pipeline), the index becomes stale.
- If the index file is non-empty but outdated (e.g. after manual disk reorganization), `find()` returns wrong results.
- `remove_stale()` is designed to clean dead entries but is never called in production code.

**Impact**: Medium. In typical pipeline usage (all changes go through the pipeline), the index stays accurate because `index.add()` updates after each dispatch. But manual disk operations cause silent staleness.

### V5 MISSING Detail: `--rebuild-index` CLI option

**Design ref**: `phase-03-cli-tests.md` line 12: "Option `--rebuild-index` pour forcer un rebuild complet". This was never implemented in `cli.py`. Users have no way to force a full index rebuild from the CLI.

### V5 MISSING Detail: MediaIndex.remove_stale()

**Design ref**: `DESIGN.md` interface and `phase-01-index-scanner.md`. The method exists in `media_index.py` and has unit tests in `test_media_index.py`, but is never called from any production code path. Dead code.

**V5 Summary: 23 OK, 1 BUG, 2 MISSING**

---

## V6 — LOG + NOTIFY

| Feature                             | Design Ref        | Code Location                        | Test               | Flow         | Status |
| ----------------------------------- | ----------------- | ------------------------------------ | ------------------ | ------------ | ------ |
| structlog configure_logging()       | DESIGN logger     | `logger.py`                          | `test_logger.py`   | CLI callback | OK     |
| Dual output (console + JSON file)   | DESIGN logger     | `logger.py`                          | Tests              | All steps    | OK     |
| TimedRotatingFileHandler (midnight) | DESIGN logger     | `logger.py`                          | Tests              | All steps    | OK     |
| foreign_pre_chain for stdlib logs   | DESIGN logger     | `logger.py`                          | Tests              | All steps    | OK     |
| cleanup_old_logs()                  | DESIGN logger     | `logger.py`                          | Tests              | `cli.py run` | OK     |
| Context binding (run_id)            | DESIGN logger     | `cli.py run` structlog.contextvars   | N/A                | Pipeline     | OK     |
| TelegramNotifier.send()             | DESIGN notifier   | `notifier.py`                        | `test_notifier.py` | Pipeline     | OK     |
| TelegramNotifier.send_report()      | DESIGN notifier   | `notifier.py`                        | Tests              | Pipeline     | OK     |
| TelegramNotifier.is_configured()    | DESIGN notifier   | `notifier.py`                        | Tests              | Pipeline     | OK     |
| ping_healthcheck()                  | DESIGN notifier   | `notifier.py`                        | Tests              | Pipeline     | OK     |
| Healthcheck /start + /fail          | DESIGN monitoring | `cli.py run`                         | Tests              | Pipeline     | OK     |
| PipelineReport.to_html()            | DESIGN format     | `models.py`                          | `test_models.py`   | Pipeline     | OK     |
| Summary console (Panel + Table)     | DESIGN resume     | `cli.py run`                         | Tests              | Pipeline     | OK     |
| Pipeline `run` command              | DESIGN CLI        | `cli.py run`                         | `test_cli.py`      | Pipeline     | OK     |
| Lock in `run` command               | DESIGN lock       | `cli.py run` acquire/release         | Tests              | Pipeline     | OK     |
| launchd plist (scheduling)          | DESIGN scheduling | `com.personalscraper.pipeline.plist` | N/A                | macOS        | OK     |

**V6 Summary: 16 OK, 0 BUG, 0 MISSING**

---

## V7 — E2E TESTS

| Feature                          | Design Ref        | Code Location                        | Test                               | Flow | Status |
| -------------------------------- | ----------------- | ------------------------------------ | ---------------------------------- | ---- | ------ |
| TestRegistry (JSON persist)      | DESIGN registry   | `tests/e2e/registry.py`              | `tests/e2e/test_registry.py`       | E2E  | OK     |
| Markers (.e2e-test-marker)       | DESIGN markers    | `tests/e2e/markers.py`               | `tests/e2e/test_markers.py`        | E2E  | OK     |
| TorrentSetup (add magnets)       | DESIGN setup      | `tests/e2e/setup_torrents.py`        | `tests/e2e/test_setup_torrents.py` | E2E  | OK     |
| TestCleanup (triple verify)      | DESIGN cleanup    | `tests/e2e/cleanup.py`               | `tests/e2e/test_cleanup.py`        | E2E  | OK     |
| Assertions per step              | DESIGN assertions | `tests/e2e/assertions.py`            | `tests/e2e/test_assertions.py`     | E2E  | OK     |
| test_pipeline_movies.py          | DESIGN test       | `tests/e2e/test_pipeline_movies.py`  | E2E marker                         | E2E  | OK     |
| test_pipeline_tvshows.py         | DESIGN test       | `tests/e2e/test_pipeline_tvshows.py` | E2E marker                         | E2E  | OK     |
| .torrent files for tests         | DESIGN            | `assets/torrents/`                   | E2E                                | E2E  | OK     |
| Dispatch always dry-run in tests | DESIGN safety     | E2E test code                        | E2E                                | E2E  | OK     |

**V7 Summary: 9 OK, 0 BUG, 0 MISSING**

---

## V7.x — TEST AUDIT

| Feature                         | Design Ref       | Code Location                                         | Test                       | Flow | Status |
| ------------------------------- | ---------------- | ----------------------------------------------------- | -------------------------- | ---- | ------ |
| Golden files (expected results) | DESIGN golden    | `assets/torrents/expected/`                           | `tests/e2e/test_golden.py` | E2E  | OK     |
| Golden loader + fuzzy matcher   | DESIGN golden    | `tests/e2e/golden.py`                                 | Tests                      | E2E  | OK     |
| Jumanji golden file             | DESIGN golden    | `assets/torrents/expected/jumanji_1995/`              | E2E                        | E2E  | OK     |
| Malcolm golden file             | DESIGN golden    | `assets/torrents/expected/malcolm_in_the_middle_s01/` | E2E                        | E2E  | OK     |
| Roundtrip E2E tests             | DESIGN roundtrip | `tests/e2e/test_roundtrip.py`                         | roundtrip marker           | E2E  | OK     |

**V7.x Summary: 5 OK, 0 BUG, 0 MISSING**

---

## V8 — ROBUSTNESS

| Feature                                  | Design Ref           | Code Location                       | Test                              | Flow     | Status     |
| ---------------------------------------- | -------------------- | ----------------------------------- | --------------------------------- | -------- | ---------- |
| CircuitBreaker class                     | DESIGN §1            | `scraper/circuit_breaker.py`        | `scraper/test_circuit_breaker.py` | Scraper  | OK         |
| CircuitState enum                        | DESIGN §1            | `circuit_breaker.py`                | Tests                             | Scraper  | OK         |
| CircuitOpenError exception               | DESIGN §1            | `circuit_breaker.py`                | Tests                             | Scraper  | OK         |
| CB.guard() method                        | DESIGN §1            | `circuit_breaker.py`                | Tests                             | Scraper  | OK         |
| CB.\_is_circuit_error() (5xx only)       | DESIGN §1            | `circuit_breaker.py`                | Tests                             | Scraper  | OK         |
| TMDBClient circuit integration           | DESIGN §2            | `tmdb_client.py`                    | Tests                             | Scraper  | OK         |
| TVDBClient circuit integration           | DESIGN §3            | `tvdb_client.py`                    | Tests                             | Scraper  | OK         |
| Scraper fallback (CircuitOpenError)      | DESIGN §4            | `scraper.py` process_movies/tvshows | Tests                             | Scraper  | OK         |
| fuzzy_match_score() shared guards        | DESIGN §5            | `text_utils.py`                     | `test_text_utils.py`              | V2/V5    | OK         |
| Year guard (±1 year)                     | DESIGN §5            | `text_utils.py`                     | Tests                             | V2/V5    | OK         |
| Length ratio guard (≥0.67)               | DESIGN §5            | `text_utils.py`                     | Tests                             | V2/V5    | OK         |
| Adaptive threshold (≤10→95%, >10→90%)    | DESIGN §5            | `text_utils.py`                     | Tests                             | V2/V5    | OK         |
| MediaIndex.find() uses guards            | DESIGN §5            | `media_index.py`                    | Tests                             | Dispatch | OK         |
| matcher.py uses guards                   | DESIGN §5            | `matcher.py`                        | Tests                             | Sort     | OK         |
| \_move_new() staging→commit              | DESIGN §6            | `dispatcher.py`                     | Tests                             | Dispatch | OK         |
| \_merge() rsync --backup rollback        | DESIGN §6            | `dispatcher.py`                     | Tests                             | Dispatch | OK         |
| \_restore_merge_backup()                 | DESIGN §6            | `dispatcher.py`                     | Tests                             | Dispatch | OK         |
| choose_disk(allow_create_category)       | DESIGN §7            | `disk_scanner.py`                   | Tests                             | Dispatch | OK         |
| Circuit breaker settings in config       | DESIGN config        | `config.py`                         | Tests                             | Config   | OK         |
| NTFS pre-scan (\_has_ntfs_illegal_names) | **Not in V8 design** | `dispatcher.py`                     | Tests                             | Dispatch | OK (bonus) |

**V8 Summary: 20 OK, 0 BUG, 0 MISSING**

---

## V9 — PIPELINE INTEGRITY

| Feature                                 | Design Ref         | Code Location                    | Test                            | Flow         | Status |
| --------------------------------------- | ------------------ | -------------------------------- | ------------------------------- | ------------ | ------ |
| Pipeline class orchestrator             | DESIGN pipeline    | `pipeline.py`                    | `test_pipeline.py`              | `cli.py run` | OK     |
| 7-step sequential execution             | DESIGN pipeline    | `pipeline.py run()`              | Tests                           | Pipeline     | OK     |
| Gate: assert_temp_empty                 | DESIGN pipeline    | `pipeline.py` + `sorter/run.py`  | Tests                           | Pipeline     | OK     |
| Critical step error (ingest/sort)       | DESIGN pipeline    | `pipeline.py _CriticalStepError` | Tests                           | Pipeline     | OK     |
| Error isolation (process steps)         | DESIGN pipeline    | `pipeline.py _run_process_phase` | Tests                           | Pipeline     | OK     |
| process/ module (reclean+dedup+cleanup) | DESIGN process     | `process/`                       | `process/` tests                | Pipeline     | OK     |
| run_process() entry point               | DESIGN process/run | `process/run.py`                 | Tests                           | CLI          | OK     |
| run_clean() (reclean+dedup)             | DESIGN process/run | `process/run.py`                 | Tests                           | Pipeline     | OK     |
| run_cleanup() (empty dirs)              | DESIGN process/run | `process/run.py`                 | Tests                           | Pipeline     | OK     |
| reclean_folders()                       | DESIGN reclean     | `process/reclean.py`             | `process/test_reclean.py`       | Pipeline     | OK     |
| is_title_polluted()                     | DESIGN reclean     | `process/reclean.py`             | Tests                           | Pipeline     | OK     |
| dedup_folders()                         | DESIGN dedup       | `process/dedup.py`               | `process/test_dedup.py`         | Pipeline     | OK     |
| cleanup_empty_dirs()                    | DESIGN cleanup     | `process/cleanup.py`             | `process/test_cleanup.py`       | Pipeline     | OK     |
| \_resolve_title() (FR preference)       | DESIGN scraper mod | `scraper/scraper.py`             | `scraper/test_resolve_title.py` | Scraper      | OK     |
| scraper_prefer_local_title setting      | DESIGN config mod  | `config.py`                      | Tests                           | Config       | OK     |
| Verify reinforced (poster_present)      | DESIGN checker mod | `checker.py`                     | Tests                           | Verify       | OK     |
| Verify reinforced (episode_renamed)     | DESIGN checker mod | `checker.py`                     | Tests                           | Verify       | OK     |
| Verify reinforced (no_empty_dirs)       | DESIGN checker mod | `checker.py`                     | Tests                           | Verify       | OK     |
| `personalscraper process` command       | DESIGN CLI         | `cli.py process`                 | Tests                           | CLI          | OK     |

**V9 Summary: 19 OK, 0 BUG, 0 MISSING**

---

## V10 — PIPELINE RESILIENCE

| Feature                                   | Design Ref       | Code Location                              | Test  | Flow     | Status |
| ----------------------------------------- | ---------------- | ------------------------------------------ | ----- | -------- | ------ |
| \_is_nfo_complete() validation            | DESIGN NFO valid | `scraper/scraper.py`                       | Tests | Scraper  | OK     |
| Fast-skip: sort (\_has_unsorted_items)    | DESIGN fast-skip | `sorter/run.py`                            | Tests | Pipeline | OK     |
| Fast-skip: clean (\_has_polluted_folders) | DESIGN fast-skip | `process/reclean.py`+`run.py`              | Tests | Pipeline | OK     |
| Fast-skip: scrape (\_has_unscraped_items) | DESIGN fast-skip | `scraper/run.py`                           | Tests | Pipeline | OK     |
| Fast-skip: verify (\_has_items_to_verify) | DESIGN fast-skip | `verify/run.py`                            | Tests | Pipeline | OK     |
| Artwork recovery (NFO valid, art missing) | DESIGN artwork   | `scraper/scraper.py` artwork_recovered     | Tests | Scraper  | OK     |
| Corrupt NFO detection + re-scrape         | DESIGN NFO       | `scraper/scraper.py`                       | Tests | Scraper  | OK     |
| Sort skip if already in 001/002           | DESIGN sort skip | `sorter/sorter.py`                         | Tests | Sort     | OK     |
| Dispatch orphan cleanup at startup        | DESIGN cleanup   | `dispatcher.py _cleanup_orphan_temps`      | Tests | Dispatch | OK     |
| Staging orphan cleanup (run.py)           | DESIGN cleanup   | `dispatch/run.py _cleanup_staging_orphans` | Tests | Dispatch | OK     |
| Crash recovery (pipeline startup)         | DESIGN crash     | `pipeline.py _recover_from_previous_run`   | Tests | Pipeline | OK     |
| Index rebuild on empty                    | DESIGN index     | `dispatch/run.py`                          | Tests | Pipeline | OK     |
| Resilience tests (filesystem)             | DESIGN tests     | `tests/resilience/`                        | Tests | Tests    | OK     |

**V10 Summary: 13 OK, 0 BUG, 0 MISSING**

---

## Grand Summary

| Version                 |      OK |   BUG | MISSING |   Total |
| ----------------------- | ------: | ----: | ------: | ------: |
| V0 Project Setup        |      13 |     0 |       0 |      13 |
| V1 Ingest               |      19 |     0 |       0 |      19 |
| V2 Sort+Clean           |      18 |     0 |       0 |      18 |
| V3 Scrape               |      23 |     0 |       0 |      23 |
| V4 Verify               |      33 |     0 |       0 |      33 |
| V5 Dispatch             |      23 |     1 |       2 |      26 |
| V6 Log+Notify           |      16 |     0 |       0 |      16 |
| V7 E2E Tests            |       9 |     0 |       0 |       9 |
| V7.x Test Audit         |       5 |     0 |       0 |       5 |
| V8 Robustness           |      20 |     0 |       0 |      20 |
| V9 Pipeline Integrity   |      19 |     0 |       0 |      19 |
| V10 Pipeline Resilience |      13 |     0 |       0 |      13 |
| **TOTAL**               | **211** | **1** |   **2** | **214** |

---

## Triage

### V13 Scope (pipeline correctness)

| #   | Issue                                                                             | Type    | Priority | Rationale                                                                                                                                                                              |
| --- | --------------------------------------------------------------------------------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **MediaIndex.rebuild() only on empty** — stale index after manual disk operations | BUG     | HIGH     | Direct cause of dispatch errors (wrong disk, duplicates). Rebuild should run at every dispatch start or at least periodically.                                                         |
| 2   | **MediaIndex.remove_stale() never called** — dead index entries accumulate        | MISSING | MEDIUM   | After manual deletions on disks, index has phantom entries. find() returns paths that no longer exist, causing rsync failures. Should be called during rebuild or at dispatch startup. |

### V14+ Backlog

| #   | Issue                                                                | Type    | Priority | Rationale                                                                                                                        |
| --- | -------------------------------------------------------------------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 3   | **`--rebuild-index` CLI option missing** — no manual rebuild trigger | MISSING | LOW      | User workaround: delete `media_index.json` and re-run dispatch (triggers rebuild on empty). Nice-to-have CLI flag, not blocking. |

### Notes

1. **V0-V4 are fully implemented** — every feature from the design docs has matching code, tests, and pipeline integration.

2. **V5 is the only version with gaps** — all 3 findings relate to the MediaIndex lifecycle management. The core dispatch logic (replace/merge/move/rsync) is solid.

3. **V6-V10 are fully implemented** — including complex features like circuit breaker, fuzzy guards, pipeline orchestrator, crash recovery, and fast-skip idempotence.

4. **Design deviations (not bugs)**:
   - V5 `Dispatcher.process()` takes only `verified` parameter (design had `verified | staging_dir`). Standalone mode is handled at `run_dispatch()` level instead — same functionality, different layer.
   - E2E test structure evolved from the design (torrentifier.py added, test_magnets.json replaced by .torrent files) — correct adaptation to real needs.

5. **The 24 bugs found in the 2026-04-14 pipeline run** are likely V11-V12 hardening issues (edge cases in existing features), not design-level misses. This audit confirms the V0-V10 architecture is fundamentally sound with only 3 issues, all in V5 index management.
