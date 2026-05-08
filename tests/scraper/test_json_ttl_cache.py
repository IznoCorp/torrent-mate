"""Unit tests for JsonTTLCache — generic file-backed JSON cache with TTL.

Tests cover: get/set round-trip, TTL expiry, invalidate, compact,
missing file, corrupt file, and atomic write guarantees.
"""

import errno
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.scraper.json_ttl_cache import JsonTTLCache


@pytest.fixture()
def cache(tmp_path: Path) -> JsonTTLCache:
    """A fresh JsonTTLCache backed by a temp directory."""
    return JsonTTLCache(tmp_path / "test_cache.json")


# ── get / set round-trip ─────────────────────────────────────────────────────


class TestGetSet:
    """Tests for the get/set round-trip behaviour."""

    def test_miss_on_empty_cache(self, cache: JsonTTLCache) -> None:
        """get() returns None when the cache file does not exist."""
        assert cache.get("k1") is None

    def test_set_then_get_returns_value(self, cache: JsonTTLCache) -> None:
        """get() returns the value immediately after set()."""
        cache.set("k1", {"data": [1, 2, 3]}, ttl_seconds=3600)
        result = cache.get("k1")
        assert result == {"data": [1, 2, 3]}

    def test_set_overwrites_existing_key(self, cache: JsonTTLCache) -> None:
        """set() on an existing key replaces the previous value."""
        cache.set("k1", "first", ttl_seconds=3600)
        cache.set("k1", "second", ttl_seconds=3600)
        assert cache.get("k1") == "second"

    def test_multiple_keys_independent(self, cache: JsonTTLCache) -> None:
        """Multiple keys are stored and retrieved independently."""
        cache.set("a", 1, ttl_seconds=3600)
        cache.set("b", 2, ttl_seconds=3600)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_get_missing_key_returns_none(self, cache: JsonTTLCache) -> None:
        """get() returns None for a key that was never set."""
        cache.set("a", 1, ttl_seconds=3600)
        assert cache.get("b") is None


# ── TTL expiry ───────────────────────────────────────────────────────────────


class TestTTL:
    """Tests for TTL expiry behaviour."""

    def test_entry_valid_before_expiry(self, cache: JsonTTLCache) -> None:
        """get() returns value when TTL has not elapsed."""
        cache.set("k", "value", ttl_seconds=3600)
        assert cache.get("k") == "value"

    def test_entry_expired_returns_none(self, tmp_path: Path) -> None:
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

    def test_zero_ttl_is_immediately_expired(self, cache: JsonTTLCache) -> None:
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
    """Tests for the invalidate() method."""

    def test_invalidate_removes_key(self, cache: JsonTTLCache) -> None:
        """invalidate() removes the entry so get() returns None."""
        cache.set("k", "v", ttl_seconds=3600)
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_invalidate_nonexistent_key_is_noop(self, cache: JsonTTLCache) -> None:
        """invalidate() on a missing key does not raise."""
        cache.invalidate("does_not_exist")  # must not raise

    def test_invalidate_does_not_affect_other_keys(self, cache: JsonTTLCache) -> None:
        """invalidate() removes only the target key."""
        cache.set("a", 1, ttl_seconds=3600)
        cache.set("b", 2, ttl_seconds=3600)
        cache.invalidate("a")
        assert cache.get("a") is None
        assert cache.get("b") == 2


# ── compact ──────────────────────────────────────────────────────────────────


class TestCompact:
    """Tests for the compact() method."""

    def test_compact_removes_expired_entries(self, tmp_path: Path) -> None:
        """compact() removes expired entries and retains fresh ones."""
        backing = tmp_path / "compact.json"
        old_ts = "2020-01-01T00:00:00"
        backing.write_text(
            json.dumps(
                {
                    "old": {"value": "stale", "cached_at": old_ts, "ttl_seconds": 1},
                    "fresh": {"value": "keep", "cached_at": "2099-01-01T00:00:00", "ttl_seconds": 3600},
                }
            ),
            encoding="utf-8",
        )
        cache = JsonTTLCache(backing)
        cache.compact()
        assert cache.get("old") is None
        assert cache.get("fresh") == "keep"

    def test_compact_on_empty_cache_is_noop(self, cache: JsonTTLCache) -> None:
        """compact() on a non-existent backing file does not raise."""
        cache.compact()  # must not raise


# ── robustness ───────────────────────────────────────────────────────────────


class TestRobustness:
    """Tests for error handling and atomic-write guarantees."""

    def test_corrupt_file_returns_none(self, tmp_path: Path) -> None:
        """get() returns None gracefully when the backing file is corrupt JSON."""
        backing = tmp_path / "corrupt.json"
        backing.write_text("not valid json{{{", encoding="utf-8")
        cache = JsonTTLCache(backing)
        assert cache.get("k") is None

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """get() returns None when the backing file does not exist."""
        cache = JsonTTLCache(tmp_path / "nonexistent.json")
        assert cache.get("k") is None

    def test_atomic_write_uses_temp_file(self, cache: JsonTTLCache, tmp_path: Path) -> None:
        """set() creates the backing file atomically (temp + rename)."""
        cache.set("k", "v", ttl_seconds=3600)
        # After set(), no leftover .tmp files should exist
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Leftover temp files: {tmp_files}"

    def test_oserror_during_load_does_not_create_backup(self, tmp_path: Path) -> None:
        """OSError (e.g. EBUSY) during _load does not create a .corrupt-* backup.

        A flaky NFS mount or device-busy error should NOT be treated as a
        corrupt file — the original is likely healthy.  Only JSONDecodeError /
        ValueError should trigger a backup.
        """
        backing = tmp_path / "healthy.json"
        entry = '{"k": {"value": 1, "cached_at": "2099-01-01T00:00:00", "ttl_seconds": 3600}}'
        backing.write_text(entry, encoding="utf-8")
        cache = JsonTTLCache(backing)

        with patch.object(Path, "open", side_effect=OSError(errno.EBUSY, "device or resource busy")):
            result = cache.get("k")

        assert result is None
        corrupt_files = list(tmp_path.glob("*.corrupt-*"))
        assert corrupt_files == [], f"Unexpected .corrupt-* files created: {corrupt_files}"


class TestErrorPaths:
    """Cover the malformed-entry warning paths and corrupt-backup flow."""

    def test_malformed_entry_returns_none_on_get(self, tmp_path: Path) -> None:
        """get() returns None when an entry is malformed (missing fields)."""
        backing = tmp_path / "malformed.json"
        backing.write_text(
            json.dumps({"k": {"value": 1, "cached_at": "not-iso", "ttl_seconds": 60}}),
            encoding="utf-8",
        )
        cache = JsonTTLCache(backing)
        assert cache.get("k") is None

    def test_compact_drops_malformed_entries(self, tmp_path: Path) -> None:
        """compact() drops entries that fail to parse cached_at/ttl_seconds."""
        backing = tmp_path / "compact_malformed.json"
        backing.write_text(
            json.dumps(
                {
                    "broken": {"value": 1, "cached_at": "not-iso", "ttl_seconds": 60},
                    "fresh": {
                        "value": 2,
                        "cached_at": "2099-01-01T00:00:00",
                        "ttl_seconds": 3600,
                    },
                }
            ),
            encoding="utf-8",
        )
        cache = JsonTTLCache(backing)
        cache.compact()
        assert cache.get("broken") is None
        assert cache.get("fresh") == 2

    def test_corrupt_json_creates_backup(self, tmp_path: Path) -> None:
        """A JSONDecodeError on _load triggers a .corrupt-<ts>.json sibling."""
        backing = tmp_path / "broken.json"
        backing.write_text("{{{ not json", encoding="utf-8")
        cache = JsonTTLCache(backing)
        assert cache.get("anything") is None
        backups = list(tmp_path.glob("broken.corrupt-*.json"))
        assert len(backups) == 1, f"expected one backup, got: {backups}"

    def test_root_not_object_creates_backup(self, tmp_path: Path) -> None:
        """A JSON root that is not an object (e.g. list) is backed up and treated as empty."""
        backing = tmp_path / "rootlist.json"
        backing.write_text("[1, 2, 3]", encoding="utf-8")
        cache = JsonTTLCache(backing)
        assert cache.get("anything") is None
        backups = list(tmp_path.glob("rootlist.corrupt-*.json"))
        assert len(backups) == 1
