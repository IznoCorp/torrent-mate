"""Resilience tests: idempotence (double-run) and orphan cleanup.

All tests use real filesystem operations. API calls are mocked.
"""


from personalscraper.process.reclean import reclean_folders
from personalscraper.sorter.run import run_sort


class TestSortDoubleRun:
    """Test 6: Sort is idempotent — second run skips everything."""

    def test_sort_double_run_idempotent(self, staging, resilience_settings):
        """Second sort run skips all items (nothing left in 097-TEMP)."""
        temp = staging / "097-TEMP"
        movies = staging / "001-MOVIES"

        # Create item to sort
        item = temp / "Movie.Title.2024.1080p"
        item.mkdir()
        (item / "movie.mkv").write_text("video")

        # First sort
        report1 = run_sort(resilience_settings)
        assert report1.success_count >= 1

        # Second sort — 097-TEMP should be empty
        report2 = run_sort(resilience_settings)
        assert report2.success_count == 0
        assert report2.error_count == 0


class TestCleanDoubleRun:
    """Test 10: Clean is idempotent — second run skips clean folders."""

    def test_reclean_double_run_idempotent(self, staging):
        """Second reclean skips all folders (already clean)."""
        movies = staging / "001-MOVIES"
        polluted = movies / "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted.mkdir()
        (polluted / "movie.mkv").write_text("video")

        # First clean
        report1 = reclean_folders(movies)
        assert report1.success_count >= 1

        # Second clean — all folders should be clean
        report2 = reclean_folders(movies)
        assert report2.success_count == 0
        assert report2.skip_count >= 1


class TestMergePartialRecovery:
    """Test 4: Merge partial — source + target both exist after crash."""

    def test_partial_merge_retried(self, staging):
        """Source + target coexist (incomplete merge) → reclean re-merges."""
        movies = staging / "001-MOVIES"

        # Simulate partial merge: both source (polluted) and target exist
        polluted = movies / "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted.mkdir()
        (polluted / "extra.txt").write_text("leftover")

        target = movies / "Movie Title (2024)"
        target.mkdir()
        (target / "movie.mkv").write_text("video")
        (target / "movie.nfo").write_text("nfo")

        # Reclean should merge polluted into target
        report = reclean_folders(movies)
        assert report.success_count >= 1
        assert not polluted.exists()
        assert target.exists()
        assert (target / "extra.txt").exists()  # Merged from polluted
        assert (target / "movie.mkv").exists()  # Original preserved


class TestDispatchOrphanCleanup:
    """Test 5: Orphaned _tmp_dispatch_* cleaned at dispatch start."""

    def test_tmp_dispatch_orphan_cleaned(self, staging, resilience_settings):
        """_tmp_dispatch_* dirs are cleaned before dispatch runs."""
        from personalscraper.dispatch.run import _cleanup_staging_orphans

        movies = staging / "001-MOVIES"
        orphan = movies / "_tmp_dispatch_SomeMovie"
        orphan.mkdir()
        (orphan / "file.mkv").write_text("data")

        cleaned = _cleanup_staging_orphans(resilience_settings)

        assert cleaned >= 1
        assert not orphan.exists()

    def test_merge_backup_orphan_cleaned(self, staging, resilience_settings):
        """merge_backup/ inside a media dir is cleaned."""
        from personalscraper.dispatch.run import _cleanup_staging_orphans

        movies = staging / "001-MOVIES"
        movie = movies / "Some Movie (2024)"
        movie.mkdir()
        backup = movie / ".merge_backup"
        backup.mkdir()
        (backup / "old_file.mkv").write_text("backup")

        cleaned = _cleanup_staging_orphans(resilience_settings)

        assert cleaned >= 1
        assert not backup.exists()
        assert movie.exists()  # Movie dir itself preserved
