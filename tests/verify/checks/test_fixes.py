"""Unit tests for fix() methods on DirNaming, NoEmptyDirs, NtfsSafeNames."""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checks.base import CheckContext, CheckStage


def _ctx(media_dir: Path, media_type: str = "movie", dry_run: bool = False) -> CheckContext:
    return CheckContext(
        media_dir=media_dir,
        media_type=media_type,
        stage=CheckStage.DISPATCH,
        config=MagicMock(),
        patterns=NamingPatterns(),
        dry_run=dry_run,
    )


def test_dir_naming_fix_renames_from_nfo(tmp_path):
    """DirNaming.fix() renames a movie directory using NFO title + year."""
    from personalscraper.verify.checks.naming import DirNaming

    d = tmp_path / "Bad Name"
    d.mkdir()
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Good Movie"
    ET.SubElement(root, "year").text = "2000"
    ET.ElementTree(root).write(d / "Good Movie.nfo", encoding="unicode")
    ctx = _ctx(d)
    actions = DirNaming().fix(ctx)
    assert len(actions) == 1
    assert actions[0].new_path == tmp_path / "Good Movie (2000)"
    assert (tmp_path / "Good Movie (2000)").exists()


def test_dir_naming_fix_dry_run_no_rename(tmp_path):
    """DirNaming.fix() in dry-run mode describes the rename but does not move."""
    from personalscraper.verify.checks.naming import DirNaming

    d = tmp_path / "Bad Name"
    d.mkdir()
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Good Movie"
    ET.SubElement(root, "year").text = "2000"
    ET.ElementTree(root).write(d / "Good Movie.nfo", encoding="unicode")
    ctx = _ctx(d, dry_run=True)
    actions = DirNaming().fix(ctx)
    assert len(actions) == 1
    assert not (tmp_path / "Good Movie (2000)").exists()  # dry run: no actual rename
    # Description now carries the [DRY-RUN] marker, matching the sibling fixes
    # (NoEmptyDirs / NtfsSafeNames) instead of the silent "Renamed …" wording.
    assert actions[0].description.startswith("[DRY-RUN] Would rename")
    assert "Good Movie (2000)" in actions[0].description


def test_dir_naming_fix_target_exists_no_rename(tmp_path):
    """DirNaming.fix() is a no-op when the canonical target dir already exists.

    Both the malformed source dir and the pre-existing collision target must be
    left untouched (no rename, no overwrite).
    """
    from personalscraper.verify.checks.naming import DirNaming

    d = tmp_path / "Bad Name"
    d.mkdir()
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Good Movie"
    ET.SubElement(root, "year").text = "2000"
    ET.ElementTree(root).write(d / "Good Movie.nfo", encoding="unicode")
    # Pre-existing sibling occupying the canonical target name.
    target = tmp_path / "Good Movie (2000)"
    target.mkdir()
    (target / "sentinel.txt").write_text("keep")

    ctx = _ctx(d)
    actions = DirNaming().fix(ctx)

    assert actions == []
    # Source dir untouched (not renamed away).
    assert d.is_dir()
    assert (d / "Good Movie.nfo").exists()
    # Pre-existing target untouched (not overwritten).
    assert target.is_dir()
    assert (target / "sentinel.txt").read_text() == "keep"


def test_no_empty_dirs_fix_removes_empty(tmp_path):
    """NoEmptyDirs.fix() removes empty subdirectories."""
    from personalscraper.verify.checks.structure import NoEmptyDirs

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    empty = d / "Extras"
    empty.mkdir()
    ctx = _ctx(d)
    actions = NoEmptyDirs().fix(ctx)
    assert not empty.exists()
    assert len(actions) >= 1


def test_ntfs_safe_names_fix_renames_illegal(tmp_path):
    """NtfsSafeNames.fix() renames files with NTFS-illegal characters."""
    from personalscraper.verify.checks.ntfs import NtfsSafeNames

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    bad = d / "file:bad.srt"
    bad.write_bytes(b"1\n")
    ctx = _ctx(d)
    actions = NtfsSafeNames().fix(ctx)
    assert not bad.exists()
    assert len(actions) == 1


# ---------------------------------------------------------------------------
# OSError / edge branches (migrated from the deleted helper tests in
# tests/verify/test_library_checks_fix.py::TestFixHelpers when the empty-dir and
# NTFS-name helpers were folded into the plugin fix() methods).
# ---------------------------------------------------------------------------


def test_no_empty_dirs_fix_dry_run_reports(tmp_path):
    """NoEmptyDirs.fix() in dry-run reports the empty subdir without removing it."""
    from personalscraper.verify.checks.structure import NoEmptyDirs

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    empty = d / "Subs"
    empty.mkdir()
    ctx = _ctx(d, dry_run=True)
    actions = NoEmptyDirs().fix(ctx)
    assert empty.exists()
    assert any("Would remove" in a.description for a in actions)


def test_no_empty_dirs_fix_rmdir_oserror(tmp_path):
    """NoEmptyDirs.fix() skips a subdir whose rmdir raises OSError, no crash."""
    from personalscraper.verify.checks.structure import NoEmptyDirs

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    empty = d / "Subs"
    empty.mkdir()
    ctx = _ctx(d)
    with patch.object(Path, "rmdir", side_effect=OSError("denied")):
        actions = NoEmptyDirs().fix(ctx)
    # The continue path means no action was appended for the failed rmdir.
    assert all("Removed" not in a.description for a in actions)


def test_no_empty_dirs_fix_rglob_oserror(tmp_path):
    """NoEmptyDirs.fix() catches an rglob OSError and returns an empty list."""
    from personalscraper.verify.checks.structure import NoEmptyDirs

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    ctx = _ctx(d)
    with patch.object(Path, "rglob", side_effect=OSError("scan failed")):
        actions = NoEmptyDirs().fix(ctx)
    assert actions == []


def test_ntfs_safe_names_fix_dry_run_reports(tmp_path):
    """NtfsSafeNames.fix() in dry-run reports the rename without performing it."""
    from personalscraper.verify.checks.ntfs import NtfsSafeNames

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    bad = d / "weird:file.mkv"
    bad.write_bytes(b"\x00")
    ctx = _ctx(d, dry_run=True)
    actions = NtfsSafeNames().fix(ctx)
    assert bad.exists()
    assert any("Would rename" in a.description for a in actions)
    # Dry-run FixActions carry no new_path.
    assert all(a.new_path is None for a in actions)


def test_ntfs_safe_names_fix_no_illegal_chars(tmp_path):
    """NtfsSafeNames.fix() yields no actions for files with safe names."""
    from personalscraper.verify.checks.ntfs import NtfsSafeNames

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    ok = d / "ok_file.mkv"
    ok.write_bytes(b"\x00")
    ctx = _ctx(d)
    actions = NtfsSafeNames().fix(ctx)
    assert actions == []
    assert ok.exists()


def test_ntfs_safe_names_fix_rename_oserror(tmp_path):
    """NtfsSafeNames.fix() skips a file whose rename raises OSError, no crash."""
    from personalscraper.verify.checks.ntfs import NtfsSafeNames

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    bad = d / "weird:file.mkv"
    bad.write_bytes(b"\x00")
    ctx = _ctx(d)
    with patch.object(Path, "rename", side_effect=OSError("rename denied")):
        actions = NtfsSafeNames().fix(ctx)
    assert all("Renamed" not in a.description for a in actions)


def test_ntfs_safe_names_fix_rglob_oserror(tmp_path):
    """NtfsSafeNames.fix() catches an rglob OSError and returns an empty list."""
    from personalscraper.verify.checks.ntfs import NtfsSafeNames

    d = tmp_path / "Movie (2020)"
    d.mkdir()
    ctx = _ctx(d)
    with patch.object(Path, "rglob", side_effect=OSError("scan failed")):
        actions = NtfsSafeNames().fix(ctx)
    assert actions == []
