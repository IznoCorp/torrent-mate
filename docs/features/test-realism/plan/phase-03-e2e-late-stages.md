# Phase 03 — Integration tests — enforce / verify / dispatch / full pipeline

**Goal**: land catalogue items #9–#15 in `tests/integration/`. Four commits grouped by module.

## Gate (from Phase 02)

- `tests/integration/test_ingest.py`, `test_sort.py`, `test_process.py`, `test_scrape.py` all present and green.
- `tests/e2e/` diff still zero.

## Sub-phase 3.1 — Enforce + Verify integration

`tests/integration/test_enforce.py` (catalogue #9):

- `test_enforce_creates_missing_season_dir(staging_tree, integration_config)`
  - TV show folder with orphan episode files at the root.
  - Run `personalscraper.enforce.run.run_enforce(...)`.
  - Assert files moved into the expected `Saison 01/` subfolder.

`tests/integration/test_verify.py` (catalogue #10):

- `test_verify_accepts_complete_folder(staging_tree, integration_config)` — folder with NFO + poster + landscape ⇒ status `"valid"`.
- `test_verify_blocks_missing_poster(staging_tree, integration_config)` — same folder minus poster ⇒ status `"blocked"`.

### Commit

`test(integration): enforce and verify gate invariants`

## Sub-phase 3.2 — Dispatch integration — new & replace

`tests/integration/test_dispatch_new.py` (catalogue #11):

- `test_dispatch_picks_disk_with_most_space(staging_tree, fake_disks, integration_config, rsync_available, monkeypatch)`
  - Monkeypatch `shutil.disk_usage` to return differing free-space values for the four fake disks.
  - A verified movie folder in staging.
  - Run `personalscraper.dispatch.run.run_dispatch(...)`.
  - Assert the movie lands on the disk with the most free space.

`tests/integration/test_dispatch_replace.py` (catalogue #12):

- `test_dispatch_replaces_existing_movie(staging_tree, fake_disks, integration_config, rsync_available)`
  - Pre-create `Disk1/movies/Shrinking (2023)/` with an old small file.
  - Put a bigger `Shrinking (2023)/` in staging.
  - Run dispatch.
  - Assert old content gone, new content present, no `_tmp_dispatch_*` leftovers, `media_index.json` updated.

### Commit

`test(integration): dispatch new-placement and replace invariants`

## Sub-phase 3.3 — Dispatch integration — merge & crash recovery

`tests/integration/test_dispatch_merge.py` (catalogue #13):

- `test_dispatch_merges_tvshow_new_episodes(staging_tree, fake_disks, integration_config, rsync_available)`
  - Pre-create `Disk2/tv_shows/Fallout (2024)/Saison 01/episode1.mkv`.
  - Staging has same show with `episode2.mkv`.
  - Run dispatch.
  - Assert both episodes present on disk, staging folder gone, no rsync backup leftovers.

`tests/integration/test_dispatch_recovery.py` (catalogue #14):

- `test_crash_recovery_uses_filesystem_scan(staging_tree, fake_disks, integration_config, rsync_available)`
  - Simulate a crashed prior run: destination folder on Disk1 exists, but `media_index.json` is empty.
  - Run dispatch on a source in staging.
  - Assert the dispatcher detects the existing folder via filesystem scan, merges/replaces correctly, leaves a clean state and a re-populated index.

### Commit

`test(integration): dispatch merge and crash-recovery invariants`

## Sub-phase 3.4 — Full-pipeline integration

`tests/integration/test_full_pipeline.py` (catalogue #15):

- `test_dry_run_three_torrents(fake_qbit, fake_tmdb, fake_tvdb, staging_tree, fake_disks, integration_config_path, rsync_available)`
  - Seed 3 completed torrents (2 movies, 1 tv episode) in `fake_qbit`.
  - Seed `fake_tmdb` and `fake_tvdb` with matching hits.
  - Invoke the orchestrator (`personalscraper run --dry-run --config <integration_config_path>`) via `typer.testing.CliRunner` or directly via `Pipeline(...).run(dry_run=True)`.
  - Assert returned `PipelineReport` has 6 StepReports, each with the expected `success_count` / `skip_count`.
  - Assert no file actually moved to any disk (dry-run invariant).

Budget 5 s (fixture build + run). Uses `rsync_available` to skip if rsync is missing.

### Commit

`test(integration): full pipeline dry-run orchestration`

## Quality gate (after 3.4)

- `tests/integration/` collects ≥ 16 tests (smoke + 15 catalogue), all green.
- Default `pytest` runtime still ≤ 30 s.
- `tests/e2e/` diff: zero changes.
- `pytest --durations=20` confirms no integration test exceeds 5 s (full-pipeline test cap).
