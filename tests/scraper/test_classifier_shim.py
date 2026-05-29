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

import builtins
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata._base import MediaDetails
from personalscraper.scraper.classifier import (
    ClassifierMixin,
    _coerce_to_classifier_dict,
    _media_details_to_classifier_dict,
    _parse_folder_name,
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


# ── _parse_folder_name — fallback paths ──────────────────────────────────────


class TestParseFolderName:
    """Cover the NameCleaner import-failure branch (line 106)."""

    def test_namecleaner_import_error_falls_back_to_raw_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """When NameCleaner cannot be imported, we log and return raw name + None year."""
        original_import = builtins.__import__

        def import_blocking_namecleaner(
            name: str,
            globals: object | None = None,
            locals: object | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if name == "personalscraper.sorter.cleaner":
                raise ImportError("stubbed")
            return original_import(name, globals, locals, fromlist, level)

        with patch.object(builtins, "__import__", side_effect=import_blocking_namecleaner):
            with caplog.at_level("WARNING"):
                title, year = _parse_folder_name("Some.Movie.2024.x264-GRP")

        assert year is None
        assert title == "Some.Movie.2024.x264-GRP"
        assert "folder_name_cleaner_unavailable" in caplog.text

    def test_clean_format_takes_priority(self) -> None:
        """``Title (Year)`` format short-circuits before NameCleaner is invoked."""
        title, year = _parse_folder_name("Inception (2010)")
        assert title == "Inception"
        assert year == 2010

    def test_namecleaner_extracts_title_and_year(self, caplog: pytest.LogCaptureFixture) -> None:
        """NameCleaner success path returns the cleaned title + extracted year."""
        with patch("personalscraper.sorter.cleaner.NameCleaner") as MockCleaner:
            instance = MockCleaner.return_value
            instance.clean.return_value = "Some Movie"
            instance.extract_year.return_value = 2024
            with caplog.at_level("INFO"):
                title, year = _parse_folder_name("Some.Movie.2024.x264-GRP")

        assert title == "Some Movie"
        assert year == 2024
        assert "folder_name_cleaned" in caplog.text

    def test_namecleaner_value_error_falls_back(self, caplog: pytest.LogCaptureFixture) -> None:
        """A ValueError raised inside NameCleaner is logged at WARNING and we fall back."""
        with patch("personalscraper.sorter.cleaner.NameCleaner") as MockCleaner:
            MockCleaner.return_value.clean.side_effect = ValueError("bad name")
            with caplog.at_level("WARNING"):
                title, year = _parse_folder_name("Garbage.Name")

        assert title == "Garbage.Name"
        assert year is None
        assert "folder_name_clean_failed" in caplog.text


# ── ClassifierMixin._classify_item — unit tests ──────────────────────────────


def _make_classifier(
    *,
    config: object | None = None,
    needs_keywords: bool = False,
    keywords_cache: object | None = None,
    prefer_local: bool = False,
    tmdb: object | None = None,
) -> ClassifierMixin:
    """Build a bare ClassifierMixin with the attributes the methods need."""
    instance = ClassifierMixin.__new__(ClassifierMixin)
    instance.config = config  # type: ignore[assignment]
    instance._needs_keywords = needs_keywords  # type: ignore[assignment]
    instance._keywords_cache = keywords_cache  # type: ignore[assignment]
    instance._prefer_local_title = prefer_local  # type: ignore[assignment]

    _tmdb_client = tmdb if tmdb is not None else MagicMock()
    _registry = MagicMock()

    def _locked_side_effect(capability: object, match: object) -> MagicMock:
        locked = MagicMock()
        locked.provider = _tmdb_client
        locked.bound_id = getattr(match, "id", str(match))
        return locked

    _registry.locked.side_effect = _locked_side_effect
    instance._registry = _registry  # type: ignore[assignment]
    return instance


class TestClassifyItem:
    """Cover the cache-hit branch (line 167) and origin_country dict branches (187-190)."""

    def test_returns_none_when_config_is_none(self) -> None:
        """Skipped legacy mode → returns None immediately."""
        c = _make_classifier(config=None)
        result = c._classify_item("movie", Path("/tmp/x"), "title", {}, tmdb_id=1)
        assert result is None

    def test_keywords_cache_hit_skips_fetch(self) -> None:
        """A cache hit is used directly — TMDBClient.get_keywords is not called."""
        cache = MagicMock()
        cache.get.return_value = ["cached-kw"]
        tmdb = MagicMock()
        config = MagicMock()
        c = _make_classifier(
            config=config,
            needs_keywords=True,
            keywords_cache=cache,
            tmdb=tmdb,
        )

        with patch("personalscraper.scraper.scraper._classifier") as mock_clf:
            mock_clf.classify.return_value = ("movies", "default")
            result = c._classify_item("movie", Path("/tmp/x"), "title", {}, tmdb_id=42)

        assert result == "movies"
        # Cache hit ⇒ TMDB.get_keywords must NOT be called.
        tmdb.get_keywords.assert_not_called()
        # Classify received the cached keywords list.
        assert mock_clf.classify.call_args.kwargs["tmdb_keywords"] == ["cached-kw"]

    def test_keywords_cache_miss_fetches_and_caches(self) -> None:
        """A cache miss triggers a fetch then a set() call."""
        cache = MagicMock()
        cache.get.return_value = None
        tmdb = MagicMock()
        tmdb.get_keywords.return_value = ["fresh-kw"]
        config = MagicMock()
        c = _make_classifier(
            config=config,
            needs_keywords=True,
            keywords_cache=cache,
            tmdb=tmdb,
        )

        with patch("personalscraper.scraper.scraper._classifier") as mock_clf:
            mock_clf.classify.return_value = ("movies", "default")
            c._classify_item("movie", Path("/tmp/x"), "title", {}, tmdb_id=42)

        tmdb.get_keywords.assert_called_once_with("42", "movie")
        cache.set.assert_called_once_with(42, "movie", ["fresh-kw"])

    def test_origin_country_iso_3166_dict_shape_extracted(self) -> None:
        """origin_country containing ``{"iso_3166_1": ...}`` dicts is extracted (lines 187-190)."""
        config = MagicMock()
        c = _make_classifier(config=config, needs_keywords=False)
        api_data = {
            "origin_country": [
                {"iso_3166_1": "JP"},
                {"iso_639_1": "fr"},  # falls back to iso_639_1
                {"unrelated": "ignored"},  # produces no entry
                "DE",  # plain string also handled
            ],
        }

        with patch("personalscraper.scraper.scraper._classifier") as mock_clf:
            mock_clf.classify.return_value = ("anime", "country")
            c._classify_item("movie", Path("/tmp/x"), "title", api_data, tmdb_id=None)

        kwargs = mock_clf.classify.call_args.kwargs
        assert kwargs["origin_country"] == ["JP", "fr", "DE"]

    def test_classify_returns_none_when_classifier_says_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """When classifier.classify() returns None, _classify_item returns None and warns."""
        config = MagicMock()
        c = _make_classifier(config=config, needs_keywords=False)

        with patch("personalscraper.scraper.scraper._classifier") as mock_clf:
            mock_clf.classify.return_value = (None, "no_match")
            with caplog.at_level("WARNING"):
                result = c._classify_item("movie", Path("/tmp/x"), "title", {}, tmdb_id=None)

        assert result is None
        assert "classify_no_category" in caplog.text


class TestResolveTitleNoTranslationBranch:
    """Cover the title==original branch logging (lines 254-255)."""

    def test_local_title_equals_original_but_differs_from_match_returns_match(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When local_title == original_title AND local_title != match_title, log + return match."""
        c = _make_classifier(prefer_local=True)
        api_data = {
            "title": "Same Title",
            "original_title": "Same Title",
        }

        with caplog.at_level("DEBUG"):
            result = c._resolve_title("Different Match", api_data, "movie")

        assert result == "Different Match"
        assert "title_no_translation" in caplog.text
