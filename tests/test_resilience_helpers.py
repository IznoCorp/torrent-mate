"""Tests for V10 resilience helper functions — NFO validation and fast-skip."""

import xml.etree.ElementTree as ET

from personalscraper.process.reclean import _has_polluted_folders
from personalscraper.scraper.scraper import _is_nfo_complete
from personalscraper.sorter.run import _has_unsorted_items

# ── _is_nfo_complete ──────────────────────────────────


class TestIsNfoComplete:
    """Tests for NFO validation — parsable XML + uniqueid."""

    def test_valid_nfo(self, tmp_path):
        """NFO with valid XML and uniqueid returns True."""
        nfo = tmp_path / "movie.nfo"
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Test"
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tmdb")
        uid.text = "12345"
        ET.ElementTree(root).write(nfo, encoding="unicode")

        assert _is_nfo_complete(nfo) is True

    def test_truncated_nfo(self, tmp_path):
        """Truncated XML (not parsable) returns False."""
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("<movie><title>Test</tit")  # Truncated

        assert _is_nfo_complete(nfo) is False

    def test_nfo_without_uniqueid(self, tmp_path):
        """Valid XML without uniqueid returns False."""
        nfo = tmp_path / "movie.nfo"
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Test"
        ET.SubElement(root, "year").text = "2024"
        ET.ElementTree(root).write(nfo, encoding="unicode")

        assert _is_nfo_complete(nfo) is False

    def test_nfo_with_empty_uniqueid(self, tmp_path):
        """Uniqueid with empty text returns False."""
        nfo = tmp_path / "movie.nfo"
        root = ET.Element("movie")
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tmdb")
        uid.text = ""
        ET.ElementTree(root).write(nfo, encoding="unicode")

        assert _is_nfo_complete(nfo) is False

    def test_nfo_absent(self, tmp_path):
        """Non-existent file returns False."""
        assert _is_nfo_complete(tmp_path / "nonexistent.nfo") is False

    def test_tvshow_nfo_valid(self, tmp_path):
        """tvshow.nfo with uniqueid returns True."""
        nfo = tmp_path / "tvshow.nfo"
        root = ET.Element("tvshow")
        ET.SubElement(root, "title").text = "Show"
        uid = ET.SubElement(root, "uniqueid")
        uid.set("type", "tvdb")
        uid.text = "456"
        ET.ElementTree(root).write(nfo, encoding="unicode")

        assert _is_nfo_complete(nfo) is True


# ── _has_unsorted_items ───────────────────────────────


class TestHasUnsortedItems:
    """Tests for sort fast-skip check.

    _has_unsorted_items now takes an ingest_dir Path directly
    (V15 P6.5: no longer accepts a Settings object).
    """

    def test_empty_dir(self, tmp_path):
        """Empty 097-TEMP returns False."""
        ingest_dir = tmp_path / "097-TEMP"
        ingest_dir.mkdir()

        assert _has_unsorted_items(ingest_dir) is False

    def test_with_files(self, tmp_path):
        """097-TEMP with files returns True."""
        ingest_dir = tmp_path / "097-TEMP"
        ingest_dir.mkdir()
        (ingest_dir / "movie.mkv").write_text("video")

        assert _has_unsorted_items(ingest_dir) is True

    def test_hidden_only(self, tmp_path):
        """097-TEMP with only hidden files returns False."""
        ingest_dir = tmp_path / "097-TEMP"
        ingest_dir.mkdir()
        (ingest_dir / ".DS_Store").write_bytes(b"\x00")
        (ingest_dir / ".gitkeep").write_text("")

        assert _has_unsorted_items(ingest_dir) is False

    def test_dir_missing(self, tmp_path):
        """Non-existent 097-TEMP returns False."""
        ingest_dir = tmp_path / "097-TEMP"
        assert _has_unsorted_items(ingest_dir) is False


# ── _has_polluted_folders ─────────────────────────────


class TestHasPollutedFolders:
    """Tests for clean fast-skip check."""

    def test_all_clean(self, tmp_path):
        """All clean folders returns False."""
        d = tmp_path / "001-MOVIES"
        d.mkdir()
        (d / "The Matrix (1999)").mkdir()
        (d / "Inception (2010)").mkdir()

        assert _has_polluted_folders(d) is False

    def test_one_polluted(self, tmp_path):
        """One polluted folder returns True."""
        d = tmp_path / "001-MOVIES"
        d.mkdir()
        (d / "The Matrix (1999)").mkdir()
        (d / "Movie.Title.2024.1080p.BluRay.x264-GROUP").mkdir()

        assert _has_polluted_folders(d) is True

    def test_empty_dir(self, tmp_path):
        """Empty category dir returns False."""
        d = tmp_path / "001-MOVIES"
        d.mkdir()

        assert _has_polluted_folders(d) is False

    def test_nonexistent_dir(self, tmp_path):
        """Non-existent dir returns False."""
        assert _has_polluted_folders(tmp_path / "nonexistent") is False
