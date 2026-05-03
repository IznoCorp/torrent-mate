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

| Tier                                  | Budget                         | Enforced by                         |
| ------------------------------------- | ------------------------------ | ----------------------------------- |
| Unit                                  | ≤ 10 s                         | Budget (advisory)                   |
| Integration                           | ≤ 20 s                         | Budget (advisory)                   |
| **Total default suite** (`make test`) | **≤ 30 s**                     | CI hard limit                       |
| Manual E2E (per test)                 | `ceil(GB) × 3 min, min 10 min` | `@pytest.mark.timeout` on each test |

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

- **`tests/integration/conftest.py`** — integration-tier fixtures: temporary staging directory,
  mock qBittorrent client, patched Config, scraper stubs.
- **`tests/fixtures/config.py`** — shared Config factory used by both unit and integration tests.
  Produces a minimal in-memory Config without touching disk.

When writing a new test, import fixtures from the nearest `conftest.py` in the hierarchy rather
than duplicating setup logic.

## Golden Files

Located in `assets/torrents/expected/`. Add exact validation on top of smoke tests:

- NFO invariants
- Artwork existence
- Directory structure
- Dispatch expectations

E2E tests auto-match torrents to golden files via fuzzy matching. If no golden file exists, only smoke tests run.

## Lint & Format

```bash
make lint            # ruff check
make format          # ruff format + fix
```

### Trailers network marker

The @pytest.mark.network marker gates opt-in network integration tests.
Registered in pyproject.toml under [tool.pytest.ini_options] markers.

To run: TRAILER_INTEGRATION_TESTS=1 python -m pytest tests/trailers/test_integration_network.py -m network -v

Requires TMDB_READ_ACCESS_TOKEN in environment. Uses a stable Blender Foundation clip (ID aqz-KE-bpKQ, also used in tests/scraper/test_ytdlp_downloader.py).
Skipped automatically without TRAILER_INTEGRATION_TESTS=1 (no explicit -k/-m needed).

Hermetic E2E (tests/trailers/test_integration_hermetic.py) runs by default: yt-dlp is mocked to copy
a fixture MP4. Covers the full TrailerFinder -> placement -> state stack without any network call.

## Testing Requirement

Every bug fix MUST have a test reproducing the bug. No exception.
