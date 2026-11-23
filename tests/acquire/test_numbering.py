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
