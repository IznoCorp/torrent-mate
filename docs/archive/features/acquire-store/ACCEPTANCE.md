# ACCEPTANCE — acquire-store (RP3)

All criteria are executable shell commands with documented expected output.
Re-exercise every ACC-NN criterion before squash merge (SH-16 convention).

## ACC-01 — Smoke import

```bash
python -c "import personalscraper"
```

Expected: exit 0 (no ImportError).

## ACC-02 — core/sqlite importable and event-free

```bash
python -c "
from personalscraper.core.sqlite import open_db, db_lock, apply_migrations, probe_mount
from personalscraper.core.sqlite.errors import SqliteLockError, SqliteCorruptError
import inspect, personalscraper.core.sqlite._open as m
sig = inspect.signature(m.open_db)
assert 'event_bus' not in sig.parameters, 'core open_db must be event-free'
print('ACC-02 OK')
"
```

Expected: `ACC-02 OK`

## ACC-03 — IndexerXxxError isinstance core markers

```bash
python -m pytest tests/indexer/test_core_sqlite_isinstance.py -v --tb=short 2>&1 | tail -5
```

Expected: `6 passed`

## ACC-04 — acquire.json5 config overlay

```bash
ls config/acquire.json5
```

Expected: file present (exit 0).

## ACC-05 — AcquireConfig derives db_path

```bash
python -c "
from personalscraper.conf.models.acquire import AcquireConfig
cfg = AcquireConfig(db_path=None)
assert cfg.db_path is None
print('ACC-05 OK: field accepts None for deferred resolve')
"
```

Expected: `ACC-05 OK: field accepts None for deferred resolve`

## ACC-06 — Migration contract on fresh acquire.db

```bash
python -m pytest tests/acquire/test_migrations.py::TestAcquireMigrations001 -v --tb=short 2>&1 | tail -5
```

Expected: `6 passed`

## ACC-07 — All four tables present

```bash
python -m pytest tests/acquire/test_store.py::test_all_four_tables_exist -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-08 — Fail-open: store-absent deletion proceeds

```bash
python -m pytest tests/acquire/test_delete_authority.py::test_store_absent_returns_allow -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-09 — Fail-open: store lookup error → ALLOW

```bash
python -m pytest tests/acquire/test_delete_authority.py::test_lookup_exception_fail_open_with_mutation_proof -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-10 — VETO on active unmet obligation

```bash
python -m pytest tests/acquire/test_delete_authority.py::test_seedtime_not_met_veto -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-11 — Stale obligation inert (obligation-then-kill-before-move)

```bash
python -m pytest tests/acquire/test_delete_authority.py::test_stale_obligation_mutation_proof -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-12 — record_dispatch HIT writes obligation

```bash
python -m pytest tests/acquire/test_record_dispatch.py::test_record_dispatch_hit_writes_obligation -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-13 — record_dispatch fail-soft on client error

```bash
python -m pytest tests/acquire/test_record_dispatch.py::test_record_dispatch_fail_soft_on_client_error -v --tb=short 2>&1 | tail -5
```

Expected: `1 passed`

## ACC-14 — Crash-window: stale obligation + re-run + lock-free concurrency

```bash
python -m pytest tests/acquire/test_crash_window.py -v --tb=short 2>&1 | tail -5
```

Expected: `5 passed`

## ACC-15 — Layering: dispatch/maintenance ⇏ acquire

```bash
python -m pytest tests/architecture/test_layering.py -v -k "deleter" --tb=short 2>&1 | tail -5
```

Expected: `3 passed, 12 deselected`

## ACC-16 — make check green

```bash
make check 2>&1 | tail -5
```

Expected: exit 0, summary line shows `6425 passed, 3 skipped, 2 xfailed` with `0 failed` / `0 error`.
