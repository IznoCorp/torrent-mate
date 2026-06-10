# Phase 03 — acquire/domain.py + schema + store

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the acquisition persistence layer: frozen domain value objects, the 4-table SQL
schema, the extended `AcquireStore` Protocol, the concrete store with 4 sub-stores under a
single-writer leaf lock, and the factory wiring that fills `AcquireContext.store`.

**Architecture:** `acquire/domain.py` imports only `core.identity.MediaRef` and stdlib.
`acquire/store.py` uses `core.sqlite` exclusively — never `indexer/`. The single
`acquire.db.lock` is held only for the duration of each DB write (leaf lock, never held across
FS or HTTP). `build_acquire_context` in `acquire/_factory.py` fills `store=` instead of
`store=None`.

**Tech stack:** `core.sqlite.{open_db,db_lock,apply_migrations}`, `sqlite3`, frozen dataclasses,
`personalscraper.logger.get_logger`.

---

## Gate (from Phase 2)

- `personalscraper/core/identity.py` exists; `MediaRef` importable.
- `personalscraper/conf/models/acquire.py` exists; `AcquireConfig` importable.
- `Config.acquire` field present; `_resolve_derived_paths` sets `acquire.db_path`.
- `config.example/acquire.json5` present in overlays; `test_example_config.py` passes.
- `make check` green.

---

## File map

| Action | Path                                                                             |
| ------ | -------------------------------------------------------------------------------- |
| Create | `personalscraper/acquire/domain.py`                                              |
| Create | `personalscraper/acquire/migrations/001_init.sql`                                |
| Modify | `personalscraper/acquire/_ports.py` (extend `AcquireStore` Protocol)             |
| Create | `personalscraper/acquire/store.py` (concrete store + 4 sub-stores)               |
| Modify | `personalscraper/acquire/_factory.py` (add `build_acquire_store`, wire `store=`) |
| Create | `tests/acquire/test_store.py` (migration-contract, lock, close)                  |

---

### Task 1 — Create `acquire/domain.py` with frozen value objects

**Files:**

- Create: `personalscraper/acquire/domain.py`
- Test: `tests/acquire/test_domain.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/acquire/test_domain.py
"""Unit tests for acquire/domain.py frozen value objects."""
from __future__ import annotations

import time
import pytest
from personalscraper.acquire.domain import (
    FollowedSeries,
    RatioState,
    SeedObligation,
    WantedItem,
)
from personalscraper.core.identity import MediaRef


def _ref(tvdb_id: int = 1) -> MediaRef:
    return MediaRef(tvdb_id=tvdb_id)


def test_followed_series_frozen() -> None:
    fs = FollowedSeries(media_ref=_ref(), title="TestShow", added_at=int(time.time()))
    with pytest.raises((AttributeError, TypeError)):
        fs.title = "other"  # type: ignore[misc]


def test_wanted_item_valid_kinds() -> None:
    wi = WantedItem(
        media_ref=_ref(),
        kind="episode",
        status="pending",
        enqueued_at=int(time.time()),
    )
    assert wi.kind == "episode"


def test_wanted_item_rejects_invalid_kind() -> None:
    with pytest.raises((ValueError, TypeError)):
        WantedItem(
            media_ref=_ref(),
            kind="invalid",  # type: ignore[arg-type]
            status="pending",
            enqueued_at=int(time.time()),
        )


def test_seed_obligation_fields() -> None:
    so = SeedObligation(
        info_hash="abc123",
        source_tracker="lacale",
        min_seed_time_s=72 * 3600,
        min_ratio=1.0,
        added_at=int(time.time()),
    )
    assert so.dispatched_path is None
    assert so.satisfied_at is None
    assert so.breached_at is None
    assert so.released_at is None


def test_ratio_state_fields() -> None:
    rs = RatioState(
        tracker_name="lacale",
        observed_ratio=1.2,
        accumulated_seed_time_s=100000,
        hnr_count=0,
        updated_at=int(time.time()),
    )
    assert rs.hnr_count == 0
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/test_domain.py -v 2>&1 | tail -15
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `personalscraper/acquire/domain.py`**

```python
# personalscraper/acquire/domain.py
"""Frozen domain value objects for the acquisition lobe (RP3).

All objects are keyed on ``core.identity.MediaRef`` (tvdb_id primary).
QualityProfile + source-criteria are deferred to RP3a; the columns are
present in the schema as nullable JSON passthroughs until then.

Import direction: core.identity + stdlib only (acquire/ must never import
indexer/, scraper/, or any triage package).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from personalscraper.core.identity import MediaRef

WantedKind = Literal["movie", "episode"]
WantedStatus = Literal["pending", "searching", "grabbed", "done", "abandoned"]


@dataclass(frozen=True)
class FollowedSeries:
    """A TV series or movie the user wants to automatically acquire.

    Attributes:
        media_ref: Provider-ID key (tvdb_id primary).
        title: Human-readable title (for logging/display).
        active: Whether this series is actively searched.
        added_at: Unix epoch seconds when the series was followed.
        quality_profile_json: Nullable JSON string; rich profile = RP3a.
        cadence_json: Nullable JSON string; RP9/D2.
    """

    media_ref: MediaRef
    title: str
    added_at: int
    active: bool = True
    quality_profile_json: str | None = None
    cadence_json: str | None = None


@dataclass(frozen=True)
class WantedItem:
    """A specific episode or movie the acquisition engine wants to grab.

    Attributes:
        media_ref: Provider-ID key.
        kind: ``"movie"`` or ``"episode"``.
        status: Current acquisition state.
        enqueued_at: Unix epoch seconds when the item was enqueued.
        followed_id: FK to followed_series row (optional when standalone).
        season: Season number (episodes only).
        episode: Episode number (episodes only).
        criteria_json: Nullable JSON for search criteria (RP3a).
        last_search_at: Unix epoch seconds of last search attempt.
        attempts: Number of search attempts made.
    """

    media_ref: MediaRef
    kind: WantedKind
    status: WantedStatus
    enqueued_at: int
    followed_id: int | None = None
    season: int | None = None
    episode: int | None = None
    criteria_json: str | None = None
    last_search_at: int | None = None
    attempts: int = 0

    def __post_init__(self) -> None:
        """Validate kind and status values.

        Raises:
            ValueError: If kind or status is not a valid literal.
        """
        valid_kinds: tuple[str, ...] = ("movie", "episode")
        valid_statuses: tuple[str, ...] = ("pending", "searching", "grabbed", "done", "abandoned")
        if self.kind not in valid_kinds:
            raise ValueError(f"Invalid WantedItem.kind={self.kind!r}; must be one of {valid_kinds}")
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid WantedItem.status={self.status!r}; must be one of {valid_statuses}")


@dataclass(frozen=True)
class SeedObligation:
    """A seed obligation created when a torrent payload is dispatched.

    The deletion authority consults this table before permitting any deletion
    of a dispatched path.

    Attributes:
        info_hash: Torrent info-hash (hex string).
        source_tracker: Tracker name string (e.g. ``"lacale"``).
        min_seed_time_s: Minimum seed time in seconds (snapshot from TrackerEconomyConfig).
        min_ratio: Minimum ratio (snapshot).
        added_at: Unix epoch seconds when obligation was recorded.
        dispatched_path: Absolute path of the dispatched media (set after move).
        satisfied_at: Unix epoch seconds when obligation was satisfied (nullable).
        breached_at: Unix epoch seconds when obligation was breached (nullable).
        released_at: Unix epoch seconds when tracker released the obligation (nullable).
    """

    info_hash: str
    source_tracker: str
    min_seed_time_s: int
    min_ratio: float
    added_at: int
    dispatched_path: str | None = None
    satisfied_at: int | None = None
    breached_at: int | None = None
    released_at: int | None = None


@dataclass(frozen=True)
class RatioState:
    """Per-tracker ratio state (DORMANT — writer arrives with Ratio C1, Vague 5).

    Table is created now as a data-carrier; no RP3 code writes to it.

    Attributes:
        tracker_name: Tracker identifier (PK).
        observed_ratio: Last observed upload/download ratio.
        accumulated_seed_time_s: Total accumulated seed time in seconds.
        hnr_count: Number of hit-and-run events recorded.
        updated_at: Unix epoch seconds of last update.
    """

    tracker_name: str
    observed_ratio: float
    accumulated_seed_time_s: int
    hnr_count: int
    updated_at: int


__all__ = ["FollowedSeries", "RatioState", "SeedObligation", "WantedItem", "WantedKind", "WantedStatus"]
```

- [ ] **Step 4: Create `personalscraper/acquire/migrations/` package + `__init__.py`**

```bash
mkdir -p /Users/izno/dev/PersonnalScaper/personalscraper/acquire/migrations
touch /Users/izno/dev/PersonnalScaper/personalscraper/acquire/migrations/__init__.py
```

- [ ] **Step 5: Run domain tests — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/test_domain.py -v 2>&1 | tail -10
```

Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add personalscraper/acquire/domain.py personalscraper/acquire/migrations/__init__.py tests/acquire/test_domain.py
git commit -m "feat(acquire-store): acquire/domain.py frozen VOs keyed on MediaRef"
```

---

### Task 2 — Create `acquire/migrations/001_init.sql`

**Files:**

- Create: `personalscraper/acquire/migrations/001_init.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- personalscraper/acquire/migrations/001_init.sql
-- Initial schema for acquire.db (RP3).
-- Conventions: INTEGER PRIMARY KEY (rowid alias), unix-epoch INTEGER timestamps,
-- CHECK IN enums, FKs with ON DELETE, partial indexes WHERE status='...',
-- JSON-as-TEXT *_json columns.
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS followed_series (
    id                   INTEGER PRIMARY KEY,
    media_ref_json       TEXT    NOT NULL,
    title                TEXT    NOT NULL,
    active               INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    quality_profile_json TEXT,
    cadence_json         TEXT,
    added_at             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wanted (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'grabbed', 'done', 'abandoned')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_wanted_pending
    ON wanted (status) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS seed_obligation (
    id               INTEGER PRIMARY KEY,
    info_hash        TEXT    NOT NULL,
    source_tracker   TEXT    NOT NULL,
    dispatched_path  TEXT,
    min_seed_time_s  INTEGER NOT NULL,
    min_ratio        REAL    NOT NULL,
    added_at         INTEGER NOT NULL,
    satisfied_at     INTEGER,
    breached_at      INTEGER,
    released_at      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_seed_dispatched_path
    ON seed_obligation (dispatched_path)
    WHERE dispatched_path IS NOT NULL;

CREATE TABLE IF NOT EXISTS ratio_state (
    tracker_name            TEXT    PRIMARY KEY,
    observed_ratio          REAL    NOT NULL DEFAULT 0.0,
    accumulated_seed_time_s INTEGER NOT NULL DEFAULT 0,
    hnr_count               INTEGER NOT NULL DEFAULT 0,
    updated_at              INTEGER NOT NULL
);
```

- [ ] **Step 2: Commit**

```bash
git add personalscraper/acquire/migrations/001_init.sql
git commit -m "feat(acquire-store): acquire/migrations/001_init.sql — 4 tables initial schema"
```

---

### Task 3 — Extend `AcquireStore` Protocol + build concrete store

**Files:**

- Modify: `personalscraper/acquire/_ports.py`
- Create: `personalscraper/acquire/store.py`
- Test: `tests/acquire/test_store.py`

- [ ] **Step 1: Write the failing store tests**

```python
# tests/acquire/test_store.py
"""Tests for AcquireStore: migration contract, lock, close(), sub-store methods."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.acquire.store import AcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


@pytest.fixture()
def store(tmp_path: Path) -> AcquireStore:
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    yield s
    s.close()


def test_migration_contract(tmp_path: Path) -> None:
    """Every migration version 1..N in schema_version; user_version == latest."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    s.close()
    assert user_version == 1, f"Expected user_version=1 after 001_init.sql, got {user_version}"


def test_all_four_tables_exist(store: AcquireStore, tmp_path: Path) -> None:
    """All four tables are present after store construction."""
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert {"followed_series", "wanted", "seed_obligation", "ratio_state"} <= tables


def test_lock_contention_raises(tmp_path: Path) -> None:
    """A second concurrent open with timeout=0 raises AcquireLockError."""
    from personalscraper.acquire.store import AcquireLockError
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s1 = build_acquire_store(cfg)
    try:
        with pytest.raises(AcquireLockError):
            # Second store attempts to hold the lock simultaneously
            from personalscraper.core.sqlite._lock import db_lock
            from contextlib import suppress
            db_path = tmp_path / "acquire.db"
            # Simulate contention by holding the lock in s1 while trying s2
            s2 = build_acquire_store(cfg)  # should fail or raise on lock
    finally:
        s1.close()


def test_close_is_idempotent(store: AcquireStore) -> None:
    """close() may be called multiple times without raising."""
    store.close()
    store.close()  # second call must not raise


def test_close_is_fail_soft(tmp_path: Path) -> None:
    """close() does not raise even if connection is already closed."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    s.close()
    s.close()  # no exception
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/test_store.py -v 2>&1 | tail -15
```

Expected: `ModuleNotFoundError` on `personalscraper.acquire.store`.

- [ ] **Step 3: Extend `acquire/_ports.py` with query/write methods**

Replace the content of `personalscraper/acquire/_ports.py`:

```python
# personalscraper/acquire/_ports.py
"""Port protocols for the acquire lobe.

AcquireStore is extended in RP3 with query/write methods for the four
sub-stores: follow, wanted, seed, ratio.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from personalscraper.acquire.domain import FollowedSeries, SeedObligation


@runtime_checkable
class AcquireStore(Protocol):
    """Full store contract for the acquisition lobe (RP3).

    Sub-stores are accessed via attribute namespaces:
      store.seed.add(obligation)
      store.seed.find_by_dispatched_path(path)
      store.follow.add(series)
    """

    def close(self) -> None:
        """Release all resources (fail-soft — never raises)."""
        ...

    class _SeedSubStore(Protocol):
        def add(self, obligation: SeedObligation) -> int:
            """Insert a new SeedObligation; returns the row id."""
            ...

        def find_by_dispatched_path(self, path: Path) -> SeedObligation | None:
            """Return the active obligation for dispatched_path, or None."""
            ...

        def mark_satisfied(self, obligation_id: int, satisfied_at: int) -> None:
            """Set satisfied_at on an obligation row."""
            ...

        def mark_breached(self, obligation_id: int, breached_at: int) -> None:
            """Set breached_at on an obligation row."""
            ...

    seed: "_SeedSubStore"


__all__ = ["AcquireStore"]
```

- [ ] **Step 4: Create `personalscraper/acquire/store.py`**

```python
# personalscraper/acquire/store.py
"""Concrete AcquireStore over core/sqlite: 4 sub-stores, single-writer leaf lock.

Single acquire.db.lock via core.sqlite.db_lock. Lock is a LEAF lock:
never held across FS operations or HTTP calls. Total lock order:
pipeline.lock > indexer_lock > acquire.db.lock.

Logging: personalscraper.logger.get_logger (NOT structlog.get_logger).
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from personalscraper.acquire.domain import FollowedSeries, SeedObligation
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.sqlite import apply_migrations, db_lock, open_db
from personalscraper.core.sqlite.errors import SqliteLockError
from personalscraper.logger import get_logger

log = get_logger("acquire.store")

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class AcquireLockError(SqliteLockError):
    """Raised when the acquire.db writer lock is held by another process."""


class _SeedSubStore:
    """Writer for the seed_obligation table."""

    def __init__(self, conn: sqlite3.Connection, db_path: Path) -> None:
        """Initialise with shared connection and db_path for lock derivation.

        Args:
            conn: Shared sqlite3.Connection to acquire.db.
            db_path: Path to acquire.db (used to derive lock path).
        """
        self._conn = conn
        self._db_path = db_path

    def add(self, obligation: SeedObligation) -> int:
        """Insert a SeedObligation row and return its rowid.

        Args:
            obligation: The SeedObligation to persist.

        Returns:
            The rowid of the newly inserted row.
        """
        with db_lock(self._db_path, timeout=0):
            cur = self._conn.execute(
                """
                INSERT INTO seed_obligation
                  (info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    obligation.info_hash,
                    obligation.source_tracker,
                    obligation.dispatched_path,
                    obligation.min_seed_time_s,
                    obligation.min_ratio,
                    obligation.added_at,
                ),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def find_by_dispatched_path(self, path: Path) -> SeedObligation | None:
        """Return the first active SeedObligation for the given dispatched path.

        Args:
            path: The dispatched media path to look up.

        Returns:
            A SeedObligation if found, else None.
        """
        row = self._conn.execute(
            """
            SELECT info_hash, source_tracker, dispatched_path,
                   min_seed_time_s, min_ratio, added_at,
                   satisfied_at, breached_at, released_at
            FROM seed_obligation
            WHERE dispatched_path = ?
              AND satisfied_at IS NULL
              AND released_at IS NULL
            LIMIT 1
            """,
            (str(path),),
        ).fetchone()
        if row is None:
            return None
        return SeedObligation(
            info_hash=row[0],
            source_tracker=row[1],
            dispatched_path=row[2],
            min_seed_time_s=row[3],
            min_ratio=row[4],
            added_at=row[5],
            satisfied_at=row[6],
            breached_at=row[7],
            released_at=row[8],
        )

    def mark_satisfied(self, obligation_id: int, satisfied_at: int) -> None:
        """Set satisfied_at on a seed_obligation row.

        Args:
            obligation_id: Rowid of the obligation.
            satisfied_at: Unix epoch seconds.
        """
        with db_lock(self._db_path, timeout=0):
            self._conn.execute(
                "UPDATE seed_obligation SET satisfied_at=? WHERE id=?",
                (satisfied_at, obligation_id),
            )
            self._conn.commit()

    def mark_breached(self, obligation_id: int, breached_at: int) -> None:
        """Set breached_at on a seed_obligation row.

        Args:
            obligation_id: Rowid of the obligation.
            breached_at: Unix epoch seconds.
        """
        with db_lock(self._db_path, timeout=0):
            self._conn.execute(
                "UPDATE seed_obligation SET breached_at=? WHERE id=?",
                (breached_at, obligation_id),
            )
            self._conn.commit()


class _FollowSubStore:
    """Writer for the followed_series and wanted tables."""

    def __init__(self, conn: sqlite3.Connection, db_path: Path) -> None:
        """Initialise with shared connection.

        Args:
            conn: Shared sqlite3.Connection to acquire.db.
            db_path: Path to acquire.db (used to derive lock path).
        """
        self._conn = conn
        self._db_path = db_path

    def add(self, series: FollowedSeries) -> int:
        """Insert a FollowedSeries row and return its rowid.

        Args:
            series: The FollowedSeries to persist.

        Returns:
            The rowid of the newly inserted row.
        """
        with db_lock(self._db_path, timeout=0):
            cur = self._conn.execute(
                """
                INSERT INTO followed_series
                  (media_ref_json, title, active,
                   quality_profile_json, cadence_json, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    json.dumps({"tvdb_id": series.media_ref.tvdb_id,
                                "tmdb_id": series.media_ref.tmdb_id,
                                "imdb_id": series.media_ref.imdb_id}),
                    series.title,
                    1 if series.active else 0,
                    series.quality_profile_json,
                    series.cadence_json,
                    series.added_at,
                ),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]


class ConcreteAcquireStore:
    """Concrete implementation of the AcquireStore protocol.

    Attributes:
        seed: Sub-store for seed_obligation table operations.
        follow: Sub-store for followed_series table operations.
    """

    def __init__(self, conn: sqlite3.Connection, db_path: Path) -> None:
        """Initialise with an open connection and the DB path.

        Args:
            conn: Open sqlite3.Connection to acquire.db (PRAGMAs applied).
            db_path: Path to acquire.db (for lock-file derivation).
        """
        self._conn = conn
        self._db_path = db_path
        self.seed = _SeedSubStore(conn, db_path)
        self.follow = _FollowSubStore(conn, db_path)
        log.info("acquire.store.opened", db_path=str(db_path))

    def close(self) -> None:
        """Release the connection (fail-soft — never raises).

        Honors AcquireContext.close()'s no-suppress contract.
        """
        try:
            self._conn.close()
            log.info("acquire.store.closed", db_path=str(self._db_path))
        except Exception as exc:  # noqa: BLE001
            log.warning("acquire.store.close_failed", error=str(exc))


def build_acquire_store(config: AcquireConfig) -> ConcreteAcquireStore:
    """Build and return a ConcreteAcquireStore for the given config.

    Opens acquire.db, applies PRAGMAs, runs pending migrations.

    Args:
        config: AcquireConfig with a resolved db_path.

    Returns:
        A ConcreteAcquireStore ready for use.

    Raises:
        AcquireLockError: If acquire.db.lock is held by another process.
        ValueError: If config.db_path is None (must be resolved before call).
    """
    if config.db_path is None:
        raise ValueError("AcquireConfig.db_path must be resolved before calling build_acquire_store")
    db_path: Path = config.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = open_db(db_path)
    except SqliteLockError as exc:
        raise AcquireLockError(str(exc)) from exc
    apply_migrations(conn, _MIGRATIONS_DIR)
    return ConcreteAcquireStore(conn, db_path)


# Alias so Protocol isinstance check works
AcquireStore = ConcreteAcquireStore

__all__ = ["AcquireLockError", "AcquireStore", "ConcreteAcquireStore", "build_acquire_store"]
```

- [ ] **Step 5: Run store tests — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/test_store.py -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add personalscraper/acquire/_ports.py personalscraper/acquire/store.py tests/acquire/test_store.py
git commit -m "feat(acquire-store): AcquireStore Protocol + concrete store + 4 sub-stores"
```

---

### Task 4 — Wire store into `build_acquire_context` + phase gate

**Files:**

- Modify: `personalscraper/acquire/_factory.py`

- [ ] **Step 1: Update `_factory.py` to call `build_acquire_store`**

In `personalscraper/acquire/_factory.py`, add the store build and pass it to `AcquireContext`:

```python
# In build_acquire_context, after building tracker_registry:
from personalscraper.acquire.store import build_acquire_store

store = build_acquire_store(config.acquire)
return AcquireContext(
    tracker_registry=tracker_registry,
    store=store,
    torrent_client=torrent_client,
)
```

Update imports and docstring to reflect that `store` is now always set.

- [ ] **Step 2: Run acquire tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/ -x -q 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 3: Run make check (full gate)**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -30
```

Expected: green. 0 failures.

- [ ] **Step 4: Commit**

```bash
git add personalscraper/acquire/_factory.py
git commit -m "chore(acquire-store): phase 3 gate — domain + schema + store wired into AcquireContext"
```
