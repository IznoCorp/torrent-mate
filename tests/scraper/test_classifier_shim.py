"""Tests for the phase-27 classifier shim.

The classifier and title-resolver still consume a TMDB-flavoured raw dict
shape so downstream NFO + artwork consumers (which haven't migrated yet)
can keep working. The shim accepts either the typed
``MediaDetails`` emitted by api-unify clients or the legacy dict and
returns a uniform dict that downstream code can read safely.

These tests pin the contract so a regression in the typed → dict
adaptation cannot silently break classification or local-title
resolution.
"""

from __future__ import annotations

from personalscraper.api.metadata._base import MediaDetails
from personalscraper.scraper.classifier import (
    _coerce_to_classifier_dict,
    _media_details_to_classifier_dict,
)


class TestMediaDetailsToClassifierDict:
    """``_media_details_to_classifier_dict`` — typed MediaDetails → dict shape."""

    def test_movie_basic_fields(self) -> None:
        """Title + original_title flow through both ``title`` / ``name`` aliases."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="603",
            title="Matrix",
            original_title="The Matrix",
            year=1999,
        )
        d = _media_details_to_classifier_dict(md)
        assert d["title"] == "Matrix"
        assert d["name"] == "Matrix"  # alias for TV-style lookup
        assert d["original_title"] == "The Matrix"
        assert d["original_name"] == "The Matrix"

    def test_genre_names_and_ids_zip_into_dicts(self) -> None:
        """Genres + genre_ids zip into the legacy ``[{"id", "name"}]`` shape."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            genres=["Animation", "Drama"],
            genre_ids=[16, 18],
        )
        d = _media_details_to_classifier_dict(md)
        assert d["genres"] == [
            {"id": 16, "name": "Animation"},
            {"id": 18, "name": "Drama"},
        ]

    def test_genres_only_names_no_ids(self) -> None:
        """Provider that only has names (e.g. TVDB legacy) still produces entries."""
        md = MediaDetails(provider="tvdb", provider_id="1", genres=["Reality"], genre_ids=[])
        d = _media_details_to_classifier_dict(md)
        assert d["genres"] == [{"id": None, "name": "Reality"}]

    def test_genres_only_ids_no_names(self) -> None:
        """Provider that only has IDs still produces entries."""
        md = MediaDetails(provider="tmdb", provider_id="1", genres=[], genre_ids=[16])
        d = _media_details_to_classifier_dict(md)
        # Empty genre name string is filtered → genre dict still surfaces with id+empty name
        assert d["genres"] == [{"id": 16, "name": None}]

    def test_origin_countries_preferred_over_production(self) -> None:
        """``origin_country`` is filled from origin_countries when present."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            origin_countries=["JP"],
            production_countries=["US"],
        )
        d = _media_details_to_classifier_dict(md)
        assert d["origin_country"] == ["JP"]

    def test_production_countries_fallback(self) -> None:
        """When origin_countries empty, ``origin_country`` falls back to production list."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            origin_countries=[],
            production_countries=["US", "FR"],
        )
        d = _media_details_to_classifier_dict(md)
        assert d["origin_country"] == ["US", "FR"]

    def test_production_countries_dict_shape(self) -> None:
        """``production_countries`` is exposed in the legacy {"iso_3166_1"} shape."""
        md = MediaDetails(
            provider="tmdb",
            provider_id="1",
            production_countries=["JP", "FR"],
        )
        d = _media_details_to_classifier_dict(md)
        assert d["production_countries"] == [
            {"iso_3166_1": "JP"},
            {"iso_3166_1": "FR"},
        ]


class TestCoerceToClassifierDict:
    """``_coerce_to_classifier_dict`` — accepts MediaDetails or raw dict."""

    def test_passthrough_for_dict_input(self) -> None:
        """A dict is returned unchanged (no conversion)."""
        d = {"title": "X", "genres": [{"id": 1, "name": "G"}]}
        out = _coerce_to_classifier_dict(d)
        assert out is d  # exact same object

    def test_converts_media_details(self) -> None:
        """A MediaDetails is converted via ``_media_details_to_classifier_dict``."""
        md = MediaDetails(provider="tmdb", provider_id="1", title="X")
        out = _coerce_to_classifier_dict(md)
        assert isinstance(out, dict)
        assert out["title"] == "X"
