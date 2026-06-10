# acquire-store: Total Lock Order

## Invariant

```
pipeline.lock (outer)
 └─ indexer_lock
      └─ acquire.db.lock (leaf — migration only)
```

No `acquire.db` writer may acquire `pipeline.lock` or `indexer_lock` while
holding `acquire.db.lock`. Opposite-order pairs are structurally unreachable,
making the system provably deadlock-free.

`acquire.db` is a **separate SQLite file** from `library.db`, so the indexer
scan's `library.db` writer never contends with the `acquire.db` writer — a
structural reduction of lock pressure independent of the lock-order discipline.

## Lock model (DESIGN §6.3, implemented sub-phase 3.4)

### `acquire.db.lock` — brief migration-only leaf

The core `db_lock` (FileLock, `personalscraper/core/sqlite/_lock.py::db_lock`)
is taken **ONLY** around `open_db` + `apply_migrations` in `_ensure_open`, with a
generous timeout (`_MIGRATION_LOCK_TIMEOUT_S = 10.0`, never `timeout=0`).
`apply_migrations` is idempotent — a no-op once `user_version` is current — so
the steady-state path holds this lock for **microseconds**. It is released
immediately after the `with` block exits; the `sqlite3.Connection` survives
without any held lock.

The lock is a **strict leaf**:

- Never held across a filesystem operation (`shutil.move`, `os.unlink`, `rsync`).
- Never held across a qBit/Transmission HTTP call.
- Never held for the store's lifetime (the 3.3 lifetime-lock regression is
  removed — see DESIGN §6.3 change-log).

### Runtime writes — SQLite-native single-writer (no FileLock)

Cross-process single-writer is provided by **SQLite itself**:

- `acquire.db` is opened in **WAL** mode (canonical PRAGMA set including
  `busy_timeout=5000`).
- Every write goes through `BEGIN IMMEDIATE` (`_write_tx`, store.py line 224).
  SQLite serializes writers across processes — the **same model** used by the
  indexer outbox publisher and the Phase-5 lock-free seed-obligation writer.
- **No per-write `FileLock`.** Write serialization is delegated to SQLite's
  built-in lock manager, which is safe across processes in WAL mode.

### Reads — lock-free (WAL)

No lock anywhere on the read path. This is a **hard requirement** of the
Phase-4/5 fail-open delete-permit reader, which must never block on or contend
for the writer lock.

### Lazy open

`build_acquire_store(config)` returns an **inert** handle — no `mkdir`, no
connection, no lock, no migration. The connection opens on the **first
sub-store access** via `_ensure_open`. Commands that never touch acquire state
(e.g. the library-index cron, read-only JSON CLI commands) open nothing and take
no lock — the shared composition root does **not** serialize unrelated commands.

## Rules

1. **`acquire.db.lock` is a brief migration-only leaf** — held only around
   `open_db` + `apply_migrations` in `_ensure_open`, then released immediately.
   Runtime writes use SQLite-native serialization (`BEGIN IMMEDIATE` +
   `busy_timeout`), not the FileLock. The lock is never held across any FS
   operation or HTTP call.

2. **`record_dispatch` goes through the store's `BEGIN IMMEDIATE` path** —
   the dispatch-time seed-obligation writer (`delete_authority.py::record_dispatch`)
   calls `store.seed.add()` which uses `_write_tx` (`BEGIN IMMEDIATE`), **not**
   the `acquire.db.lock` FileLock. This keeps the dispatch critical path
   lock-free from the FileLock perspective — dispatch holds no acquire lock.

3. **`indexer_lock` precedes `acquire.db.lock`** — if both locks are needed in
   the same call chain, the total order `pipeline.lock > indexer_lock >
acquire.db.lock` must be followed. In practice no RP3 code path acquires
   both simultaneously; the structural separation (`acquire.db` ≠ `library.db`)
   makes mutual exclusion unnecessary for the two databases.

## Implementation reference

- Pipeline lock: `personalscraper/lock.py::acquire_lock` (PID-based filesystem
  lock, configurable `data_dir`; existing, unchanged by RP3)
- Indexer lock: `personalscraper/indexer/db.py::indexer_lock` → delegates to
  `core/sqlite/_lock.py::db_lock`
- Core db_lock: `personalscraper/core/sqlite/_lock.py::db_lock` (FileLock, used
  by both `indexer_lock` and the brief acquire migration lock)
- Acquire store writer: `personalscraper/acquire/store.py`:
  - `_ensure_open()` — brief leaf lock around open+migrate
  - `_write_tx()` — `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` (no FileLock)
- Lock-free obligation writer:
  `personalscraper/acquire/delete_authority.py::record_dispatch` — uses
  `store.seed.add()` (`BEGIN IMMEDIATE` path, no `acquire.db.lock` FileLock)
