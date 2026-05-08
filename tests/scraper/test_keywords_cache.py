"""Tests for the TMDB keywords cache.

Covers: cache hit within TTL, cache miss (unknown key), cache expiry (>30 days),
concurrent write safety (two sets in quick succession), and atomic write
(no temp files left on disk).
"""

import errno
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.scraper.keywords_cache import KeywordsCache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cache(tmp_path: Path) -> KeywordsCache:
    """Create a KeywordsCache backed by a temp directory.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        KeywordsCache instance ready for use.
    """
    data_dir = tmp_path / ".data"
    data_dir.mkdir()
    return KeywordsCache(data_dir)


# ---------------------------------------------------------------------------
# Cache miss
# ---------------------------------------------------------------------------


class TestCacheMiss:
    """Returns None for unknown keys."""

    def test_miss_unknown_id(self, cache: KeywordsCache) -> None:
        """get() returns None when the key has never been written."""
        result = cache.get(999, "movie")
        assert result is None

    def test_miss_unknown_tv_id(self, cache: KeywordsCache) -> None:
        """get() returns None for an unknown TV id."""
        result = cache.get(42, "tv")
        assert result is None

    def test_miss_wrong_media_type(self, cache: KeywordsCache) -> None:
        """Writing under movie key does not create a tv key."""
        cache.set(100, "movie", ["action"])
        result = cache.get(100, "tv")
        assert result is None


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------


class TestCacheHit:
    """Returns the stored list when the entry is fresh."""

    def test_hit_returns_keywords(self, cache: KeywordsCache) -> None:
        """get() returns the exact list written by set()."""
        keywords = ["stand-up-comedy", "one-man-show"]
        cache.set(123, "movie", keywords)
        result = cache.get(123, "movie")
        assert result == keywords

    def test_hit_tv(self, cache: KeywordsCache) -> None:
        """Hit works for media_type='tv'."""
        cache.set(456, "tv", ["anime", "based-on-manga"])
        result = cache.get(456, "tv")
        assert result == ["anime", "based-on-manga"]

    def test_hit_empty_list(self, cache: KeywordsCache) -> None:
        """An empty keyword list (e.g. 404 result) is a valid cache entry."""
        cache.set(789, "movie", [])
        result = cache.get(789, "movie")
        assert result == []

    def test_hit_does_not_mutate(self, cache: KeywordsCache) -> None:
        """Modifying the returned list does not corrupt the cache."""
        cache.set(11, "movie", ["kw1", "kw2"])
        first = cache.get(11, "movie")
        assert first is not None
        first.append("mutated")
        second = cache.get(11, "movie")
        assert second == ["kw1", "kw2"]


# ---------------------------------------------------------------------------
# Cache expiry
# ---------------------------------------------------------------------------


class TestCacheExpiry:
    """Expired entries (> 30 days) are treated as misses."""

    def _write_entry_with_age(self, cache: KeywordsCache, tmdb_id: int, media_type: str, days: int) -> None:
        """Write a cache entry with a back-dated cached_at timestamp.

        Args:
            cache: Cache instance to write into.
            tmdb_id: TMDB numeric identifier.
            media_type: "movie" or "tv".
            days: How many days ago to date the entry.
        """
        old_time = datetime.now() - timedelta(days=days)
        data = {f"{media_type}_{tmdb_id}": {"keywords": ["stale"], "cached_at": old_time.isoformat()}}
        cache._path.write_text(json.dumps(data), encoding="utf-8")

    def test_expired_entry_returns_none(self, cache: KeywordsCache) -> None:
        """Entry older than 30 days is a cache miss."""
        self._write_entry_with_age(cache, 1, "movie", days=31)
        result = cache.get(1, "movie")
        assert result is None

    def test_exactly_30_days_is_expired(self, cache: KeywordsCache) -> None:
        """Entry at exactly 30 days is considered expired (> 30 days boundary is exclusive)."""
        # 30 days + 1 second → expired
        old_time = datetime.now() - timedelta(days=30, seconds=1)
        data = {"movie_2": {"keywords": ["kw"], "cached_at": old_time.isoformat()}}
        cache._path.write_text(json.dumps(data), encoding="utf-8")
        result = cache.get(2, "movie")
        assert result is None

    def test_fresh_entry_not_expired(self, cache: KeywordsCache) -> None:
        """Entry at 29 days is still valid."""
        self._write_entry_with_age(cache, 3, "tv", days=29)
        result = cache.get(3, "tv")
        assert result is not None
        assert result == ["stale"]

    def test_expired_entry_replaced_after_set(self, cache: KeywordsCache) -> None:
        """After an expired entry is refreshed with set(), get() returns new data."""
        self._write_entry_with_age(cache, 4, "movie", days=31)
        assert cache.get(4, "movie") is None  # expired
        cache.set(4, "movie", ["new-kw"])
        assert cache.get(4, "movie") == ["new-kw"]


# ---------------------------------------------------------------------------
# Corrupt / invalid entries
# ---------------------------------------------------------------------------


class TestCorruptEntries:
    """Graceful handling of malformed cache data."""

    def test_invalid_cached_at_returns_none(self, cache: KeywordsCache) -> None:
        """Entry with unparseable cached_at is treated as a miss."""
        data = {"movie_5": {"keywords": ["kw"], "cached_at": "not-a-date"}}
        cache._path.write_text(json.dumps(data), encoding="utf-8")
        result = cache.get(5, "movie")
        assert result is None

    def test_corrupt_json_returns_none(self, cache: KeywordsCache) -> None:
        """Truncated / invalid JSON returns None (fresh start, no crash)."""
        cache._path.write_text("{corrupt", encoding="utf-8")
        result = cache.get(1, "movie")
        assert result is None


# ---------------------------------------------------------------------------
# Concurrent write safety
# ---------------------------------------------------------------------------


class TestConcurrentWrites:
    """Two successive set() calls do not lose data."""

    def test_two_writes_both_readable(self, cache: KeywordsCache) -> None:
        """Two set() calls in quick succession preserve both entries."""
        cache.set(10, "movie", ["action", "adventure"])
        cache.set(20, "tv", ["sci-fi"])
        assert cache.get(10, "movie") == ["action", "adventure"]
        assert cache.get(20, "tv") == ["sci-fi"]

    def test_overwrite_updates_entry(self, cache: KeywordsCache) -> None:
        """A second set() for the same key replaces the previous value."""
        cache.set(30, "movie", ["old"])
        cache.set(30, "movie", ["new"])
        assert cache.get(30, "movie") == ["new"]


# ---------------------------------------------------------------------------
# Atomic write — no temp files left on disk
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """os.replace ensures no temp file survives after set()."""

    def test_no_tmp_files_after_set(self, cache: KeywordsCache) -> None:
        """No ``.tmp`` files remain in data_dir after a successful write."""
        data_dir = cache._path.parent
        cache.set(50, "movie", ["kw1"])
        tmp_files = list(data_dir.glob("*.tmp"))
        assert tmp_files == [], f"Leftover temp files: {tmp_files}"

    def test_backing_file_created(self, cache: KeywordsCache) -> None:
        """The backing JSON file exists after the first set()."""
        assert not cache._path.exists()
        cache.set(60, "tv", ["drama"])
        assert cache._path.exists()

    def test_backing_file_is_valid_json(self, cache: KeywordsCache) -> None:
        """The backing file contains valid, parseable JSON after set()."""
        cache.set(70, "movie", ["comedy"])
        raw = json.loads(cache._path.read_text(encoding="utf-8"))
        assert "movie_70" in raw
        assert raw["movie_70"]["keywords"] == ["comedy"]

    def test_data_dir_created_if_missing(self, tmp_path: Path) -> None:
        """KeywordsCache creates data_dir automatically on first write."""
        data_dir = tmp_path / "nested" / ".data"
        assert not data_dir.exists()
        cache = KeywordsCache(data_dir)
        cache.set(80, "movie", ["thriller"])
        assert cache._path.exists()
        assert cache.get(80, "movie") == ["thriller"]


# ---------------------------------------------------------------------------
# Naive cached_at backward-compatibility
# ---------------------------------------------------------------------------


class TestNaiveCachedAt:
    """check_ttl() promotes naive cached_at to UTC — still-fresh entries hit."""

    def test_naive_cached_at_still_valid(self, cache: KeywordsCache) -> None:
        """Naive cached_at (no tzinfo) from older cache versions hits within TTL.

        Writes a raw cache entry with a naive ISO timestamp (no tz offset) dated
        1 day ago — far inside the 30-day TTL — and asserts get() returns the
        keywords rather than treating it as a miss.
        """
        one_day_ago = datetime.now() - timedelta(days=1)  # naive, no tzinfo
        data = {"movie_91": {"keywords": ["retro"], "cached_at": one_day_ago.isoformat()}}
        cache._path.write_text(json.dumps(data), encoding="utf-8")
        result = cache.get(91, "movie")
        assert result == ["retro"]


# ---------------------------------------------------------------------------
# OSError hygiene — no .corrupt-* backup on transient I/O errors
# ---------------------------------------------------------------------------


class TestOSErrorHygiene:
    """OSError during _load must NOT create a .corrupt-* backup file."""

    def test_oserror_during_load_does_not_create_backup(self, tmp_path: Path) -> None:
        """EBUSY / transient NFS error during _load does not create a .corrupt-* file.

        A flaky mount or device-busy condition should NOT be treated as a
        corrupt file — the original is likely healthy.  Only JSONDecodeError /
        ValueError should trigger a backup.
        """
        data_dir = tmp_path / ".data"
        data_dir.mkdir()
        cache = KeywordsCache(data_dir)

        # Write a valid entry first so the file exists.
        cache.set(101, "movie", ["action"])

        with patch.object(Path, "open", side_effect=OSError(errno.EBUSY, "device or resource busy")):
            result = cache.get(101, "movie")

        assert result is None
        corrupt_files = list(data_dir.glob("*.corrupt-*"))
        assert corrupt_files == [], f"Unexpected .corrupt-* files created: {corrupt_files}"


# ---------------------------------------------------------------------------
# Extra coverage — non-list keywords, root-not-object, copy failure, save fail
# ---------------------------------------------------------------------------


class TestNonListKeywords:
    """Cover the ``keywords`` field type-guard (line 129)."""

    def test_non_list_keywords_returns_empty(self, cache: KeywordsCache) -> None:
        """A cache entry whose ``keywords`` is not a list returns ``[]`` (defensive)."""
        from datetime import datetime as _dt

        from personalscraper.scraper.json_ttl_cache import UTC as _UTC

        now_iso = _dt.now(_UTC).isoformat()
        # Write a JSON file directly with a malformed keywords field (string instead of list).
        data = {"movie_555": {"keywords": "not-a-list", "cached_at": now_iso}}
        cache._path.write_text(json.dumps(data), encoding="utf-8")

        result = cache.get(555, "movie")
        assert result == []


class TestRootNotObjectBackup:
    """Cover the root-not-object backup branch (lines 212-213)."""

    def test_root_list_creates_backup(self, cache: KeywordsCache) -> None:
        """A JSON root that is a list (not a dict) is backed up and treated as empty."""
        cache._path.write_text("[1, 2, 3]", encoding="utf-8")
        result = cache.get(1, "movie")
        assert result is None
        backups = list(cache._path.parent.glob("tmdb_keywords_cache.corrupt-*.json"))
        assert len(backups) == 1


class TestCorruptBackupCopyFailure:
    """Cover the OSError branch of ``_backup_corrupt`` (lines 182-183)."""

    def test_corrupt_backup_copy_failure_logged(self, cache: KeywordsCache, caplog: pytest.LogCaptureFixture) -> None:
        """If shutil.copy fails when backing up corrupt JSON, the error is logged."""
        cache._path.write_text("{not json", encoding="utf-8")

        with patch(
            "personalscraper.scraper.keywords_cache.shutil.copy",
            side_effect=OSError(errno.EACCES, "denied"),
        ):
            with caplog.at_level("ERROR"):
                result = cache.get(1, "movie")

        assert result is None
        assert "keywords_cache_corrupt_backup_failed" in caplog.text


class TestAtomicSaveErrors:
    """Cover the atomic-save error path (lines 260-266)."""

    def test_atomic_save_oserror_cleans_temp_and_reraises(self, cache: KeywordsCache) -> None:
        """When os.replace raises, the temp file is unlinked and the OSError propagates."""
        import os as _os

        with patch.object(_os, "replace", side_effect=OSError(errno.EIO, "i/o error")):
            with pytest.raises(OSError, match="i/o error"):
                cache.set(1, "movie", ["kw"])

        leftover = list(cache._path.parent.glob("*.tmp"))
        assert leftover == [], f"leftover temp files: {leftover}"

    def test_atomic_save_oserror_with_unlink_failure(self, cache: KeywordsCache) -> None:
        """If unlink also fails after os.replace failure, original OSError still propagates."""
        import os as _os

        original_unlink = _os.unlink

        def flaky_unlink(path: str) -> None:
            if path.endswith(".tmp"):
                raise OSError(errno.EIO, "unlink failed")
            original_unlink(path)

        with patch.object(_os, "replace", side_effect=OSError(errno.EIO, "replace failed")):
            with patch.object(_os, "unlink", flaky_unlink):
                with pytest.raises(OSError, match="replace failed"):
                    cache.set(1, "movie", ["kw"])
