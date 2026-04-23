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

    def test_uniqueid_zero_is_incomplete(self, tmp_path: Path) -> None:
        """A legacy NFO whose only <uniqueid> is ``"0"`` must be treated as incomplete.

        Regression guard: such NFOs came from runs where TMDB did not know
        the show and the scraper emitted ``<uniqueid type="tmdb">0</uniqueid>``.
        They were then fast-skipped by process on every subsequent run,
        never getting regenerated. The tmdb=0 default was fixed in
        a53a44f, but this validator needs to reject the legacy value so
        the show actually gets re-scraped.
        """
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text('<tvshow><uniqueid default="true" type="tmdb">0</uniqueid></tvshow>')
        assert is_nfo_complete(nfo) is False

    def test_uniqueid_none_string_is_incomplete(self, tmp_path: Path) -> None:
        """Legacy ``None`` text (from str(None) bug) must be treated as incomplete."""
        nfo = tmp_path / "episode.nfo"
        nfo.write_text('<episodedetails><uniqueid type="tvdb">None</uniqueid></episodedetails>')
        assert is_nfo_complete(nfo) is False

    def test_one_real_id_among_placeholders_is_valid(self, tmp_path: Path) -> None:
        """If any <uniqueid> carries a real value, the NFO stays valid."""
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text(
            '<tvshow>'
            '<uniqueid default="true" type="tmdb">0</uniqueid>'
            '<uniqueid type="tvdb">475278</uniqueid>'
            "</tvshow>"
        )
        assert is_nfo_complete(nfo) is True
