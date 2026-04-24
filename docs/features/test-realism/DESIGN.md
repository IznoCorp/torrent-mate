# DESIGN — Test Realism Refactor

**Codename**: `test-realism`
**Type**: test / refactor (minor SemVer bump — no production behaviour change, but test suite reshuffled)
**Status**: preparation — not yet implemented

## 1. Problem

Three test files dominate the suite by volume and share a common pathology: they rely on `unittest.mock.patch` / `pytest-mock` to replace so many collaborators that the test ends up verifying the mocks, not the code.

Representative counts (as of branch `feat/ext-staging`):

| File                                 | `@patch` calls | Real coverage concern                                                                                                                                                                                            |
| ------------------------------------ | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/dispatch/test_dispatcher.py`  | ~37            | rsync, disk status, shutil.which — every subprocess and filesystem interaction is mocked. Dispatch-vs-filesystem invariants are untested (cross-FS move, no-space skip, rollback after rsync failure).           |
| `tests/test_cli.py`                  | ~66            | Config loader, lock acquire/release, settings, every pipeline step, logging — the CLI is tested with the pipeline stubbed to constants. Wiring from flag → subcommand → pipeline argument is mostly mock wiring. |
| `tests/test_pipeline_integration.py` | ~42            | All 6 pipeline phases mocked. The orchestrator is tested against its own scaffolding; bugs in order-of-operations, gating between steps, state-file coherence, and JSON invariants are invisible.                |

Symptoms this has masked in production (from recent bug runs) :

- Dispatch leaving orphans in `_tmp_dispatch_*` after rsync failure — unit tests green.
- Tracker JSON silently becoming empty on corruption — unit tests green.
- AnimeRule `applies_to="movies"` matching no media — unit tests green.

Plain-language summary : the current suite tells us the Python code runs; it does not tell us the pipeline works.

## 2. Non-goals

- **No move to a different test framework.** Pytest stays.
- **No deletion of existing tests** except when a new E2E test strictly supersedes them (rare, explicit per case).
- **No production code refactor.** If a test needs a "seam" (dependency injection, a factory override) and the code does not already have one, we add the seam minimally — no restructuring.
- **No network I/O in CI.** External APIs (TMDB/TVDB/qBittorrent) stay mocked.
- **No test runtime increase beyond ~30s for the full suite.**

## 3. Target state

1. Three **thin** hotspot tests : keep them for CLI-surface verification (exit codes, flag forwarding), trim their patches to what they actually assert.
2. A new **E2E tier** : `tests/e2e/` (it already exists — currently empty or sparse) housing ~15 small tests, each spinning up a real `tmp_path` staging + disks tree, real `rsync` via subprocess (skip if not installed), and mocked network APIs.
3. Clear **convention** for future tests :
   - Unit tests : mock what you don't own (TMDB, qBit), use real temp dirs for everything you do own.
   - E2E : mock only network; everything else is real files.

## 4. E2E test catalogue (target ~15)

Each test is a `with tmp_path:` block or fixture-based, no Docker, no network.

| #   | Scenario                                                                                                                   | What it proves             |
| --- | -------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| 1   | Ingest : one completed torrent, one incomplete, one already tracked → only completed is copied to 097-TEMP                 | ingest filter invariants   |
| 2   | Ingest : ratio threshold (< 1.0 skip, ≥ 1.0 keep)                                                                          | numeric guard              |
| 3   | Sort : movie file lands in movies dir, TV episode lands in tvshows dir, unknown type in other                              | category routing           |
| 4   | Sort : existing movie folder matched by fuzzy → destination reused                                                         | dedupe-on-sort             |
| 5   | Process reclean : polluted folder (WEBRip tags, CRLF) → cleaned name                                                       | string cleaning end-to-end |
| 6   | Process dedup : `Shrinking` + `Shrinking (2023)` → merged; `The Matrix (1999)` + `The Matrix (2003)` → not merged          | fuzzy guards               |
| 7   | Scrape : mocked TMDB hit writes NFO with correct `<uniqueid type="tmdb">`                                                  | NFO contract               |
| 8   | Scrape : mocked TMDB miss leaves folder untouched                                                                          | no destructive default     |
| 9   | Enforce : missing season folder is created; orphan files moved into season folder                                          | structure enforcement      |
| 10  | Verify : folder with complete NFO + artwork → valid; missing poster → blocked                                              | gate logic                 |
| 11  | Dispatch : new movie → moved to disk with most free space                                                                  | disk selection             |
| 12  | Dispatch : existing movie folder on Disk1 → replaced via tmp + rename                                                      | replace invariants         |
| 13  | Dispatch : existing TV show on Disk2 → merged with rsync backup                                                            | merge invariants           |
| 14  | Dispatch : crash after rsync but before index.add → next run recovers via filesystem scan                                  | idempotence                |
| 15  | Full pipeline : `personalscraper run --dry-run` on a 3-torrent seed → each phase's StepReport contains the expected counts | orchestrator               |

Shared fixtures land in `tests/e2e/conftest.py` :

- `staging_tree` : builds the `001-MOVIES/`, `002-TVSHOWS/`, ..., `097-TEMP/` tree.
- `fake_disks` : builds four `tmp_path / "Disk{N}"` dirs with the expected category sub-folders.
- `config_json5` : writes a complete `config.json5` pointing at the fixture paths.
- `fake_tmdb` / `fake_tvdb` : cheap session-scoped mocks returning canned JSON fixtures.
- `fake_qbit` : minimal in-memory torrent list.

## 5. Hotspot-file trimming

For each of the three files :

1. Enumerate every `@patch` and mark whether its target is **external** (network, subprocess, os-level) or **internal** (our own module).
2. Keep external mocks. Drop internal mocks where a real `tmp_path`-based fixture achieves the same goal.
3. Where a test asserts only "function was called with arg X", rewrite to assert on the observable effect (file created, JSON state updated) whenever practical. When it's truly a wiring test, keep the mock but reduce to a single narrow `patch` per test.

Concretely :

- `test_dispatcher.py` : replace `@patch("shutil.which", return_value="/usr/bin/rsync")` (on ~25 tests) with a session-scoped fixture that skips if rsync is actually missing. Drop `@patch("personalscraper.dispatch.dispatcher._rsync")` in favour of real small-file rsync in E2E tests.
- `test_cli.py` : collapse the pipeline-step mocks into a single `@pytest.fixture(autouse=True)` that stubs all step `run_*` to no-op StepReports, leaving only the test-specific narrow assertion. Tests that genuinely invoke the pipeline (if any) move to E2E.
- `test_pipeline_integration.py` : split. Three-quarters of it becomes a fast "orchestrator unit test" with a single mocked seam (an injected step dispatcher). The gate / ordering / error-propagation assertions move to E2E.

## 6. Runtime budget

- Current test suite : ~22 s on the dev laptop.
- Target after refactor : ≤ 30 s total (unit + E2E).
- Individual E2E tests : budget ≤ 1 s each (small file fixtures, no actual media). Test #15 (full pipeline) has a 5 s budget.
- If rsync is unavailable, the six tests that need it `pytest.skip` — CI image must have rsync (it already does on the project's runners).

## 7. Risks & mitigations

| Risk                                                                                   | Mitigation                                                                                                                                     |
| -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| E2E tests become flaky on filesystem edge cases (case-insensitivity, mtime resolution) | Centralise fs helpers in `tests/e2e/conftest.py`; assert on stable invariants (file presence, JSON keys), not on timestamps.                   |
| Runtime creeps past 30 s                                                               | Measure per-test via `pytest --durations=20` in CI; flag regressions >1 s/test.                                                                |
| Trimmed hotspot tests lose coverage on a real regression                               | The E2E catalogue covers the same invariants at a higher level; net coverage should go up, not down. Measured via `pytest --cov` before/after. |
| Mocks still needed for TMDB/TVDB need fresh fixtures                                   | Reuse existing `tests/scraper/fixtures/*.json` canned responses.                                                                               |
| Developer friction when writing a new test (which tier ?)                              | Write `docs/reference/testing.md` decision tree; one-liner in CLAUDE.md.                                                                       |

## 8. Success criteria

- `tests/e2e/` contains ≥ 15 passing tests.
- `@patch` count in the three hotspot files drops by ≥ 60%.
- Full suite runtime ≤ 30 s.
- Coverage (line + branch) does not regress — measured before/after via `pytest --cov`.
- `docs/reference/testing.md` documents the unit vs E2E decision rule.
- CI runs both tiers automatically.
