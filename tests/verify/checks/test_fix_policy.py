"""Pins the unified verify fix policy.

Verify now auto-fixes no_empty_dirs + ntfs_safe_names in the pipeline
(not just dir_naming).
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.verifier import Verifier


def _valid_movie(d: Path) -> None:
    """Create a minimal valid movie directory for fix-policy tests."""
    (d / "M.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "M"
    ET.SubElement(root, "year").text = "2020"
    for t, v in (("tmdb", "1"), ("imdb", "tt1")):
        u = ET.SubElement(root, "uniqueid")
        u.set("type", t)
        u.text = v
    ET.SubElement(root, "genre").text = "Drame"
    ET.ElementTree(root).write(d / "M.nfo", encoding="unicode")
    (d / "M-poster.jpg").write_bytes(b"\xff")
    (d / "M-landscape.jpg").write_bytes(b"\xff")


def test_verify_pipeline_fixes_empty_dirs(tmp_path, test_config):
    """Verify pipeline now auto-fixes no_empty_dirs (Phase 7 behavior)."""
    d = tmp_path / "M (2020)"
    d.mkdir()
    _valid_movie(d)
    (d / "Empty").mkdir()  # empty subdir → no_empty_dirs ERROR (fixable)
    v = Verifier(MagicMock(), PATTERNS, test_config, dry_run=False, fix=True)
    result = v.verify_movie(d)
    assert not (d / "Empty").exists()  # empty dir removed by verify now
    assert result.status in ("valid", "fixed")


def test_verify_pipeline_fixes_ntfs_names(tmp_path, test_config):
    """Verify pipeline now auto-fixes ntfs_safe_names (Phase 7 behavior)."""
    d = tmp_path / "M (2020)"
    d.mkdir()
    _valid_movie(d)
    (d / "bad:name.srt").write_bytes(b"1\n")  # NTFS-illegal → fixable
    v = Verifier(MagicMock(), PATTERNS, test_config, dry_run=False, fix=True)
    result = v.verify_movie(d)
    assert not (d / "bad:name.srt").exists()  # renamed by verify now
    assert result.status in ("valid", "fixed")
