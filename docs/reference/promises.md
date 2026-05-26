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

## Close-to-block modules (2026-05-24)

Last refreshed 2026-05-24 — regenerate via:
`python3 scripts/check-module-size.py`.

Modules within 100 LOC of the 1000 BLOCK ceiling:

| Module                                          | LOC | Distance to BLOCK |
| ----------------------------------------------- | --- | ----------------- |
| `personalscraper/scraper/tv_service.py`         | 998 | **2 LOC**         |
| `personalscraper/scraper/existing_validator.py` | 917 | 83 LOC            |

Any feature touching these modules must either stay under the ceiling or split
before merging.

## Split plan (deferred to 0.17+)

Per Phase 8 §8.11 (Option B): splitting `tv_service.py` and `existing_validator.py`
is deferred to 0.17+. The 0.16.0 scope is limited to enforcing the hard-block and
documenting the near-block risk. When 0.17+ picks this up:

- `tv_service.py` (998): extract TVDB-specific helpers to `_tvdb.py` or split by
  concern (search vs. episode vs. season).
- `existing_validator.py` (917): extract NFO validation to `_nfo_validator.py`.

Until then, these modules are **split-required** before any feature that would
add > 2 LOC to `tv_service.py` or > 83 LOC to `existing_validator.py`.

## Integration

```bash
make check   # includes: python3 scripts/check-module-size.py
```

Any module hitting 1000 LOC fails `make check` → blocks merge.
