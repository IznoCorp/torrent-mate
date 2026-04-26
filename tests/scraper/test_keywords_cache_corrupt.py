"""Tests for KeywordsCache corrupt-file backup (I8 fix).

When ``_load`` encounters a parse error, the corrupt file must be renamed to
``tmdb_keywords_cache.corrupt-<unix_ts>.json`` before returning ``{}``.
This preserves data for forensic analysis and prevents the next ``set()``
from silently destroying all prior entries.
"""

from pathlib import Path

import pytest

from personalscraper.scraper.keywords_cache import KeywordsCache


@pytest.fixture()
def cache(tmp_path: Path) -> KeywordsCache:
    """A KeywordsCache backed by a temp data directory.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        KeywordsCache instance ready for use.
    """
    data_dir = tmp_path / ".data"
    data_dir.mkdir()
    return KeywordsCache(data_dir)


class TestCorruptFileBackup:
    """_load() backs up the corrupt file before returning {}."""

    def test_corrupt_file_is_backed_up_before_reset(self, cache: KeywordsCache) -> None:
        """Writing garbage to the cache file triggers a backup on the next read.

        Steps:
          1. Write valid data via ``set()``.
          2. Corrupt the backing file (write invalid JSON).
          3. Call ``get()`` — this triggers ``_load()`` which detects the parse
             error, backs up the corrupt file, and returns ``{}``.
          4. Assert: a ``*.corrupt-*.json`` sibling exists in the data directory.
          5. Assert: ``get()`` returns ``None`` (fresh empty cache, not the old data).
          6. Assert: a subsequent ``set()`` works and is readable (cache recovered).
        """
        # Step 1: write valid data.
        cache.set(42, "movie", ["action", "drama"])
        assert cache.get(42, "movie") == ["action", "drama"]

        # Step 2: corrupt the backing file.
        cache._path.write_text("{not valid json <<<", encoding="utf-8")

        # Step 3: trigger _load() via get().
        result = cache.get(42, "movie")

        # Step 4: a backup file must now exist in the data directory.
        data_dir = cache._path.parent
        corrupt_files = list(data_dir.glob("tmdb_keywords_cache.corrupt-*.json"))
        assert corrupt_files, (
            f"Expected a corrupt-backup file in {data_dir}, but none found. Files present: {list(data_dir.iterdir())}"
        )

        # Step 5: get() returns None because the cache is now empty.
        assert result is None

        # Step 6: the cache can be written to and read back after corruption.
        cache.set(99, "tv", ["sci-fi"])
        assert cache.get(99, "tv") == ["sci-fi"]

    def test_corrupt_backup_preserves_json_suffix(self, cache: KeywordsCache) -> None:
        """The backup file retains the ``.json`` suffix for easy identification."""
        cache._path.write_text("{{broken", encoding="utf-8")
        cache.get(1, "movie")  # triggers backup

        data_dir = cache._path.parent
        corrupt_files = list(data_dir.glob("tmdb_keywords_cache.corrupt-*.json"))
        assert corrupt_files, "No corrupt backup file found"
        for f in corrupt_files:
            assert f.suffix == ".json", f"Backup file missing .json suffix: {f.name}"

    def test_valid_file_does_not_create_backup(self, cache: KeywordsCache) -> None:
        """No backup file is created when the cache file is valid JSON."""
        cache.set(10, "movie", ["comedy"])
        cache.get(10, "movie")  # normal read, no error

        data_dir = cache._path.parent
        corrupt_files = list(data_dir.glob("tmdb_keywords_cache.corrupt-*.json"))
        assert not corrupt_files, f"Unexpected corrupt backup on valid read: {corrupt_files}"
