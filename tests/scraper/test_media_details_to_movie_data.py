"""Tests for ``_media_details_to_movie_data`` — phase 27 movie shim.

Mirrors the TVDB equivalent (``_tvdb_series_to_show_data``): converts
the typed ``MediaDetails`` returned by ``TMDBClient.get_movie`` into the
legacy raw-dict shape that the NFO generator and artwork downloader
still consume. Once those two consumers migrate to MediaDetails, this
shim can be deleted.
"""

from __future__ import annotations

from personalscraper.api.metadata._base import ArtworkItem, MediaDetails
from personalscraper.scraper.movie_service import (
    _coerce_to_movie_data,
    _media_details_to_movie_data,
)


class TestMediaDetailsToMovieData:
    """``_media_details_to_movie_data`` — typed MediaDetails → dict shape."""

    def test_basic_fields_propagate(self) -> None:
        """Title / original_title / overview / runtime / rating flow through."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="603",
            title="Matrix",
            original_title="The Matrix",
            year=1999,
            overview="A computer hacker learns about reality.",
            runtime_minutes=139,
            rating=8.7,
        )
        d = _media_details_to_movie_data(md)
        assert d["title"] == "Matrix"
        assert d["original_title"] == "The Matrix"
        assert d["overview"] == "A computer hacker learns about reality."
        assert d["runtime"] == 139
        assert d["vote_average"] == 8.7
        assert d["release_date"] == "1999-01-01"

    def test_id_coerced_to_int_when_numeric(self) -> None:
        """Numeric provider_id is coerced to int for legacy ``id`` consumers."""
        md = MediaDetails(provider="tmdb", provider_id="42")
        d = _media_details_to_movie_data(md)
        assert d["id"] == 42

    def test_id_kept_as_string_when_non_numeric(self) -> None:
        """Non-numeric provider_id passes through as-is (won't break the dict)."""
        md = MediaDetails(provider="omdb", provider_id="tt0123456")
        d = _media_details_to_movie_data(md)
        assert d["id"] == "tt0123456"

    def test_genres_zip_into_dicts(self) -> None:
        """Names + IDs zip into ``[{"id", "name"}]`` legacy shape."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            genres=["Action", "Sci-Fi"],
            genre_ids=[28, 878],
        )
        d = _media_details_to_movie_data(md)
        assert d["genres"] == [
            {"id": 28, "name": "Action"},
            {"id": 878, "name": "Sci-Fi"},
        ]

    def test_country_lists_split(self) -> None:
        """origin_countries → ``origin_country`` flat list, production → dict shape."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            origin_countries=["US"],
            production_countries=["US", "FR"],
        )
        d = _media_details_to_movie_data(md)
        assert d["origin_country"] == ["US"]
        assert d["production_countries"] == [
            {"iso_3166_1": "US"},
            {"iso_3166_1": "FR"},
        ]

    def test_external_ids_legacy_keying(self) -> None:
        """external_ids keys gain a ``_id`` suffix for the legacy shape."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            external_ids={"imdb": "tt0001", "tvdb": "12345"},
        )
        d = _media_details_to_movie_data(md)
        assert d["external_ids"]["imdb_id"] == "tt0001"
        assert d["external_ids"]["tvdb_id"] == "12345"
        # ``imdb_id`` also surfaces at top-level (NFO writer reads either).
        assert d["imdb_id"] == "tt0001"

    def test_images_split_by_type(self) -> None:
        """Curated ArtworkItem list is bucketed into posters / backdrops / logos."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            images=[
                ArtworkItem(type="poster", url="http://x/p1.jpg", language="fr", vote_average=7.0),
                ArtworkItem(type="poster", url="http://x/p2.jpg", language="en", vote_average=5.0),
                ArtworkItem(type="backdrop", url="http://x/b1.jpg", vote_average=6.0),
                ArtworkItem(type="landscape", url="http://x/l1.jpg"),
                # Empty url — should be skipped (artwork.py would do the same)
                ArtworkItem(type="poster", url=""),
            ],
        )
        d = _media_details_to_movie_data(md)
        assert len(d["images"]["posters"]) == 2
        assert len(d["images"]["backdrops"]) == 1
        assert len(d["images"]["logos"]) == 1
        # Poster vote_average preserved
        votes = {p["file_path"]: p["vote_average"] for p in d["images"]["posters"]}
        assert votes["http://x/p1.jpg"] == 7.0

    def test_primary_backdrop_url_surfaces(self) -> None:
        """``primary_backdrop_url`` becomes top-level ``backdrop_path``."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            primary_backdrop_url="https://image.tmdb.org/t/p/w1280/abc.jpg",
        )
        d = _media_details_to_movie_data(md)
        assert d["backdrop_path"] == "https://image.tmdb.org/t/p/w1280/abc.jpg"

    def test_no_year_no_release_date(self) -> None:
        """Missing year produces empty release_date string."""
        md = MediaDetails(provider="tmdb", provider_id="1", year=None)
        d = _media_details_to_movie_data(md)
        assert d["release_date"] == ""
        assert d["first_air_date"] == ""


class TestCoerceToMovieData:
    """``_coerce_to_movie_data`` accepts MediaDetails or dict."""

    def test_passthrough_for_dict(self) -> None:
        """Dict input is returned unchanged."""
        d = {"id": 1, "title": "X"}
        assert _coerce_to_movie_data(d) is d

    def test_converts_media_details(self) -> None:
        """MediaDetails input is converted via ``_media_details_to_movie_data``."""
        md = MediaDetails(provider="tmdb", provider_id="1", title="X")
        out = _coerce_to_movie_data(md)
        assert isinstance(out, dict)
        assert out["title"] == "X"
