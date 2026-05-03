# Phase 5 Inventory — `scraper/scraper.py`

Generated before splitting `personalscraper/scraper/scraper.py`.

## Current Symbols

Module constants:

- `_FOLDER_PATTERN`
- `_SXXEXX_RE`
- `_EPISODE_STRICT_RE`
- `_EPISODE_FALLBACK_RE`

Top-level functions/classes:

- `_merge_dirs` — `rename_service`
- `_rename_dir_case_safe` — `rename_service`
- `ScrapeResult` — `_shared`
- `_parse_folder_name` — `classifier`
- `_find_video_file` — `_shared`
- `_cleanup_stale_files` — `rename_service`
- `_cleanup_empty_release_dirs` — `rename_service`
- `_local_show_seasons` — `existing_validator`
- `_infer_year_from_child_names` — `existing_validator`
- `verify_tvshow_scrape_drift` — `existing_validator`
- `_tvdb_series_to_show_data` — `tv_service`
- `Scraper` — split into mixins/services plus final façade class

`Scraper` methods:

- `__init__` — `orchestrator`
- `_to_tvdb_language` — `tv_service`
- `_classify_item` — `classifier`
- `_resolve_title` — `_shared` or `orchestrator`
- `_strip_trailing_year` — `_shared`
- `_check_missing_movie_artwork` — `existing_validator`
- `_check_missing_tvshow_artwork` — `existing_validator`
- `_extract_tmdb_id_from_nfo` — `existing_validator`
- `_recover_movie_artwork` — `existing_validator`
- `_recover_tvshow_artwork` — `existing_validator`
- `_repair_movie_dir` — `existing_validator`
- `_verify_existing_scrape` — `existing_validator`
- `_repair_tvshow_dir` — `existing_validator`
- `scrape_movie` — `movie_service`
- `process_movies` — `orchestrator`
- `scrape_tvshow` — `tv_service`
- `_download_episode_thumb` — `tv_service`
- `_generate_episode_nfos` — `tv_service`
- `process_tvshows` — `orchestrator`

## External Consumers

Production imports:

- `personalscraper/scraper/run.py` imports `Scraper`, `ScrapeResult`, `verify_tvshow_scrape_drift`, and `_parse_folder_name`.
- `personalscraper/process/reclean.py` imports `_merge_dirs`.
- `personalscraper/process/dedup.py` imports `_merge_dirs`.

Tests importing public symbols from `personalscraper.scraper.scraper`:

- `tests/scraper/test_scraper.py`
- `tests/scraper/test_run_scrape.py`
- `tests/scraper/test_resolve_title.py`
- `tests/resilience/test_scrape_recovery.py`
- `tests/test_resilience_helpers.py`
- `tests/process/test_dedup.py`

Tests patching `personalscraper.scraper.scraper` attributes:

- `TMDBClient`
- `TVDBClient`
- `match_movie`
- `match_tvshow`
- `extract_stream_info`
- `_merge_dirs`
- `_classifier.classify`

Integration fixtures patch:

- `personalscraper.scraper.scraper.TMDBClient`
- `personalscraper.scraper.scraper.TVDBClient`

## Compatibility Requirements

- `personalscraper.scraper.scraper` must remain a façade with all historic symbols.
- Service code must resolve patch-sensitive collaborators through the façade at runtime where tests patch the old module path.
- `Scraper` must remain importable from `personalscraper.scraper.scraper`.
- `ScrapeResult`, `_merge_dirs`, `_parse_folder_name`, `_find_video_file`, `_cleanup_stale_files`, `_cleanup_empty_release_dirs`, `_is_nfo_complete`, and `verify_tvshow_scrape_drift` must keep their old import path.
- TVDB-primary matching and TV NFO canonical-id rules are already covered by `tests/scraper/test_confidence.py` and `tests/scraper/test_api_guardrails.py`; phase 5 must preserve those contracts.

## Extraction Strategy

Use mixin/service modules to avoid changing external construction:

- `_shared.py` for dataclasses and cross-service helpers.
- `rename_service.py` for filesystem merge/rename helpers.
- `classifier.py` for folder parsing and category classification helpers.
- `existing_validator.py` for repair/re-validation helpers.
- `movie_service.py` for movie scrape methods.
- `tv_service.py` for TV scrape methods.
- `orchestrator.py` for `Scraper.__init__`, batch processing methods, and the final `Scraper` class composing mixins.

Keep `scraper.py` as a re-export shell.
