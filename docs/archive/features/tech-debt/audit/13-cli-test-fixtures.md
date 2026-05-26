# 13 — CLI Test Fixtures Audit (pre-9.1)

**Date**: 2026-05-24
**Scope**: Audit of existing `_e2e_helpers.py` helpers + planned 9.1 extensions.

## Existing helpers (11, 273 LOC)

| #   | Name                                                               | Category     | Description                                                              |
| --- | ------------------------------------------------------------------ | ------------ | ------------------------------------------------------------------------ |
| 1   | `make_synthetic_db(tmp_path) -> Path`                              | DB seeder    | Creates fully-migrated `test_indexer.db` in tmp_path                     |
| 2   | `make_test_config_with_db(test_config, db_path) -> Config`         | Config       | Copies test config with `indexer.db_path` pointing at the synthetic DB   |
| 3   | `seed_disk(conn, label, mount_path) -> int`                        | DB seeder    | Inserts `disk` row, returns id                                           |
| 4   | `seed_phantom_path(conn, disk_id, rel_path, n_files) -> int`       | DB seeder    | Inserts `path` + N `media_file` rows whose directory doesn't exist on FS |
| 5   | `seed_media_item_with_release(conn, title, category_id) -> int`    | DB seeder    | Inserts `media_item` + `media_release`, returns release_id               |
| 6   | `seed_scan_run(conn, ...) -> int`                                  | DB seeder    | Inserts completed `scan_run` row                                         |
| 7   | `seed_index_outbox(conn, ...) -> int`                              | DB seeder    | Inserts `index_outbox` row                                               |
| 8   | `seed_repair_queue(conn, ...) -> int`                              | DB seeder    | Inserts `repair_queue` row                                               |
| 9   | `seed_media_file_on_disk(conn, disk_id, mount_path, ...) -> tuple` | FS+DB seeder | Creates real file on disk + matching `path`/`media_file` rows            |
| 10  | `run_cli(args) -> Result`                                          | CLI          | Invokes Typer CLI via CliRunner                                          |
| 11  | `json_from_result(result) -> dict`                                 | Assertion    | Extracts JSON dict from Rich-formatted CliRunner output                  |

**No overlaps with planned extensions** — existing helpers are DB/FS seeders and CLI invocation. Planned extensions are mock clients, new assertions, event capture, and FS/BDD snapshots.

## Extensions to add (15, ~200 LOC estimated)

| #   | Name                                                       | Category    | Description                                                                         |
| --- | ---------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------- |
| 12  | `mock_qbit_client(monkeypatch)`                            | Mock client | Patches `build_active_torrent_client` + `QBitClient` in ingest, returns canned mock |
| 13  | `mock_transmission_client(monkeypatch)`                    | Mock client | Patches `TransmissionClient` class                                                  |
| 14  | `mock_tmdb_client(monkeypatch)`                            | Mock client | Patches `TMDBClient` class, returns mock with canonical payloads                    |
| 15  | `mock_tvdb_client(monkeypatch)`                            | Mock client | Patches `TVDBClient` class                                                          |
| 16  | `mock_omdb_client(monkeypatch)`                            | Mock client | Patches `OMDbAdapter` class                                                         |
| 17  | `mock_trakt_client(monkeypatch)`                           | Mock client | Patches `TraktClient` class                                                         |
| 18  | `mock_yt_dlp(monkeypatch)`                                 | Mock client | Patches `yt_dlp.YoutubeDL` class                                                    |
| 19  | `seed_pipeline_lock(staging_dir) -> Path`                  | FS seeder   | Creates `pipeline.lock` file, returns path                                          |
| 20  | `seed_staging_layout(tmp_path, config) -> dict`            | FS seeder   | Creates `001-MOVIES/`, `002-TVSHOWS/` etc. per config                               |
| 21  | `assert_no_python_traceback(result)`                       | Assertion   | Asserts no `Traceback (most recent call last):` in output                           |
| 22  | `assert_json_schema(result, required_keys, optional_keys)` | Assertion   | Parses JSON + validates top-level keys                                              |
| 23  | `assert_events_emitted(captured_bus, expected_classes)`    | Assertion   | Verifies events against design-conformity-matrix (anti-drift)                       |
| 24  | `fs_snapshot(path) -> dict`                                | Utility     | Recursive hash of directory tree                                                    |
| 25  | `bdd_diff_ignoring(conn, before_snapshot, ignore_cols)`    | Utility     | Diff two DB snapshots excluding time-sensitive columns                              |
| 26  | `capture_event_bus(monkeypatch) -> list`                   | Utility     | Intercepts `EventBus.emit` calls, returns captured events                           |

**Module size forecast**: 273 + ~200 = ~473 LOC, well under 800 warning threshold.
