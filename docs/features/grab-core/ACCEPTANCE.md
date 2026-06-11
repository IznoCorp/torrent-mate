# ACCEPTANCE — grab-core (RP5b)

Every criterion is an executable shell command. Run from the repo root.
All must pass before squash merge.

---

## ACC-01 — Within-tracker same info_hash dedup → one survivor + -QTZ cross-tracker pair merges

```bash
python -m pytest \
    tests/acquire/test_dedup.py::test_dedup_same_info_hash_within_tracker_collapses \
    tests/acquire/test_dedup.py::test_dedup_qtz_aac_pair_merges_exact_size \
    tests/acquire/test_dedup.py::test_dedup_qtz_dts_pair_merges_via_size_tolerance \
    -v
```

Expected: `3 passed`

---

## ACC-02 — Sub-floor resolution filtered + None-resolution passes (fail-open) + mocked add → GrabSucceeded

```bash
python -m pytest \
    tests/acquire/test_filters.py::test_resolution_floor_drops_below_minimum \
    tests/acquire/test_filters.py::test_resolution_none_fails_open \
    tests/acquire/test_orchestrator.py::test_grab_happy_path_emits_exactly_one_grab_succeeded_exact_payload \
    -v
```

Expected: `3 passed`

---

## ACC-03 — Two concurrent claim_for_search → exactly one wins + record_dispatch never called during grab + failure → row retriable

```bash
python -m pytest \
    tests/acquire/test_service.py::test_claim_for_search_atomic_only_one_wins \
    tests/acquire/test_orchestrator.py::test_all_trackers_errored_retryable_not_abandoned \
    tests/acquire/test_orchestrator.py::test_negative_seed_write_never_called_during_full_success \
    -v
```

Expected: `3 passed`

---

## ACC-04 — `personalscraper grab --dry-run` over a seeded wanted item prints the ranked candidate without adding

```bash
python -m pytest \
    tests/commands/test_grab.py::test_grab_dry_run_prints_top_candidate \
    -v
```

Expected: `1 passed`

---

## ACC-05 — `make check` green

```bash
make check
```

Expected: exit code 0.

```
ruff: All checks passed! 877 files already formatted
mypy: Success: no issues found in 326 source files
check_logging: 0 finding(s): 0 error(s), 0 warning(s)
6655 passed, 3 skipped, 2 xfailed
check-module-size: 1 finding(s) (pre-existing movie_service.py WARN, not grab-core)
check-typed-api: OK
check-pragma-discipline: OK
audit-cli-coverage: 3 finding(s) — exit 0 (fail-soft; pre-existing, not grab-core)
cli-coverage-report: OK — 0 ❌ on critical commands
```
