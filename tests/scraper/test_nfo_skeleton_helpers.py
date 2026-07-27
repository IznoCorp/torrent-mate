"""Unit tests for the shared NFO skeleton helpers (SCRAPER-05).

Covers the three builders the movie / tvshow / episode generators now share:
``_strip_title_year`` (title guard), ``_clean_id`` (id guard) and the single
``_write_uniqueids`` writer. These pin the guard behaviour in isolation,
including the previously-buggy movie case (an empty imdb id used to emit an
``<uniqueid default="true" type="imdb"></uniqueid>`` placeholder row).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from personalscraper.scraper.nfo_generator import (
    _clean_id,
    _strip_title_year,
    _write_uniqueids,
)

# ---------------------------------------------------------------------------
# _strip_title_year
# ---------------------------------------------------------------------------


class TestStripTitleYear:
    """Title guard shared by the movie and tvshow generators."""

    def test_strips_matching_trailing_year(self) -> None:
        """A trailing ``(YYYY)`` that matches the date is removed."""
        assert _strip_title_year("INVINCIBLE (2021)", "2021-03-25") == "INVINCIBLE"

    def test_keeps_title_when_year_does_not_match(self) -> None:
        """A parenthetical that is not the release year stays put."""
        assert _strip_title_year("Blade Runner (2049)", "1982-06-25") == "Blade Runner (2049)"

    def test_keeps_title_without_trailing_year(self) -> None:
        """A bare title is returned unchanged."""
        assert _strip_title_year("The Piano Lesson", "2024-11-07") == "The Piano Lesson"

    def test_empty_date_is_a_noop(self) -> None:
        """With no year to match, even a real ``(2021)`` is preserved."""
        assert _strip_title_year("Show (2021)", "") == "Show (2021)"

    def test_year_only_matches_full_four_digit_paren(self) -> None:
        """A bare ``(202)`` must not be mistaken for the year."""
        assert _strip_title_year("Weird (202)", "2021") == "Weird (202)"


# ---------------------------------------------------------------------------
# _clean_id
# ---------------------------------------------------------------------------


class TestCleanId:
    """Id guard collapsing provider placeholders to the empty string."""

    @pytest.mark.parametrize("placeholder", [None, 0, "0", "", "None"])
    def test_placeholders_collapse_to_empty(self, placeholder: object) -> None:
        """Every placeholder form maps to ``""``."""
        assert _clean_id(placeholder) == ""

    def test_real_numeric_id_is_stringified(self) -> None:
        """A real numeric id becomes its string form."""
        assert _clean_id(804406) == "804406"

    def test_real_string_id_passes_through(self) -> None:
        """A real string id is returned unchanged."""
        assert _clean_id("tt15507512") == "tt15507512"


# ---------------------------------------------------------------------------
# _write_uniqueids
# ---------------------------------------------------------------------------


def _uniqueids(root: ET.Element) -> list[tuple[str | None, str | None, str | None]]:
    """Return ``(type, default, text)`` tuples in document order."""
    return [(u.get("type"), u.get("default"), u.text) for u in root.findall("uniqueid")]


class TestWriteUniqueids:
    """The single ``<uniqueid>`` writer shared by all three generators."""

    def test_episode_general_form_orders_and_flags_canonical(self) -> None:
        """Rows keep input order; only the canonical family gets ``default``."""
        root = ET.Element("episodedetails")
        _write_uniqueids(root, [("tvdb", "42"), ("tmdb", "7"), ("imdb", "tt9")], "tvdb")
        assert _uniqueids(root) == [
            ("tvdb", "true", "42"),
            ("tmdb", None, "7"),
            ("imdb", None, "tt9"),
        ]

    def test_blank_values_are_skipped(self) -> None:
        """Blank ids are omitted; a canonical with no value flags nothing."""
        root = ET.Element("episodedetails")
        _write_uniqueids(root, [("tvdb", ""), ("tmdb", "7"), ("imdb", "")], "tvdb")
        assert _uniqueids(root) == [("tmdb", None, "7")]

    def test_canonical_falls_through_to_present_family(self) -> None:
        """The caller-resolved canonical (here tmdb) receives the default."""
        root = ET.Element("episodedetails")
        _write_uniqueids(root, [("tvdb", ""), ("tmdb", "7"), ("imdb", "tt9")], "tmdb")
        assert _uniqueids(root) == [("tmdb", "true", "7"), ("imdb", None, "tt9")]

    def test_movie_shape_imdb_default(self) -> None:
        """Movies pass imdb/tmdb with imdb canonical → imdb is default."""
        root = ET.Element("movie")
        _write_uniqueids(root, [("imdb", "tt1"), ("tmdb", "603")], "imdb")
        assert _uniqueids(root) == [("imdb", "true", "tt1"), ("tmdb", None, "603")]

    def test_movie_empty_imdb_no_placeholder_default_row(self) -> None:
        """Regression (SCRAPER-05): empty imdb must not emit a blank default row.

        Before the shared guard, ``generate_movie_nfo`` wrote
        ``<uniqueid default="true" type="imdb"></uniqueid>`` whenever the imdb
        id was missing — a placeholder Kodi tries to resolve. The general form
        skips the blank; the caller resolves the default onto tmdb instead.
        """
        root = ET.Element("movie")
        _write_uniqueids(root, [("imdb", ""), ("tmdb", "603")], "tmdb")
        rows = _uniqueids(root)
        assert rows == [("tmdb", "true", "603")]
        # No empty-text uniqueid, and no default flag on a blank row.
        assert all(text for _type, _default, text in rows)

    def test_at_most_one_default(self) -> None:
        """At most one row is ever flagged ``default="true"``."""
        root = ET.Element("tvshow")
        _write_uniqueids(root, [("tvdb", "1"), ("tmdb", "2"), ("imdb", "tt3")], "tvdb")
        defaults = [u for u in root.findall("uniqueid") if u.get("default") == "true"]
        assert len(defaults) == 1
        assert defaults[0].get("type") == "tvdb"
