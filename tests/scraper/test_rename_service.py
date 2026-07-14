"""Unit tests for ``personalscraper.scraper.rename_service``.

Covers ``_merge_dirs`` (recursive merge, file-replace, dir-replace, OSError),
``_rename_dir_case_safe`` (case-only rename, tmp-collision, OSError fallback),
``_cleanup_stale_files`` (no-op, unlink, OSError), and
``_cleanup_empty_release_dirs`` (skip-hidden/season, residual-files log,
rmtree failure).
"""

from __future__ import annotations

import errno
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.scraper.rename_service import (
    _cleanup_empty_release_dirs,
    _cleanup_stale_files,
    _merge_dirs,
    _rename_dir_case_safe,
)

# ── _merge_dirs ──────────────────────────────────────────────────────────────


class TestMergeDirs:
    """Cover the recursive merge, replace, and error paths of ``_merge_dirs``."""

    def test_recursive_merge_aggregates_counts(self, tmp_path: Path) -> None:
        """Recursive merge sums sub_moved/sub_failed from nested directories."""
        source = tmp_path / "src"
        target = tmp_path / "dst"
        (source / "Saison 01").mkdir(parents=True)
        (source / "Saison 01" / "ep01.mkv").write_bytes(b"x")
        (source / "Saison 01" / "ep02.mkv").write_bytes(b"y")
        (target / "Saison 01").mkdir(parents=True)

        moved, failed = _merge_dirs(source, target)

        assert moved == 2
        assert failed == 0
        assert (target / "Saison 01" / "ep01.mkv").exists()
        assert (target / "Saison 01" / "ep02.mkv").exists()
        # Source has been removed because it was fully emptied.
        assert not source.exists()

    def test_same_directory_is_never_merged(self, tmp_path: Path) -> None:
        """Merging a directory into ITSELF is a no-op — never a data-destroyer.

        Regression (prod incident, Flow → FLOW): on a case-insensitive filesystem
        the case-only rename target aliases the source, so the old merge walked
        the source, saw each dest as "already existing" (it WAS the source item),
        unlinked it — destroying the only copy of the video — then rmdir'd the
        emptied source. The samefile guard must make this a harmless no-op.
        """
        source = tmp_path / "Flow (2024)"
        source.mkdir()
        video = source / "Flow.2024.1080p.WEB.x264-PROOF.mkv"
        video.write_bytes(b"precious-bytes")

        moved, failed = _merge_dirs(source, source)

        assert (moved, failed) == (0, 0)
        assert source.exists()
        assert video.read_bytes() == b"precious-bytes"

    @pytest.mark.skipif(sys.platform != "darwin", reason="needs a case-insensitive filesystem")
    def test_case_alias_target_keeps_video(self, tmp_path: Path) -> None:
        """A case-only alias of the source ('FLOW (2024)') must not be merged into.

        Exact prod reproduction: only ``Flow (2024)`` exists on disk; the target
        path differs only by case and therefore aliases it on APFS. The guard
        detects samefile and skips — the video survives.
        """
        source = tmp_path / "Flow (2024)"
        source.mkdir()
        video = source / "Flow.2024.1080p.WEB.x264-PROOF.mkv"
        video.write_bytes(b"precious-bytes")
        alias = tmp_path / "FLOW (2024)"
        if not alias.exists():  # pragma: no cover — case-sensitive volume
            pytest.skip("filesystem is case-sensitive; alias scenario impossible")

        moved, failed = _merge_dirs(source, alias)

        assert (moved, failed) == (0, 0)
        assert video.read_bytes() == b"precious-bytes"

    def test_replace_existing_file(self, tmp_path: Path) -> None:
        """A file in target that already exists is unlinked then replaced."""
        source = tmp_path / "src"
        target = tmp_path / "dst"
        source.mkdir()
        target.mkdir()
        (source / "ep.mkv").write_bytes(b"new")
        (target / "ep.mkv").write_bytes(b"old")

        moved, failed = _merge_dirs(source, target)

        assert moved == 1
        assert failed == 0
        assert (target / "ep.mkv").read_bytes() == b"new"

    def test_replace_existing_directory_when_source_is_file(self, tmp_path: Path) -> None:
        """When source item is a file but dest is a directory, rmtree is invoked."""
        source = tmp_path / "src"
        target = tmp_path / "dst"
        source.mkdir()
        target.mkdir()
        (source / "name").write_bytes(b"file")
        (target / "name").mkdir()
        (target / "name" / "leftover.txt").write_text("x", encoding="utf-8")

        moved, failed = _merge_dirs(source, target)

        assert moved == 1
        assert failed == 0
        assert (target / "name").is_file()

    def test_oserror_during_move_increments_failed_count(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """An OSError on shutil.move increments ``failed`` and logs ``merge_item_failed``."""
        source = tmp_path / "src"
        target = tmp_path / "dst"
        source.mkdir()
        target.mkdir()
        (source / "boom.mkv").write_bytes(b"x")

        with patch(
            "personalscraper.scraper.rename_service._FOLDER_PATTERN",
            new=None,  # placeholder; not relevant here
        ):
            pass  # keep the patch above out of the way; real patch below.

        with patch("shutil.move", side_effect=OSError(errno.EACCES, "denied")):
            with caplog.at_level("WARNING"):
                moved, failed = _merge_dirs(source, target)

        assert moved == 0
        assert failed == 1
        assert "merge_item_failed" in caplog.text
        assert "merge_partial" in caplog.text

    def test_rmdir_failure_logged_and_swallowed(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """If rmdir of an empty source fails, the warning is logged but no exception escapes."""
        source = tmp_path / "src"
        target = tmp_path / "dst"
        source.mkdir()
        target.mkdir()
        (source / "ep.mkv").write_bytes(b"x")

        original_rmdir = Path.rmdir

        def flaky_rmdir(self: Path) -> None:
            if self == source:
                raise OSError(errno.EACCES, "rmdir denied")
            original_rmdir(self)

        with patch.object(Path, "rmdir", flaky_rmdir):
            with caplog.at_level("WARNING"):
                _merge_dirs(source, target)

        assert "merge_source_rmdir_failed" in caplog.text


# ── _rename_dir_case_safe ────────────────────────────────────────────────────


class TestRenameDirCaseSafe:
    """Cover the case-only rename + tmp-collision + OSError branches."""

    def test_case_rename_with_tmp_collision(self, tmp_path: Path) -> None:
        """When the first ``.case-rename-tmp`` exists, fallback suffix is appended."""
        source = tmp_path / "Show"
        source.mkdir()
        # Pre-create the first tmp so the loop has to bump the suffix.
        (tmp_path / "Show.case-rename-tmp").mkdir()

        # Simulate a case-insensitive filesystem: target exists and reports samefile().
        target = tmp_path / "show"

        with patch.object(Path, "exists", autospec=True) as mock_exists:
            # exists() truth table:
            # - target.exists() → True (case-insensitive FS)
            # - first tmp .exists() → True (collision)
            # - second tmp .exists() → False (free slot)
            calls = {"n": 0}

            def fake_exists(self: Path) -> bool:
                calls["n"] += 1
                # Map: target → True, .case-rename-tmp → True, .case-rename-tmp-1 → False
                if self == target:
                    return True
                if self.name == "Show.case-rename-tmp":
                    return True
                if self.name == "Show.case-rename-tmp-1":
                    return False
                # Defaults — fallback to actual check for unrelated paths.
                return source.is_dir() if self == source else False

            mock_exists.side_effect = fake_exists

            with patch.object(Path, "samefile", return_value=True):
                with patch.object(Path, "rename") as mock_rename:
                    result = _rename_dir_case_safe(source, target)

        assert result == target
        assert mock_rename.call_count == 2  # source→tmp, tmp→target

    def test_case_rename_oserror_falls_through_to_simple_rename(self, tmp_path: Path) -> None:
        """If samefile() raises OSError, the function falls through to a plain rename."""
        source = tmp_path / "src"
        source.mkdir()
        target = tmp_path / "dst"
        target.mkdir()
        # Remove target so plain rename can work after the OSError fallback.
        target.rmdir()
        # Recreate target as a marker that exists() returns True.
        target.mkdir()
        # Now empty target so rename can succeed.
        target.rmdir()

        # Make exists() report True for target so the if-branch is entered;
        # samefile() raises OSError → pass; the trailing source.rename(target) executes.
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "samefile", side_effect=OSError("samefile failed")):
                result = _rename_dir_case_safe(source, target)

        assert result == target
        assert target.exists()
        assert not source.exists()


# ── _cleanup_stale_files ─────────────────────────────────────────────────────


class TestCleanupStaleFiles:
    """Cover the no-op short-circuit + unlink + OSError branches."""

    def test_no_op_when_old_equals_new(self, tmp_path: Path) -> None:
        """Identical prefixes short-circuit and return 0 without scanning."""
        (tmp_path / "Title 2024-fanart.jpg").write_bytes(b"x")
        removed = _cleanup_stale_files(tmp_path, old_prefix="Title 2024", new_prefix="Title 2024")
        assert removed == 0
        # File is untouched.
        assert (tmp_path / "Title 2024-fanart.jpg").exists()

    def test_removes_stale_when_sanitized_exists(self, tmp_path: Path) -> None:
        """A stale file with the old prefix is unlinked when its sanitized sibling exists."""
        (tmp_path / "Title : Subtitle-fanart.jpg").write_bytes(b"old")
        (tmp_path / "Title Subtitle-fanart.jpg").write_bytes(b"new")
        removed = _cleanup_stale_files(
            tmp_path,
            old_prefix="Title : Subtitle",
            new_prefix="Title Subtitle",
        )
        assert removed == 1
        assert not (tmp_path / "Title : Subtitle-fanart.jpg").exists()
        assert (tmp_path / "Title Subtitle-fanart.jpg").exists()

    def test_unlink_oserror_logged_and_swallowed(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """An OSError on the unlink call logs a warning and is counted as not-removed."""
        stale = tmp_path / "Title : Sub-fanart.jpg"
        new = tmp_path / "Title Sub-fanart.jpg"
        stale.write_bytes(b"x")
        new.write_bytes(b"y")

        with patch.object(Path, "unlink", side_effect=OSError(errno.EACCES, "denied")):
            with caplog.at_level("WARNING"):
                removed = _cleanup_stale_files(
                    tmp_path,
                    old_prefix="Title : Sub",
                    new_prefix="Title Sub",
                )

        assert removed == 0
        assert "stale_file_remove_failed" in caplog.text


# ── _cleanup_empty_release_dirs ──────────────────────────────────────────────


class TestCleanupEmptyReleaseDirs:
    """Cover the skip-hidden/season, residual-files log, and rmtree-failure branches."""

    def test_skip_hidden_and_season_dirs(self, tmp_path: Path) -> None:
        """Hidden ``.actors`` and ``Saison XX`` directories are never removed."""
        (tmp_path / ".actors").mkdir()
        (tmp_path / "Saison 01").mkdir()
        (tmp_path / "release-group").mkdir()  # empty, removable

        removed = _cleanup_empty_release_dirs(tmp_path)

        assert removed == 1
        assert (tmp_path / ".actors").exists()
        assert (tmp_path / "Saison 01").exists()
        assert not (tmp_path / "release-group").exists()

    def test_keeps_dir_with_video_files(self, tmp_path: Path) -> None:
        """Directories that still have video files are preserved."""
        sub = tmp_path / "Show.S01E01.1080p.WEB-GROUP"
        sub.mkdir()
        (sub / "ep.mkv").write_bytes(b"x")

        removed = _cleanup_empty_release_dirs(tmp_path)

        assert removed == 0
        assert sub.exists()

    def test_logs_residual_non_video_files(self, tmp_path: Path) -> None:
        """A subdir with only NFOs / images logs ``release_dir_residual_files`` before removal."""
        sub = tmp_path / "Show.S01E01-GROUP"
        sub.mkdir()
        (sub / "info.nfo").write_text("x", encoding="utf-8")

        with patch("personalscraper.scraper.rename_service.log") as mock_log:
            removed = _cleanup_empty_release_dirs(tmp_path)

        assert removed == 1
        # The residual-files warning was emitted with the file list.
        residual_calls = [c for c in mock_log.warning.call_args_list if c.args[0] == "release_dir_residual_files"]
        assert residual_calls, "expected release_dir_residual_files warning"

    def test_rmtree_failure_logged_and_continues(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """An OSError on shutil.rmtree logs a warning and does not raise."""
        sub = tmp_path / "release-group"
        sub.mkdir()

        with patch("shutil.rmtree", side_effect=OSError(errno.EACCES, "denied")):
            with caplog.at_level("WARNING"):
                removed = _cleanup_empty_release_dirs(tmp_path)

        assert removed == 0
        assert "release_dir_remove_failed" in caplog.text

    def test_skip_non_dir_entries(self, tmp_path: Path) -> None:
        """Files at the top level are skipped (only directories are inspected)."""
        (tmp_path / "stray.txt").write_text("x", encoding="utf-8")
        sub = tmp_path / "release-group"
        sub.mkdir()

        removed = _cleanup_empty_release_dirs(tmp_path)

        assert removed == 1
        assert (tmp_path / "stray.txt").exists()


class TestCleanupReleaseDirsArchiveAndSample:
    """DEV #1 / review COV-2: sample-only dirs removed, archive dirs retained."""

    def test_removes_sample_only_release_dir(self, tmp_path: Path) -> None:
        """A release dir whose only video is a sample clip is removed."""
        sub = tmp_path / "Show.S01E01.1080p.WEB-GROUP"
        (sub / "Sample").mkdir(parents=True)
        (sub / "Sample" / "show.s01e01-sample.mkv").write_bytes(b"x")

        removed = _cleanup_empty_release_dirs(tmp_path)

        assert removed == 1
        assert not sub.exists()

    def test_retains_archive_bearing_release_dir(self, tmp_path: Path) -> None:
        """A release dir still holding un-extracted archives is preserved (no data loss)."""
        sub = tmp_path / "Show.S01E01.1080p.WEB-GROUP"
        sub.mkdir()
        (sub / "release.rar").write_bytes(b"RAR")
        (sub / "release.r00").write_bytes(b"VOL")

        removed = _cleanup_empty_release_dirs(tmp_path)

        assert removed == 0
        assert sub.exists()
        assert (sub / "release.rar").exists()
