# Phase 01 — E2E scaffolding & shared fixtures

**Goal**: `tests/e2e/conftest.py` exposes fixtures that any E2E test can compose (staging tree, fake disks, config.json5, fake TMDB/TVDB/qBit). No tests yet.

## Sub-phase 1.1 — Directory + conftest skeleton

- Ensure `tests/e2e/__init__.py` exists (empty).
- New `tests/e2e/conftest.py` with these fixtures :
  - `staging_tree(tmp_path) -> Path` — builds `001-MOVIES/`, `002-TVSHOWS/`, `003-EBOOKS/`, `004-AUDIO/`, `005-APPS/`, `006-ANDROID/`, `097-TEMP/`, `098-OTHER/`. Returns the staging root.
  - `fake_disks(tmp_path) -> list[Path]` — builds `Disk1/…Disk4/` each with `movies/`, `tv_shows/`, `anime/`, `tv_programs/` subfolders. Returns the list of disk root paths.
  - `config_json5(staging_tree, fake_disks) -> Path` — writes a complete `config.json5` at `tmp_path / "config.json5"` pointing at the fixtures. Uses the current Pydantic schema defaults for everything else (fuzzy_match, genre_mapping, …).
  - `loaded_config(config_json5) -> Config` — returns a validated Config.
  - `fake_tmdb(monkeypatch) -> FakeTMDBSession` — monkeypatches `requests.Session` where TMDBClient uses it, driven by JSON fixtures under `tests/e2e/fixtures/tmdb/`.
  - `fake_tvdb(monkeypatch) -> FakeTVDBSession` — same pattern for TVDB.
  - `fake_qbit(monkeypatch) -> FakeQBitClient` — replaces `qbittorrentapi.Client` with an in-memory stand-in. Provides a helper `.seed(torrent_list)` for tests.

- Fixture JSON payloads live under `tests/e2e/fixtures/` :
  - `tmdb/movie_shrinking.json`, `tmdb/tv_fallout.json`, `tmdb/search_empty.json`
  - `tvdb/series_fallout.json`
  - `qbit/completed_torrents.json`

### Quality gate

- `pytest tests/e2e -q` collects zero tests and exits 0 (fixtures evaluated lazily; empty module).
- Unit suite still green.

### Commit

`test(e2e): scaffold shared fixtures for end-to-end tests`
