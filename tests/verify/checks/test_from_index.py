"""Unit tests for IndexableCheck.from_index() on the four indexable plugins."""

import json

from personalscraper.verify.checks.base import IndexContext, Severity


def _ictx(media_type: str = "movie", category: str = "movies") -> IndexContext:
    return IndexContext(row={}, media_type=media_type, category=category)


def test_nfo_present_from_index_missing():
    """NfoPresent.from_index returns a failed result when nfo_status=="missing"."""
    from personalscraper.verify.checks.nfo import NfoPresent

    row = {"nfo_status": "missing"}
    results = NfoPresent().from_index(row, _ictx())
    assert results is not None
    assert len(results) == 1
    assert not results[0].passed
    assert results[0].name == "nfo_present"


def test_nfo_present_from_index_valid():
    """NfoPresent.from_index returns [] when nfo_status=="valid"."""
    from personalscraper.verify.checks.nfo import NfoPresent

    row = {"nfo_status": "valid"}
    results = NfoPresent().from_index(row, _ictx())
    assert results == []  # valid → no finding


def test_nfo_present_from_index_null_skipped():
    """NfoPresent.from_index returns [] when nfo_status is NULL."""
    from personalscraper.verify.checks.nfo import NfoPresent

    row = {"nfo_status": None}
    results = NfoPresent().from_index(row, _ictx())
    assert results == []  # NULL → unflagged (cannot distinguish from not-yet-enriched)


def test_nfo_valid_from_index_invalid():
    """NfoValid.from_index returns a failed result when nfo_status=="invalid"."""
    from personalscraper.verify.checks.nfo import NfoValid

    row = {"nfo_status": "invalid"}
    results = NfoValid().from_index(row, _ictx())
    assert results is not None and len(results) == 1
    assert not results[0].passed
    assert results[0].name == "nfo_valid"


def test_poster_present_from_index_missing():
    """PosterPresent.from_index returns a failed result when poster key is absent."""
    from personalscraper.verify.checks.artwork import PosterPresent

    row = {"artwork_json": json.dumps({})}  # no poster key
    results = PosterPresent().from_index(row, _ictx())
    assert results is not None and len(results) == 1
    assert not results[0].passed


def test_poster_present_from_index_present():
    """PosterPresent.from_index returns [] when poster key is present."""
    from personalscraper.verify.checks.artwork import PosterPresent

    row = {"artwork_json": json.dumps({"poster": "poster.jpg"})}
    results = PosterPresent().from_index(row, _ictx())
    assert results == []


def test_artwork_landscape_from_index_movie_missing():
    """ArtworkLandscape.from_index returns WARNING when landscape is absent for a movie."""
    from personalscraper.verify.checks.artwork import ArtworkLandscape

    row = {"artwork_json": json.dumps({})}
    results = ArtworkLandscape().from_index(row, _ictx(media_type="movie"))
    assert results is not None and len(results) == 1
    assert results[0].severity == Severity.WARNING


def test_artwork_landscape_from_index_tvshow_skipped():
    """DB-mode landscape is movie-only today — preserved."""
    from personalscraper.verify.checks.artwork import ArtworkLandscape

    row = {"artwork_json": json.dumps({})}
    results = ArtworkLandscape().from_index(row, _ictx(media_type="tvshow"))
    assert results is None  # tvshow → not derivable in DB-mode
