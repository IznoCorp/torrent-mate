"""Tests for the golden file loader and matcher.

Tests load_golden_file, match_torrent_to_golden, and discover_golden_files
using temporary golden file fixtures.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.e2e.golden import (
    _normalize_torrent_name,
    discover_golden_files,
    load_golden_file,
    match_torrent_to_golden,
)

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalizeTorrentName:
    """Tests for _normalize_torrent_name."""

    def test_strip_release_group(self) -> None:
        """Should strip [LaCale] and similar tags."""
        result = _normalize_torrent_name("[LaCale]-Jumanji.1995.MULTi.VF2.1080p.BluRay.HDLight.DD5.1.x264-PopHD")
        assert "lacale" not in result
        assert "pophd" not in result
        assert "jumanji" in result
        assert "1995" in result

    def test_strip_codec_resolution(self) -> None:
        """Should strip codec and resolution info."""
        result = _normalize_torrent_name("Movie.2024.1080p.WEBRip.x265.HEVC.AAC.5.1-Group")
        assert "1080p" not in result
        assert "x265" not in result
        assert "hevc" not in result

    def test_dots_to_spaces(self) -> None:
        """Should convert dots to spaces."""
        result = _normalize_torrent_name("Some.Movie.2024")
        assert "some movie 2024" == result

    def test_malcolm_torrent(self) -> None:
        """Should normalize Malcolm torrent name."""
        result = _normalize_torrent_name(
            "[LaCale]-Malcolm In The Middle S01 Multi VFI NOST 1080p WEBRip NF x265 HEVC AAC 5.1-Papaya"
        )
        assert "malcolm" in result
        assert "middle" in result
        assert "s01" in result


# ---------------------------------------------------------------------------
# Load golden file
# ---------------------------------------------------------------------------


class TestLoadGoldenFile:
    """Tests for load_golden_file."""

    def test_load_complete(self, tmp_path: Path) -> None:
        """Should load all 4 JSON files."""
        slug = "test_movie_2024"
        golden_dir = tmp_path / slug
        golden_dir.mkdir()

        nfo_data = {"title": "Test", "year": 2024}
        artwork_data = {"required": ["poster.jpg"]}
        structure_data = {"required_files": ["*.mkv"]}
        dispatch_data = {"action": "moved"}

        (golden_dir / "expected_nfo.json").write_text(json.dumps(nfo_data))
        (golden_dir / "expected_artwork.json").write_text(json.dumps(artwork_data))
        (golden_dir / "expected_structure.json").write_text(json.dumps(structure_data))
        (golden_dir / "expected_dispatch.json").write_text(json.dumps(dispatch_data))

        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path):
            gf = load_golden_file(slug)

        assert gf.name == slug
        assert gf.nfo == nfo_data
        assert gf.artwork == artwork_data
        assert gf.structure == structure_data
        assert gf.dispatch == dispatch_data

    def test_load_partial(self, tmp_path: Path) -> None:
        """Should load with missing JSON files (empty dicts)."""
        slug = "partial"
        golden_dir = tmp_path / slug
        golden_dir.mkdir()

        nfo_data = {"title": "Partial"}
        (golden_dir / "expected_nfo.json").write_text(json.dumps(nfo_data))

        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path):
            gf = load_golden_file(slug)

        assert gf.nfo == nfo_data
        assert gf.artwork == {}
        assert gf.structure == {}
        assert gf.dispatch == {}

    def test_load_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing directory."""
        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path):
            with pytest.raises(FileNotFoundError):
                load_golden_file("nonexistent")


# ---------------------------------------------------------------------------
# Match torrent to golden
# ---------------------------------------------------------------------------


class TestMatchTorrentToGolden:
    """Tests for match_torrent_to_golden."""

    def test_match_jumanji(self, tmp_path: Path) -> None:
        """Should match Jumanji torrent name to jumanji_1995 slug."""
        slug = "jumanji_1995"
        golden_dir = tmp_path / slug
        golden_dir.mkdir()
        (golden_dir / "expected_nfo.json").write_text(json.dumps({"title": "Jumanji"}))

        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path):
            gf = match_torrent_to_golden(
                "[LaCale]-Jumanji.1995.MULTi.VF2.1080p.BluRay.HDLight.DD5.1.x264-PopHD"
            )

        assert gf is not None
        assert gf.name == slug

    def test_match_malcolm(self, tmp_path: Path) -> None:
        """Should match Malcolm torrent name to malcolm_in_the_middle_s01 slug."""
        slug = "malcolm_in_the_middle_s01"
        golden_dir = tmp_path / slug
        golden_dir.mkdir()
        (golden_dir / "expected_nfo.json").write_text(json.dumps({"title": "Malcolm"}))

        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path):
            gf = match_torrent_to_golden(
                "[LaCale]-Malcolm In The Middle S01 Multi VFI NOST 1080p WEBRip NF x265 HEVC AAC 5.1-Papaya"
            )

        assert gf is not None
        assert gf.name == slug

    def test_match_unknown(self, tmp_path: Path) -> None:
        """Should return None for unknown torrent."""
        slug = "jumanji_1995"
        golden_dir = tmp_path / slug
        golden_dir.mkdir()
        (golden_dir / "expected_nfo.json").write_text(json.dumps({"title": "Jumanji"}))

        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path):
            gf = match_torrent_to_golden("Completely.Different.Movie.2024.720p")

        assert gf is None

    def test_match_no_expected_dir(self, tmp_path: Path) -> None:
        """Should return None when expected dir doesn't exist."""
        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path / "nonexistent"):
            gf = match_torrent_to_golden("Anything")

        assert gf is None


# ---------------------------------------------------------------------------
# Discover golden files
# ---------------------------------------------------------------------------


class TestDiscoverGoldenFiles:
    """Tests for discover_golden_files."""

    def test_discover_multiple(self, tmp_path: Path) -> None:
        """Should discover all golden file directories."""
        for slug in ["movie_a", "movie_b"]:
            d = tmp_path / slug
            d.mkdir()
            (d / "expected_nfo.json").write_text(json.dumps({"title": slug}))

        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path):
            golden_files = discover_golden_files()

        assert len(golden_files) == 2
        names = {gf.name for gf in golden_files}
        assert names == {"movie_a", "movie_b"}

    def test_discover_empty(self, tmp_path: Path) -> None:
        """Should return empty list when no golden files exist."""
        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path):
            golden_files = discover_golden_files()

        assert golden_files == []

    def test_discover_nonexistent_dir(self, tmp_path: Path) -> None:
        """Should return empty list when expected dir doesn't exist."""
        with patch("tests.e2e.golden.EXPECTED_DIR", tmp_path / "nonexistent"):
            golden_files = discover_golden_files()

        assert golden_files == []
