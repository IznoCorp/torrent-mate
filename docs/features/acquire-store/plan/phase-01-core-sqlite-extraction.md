# Phase 01 — core/sqlite extraction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract all neutral SQLite machinery from `personalscraper/indexer/db.py` into a new
`personalscraper/core/sqlite/` package, keeping the indexer `db.py` as a thin re-export shim so
all 77 test files keep working without modification.

**Architecture:** The core package stays completely event-free — no `EventBus` param, no import of
`indexer/events.py`. The indexer subclasses core markers; the shim re-exports every public symbol.
One test assertion on `indexer.lock.stale_recovered` is updated to `core.sqlite.lock.stale_recovered`.

**Tech stack:** stdlib `sqlite3`, `filelock`, `personalscraper.logger.get_logger` (NOT
`structlog.get_logger`).

---

## Gate (from previous phase)

Phase 1 is the **first phase** — no prior phase. Start from a clean `feat/acquire-store` branch.
Verify: `git branch --show-current` → `feat/acquire-store`.

---

## File map

| Action | Path                                                                   |
| ------ | ---------------------------------------------------------------------- |
| Create | `personalscraper/core/sqlite/__init__.py`                              |
| Create | `personalscraper/core/sqlite/errors.py`                                |
| Create | `personalscraper/core/sqlite/_pragmas.py`                              |
| Create | `personalscraper/core/sqlite/_fs_probe.py` (moved from `indexer/`)     |
| Create | `personalscraper/core/sqlite/_open.py`                                 |
| Create | `personalscraper/core/sqlite/_lock.py`                                 |
| Create | `personalscraper/core/sqlite/_migrate.py`                              |
| Modify | `personalscraper/indexer/db.py` (re-export shim + re-parent errors)    |
| Modify | `personalscraper/indexer/_fs_probe.py` (keep as re-export shim)        |
| Modify | `tests/indexer/test_db.py` line 186 (event string rename)              |
| Create | `tests/indexer/test_core_sqlite_isinstance.py` (isinstance regression) |

---

### Task 1 — Create `core/sqlite/errors.py` with bare marker exceptions

**Files:**

- Create: `personalscraper/core/sqlite/errors.py`
- Test: `tests/indexer/test_core_sqlite_isinstance.py`

- [ ] **Step 1: Write the failing isinstance regression test**

```python
# tests/indexer/test_core_sqlite_isinstance.py
"""Regression test: IndexerXxxError subclasses core Sqlite markers (RP3 Phase 1)."""
from __future__ import annotations

import pytest

from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
    SqliteLockError,
    SqliteMigrationError,
)
from personalscraper.indexer.db import (
    IndexerCorruptError,
    IndexerDiskFullError,
    IndexerFKOrphansError,
    IndexerInvalidPathError,
    IndexerLockError,
    IndexerMigrationError,
)


def test_indexer_lock_error_is_sqlite_lock_error() -> None:
    err = IndexerLockError(pid=42)
    assert isinstance(err, SqliteLockError)
    assert err.pid == 42


def test_indexer_corrupt_error_is_sqlite_corrupt_error(tmp_path) -> None:
    from pathlib import Path
    err = IndexerCorruptError(db_path=tmp_path / "a.db", quarantine_path=tmp_path / "a.db.bak")
    assert isinstance(err, SqliteCorruptError)


def test_indexer_diskfull_error_is_sqlite_diskfull_error(tmp_path) -> None:
    from pathlib import Path
    err = IndexerDiskFullError(path=tmp_path / "a.db", free_bytes=100, required_bytes=500)
    assert isinstance(err, SqliteDiskFullError)


def test_indexer_invalid_path_error_is_sqlite_invalid_path_error(tmp_path) -> None:
    from pathlib import Path
    err = IndexerInvalidPathError(db_path=tmp_path / "a.db", mount_point="/Volumes/ext")
    assert isinstance(err, SqliteInvalidPathError)


def test_indexer_fkorphans_error_is_sqlite_fkorphans_error() -> None:
    err = IndexerFKOrphansError(orphan_count=3)
    assert isinstance(err, SqliteFKOrphansError)
    assert err.orphan_count == 3


def test_indexer_migration_error_is_sqlite_migration_error(tmp_path) -> None:
    from pathlib import Path
    err = IndexerMigrationError(version=2, script=tmp_path / "002.sql", cause=RuntimeError("x"))
    assert isinstance(err, SqliteMigrationError)
```

- [ ] **Step 2: Run test — expect FAIL (module missing)**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/test_core_sqlite_isinstance.py -v 2>&1 | tail -20
```

Expected: `ModuleNotFoundError: No module named 'personalscraper.core.sqlite'`

- [ ] **Step 3: Create `personalscraper/core/sqlite/errors.py`**

```python
# personalscraper/core/sqlite/errors.py
"""Minimal marker exceptions for the core SQLite layer.

These are bare base classes only — they carry NO attributes.
The attribute-bearing ``IndexerXxxError`` subclasses live in
``personalscraper.indexer.db`` and re-parent onto these markers so
``isinstance(IndexerLockError(...), SqliteLockError)`` is True.

Import direction: this module imports only stdlib (RuntimeError, ValueError,
OSError) — never from any package in personalscraper.
"""
from __future__ import annotations

__all__ = [
    "SqliteLockError",
    "SqliteCorruptError",
    "SqliteInvalidPathError",
    "SqliteDiskFullError",
    "SqliteFKOrphansError",
    "SqliteMigrationError",
]


class SqliteLockError(RuntimeError):
    """Base marker: writer lock held by another process."""


class SqliteCorruptError(RuntimeError):
    """Base marker: database file is malformed."""


class SqliteInvalidPathError(ValueError):
    """Base marker: db_path is on an unsupported filesystem."""


class SqliteDiskFullError(OSError):
    """Base marker: insufficient free disk space."""


class SqliteFKOrphansError(RuntimeError):
    """Base marker: foreign-key orphan rows detected."""


class SqliteMigrationError(RuntimeError):
    """Base marker: migration script failed."""
```

- [ ] **Step 4: Create `personalscraper/core/sqlite/__init__.py`**

```python
# personalscraper/core/sqlite/__init__.py
"""Neutral SQLite machinery shared by indexer/ and acquire/.

Event-free: no EventBus import, no event emission.
"""
from __future__ import annotations
```

- [ ] **Step 5: Re-parent IndexerXxxError in `personalscraper/indexer/db.py`**

In `personalscraper/indexer/db.py`, add the core imports at the top of the exceptions section and change each `IndexerXxxError` base class:

```python
# Add after existing stdlib imports, before the exceptions block:
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
    SqliteLockError,
    SqliteMigrationError,
)
```

Then change each exception's base class (keep ALL existing attributes and `__init__` bodies):

- `class IndexerLockError(RuntimeError):` → `class IndexerLockError(SqliteLockError):`
- `class IndexerCorruptError(RuntimeError):` → `class IndexerCorruptError(SqliteCorruptError):`
- `class IndexerInvalidPathError(ValueError):` → `class IndexerInvalidPathError(SqliteInvalidPathError):`
- `class IndexerDiskFullError(OSError):` → `class IndexerDiskFullError(SqliteDiskFullError):`
- `class IndexerFKOrphansError(RuntimeError):` → `class IndexerFKOrphansError(SqliteFKOrphansError):`
- `class IndexerMigrationError(RuntimeError):` → `class IndexerMigrationError(SqliteMigrationError):`

- [ ] **Step 6: Run isinstance regression tests — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/test_core_sqlite_isinstance.py -v 2>&1 | tail -10
```

Expected: `6 passed`

- [ ] **Step 7: Commit**

```bash
git add personalscraper/core/sqlite/__init__.py personalscraper/core/sqlite/errors.py personalscraper/indexer/db.py tests/indexer/test_core_sqlite_isinstance.py
git commit -m "refactor(acquire-store): add core/sqlite/errors.py markers + re-parent IndexerXxxError"
```

---

### Task 2 — Move `_fs_probe` to core and add re-export shim

- Plan-drift (sub-phase 1.2): re-targeted `tests/indexer/test_fs_probe.py` module references and `tests/indexer/test_db.py` patch string to `core.sqlite._fs_probe` (definition-site patch fix).

**Files:**

- Create: `personalscraper/core/sqlite/_fs_probe.py`
- Modify: `personalscraper/indexer/_fs_probe.py` (re-export shim)

- [ ] **Step 1: Create `personalscraper/core/sqlite/_fs_probe.py`**

Copy the full content of `personalscraper/indexer/_fs_probe.py` verbatim, but change the logger name from `"indexer.fs_probe"` to `"core.sqlite.fs_probe"`:

```python
# personalscraper/core/sqlite/_fs_probe.py
"""Filesystem-type probe — neutral, moved from indexer/_fs_probe.py (RP3 Phase 1).

All importers in indexer/ and conf/ continue to use
``personalscraper.indexer._fs_probe`` via the re-export shim.
"""
from __future__ import annotations
# ... (full content of indexer/_fs_probe.py with logger name changed) ...
log = get_logger("core.sqlite.fs_probe")
```

Concretely: copy `personalscraper/indexer/_fs_probe.py` to `personalscraper/core/sqlite/_fs_probe.py`, then change `get_logger("indexer.fs_probe")` to `get_logger("core.sqlite.fs_probe")`.

- [ ] **Step 2: Replace `personalscraper/indexer/_fs_probe.py` with a re-export shim**

```python
# personalscraper/indexer/_fs_probe.py
"""Re-export shim — real implementation moved to core/sqlite/_fs_probe.py (RP3).

All existing importers (conf/models/indexer.py, conf/models/disks.py,
indexer/_fs_capability.py, indexer/scanner/__init__.py,
indexer/scanner/_spotlight.py, indexer/db.py) continue to import from this
module and get the same symbols without modification.
"""
from __future__ import annotations

from personalscraper.core.sqlite._fs_probe import (  # noqa: F401
    MountInfo,
    _build_mount_table,
    _run_mount,
    canonical_fs_type,
    probe_mount,
)

__all__ = ["MountInfo", "_build_mount_table", "_run_mount", "canonical_fs_type", "probe_mount"]
```

- [ ] **Step 3: Verify existing importers still work**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "
from personalscraper.indexer._fs_probe import probe_mount, MountInfo, canonical_fs_type
from personalscraper.conf.models.indexer import IndexerConfig
print('OK: all re-exports resolve')
"
```

Expected: `OK: all re-exports resolve`

- [ ] **Step 4: Run indexer tests to confirm no breakage**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/ -x -q 2>&1 | tail -15
```

Expected: all pass (no failures).

- [ ] **Step 5: Commit**

```bash
git add personalscraper/core/sqlite/_fs_probe.py personalscraper/indexer/_fs_probe.py
git commit -m "refactor(acquire-store): move _fs_probe to core/sqlite, keep indexer shim"
```

---

### Task 3 — Move `_apply_pragmas`, `apply_migrations`, `db_lock` to core

**Files:**

- Create: `personalscraper/core/sqlite/_pragmas.py`
- Create: `personalscraper/core/sqlite/_migrate.py`
- Create: `personalscraper/core/sqlite/_lock.py`

- [ ] **Step 1: Create `personalscraper/core/sqlite/_pragmas.py`**

Extract `_apply_pragmas` from `indexer/db.py` verbatim (it has no indexer-specific imports):

```python
# personalscraper/core/sqlite/_pragmas.py
"""Canonical 8-PRAGMA set for WAL-mode SQLite connections (SSOT).

Event-free: no EventBus, no domain imports.
"""
from __future__ import annotations

import sqlite3

from personalscraper.logger import get_logger

log = get_logger("core.sqlite.pragmas")


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply the canonical 8-PRAGMA set to an open SQLite connection.

    Must be called immediately after sqlite3.connect() on every connection
    that should use WAL mode.

    Args:
        conn: An open sqlite3.Connection.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-65536")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
```

- [ ] **Step 2: Create `personalscraper/core/sqlite/_migrate.py`**

Extract `apply_migrations` from `indexer/db.py` verbatim (already `(conn, dir_)`-parameterised):

```python
# personalscraper/core/sqlite/_migrate.py
"""SQL migration applier — applies pending *.sql scripts in sorted order.

Event-free: no EventBus, no domain imports.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from personalscraper.core.sqlite.errors import SqliteMigrationError
from personalscraper.logger import get_logger

log = get_logger("core.sqlite.migrate")

def apply_migrations(
    conn: sqlite3.Connection,
    dir_: Path,
    *,
    error_factory: Callable[[int], BaseException] | None = None,
) -> None:
    """Apply pending *.sql migration scripts from dir_ in sorted order.

    Reads schema_version from PRAGMA user_version, applies every script
    whose numeric prefix is > current version, then updates user_version.

    Args:
        conn: An open sqlite3.Connection (must have foreign_keys=ON).
        dir_: Directory containing NNN_name.sql migration scripts.
        error_factory: Optional callable that builds a rich exception from
            the failed migration version.  When None, a bare
            SqliteMigrationError with a human-readable message is raised.

    Raises:
        SqliteMigrationError: If a migration script fails and no
            error_factory is supplied.
        BaseException: Whatever error_factory(version) returns, when supplied.
    """
    ...
```

- `error_factory` is keyword-only so the indexer can pass `IndexerMigrationError` →
  `isinstance(exc, IndexerMigrationError)` + `.version` works post-rewire (Task 4).
  When absent, a bare `SqliteMigrationError(f"Migration {ver} failed")` is raised.

**Concretely:** copy the body of `apply_migrations` from `personalscraper/indexer/db.py` (line 588 onward), plus private helpers `_migration_version` and `_db_path_from_conn`. Update log event strings `indexer.migration.*` → `core.sqlite.migration.*`. At the failure raise site: `error_factory(ver) if error_factory is not None else SqliteMigrationError(...)`.

- [ ] **Step 3: Create `personalscraper/core/sqlite/_lock.py`**

Extract `indexer_lock` → rename to `db_lock`, update log event strings from `indexer.lock.*` to `core.sqlite.lock.*`:

```python
# personalscraper/core/sqlite/_lock.py
"""Single-writer FileLock with PID sidecar and stale-recovery (SSOT).

Event-free: no EventBus. Logs via core.sqlite.lock.* event names.
"""
from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from personalscraper.core.sqlite.errors import SqliteLockError
from personalscraper.logger import get_logger

log = get_logger("core.sqlite.lock")


@contextmanager
def db_lock(
    path: Path,
    *,
    timeout: float = 0,
    error_factory: Callable[[int], BaseException] | None = None,
) -> Generator[None, None, None]:
    """Acquire the single-writer lock for a SQLite database file.

    Mirrors indexer_lock semantics: FileLock + JSON sidecar + stale-PID recovery.
    Logs core.sqlite.lock.stale_recovered on stale-PID cleanup.

    Args:
        path: Path of the database file (lock files derived from this).
        timeout: Seconds to wait before declaring a timeout. 0 = fail immediately.
        error_factory: Optional callable that builds a rich exception from
            the holder PID.  When None, a bare SqliteLockError with a
            human-readable message is raised.

    Yields:
        None — lock is held for the duration of the with block.

    Raises:
        SqliteLockError: If the lock is held by a live process and no
            error_factory is supplied.
        BaseException: Whatever error_factory(pid) returns, when supplied.
    """
    ...
```

- `error_factory` is keyword-only so the indexer can pass `IndexerLockError` →
  `isinstance(exc, IndexerLockError)` + `.pid` works post-rewire (Task 4).
  When absent, a bare `SqliteLockError(f"Writer lock held by PID {held_pid}")` is raised.

- [ ] **Step 4: Verify imports**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.core.sqlite._migrate import apply_migrations
from personalscraper.core.sqlite._lock import db_lock
print('OK: core/sqlite sub-modules importable')
"
```

Expected: `OK: core/sqlite sub-modules importable`

- [ ] **Step 5: Commit**

```bash
git add personalscraper/core/sqlite/_pragmas.py personalscraper/core/sqlite/_migrate.py personalscraper/core/sqlite/_lock.py
git commit -m "refactor(acquire-store): extract _pragmas, _migrate, db_lock into core/sqlite"
```

---

### Task 4 — Create event-free `core/sqlite/_open.py` and update indexer shims

**Files:**

- Create: `personalscraper/core/sqlite/_open.py`
- Modify: `personalscraper/indexer/db.py` (add shims for `apply_pragmas`, `apply_migrations`, `db_lock`)

- [ ] **Step 1: Create `personalscraper/core/sqlite/_open.py`**

`open_db` in core takes **no `event_bus` param**. It raises `SqliteDiskFullError` directly (no event emission). Copy the body of `open_db` from `indexer/db.py` and:

- Remove `event_bus: EventBus` param and the `check_free_space` call
- Replace the free-space check with a direct `SqliteDiskFullError` raise
- Replace all `Indexer*Error` raises with `Sqlite*Error` raises
- Import `_fs_probe.probe_mount` from `personalscraper.core.sqlite._fs_probe`

```python
# personalscraper/core/sqlite/_open.py
"""Event-free open_db for core SQLite connections.

No event_bus param, no EventBus import. Raises SqliteDiskFullError directly.
Used by acquire/store.py (and future core consumers). indexer/db.py wraps
this and adds the event_bus param + DiskFullWarning emission.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.core.sqlite._fs_probe import probe_mount
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
)
from personalscraper.logger import get_logger

log = get_logger("core.sqlite.open")


def open_db(
    path: Path,
    expected_growth_bytes: int = 0,
    *,
    rebuild: bool = False,
    allow_fk_orphans: bool = False,
) -> sqlite3.Connection:
    """Open (or create) a SQLite database, applying the canonical PRAGMA set.

    Event-free: raises SqliteDiskFullError directly (no DiskFullWarning event).
    indexer/db.py wraps this to add event_bus + DiskFullWarning.

    Args:
        path: Path to the SQLite database file.
        expected_growth_bytes: If > 0, check free space before opening.
        rebuild: If True, delete an existing DB before opening.
        allow_fk_orphans: If True, skip the FK orphan check.

    Returns:
        An open sqlite3.Connection with PRAGMAs applied.

    Raises:
        SqliteInvalidPathError: path is on a WAL-unsafe filesystem.
        SqliteDiskFullError: insufficient free space.
        SqliteCorruptError: database is malformed (quarantined).
        SqliteFKOrphansError: FK orphan rows found (unless allow_fk_orphans).
    """
    # (copy body of open_db from indexer/db.py, removing event_bus param
    #  and check_free_space call; replace Indexer*Error with Sqlite*Error;
    #  inline the free-space logic raising SqliteDiskFullError directly)
    ...
```

- [ ] **Step 2: Add re-export shims in `indexer/db.py` for moved symbols**

In `indexer/db.py`, import from core and re-export so that `from personalscraper.indexer.db import apply_migrations, _apply_pragmas, indexer_lock` still works. Also keep `open_db` and `check_free_space` in `indexer/db.py` wrapping the core versions with `event_bus` param (this is the required signature per `test_event_bus_required_signatures.py`).

The wrapper `open_db` in `indexer/db.py`:

```python
def open_db(
    path: Path,
    expected_growth_bytes: int = 0,
    *,
    rebuild: bool = False,
    allow_fk_orphans: bool = False,
    event_bus: EventBus,
) -> sqlite3.Connection:
    """Indexer open_db: wraps core open_db, adds DiskFullWarning event."""
    if expected_growth_bytes > 0:
        check_free_space(path, expected_growth_bytes, event_bus=event_bus)
    from personalscraper.core.sqlite._open import open_db as _core_open_db
    return _core_open_db(path, 0, rebuild=rebuild, allow_fk_orphans=allow_fk_orphans)
```

- [ ] **Step 3: Update event string in `tests/indexer/test_db.py` line 186**

Change:

```python
assert _has_structlog_event("indexer.lock.stale_recovered"), (
    f"Expected 'indexer.lock.stale_recovered' in caplog; got: ..."
)
```

To:

```python
assert _has_structlog_event("core.sqlite.lock.stale_recovered"), (
    f"Expected 'core.sqlite.lock.stale_recovered' in caplog; got: ..."
)
```

- [ ] **Step 4: Run full indexer test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/indexer/ -x -q 2>&1 | tail -20
```

Expected: all pass, 0 failures.

- [ ] **Step 5: Run residual-import check**

```bash
cd /Users/izno/dev/PersonnalScaper && rg "from personalscraper.indexer.db import" --type py tests/ personalscraper/ 2>/dev/null | head -20
```

Expected: all imports resolve (shims in place). Zero broken imports.

- [ ] **Step 6: Run architecture smoke test**

```bash
cd /Users/izno/dev/PersonnalScaper && python -c "import personalscraper" && echo "smoke OK"
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/architecture/ -x -q 2>&1 | tail -10
```

Expected: architecture tests pass.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/core/sqlite/_open.py personalscraper/indexer/db.py tests/indexer/test_db.py
git commit -m "refactor(acquire-store): core/sqlite/_open.py (event-free); indexer/db.py wrapper shim"
```

---

### Task 5 — Expose public API in `core/sqlite/__init__.py` and run make check

**Files:**

- Modify: `personalscraper/core/sqlite/__init__.py`

- [ ] **Step 1: Update `__init__.py` to re-export public symbols**

```python
# personalscraper/core/sqlite/__init__.py
"""Neutral SQLite machinery — event-free, shared by indexer/ and acquire/.

Public API:
  apply_pragmas(conn)          — canonical 8-PRAGMA set
  open_db(path, ...)           — event-free open + corruption-quarantine
  db_lock(path, *, timeout=0)  — FileLock + sidecar + stale-PID recovery
  apply_migrations(conn, dir_) — apply *.sql migration scripts
  probe_mount(path)            — filesystem-type probe
  Sqlite*Error                 — marker exception hierarchy
"""
from __future__ import annotations

from personalscraper.core.sqlite._fs_probe import MountInfo, probe_mount
from personalscraper.core.sqlite._lock import db_lock
from personalscraper.core.sqlite._migrate import apply_migrations
from personalscraper.core.sqlite._open import open_db
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
    SqliteLockError,
    SqliteMigrationError,
)

__all__ = [
    "MountInfo",
    "SqliteCorruptError",
    "SqliteDiskFullError",
    "SqliteFKOrphansError",
    "SqliteInvalidPathError",
    "SqliteLockError",
    "SqliteMigrationError",
    "apply_migrations",
    "apply_pragmas",
    "db_lock",
    "open_db",
    "probe_mount",
]
```

- [ ] **Step 2: Run full gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -30
```

Expected: lint + test + module-size all green. Look for `NNNN passed, 0 failed`.

- [ ] **Step 3: Commit**

```bash
git add personalscraper/core/sqlite/__init__.py
git commit -m "chore(acquire-store): phase 1 gate — core/sqlite extraction complete"
```
