# Testing Reference

Test commands, markers, timeouts, and golden files.

## Unit Tests (~6s)

```bash
make test                           # or: python -m pytest -v
python -m pytest tests/ -x -q       # stop on first failure
```

## E2E Tests (manual only)

Real torrents — requires qBittorrent running:

```bash
python -m pytest -m e2e_torrent -v -s   # 3 pipeline tests (movie, tvshow, mixed CLI)
```

E2E tests use `.torrent` files from `assets/torrents/`. Dispatch always runs in dry-run mode — storage disks are never modified. All staging artifacts and qBit test torrents are cleaned up after each test.

### E2E Timeout

`ceil(GB) × 3 min, minimum 10 min` — prevents tests from hanging on stalled torrents.

## Roundtrip E2E Tests

Scrape accuracy — requires TMDB/TVDB API keys:

```bash
python -m pytest -m roundtrip -v -s     # 2 tests (movie + tvshow roundtrip matching)
```

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

## Testing Requirement

Every bug fix MUST have a test reproducing the bug. No exception.
