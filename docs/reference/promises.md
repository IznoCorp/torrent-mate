# Module Size Budget — Hard-Block Promise

**Status**: FULFILLED in 0.16.0 (promised in 0.10.0 DESIGN arch-cleanup, stalled 5 versions).

**Enforcement**: `scripts/check-module-size.py` — wired into `make check` (Makefile line 76).

## Thresholds

| Level | LOC       | Behavior                                           |
| ----- | --------- | -------------------------------------------------- |
| WARN  | 800 - 999 | Printed to stderr, exit 0                          |
| BLOCK | ≥ 1000    | Printed to stdout, **exit 1** (fails `make check`) |

Soft ceiling: 800 LOC (cognitive-load advisory). Hard ceiling: 1000 LOC (build-breaking).

## Rationale

DEV #46 — The 0.10.0 DESIGN §13 (arch-cleanup) promised hard-block enforcement at
1000 LOC. The script existed since 0.10.0 but the `--strict` flag that was supposed
to gate it was dead code (defined, parsed, never inspected). Actual exit logic
already returned 1 for REPORT-level findings — but there were none to trip it.
The 0.16.0 action cleaned the dead flag and documented the convention here so
the hard-block is auditable and the promise is closed.

## Close-to-block modules (2026-08-16)

Last refreshed 2026-08-16 — regenerate via:
`python3 scripts/check-module-size.py`.

Module LOC are non-blank-line counts (the proxy used by
`scripts/check-module-size.py`). Current WARN findings (7 modules at or above
the 800 soft ceiling):

| Module                                        | LOC | Distance to BLOCK |
| --------------------------------------------- | --- | ----------------- |
| `personalscraper/acquire/orchestrator.py`     | 999 | 1 LOC             |
| `personalscraper/web/routes/acquisition.py`   | 999 | 1 LOC             |
| `personalscraper/trailers/cli.py`             | 961 | 39 LOC            |
| `personalscraper/acquire/store.py`            | 873 | 127 LOC           |
| `personalscraper/acquire/_wanted_store.py`    | 851 | 149 LOC           |
| `personalscraper/maintenance/rescraper.py`    | 851 | 149 LOC           |
| `personalscraper/web/models/acquisition.py`   | 805 | 195 LOC           |

`acquire/orchestrator.py` and `web/routes/acquisition.py` both sit at 999 —
**one line** below the 1000 BLOCK ceiling. Any feature touching either module
must extract a cohesive concern into a sibling module before merging (as was
done for `acquire/_query.py`, extracted from the acquisition hot path).

The scraper modules that were near the ceiling in earlier refreshes have all
dropped well below the WARN threshold: `movie_service.py` (614),
`tv_service.py` (704), `existing_validator.py` (535).

## Split plan

The two 999-LOC modules (`acquire/orchestrator.py`,
`web/routes/acquisition.py`) are the active split candidates: any change that
adds a net line to either one trips the BLOCK and fails `make check`, so the
extraction must happen **first**, in the same PR. The remaining WARN modules
(`trailers/cli.py`, `acquire/store.py`, `acquire/_wanted_store.py`,
`maintenance/rescraper.py`, `web/models/acquisition.py`) have 39–195 LOC of
headroom; split them opportunistically when a feature grows them toward the
ceiling.

`movie_service.py`, `tv_service.py`, and `existing_validator.py` were
near-block in earlier versions (975, 998, and 917 at their peaks) but have
since dropped below the WARN threshold; no split is required for them.

## Integration

```bash
make check   # includes: python3 scripts/check-module-size.py
```

Any module hitting 1000 LOC fails `make check` → blocks merge.
