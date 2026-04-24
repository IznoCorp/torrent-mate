# Phase 02 — Integration tests — ingest / sort / process / scrape

**Goal**: land catalogue items #1–#8 from the DESIGN (early pipeline phases) in `tests/integration/`. Three commits, one per module cluster.

## Gate (from Phase 01)

- `tests/integration/conftest.py` exposes `staging_tree`, `fake_disks`, `integration_config`, `integration_config_path`, `fake_tmdb`, `fake_tvdb`, `fake_qbit`, `rsync_available`.
- `tests/integration/test_fixtures_smoke.py` green.
- `tests/e2e/` untouched.

## Sub-phase 2.1 — Ingest integration

`tests/integration/test_ingest.py` — two tests (catalogue #1, #2):

- `test_ingest_filters_completed_and_untracked(fake_qbit, staging_tree, integration_config, tmp_path)`
  - Seed `fake_qbit` with one completed + one incomplete + one already-tracked torrent.
  - Invoke `personalscraper.ingest.ingest.run_ingest(...)` directly with `integration_config`.
  - Assert `staging_tree / "097-TEMP"` contains exactly one folder matching the completed torrent.
  - Assert `integration_config.paths.data_dir / "ingested_torrents.json"` has the new hash.

- `test_ingest_ratio_threshold(fake_qbit, staging_tree, integration_config)`
  - Seed two completed torrents, ratios `0.99` and `1.00`.
  - Run ingest with the ratio threshold configured in `integration_config` (set to `1.0` for this test via a small override fixture).
  - Assert only the `1.00`-ratio torrent was moved.

### Commit

`test(integration): ingest filter and ratio invariants`

## Sub-phase 2.2 — Sort integration

`tests/integration/test_sort.py` — two tests (catalogue #3, #4):

- `test_sort_routes_by_file_type(staging_tree, integration_config)`
  - Populate `097-TEMP` with a `.mkv` movie, a `.mp4` episode (S01E01 naming), and a `.txt` unknown.
  - Invoke `personalscraper.sorter.run.run_sort(...)`.
  - Assert movie in `001-MOVIES/`, episode in `002-TVSHOWS/`, unknown in `098-OTHER/` (or whichever `other`-role staging dir resolves to in `integration_config`).

- `test_sort_reuses_existing_folder_via_fuzzy(staging_tree, integration_config)`
  - Pre-create `001-MOVIES/Shrinking (2023)/`.
  - Drop `Shrinking.2024.mkv` in `097-TEMP`.
  - Run sort.
  - Assert the file lands inside the existing folder, not a new one.

### Commit

`test(integration): sort routing and fuzzy-reuse invariants`

## Sub-phase 2.3 — Process + Scrape integration

`tests/integration/test_process.py` — two tests (catalogue #5, #6):

- `test_reclean_removes_pollution(staging_tree, integration_config)`
  - Place `001-MOVIES/The.Matrix.1999.1080p.BluRay.x264-RARBG/video.mkv`.
  - Run `personalscraper.process.run.run_process(..., clean=True, dedup=False, scrape=False)`.
  - Assert folder renamed to `The Matrix (1999)` and video preserved.

- `test_dedup_merges_fuzzy_duplicates(staging_tree, integration_config)`
  - Place `Shrinking/` (sparse) + `Shrinking (2023)/` (complete with NFO).
  - Run dedup.
  - Assert `Shrinking/` gone; `Shrinking (2023)/` keeps its NFO.

`tests/integration/test_scrape.py` — two tests (catalogue #7, #8):

- `test_scrape_writes_nfo_on_tmdb_hit(staging_tree, fake_tmdb, integration_config)`
  - Drop `001-MOVIES/Shrinking (2023)/Shrinking.mkv`.
  - Seed `fake_tmdb` with `movie_shrinking.json`.
  - Run `personalscraper.scraper.run.run_scrape(...)`.
  - Assert `Shrinking.nfo` exists with `<uniqueid type="tmdb" default="true">…</uniqueid>`.

- `test_scrape_leaves_folder_on_tmdb_miss(staging_tree, fake_tmdb, integration_config)`
  - Same setup, but `fake_tmdb` returns `search_empty.json`.
  - Run scrape.
  - Assert no NFO written and folder contents unchanged (no destructive default).

### Commit

`test(integration): process and scrape invariants on real fs`

## Quality gate (after 2.3)

- `tests/integration/` collects ≥ 9 tests (smoke + 8), all green.
- Full default `pytest` runtime still ≤ 30 s.
- `tests/e2e/` diff: zero changes.
