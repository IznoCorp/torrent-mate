"""``ReleaseNumbering.parse``: the season and episode a release name numbers (K3 P9a, DESIGN § 2.9).

The numbering is read off the same patterns the filters use (``SxxEyy`` of ``filter_to_episode``,
guessit's episode list of ``filter_to_season``), so a candidate stored with its numbering agrees
with the filter that kept it. A pack numbers its season and no episode; a film and a name with no
marker number nothing.
"""

from __future__ import annotations

import pytest

from personalscraper.acquire.numbering import ReleaseNumbering


@pytest.mark.parametrize(
    ("title", "numbering"),
    [
        ("Show.S02E05.1080p.WEB-DL.x264-GRP", (2, 5)),
        ("Show.S9E5.720p.HDTV", (9, 5)),
        ("Show 2019 S01E03 720p", (1, 3)),
        ("Show.2x05.720p.HDTV", (2, 5)),
    ],
)
def test_an_episode_names_its_season_and_its_episode(title: str, numbering: tuple[int, int]) -> None:
    """One ``SxxEyy`` token (zero-padded or not) is the release's season and episode."""
    assert ReleaseNumbering.parse(title) == numbering


@pytest.mark.parametrize(
    "title",
    [
        "Show.S09E05-E06.MULTI.1080p",
        "Show.S09E05E06.1080p.WEB",
        "Show.S09E05E06E07.1080p.WEB",
    ],
)
def test_a_multi_episode_release_is_numbered_by_its_first_episode(title: str) -> None:
    """A span is the episode ``filter_to_episode`` matches it by: its first (``S09E05-E06`` keeps E05)."""
    assert ReleaseNumbering.parse(title) == (9, 5)


@pytest.mark.parametrize(
    ("title", "season"),
    [
        ("Show.S02.COMPLETE.1080p.BluRay", 2),
        ("Show.S2.1080p.WEB-DL", 2),
        ("Show.Saison.2.FRENCH.1080p", 2),
        ("Show.Season.2.Complete.720p", 2),
    ],
)
def test_a_season_pack_numbers_its_season_and_no_episode(title: str, season: int) -> None:
    """A pack carries no episode marker: its season is known, its episode is ``None``."""
    assert ReleaseNumbering.parse(title) == (season, None)


@pytest.mark.parametrize(
    "title",
    ["Show.S01-S03.COMPLETE.1080p", "Show.Saisons.1-4.FRENCH.1080p"],
)
def test_a_multi_season_pack_numbers_nothing(title: str) -> None:
    """A pack of several seasons is no one season's: neither number is claimed."""
    assert ReleaseNumbering.parse(title) == (None, None)


@pytest.mark.parametrize(
    "title",
    ["The.Matrix.1999.1080p.BluRay.x264", "Some.Movie.2021.MULTI.1080p.WEB"],
)
def test_a_film_numbers_nothing(title: str) -> None:
    """A film name has no season and no episode."""
    assert ReleaseNumbering.parse(title) == (None, None)


@pytest.mark.parametrize("title", ["", "Show.Intégrale.1080p", "just a name"])
def test_a_name_with_no_marker_numbers_nothing(title: str) -> None:
    """No marker, nothing numbered: an empty or markerless name is ``(None, None)``, never an error."""
    assert ReleaseNumbering.parse(title) == (None, None)


@pytest.mark.parametrize(
    ("title", "numbering"),
    [
        # A token guessit leaves unread: only the ``SxxEyy`` pattern numbers these.
        ("Show.S02E05v2", (2, 5)),
        ("Show.S02E05E06v2", (2, 5)),
        # Case is free.
        ("show.s02e05v2", (2, 5)),
        ("SHOW.S02E05V2", (2, 5)),
        # Zero-padding is free, however long.
        ("Show.S0002E0005v2", (2, 5)),
        ("Show.S02E00005v2", (2, 5)),
        # The digits stand alone: a digit before the ``S`` or after the episode is no token.
        ("Show.12S02E05.1080p", (None, None)),
        ("Show.S02E12345", (2, 12345)),
    ],
)
def test_the_episode_token_is_read_as_the_episode_filter_reads_it(
    title: str, numbering: tuple[int | None, int | None]
) -> None:
    """The ``SxxEyy`` pattern of ``filter_to_episode`` decides, with its bounds, its case and its padding."""
    assert ReleaseNumbering.parse(title) == numbering


@pytest.mark.parametrize(
    "title",
    ["Show.2x05-06.720p", "Show.2x05x06.720p", "Show.S02.E05-E06.1080p", "Show.S02.E05.E06"],
)
def test_a_span_with_no_episode_token_is_numbered_by_its_first_episode(title: str) -> None:
    """A span only guessit reads (no ``SxxEyy`` token) is numbered by the first of its episodes, ascending."""
    assert ReleaseNumbering.parse(title) == (2, 5)


def test_a_title_guessit_cannot_parse_numbers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-soft: whatever guessit raises, the name is unnumbered and the parse does not."""

    def _raises(title: str) -> dict[str, object]:
        raise RuntimeError(title)

    monkeypatch.setattr("guessit.guessit", _raises)
    assert ReleaseNumbering.parse("Show.2x05.720p") == (None, None)
    assert ReleaseNumbering.parse("Show.S02E05.720p") == (2, 5)


@pytest.mark.parametrize(
    "title",
    [
        "Show.S02E01-E12.1080p",
        "Show.S02E01E02E03E04E05E06E07E08E09E10E11E12.1080p",
        "Show.S02E01-12.1080p",
        "Show.S02.E01-E12.1080p",
        "Show.2x01-12.1080p",
        "Show.Season.2.Episodes.1-12.1080p",
    ],
)
def test_a_span_from_e01_to_the_expected_count_is_a_pack(title: str) -> None:
    """A range covering the season is a pack as ``filter_to_season`` reads it: the season, no episode."""
    assert ReleaseNumbering.parse(title, expected_count=12) == (2, None)


def test_a_span_beyond_the_expected_count_is_a_pack() -> None:
    """Coverage is « at least » the aired count: a range reaching past it still covers the season."""
    assert ReleaseNumbering.parse("Show.S02E01-E12.1080p", expected_count=10) == (2, None)


@pytest.mark.parametrize(
    ("title", "expected_count", "numbering"),
    [
        ("Show.S02E01-E12.1080p", None, (2, 1)),
        ("Show.S02E01-E12.1080p", 13, (2, 1)),
        ("Show.S02E01-E05.1080p", 12, (2, 1)),
        ("Show.S02E03-E12.1080p", 12, (2, 3)),
        ("Show.S02E05-E06.1080p", 12, (2, 5)),
        ("Show.S02E01.1080p", 1, (2, 1)),
        ("Show.S02E05.1080p", 12, (2, 5)),
    ],
)
def test_any_other_span_stays_numbered_by_its_first_episode(
    title: str, expected_count: int | None, numbering: tuple[int, int]
) -> None:
    """Unknown count, short range, range not starting at E01, two episodes, lone episode: the first episode."""
    assert ReleaseNumbering.parse(title, expected_count=expected_count) == numbering


def test_the_expected_count_changes_nothing_for_a_pack_a_film_or_nothing() -> None:
    """The count only reads spans: a pack, a film and a markerless name answer as without it."""
    assert ReleaseNumbering.parse("Show.S02.COMPLETE.1080p", expected_count=12) == (2, None)
    assert ReleaseNumbering.parse("The.Matrix.1999.1080p", expected_count=12) == (None, None)
    assert ReleaseNumbering.parse("just a name", expected_count=12) == (None, None)
