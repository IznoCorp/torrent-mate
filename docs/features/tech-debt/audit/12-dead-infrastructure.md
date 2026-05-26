# Audit — Dead infrastructure (SH-17 / CF-G / P11)

> **Sub-phase**: 8.4 (phase-08-polish.md)
> **Generated from**: `scripts/audit-dead-infrastructure.py`
> **DB audited**: `/Users/izno/dev/PersonnalScaper/.data/library.db`

> READ-ONLY inventory pass. The script writes this report and exits;
> it does NOT drop tables, columns, or code. Each finding is a
> CANDIDATE for review — false positives are expected (string
> dispatch, dynamic imports, deserialisation paths). Operator decides.

## Scan summary

- Tables scanned: **17**
- Columns scanned: **117**
- Module-level functions scanned: **600**
- Protocol classes scanned: **4**

- Empty-table findings: **2**
- Always-NULL column findings: **11**
- Dead function candidates: **261**
- Dead Protocol candidates: **2**

## A. Empty tables (`COUNT(*) == 0`)

| Table | Row count | Note |
| --- | ---: | --- |
| `deleted_item` | 0 | DROP candidate — verify no production wiring (cross-caller grep) |
| `pending_op` | 0 | KEEP — see audit/14-pending-op-item-issue.md (live hinted-handoff queue) |

**Phase 1 fix expectation** (plan §8.4): `deleted_item` should have rows
post-Phase 1 BDD work. If it appears in the table above, Phase 1 closure
did not wire deleted_item population — surface as a follow-up.

## B. Columns 100 % NULL in non-empty tables

| Table | Column | Total rows | NULL rows |
| --- | --- | ---: | ---: |
| `item_issue` | `detail` | 9 | 9 |
| `media_file` | `deleted_at` | 143070 | 143070 |
| `media_file` | `xxh3_full` | 143070 | 143070 |
| `media_file` | `xxh3_partial` | 143070 | 143070 |
| `media_item` | `date_metadata_refreshed` | 1937 | 1937 |
| `media_item` | `original_title` | 1937 | 1937 |
| `media_release` | `edition` | 27470 | 27470 |
| `media_release` | `primary_lang` | 27470 | 27470 |
| `media_release` | `quality` | 27470 | 27470 |
| `scan_event` | `file_id` | 51 | 51 |
| `scan_event` | `item_id` | 51 | 51 |

**Interpretation**: a column always NULL on a populated table is a
strong DROP candidate, but verify it is not a write-path that fires
rarely (per-disk, per-error, per-recovery). Check writers via
`rg --type py 'set <col>' personalscraper/`.

## C. Dead function candidates

Heuristic: name appears 0 times in any module other than its definition
module. Dunder methods, names in `__all__`, common framework hooks
(configure, main, model_dump, model_validate, register, setup, teardown), and class methods are skipped.

FALSE POSITIVE WARNING: a function called via
`getattr(module, name)`, dispatched by string from a registry, exposed
via Typer / Click decorators, or imported by a script under `scripts/`
will appear here. Verify with full-tree grep before any deletion.

Showing all 261 candidate(s):

| Name | File | Line |
| --- | --- | ---: |
| `resolve_active` | `personalscraper/api/_activation.py` | 41 |
| `_check_response` | `personalscraper/api/metadata/omdb.py` | 208 |
| `_sentinel` | `personalscraper/api/metadata/omdb.py` | 218 |
| `_parse_year` | `personalscraper/api/metadata/omdb.py` | 225 |
| `_parse_runtime` | `personalscraper/api/metadata/omdb.py` | 238 |
| `_parse_rating_value` | `personalscraper/api/metadata/omdb.py` | 248 |
| `_assert_list` | `personalscraper/api/metadata/trakt.py` | 245 |
| `_parse_related` | `personalscraper/api/metadata/trakt.py` | 356 |
| `_resolve_id` | `personalscraper/api/metadata/trakt.py` | 385 |
| `_parse_images` | `personalscraper/api/metadata/trakt.py` | 402 |
| `_check_lockout` | `personalscraper/api/torrent/qbittorrent.py` | 275 |
| `_set_lockout` | `personalscraper/api/torrent/qbittorrent.py` | 296 |
| `_as_list` | `personalscraper/api/tracker/c411.py` | 60 |
| `_attrs_to_dict` | `personalscraper/api/tracker/c411.py` | 69 |
| `_parse_rfc2822` | `personalscraper/api/tracker/c411.py` | 80 |
| `_enclosure_url` | `personalscraper/api/tracker/c411.py` | 270 |
| `_enclosure_length` | `personalscraper/api/tracker/c411.py` | 278 |
| `_parse_iso` | `personalscraper/api/tracker/lacale.py` | 223 |
| `init_config_cmd` | `personalscraper/commands/config.py` | 57 |
| `_backup_dir` | `personalscraper/commands/init_config.py` | 21 |
| `_prompt_for_values` | `personalscraper/commands/init_config.py` | 88 |
| `_print_reconcile_rich` | `personalscraper/commands/library/audit.py` | 136 |
| `_check_integrity` | `personalscraper/commands/library/doctor.py` | 146 |
| `_check_foreign_keys_pragma` | `personalscraper/commands/library/doctor.py` | 176 |
| `_check_fk_orphans` | `personalscraper/commands/library/doctor.py` | 202 |
| `_check_schema_version` | `personalscraper/commands/library/doctor.py` | 224 |
| `_check_no_stuck_scan_run` | `personalscraper/commands/library/doctor.py` | 261 |
| `_check_repair_queue_backlog` | `personalscraper/commands/library/doctor.py` | 302 |
| `_check_index_outbox_lag` | `personalscraper/commands/library/doctor.py` | 337 |
| `_check_merkle_drift` | `personalscraper/commands/library/doctor.py` | 384 |
| `_check_canonical_provider_populated` | `personalscraper/commands/library/doctor.py` | 422 |
| `_check_phantom_paths` | `personalscraper/commands/library/doctor.py` | 481 |
| `run_doctor` | `personalscraper/commands/library/doctor.py` | 528 |
| `_print_table` | `personalscraper/commands/library/doctor.py` | 653 |
| `_resolve_event_bus` | `personalscraper/commands/library/query.py` | 16 |
| `_print_search_table` | `personalscraper/commands/library/query.py` | 112 |
| `_print_show_sections` | `personalscraper/commands/library/query.py` | 154 |
| `library_backfill_ids` | `personalscraper/commands/library/scan.py` | 349 |
| `_run_help` | `personalscraper/commands/pipeline.py` | 21 |
| `torrents_list` | `personalscraper/commands/pipeline.py` | 462 |
| `_print_torrents_rich` | `personalscraper/commands/pipeline.py` | 523 |
| `_rule_matches` | `personalscraper/conf/classifier.py` | 267 |
| `_load_json5_file` | `personalscraper/conf/loader.py` | 98 |
| `_check_category_orphans` | `personalscraper/conf/loader.py` | 320 |
| `_decode_field_value` | `personalscraper/core/event_bus.py` | 58 |
| `_parse_retry_after` | `personalscraper/core/http_helpers.py` | 22 |
| `_retry_after_from_exception` | `personalscraper/core/http_helpers.py` | 58 |
| `_media_type_to_kind` | `personalscraper/dispatch/media_index.py` | 91 |
| `_kind_to_media_type` | `personalscraper/dispatch/media_index.py` | 103 |
| `_cleanup_staging_orphans` | `personalscraper/dispatch/run.py` | 30 |
| `_drain_dispatch_outbox` | `personalscraper/dispatch/run.py` | 203 |
| `_enrich_after_dispatch` | `personalscraper/dispatch/run.py` | 242 |
| `_check_movie` | `personalscraper/enforce/coherence_checker.py` | 76 |
| `_check_tvshow` | `personalscraper/enforce/coherence_checker.py` | 102 |
| `_check_nfo_ids` | `personalscraper/enforce/coherence_checker.py` | 131 |
| `_check_genre_coherence` | `personalscraper/enforce/coherence_checker.py` | 163 |
| `_has_illegal_chars` | `personalscraper/enforce/file_sanitizer.py` | 34 |
| `_sanitize_directory` | `personalscraper/enforce/file_sanitizer.py` | 79 |
| `_validate_movie` | `personalscraper/enforce/structure_validator.py` | 90 |
| `_move_orphan_episodes_to_seasons` | `personalscraper/enforce/structure_validator.py` | 163 |
| `_validate_tvshow` | `personalscraper/enforce/structure_validator.py` | 209 |
| `_normalise_subtitle_codec` | `personalscraper/indexer/_container_fastpath.py` | 304 |
| `get_active_bucket` | `personalscraper/indexer/_throttle.py` | 183 |
| `_find_ntfs_mount` | `personalscraper/indexer/db.py` | 179 |
| `_migration_version` | `personalscraper/indexer/db.py` | 568 |
| `reconcile_file` | `personalscraper/indexer/drift.py` | 132 |
| `reset_strikes_on_reappearance` | `personalscraper/indexer/drift.py` | 553 |
| `should_apply_drift_for_disk` | `personalscraper/indexer/drift.py` | 575 |
| `_str_or_none` | `personalscraper/indexer/mediainfo.py` | 277 |
| `_yesno_to_bool` | `personalscraper/indexer/mediainfo.py` | 289 |
| `_normalise_hdr_format` | `personalscraper/indexer/mediainfo.py` | 318 |
| `_detect_atmos` | `personalscraper/indexer/mediainfo.py` | 353 |
| `_normalise_subtitle_format` | `personalscraper/indexer/mediainfo.py` | 380 |
| `_int_or_none` | `personalscraper/indexer/mediainfo.py` | 413 |
| `_apply_move` | `personalscraper/indexer/outbox/_apply.py` | 33 |
| `_apply_nfo_write` | `personalscraper/indexer/outbox/_apply.py` | 106 |
| `_apply_artwork_write` | `personalscraper/indexer/outbox/_apply.py` | 198 |
| `_apply_trailer_download` | `personalscraper/indexer/outbox/_apply.py` | 282 |
| `_dedup_key` | `personalscraper/indexer/outbox/_drain.py` | 36 |
| `_rel_path_for_paranoia` | `personalscraper/indexer/outbox/_drain.py` | 72 |
| `_insert_outbox_scan_event` | `personalscraper/indexer/outbox/_drain.py` | 96 |
| `_create_drain_scan_run` | `personalscraper/indexer/outbox/_drain.py` | 164 |
| `_finish_drain_scan_run` | `personalscraper/indexer/outbox/_drain.py` | 202 |
| `_apply_row_with_retry` | `personalscraper/indexer/outbox/_drain.py` | 233 |
| `_replay_pending_ops` | `personalscraper/indexer/outbox/_drain.py` | 340 |
| `_tokenise` | `personalscraper/indexer/query.py` | 198 |
| `_parse_chunk` | `personalscraper/indexer/query.py` | 256 |
| `_compile_token` | `personalscraper/indexer/query.py` | 329 |
| `_compile_flex_token` | `personalscraper/indexer/query.py` | 466 |
| `_build_sql` | `personalscraper/indexer/query.py` | 516 |
| `_row_to_media_item` | `personalscraper/indexer/query.py` | 553 |
| `detect_dispatch_path_missing` | `personalscraper/indexer/reconcile.py` | 229 |
| `detect_enrich_stale` | `personalscraper/indexer/reconcile.py` | 256 |
| `detect_release_orphans` | `personalscraper/indexer/reconcile.py` | 282 |
| `detect_season_count_drift` | `personalscraper/indexer/reconcile.py` | 329 |
| `detect_items_without_files` | `personalscraper/indexer/reconcile.py` | 356 |
| `parse_season_dir` | `personalscraper/indexer/release_linker.py` | 40 |
| `parse_episode_number` | `personalscraper/indexer/release_linker.py` | 56 |
| `_parse_title_year` | `personalscraper/indexer/release_linker.py` | 80 |
| `find_item_for_path` | `personalscraper/indexer/release_linker.py` | 98 |
| `get_or_create_season` | `personalscraper/indexer/release_linker.py` | 179 |
| `get_or_create_episode` | `personalscraper/indexer/release_linker.py` | 203 |
| `get_or_create_default_release` | `personalscraper/indexer/release_linker.py` | 227 |
| `_row_to_disk` | `personalscraper/indexer/repos/disk_repo.py` | 34 |
| `_row_to_path` | `personalscraper/indexer/repos/disk_repo.py` | 55 |
| `update_mount_path` | `personalscraper/indexer/repos/disk_repo.py` | 170 |
| `insert_path` | `personalscraper/indexer/repos/disk_repo.py` | 301 |
| `get_path_by_id` | `personalscraper/indexer/repos/disk_repo.py` | 360 |
| `_row_to_file` | `personalscraper/indexer/repos/file_repo.py` | 34 |
| `_row_to_stream` | `personalscraper/indexer/repos/file_repo.py` | 62 |
| `increment_miss_strike` | `personalscraper/indexer/repos/file_repo.py` | 206 |
| `insert_stream` | `personalscraper/indexer/repos/file_repo.py` | 231 |
| `get_streams_for_file` | `personalscraper/indexer/repos/file_repo.py` | 274 |
| `_row_to_item` | `personalscraper/indexer/repos/item_repo.py` | 34 |
| `_row_to_attr` | `personalscraper/indexer/repos/item_repo.py` | 64 |
| `find_by_tmdb_id` | `personalscraper/indexer/repos/item_repo.py` | 155 |
| `get_by_title_and_kind` | `personalscraper/indexer/repos/item_repo.py` | 333 |
| `find_on_disk` | `personalscraper/indexer/repos/item_repo.py` | 408 |
| `_row_to_scan_run` | `personalscraper/indexer/repos/log_repo.py` | 34 |
| `_row_to_scan_event` | `personalscraper/indexer/repos/log_repo.py` | 56 |
| `_row_to_deleted_item` | `personalscraper/indexer/repos/log_repo.py` | 76 |
| `_sweep_stale_scan_runs` | `personalscraper/indexer/repos/log_repo.py` | 108 |
| `get_scan_run_by_id` | `personalscraper/indexer/repos/log_repo.py` | 213 |
| `_row_to_outbox` | `personalscraper/indexer/repos/outbox_repo.py` | 47 |
| `_row_to_pending_op` | `personalscraper/indexer/repos/outbox_repo.py` | 67 |
| `_row_to_repair_queue` | `personalscraper/indexer/repos/outbox_repo.py` | 86 |
| `insert_outbox_event` | `personalscraper/indexer/repos/outbox_repo.py` | 113 |
| `claim_pending_op` | `personalscraper/indexer/repos/outbox_repo.py` | 135 |
| `complete_pending_op` | `personalscraper/indexer/repos/outbox_repo.py` | 165 |
| `get_pending_op_by_id` | `personalscraper/indexer/repos/outbox_repo.py` | 219 |
| `get_repair_queue_by_id` | `personalscraper/indexer/repos/outbox_repo.py` | 308 |
| `_row_to_release` | `personalscraper/indexer/repos/release_repo.py` | 34 |
| `_row_to_season` | `personalscraper/indexer/repos/tv_repo.py` | 38 |
| `_row_to_episode` | `personalscraper/indexer/repos/tv_repo.py` | 57 |
| `insert_season` | `personalscraper/indexer/repos/tv_repo.py` | 79 |
| `get_season_by_id` | `personalscraper/indexer/repos/tv_repo.py` | 161 |
| `insert_episode` | `personalscraper/indexer/repos/tv_repo.py` | 183 |
| `get_episode_by_id` | `personalscraper/indexer/repos/tv_repo.py` | 205 |
| `get_episodes_for_season` | `personalscraper/indexer/repos/tv_repo.py` | 222 |
| `_capture_index_ddl` | `personalscraper/indexer/scanner/_index_ddl.py` | 18 |
| `_fetch_candidate_rows` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 216 |
| `_backfill_one` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 227 |
| `_fetch_cross_provider_ids` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 330 |
| `_fetch_ratings` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 435 |
| `_call_rating_client` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 475 |
| `_resolve_nfo_path` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 532 |
| `_parse_canonical_from_nfo` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 560 |
| `_parse_mount_output` | `personalscraper/indexer/scanner/_spotlight.py` | 37 |
| `_get_mount_output` | `personalscraper/indexer/scanner/_spotlight.py` | 70 |
| `detect_fs_type` | `personalscraper/indexer/scanner/_spotlight.py` | 89 |
| `_log_stat_failed` | `personalscraper/indexer/scanner/_walker.py` | 40 |
| `_check_field_naming_convention` | `personalscraper/indexer/schema.py` | 83 |
| `_human_bytes` | `personalscraper/info/run.py` | 54 |
| `_is_orphan_tracker_entry` | `personalscraper/ingest/ingest.py` | 32 |
| `_get_dir_size` | `personalscraper/ingest/ingest.py` | 91 |
| `_check_disk_space` | `personalscraper/ingest/ingest.py` | 179 |
| `transfer_torrent` | `personalscraper/ingest/ingest.py` | 195 |
| `_default_tracker_file` | `personalscraper/ingest/tracker.py` | 19 |
| `deduce_audio_profile` | `personalscraper/library/analyzer.py` | 309 |
| `_analyze_video_file` | `personalscraper/library/analyzer.py` | 350 |
| `_collect_files_for_item` | `personalscraper/library/analyzer.py` | 540 |
| `_file_analysis_from_index` | `personalscraper/library/analyzer.py` | 582 |
| `_publish_deleted` | `personalscraper/library/disk_cleaner.py` | 117 |
| `_delete_dir` | `personalscraper/library/disk_cleaner.py` | 229 |
| `_delete_file` | `personalscraper/library/disk_cleaner.py` | 295 |
| `_has_main_video` | `personalscraper/library/disk_cleaner.py` | 344 |
| `_looks_like_main_video` | `personalscraper/library/disk_cleaner.py` | 383 |
| `_is_orphan_release_dir` | `personalscraper/library/disk_cleaner.py` | 396 |
| `_clean_media_dir` | `personalscraper/library/disk_cleaner.py` | 519 |
| `_json_default` | `personalscraper/library/models.py` | 550 |
| `serialize_to_json` | `personalscraper/library/models.py` | 557 |
| `_max_priority` | `personalscraper/library/recommender.py` | 28 |
| `_evaluate_movie` | `personalscraper/library/recommender.py` | 34 |
| `_evaluate_tvshow` | `personalscraper/library/recommender.py` | 176 |
| `_detect_needs` | `personalscraper/library/rescraper.py` | 52 |
| `_resolve_tmdb_id` | `personalscraper/library/rescraper.py` | 105 |
| `_find_largest_video` | `personalscraper/library/rescraper.py` | 173 |
| `_rescrape_item` | `personalscraper/library/rescraper.py` | 196 |
| `_rescrape_episodes` | `personalscraper/library/rescraper.py` | 376 |
| `_collect_rescrape_candidates` | `personalscraper/library/rescraper.py` | 456 |
| `extract_nfo_metadata` | `personalscraper/library/scanner.py` | 151 |
| `_check_artwork_movie` | `personalscraper/library/scanner.py` | 224 |
| `_check_artwork_tvshow` | `personalscraper/library/scanner.py` | 245 |
| `_detect_issues` | `personalscraper/library/scanner.py` | 265 |
| `scan_movie_dir` | `personalscraper/library/scanner.py` | 370 |
| `scan_tvshow_dir` | `personalscraper/library/scanner.py` | 427 |
| `_nfo_status_string` | `personalscraper/library/scanner.py` | 485 |
| `_artwork_inventory` | `personalscraper/library/scanner.py` | 502 |
| `_upsert_media_item` | `personalscraper/library/scanner.py` | 523 |
| `_upsert_seasons_and_episodes` | `personalscraper/library/scanner.py` | 641 |
| `_read_episode_titles` | `personalscraper/library/scanner.py` | 688 |
| `_ensure_disk_row` | `personalscraper/library/scanner.py` | 766 |
| `_classify_results` | `personalscraper/library/validator.py` | 37 |
| `_fix_empty_dirs` | `personalscraper/library/validator.py` | 53 |
| `_fix_ntfs_names` | `personalscraper/library/validator.py` | 85 |
| `_default_lock_file` | `personalscraper/lock.py` | 19 |
| `redact_secrets` | `personalscraper/logger.py` | 29 |
| `_build_dir_regex` | `personalscraper/naming_patterns.py` | 134 |
| `_completeness_score` | `personalscraper/process/dedup.py` | 39 |
| `_propagate_rename_to_disks` | `personalscraper/process/reclean.py` | 26 |
| `is_title_polluted` | `personalscraper/process/reclean.py` | 148 |
| `_format_clean_name` | `personalscraper/process/reclean.py` | 168 |
| `_revert_unmatched_recleans` | `personalscraper/process/run.py` | 24 |
| `_kind_from_stem` | `personalscraper/scraper/artwork.py` | 62 |
| `build_lang_priority` | `personalscraper/scraper/artwork.py` | 85 |
| `_media_details_to_classifier_dict` | `personalscraper/scraper/classifier.py` | 22 |
| `_coerce_to_classifier_dict` | `personalscraper/scraper/classifier.py` | 56 |
| `_tv_fallback_title_variants` | `personalscraper/scraper/confidence.py` | 71 |
| `score_match` | `personalscraper/scraper/confidence.py` | 82 |
| `_candidate_has_any_season` | `personalscraper/scraper/confidence.py` | 202 |
| `get_episode_titles` | `personalscraper/scraper/confidence.py` | 440 |
| `prompt_user_choice` | `personalscraper/scraper/confidence.py` | 489 |
| `_provider_id_fields` | `personalscraper/scraper/episode_manager.py` | 34 |
| `_cleanup_orphan_episode_siblings` | `personalscraper/scraper/episode_manager.py` | 333 |
| `_rename_subtitles` | `personalscraper/scraper/episode_manager.py` | 370 |
| `_read_canonical_provider` | `personalscraper/scraper/existing_validator.py` | 94 |
| `_episode_nfo_has_canonical_uniqueid` | `personalscraper/scraper/existing_validator.py` | 124 |
| `_fetch_season_episodes` | `personalscraper/scraper/existing_validator.py` | 280 |
| `_fetch_season_episodes_tvdb` | `personalscraper/scraper/existing_validator.py` | 313 |
| `_dedup_and_move_root_episode` | `personalscraper/scraper/existing_validator.py` | 348 |
| `_build_root_moved_map` | `personalscraper/scraper/existing_validator.py` | 444 |
| `_cache_key` | `personalscraper/scraper/keywords_cache.py` | 37 |
| `_lang_to_kodi` | `personalscraper/scraper/mediainfo.py` | 70 |
| `_map_video_codec` | `personalscraper/scraper/mediainfo.py` | 83 |
| `_map_audio_codec` | `personalscraper/scraper/mediainfo.py` | 95 |
| `_parse_aspect_ratio` | `personalscraper/scraper/mediainfo.py` | 119 |
| `_media_details_to_movie_data` | `personalscraper/scraper/movie_service.py` | 34 |
| `_media_details_to_show_data` | `personalscraper/scraper/movie_service.py` | 124 |
| `_indent` | `personalscraper/scraper/nfo_generator.py` | 88 |
| `_needs_repair` | `personalscraper/scraper/run.py` | 86 |
| `_best_video` | `personalscraper/scraper/trailer_finder.py` | 54 |
| `_video_to_url` | `personalscraper/scraper/trailer_finder.py` | 92 |
| `_tmdb_key` | `personalscraper/scraper/trailers_cache.py` | 31 |
| `_yt_key` | `personalscraper/scraper/trailers_cache.py` | 45 |
| `_safe_get_rating` | `personalscraper/scraper/tv_service.py` | 44 |
| `_episode_payload` | `personalscraper/scraper/tv_service.py` | 56 |
| `_redact_url_key` | `personalscraper/scraper/youtube_search.py` | 44 |
| `_build_youtube_session` | `personalscraper/scraper/youtube_search.py` | 57 |
| `_is_apfs_native` | `personalscraper/scraper/ytdlp_downloader.py` | 46 |
| `_is_bot_detection_error` | `personalscraper/scraper/ytdlp_downloader.py` | 63 |
| `_raise_wall_clock_timeout` | `personalscraper/scraper/ytdlp_downloader.py` | 80 |
| `_guess_cached` | `personalscraper/sorter/cleaner.py` | 18 |
| `_extension_of` | `personalscraper/sorter/file_type.py` | 116 |
| `_has_tvshow_markers` | `personalscraper/sorter/file_type.py` | 128 |
| `_has_unsorted_items` | `personalscraper/sorter/run.py` | 142 |
| `_get_strategy` | `personalscraper/sorter/sorter.py` | 29 |
| `_trailers_boundary` | `personalscraper/trailers/cli.py` | 46 |
| `_parse_since` | `personalscraper/trailers/cli.py` | 90 |
| `_item_added_at` | `personalscraper/trailers/cli.py` | 111 |
| `_filter_since` | `personalscraper/trailers/cli.py` | 131 |
| `_resolve_level_and_season` | `personalscraper/trailers/cli.py` | 147 |
| `_apply_level_filter` | `personalscraper/trailers/cli.py` | 196 |
| `_seasons_enabled_from_config` | `personalscraper/trailers/cli.py` | 218 |
| `_min_file_size` | `personalscraper/trailers/cli.py` | 233 |
| `_allowed_extensions` | `personalscraper/trailers/cli.py` | 248 |
| `_resolve_category_token` | `personalscraper/trailers/cli.py` | 263 |
| `_apply_filters` | `personalscraper/trailers/cli.py` | 299 |
| `_set_state_for_item` | `personalscraper/trailers/orchestrator.py` | 72 |
| `find_existing_trailer` | `personalscraper/trailers/placement.py` | 102 |
| `_resolve_lock_holder_pid` | `personalscraper/trailers/state.py` | 110 |
| `_has_items_to_verify` | `personalscraper/verify/run.py` | 22 |

## D. Dead Protocol candidates

Heuristic: ``class X(Protocol):`` whose name is referenced 0 times
outside the definition module. Protocols used only via structural
typing (e.g. duck-typed via `def f(x: SomeProtocol)`) with a single
annotation site in the same module appear here as false positives.

| Name | File | Line |
| --- | --- | ---: |
| `_RatingClient` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 51 |
| `_DetailsClient` | `personalscraper/indexer/scanner/_modes/backfill_ids.py` | 58 |

## Cross-references

- Sub-phase spec: `docs/features/tech-debt/plan/phase-08-polish.md` §8.4
- Related sub-phase 8.2 audit: `docs/features/tech-debt/audit/14-pending-op-item-issue.md`
- BDD audit baseline: `docs/features/tech-debt/audit/05-bdd-audit.md`
- DESIGN.md §11 (architecture), §9 (BDD lifecycle invariants)

## Reproduce

```bash
python3 scripts/audit-dead-infrastructure.py --db /Users/izno/dev/PersonnalScaper/.data/library.db
```
