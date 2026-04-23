# Phase 03 — E2E tests — enforce / verify / dispatch / full pipeline

**Goal**: land catalogue items #9–#15.

## Sub-phase 3.1 — Enforce + Verify E2E

`tests/e2e/test_enforce_e2e.py` :

- `test_enforce_creates_missing_season_dir(staging_tree, loaded_config)`
  - TV show folder with orphan episode files at the root.
  - Run enforce.
  - Assert files moved into the expected `Saison 01/` subfolder.

`tests/e2e/test_verify_e2e.py` :

- `test_verify_accepts_complete_folder` — folder with NFO + poster + landscape ⇒ status `"valid"`.
- `test_verify_blocks_missing_poster` — same folder minus poster ⇒ status `"blocked"`.

### Commit

`test(e2e): enforce and verify gate invariants`

## Sub-phase 3.2 — Dispatch E2E — new & replace

`tests/e2e/test_dispatch_new_e2e.py` :

- `test_dispatch_picks_disk_with_most_space(...)`
  - Four fake disks with differing (simulated) free space via a shutil.disk_usage monkeypatch.
  - A verified movie folder in staging.
  - Run dispatch.
  - Assert the movie lands on the disk with the most free space.

`tests/e2e/test_dispatch_replace_e2e.py` :

- `test_dispatch_replaces_existing_movie(...)`
  - Pre-create `Disk1/movies/Shrinking (2023)/` with an old small file.
  - Put a bigger `Shrinking (2023)/` in staging.
  - Run dispatch.
  - Assert old content is gone, new content present, `_tmp_dispatch_*` cleaned.
  - Skip if `rsync` not on PATH.

### Commit

`test(e2e): dispatch new-placement and replace invariants`

## Sub-phase 3.3 — Dispatch E2E — merge & crash recovery

`tests/e2e/test_dispatch_merge_e2e.py` :

- `test_dispatch_merges_tvshow_new_episodes(...)`
  - Pre-create `Disk2/tv_shows/Fallout (2024)/Saison 01/episode1.mkv`.
  - Staging has same show with `episode2.mkv`.
  - Run dispatch.
  - Assert both episodes present on disk, staging folder gone, no backup leftovers.

`tests/e2e/test_dispatch_recovery_e2e.py` :

- `test_crash_recovery_uses_filesystem_scan(...)`
  - Simulate a crashed prior run : source in staging + destination on Disk1, but empty `media_index.json`.
  - Run dispatch.
  - Assert the dispatcher detects the existing folder via filesystem scan and re-syncs, leaving a clean state.

### Commit

`test(e2e): dispatch merge and crash-recovery invariants`

## Sub-phase 3.4 — Full-pipeline E2E

`tests/e2e/test_full_pipeline_e2e.py` :

- `test_dry_run_three_torrents(fake_qbit, fake_tmdb, fake_tvdb, staging_tree, fake_disks, loaded_config)`
  - Seed 3 completed torrents (2 movies, 1 tv episode).
  - Run `personalscraper.pipeline.run_pipeline(..., dry_run=True)`.
  - Assert returned `PipelineReport` has 6 StepReports, each with the expected `success_count` / `skip_count`.
  - Assert no file was actually moved between disks.

Budget 5 s (fixture build + run). Skip if rsync missing.

### Commit

`test(e2e): full pipeline dry-run orchestration`
