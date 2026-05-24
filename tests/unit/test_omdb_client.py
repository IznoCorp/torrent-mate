"""Tests for OMDB client — api/metadata/omdb.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.metadata._base import MediaDetails, SearchResult
from personalscraper.api.metadata._omdb_quota import OmdbQuotaTracker
from personalscraper.api.metadata.omdb import (
    OMDBClient,
    OmdbQuotaExhausted,
    _parse_rating_value,
    _parse_runtime,
    _parse_year,
    _sentinel,
)


def _make_client() -> OMDBClient:
    """Build an OMDBClient with a mock transport."""
    transport = MagicMock()
    return OMDBClient(transport)


class TestOMDBClientSearch:
    """OMDBClient.search() — mocked HTTP."""

    def test_search_returns_typed_results(self) -> None:
        """search() returns list[SearchResult] with typed fields."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Search": [
                {
                    "Title": "Inception",
                    "Year": "2010",
                    "imdbID": "tt1375666",
                    "Type": "movie",
                    "Poster": "https://example.com/poster.jpg",
                },
            ],
            "totalResults": "1",
            "Response": "True",
        }
        results = client.search("Inception")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Inception"
        assert results[0].year == 2010
        assert results[0].provider_id == "tt1375666"
        assert results[0].media_type == "movie"

    def test_search_passes_type_filter(self) -> None:
        """search() sends type=series for media_type='tv'."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Search": [],
            "totalResults": "0",
            "Response": "True",
        }
        client.search("Breaking Bad", media_type="tv")
        call_args = client._transport.get.call_args  # type: ignore[attr-defined]
        assert call_args.kwargs["params"]["type"] == "series"

    def test_search_with_year(self) -> None:
        """search() sends y= param when year is given."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Search": [],
            "totalResults": "0",
            "Response": "True",
        }
        client.search("Inception", year=2010)
        call_args = client._transport.get.call_args  # type: ignore[attr-defined]
        assert call_args.kwargs["params"]["y"] == "2010"

    def test_search_response_false_raises_api_error(self) -> None:
        """search() raises ApiError when Response is False."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Response": "False",
            "Error": "Movie not found!",
        }
        with pytest.raises(ApiError, match="Movie not found!"):
            client.search("asdfghqwerty12345")


class TestOMDBClientGetDetails:
    """OMDBClient.get_details() — mocked HTTP."""

    def test_get_details_returns_media_details(self) -> None:
        """get_details() returns MediaDetails with parsed fields."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Title": "Inception",
            "Year": "2010",
            "Rated": "PG-13",
            "Runtime": "148 min",
            "Genre": "Action, Adventure, Sci-Fi",
            "Plot": "A thief who steals corporate secrets...",
            "Poster": "https://example.com/poster.jpg",
            "imdbRating": "8.8",
            "imdbID": "tt1375666",
            "Type": "movie",
            "Response": "True",
        }
        details = client.get_details("tt1375666")
        assert isinstance(details, MediaDetails)
        assert details.title == "Inception"
        assert details.year == 2010
        assert details.runtime_minutes == 148
        assert details.provider_id == "tt1375666"
        assert len(details.genres) == 3
        assert details.rating == 8.8
        assert len(details.images) == 1
        assert details.images[0].type == "poster"

    def test_get_details_na_sentinel(self) -> None:
        """get_details() converts 'N/A' fields to None/empty."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Title": "Unknown",
            "Year": "2020",
            "Runtime": "N/A",
            "Genre": "N/A",
            "Plot": "N/A",
            "Poster": "N/A",
            "imdbRating": "N/A",
            "imdbID": "tt1234567",
            "Type": "movie",
            "Response": "True",
        }
        details = client.get_details("tt1234567")
        assert details.runtime_minutes is None
        assert details.genres == []
        assert details.images == []
        assert details.rating is None

    def test_get_details_response_false_raises_api_error(self) -> None:
        """get_details() raises ApiError when Response is False."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Response": "False",
            "Error": "Error getting data.",
        }
        with pytest.raises(ApiError, match="Error getting data"):
            client.get_details("tt0000000")


class TestOMDBClientGetNotations:
    """OMDBClient.get_notations() — mocked HTTP."""

    def test_get_notations_returns_list(self) -> None:
        """get_notations() returns list[Notations] for all three sources."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Title": "Inception",
            "Ratings": [
                {"Source": "Internet Movie Database", "Value": "8.8/10"},
                {"Source": "Rotten Tomatoes", "Value": "87%"},
                {"Source": "Metacritic", "Value": "74/100"},
            ],
            "Response": "True",
        }
        notations = client.get_notations("tt1375666")
        assert notations is not None
        assert len(notations) == 3
        assert notations[0].source == "imdb"
        assert notations[0].score == 8.8
        assert notations[1].source == "rotten_tomatoes"
        assert notations[1].score == 8.7
        assert notations[2].source == "metacritic"
        assert notations[2].score == 7.4

    def test_get_notations_empty_returns_none(self) -> None:
        """get_notations() returns None when Ratings[] is empty."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Title": "Some Movie",
            "Ratings": [],
            "Response": "True",
        }
        assert client.get_notations("tt1234567") is None

    def test_get_notations_response_false_raises_api_error(self) -> None:
        """get_notations() raises ApiError when Response is False."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "Response": "False",
            "Error": "Movie not found!",
        }
        with pytest.raises(ApiError, match="Movie not found!"):
            client.get_notations("tt0000000")


class TestOMDBClientGetRecommendations:
    """OMDBClient.get_recommendations() — always returns empty."""

    def test_get_recommendations_returns_empty(self) -> None:
        """get_recommendations() returns []."""
        client = _make_client()
        assert client.get_recommendations("tt1375666") == []


class TestOMDBClientPolicy:
    """OMDBClient.policy() — transport configuration."""

    def test_policy_includes_api_key(self) -> None:
        """policy() creates TransportPolicy with query-param ApiKeyAuth."""
        from personalscraper.api.transport._policy import TransportPolicy

        policy = OMDBClient.policy("test_key_123")
        assert isinstance(policy, TransportPolicy)
        assert policy.provider_name == "omdb"
        assert policy.base_url == "http://www.omdbapi.com"
        # Verify auth params for query string
        assert policy.auth.auth_params() == {"apikey": "test_key_123"}


class TestParseYear:
    """Year parsing from OMDB formats."""

    def test_simple_year(self) -> None:
        """Parses '2010'."""
        assert _parse_year("2010") == 2010

    def test_range_ended(self) -> None:
        """Parses '2008–2013' → first year."""
        assert _parse_year("2008–2013") == 2008

    def test_range_ongoing(self) -> None:
        """Parses '1989–' → first year."""
        assert _parse_year("1989–") == 1989

    def test_none(self) -> None:
        """Returns None for None."""
        assert _parse_year(None) is None

    def test_empty(self) -> None:
        """Returns None for empty string."""
        assert _parse_year("") is None


class TestParseRuntime:
    """Runtime parsing from OMDB format."""

    def test_normal(self) -> None:
        """Parses '148 min'."""
        assert _parse_runtime("148 min") == 148

    def test_na(self) -> None:
        """Returns None for 'N/A'."""
        assert _parse_runtime("N/A") is None

    def test_none(self) -> None:
        """Returns None for None."""
        assert _parse_runtime(None) is None


class TestParseRatingValue:
    """Rating value normalization to 0-10."""

    def test_imdb_format(self) -> None:
        """Parses '8.8/10'."""
        assert _parse_rating_value("8.8/10") == 8.8

    def test_rt_format(self) -> None:
        """Parses '87%'."""
        assert _parse_rating_value("87%") == 8.7

    def test_metacritic_format(self) -> None:
        """Parses '74/100' → normalized to 0-10."""
        assert _parse_rating_value("74/100") == 7.4

    def test_integer(self) -> None:
        """Parses plain number string."""
        assert _parse_rating_value("8.0") == 8.0


class TestQuotaExhaustionDetection:
    """_is_quota_exhaustion() pins the upstream error string for canary detection."""

    def test_exact_upstream_payload_matches(self) -> None:
        """Matches the exact error message OMDB returns for quota exhaustion.

        Canary: if OMDB rewords this error, this test fails and alerts us
        that the substring match in _is_quota_exhaustion needs updating.
        """
        client = _make_client()
        exc = ApiError(
            provider="omdb",
            http_status=401,
            message="Request limit reached!",
        )
        assert client._is_quota_exhaustion(exc) is True

    def test_case_insensitive_match(self) -> None:
        """Substring match is case-insensitive (exc.message.lower())."""
        client = _make_client()
        exc = ApiError(
            provider="omdb",
            http_status=401,
            message="REQUEST LIMIT REACHED!",
        )
        assert client._is_quota_exhaustion(exc) is True

    def test_wrong_status_not_matched(self) -> None:
        """Does NOT match when HTTP status is not 401."""
        client = _make_client()
        exc = ApiError(
            provider="omdb",
            http_status=429,
            message="Request limit reached!",
        )
        assert client._is_quota_exhaustion(exc) is False

    def test_wrong_message_not_matched(self) -> None:
        """Does NOT match when error message is unrelated."""
        client = _make_client()
        exc = ApiError(
            provider="omdb",
            http_status=401,
            message="Invalid API key!",
        )
        assert client._is_quota_exhaustion(exc) is False

    def test_unexpected_message_not_matched(self) -> None:
        """Does NOT match when message differs (catches OMDB rewording)."""
        client = _make_client()
        exc = ApiError(
            provider="omdb",
            http_status=401,
            message="Daily quota exceeded!",
        )
        assert client._is_quota_exhaustion(exc) is False


class TestSentinel:
    """'N/A' sentinel handling."""

    def test_na(self) -> None:
        """Returns None for 'N/A'."""
        assert _sentinel("N/A") is None

    def test_normal_value(self) -> None:
        """Returns the original string."""
        assert _sentinel("Inception") == "Inception"


class TestQuotaExhaustionCanaryFixture:
    """Pinned byte-level payload fixture so substring detection stays anchored.

    If OMDB rewords the quota-exhaustion error, the fixture must be
    deliberately updated (making the change visible in code review).
    """

    def test_recorded_fixture_matches(self) -> None:
        """Parses recorded OMDB 401 response and asserts _is_quota_exhaustion matches."""
        fixture = Path(__file__).parent / "fixtures" / "omdb_quota_exhausted_response.json"
        payload = json.loads(fixture.read_text())

        client = _make_client()
        exc = ApiError(
            provider="omdb",
            http_status=401,
            message=payload["Error"],
        )
        assert client._is_quota_exhaustion(exc) is True


class TestOmdbQuotaIntegration:
    """Call-site integration: quota tracker ↔ OMDbAdapter."""

    def test_get_details_raises_OmdbQuotaExhausted_when_tracker_skips(self, tmp_path: Path) -> None:
        """get_details raises OmdbQuotaExhausted(pre_call=True) when tracker blocks the call."""
        transport = MagicMock()
        tracker = OmdbQuotaTracker(state_path=tmp_path / ".quota.json")
        tracker.mark_exhausted("test")
        client = OMDBClient(transport, quota_tracker=tracker)

        with pytest.raises(OmdbQuotaExhausted) as excinfo:
            client.get_details("tt1375666")
        assert excinfo.value.pre_call is True
        assert excinfo.value.http_status == 0

    def test_get_notations_raises_OmdbQuotaExhausted_when_tracker_skips(self, tmp_path: Path) -> None:
        """get_notations propagates OmdbQuotaExhausted so façades can discriminate."""
        transport = MagicMock()
        tracker = OmdbQuotaTracker(state_path=tmp_path / ".quota.json")
        tracker.mark_exhausted("test")
        client = OMDBClient(transport, quota_tracker=tracker)

        with pytest.raises(OmdbQuotaExhausted) as excinfo:
            client.get_notations("tt1375666")
        assert excinfo.value.pre_call is True

    def test_search_returns_empty_when_tracker_skips(self, tmp_path: Path) -> None:
        """Search swallows OmdbQuotaExhausted into [] (legacy soft contract)."""
        transport = MagicMock()
        tracker = OmdbQuotaTracker(state_path=tmp_path / ".quota.json")
        tracker.mark_exhausted("test")
        client = OMDBClient(transport, quota_tracker=tracker)

        assert client.search("Inception") == []

    def test_quota_aware_get_raises_when_tracker_marked_exhausted(self, tmp_path: Path) -> None:
        """_quota_aware_get raises OmdbQuotaExhausted(pre_call=True) when blocked."""
        transport = MagicMock()
        tracker = OmdbQuotaTracker(state_path=tmp_path / ".quota.json")
        tracker.mark_exhausted("test")
        client = OMDBClient(transport, quota_tracker=tracker)

        with pytest.raises(OmdbQuotaExhausted) as excinfo:
            client._quota_aware_get({"i": "tt1375666"}, method="get_notations", item_id="tt1375666")
        assert excinfo.value.pre_call is True

    def test_quota_aware_get_marks_exhausted_on_real_apierror(self, tmp_path: Path) -> None:
        """Real upstream 401 → tracker marked exhausted AND OmdbQuotaExhausted raised (pre_call=False)."""
        transport = MagicMock()
        transport.get.side_effect = ApiError(
            provider="omdb",
            http_status=401,
            message="Request limit reached!",
        )
        tracker = OmdbQuotaTracker(state_path=tmp_path / ".quota.json")
        client = OMDBClient(transport, quota_tracker=tracker)

        with pytest.raises(OmdbQuotaExhausted) as excinfo:
            client._quota_aware_get({"i": "tt1375666"}, method="get_notations", item_id="tt1375666")
        assert excinfo.value.pre_call is False
        assert excinfo.value.http_status == 401
        assert tracker.status().exhausted is True

    def test_non_quota_apierror_propagates_unchanged(self, tmp_path: Path) -> None:
        """Non-quota ApiError (e.g. 500) is NOT swallowed as OmdbQuotaExhausted."""
        transport = MagicMock()
        transport.get.side_effect = ApiError(
            provider="omdb",
            http_status=500,
            message="Internal Server Error",
        )
        tracker = OmdbQuotaTracker(state_path=tmp_path / ".quota.json")
        client = OMDBClient(transport, quota_tracker=tracker)

        with pytest.raises(ApiError) as excinfo:
            client._quota_aware_get({"i": "tt1375666"}, method="get_notations", item_id="tt1375666")
        assert not isinstance(excinfo.value, OmdbQuotaExhausted)
        assert tracker.status().exhausted is False


class TestImdbFacadeQuotaPropagation:
    """Façade re-raise discipline: IMDb-side OmdbQuotaExhausted bypasses except ApiError."""

    def _build(self, tmp_path: Path, *, mark_exhausted: bool):
        """Build (façade, tracker) pair with the tracker optionally pre-exhausted."""
        from personalscraper.api.metadata.imdb import IMDbClient

        transport = MagicMock()
        tracker = OmdbQuotaTracker(state_path=tmp_path / ".quota.json")
        if mark_exhausted:
            tracker.mark_exhausted("test")
        backend = OMDBClient(transport, quota_tracker=tracker)
        return IMDbClient(backend), transport

    def test_validate_id_propagates_OmdbQuotaExhausted(self, tmp_path: Path) -> None:
        """IMDbClient.validate_id re-raises OmdbQuotaExhausted (no ApiError swallow)."""
        client, _ = self._build(tmp_path, mark_exhausted=True)
        with pytest.raises(OmdbQuotaExhausted):
            client.validate_id("tt1375666", "Inception", 2010)

    def test_get_rating_propagates_OmdbQuotaExhausted(self, tmp_path: Path) -> None:
        """IMDbClient.get_rating re-raises OmdbQuotaExhausted (no ProviderFeatureUnavailable wrap)."""
        client, _ = self._build(tmp_path, mark_exhausted=True)
        with pytest.raises(OmdbQuotaExhausted):
            client.get_rating("tt1375666")

    def test_get_rating_returns_none_on_non_quota_ApiError(self, tmp_path: Path) -> None:
        """IMDbClient.get_rating still wraps non-quota ApiError as ProviderFeatureUnavailable."""
        from personalscraper.api._helpers import ProviderFeatureUnavailable

        client, transport = self._build(tmp_path, mark_exhausted=False)
        transport.get.side_effect = ApiError(
            provider="omdb",
            http_status=500,
            message="Internal Server Error",
        )
        with pytest.raises(ProviderFeatureUnavailable):
            client.get_rating("tt1375666")


class TestRtFacadeQuotaPropagation:
    """Façade re-raise discipline: RT-side OmdbQuotaExhausted bypasses except ApiError."""

    def _build(self, tmp_path: Path, *, mark_exhausted: bool):
        """Build (façade, tracker) pair with the tracker optionally pre-exhausted."""
        from personalscraper.api.metadata.rotten_tomatoes import RottenTomatoesClient

        transport = MagicMock()
        tracker = OmdbQuotaTracker(state_path=tmp_path / ".quota.json")
        if mark_exhausted:
            tracker.mark_exhausted("test")
        backend = OMDBClient(transport, quota_tracker=tracker)
        return RottenTomatoesClient(backend), transport

    def test_get_rating_propagates_OmdbQuotaExhausted(self, tmp_path: Path) -> None:
        """RottenTomatoesClient.get_rating re-raises OmdbQuotaExhausted (no ProviderFeatureUnavailable wrap)."""
        client, _ = self._build(tmp_path, mark_exhausted=True)
        with pytest.raises(OmdbQuotaExhausted):
            client.get_rating("tt1375666")

    def test_get_rating_returns_none_on_non_quota_ApiError(self, tmp_path: Path) -> None:
        """RottenTomatoesClient.get_rating still wraps non-quota ApiError as ProviderFeatureUnavailable."""
        from personalscraper.api._helpers import ProviderFeatureUnavailable

        client, transport = self._build(tmp_path, mark_exhausted=False)
        transport.get.side_effect = ApiError(
            provider="omdb",
            http_status=500,
            message="Internal Server Error",
        )
        with pytest.raises(ProviderFeatureUnavailable):
            client.get_rating("tt1375666")
