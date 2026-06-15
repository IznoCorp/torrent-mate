# ACCEPTANCE — ownership (RP6)

All criteria are executable shell commands with documented expected output.
Re-exercise every ACC-NN criterion before squash merge (SH-16 convention).

## ACC-01 — Smoke import

```bash
python -c "import personalscraper"
```

Expected: exit 0 (no ImportError).

## ACC-02 — Core port importable

```bash
python -c "
from personalscraper.core.ownership import OwnershipChecker, NullOwnershipChecker
from personalscraper.core.identity import MediaRef
checker = NullOwnershipChecker()
assert checker.owns(MediaRef(tvdb_id=1), kind='movie') is False
print('ACC-02 OK')
"
```

Expected: `ACC-02 OK`

## ACC-03 — NullOwnershipChecker satisfies Protocol

```bash
python -c "
from personalscraper.core.ownership import OwnershipChecker, NullOwnershipChecker
assert isinstance(NullOwnershipChecker(), OwnershipChecker)
print('ACC-03 OK')
"
```

Expected: `ACC-03 OK`

## ACC-04 — Predicate: owned movie returns True

```bash
python -m pytest tests/indexer/test_ownership_predicate.py::TestIsOwnedMovie::test_owned_movie_tvdb_match_returns_true -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-05 — Predicate: soft-deleted movie returns False

```bash
python -m pytest tests/indexer/test_ownership_predicate.py::TestIsOwnedMovie::test_soft_deleted_movie_returns_false -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-06 — Predicate: provider-id fallback (tmdb) returns True

```bash
python -m pytest tests/indexer/test_ownership_predicate.py::TestIsOwnedMovie::test_provider_id_fallback_tmdb -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-07 — Mutation proof: deleted_at IS NULL filter is load-bearing

```bash
python -m pytest tests/indexer/test_ownership_predicate.py::TestSoftDeleteFilterLoadBearing -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-08 — Adapter: fail-soft on closed checker returns False (no raise)

```bash
python -m pytest tests/indexer/test_ownership_adapter.py::test_fail_soft_closed_checker_returns_false -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-09 — Adapter: fail-soft on any exception returns False (no raise)

```bash
python -m pytest tests/indexer/test_ownership_adapter.py::test_fail_soft_does_not_raise_on_any_exception -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-10 — Full ownership test suite

```bash
python -m pytest tests/core/test_ownership.py tests/indexer/test_ownership_predicate.py tests/indexer/test_ownership_adapter.py tests/integration/test_ownership_wiring.py -v --tb=short 2>&1 | tail -5
```

Expected: all pass, 0 failures, 0 errors.

## ACC-11 — Layering: acquire/ does NOT import indexer/

```bash
python -m pytest tests/architecture/test_layering.py::test_acquire_does_not_import_triage -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-12 — Layering: core/ does NOT import upward (includes indexer/)

```bash
python -m pytest tests/architecture/test_layering.py::test_core_does_not_import_upward -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-13 — Composition root: NullOwnershipChecker when no library.db

```bash
python -m pytest tests/integration/test_ownership_wiring.py::test_ownership_null_when_no_library_db -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-14 — Composition root: IndexerOwnershipChecker wired when library.db exists

```bash
python -m pytest tests/integration/test_ownership_wiring.py::test_ownership_wired_with_library_db -v --tb=short 2>&1 | tail -3
```

Expected: `1 passed`

## ACC-15 — make check green

```bash
make check 2>&1 | tail -5
```

Expected: exit 0, summary line shows 0 failed / 0 errors.
