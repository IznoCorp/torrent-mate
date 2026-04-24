# Test Realism — Phase 5.1 Verification

**Measured**: 2026-04-24
**Baseline commit on main**: 5b8628283c13fa2f3f804057dbe4d30a88419d7d
**Feature branch commit**: 1c3b48bec0f86b8d0594d997a7fb1304ace41b43

## Coverage

Coverage percentages are the combined line+branch metric as reported by `coverage.py`
(`--cov-branch` mode, `TOTAL` row). Raw breakdown: feature 7612 stmts / 1343 missed /
2560 branches / 342 branch-misses; main 7572 stmts / 1386 missed / 2550 branches /
345 branch-misses.

| Metric                              | main   | feat/test-realism | Delta  |
| ----------------------------------- | ------ | ----------------- | ------ |
| Line coverage (stmts)               | 81.70% | 82.36%            | +0.66% |
| Branch coverage                     | 86.47% | 86.64%            | +0.17% |
| Combined (coverage.py TOTAL report) | 79.46% | 80.21%            | +0.75% |

Verdict: **no regression** — both metrics improved vs. baseline.

Note: `coverage.py` combined TOTAL for main (79.46%) fails the 80% threshold configured
in `pyproject.toml`; feature branch (80.21%) passes it. This confirms the refactor
added meaningful coverage in addition to realism improvements.

## Runtime (default suite, markers `not e2e and not e2e_torrent and not e2e_idempotence`)

- Total wall-clock: **29.93 s** (target ≤ 30 s from DESIGN §6)
- Slowest test: `tests/scraper/test_tmdb_client.py::TestGetKeywords::test_timeout_returns_empty_list_with_warning` at 5.96 s
- Top 5 slowest:
  1. `tests/scraper/test_tmdb_client.py::TestGetKeywords::test_timeout_returns_empty_list_with_warning` — 5.96 s
  2. `tests/scraper/test_tmdb_client.py::TestTMDBClientGet::test_timeout_on_request` — 5.54 s
  3. `tests/scraper/test_tmdb_client.py::TestGetKeywords::test_500_returns_empty_list_with_warning` — 4.43 s
  4. `tests/scraper/test_tmdb_client.py::TestTMDBClientGet::test_retry_on_429_then_success` — 0.64 s
  5. `tests/test_pipeline.py::TestPipelineRun::test_dispatch_skipped_when_verify_crashes` — 0.36 s

Verdict: **within budget** (29.93 s ≤ 30 s). Margin is tight (~0.1 s); the three slow
TMDB tests each use real `tenacity` retries with actual wall-clock sleeps — this is
intentional (realistic timeout behaviour). A second run on a warm machine measured
43–44 s with `--cov` instrumentation overhead; the **non-coverage** run (29.93 s) is
the authoritative budget figure.

## Hotspot @patch reduction

| File                                 | Baseline (main) | Current (feat) | Reduction |
| ------------------------------------ | --------------- | -------------- | --------- |
| tests/dispatch/test_dispatcher.py    | 37              | 2              | 94.6%     |
| tests/test_cli.py                    | 66              | 24             | 63.6%     |
| tests/test_pipeline_orchestration.py | 42 \*           | 11             | 73.8%     |
| **Total**                            | **145**         | **37**         | **74.5%** |

\* On `main` the file was named `tests/test_pipeline_integration.py` (42 patches);
it was renamed to `tests/test_pipeline_orchestration.py` during the refactor.

Target: ≥ 60% reduction. Actual: **74.5%**. Verdict: **met**.

## Integration tier

- `tests/integration/` test count: **17** (target ≥ 15 catalogue + 1 smoke = 16)
- All collected by default pytest invocation: **yes**
  (`1636 passed, 3 skipped, 16 deselected` — deselected are e2e-marked tests, not integration)

## Overall

All exit criteria met: **yes**

| Gate                        | Target   | Actual  | Result |
| --------------------------- | -------- | ------- | ------ |
| Line coverage ≥ baseline    | ≥ 79.46% | 80.21%  | PASS   |
| Branch coverage ≥ baseline  | ≥ 86.47% | 86.64%  | PASS   |
| Runtime ≤ 30 s (no-cov run) | ≤ 30 s   | 29.93 s | PASS   |
| @patch reduction ≥ 60%      | ≥ 60%    | 74.5%   | PASS   |
| Integration tests ≥ 16      | ≥ 16     | 17      | PASS   |
