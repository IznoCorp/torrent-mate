"""Tests for personalscraper.nfo_utils — shared NFO validation."""

from pathlib import Path

from personalscraper.nfo_utils import is_nfo_complete


class TestIsNfoComplete:
    """Tests for is_nfo_complete shared function."""

    def test_valid_nfo(self, tmp_path: Path) -> None:
        """NFO with uniqueid should be complete."""
        nfo = tmp_path / "movie.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb">123</uniqueid></movie>')
        assert is_nfo_complete(nfo) is True

    def test_missing_nfo(self, tmp_path: Path) -> None:
        """Non-existent NFO should be incomplete."""
        assert is_nfo_complete(tmp_path / "missing.nfo") is False

    def test_empty_nfo(self, tmp_path: Path) -> None:
        """Empty file should be incomplete."""
        nfo = tmp_path / "empty.nfo"
        nfo.write_text("")
        assert is_nfo_complete(nfo) is False

    def test_no_uniqueid(self, tmp_path: Path) -> None:
        """NFO without uniqueid should be incomplete."""
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("<movie><title>Test</title></movie>")
        assert is_nfo_complete(nfo) is False

    def test_corrupt_xml(self, tmp_path: Path) -> None:
        """Non-parsable XML should be incomplete."""
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("<movie><title>broken")
        assert is_nfo_complete(nfo) is False
