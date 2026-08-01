# Phase 1 — Domain + Store (season kind, absorbed/fallback)

## Gate

- [ ] `make lint` (ruff + mypy) zero errors
- [ ] `make test` all pass (focus: acquire/test_domain.py, acquire/store/ tests)
- [ ] `python -c "import personalscraper"` smoke test
- [ ] `rg "WantedKind" --type py personalscraper/acquire/` confirms "season" in Literal
- [ ] `rg "WantedStatus" --type py personalscraper/acquire/` confirms "absorbed" + "fallback_episodes" present
- [ ] Migration 013 applies cleanly on a real acquire.db copy: `sqlite3 acquire.db < 013_...sql`

## Sub-phase 1.1 — Domain value objects (WantedKind, WantedStatus, new events)

**Files**: `acquire/domain.py:20-21`, `acquire/domain.py:29`, `acquire/events.py:85-91,364`

### Step 1: Widen `WantedKind`

In `acquire/domain.py:20`:

```python
# BEFORE
WantedKind = Literal["movie", "episode"]

# AFTER
WantedKind = Literal["movie", "episode", "season"]
```

### Step 2: Widen `WantedStatus`

In `acquire/domain.py:21`:

```python
# BEFORE
WantedStatus = Literal["pending", "searching", "available", "grabbed", "done", "abandoned"]

# AFTER
WantedStatus = Literal["pending", "searching", "available", "grabbed", "done", "abandoned", "absorbed", "fallback_episodes"]
```

Also widen the `valid_statuses` tuple in `WantedItem.__post_init__`:

```python
# In domain.py:206 — the second tuple in WantedItem.__post_init__
valid_statuses: tuple[str, ...] = (
    "pending", "searching", "available", "grabbed", "done", "abandoned",
    "absorbed", "fallback_episodes",
)
```

**Plan-drift note**: `OPEN_WANTED_STATUSES` at domain.py:29 stays `{"pending", "searching", "available", "grabbed"}` — "absorbed" and "fallback_episodes" are closed/terminal states, not open for search.

### Step 3: Add `absorbed_by` field to `WantedItem`

In `acquire/domain.py`, add to the `WantedItem` dataclass:

```python
absorbed_by: int | None = None
```

This carries the season wanted row id on an absorbed episode row. Persisted in the migration below; reads via `_row_to_wanted` (in `_store_rows.py`).

### Step 4: Widen `WantedEnqueued.kind`

In `acquire/events.py:85-91`:

```python
# BEFORE
kind: Literal["movie", "episode"]

# AFTER
kind: Literal["movie", "episode", "season"]
```

### Step 5: Add new events to the acquisition event catalog

In `acquire/events.py`, add TWO new event classes after `WantedEnqueued`:

```python
@dataclass(frozen=True, kw_only=True)
class SeasonAbsorbedEpisodes(Event):
    """A season wanted absorbed its season's live episode wanteds (R5).

    Emitted when detection or the conversion path absorbs episode rows
    into a season wanted — the episode rows transition to ``absorbed``
    and the season wanted governs their acquisition.

    Attributes:
        season_wanted_id: Rowid of the absorbing season ``wanted`` row.
        media_ref: Provider-ID key of the parent series.
        season: Season number.
        absorbed_ids: Rowids of the episode rows that were absorbed.
    """

    season_wanted_id: int
    media_ref: MediaRef
    season: int
    absorbed_ids: tuple[int, ...]


@dataclass(frozen=True, kw_only=True)
class SeasonFellBackToEpisodes(Event):
    """A season wanted fell back to per-episode retry (R6).

    Emitted when a season wanted reaches its cutoff — the season row
    transitions to ``fallback_episodes`` and the missing episodes are
    re-enqueued individually. Telegram notification fires per existing
    cutoff path.

    Attributes:
        season_wanted_id: Rowid of the season ``wanted`` row.
        media_ref: Provider-ID key of the parent series.
        season: Season number.
        reenqueued_count: Number of missing episodes re-enqueued.
    """

    season_wanted_id: int
    media_ref: MediaRef
    season: int
    reenqueued_count: int
```

Register both in `__all__` and in the eager-import hub. The eager-import hub is `personalscraper/acquire/events.py` itself — every event class in `__all__` is already importable from `personalscraper.acquire.events`. No separate hub file exists. To ensure production event-bus wiring, import these in `personalscraper/core/event_bus.py`'s eager-import block if one exists; verify by grepping the current `SeasonAbsorbedEpisodes` and `SeasonFellBackToEpisodes` are accessible via `from personalscraper.acquire.events import ...` at all emission sites.

### Step 6: Tests

```python
# tests/acquire/test_domain.py
def test_wanted_kind_includes_season():
    """WantedKind must accept 'season' after widening."""
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.core.identity import MediaRef
    import time
    now = int(time.time())
    item = WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="season",
        status="pending",
        enqueued_at=now,
        season=3,
        episode=None,
    )
    assert item.kind == "season"
    assert item.season == 3
    assert item.episode is None


def test_wanted_status_includes_absorbed_and_fallback():
    """WantedStatus must accept 'absorbed' and 'fallback_episodes'."""
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.core.identity import MediaRef
    import time
    now = int(time.time())
    # absorbed
    item = WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="episode",
        status="absorbed",
        enqueued_at=now,
        season=3,
        episode=5,
    )
    assert item.status == "absorbed"
    # fallback_episodes
    item2 = WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="season",
        status="fallback_episodes",
        enqueued_at=now,
        season=3,
        episode=None,
    )
    assert item2.status == "fallback_episodes"


def test_wanted_enqueued_kind_season():
    """WantedEnqueued must accept kind='season'."""
    from personalscraper.acquire.events import WantedEnqueued
    from personalscraper.core.identity import MediaRef
    ev = WantedEnqueued(media_ref=MediaRef(tvdb_id=12345), kind="season", season=3, episode=None)
    assert ev.kind == "season"
    assert ev.season == 3
    assert ev.episode is None


def test_season_absorbed_episodes_event():
    """SeasonAbsorbedEpisodes carries the expected fields."""
    from personalscraper.acquire.events import SeasonAbsorbedEpisodes
    from personalscraper.core.identity import MediaRef
    ev = SeasonAbsorbedEpisodes(
        season_wanted_id=42,
        media_ref=MediaRef(tvdb_id=12345),
        season=3,
        absorbed_ids=(10, 11, 12),
    )
    assert ev.season_wanted_id == 42
    assert len(ev.absorbed_ids) == 3


def test_season_fell_back_to_episodes_event():
    """SeasonFellBackToEpisodes carries the expected fields."""
    from personalscraper.acquire.events import SeasonFellBackToEpisodes
    from personalscraper.core.identity import MediaRef
    ev = SeasonFellBackToEpisodes(
        season_wanted_id=42,
        media_ref=MediaRef(tvdb_id=12345),
        season=3,
        reenqueued_count=5,
    )
    assert ev.season == 3
    assert ev.reenqueued_count == 5
```

Run: `pytest tests/acquire/test_domain.py -v -k "season or absorbed or fallback"` and `pytest tests/acquire/ -v -k "test_wanted_enqueued or test_season"`

## Sub-phase 1.2 — Store: find() for season kind, absorb/fallback write methods

**Files**: `acquire/_wanted_store.py:810-849`, `acquire/_store_rows.py`

### Step 1: Adapt `find()` to accept `kind="season"`

The existing `find()` at `_wanted_store.py:810-849` uses `kind`, `season`, and `episode` in its WHERE clause. For season wanted items (`kind="season"`, `season=N`, `episode=None`), the `episode IS ?` clause with `None` parameter correctly matches NULL episodes. No code change needed — the signature already handles this. Verify by test:

```python
# tests/acquire/store/test_wanted_store.py
def test_find_season_wanted():
    """find() with kind='season', season=N, episode=None returns the season row."""
    store = build_acquire_store(...)
    # Insert a season wanted
    wid = store.wanted.add(WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="season", status="pending", enqueued_at=now,
        followed_id=follow_id, season=3, episode=None,
    ))
    found = store.wanted.find(followed_id=follow_id, kind="season", season=3, episode=None)
    assert found is not None
    assert found.id == wid
    assert found.kind == "season"
```

### Step 2: Add `list_season_pending()` method

The search pass needs to list season items. Add to `_WantedSubStore`:

```python
def list_season_pending(self) -> list[WantedItem]:
    """Return pending season wanted rows (idx_wanted_pending covers kind='season' too)."""
    return [w for w in self.list_pending() if w.kind == "season"]
```

**Plan-drift note**: Actually, `list_pending()` returns ALL pending rows regardless of kind. The search pass filter for season kind can happen in the service layer via `[w for w in self._store.wanted.list_pending() if w.kind == "season"]` — no new store method needed unless profiling shows the in-memory filter is slow. For v1, filter in memory.

### Step 3: Add `absorb_episodes()` method

```python
def absorb_episodes(self, season_wanted_id: int, episode_ids: tuple[int, ...]) -> int:
    """Transition episode wanteds to ``absorbed``, linking them to the season row.

    Called when a season wanted absorbs its live episode siblings (R5).
    Runs inside a single ``BEGIN IMMEDIATE`` transaction.

    Args:
        season_wanted_id: Rowid of the absorbing season ``wanted`` row.
        episode_ids: Rowids of the episode rows to absorb.

    Returns:
        Number of rows actually transitioned (may be less than len(episode_ids)
        if some were already absorbed/closed).
    """
    if not episode_ids:
        return 0
    placeholders = ", ".join("?" for _ in episode_ids)
    with self._write_tx(self._conn):
        cur = self._conn.execute(
            f"UPDATE wanted SET status = 'absorbed', absorbed_by = ? "
            f"WHERE id IN ({placeholders}) AND status IN ('pending', 'searching', 'available')",
            (season_wanted_id, *episode_ids),
        )
        return cur.rowcount
```

### Step 4: Add `fallback_season()` method

```python
def fallback_season(self, season_wanted_id: int) -> bool:
    """Transition a season row to ``fallback_episodes`` — the cutoff path (R6).

    Guarded on ``kind='season'`` and OPEN_WANTED_STATUSES.

    Args:
        season_wanted_id: Rowid of the season ``wanted`` row.

    Returns:
        ``True`` iff the row transitioned.
    """
    open_statuses = tuple(sorted(OPEN_WANTED_STATUSES))
    placeholders = ", ".join("?" for _ in open_statuses)
    with self._write_tx(self._conn):
        cur = self._conn.execute(
            f"UPDATE wanted SET status = 'fallback_episodes' "
            f"WHERE id = ? AND kind = 'season' AND status IN ({placeholders})",
            (season_wanted_id, *open_statuses),
        )
        return cur.rowcount == 1
```

### Step 5: Tests

```python
# tests/acquire/store/test_wanted_store.py
def test_absorb_episodes_transitions_status():
    """absorb_episodes() sets status='absorbed' + absorbed_by on matching rows."""
    # Setup: create a season wanted (id=100) + 3 episode wanteds (ids=101-103)
    # ...
    count = store.wanted.absorb_episodes(100, (101, 102, 103))
    assert count == 3
    for eid in (101, 102, 103):
        row = store.wanted.get(eid)
        assert row is not None and row.status == "absorbed"


def test_fallback_season_transitions_season_row():
    """fallback_season() transitions only the season row."""
    # Setup: create a season wanted (id=100, kind='season')
    # ...
    ok = store.wanted.fallback_season(100)
    assert ok
    row = store.wanted.get(100)
    assert row.status == "fallback_episodes"
```

## Sub-phase 1.3 — Migration 013 (CHECK constraint widening + absorbed_by column)

**Files**: `acquire/migrations/013_season_kind.sql` (NEW)

### Schema changes

1. Widen `kind` CHECK: `('movie', 'episode')` → `('movie', 'episode', 'season')`
2. Widen `status` CHECK: add `'absorbed'`, `'fallback_episodes'`
3. Add column `absorbed_by INTEGER REFERENCES wanted(id) ON DELETE SET NULL` — nullable; set when an episode row is absorbed by a season wanted.

### Migration SQL

Like migration 008, SQLite cannot ALTER a CHECK constraint → table rebuild. Follow the 008 pattern exactly (transaction safety, FK disable/restore, version marker inside transaction).

```sql
-- personalscraper/acquire/migrations/013_season_kind.sql
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

CREATE TABLE wanted_new (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode', 'season')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'available',
                                      'grabbed', 'done', 'abandoned',
                                      'absorbed', 'fallback_episodes')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    grabbed_hash    TEXT,
    last_search_outcome TEXT,
    last_search_found   INTEGER,
    tried_hashes_json TEXT,
    absorbed_by     INTEGER REFERENCES wanted_new(id) ON DELETE SET NULL
);

INSERT INTO wanted_new (
    id, followed_id, media_ref_json, kind, season, episode,
    status, criteria_json, enqueued_at, last_search_at, attempts,
    grabbed_hash, last_search_outcome, last_search_found, tried_hashes_json
)
SELECT
    id, followed_id, media_ref_json, kind, season, episode,
    status, criteria_json, enqueued_at, last_search_at, attempts,
    grabbed_hash, last_search_outcome, last_search_found, tried_hashes_json
FROM wanted;

DROP TABLE wanted;
ALTER TABLE wanted_new RENAME TO wanted;

CREATE INDEX IF NOT EXISTS idx_wanted_pending
    ON wanted (status) WHERE status = 'pending';

INSERT OR IGNORE INTO schema_version(version) VALUES (13);
PRAGMA user_version = 13;

COMMIT;
PRAGMA foreign_key_check;
PRAGMA foreign_keys = ON;
```

### Also update `_store_rows.py`

Add to `_row_to_wanted()`:

```python
absorbed_by = int(row["absorbed_by"]) if row["absorbed_by"] is not None else None
```

And include `absorbed_by` in the WantedItem constructor call.

### Also update `_wanted_store.py` SELECTs

Every SELECT that lists wanted rows must include `absorbed_by` in the column list. The `get()`, `find()`, `list_pending()`, `list_available()`, etc. — add `absorbed_by` to the SELECT and pass through `_row_to_wanted`.

### Tests

```python
def test_migration_013_accepts_season_kind():
    """INSERT with kind='season' must succeed after migration."""
    store = build_acquire_store(config.acquire)
    wid = store.wanted.add(WantedItem(
        media_ref=MediaRef(tvdb_id=12345), kind="season",
        status="pending", enqueued_at=int(time.time()),
        season=3, episode=None,
    ))
    row = store.wanted.get(wid)
    assert row.kind == "season"
```

Run: `pytest tests/acquire/store/ -v -k "test_find_season or test_absorb or test_fallback or test_migration_013"`

## Commit

```bash
git add personalscraper/acquire/domain.py personalscraper/acquire/events.py \
        personalscraper/acquire/_wanted_store.py personalscraper/acquire/_store_rows.py \
        personalscraper/acquire/migrations/013_season_kind.sql \
        tests/acquire/test_domain.py tests/acquire/store/test_wanted_store.py
git commit -m "feat(season-grab): widen WantedKind to 'season', add absorbed/fallback_episodes statuses, events SeasonAbsorbedEpisodes/SeasonFellBackToEpisodes, migration 013"
```
