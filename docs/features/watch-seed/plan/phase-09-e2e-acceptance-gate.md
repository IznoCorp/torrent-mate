# Phase 9 — E2E roundtrip + ACCEPTANCE gate

## Gate

- **Requires Phase 1–8 ALL complete**: every prior phase must pass its own gate checks before this final integration gate. This phase does not build new features — it validates, hardens, and re-exercises every ACC criterion.

## Overview

Write the E2E roundtrip test (fixture `complete/` + fake trackers → sweep → assert SEED_PURE tags + obligations + ingest skips + Watcher predicate ignores). Run ALL ACC-1 through ACC-13. Check module sizes, layering guard, AppContext boundary, event catalog, and `make check` full pipeline. Fix any regressions found. Commit fixes. This phase is the **final quality gate** before PR.

### Sub-phases (5 commits)

| #   | Commit                                                                | Scope      |
| --- | --------------------------------------------------------------------- | ---------- |
| 9.1 | `test(watch-seed): add E2E roundtrip test — cross-seed → ingest skip` | E2E test   |
| 9.2 | `test(watch-seed): re-exercise ACC-1 through ACC-13`                  | ACC gate   |
| 9.3 | `chore(watch-seed): fix any regressions found during gate`            | Fixes      |
| 9.4 | `chore(watch-seed): update test feature map + event catalog`          | Maps       |
| 9.5 | `chore(watch-seed): final make check green + module size audit`       | Final gate |

## Sub-phase 9.1 — E2E roundtrip test (ACC-7)

**Files:**

- Create: `tests/e2e/test_cross_seed_roundtrip.py`

```python
"""E2E roundtrip: cross-seed injection → SEED_PURE tag → ingest skip.

Uses fake qBit client + fake HTTP transport for the tracker registry.
No real network calls, no real torrent filesystem.
"""

import pytest

from personalscraper.acquire.cross_seed import CrossSeedService


@pytest.mark.e2e
class TestCrossSeedRoundtrip:
    """ACC-7: injected cross-seed → SEED_PURE tag → ingest skips it."""

    def test_cross_seed_injection_survives_ingest_skip(self, fake_qbit, fake_registry,
                                                       fake_store, test_config):
        """Full roundtrip:
        1. Source torrent exists in fake qBit complete/ list.
        2. Fake registry returns one matching candidate.
        3. CrossSeedService.check() → inject → recheck 100% → tag SEED_PURE
           → write SeedObligation.
        4. Verify SEED_PURE tag is present on the injected torrent.
        5. Verify SeedObligation was written via SeedSubStore.
        6. Verify the injected torrent's info_hash IS in the SEED_PURE set
           (ingest predicate would skip it).
        """
        info_hash = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
        source_data = _make_source_torrent(info_hash)
        fake_qbit.add_torrent(source_data, save_path="/complete/Release.Name.2024",
                              tags=set())  # not SEED_PURE

        candidate_bytes = _make_candidate_torrent_bytes()
        fake_registry.add_candidate("lacale", info_hash, candidate_bytes)

        cs = CrossSeedService(
            registry=fake_registry,
            lister=fake_qbit,
            injector=fake_qbit,
            store=fake_store,
            config=test_config,
        )

        result = cs.check(info_hash)

        # Assert injection happened
        assert len(result.injected) >= 1

        # Assert SEED_PURE tag was applied
        torrents = fake_qbit.get_completed()
        injected = next(t for t in torrents if t.info_hash == info_hash)
        from personalscraper.core.tags import SEED_PURE
        assert SEED_PURE in injected.tags

        # Assert SeedObligation was written
        obligations = fake_store.find_active_under("/complete/Release.Name.2024")
        assert any(o.source_tracker == "lacale" for o in obligations)

    def test_watcher_predicate_ignores_seed_pure(self, fake_qbit):
        """Watcher work predicate (W7) must exclude SEED_PURE-tagged torrents."""
        from personalscraper.acquire.watcher import WatcherInput, WatcherService
        from personalscraper.conf.models.watch_seed import WatchConfig

        svc = WatcherService(WatchConfig())
        inp = WatcherInput(
            completed_hashes=frozenset({"hash1"}),
            ingested_hashes=frozenset(),
            seed_pure_hashes=frozenset({"hash1"}),  # same hash is SEED_PURE
            sentinel_present=False,
            pipeline_lock_held=False,
            now=1_000_000.0,
        )
        from personalscraper.acquire.watcher import WatcherState, WatcherDecision
        out = svc.evaluate(inp, WatcherState())
        # SEED_PURE exclusion → work predicate false → IDLE (no cross-seed, no run)
        assert out.decision == WatcherDecision.IDLE
```

The E2E test uses the `e2e` marker. Register it in `pyproject.toml` if not already present.

## Sub-phase 9.2 — re-exercise ALL ACC criteria

Run each ACC criterion as an executable check. Document the output of each:

| ACC    | Command                                                                                                                                                                                                                    | Expected                           | Phase |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ----- |
| ACC-1  | `python -m pytest tests/unit/test_torrent_layout.py -q`                                                                                                                                                                    | N passed, 0 failed                 | 1     |
| ACC-2  | `python -m pytest tests/unit/test_structural_match.py -q`                                                                                                                                                                  | N passed, 0 failed                 | 1     |
| ACC-3  | `python -c "from personalscraper.api.torrent._contracts import TorrentInjector; from personalscraper.api.torrent.qbittorrent import QBitClient; print(hasattr(QBitClient,'inject') and hasattr(QBitClient,'list_files'))"` | True                               | 2     |
| ACC-4  | `python -c "from personalscraper.conf.models.api_config import TrackerProviderConfig; print(TrackerProviderConfig().cross_seed)"` + `grep -c 'cross_seed' config/tracker.json5 config.example/tracker.json5`               | False / each ≥ 1                   | 3     |
| ACC-5  | `personalscraper cross-seed --help >/dev/null 2>&1 && echo OK`                                                                                                                                                             | OK                                 | 5     |
| ACC-6  | `python -m pytest tests/integration/acquire/test_cross_seed_service.py -q`                                                                                                                                                 | N passed, 0 failed                 | 4     |
| ACC-7  | `python -m pytest tests/e2e -q -k cross_seed`                                                                                                                                                                              | N passed, 0 failed                 | 9     |
| ACC-8  | `personalscraper watch --help >/dev/null 2>&1 && personalscraper watch-now --help >/dev/null 2>&1 && echo OK`                                                                                                              | OK                                 | 7     |
| ACC-9  | `python -m pytest tests/integration/acquire/test_watcher_loop.py -q -k sentinel`                                                                                                                                           | N passed, 0 failed                 | 7     |
| ACC-10 | `python -m pytest tests/unit/test_watcher_service.py -q`                                                                                                                                                                   | N passed, 0 failed                 | 6     |
| ACC-11 | `personalscraper run --help 2>&1 \| grep -c 'no-console'`                                                                                                                                                                  | ≥ 1                                | 7     |
| ACC-12 | `ls com.personalscraper.pipeline.plist.template scripts/install-launchd.sh scripts/uninstall-launchd.sh launchd-plists 2>&1 \| grep -c 'No such file'` + `test -f ecosystem.config.js && echo OK`                          | 4 / OK                             | 8     |
| ACC-13 | `make test 2>&1 \| tail -1`                                                                                                                                                                                                | "NNNN passed" with 0 failed/errors | 9     |

## Sub-phase 9.3 — fix regressions

Any ACC that fails in sub-phase 9.2 gets a fix commit in this sub-phase. Common regressions to watch for:

- **Config overlay drift**: `config/` has new fields but `config.example/` doesn't → add them.
- **AppContext boundary test failure**: new commands touch `AppContext` but aren't allowlisted → add to `test_app_context_boundary.py`.
- **Logging convention**: new modules use `structlog.get_logger` instead of `personalscraper.logger.get_logger` → fix + verify with `make lint`'s `check_logging.py`.
- **Module size**: any new module exceeds 800 LOC soft limit → refactor or split.
- **Event catalog**: new events not registered in the catalog → add.
- **Import errors**: a module imports from a package that's only available in type-checking context → move to `TYPE_CHECKING` guard.

## Sub-phase 9.4 — update test feature map + event catalog

**Files:**

- Modify: `tests/feature_map/watch-seed.json` (generated by pre-commit hook from test files)
- Modify: event catalog (if a central registry exists — check `personalscraper/core/event_bus.py`)

Run the feature map update:

```bash
python scripts/update_feature_map.py --check  # CI mode: fails if drift
python scripts/update_feature_map.py           # regenerate
```

Verify new events (`WatcherRunTriggered`, `CrossSeedInjected`, `CrossSeedRejected`) are in the catalog.

## Sub-phase 9.5 — final gate

Run the full quality pipeline:

```bash
make lint        # ruff + mypy + check_logging: 0 errors
make test        # All NNNN passed, 0 failed, 0 errors
make check       # lint + test + module-size + typed-api
python scripts/check-module-size.py  # all modules ≤ 1000 LOC
```

Additional checks:

- **Layering guard**: `python -m pytest tests/architecture/test_layering.py -q` — 0 violations.
- **AppContext boundary**: `python -m pytest tests/architecture/test_app_context_boundary.py -q` — 0 violations.
- **Residual import grep**: for any module deleted in this feature, grep `personalscraper/` and `tests/` for old import paths — zero matches.
- **Event catalog coherence**: `python -m pytest tests/architecture/test_event_schema_version.py -q` — pass.
- **Design gaps**: `python scripts/audit_design_coverage.py --strict` — pass (CI-only check).
- **Feature map**: `python scripts/update_feature_map.py --check` — pass.

## Gate check (FINAL — before PR)

- [ ] `make check` — all green.
- [ ] ACC-1 through ACC-13 ALL pass with documented output.
- [ ] `make test 2>&1 | tail -1` shows NNNN passed, 0 failed, 0 errors (ACC-13).
- [ ] Module size check: zero modules > 1000 LOC.
- [ ] Layering guard: zero violations.
- [ ] AppContext boundary: all new commands allowlisted.
- [ ] Event catalog: all new events registered.
- [ ] Config anti-drift: `diff <(grep -c 'cross_seed\|watch' config/config.json5) <(grep -c 'cross_seed\|watch' config.example/config.json5)` — identical counts.
- [ ] `python -c "import personalscraper"` — smoke test passes.
