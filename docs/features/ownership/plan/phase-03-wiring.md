# Phase 3 — Adapter + composition-root wiring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **PLAN-DRIFT NOTES (applied at implementation — deviations from the literal steps below, all documented):**
>
> 1. **Wiring moved to the TRUE composition root (`cli_helpers/_build_app_context`), NOT `acquire/_factory.py`.**
>    The literal plan (Task 3.3) built `IndexerOwnershipChecker` _inside_ `build_acquire_context` via a
>    function-body `from personalscraper.indexer.ownership import ...`. That would **break the layering guard**
>    `tests/architecture/test_layering.py::test_acquire_does_not_import_triage` — it flags ALL imports of
>    `personalscraper.indexer` under `acquire/` (function-body lazy imports included; only `TYPE_CHECKING` is
>    exempt). DESIGN §1/§6 require `acquire/` to never import `indexer/`. Resolution: `build_acquire_context`
>    gained an `ownership: OwnershipChecker | None = None` parameter; the concrete `IndexerOwnershipChecker` is
>    built by a new helper `cli_helpers._build_ownership_checker(config)` (cli_helpers is NOT layering-guarded)
>    and injected. This also keeps the existing `tests/acquire/test_factory.py` green (the bare-MagicMock-config
>    calls would have raised `TypeError` from `Path(MagicMock())` had the db_path logic lived in the factory).
> 2. **Lazy, read-only, lock-free connection inside the adapter (no boot connection at all).** The literal plan
>    opened the read connection at _build_ time in the factory. Instead, `IndexerOwnershipChecker` takes a
>    `db_path` and opens the connection **lazily on the first `owns()`** with `isolation_level=None` +
>    `PRAGMA query_only=ON` (no `BEGIN`, no writer lock, no lifetime lock at the composition root). This is a
>    strict improvement that directly honours the acquire.db lifetime-lock regression lesson (zero boot I/O).
>    Consequence: `indexer/ownership.py` is added to the `ALLOWLIST` in `scripts/check-pragma-discipline.py`
>    (justified: it MUST bypass the canonical writer PRAGMA set to stay read-only / lock-free).
> 3. **Seeding fixtures use `media_item.external_ids_json`, NOT the flat `tvdb_id` column.** Migration 005
>    dropped `media_item.tvdb_id/tmdb_id/imdb_id`; the predicate matches via
>    `json_extract(external_ids_json, '$.tvdb.series_id')`. The literal plan's `INSERT … tvdb_id …` SQL would
>    fail at insert time. Fixtures mirror `tests/indexer/test_ownership_predicate.py`. Also: `disk` rows seed
>    `mount_path` when `is_mounted=1` (CHECK constraint).
> 4. **`AcquireContext.ownership` is `field(default_factory=NullOwnershipChecker)`** (a non-`None` always-valid
>    port impl), and `close()` closes it only when it exposes a `close()` (the indexer impl does;
>    `NullOwnershipChecker` does not). Existing `tests/acquire/test_context.py` field-set + close tests updated
>    accordingly (in-scope).
> 5. **Test file locations:** adapter unit tests → `tests/indexer/test_ownership_adapter.py`; integration test
>    → `tests/integration/test_ownership_wiring.py` (drives `_build_ownership_checker` → `build_acquire_context`
>    end-to-end, plus the broken-db fail-soft case).

**Goal:** Add `IndexerOwnershipChecker` (the `OwnershipChecker` port impl) to `personalscraper/indexer/ownership.py`, wire it into the composition root (`personalscraper/acquire/_factory.py` + `personalscraper/acquire/context.py`), expose it on `AcquireContext` as a single handle, and write an integration test confirming the full wiring works end-to-end.

**Architecture:** `IndexerOwnershipChecker` holds a read-only SQLite connection and calls `is_owned`. It is **fail-soft**: any `Exception` from the DB → log + return `False`, never raises into the grab loop. The composition root (`build_acquire_context`) builds it from a dedicated read connection to `library.db` (opened with `sqlite3.connect(db_path, check_same_thread=False)` — read-only, no WAL writer lock needed). When no `library.db` is configured or the path doesn't exist, `NullOwnershipChecker` is used instead. The `acquire/` module imports ONLY `core.ownership` (the port) — never `indexer/`.

**Tech Stack:** Python 3.12, `sqlite3`, `personalscraper.core.ownership`, `personalscraper.acquire._factory`, pytest.

---

## Gate — what this phase requires

Phases 1 and 2 delivered:

- `personalscraper/core/ownership.py` (`OwnershipChecker`, `NullOwnershipChecker`)
- `personalscraper/indexer/ownership.py` (`is_owned`)

Verify both before starting:

```bash
python -c "
from personalscraper.core.ownership import NullOwnershipChecker
from personalscraper.indexer.ownership import is_owned
print('gate OK')
"
```

Expected: `gate OK`.

---

## Key files to read before editing

| File                                      | What to look for                                                                                 |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `personalscraper/acquire/context.py`      | `AcquireContext` frozen dataclass — add `ownership` field here                                   |
| `personalscraper/acquire/_factory.py`     | `build_acquire_context` — add ownership build logic here                                         |
| `personalscraper/cli_helpers/__init__.py` | `_build_app_context` — shows how `build_acquire_context` is called; no changes needed here       |
| `personalscraper/indexer/db.py`           | `open_db` signature — NOT used here; we use plain `sqlite3.connect` for the read-only connection |

---

## File map

| Action     | Path                                                                                   |
| ---------- | -------------------------------------------------------------------------------------- |
| **Modify** | `personalscraper/indexer/ownership.py` — add `IndexerOwnershipChecker` class           |
| **Modify** | `personalscraper/acquire/context.py` — add `ownership` field                           |
| **Modify** | `personalscraper/acquire/_factory.py` — build and inject the checker                   |
| **Create** | `tests/indexer/test_ownership_adapter.py` — adapter unit tests (fail-soft, isinstance) |
| **Create** | `tests/integration/test_ownership_wiring.py` — composition-root integration test       |

---

## Task 3.1 — Add `IndexerOwnershipChecker` to `indexer/ownership.py`

**Files:**

- Modify: `personalscraper/indexer/ownership.py`

- [ ] **Step 1: Write failing adapter tests first**

Create `tests/indexer/test_ownership_adapter.py`:

```python
"""Unit tests for IndexerOwnershipChecker: port conformance + fail-soft.

NON-VACUOUS discipline:
- isinstance check: IndexerOwnershipChecker satisfies OwnershipChecker Protocol
- fail-soft: a closed/broken connection → False, no raise (LOAD-BEARING)
- live file: delegates correctly to is_owned (via seeded in-memory DB)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.identity import MediaRef
from personalscraper.core.ownership import OwnershipChecker
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.ownership import IndexerOwnershipChecker

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

NOW = 1_700_000_000


def _seeded_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    # Seed one disk, path, movie item with a live file
    conn.execute("INSERT INTO disk(uuid, label, is_mounted) VALUES ('u1','D1',1)")
    conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1,'movies/test')")
    conn.execute(
        "INSERT INTO media_item(kind,title,title_sort,year,category_id,tvdb_id,date_created,date_modified)"
        " VALUES ('movie','Test','Test',2020,'movies',9001,?,?)",
        (NOW, NOW),
    )
    conn.execute("INSERT INTO media_release(item_id) VALUES (1)")
    conn.execute(
        "INSERT INTO media_file(release_id,path_id,filename,size_bytes,mtime_ns,oshash,scan_generation,last_verified_at)"
        " VALUES (1,1,'t.mkv',1000000000,?,?,1,?)",
        (NOW * 10**9, "abcd1234abcd1234", NOW),
    )
    return conn


def test_implements_protocol() -> None:
    """IndexerOwnershipChecker satisfies the OwnershipChecker runtime-checkable Protocol."""
    conn = _seeded_conn()
    checker = IndexerOwnershipChecker(conn)
    assert isinstance(checker, OwnershipChecker)


def test_owns_live_movie_returns_true() -> None:
    """owns() returns True when a live file exists for the matched tvdb_id."""
    conn = _seeded_conn()
    checker = IndexerOwnershipChecker(conn)
    ref = MediaRef(tvdb_id=9001)
    assert checker.owns(ref, kind="movie") is True


def test_owns_unknown_movie_returns_false() -> None:
    """owns() returns False when no item matches the given tvdb_id."""
    conn = _seeded_conn()
    checker = IndexerOwnershipChecker(conn)
    ref = MediaRef(tvdb_id=9999)
    assert checker.owns(ref, kind="movie") is False


def test_fail_soft_broken_connection_returns_false() -> None:
    """LOAD-BEARING: a closed/broken DB connection → False, no exception raised.

    This proves the fail-soft contract: the grab loop must never crash because
    the ownership check threw.
    """
    conn = _seeded_conn()
    conn.close()  # break the connection
    checker = IndexerOwnershipChecker(conn)
    ref = MediaRef(tvdb_id=9001)
    # Must not raise — must return False silently
    result = checker.owns(ref, kind="movie")
    assert result is False


def test_fail_soft_does_not_raise_on_any_exception() -> None:
    """LOAD-BEARING: any Exception from is_owned → False, never propagates."""
    conn = _seeded_conn()
    checker = IndexerOwnershipChecker(conn)
    ref = MediaRef(tvdb_id=9001)

    with patch("personalscraper.indexer.ownership.is_owned", side_effect=RuntimeError("boom")):
        result = checker.owns(ref, kind="movie")

    assert result is False
```

- [ ] **Step 2: Run adapter tests — must FAIL (class does not exist yet)**

```bash
pytest tests/indexer/test_ownership_adapter.py -v --tb=short
```

Expected: `ImportError` — `IndexerOwnershipChecker` not yet defined.

- [ ] **Step 3: Add `IndexerOwnershipChecker` to `personalscraper/indexer/ownership.py`**

Append after the existing `is_owned` and helpers. Read the file first to find the correct insertion point (after `__all__ = ["is_owned"]`). Replace the `__all__` line and add the import + class.

Add this import at the TOP of the file alongside the existing imports (NOT inside the class):

```python
from typing import Literal
from personalscraper.core.identity import MediaRef
```

(`Literal` and `sqlite3` are already imported at the top of the file — only add `MediaRef` if not already there. Do NOT import `OwnershipChecker` at runtime — it is `@runtime_checkable` so `isinstance` works without an explicit import in this module; importing it would create an unused-import lint error since it's never referenced at runtime in the adapter body.)

Then append the class:

```python
class IndexerOwnershipChecker:
    """Port implementation of :class:`~personalscraper.core.ownership.OwnershipChecker`.

    Wraps :func:`is_owned` with a held read-only SQLite connection.
    Fail-soft: any Exception from the DB or predicate → log + return False.
    This adapter lives in ``indexer/`` because it imports ``sqlite3`` +
    ``is_owned``; ``acquire/`` imports only the ``core.ownership`` port.

    Import direction: imports ``core.ownership`` (port) + ``core.identity``
    only. Does NOT import ``acquire/`` — allowed downward direction.

    Attributes:
        _conn: Read-only SQLite connection to the indexer database.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise with a read-only SQLite connection.

        Args:
            conn: Open ``sqlite3.Connection`` to library.db. The caller owns
                the connection lifetime; ``IndexerOwnershipChecker`` never
                closes it.
        """
        self._conn = conn

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Return True iff the library contains a live file for this work.

        Delegates to :func:`is_owned`. Any exception from the DB is caught
        and logged; ``False`` is returned instead of propagating (fail-soft).

        Args:
            media_ref: Provider IDs (tvdb primary, tmdb fallback, imdb last).
            kind: ``"movie"`` or ``"episode"``.
            season: Season number; required when ``kind="episode"``.
            episode: Episode number; required when ``kind="episode"``.

        Returns:
            ``True`` if ownership is confirmed; ``False`` on any error or
            when the work is not found / all files are soft-deleted.
        """
        try:
            return is_owned(
                self._conn,
                kind=kind,
                tvdb_id=media_ref.tvdb_id,
                tmdb_id=media_ref.tmdb_id,
                imdb_id=media_ref.imdb_id,
                season=season,
                episode=episode,
            )
        except Exception:
            log.warning(
                "indexer.ownership.fail_soft",
                kind=kind,
                tvdb_id=media_ref.tvdb_id,
                tmdb_id=media_ref.tmdb_id,
            )
            return False


__all__ = ["IndexerOwnershipChecker", "is_owned"]
```

- [ ] **Step 4: Run adapter tests — must PASS**

```bash
pytest tests/indexer/test_ownership_adapter.py -v --tb=short
```

Expected: `5 passed`.

- [ ] **Step 5: Run the predicate tests still pass**

```bash
pytest tests/indexer/test_ownership_predicate.py tests/indexer/test_ownership_adapter.py -v --tb=short -q
```

Expected: all pass, 0 failures.

- [ ] **Step 6: Commit the adapter**

```bash
git add personalscraper/indexer/ownership.py tests/indexer/test_ownership_adapter.py
git commit -m "feat(ownership): indexer adapter — IndexerOwnershipChecker with fail-soft"
```

---

## Task 3.2 — Add `ownership` field to `AcquireContext`

**Files:**

- Modify: `personalscraper/acquire/context.py`

Read the file before editing. `AcquireContext` is a `@dataclass(frozen=True)`. Add `ownership` as an optional field with default `None`. Use `TYPE_CHECKING` for the import to avoid a circular import — exactly like the existing fields.

- [ ] **Step 7: Add the field**

In `personalscraper/acquire/context.py`:

1. Under `if TYPE_CHECKING:`, add:

   ```python
   from personalscraper.core.ownership import OwnershipChecker
   ```

2. In the `AcquireContext` dataclass, add after the `grab` field:

   ```python
   ownership: "OwnershipChecker | None" = None
   ```

3. Update the class docstring `Attributes:` section to document `ownership`:

   ```
   ownership: ``OwnershipChecker`` implementation or ``None``. Answered
       by ``IndexerOwnershipChecker`` when ``library.db`` is available;
       falls back to ``NullOwnershipChecker`` (always False) when no DB
       is wired. The ``close()`` method does NOT touch this handle — it
       holds a borrowed read connection (owned by the factory).
   ```

4. Verify `close()` does NOT need updating — it only closes `tracker_registry` and `store`. The read connection for ownership is opened by the factory and does not need an explicit close (SQLite read connections are closed when GC'd; the factory can close it explicitly if needed — keep it simple for now: no close in AcquireContext).

- [ ] **Step 8: Smoke check AcquireContext still imports cleanly**

```bash
python -c "from personalscraper.acquire.context import AcquireContext; print('OK')"
```

Expected: `OK`.

---

## Task 3.3 — Wire into `build_acquire_context`

**Files:**

- Modify: `personalscraper/acquire/_factory.py`

Read the file before editing. The factory builds the context from `config` + `settings`. Add the ownership build logic after the existing `delete_authority` block.

- [ ] **Step 9: Add ownership wiring to `build_acquire_context`**

In `personalscraper/acquire/_factory.py`:

1. Add at the top of the function (lazy imports block), inside `build_acquire_context`:

   ```python
   # RP6: build ownership checker from library.db read connection.
   # NullOwnershipChecker when no db_path is configured or file absent.
   from personalscraper.core.ownership import NullOwnershipChecker  # noqa: PLC0415
   ```

2. After the `delete_authority = build_delete_authority(...)` call, add:

   ```python
   # RP6: ownership checker — SELECT-only read connection to library.db.
   # NullOwnershipChecker (fail-open) when no indexer db_path is configured
   # or the file does not yet exist (first-run, dry-run, or test stub).
   ownership: "OwnershipChecker | NullOwnershipChecker"
   db_path = getattr(getattr(config, "indexer", None), "db_path", None)
   if db_path is not None and Path(db_path).exists():
       import sqlite3 as _sqlite3  # noqa: PLC0415
       from personalscraper.indexer.ownership import IndexerOwnershipChecker  # noqa: PLC0415
       _read_conn = _sqlite3.connect(str(db_path), check_same_thread=False)
       _read_conn.execute("PRAGMA query_only=ON")
       ownership = IndexerOwnershipChecker(_read_conn)
   else:
       ownership = NullOwnershipChecker()
   ```

3. Pass `ownership` to the `AcquireContext` constructor:

   ```python
   return AcquireContext(
       tracker_registry=tracker_registry,
       store=store,
       delete_authority=delete_authority,
       torrent_client=torrent_client,
       grab=grab,
       ownership=ownership,
   )
   ```

4. Add `from pathlib import Path` to the top-level imports if not already present (check the file — it may already import `Path`).

5. Add the `OwnershipChecker` type hint to the `TYPE_CHECKING` block:
   ```python
   if TYPE_CHECKING:
       ...
       from personalscraper.core.ownership import OwnershipChecker
   ```

- [ ] **Step 10: Smoke import the factory**

```bash
python -c "from personalscraper.acquire._factory import build_acquire_context; print('OK')"
```

Expected: `OK`.

- [ ] **Step 11: Commit the wiring**

```bash
git add personalscraper/acquire/context.py personalscraper/acquire/_factory.py
git commit -m "feat(ownership): composition-root wiring — ownership handle on AcquireContext"
```

---

## Task 3.4 — Integration test: full wiring end-to-end

**Files:**

- Create: `tests/integration/test_ownership_wiring.py`

This test builds a real `AcquireContext` via `build_acquire_context` with a seeded `library.db` file on disk, and verifies that `ctx.ownership.owns(...)` returns the expected booleans.

- [ ] **Step 12: Write the integration test**

```python
"""Integration test: ownership wiring through build_acquire_context.

Verifies that build_acquire_context correctly wires IndexerOwnershipChecker
when a library.db exists, and NullOwnershipChecker when it does not.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.core.identity import MediaRef
from personalscraper.core.ownership import NullOwnershipChecker, OwnershipChecker
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.ownership import IndexerOwnershipChecker

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"
NOW = int(time.time())


def _seed_library_db(db_path: Path) -> None:
    """Create a library.db at db_path and seed one owned movie."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    conn.execute("INSERT INTO disk(uuid,label,is_mounted) VALUES ('u1','D1',1)")
    conn.execute("INSERT INTO path(disk_id,rel_path) VALUES (1,'movies/owned')")
    conn.execute(
        "INSERT INTO media_item(kind,title,title_sort,year,category_id,tvdb_id,date_created,date_modified)"
        " VALUES ('movie','Owned Movie','Owned Movie',2020,'movies',1001,?,?)",
        (NOW, NOW),
    )
    conn.execute("INSERT INTO media_release(item_id) VALUES (1)")
    conn.execute(
        "INSERT INTO media_file(release_id,path_id,filename,size_bytes,mtime_ns,"
        "oshash,scan_generation,last_verified_at) VALUES (1,1,'owned.mkv',1000000,?,?,1,?)",
        (NOW * 10**9, "abcd1234abcd1234", NOW),
    )
    conn.commit()
    conn.close()


def _fake_config(db_path: Path) -> MagicMock:
    """Return a minimal Config stub with indexer.db_path set."""
    cfg = MagicMock()
    cfg.indexer.db_path = db_path
    cfg.acquire = MagicMock()
    cfg.tracker.providers = {}
    cfg.ranking = MagicMock()
    cfg.torrent = MagicMock()
    cfg.torrent.active = ""
    return cfg


def _fake_settings() -> MagicMock:
    return MagicMock()


def test_ownership_wired_with_library_db(tmp_path: Path) -> None:
    """build_acquire_context wires IndexerOwnershipChecker when library.db exists."""
    from personalscraper.acquire._factory import build_acquire_context
    from personalscraper.core.event_bus import EventBus
    from personalscraper.api.transport._policy import CircuitPolicy

    db_path = tmp_path / "library.db"
    _seed_library_db(db_path)

    cfg = _fake_config(db_path)
    settings = _fake_settings()
    event_bus = EventBus()
    cb_policy = CircuitPolicy(failure_threshold=3, cooldown_seconds=30)

    ctx = build_acquire_context(cfg, settings, event_bus=event_bus, cb_policy=cb_policy)

    assert ctx.ownership is not None
    assert isinstance(ctx.ownership, IndexerOwnershipChecker)
    assert isinstance(ctx.ownership, OwnershipChecker)

    # Owned movie → True
    ref_owned = MediaRef(tvdb_id=1001)
    assert ctx.ownership.owns(ref_owned, kind="movie") is True

    # Unknown movie → False
    ref_unknown = MediaRef(tvdb_id=9999)
    assert ctx.ownership.owns(ref_unknown, kind="movie") is False

    ctx.close()


def test_ownership_null_when_no_library_db(tmp_path: Path) -> None:
    """build_acquire_context uses NullOwnershipChecker when db_path does not exist."""
    from personalscraper.acquire._factory import build_acquire_context
    from personalscraper.core.event_bus import EventBus
    from personalscraper.api.transport._policy import CircuitPolicy

    db_path = tmp_path / "nonexistent_library.db"
    # Do NOT create the file

    cfg = _fake_config(db_path)
    settings = _fake_settings()
    event_bus = EventBus()
    cb_policy = CircuitPolicy(failure_threshold=3, cooldown_seconds=30)

    ctx = build_acquire_context(cfg, settings, event_bus=event_bus, cb_policy=cb_policy)

    assert ctx.ownership is not None
    assert isinstance(ctx.ownership, NullOwnershipChecker)
    ref = MediaRef(tvdb_id=1001)
    assert ctx.ownership.owns(ref, kind="movie") is False

    ctx.close()
```

- [ ] **Step 13: Run the integration test**

```bash
pytest tests/integration/test_ownership_wiring.py -v --tb=short
```

Expected: `2 passed`.

- [ ] **Step 14: Run the acquire/ layering guard — must still pass**

```bash
pytest tests/architecture/test_layering.py::test_acquire_does_not_import_triage -v --tb=short
```

Expected: `1 passed` — confirms `acquire/` still does NOT import `indexer/` directly (ownership crosses only via the core port).

- [ ] **Step 15: Commit the integration test**

```bash
git add tests/integration/test_ownership_wiring.py
git commit -m "test(ownership): integration test — full composition-root wiring"
```
