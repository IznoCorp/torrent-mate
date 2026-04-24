# DESIGN — Test Realism Refactor

**Codename**: `test-realism`
**Type**: test / refactor (minor SemVer bump — no production behaviour change, but test suite reshuffled)
**Status**: preparation — updated 2026-04-24 against `feat/test-realism` baseline (`d98ee04`)

## 1. Problem

Three test files dominate the suite by volume and share a common pathology: they rely on `unittest.mock.patch` / `pytest-mock` to replace so many collaborators that the test ends up verifying the mocks, not the code.

Representative counts (measured on `feat/test-realism` at `d98ee04`, 2026-04-24) :

| File                                 | `@patch` calls | Real coverage concern                                                                                                                                                                                                             |
| ------------------------------------ | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/dispatch/test_dispatcher.py`  | 37             | rsync, disk status, shutil.which — every subprocess and filesystem interaction is mocked. Dispatch-vs-filesystem invariants are untested (cross-FS move, no-space skip, rollback after rsync failure).                            |
| `tests/test_cli.py`                  | 66             | Config loader, lock acquire/release, settings, every pipeline step, logging — the CLI is tested with the pipeline stubbed to constants. Wiring from flag → subcommand → pipeline argument is mostly mock wiring.                  |
| `tests/test_pipeline_integration.py` | 42             | All 6 pipeline phases mocked via a MagicMock settings/config. The orchestrator is tested against its own scaffolding; bugs in order-of-operations, gating between steps, state-file coherence, and JSON invariants are invisible. |

Symptoms this has masked in production (from recent bug runs) :

- Dispatch leaving orphans in `_tmp_dispatch_*` after rsync failure — unit tests green.
- Tracker JSON silently becoming empty on corruption — unit tests green.
- AnimeRule `applies_to="movies"` matching no media — unit tests green.

Plain-language summary : the current suite tells us the Python code runs; it does not tell us the pipeline works.

## 2. What already exists (do NOT duplicate)

Audit done on 2026-04-24 :

- `tests/e2e/` is **not empty** — it contains 136 tests and a rich infrastructure : `registry.py`, `markers.py`, `cleanup.py`, `golden.py`, `setup_torrents.py`, `torrentifier.py`, `assertions.py`. All of these tests are **manual-only** and excluded from the default pytest run.
- Default collection rule in `pyproject.toml` : `addopts = "-m 'not e2e and not e2e_torrent and not e2e_idempotence'"`. Markers `roundtrip`, `e2e`, `e2e_torrent`, `e2e_idempotence` gate this tier.
- Existing manual E2E tests need : a running `qBittorrent`, real `.torrent` files in `assets/torrents/`, valid TMDB/TVDB API keys, and `Storage disks` mounted read-only.
- `docs/reference/testing.md` exists (54 lines) but documents only the existing manual tiers ; it does not expose any decision rule for "which tier does a new test belong to ?".
- `tests/fixtures/config.py::test_config` provides a stable synthetic `Config` fixture — reusable verbatim.
- `tests/test_pipeline_integration.py::integration_settings` already demonstrates a `MagicMock` + `tmp_path` seam — lesson learned : it is strictly mock-driven, so it does not test the pipeline, it tests the mocks.

**Consequence** : the feature must add a **new tier** without touching the existing manual `tests/e2e/` suite. The chosen name for the new tier is `tests/integration/` — see §3.

## 3. Target state (revised)

Three tiers, each with a clear mandate :

| Tier                  | Location                      | When it runs                       | Mocks                                         | Owns                                          |
| --------------------- | ----------------------------- | ---------------------------------- | --------------------------------------------- | --------------------------------------------- |
| Unit                  | `tests/<module>/test_*.py`    | Default (`pytest`)                 | External I/O boundaries only                  | Single-function / single-class invariants     |
| **Integration (new)** | `tests/integration/test_*.py` | Default (`pytest`)                 | Only network (TMDB, TVDB, qBit API)           | Cross-module flow on a real `tmp_path` tree   |
| Manual E2E            | `tests/e2e/test_*.py`         | Manual (`pytest -m e2e_torrent …`) | Nothing — real qBit, real torrents, real APIs | Smoke + roundtrip against real infrastructure |

Key invariants of the new integration tier :

1. Runs in CI without any external service. No network calls. No qBit. No real media.
2. Each test spins up a real staging tree (`001-MOVIES/`, `002-TVSHOWS/`, …, `097-TEMP/`) under `tmp_path` and real `tmp_path / "Disk{1..4}"` destination disks.
3. `rsync` is invoked as a real subprocess (tests `pytest.skip` cleanly if `shutil.which("rsync")` is None).
4. TMDB / TVDB / qBittorrent are the **only** mocked collaborators, via fixtures that return canned JSON fixtures shared with `tests/scraper/fixtures/`.
5. Tests must not import from `tests/e2e/` — the two tiers share no code. `tests/e2e/` stays fully intact.

## 4. Integration test catalogue (target ≥ 15)

Each test is a `with tmp_path:` block or fixture-based, no Docker, no network, no manual setup.

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

Shared fixtures land in `tests/integration/conftest.py` :

- `staging_tree` : builds `001-MOVIES/`, `002-TVSHOWS/`, …, `097-TEMP/` under `tmp_path`, populated from `config.staging_dirs`.
- `fake_disks` : builds four `tmp_path / "Disk{N}"` dirs with the expected category sub-folders.
- `integration_config` : composes `config.json5` pointing at `staging_tree` + `fake_disks` (reuses `tests/fixtures/config.py::test_config` as seed).
- `fake_tmdb` / `fake_tvdb` : session-scoped monkeypatched clients returning canned JSON from `tests/scraper/fixtures/`.
- `fake_qbit` : minimal in-memory torrent list, monkeypatched into `personalscraper.ingest.ingest`.

## 5. Hotspot-file trimming

For each of the three files (@patch counts measured on `d98ee04`) :

1. Enumerate every `@patch` and mark whether its target is **external** (network, subprocess, os-level) or **internal** (our own module).
2. Keep external mocks. Drop internal mocks where a real `tmp_path`-based fixture achieves the same goal.
3. Where a test asserts only "function was called with arg X", rewrite to assert on the observable effect (file created, JSON state updated) whenever practical. When it's truly a wiring test, keep the mock but reduce to a single narrow `patch` per test.

Concretely :

- `test_dispatcher.py` (37 `@patch`, mostly `shutil.which`) : replace the 25 copies of `@patch("shutil.which", return_value="/usr/bin/rsync")` with a session-scoped fixture `rsync_available` that skips if rsync is actually missing. Drop `@patch("personalscraper.dispatch.dispatcher._rsync")` in favour of real small-file rsync covered by the new integration tier. Target : ≤ 15 `@patch` remaining.
- `test_cli.py` (66 `@patch`) : collapse the pipeline-step mocks into a single `@pytest.fixture(autouse=True)` that stubs all step `run_*` to no-op StepReports, leaving only the test-specific narrow assertion. Tests that genuinely invoke the pipeline (if any) move to integration. Target : ≤ 25 `@patch` remaining.
- `test_pipeline_integration.py` (42 `@patch`) : split. Three-quarters of it becomes a fast "orchestrator unit test" with a single mocked seam (an injected step dispatcher). The gate / ordering / error-propagation assertions move to integration. Target : ≤ 15 `@patch` remaining, file renamed `tests/test_pipeline_orchestrator.py` to clarify its scope.

## 6. Runtime budget

- Current default test suite : ~7 s (reported by `make test`, excludes e2e / e2e_torrent / e2e_idempotence markers).
- Target after refactor : ≤ 30 s total (unit + integration).
- Individual integration tests : budget ≤ 1 s each. Test #15 (full pipeline) has a 5 s budget.
- If rsync is unavailable, the six integration tests that need it `pytest.skip` — CI image must have rsync (it already does on the project's runners).

## 7. Risks & mitigations

| Risk                                                                                                                        | Mitigation                                                                                                                                             |
| --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Integration tests become flaky on filesystem edge cases (case-insensitivity, mtime resolution)                              | Centralise fs helpers in `tests/integration/conftest.py`; assert on stable invariants (file presence, JSON keys), not on timestamps.                   |
| Naming collision between `tests/e2e/` (manual) and `tests/integration/` (CI) confuses contributors                          | `docs/reference/testing.md` decision tree + CLAUDE.md one-liner; integration tier lives under a distinct directory, no shared imports.                 |
| Runtime creeps past 30 s                                                                                                    | Measure per-test via `pytest --durations=20` in CI; flag regressions >1 s/test.                                                                        |
| Trimmed hotspot tests lose coverage on a real regression                                                                    | The integration catalogue covers the same invariants at a higher level; net coverage should go up, not down. Measured via `pytest --cov` before/after. |
| Mocks still needed for TMDB/TVDB need fresh fixtures                                                                        | Reuse existing `tests/scraper/fixtures/*.json` canned responses.                                                                                       |
| Developer friction when writing a new test (which tier ?)                                                                   | Write `docs/reference/testing.md` decision tree; one-liner in CLAUDE.md.                                                                               |
| `integration_settings` / `integration_config` fixtures in `test_pipeline_integration.py` already exist as MagicMock hybrids | Phase 4 rename to `test_pipeline_orchestrator.py` explicitly removes these mock hybrids and replaces with real `tmp_path` fixtures from phase 1.       |

## 8. Success criteria

- `tests/integration/` contains ≥ 15 passing tests collected by the default `pytest` invocation.
- Default `pytest` still excludes `e2e`, `e2e_torrent`, `e2e_idempotence`, `roundtrip` markers.
- `@patch` count in the three hotspot files drops by ≥ 60% (from 145 total to ≤ 58).
- Full default suite runtime ≤ 30 s on reference hardware (measured via `pytest --durations=20`).
- Coverage (line + branch) does not regress — measured before/after via `pytest --cov`.
- `docs/reference/testing.md` documents the three tiers with a clear decision rule for new tests.
- CLAUDE.md gains a one-line pointer to the decision rule.
- `tests/e2e/` untouched (no files added, removed, or modified — verified by diff).
