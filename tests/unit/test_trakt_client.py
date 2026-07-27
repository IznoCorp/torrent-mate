"""Tests for Trakt client — api/metadata/trakt.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api.metadata._base import MediaDetails, Recommendation, SearchResult
from personalscraper.api.metadata.trakt import TraktClient


def _make_client() -> TraktClient:
    """Build a TraktClient with a mock transport."""
    transport = MagicMock()
    return TraktClient(transport)


_INCEPTION_IDS = {
    "trakt": 16662,
    "slug": "inception-2010",
    "imdb": "tt1375666",
    "tmdb": 27205,
}


class TestTraktClientSearch:
    """TraktClient.search() — mocked HTTP."""

    def test_search_returns_typed_results(self) -> None:
        """search() unwraps {movie: {...}} and returns SearchResult list."""
        client = _make_client()
        client._transport.get.return_value = [  # type: ignore[attr-defined]
            {
                "score": 578730123365189600,
                "type": "movie",
                "movie": {
                    "title": "Inception",
                    "year": 2010,
                    "ids": _INCEPTION_IDS,
                    "overview": "Cobb, a skilled thief...",
                },
            },
        ]
        results = client.search("Inception")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Inception"
        assert results[0].year == 2010
        assert results[0].provider_id == "inception-2010"
        assert results[0].media_type == "movie"

    def test_search_tv_uses_show_endpoint(self) -> None:
        """search() uses /search/show and unwraps {show: {...}}."""
        client = _make_client()
        client._transport.get.return_value = [  # type: ignore[attr-defined]
            {
                "type": "show",
                "show": {
                    "title": "Breaking Bad",
                    "year": 2008,
                    "ids": {"slug": "breaking-bad", "imdb": "tt0903747", "trakt": 1388},
                },
            },
        ]
        results = client.search("Breaking Bad", media_type="tv")
        assert len(results) == 1
        assert results[0].media_type == "tv"
        call_args = client._transport.get.call_args  # type: ignore[attr-defined]
        assert "/search/show" in str(call_args)

    def test_search_with_year(self) -> None:
        """search() passes year as query parameter."""
        client = _make_client()
        client._transport.get.return_value = []  # type: ignore[attr-defined]
        client.search("Inception", year=2010)
        call_args = client._transport.get.call_args  # type: ignore[attr-defined]
        assert call_args.kwargs["params"]["year"] == "2010"


class TestTraktClientGetDetails:
    """TraktClient.get_movie() / get_tv() detail fetch — mocked HTTP."""

    def test_get_movie_returns_media_details(self) -> None:
        """get_movie() returns MediaDetails and hits /movies/{id}."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "title": "Inception",
            "year": 2010,
            "ids": _INCEPTION_IDS,
            "overview": "Cobb, a skilled thief...",
            "runtime": 148,
            "genres": ["action", "adventure", "science-fiction"],
            "rating": 8.62414,
            "original_title": "Inception",
            "images": {"poster": ["media.trakt.tv/poster.jpg"], "fanart": [], "banner": []},
        }
        details = client.get_movie("inception-2010")
        assert isinstance(details, MediaDetails)
        assert details.title == "Inception"
        assert details.year == 2010
        assert details.provider_id == "inception-2010"
        assert details.runtime_minutes == 148
        assert len(details.genres) == 3
        assert details.rating == 8.62414
        assert details.original_title == "Inception"
        assert details.external_ids["imdb"] == "tt1375666"
        assert client._transport.get.call_args.args[0] == "/movies/inception-2010"  # type: ignore[attr-defined]

    def test_get_tv_hits_shows_endpoint(self) -> None:
        """get_tv() routes to /shows/{id} (the media_type branch)."""
        client = _make_client()
        client._transport.get.return_value = {"title": "Test", "year": 2020, "ids": {}}  # type: ignore[attr-defined]
        client.get_tv("some-show")
        assert client._transport.get.call_args.args[0] == "/shows/some-show"  # type: ignore[attr-defined]

    def test_get_movie_passes_extended_full(self) -> None:
        """The detail fetch always sends extended=full."""
        client = _make_client()
        client._transport.get.return_value = {"title": "Test", "year": 2020, "ids": {}}  # type: ignore[attr-defined]
        client.get_movie("test-slug")
        call_args = client._transport.get.call_args  # type: ignore[attr-defined]
        assert call_args.kwargs["params"]["extended"] == "full"


class TestTraktClientGetNotations:
    """TraktClient.get_notations() — mocked HTTP."""

    def test_get_notations_returns_list(self) -> None:
        """get_notations() returns [Notations(source="trakt")]."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "rating": 8.62414,
            "votes": 86023,
            "distribution": {"1": 377, "10": 27790},
        }
        notations = client.get_notations("inception-2010")
        assert notations is not None
        assert len(notations) == 1
        assert notations[0].source == "trakt"
        assert notations[0].score == 8.62414
        assert notations[0].votes_count == 86023

    def test_get_notations_no_rating_returns_none(self) -> None:
        """get_notations() returns None when rating is missing."""
        client = _make_client()
        client._transport.get.return_value = {"votes": 0}  # type: ignore[attr-defined]
        assert client.get_notations("unknown") is None


class TestTraktClientGetRecommendations:
    """TraktClient.get_recommendations() — mocked HTTP."""

    def test_get_recommendations_returns_list(self) -> None:
        """get_recommendations() parses /related response."""
        client = _make_client()
        client._transport.get.return_value = [  # type: ignore[attr-defined]
            {
                "title": "Interstellar",
                "year": 2014,
                "ids": {"slug": "interstellar-2014", "imdb": "tt0816692", "trakt": 157336},
            },
            {
                "title": "The Prestige",
                "year": 2006,
                "ids": {"slug": "the-prestige-2006", "imdb": "tt0482571", "trakt": 18471},
            },
        ]
        results = client.get_recommendations("inception-2010")
        assert len(results) == 2
        assert isinstance(results[0], Recommendation)
        assert results[0].title == "Interstellar"
        assert results[0].year == 2014
        assert results[1].title == "The Prestige"


class TestTraktClientPolicy:
    """TraktClient.policy() — transport configuration."""

    def test_policy_includes_auth_headers(self) -> None:
        """policy() creates TransportPolicy with dual headers."""
        from personalscraper.api.transport._policy import TransportPolicy

        policy = TraktClient.policy("test_client_id")
        assert isinstance(policy, TransportPolicy)
        assert policy.provider_name == "trakt"
        assert policy.base_url == "https://api.trakt.tv"
        assert policy.auth.auth_params() == {}  # header mode, no query params
        assert policy.extra_headers == {"trakt-api-version": "2"}


class TestSearchParsingEdgeCases:
    """Edge cases for search response parsing."""

    def test_id_resolution_priority(self) -> None:
        """_resolve_id prefers slug > imdb > trakt."""
        client = _make_client()
        client._transport.get.return_value = [  # type: ignore[attr-defined]
            {
                "type": "movie",
                "movie": {
                    "title": "Test",
                    "year": 2020,
                    "ids": {"trakt": 99999},
                },
            },
        ]
        results = client.search("Test")
        assert results[0].provider_id == "99999"

    def test_empty_search_results(self) -> None:
        """search() returns empty list for no results."""
        client = _make_client()
        client._transport.get.return_value = []  # type: ignore[attr-defined]
        assert client.search("asdfghqwerty") == []
