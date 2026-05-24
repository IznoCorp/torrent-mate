"""Tests for personalscraper.nfo_utils — shared NFO validation."""

from pathlib import Path

from personalscraper.nfo_utils import glob_nfo_candidates, is_nfo_complete


class TestGlobNfoCandidates:
    """glob_nfo_candidates skips macOS AppleDouble (._) sidecars."""

    def test_returns_real_nfo(self, tmp_path: Path) -> None:
        """A single real .nfo file is returned."""
        (tmp_path / "Inception.nfo").write_text("<movie/>")
        assert glob_nfo_candidates(tmp_path) == [tmp_path / "Inception.nfo"]

    def test_skips_appledouble_sidecar(self, tmp_path: Path) -> None:
        """An ._Inception.nfo AppleDouble file must NOT shadow the real Inception.nfo."""
        (tmp_path / "Inception.nfo").write_text("<movie/>")
        (tmp_path / "._Inception.nfo").write_bytes(b"\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X        ")
        result = glob_nfo_candidates(tmp_path)
        assert result == [tmp_path / "Inception.nfo"]

    def test_appledouble_only_returns_empty(self, tmp_path: Path) -> None:
        """A directory with only ._<name>.nfo files yields zero candidates."""
        (tmp_path / "._stub.nfo").write_bytes(b"\x00")
        assert glob_nfo_candidates(tmp_path) == []

    def test_no_nfo_returns_empty(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        assert glob_nfo_candidates(tmp_path) == []

    def test_multiple_real_nfos_sorted(self, tmp_path: Path) -> None:
        """Multiple real NFOs are returned sorted (deterministic for ambiguity detection)."""
        (tmp_path / "Z.nfo").write_text("<movie/>")
        (tmp_path / "A.nfo").write_text("<movie/>")
        result = glob_nfo_candidates(tmp_path)
        assert [p.name for p in result] == ["A.nfo", "Z.nfo"]


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
            '<tvshow><uniqueid default="true" type="tmdb">0</uniqueid><uniqueid type="tvdb">475278</uniqueid></tvshow>'
        )
        assert is_nfo_complete(nfo) is True
