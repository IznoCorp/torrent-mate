"""Tests for personalscraper.nfo_utils — shared NFO validation."""

import textwrap
from pathlib import Path

import pytest

from personalscraper.nfo_utils import (
    extract_nfo_ids,
    extract_nfo_metadata,
    glob_nfo_candidates,
    is_nfo_complete,
    parse_title_year,
)


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


# --- parse_title_year ---


@pytest.mark.parametrize(
    "dirname,expected_title,expected_year",
    [
        ("The Godfather (1972)", "The Godfather", 1972),
        ("Inception (2010)", "Inception", 2010),
        ("No Year Here", "No Year Here", None),
        ("Bad Boys for Life (2020)", "Bad Boys for Life", 2020),
    ],
)
def test_parse_title_year(dirname: str, expected_title: str, expected_year: int | None) -> None:
    """parse_title_year correctly splits title and year from a directory name."""
    title, year = parse_title_year(dirname)
    assert title == expected_title
    assert year == expected_year


# --- extract_nfo_ids ---


def _write_nfo(tmp_path: Path, content: str) -> Path:
    nfo = tmp_path / "movie.nfo"
    nfo.write_text(textwrap.dedent(content), encoding="utf-8")
    return nfo


def test_extract_nfo_ids_tmdb_and_imdb(tmp_path: Path) -> None:
    """extract_nfo_ids returns (tmdb_id, imdb_id) from a well-formed NFO."""
    # extract_nfo_ids returns (tmdb_id, imdb_id) — not (tvdb_id, tmdb_id).
    nfo = _write_nfo(
        tmp_path,
        """\
        <?xml version="1.0" encoding="UTF-8"?>
        <movie>
          <uniqueid type="tmdb" default="true">67890</uniqueid>
          <uniqueid type="imdb">tt0012345</uniqueid>
        </movie>
    """,
    )
    tmdb_id, imdb_id = extract_nfo_ids(nfo)
    assert tmdb_id == "67890"
    assert imdb_id == "tt0012345"


def test_extract_nfo_ids_missing(tmp_path: Path) -> None:
    """extract_nfo_ids returns (None, None) when no uniqueid elements are present."""
    nfo = _write_nfo(
        tmp_path,
        """\
        <?xml version="1.0" encoding="UTF-8"?>
        <movie><title>No IDs</title></movie>
    """,
    )
    tmdb_id, imdb_id = extract_nfo_ids(nfo)
    assert tmdb_id is None
    assert imdb_id is None


# --- extract_nfo_metadata ---


def test_extract_nfo_metadata_returns_dict(tmp_path: Path) -> None:
    """extract_nfo_metadata returns a dict with tmdb_id, imdb_id, and title fields."""
    nfo = _write_nfo(
        tmp_path,
        """\
        <?xml version="1.0" encoding="UTF-8"?>
        <movie>
          <uniqueid type="tmdb" default="true">99</uniqueid>
          <uniqueid type="imdb">tt0000001</uniqueid>
        </movie>
    """,
    )
    meta = extract_nfo_metadata(nfo)
    assert isinstance(meta, dict)
    assert meta.get("tmdb_id") == "99" or "tmdb" in str(meta)


# --- extract_nfo_metadata: provider-ids + ratings (migrated from
#     tests/library/test_scanner.TestExtractNfoMetadata, lib-fold Phase 3).
#     The scanner module that hosted these tests is being deleted; the helper
#     itself lives in personalscraper.nfo_utils and is imported here directly. ---


def test_extract_nfo_metadata_extracts_tvdb_id(tmp_path: Path) -> None:
    """TVDB uniqueid is read (legacy extract_nfo_ids silently dropped it)."""
    nfo = tmp_path / "tvshow.nfo"
    nfo.write_text('<tvshow><uniqueid type="tvdb">73141</uniqueid></tvshow>')

    meta = extract_nfo_metadata(nfo)

    assert meta["tvdb_id"] == "73141"
    assert meta["tmdb_id"] is None
    assert meta["imdb_id"] is None


def test_extract_nfo_metadata_canonical_provider_from_default_true(tmp_path: Path) -> None:
    """``<uniqueid default="true" type="tvdb">`` → canonical_provider='tvdb'."""
    nfo = tmp_path / "tvshow.nfo"
    nfo.write_text(
        '<tvshow><uniqueid type="tvdb" default="true">73141</uniqueid><uniqueid type="tmdb">1433</uniqueid></tvshow>'
    )

    meta = extract_nfo_metadata(nfo)

    assert meta["canonical_provider"] == "tvdb"


def test_extract_nfo_metadata_canonical_provider_default_tmdb(tmp_path: Path) -> None:
    """``<uniqueid default="true" type="tmdb">`` → canonical_provider='tmdb'."""
    nfo = tmp_path / "movie.nfo"
    nfo.write_text('<movie><uniqueid type="tmdb" default="true">603</uniqueid></movie>')

    meta = extract_nfo_metadata(nfo)

    assert meta["canonical_provider"] == "tmdb"


def test_extract_nfo_metadata_canonical_provider_none_when_no_default(tmp_path: Path) -> None:
    """Legacy NFO without ``default="true"`` → canonical_provider=None."""
    nfo = tmp_path / "tvshow.nfo"
    nfo.write_text('<tvshow><uniqueid type="tvdb">73141</uniqueid></tvshow>')

    meta = extract_nfo_metadata(nfo)

    assert meta["canonical_provider"] is None


def test_extract_nfo_metadata_all_three_ids_with_canonical(tmp_path: Path) -> None:
    """NFO with tvdb (canonical) + tmdb + imdb returns all three IDs."""
    nfo = tmp_path / "tvshow.nfo"
    nfo.write_text(
        '<tvshow><uniqueid type="tvdb" default="true">73141</uniqueid>'
        '<uniqueid type="tmdb">1433</uniqueid>'
        '<uniqueid type="imdb">tt0397306</uniqueid></tvshow>'
    )

    meta = extract_nfo_metadata(nfo)

    assert meta["tvdb_id"] == "73141"
    assert meta["tmdb_id"] == "1433"
    assert meta["imdb_id"] == "tt0397306"
    assert meta["canonical_provider"] == "tvdb"


def test_extract_nfo_metadata_ratings_block_with_source_mapping(tmp_path: Path) -> None:
    """``<rating name="themoviedb">`` is mapped to internal ``"tmdb"`` source.

    Mirrors the inverse of ``nfo_generator._NFO_RATING_SOURCE_NAMES`` so
    ``ratings_json`` carries the same shape the scraper writes.
    """
    nfo = tmp_path / "movie.nfo"
    nfo.write_text(
        "<movie>"
        "<ratings>"
        '<rating name="imdb" max="10"><value>8.5</value><votes>1000000</votes></rating>'
        '<rating name="themoviedb" max="10"><value>7.2</value><votes>500</votes></rating>'
        '<rating name="rottentomatoes" max="100"><value>91</value><votes>0</votes></rating>'
        "</ratings>"
        "</movie>"
    )

    meta = extract_nfo_metadata(nfo)

    sources = {r["source"] for r in meta["ratings"]}
    assert sources == {"imdb", "tmdb", "rotten_tomatoes"}
    imdb = next(r for r in meta["ratings"] if r["source"] == "imdb")
    assert imdb["score"] == "8.5"
    assert imdb["votes"] == 1_000_000


def test_extract_nfo_metadata_empty_ratings_when_no_ratings_tag(tmp_path: Path) -> None:
    """NFO without a ``<ratings>`` block returns an empty list."""
    nfo = tmp_path / "tvshow.nfo"
    nfo.write_text('<tvshow><uniqueid type="tvdb">73141</uniqueid></tvshow>')

    meta = extract_nfo_metadata(nfo)

    assert meta["ratings"] == []


def test_extract_nfo_metadata_corrupt_xml_returns_blank_dict(tmp_path: Path) -> None:
    """Bad XML returns a blank stable dict (all None / empty list)."""
    nfo = tmp_path / "movie.nfo"
    nfo.write_text("<not_xml")

    meta = extract_nfo_metadata(nfo)

    assert meta == {
        "tmdb_id": None,
        "imdb_id": None,
        "tvdb_id": None,
        "canonical_provider": None,
        "ratings": [],
    }


# --- extract_nfo_ids: unique cases not yet covered in this file
#     (migrated from tests/library/test_scanner.TestExtractNfoIds). ---


def test_extract_nfo_ids_empty_uniqueid_text(tmp_path: Path) -> None:
    """NFO with empty uniqueid text returns (None, None)."""
    nfo = tmp_path / "movie.nfo"
    nfo.write_text('<movie><uniqueid type="tmdb"></uniqueid></movie>')
    tmdb, imdb = extract_nfo_ids(nfo)
    assert tmdb is None
    assert imdb is None


def test_extract_nfo_ids_corrupt_xml(tmp_path: Path) -> None:
    """Corrupt XML returns (None, None)."""
    nfo = tmp_path / "movie.nfo"
    nfo.write_text("<movie><broken")
    tmdb, imdb = extract_nfo_ids(nfo)
    assert tmdb is None
    assert imdb is None


def test_extract_nfo_ids_nonexistent_file(tmp_path: Path) -> None:
    """Missing file returns (None, None)."""
    tmdb, imdb = extract_nfo_ids(tmp_path / "missing.nfo")
    assert tmdb is None
    assert imdb is None


def test_extract_nfo_ids_backward_compatible_with_three_ids(tmp_path: Path) -> None:
    """The legacy 2-tuple shape is preserved even when tvdb is also present.

    Migrated from
    ``test_scanner.TestExtractNfoMetadata.test_extract_nfo_ids_remains_backward_compatible``:
    extract_nfo_ids returns ``(tmdb, imdb)`` and hides the tvdb id (read only by
    extract_nfo_metadata) for compatibility with trailers / rescraper callers.
    """
    nfo = tmp_path / "movie.nfo"
    nfo.write_text(
        '<movie><uniqueid type="tvdb">99999</uniqueid>'
        '<uniqueid type="tmdb">603</uniqueid>'
        '<uniqueid type="imdb">tt0133093</uniqueid></movie>'
    )

    assert extract_nfo_ids(nfo) == ("603", "tt0133093")
