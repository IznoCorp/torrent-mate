# Testing Reference

Three-tier test taxonomy, decision tree, runtime budgets, run commands, and fixture reference.

## Three-Tier Taxonomy

| Tier            | Location             | What it tests                                                      | Mocking strategy                                    |
| --------------- | -------------------- | ------------------------------------------------------------------ | --------------------------------------------------- |
| **Unit**        | `tests/<module>/`    | Single function or class, pure logic                               | All I/O mocked (no disk, no network, no subprocess) |
| **Integration** | `tests/integration/` | Module interactions, real filesystem, real subprocesses            | Network and external services mocked                |
| **Manual E2E**  | `tests/e2e/`         | Full pipeline with real qBit, real torrents, real APIs, real disks | Nothing mocked — requires live environment          |

Unit and integration tests run automatically in CI and via `make test`.
Manual E2E tests are excluded from the default suite — they require a live qBittorrent instance and API keys.

## Decision Tree — Where Does My New Test Go?

```
What does the test touch?
│
├── Single function or class, pure logic only
│   └─→ UNIT  (tests/<module>/)
│
├── Multiple modules together, real filesystem, OR real subprocess
│   but network/external APIs are mocked
│   └─→ INTEGRATION  (tests/integration/)
│
└── Real qBittorrent, real .torrent files, real TMDB/TVDB API,
    or real storage disks
    └─→ MANUAL E2E  (tests/e2e/)
        requires: qBit running + API keys in .env
```

Rule of thumb: mock **network** → integration.
Mock **everything** → unit. Mock **nothing** → manual E2E.

## Runtime Budget per Tier

| Tier                                  | Budget                         | Enforced by                                  |
| ------------------------------------- | ------------------------------ | -------------------------------------------- |
| Unit                                  | ≤ 10 s                         | Budget (advisory)                            |
| Integration                           | ≤ 20 s                         | Budget (advisory)                            |
| **Total default suite** (`make test`) | **≤ 30 s**                     | CI hard limit                                |
| Manual E2E (per test)                 | `ceil(GB) × 3 min, min 10 min` | computed in `wait_for_completion` (see note) |

> **E2E timeout is not a pytest marker.** There is no `timeout` marker in
> `pyproject.toml` (the registered markers are listed under
> [Markers](#markers) below). For torrent E2E, the budget is computed
> dynamically from the total torrent size in
> `TorrentSetup.wait_for_completion` (`tests/e2e/setup_torrents.py`):
> `timeout_minutes = max(ceil(total_gb) * 3, 10)`. When the download exceeds
> that budget, `wait_for_completion` raises a `TimeoutError` — pytest itself
> imposes no per-test timeout.

## How to Run Each Tier

### Default suite — unit + integration (CI, everyday use)

```bash
make test                               # unit + integration, fail-fast
python -m pytest -v                     # same, verbose
python -m pytest tests/ -x -q          # stop on first failure
```

### Unit tests only

```bash
python -m pytest tests/ --ignore=tests/integration --ignore=tests/e2e -q
```

### Integration tests only

```bash
python -m pytest tests/integration/ -q
```

### Manual E2E — real qBittorrent + real torrents

Requires qBittorrent running and credentials configured in `.env`:

```bash
python -m pytest -m e2e_torrent -v -s   # 3 pipeline tests (movie, tvshow, mixed CLI)
```

Dispatch always runs in dry-run mode — storage disks are never modified.
All staging artifacts and qBit test torrents are cleaned up after each test.

### Roundtrip E2E — scrape accuracy

Requires TMDB/TVDB API keys in `.env`:

```bash
python -m pytest -m roundtrip -v -s    # 2 tests (movie + tvshow roundtrip matching)
```

## Fixture Reference

- **`tests/conftest.py`** — root-level conftest. Patches **`tenacity` sleep at
  import time** (module-level `_patch_tenacity_sleep()`): it overrides
  `tenacity.Retrying.__init__` to inject a no-op sleep, so `@retry`-decorated
  code runs its retries instantly without touching the global `time.sleep`.
  This patch must apply before any test module imports retry-decorated code,
  hence it runs at import, not inside a fixture.
- **`tests/integration/conftest.py`** — integration-tier fixtures: temporary staging directory,
  mock qBittorrent client, patched Config, scraper stubs.
- **`tests/fixtures/config.py`** — shared Config factory used by both unit and integration tests.
  Produces a minimal in-memory Config without touching disk.
- **`tests/fixtures/settings_stub.py`** — a real, typed `Settings` stub carrying
  dummy credential values, used by CLI E2E tests so `ProviderRegistry` boots
  through `_build_app_context` without a `MagicMock` (which is not
  JSON-serialisable and breaks `TransportPolicy`).

When writing a new test, import fixtures from the nearest `conftest.py` in the hierarchy rather
than duplicating setup logic.

## Feature Map

`tests/feature_map/<codename>.json` maps test designs to the features they
cover. The files are **generated, not hand-edited**: the pre-commit hook
regenerates the relevant `<codename>.json` whenever a `test_design_*.py` file
is staged. CI catches drift via `update_feature_map.py --check` when the hook
is bypassed (`git commit --no-verify`). Current map files include
`api-unify.json`, `architecture.json`, `dispatch.json`, `indexer.json`,
`indexer-json-shapes.json`, `pipeline.json`, `scraper.json`, and
`trailers.json`.

## Golden Files

Each golden file lives in its own per-torrent subdirectory under
`assets/torrents/expected/<slug>/` (e.g. `jumanji_1995/`,
`malcolm_in_the_middle_s01/`). A subdirectory holds up to four JSON documents,
each adding exact validation on top of the smoke-test assertions:

- `expected_nfo.json` — NFO invariants
- `expected_artwork.json` — artwork existence / minimum sizes
- `expected_structure.json` — directory structure (required files/dirs, forbidden)
- `expected_dispatch.json` — dispatch expectations (action, eligible disks)

E2E tests match a torrent to its golden subdirectory by **fuzzy name match**:
`match_torrent_to_golden` (`tests/e2e/golden.py`) normalizes the torrent name
(stripping release tags, codecs, resolution labels) and scores it against each
slug with `rapidfuzz.fuzz.WRatio`. A match requires a score **≥ 80**; the
best-scoring slug above that threshold is loaded. If no slug scores ≥ 80
(or `expected/` is empty), `match_torrent_to_golden` returns `None` and only
the smoke-test assertions run.

## Lint & Format

```bash
make lint            # ruff check
make format          # ruff format + fix
```

## Markers

All custom pytest markers are registered in `pyproject.toml` under
`[tool.pytest.ini_options]`:

| Marker            | Meaning                                                         |
| ----------------- | --------------------------------------------------------------- |
| `e2e`             | End-to-end tests requiring storage disks and/or live APIs       |
| `roundtrip`       | Torrentify disk media, re-match via API, compare                |
| `e2e_torrent`     | Pipeline E2E with real torrent downloads (manual; costs ratio)  |
| `e2e_idempotence` | E2E idempotence tests on real staging data (manual)             |
| `network`         | Opt-in network tests (gated by `TRAILER_INTEGRATION_TESTS=1`)   |
| `slow`            | Slow perf-regression tests, off by default — run with `-m slow` |
| `darwin_only`     | macOS-only smoke tests (skipped on Linux/Windows CI)            |
| `multifs`         | Filesystem-capability tests using faked mount/stat fixtures     |
| `integration`     | Cross-module characterization / integration tests (not unit)    |

The default suite excludes most of these via `addopts`:

```
addopts = "-m 'not e2e and not e2e_torrent and not e2e_idempotence and not slow and not network'"
```

### Trailers network marker

The `network` marker gates opt-in network integration tests. It is **excluded
by default** via the `addopts` selector above, so the default suite never hits
the network.

To actually run the network tests you need **both**:

1. set `TRAILER_INTEGRATION_TESTS=1` (the env gate is enforced inside the
   fixtures — without it, the tests skip even if you pass `-m network`), and
2. pass `-m network` (to override the default `not network` exclusion):

```bash
TRAILER_INTEGRATION_TESTS=1 python -m pytest tests/trailers/test_integration_network.py -m network -v
```

Requires `TMDB_READ_ACCESS_TOKEN` in environment. Uses a stable Blender Foundation clip (ID aqz-KE-bpKQ, also used in tests/trailers/test_ytdlp_downloader.py).

Hermetic E2E (tests/trailers/test_integration_hermetic.py) runs by default: yt-dlp is mocked to copy
a fixture MP4. Covers the full TrailerFinder -> placement -> state stack without any network call.

## Testing Requirement

Every bug fix MUST have a test reproducing the bug. No exception.
