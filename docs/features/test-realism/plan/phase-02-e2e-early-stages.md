# Phase 02 — E2E tests — ingest / sort / process / scrape

**Goal**: land catalogue items #1–#8 from the DESIGN (early pipeline phases).

## Sub-phase 2.1 — Ingest E2E

`tests/e2e/test_ingest_e2e.py` — two tests :

- `test_ingest_filters_completed_and_untracked(fake_qbit, staging_tree, loaded_config, tmp_path)`
  - Seed fake_qbit with one completed + one incomplete + one already-tracked torrent.
  - Run `personalscraper.ingest.run.run_ingest(...)`.
  - Assert `097-TEMP` contains exactly one folder matching the completed torrent.
  - Assert `ingested_torrents.json` has the new hash.

- `test_ingest_ratio_threshold(...)`
  - Seed two completed torrents, ratios `0.99` and `1.00`.
  - Run ingest with `min_ratio=1.0`.
  - Assert only the `1.00`-ratio torrent moved.

### Commit

`test(e2e): ingest filter and ratio invariants`

## Sub-phase 2.2 — Sort E2E

`tests/e2e/test_sort_e2e.py` — two tests :

- `test_sort_routes_by_file_type(staging_tree, loaded_config)`
  - Populate `097-TEMP` with a `.mkv` movie, a `.mp4` episode (S01E01 naming), and a `.txt` unknown.
  - Run `personalscraper.sorter.run.run_sort(...)`.
  - Assert movie in `001-MOVIES/`, episode in `002-TVSHOWS/`, unknown in `098-OTHER/`.

- `test_sort_reuses_existing_folder_via_fuzzy(staging_tree, loaded_config)`
  - Pre-create `001-MOVIES/Shrinking (2023)/`.
  - Drop a `Shrinking.2024.mkv` in `097-TEMP`.
  - Run sort.
  - Assert file lands inside the existing folder, not a new one.

### Commit

`test(e2e): sort routing and fuzzy-reuse invariants`

## Sub-phase 2.3 — Process + Scrape E2E

`tests/e2e/test_process_e2e.py` — two tests :

- `test_reclean_removes_pollution(staging_tree, loaded_config)`
  - Place `001-MOVIES/The.Matrix.1999.1080p.BluRay.x264-RARBG/video.mkv`.
  - Run `run_process(..., clean=True, dedup=False, scrape=False)`.
  - Assert folder renamed to `The Matrix (1999)` and video preserved.

- `test_dedup_merges_fuzzy_duplicates(...)`
  - Place `Shrinking/` (sparse) + `Shrinking (2023)/` (complete with NFO).
  - Run dedup.
  - Assert `Shrinking/` is gone; `Shrinking (2023)/` keeps its NFO.

`tests/e2e/test_scrape_e2e.py` — two tests :

- `test_scrape_writes_nfo_on_tmdb_hit(staging_tree, fake_tmdb, loaded_config)`
  - Drop `001-MOVIES/Shrinking (2023)/Shrinking.mkv`.
  - Seed `fake_tmdb` with `movie_shrinking.json`.
  - Run scrape.
  - Assert `Shrinking.nfo` exists with `<uniqueid type="tmdb" default="true">…</uniqueid>`.

- `test_scrape_leaves_folder_on_tmdb_miss(...)`
  - Same setup, but `fake_tmdb` returns empty search.
  - Run scrape.
  - Assert no NFO written, folder contents unchanged except possibly a warning log.

### Commit

`test(e2e): process and scrape invariants on real fs`
