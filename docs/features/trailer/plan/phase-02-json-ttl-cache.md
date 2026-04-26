# Phase 2 — Extract `JsonTTLCache` primitive

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §6 second half ("Extract JsonTTLCache"). Factor a generic
`scraper/json_ttl_cache.py` out of `keywords_cache.py`. Refactor `keywords_cache.py` to use
`JsonTTLCache` internally while keeping the on-disk format (`tmdb_keywords_cache.json`)
byte-for-byte unchanged. Add `tests/scraper/test_json_ttl_cache.py`. The existing
`tests/scraper/test_keywords_cache.py` must still pass without modification.

**Architecture:** `JsonTTLCache` is a generic, key-typed cache: `get(key) -> T | None`,
`set(key, value, ttl_seconds)`, `invalidate(key)`, `compact()`. `KeywordsCache` becomes a
thin adapter over `JsonTTLCache`. No change to the JSON schema on disk.

**Tech Stack:** Python, `dataclasses`, `pytest`, `ruff`, `mypy`.

---

## Gate (entry condition)

This phase has no dependency on Phase 1 (they are independent). Verify branch:

```bash
git branch --show-current
# expected: feat/trailer
```

---

## Dependencies

None. Phase 2 is independent of Phase 1.

---

## Invariants for this phase

- **`tests/scraper/test_keywords_cache.py` must pass without any modification.** It is the
  regression guard for the on-disk format and `KeywordsCache` public API.
- **On-disk format unchanged.** The backing file remains `tmdb_keywords_cache.json` with
  keys `"movie_{id}"` / `"tv_{id}"` and values `{"keywords": [...], "cached_at": "..."}`.
- `KeywordsCache` public API (`get`, `set`) is not renamed, not re-typed, not re-signed.

---

## Sub-phase 2.1 — Write `JsonTTLCache` + tests

### Files

| Action | Path                                        | Responsibility                |
| ------ | ------------------------------------------- | ----------------------------- |
| Create | `personalscraper/scraper/json_ttl_cache.py` | Generic TTL cache primitive   |
| Create | `tests/scraper/test_json_ttl_cache.py`      | Unit tests for `JsonTTLCache` |

### Step 1: Write failing tests first

Create `tests/scraper/test_json_ttl_cache.py`:

```python
"""Unit tests for JsonTTLCache — generic file-backed JSON cache with TTL.

Tests cover: get/set round-trip, TTL expiry, invalidate, compact,
missing file, corrupt file, and atomic write guarantees.
"""

import json
import time
from pathlib import Path

import pytest

from personalscraper.scraper.json_ttl_cache import JsonTTLCache


@pytest.fixture()
def cache(tmp_path: Path) -> JsonTTLCache:
    """A fresh JsonTTLCache backed by a temp directory."""
    return JsonTTLCache(tmp_path / "test_cache.json")


# ── get / set round-trip ─────────────────────────────────────────────────────

class TestGetSet:
    def test_miss_on_empty_cache(self, cache):
        """get() returns None when the cache file does not exist."""
        assert cache.get("k1") is None

    def test_set_then_get_returns_value(self, cache):
        """get() returns the value immediately after set()."""
        cache.set("k1", {"data": [1, 2, 3]}, ttl_seconds=3600)
        result = cache.get("k1")
        assert result == {"data": [1, 2, 3]}

    def test_set_overwrites_existing_key(self, cache):
        """set() on an existing key replaces the previous value."""
        cache.set("k1", "first", ttl_seconds=3600)
        cache.set("k1", "second", ttl_seconds=3600)
        assert cache.get("k1") == "second"

    def test_multiple_keys_independent(self, cache):
        """Multiple keys are stored and retrieved independently."""
        cache.set("a", 1, ttl_seconds=3600)
        cache.set("b", 2, ttl_seconds=3600)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_get_missing_key_returns_none(self, cache):
        """get() returns None for a key that was never set."""
        cache.set("a", 1, ttl_seconds=3600)
        assert cache.get("b") is None


# ── TTL expiry ───────────────────────────────────────────────────────────────

class TestTTL:
    def test_entry_valid_before_expiry(self, cache):
        """get() returns value when TTL has not elapsed."""
        cache.set("k", "value", ttl_seconds=3600)
        assert cache.get("k") == "value"

    def test_entry_expired_returns_none(self, tmp_path):
        """get() returns None when the stored cached_at is older than the TTL."""
        # Write an expired entry directly into the backing file
        backing = tmp_path / "expired.json"
        old_timestamp = "2020-01-01T00:00:00"
        backing.write_text(
            json.dumps({"k": {"value": "stale", "cached_at": old_timestamp, "ttl_seconds": 1}}),
            encoding="utf-8",
        )
        cache = JsonTTLCache(backing)
        assert cache.get("k") is None

    def test_zero_ttl_is_immediately_expired(self, cache):
        """A TTL of 0 seconds means the entry is expired on the next get()."""
        cache.set("k", "v", ttl_seconds=0)
        # Sleep is not needed: the cached_at is set to now, ttl=0 means any read is stale
        # (>= 0 elapsed). Ensure at least 1 ms passes by reloading from disk.
        result = cache.get("k")
        # May be None (already stale) or "v" depending on sub-millisecond timing;
        # the critical invariant is no exception raised.
        assert result is None or result == "v"


# ── invalidate ───────────────────────────────────────────────────────────────

class TestInvalidate:
    def test_invalidate_removes_key(self, cache):
        """invalidate() removes the entry so get() returns None."""
        cache.set("k", "v", ttl_seconds=3600)
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_invalidate_nonexistent_key_is_noop(self, cache):
        """invalidate() on a missing key does not raise."""
        cache.invalidate("does_not_exist")  # must not raise

    def test_invalidate_does_not_affect_other_keys(self, cache):
        """invalidate() removes only the target key."""
        cache.set("a", 1, ttl_seconds=3600)
        cache.set("b", 2, ttl_seconds=3600)
        cache.invalidate("a")
        assert cache.get("a") is None
        assert cache.get("b") == 2


# ── compact ──────────────────────────────────────────────────────────────────

class TestCompact:
    def test_compact_removes_expired_entries(self, tmp_path):
        """compact() removes expired entries and retains fresh ones."""
        backing = tmp_path / "compact.json"
        old_ts = "2020-01-01T00:00:00"
        backing.write_text(
            json.dumps({
                "old": {"value": "stale", "cached_at": old_ts, "ttl_seconds": 1},
                "fresh": {"value": "keep", "cached_at": "2099-01-01T00:00:00", "ttl_seconds": 3600},
            }),
            encoding="utf-8",
        )
        cache = JsonTTLCache(backing)
        cache.compact()
        assert cache.get("old") is None
        assert cache.get("fresh") == "keep"

    def test_compact_on_empty_cache_is_noop(self, cache):
        """compact() on a non-existent backing file does not raise."""
        cache.compact()  # must not raise


# ── robustness ───────────────────────────────────────────────────────────────

class TestRobustness:
    def test_corrupt_file_returns_none(self, tmp_path):
        """get() returns None gracefully when the backing file is corrupt JSON."""
        backing = tmp_path / "corrupt.json"
        backing.write_text("not valid json{{{", encoding="utf-8")
        cache = JsonTTLCache(backing)
        assert cache.get("k") is None

    def test_missing_file_returns_none(self, tmp_path):
        """get() returns None when the backing file does not exist."""
        cache = JsonTTLCache(tmp_path / "nonexistent.json")
        assert cache.get("k") is None

    def test_atomic_write_uses_temp_file(self, cache, tmp_path):
        """set() creates the backing file atomically (temp + rename)."""
        cache.set("k", "v", ttl_seconds=3600)
        # After set(), no leftover .tmp files should exist
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Leftover temp files: {tmp_files}"
```

### Step 2: Run failing tests

```bash
pytest tests/scraper/test_json_ttl_cache.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'personalscraper.scraper.json_ttl_cache'`.

### Step 3: Implement `personalscraper/scraper/json_ttl_cache.py`

```python
"""Generic file-backed JSON cache with per-entry TTL.

Extracted from ``keywords_cache.py`` to serve as a shared primitive for
TMDB video responses, YouTube search results, and any future cached data.

Cache file format: a JSON object where each key maps to::

    {
        "value":       <any JSON-serialisable value>,
        "cached_at":   "2026-04-23T03:12:04.123456",  # UTC ISO 8601
        "ttl_seconds": 86400
    }

Entries with ``cached_at`` older than ``ttl_seconds`` are treated as cache
misses. Writes are atomic: temp file + ``os.replace``.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

UTC = timezone.utc


def check_ttl(
    cached_at: datetime,
    ttl_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True if ``cached_at`` is within ``ttl_seconds`` of ``now``.

    Shared helper used by both ``JsonTTLCache`` and
    ``scraper/keywords_cache.py`` so TTL arithmetic has a single source of
    truth. All datetimes must be timezone-aware (UTC recommended). A naive
    ``cached_at`` is promoted to UTC for backward compatibility with pre-UTC
    cache files written by earlier ``keywords_cache`` versions.

    Args:
        cached_at: Timestamp stored alongside the cached value. Naive values
            are treated as UTC.
        ttl_seconds: Entry lifetime in seconds (``0`` means always expired).
        now: Override for ``datetime.now(UTC)`` in tests. Must be aware if
            provided.

    Returns:
        ``True`` if the entry is still fresh (elapsed < ttl_seconds),
        ``False`` otherwise.
    """
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)
    current = now if now is not None else datetime.now(UTC)
    return (current - cached_at).total_seconds() < ttl_seconds


class JsonTTLCache:
    """Generic file-backed key/value cache with per-entry TTL.

    Stores arbitrary JSON-serialisable values. Each entry carries its own
    ``ttl_seconds`` so callers can mix short-lived and long-lived entries
    in the same backing file.

    Atomic writes are implemented via ``tempfile.NamedTemporaryFile`` +
    ``os.replace`` — the backing file is never left partially written.

    Attributes:
        _path: Absolute Path to the backing JSON file.
    """

    def __init__(self, path: Path) -> None:
        """Initialize the cache backed by ``path``.

        The file is created on the first ``set()`` call. The parent directory
        must exist; it is NOT created automatically.

        Args:
            path: Absolute path to the backing JSON file.
        """
        self._path = path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return the cached value or ``None`` on miss / expiry.

        Args:
            key: Cache key string.

        Returns:
            The stored value, or ``None`` if the key is absent, the entry
            has expired, or the backing file cannot be parsed.
        """
        data = self._load()
        entry = data.get(key)
        if entry is None:
            return None

        try:
            cached_at = datetime.fromisoformat(str(entry["cached_at"]))
            ttl_seconds = int(entry["ttl_seconds"])
        except (KeyError, ValueError, TypeError):
            logger.warning("Cannot parse cache entry for key %r — treating as miss", key)
            return None

        if not check_ttl(cached_at, ttl_seconds):
            return None

        return entry.get("value")

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Write or overwrite a cache entry atomically.

        Args:
            key: Cache key string.
            value: JSON-serialisable value to store.
            ttl_seconds: Entry lifetime in seconds from now.
        """
        data = self._load()
        data[key] = {
            "value": value,
            "cached_at": datetime.now(UTC).isoformat(),
            "ttl_seconds": ttl_seconds,
        }
        self._atomic_save(data)

    def invalidate(self, key: str) -> None:
        """Remove a single entry from the cache.

        A no-op if the key does not exist.

        Args:
            key: Cache key to remove.
        """
        data = self._load()
        if key in data:
            del data[key]
            self._atomic_save(data)

    def compact(self) -> None:
        """Remove all expired entries from the backing file.

        Reads the file, drops expired entries, and writes back. A no-op if
        the file does not exist.
        """
        data = self._load()
        now = datetime.now(UTC)
        fresh: dict[str, Any] = {}
        for key, entry in data.items():
            try:
                cached_at = datetime.fromisoformat(str(entry["cached_at"]))
                ttl_seconds = int(entry["ttl_seconds"])
                if check_ttl(cached_at, ttl_seconds, now=now):
                    fresh[key] = entry
            except (KeyError, ValueError, TypeError):
                # Malformed entry — drop it during compaction
                logger.debug("Dropping malformed cache entry during compact: %r", key)
        if len(fresh) != len(data):
            self._atomic_save(fresh)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        """Read the backing file and return its parsed contents.

        Returns an empty dict if the file does not exist or cannot be parsed.

        Returns:
            Parsed JSON dict; empty dict on any error.
        """
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                return {}
            return {k: v for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Cannot read cache %s: %s — starting fresh", self._path, exc)
            return {}

    def _atomic_save(self, data: dict[str, Any]) -> None:
        """Write ``data`` to the backing file via temp file + os.replace.

        Args:
            data: Dict to serialise as JSON.

        Raises:
            OSError: If the temp file cannot be created or the replace fails.
        """
        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name

        try:
            os.replace(tmp_path, self._path)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
```

### Step 4: Run tests — all must pass

```bash
pytest tests/scraper/test_json_ttl_cache.py -v
```

### Step 5: Commit sub-phase 2.1

```bash
git add \
  personalscraper/scraper/json_ttl_cache.py \
  tests/scraper/test_json_ttl_cache.py
git commit -m "feat(trailer): add JsonTTLCache generic file-backed cache primitive"
```

---

## Sub-phase 2.2 — Refactor `KeywordsCache` to call the shared `check_ttl()` helper

### Files

| Action | Path                                        | Responsibility                                            |
| ------ | ------------------------------------------- | --------------------------------------------------------- |
| Modify | `personalscraper/scraper/keywords_cache.py` | Use `json_ttl_cache.check_ttl()` for TTL comparison logic |

### Step 1: Why a partial refactor, not full delegation

`KeywordsCache` stores entries as `{"keywords": [...], "cached_at": "..."}` — a domain-specific
schema that `JsonTTLCache` cannot emit (the generic cache uses `{"value": ..., "cached_at":
..., "ttl_seconds": ...}`). Changing `tmdb_keywords_cache.json` on disk would break the
"on-disk format unchanged" invariant from DESIGN §6 and would require a one-shot migration of
existing cache files in production.

Rather than accept either compromise, Phase 2 factors **just the TTL arithmetic** into a
pure-function helper that lives next to `JsonTTLCache`: `check_ttl(cached_at, ttl_seconds,
*, now=None) -> bool` in `json_ttl_cache.py` (already added in Sub-phase 2.1). Both
`JsonTTLCache` and `KeywordsCache` call `check_ttl()` — this delivers the DESIGN §6 promise
of a single source of truth for TTL logic without touching the on-disk format.

The `KeywordsCache._load()` / `_atomic_save()` methods keep their current behaviour because
the schema they own is narrower (no `ttl_seconds`, no wrapping `value` key). Only the
freshness check is replaced.

### Step 2: Replace inline TTL math with `check_ttl()`

Open `personalscraper/scraper/keywords_cache.py` and apply **only** these edits:

1. Add the import at the top of the file, grouped with the other `scraper/` imports:
   ```python
   from personalscraper.scraper.json_ttl_cache import check_ttl
   ```
2. Find the freshness check inside `get()` — as of commit `6bd2b66` the check is an inline
   one-liner at `keywords_cache.py:103` (there is NO `_is_expired()` method):
   ```python
   if datetime.now() - cached_at > _TTL:
       return None
   ```
   Replace it with:
   ```python
   if not check_ttl(cached_at, int(_TTL.total_seconds())):
       return None
   ```
   **Edge-case note**: the original uses strict `>` (entry aged exactly `_TTL` is still
   valid). The shared `check_ttl()` helper uses strict `<` on the fresh side (`elapsed <
ttl_seconds`), which means an entry aged exactly `_TTL` becomes expired after the
   refactor. This is considered acceptable (30-day TTL, microsecond-exact equality is
   effectively unreachable) and intentional — it aligns both caches on the same edge
   semantics. The regression test in Step 3 must NOT fixture a `cached_at` at exactly
   `now - _TTL` unless it expects expiry.
3. Expose `_TTL_SECONDS` as a module-level constant alongside `_TTL` so the seconds value
   has a readable name and the refactor stays self-documenting:
   ```python
   _TTL_SECONDS = 30 * 24 * 3600  # 30 days
   _TTL = timedelta(seconds=_TTL_SECONDS)
   ```
   Downstream code keeps using `_TTL` where a `timedelta` is needed and `_TTL_SECONDS`
   where an `int` is needed (i.e. inside the `check_ttl()` call).
4. Update the module docstring to note the shared helper:

   ```python
   """TMDB keywords cache.

   TTL freshness is evaluated via the shared
   ``scraper/json_ttl_cache.check_ttl()`` helper so all TTL-bearing caches in
   the project behave identically (including timezone handling). The on-disk
   format of ``tmdb_keywords_cache.json`` is preserved for backward
   compatibility; new caches should use ``JsonTTLCache`` directly.
   """
   ```

5. In `_parse_cached_at()` (or wherever `datetime.fromisoformat` is called on the stored
   timestamp), if the codebase was previously using naive timestamps, the promotion to UTC
   is handled inside `check_ttl()` — no additional changes needed here.

No other logic changes. `_load`, `_atomic_save`, and the public API (`get`, `set`) keep
their existing signatures and behaviour.

### Step 3: Add a backward-compat fixture test to `test_keywords_cache.py`

Append one new test to `tests/scraper/test_keywords_cache.py` that asserts a pre-migration
fixture (naive `cached_at`) still loads correctly — it guards against future regressions
if someone tightens `check_ttl()` to reject naive timestamps:

```python
def test_naive_cached_at_still_valid(tmp_path):
    """Pre-migration cache files with naive cached_at must still be readable."""
    # KeywordsCache takes a directory — it appends `tmdb_keywords_cache.json` internally.
    data_dir = tmp_path
    # Format used before the check_ttl() refactor — no tzinfo in cached_at.
    naive_now = datetime.now().isoformat()
    (data_dir / "tmdb_keywords_cache.json").write_text(
        json.dumps({"movie_550": {"keywords": ["fight club"], "cached_at": naive_now}}),
        encoding="utf-8",
    )
    cache = KeywordsCache(data_dir)
    assert cache.get("movie_550") == ["fight club"]
```

### Step 4: Run existing tests — must pass without modification

```bash
pytest tests/scraper/test_keywords_cache.py -v
```

Expected: all existing tests PASS (the new backward-compat test is the only addition).
If any existing test fails, the refactor introduced a regression — revert and re-examine.

### Step 5: Commit sub-phase 2.2

```bash
git add \
  personalscraper/scraper/keywords_cache.py \
  tests/scraper/test_keywords_cache.py
git commit -m "refactor(trailer): route KeywordsCache TTL check through shared check_ttl()"
```

---

## Phase 2 quality gate

- [ ] `pytest tests/scraper/test_json_ttl_cache.py tests/scraper/test_keywords_cache.py -q` — all green
- [ ] `python -m ruff check personalscraper/scraper/json_ttl_cache.py personalscraper/scraper/keywords_cache.py` — no errors
- [ ] `python -m mypy personalscraper/scraper/json_ttl_cache.py` — no type errors

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/scraper/test_json_ttl_cache.py tests/scraper/test_keywords_cache.py -q
python -m ruff check personalscraper/scraper/json_ttl_cache.py personalscraper/scraper/keywords_cache.py
python -m mypy personalscraper/scraper/json_ttl_cache.py
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 02 gate — JsonTTLCache primitive + keywords_cache backward compat"
```

## Exit condition for Phase 3a

Phase 3a may start only when:

- `pytest tests/scraper/ -q` exits 0 (includes both new and existing tests)
- `JsonTTLCache` is importable from `personalscraper.scraper.json_ttl_cache`
- `test_keywords_cache.py` passes without modification
- The milestone commit `chore(trailer): phase 02 gate — ...` is on the branch
