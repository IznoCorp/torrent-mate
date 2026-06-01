# Module Size Budget — Hard-Block Promise

**Status**: FULFILLED in 0.16.0 (promised in 0.10.0 DESIGN arch-cleanup, stalled 5 versions).

**Enforcement**: `scripts/check-module-size.py` — wired into `make check` (Makefile line 63).

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

## Close-to-block modules (2026-06-01)

Last refreshed 2026-06-01 — regenerate via:
`python3 scripts/check-module-size.py`.

Module LOC are non-blank-line counts (the proxy used by
`scripts/check-module-size.py`). The scraper modules nearest the ceiling:

| Module                                          | LOC | Distance to BLOCK |
| ----------------------------------------------- | --- | ----------------- |
| `personalscraper/scraper/movie_service.py`      | 975 | 25 LOC            |
| `personalscraper/scraper/tv_service.py`         | 797 | 203 LOC           |
| `personalscraper/scraper/existing_validator.py` | 642 | 358 LOC           |

Only `movie_service.py` (975) is still within 100 LOC of the 1000 BLOCK ceiling
and remains the single near-WARN/near-block file. `tv_service.py` (797) is just
under the 800 WARN threshold, and `existing_validator.py` (642) is now well
below both. Any feature touching `movie_service.py` must either stay under the
ceiling or split before merging.

## Split plan

`movie_service.py` (975) is the remaining split candidate: if a feature would
push it over the 1000 BLOCK ceiling, extract a cohesive concern (e.g. movie NFO
emission or artwork resolution) into a sibling helper module before merging.

`tv_service.py` and `existing_validator.py` were near-block in earlier versions
(998 and 917 respectively at 0.16.0) but have since dropped below the WARN
threshold; no split is currently required for them.

## Integration

```bash
make check   # includes: python3 scripts/check-module-size.py
```

Any module hitting 1000 LOC fails `make check` → blocks merge.
