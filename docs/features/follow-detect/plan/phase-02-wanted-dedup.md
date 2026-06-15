# Phase 2 — Wanted dedup (`find`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add `WantedSubStore.find(...)` — a soft dedup guard that returns the first matching `WantedItem` for `(followed_id, kind, season, episode)`, or `None`. Protocol addition in `_ports.py`, implementation in `store.py`. Tests: design criterion 4.

**Architecture:** Soft guard (no UNIQUE DB constraint) so the DETECT command can report the dedup distinctly and the NULL-episode movie case stays safe. The `WHERE` uses `IS` for NULL-safe comparison. Single-writer detection makes the soft guard sufficient.

**Tech Stack:** Python 3.11+, `sqlite3`, `pytest`, `make test`

---

## Gate

Phase 1 must be complete:

- [ ] `personalscraper/acquire/cadence.py` exists and is importable.
- [ ] `personalscraper/acquire/desired.py` exports `cadence_from_config`, `cadence_from_json`, `cadence_to_json`, `effective_cadence`.
- [ ] `pytest tests/acquire/test_cadence.py` passes with 0 failures.

---

## Sub-phase 2.1 — Protocol + implementation

**Files:**

- Modify: `personalscraper/acquire/_ports.py` (add `find` to `WantedSubStore` protocol)
- Modify: `personalscraper/acquire/store.py` (add `find` to `_WantedSubStore`)
- Create: `tests/acquire/test_store_wanted_find.py`

### Task 1: Add `find` to `WantedSubStore` protocol in `_ports.py`

- [ ] **Step 1: Read `_ports.py:72-102` to locate the insert point**

```bash
grep -n "class WantedSubStore\|def list_stale\|def mark_grabbed" personalscraper/acquire/_ports.py --type py
```

- [ ] **Step 2: Add `find` method to `WantedSubStore` protocol (after `list_stale_searching`)**

```python
    def find(
        self,
        *,
        followed_id: int | None,
        kind: WantedKind,
        season: int | None,
        episode: int | None,
    ) -> WantedItem | None:
        """Return the first matching wanted row, or None (soft dedup guard).

        Uses NULL-safe comparison (``IS`` not ``=``) for ``season`` and
        ``episode`` so that a NULL episode in a future movie case does not
        accidentally match an episode row.

        Args:
            followed_id: FK to ``followed_series`` row, or ``None``.
            kind: ``"movie"`` or ``"episode"``.
            season: Season number, or ``None`` for movies.
            episode: Episode number, or ``None`` for movies.

        Returns:
            The first matching :class:`WantedItem` if found, else ``None``.
        """
        ...
```

### Task 2: Implement `find` in `_WantedSubStore` in `store.py`

- [ ] **Step 3: Read `store.py` around line 585 to find the end of `list_stale_searching`**

```bash
grep -n "def list_stale_searching\|def mark_grabbed\|def claim_for_search" personalscraper/acquire/store.py
```

- [ ] **Step 4: Add `find` implementation after `list_stale_searching` in `_WantedSubStore`**

```python
    def find(
        self,
        *,
        followed_id: int | None,
        kind: WantedKind,
        season: int | None,
        episode: int | None,
    ) -> WantedItem | None:
        """Return the first matching wanted row, or None (soft dedup guard).

        Uses ``IS`` for NULL-safe season/episode comparison to avoid false
        matches between episode rows (season/episode non-NULL) and future movie
        rows (season/episode NULL).

        Args:
            followed_id: FK to ``followed_series`` row, or ``None``.
            kind: ``"movie"`` or ``"episode"``.
            season: Season number, or ``None``.
            episode: Episode number, or ``None``.

        Returns:
            The first matching :class:`WantedItem` if found, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT id, followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   grabbed_hash
            FROM wanted
            WHERE followed_id IS ?
              AND kind = ?
              AND season IS ?
              AND episode IS ?
            ORDER BY id
            LIMIT 1
            """,
            (followed_id, kind, season, episode),
        ).fetchone()
        return _row_to_wanted(row) if row is not None else None
```

### Task 3: Write round-trip tests

- [ ] **Step 5: Create `tests/acquire/test_store_wanted_find.py`**

```python
"""Tests for _WantedSubStore.find — soft dedup guard (criterion 4)."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import AcquireStore
from personalscraper.core.identity import MediaRef


def _make_store(tmp_path: Path) -> AcquireStore:
    """Open a fresh AcquireStore for testing."""
    db = tmp_path / "acquire.db"
    return AcquireStore(db_path=db)


def _episode(followed_id: int, season: int, ep: int) -> WantedItem:
    return WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="episode",
        status="pending",
        enqueued_at=1_000_000,
        followed_id=followed_id,
        season=season,
        episode=ep,
    )


def test_find_returns_none_when_empty(tmp_path: Path) -> None:
    """find returns None when the wanted table is empty."""
    store = _make_store(tmp_path)
    with store:
        result = store.wanted.find(followed_id=1, kind="episode", season=1, episode=1)
    assert result is None


def test_find_returns_row_after_add(tmp_path: Path) -> None:
    """find returns the WantedItem that was just added via add()."""
    store = _make_store(tmp_path)
    item = _episode(followed_id=7, season=2, ep=3)
    with store:
        store.wanted.add(item)
        result = store.wanted.find(followed_id=7, kind="episode", season=2, episode=3)
    assert result is not None
    assert result.followed_id == 7
    assert result.season == 2
    assert result.episode == 3
    assert result.kind == "episode"
    assert result.status == "pending"


def test_find_returns_none_for_different_episode(tmp_path: Path) -> None:
    """find returns None when season/episode does not match."""
    store = _make_store(tmp_path)
    with store:
        store.wanted.add(_episode(followed_id=1, season=1, ep=1))
        result = store.wanted.find(followed_id=1, kind="episode", season=1, episode=2)
    assert result is None


def test_find_null_safe_season_no_false_match(tmp_path: Path) -> None:
    """find(season=None) does NOT match an episode row with season=1."""
    store = _make_store(tmp_path)
    with store:
        store.wanted.add(_episode(followed_id=1, season=1, ep=1))
        result = store.wanted.find(followed_id=1, kind="episode", season=None, episode=None)
    assert result is None


def test_find_different_followed_id_no_match(tmp_path: Path) -> None:
    """find with a different followed_id returns None."""
    store = _make_store(tmp_path)
    with store:
        store.wanted.add(_episode(followed_id=1, season=1, ep=1))
        result = store.wanted.find(followed_id=2, kind="episode", season=1, episode=1)
    assert result is None
```

- [ ] **Step 6: Run dedup tests — all must PASS**

```bash
pytest tests/acquire/test_store_wanted_find.py -v
```

Expected: `5 passed`, `0 failed`.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/acquire/_ports.py personalscraper/acquire/store.py tests/acquire/test_store_wanted_find.py
git commit -m "feat(follow-detect): add WantedSubStore.find — soft dedup guard"
```

---

## Phase 2 Gate

- [ ] **Run `make check`** — must exit 0.
- [ ] **Smoke test:** `python -c "import personalscraper"` — must exit 0.
- [ ] **Protocol check:**

```bash
python -c "
from personalscraper.acquire._ports import WantedSubStore
import inspect
assert 'find' in {m for m in dir(WantedSubStore)}, 'find missing from protocol'
print('OK')
"
```

Expected: `OK`.
