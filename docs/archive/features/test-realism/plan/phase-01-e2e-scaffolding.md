# Phase 01 — Integration scaffolding & shared fixtures

**Goal**: `tests/integration/conftest.py` exposes fixtures that any integration test can compose (staging tree, fake disks, config.json5, fake TMDB/TVDB/qBit). No production-behaviour tests yet — only the fixture module plus a single smoke test proving the fixtures compose.

## Gate (from previous phase)

None — this is the first phase.

## Sub-phase 1.1 — Directory + conftest skeleton + smoke

- Create `tests/integration/__init__.py` (empty).
- Create `tests/integration/conftest.py` with these fixtures (each Google-docstring'd in English, per CLAUDE.md):
  - `staging_tree(tmp_path) -> Path` — builds every staging subdir declared in `config.staging_dirs` under `tmp_path / "staging"`. Returns the staging root. Uses the `test_config` fixture from `tests/fixtures/config.py` to drive the list of subdir names.
  - `fake_disks(tmp_path) -> list[Path]` — builds four `tmp_path / "Disk{N}"/` dirs with the category subfolder names declared in the `test_config` disk entries. Returns the list of disk root paths.
  - `integration_config(staging_tree, fake_disks) -> Config` — composes a validated `Config` pointing at the fixtures, seeded from `tests/fixtures/config.py::test_config` and overridden so `paths.staging_dir = staging_tree` and `disks = [DiskConfig(...)]` for each entry in `fake_disks`.
  - `integration_config_path(integration_config, tmp_path) -> Path` — serialises the composed Config to `tmp_path / "config.json5"` and returns its path (for tests that invoke the CLI and need a real file).
  - `fake_tmdb(monkeypatch) -> FakeTMDB` — monkeypatches `personalscraper.scraper.tmdb_client.TMDBClient` internal `requests.Session` using canned JSON from `tests/integration/fixtures/tmdb/`.
  - `fake_tvdb(monkeypatch) -> FakeTVDB` — same pattern for TVDB.
  - `fake_qbit(monkeypatch) -> FakeQBitClient` — monkeypatches `qbittorrentapi.Client` (and where `personalscraper.ingest.ingest` imports it) with an in-memory stand-in. Provides `.seed(torrent_list)` helper.
  - `rsync_available() -> bool` — module-level fixture that `pytest.skip`s the test if `shutil.which("rsync")` returns None.
- Fixture JSON payloads live under `tests/integration/fixtures/`:
  - `tmdb/movie_shrinking.json`, `tmdb/tv_fallout.json`, `tmdb/search_empty.json`.
  - `tvdb/series_fallout.json`.
  - `qbit/completed_torrents.json`.
- **Fixture-duplication policy** (conscious anti-DRY choice): JSON payloads that already exist under `tests/scraper/fixtures/` are copied verbatim into `tests/integration/fixtures/` rather than imported. Rationale: the two tiers must be independently evolvable — a change to a scraper-unit canned response must not silently mutate an integration assertion, and vice-versa. Missing payloads are authored from scratch using the same schema as the scraper-unit fixtures.
- **Tier isolation guard** in `tests/integration/conftest.py`: at module import time, assert that no symbol from `tests.e2e` is importable by this module, and fail collection loudly if it is. Example:
  ```python
  # Enforce tier isolation: integration must not depend on the manual e2e tier.
  import sys
  assert "tests.e2e" not in sys.modules, (
      "tests/integration/ must not import from tests/e2e/ — these are distinct tiers."
  )
  ```
  This catches drift at `pytest --collect-only` time, cheaply.
- Add one trivial smoke test `tests/integration/test_fixtures_smoke.py::test_fixtures_compose` asserting: `staging_tree.is_dir()`, `len(fake_disks) == 4`, `integration_config.paths.staging_dir == staging_tree`, `integration_config_path.exists()`, `fake_qbit` has an empty torrent list. Proves the fixture chain evaluates.
- Do **not** touch `tests/e2e/` — the manual tier stays untouched.

### Quality gate

- `make test` green; smoke test collected and passing.
- `pytest -m e2e_torrent --collect-only` still reports the manual tier intact (sanity check on collection rules).
- Default pytest collection excludes `e2e`, `e2e_torrent`, `e2e_idempotence`, `roundtrip` — unchanged.

### Commit

`test(integration): scaffold shared fixtures and smoke test`
