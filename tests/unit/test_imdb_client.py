"""Tests for the :class:`IMDbClient` façade over :class:`OMDbAdapter`.

The façade delegates every HTTP call to an injected OMDb backend, so
the tests use a :class:`unittest.mock.MagicMock` to stand in for
:class:`OMDbAdapter`. The contract under test is the *projection*
layer : how the façade filters and re-shapes the OMDb response into
the IMDb business semantics required by the scraper.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api._helpers import ProviderFeatureUnavailable
from personalscraper.api.metadata._base import MediaDetails, Notations
from personalscraper.api.metadata._contracts import (
    IDCrossRef,
    IDValidator,
    RatingProvider,
)
from personalscraper.api.metadata.imdb import IMDbClient


def _media_details(title: str = "The Dark Knight", year: int | None = 2008) -> MediaDetails:
    """Build a minimally populated :class:`MediaDetails` for backend mocks."""
    return MediaDetails(
        provider="omdb",
        provider_id="tt0468569",
        title=title,
        year=year,
        overview="",
        genres=[],
        runtime_minutes=152,
        rating=9.0,
        images=[],
        external_ids={"imdb": "tt0468569"},
    )


def _imdb_notation(score: float = 9.0) -> Notations:
    """Build an IMDb-source :class:`Notations` entry."""
    return Notations(provider="omdb", source="imdb", score=score, votes_count=1_000_000)


def _rt_notation(score: float = 94.0) -> Notations:
    """Build a Rotten-Tomatoes-source :class:`Notations` entry."""
    return Notations(provider="omdb", source="rotten_tomatoes", score=score, votes_count=0)


# ---------------------------------------------------------------------------
# Capability composition
# ---------------------------------------------------------------------------


def test_imdb_client_composes_expected_capabilities() -> None:
    """``IMDbClient`` satisfies :class:`IDValidator`, :class:`RatingProvider`, :class:`IDCrossRef`.

    Structural-subtyping check via :func:`isinstance` (the capability
    protocols are ``@runtime_checkable``). The composition is asserted
    on a concrete instance with a mock backend — no HTTP traffic.
    """
    client = IMDbClient(backend=MagicMock())
    assert isinstance(client, IDValidator)
    assert isinstance(client, RatingProvider)
    assert isinstance(client, IDCrossRef)


# ---------------------------------------------------------------------------
# validate_id
# ---------------------------------------------------------------------------


def test_imdb_client_validate_id_match() -> None:
    """Title + year match → ``validate_id`` returns ``True``."""
    backend = MagicMock()
    backend.get_details.return_value = _media_details()
    client = IMDbClient(backend=backend)

    assert client.validate_id("tt0468569", "The Dark Knight", 2008) is True


def test_imdb_client_validate_id_match_is_case_and_whitespace_insensitive() -> None:
    """Case + extra whitespace differences must not poison the match."""
    backend = MagicMock()
    backend.get_details.return_value = _media_details(title="The Dark Knight")
    client = IMDbClient(backend=backend)

    assert client.validate_id("tt0468569", "  the   DARK   knight  ", 2008) is True


def test_imdb_client_validate_id_reject_title_mismatch() -> None:
    """Wholly different title → ``False``."""
    backend = MagicMock()
    backend.get_details.return_value = _media_details(title="Batman Begins")
    client = IMDbClient(backend=backend)

    assert client.validate_id("tt0468569", "The Dark Knight", 2008) is False


def test_imdb_client_validate_id_reject_year_mismatch() -> None:
    """Title matches but year mismatches → ``False``."""
    backend = MagicMock()
    backend.get_details.return_value = _media_details(year=2010)
    client = IMDbClient(backend=backend)

    assert client.validate_id("tt0468569", "The Dark Knight", 2008) is False


def test_imdb_client_validate_id_year_none_skips_year_check() -> None:
    """``expected_year=None`` skips the year comparison."""
    backend = MagicMock()
    backend.get_details.return_value = _media_details(year=2010)
    client = IMDbClient(backend=backend)

    assert client.validate_id("tt0468569", "The Dark Knight", None) is True


def test_imdb_client_validate_id_backend_failure_returns_false() -> None:
    """Backend :class:`ApiError` → ``validate_id`` returns ``False``, never raises.

    A hard OMDb failure during re-validation is operationally the same
    as a mismatch : the scraper cannot trust the ID. Surfacing the
    exception would force every call site to wrap the validator —
    swallowing it here keeps the contract tight.
    """
    backend = MagicMock()
    backend.get_details.side_effect = ApiError(provider="omdb", http_status=404, message="not found")
    client = IMDbClient(backend=backend)

    assert client.validate_id("tt9999999", "Title", 2020) is False


# ---------------------------------------------------------------------------
# get_rating
# ---------------------------------------------------------------------------


def test_imdb_client_get_rating_filters_to_imdb_source() -> None:
    """``get_rating`` drops non-IMDb entries even when OMDb returns several."""
    backend = MagicMock()
    backend.get_notations.return_value = [_imdb_notation(), _rt_notation()]
    client = IMDbClient(backend=backend)

    ratings = client.get_rating("tt0468569")
    assert ratings is not None
    assert len(ratings) == 1
    assert ratings[0].source == "imdb"


def test_imdb_client_get_rating_returns_none_when_backend_returns_none() -> None:
    """OMDb has no rating at all → façade returns ``None``."""
    backend = MagicMock()
    backend.get_notations.return_value = None
    client = IMDbClient(backend=backend)

    assert client.get_rating("tt0468569") is None


def test_imdb_client_get_rating_returns_none_when_no_imdb_entry() -> None:
    """OMDb has ratings but none from IMDb → façade returns ``None``."""
    backend = MagicMock()
    backend.get_notations.return_value = [_rt_notation()]
    client = IMDbClient(backend=backend)

    assert client.get_rating("tt0468569") is None


def test_imdb_client_get_rating_wraps_backend_error_as_unavailable() -> None:
    """A hard OMDb error becomes :exc:`ProviderFeatureUnavailable`.

    Callers iterating heterogeneous providers expect to swallow
    ``ProviderFeatureUnavailable`` and continue — wrapping the
    :class:`ApiError` lets the helper functions (``gather_ratings``)
    do their job without bespoke exception handling per provider.
    """
    backend = MagicMock()
    backend.get_notations.side_effect = ApiError(provider="omdb", http_status=500, message="boom")
    client = IMDbClient(backend=backend)

    with pytest.raises(ProviderFeatureUnavailable) as exc_info:
        client.get_rating("tt0468569")
    assert exc_info.value.provider == "imdb"
    assert exc_info.value.feature == "get_rating"


# ---------------------------------------------------------------------------
# get_cross_refs
# ---------------------------------------------------------------------------


def test_imdb_client_get_cross_refs_returns_empty_dict() -> None:
    """OMDb cannot resolve cross-refs from IMDb input — façade returns ``{}``.

    Documented limitation : the contract is preserved for symmetry
    with the other façades, but the value is always empty.
    """
    client = IMDbClient(backend=MagicMock())
    assert client.get_cross_refs("tt0468569") == {}


# ---------------------------------------------------------------------------
# get_by_id (full payload pass-through)
# ---------------------------------------------------------------------------


def test_imdb_client_get_by_id_passes_through_backend() -> None:
    """``get_by_id`` returns the backend's :class:`MediaDetails` unmodified."""
    backend = MagicMock()
    details = _media_details()
    backend.get_details.return_value = details
    client = IMDbClient(backend=backend)

    out = client.get_by_id("tt0468569", media_type=MediaType.MOVIE)
    assert out is details
    backend.get_details.assert_called_once_with("tt0468569", media_type=MediaType.MOVIE)
