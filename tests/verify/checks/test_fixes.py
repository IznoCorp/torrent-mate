"""Unit tests for fix() methods on DirNaming, NoEmptyDirs, NtfsSafeNames."""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

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
