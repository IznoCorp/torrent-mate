"""Tests for the :class:`RottenTomatoesClient` façade over :class:`OMDbAdapter`.

The façade is intentionally narrow — it implements only the
:class:`RatingProvider` capability — so the tests focus on the
filter / wrap semantics : how the façade extracts the
``rotten_tomatoes``-source rows from a heterogeneous OMDb response and
how it surfaces hard-failure cases as
:exc:`ProviderFeatureUnavailable`.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api._helpers import ProviderFeatureUnavailable
from personalscraper.api.metadata._base import Notations
from personalscraper.api.metadata._contracts import (
    IDValidator,
    RatingProvider,
)
from personalscraper.api.metadata.rotten_tomatoes import RottenTomatoesClient


def _imdb_notation() -> Notations:
    return Notations(provider="omdb", source="imdb", score=8.5, votes_count=1)


def _rt_notation(score: float = 94.0) -> Notations:
    return Notations(provider="omdb", source="rotten_tomatoes", score=score, votes_count=0)


# ---------------------------------------------------------------------------
# Capability composition
# ---------------------------------------------------------------------------


def test_rt_client_satisfies_rating_provider_only() -> None:
    """The façade composes :class:`RatingProvider`, *nothing else*.

    Rotten Tomatoes data through OMDb does not include a separate
    RT-side identifier, so the façade deliberately does NOT compose
    :class:`IDValidator`. This test pins that minimality in place.
    """
    client = RottenTomatoesClient(backend=MagicMock())
    assert isinstance(client, RatingProvider)
    assert not isinstance(client, IDValidator)


# ---------------------------------------------------------------------------
# get_rating
# ---------------------------------------------------------------------------


def test_rt_client_get_rating_parses_rotten_tomatoes_entry() -> None:
    """``get_rating`` returns the ``rotten_tomatoes`` row from a mixed payload."""
    backend = MagicMock()
    backend.get_notations.return_value = [_imdb_notation(), _rt_notation(91.0)]
    client = RottenTomatoesClient(backend=backend)

    ratings = client.get_rating("tt0468569")
    assert ratings is not None
    assert len(ratings) == 1
    assert ratings[0].source == "rotten_tomatoes"
    assert ratings[0].score == 91.0


def test_rt_client_get_rating_returns_none_when_no_rt_entry() -> None:
    """OMDb has ratings but no RT row → façade returns ``None``."""
    backend = MagicMock()
    backend.get_notations.return_value = [_imdb_notation()]
    client = RottenTomatoesClient(backend=backend)

    assert client.get_rating("tt0468569") is None


def test_rt_client_get_rating_returns_none_when_backend_returns_none() -> None:
    """OMDb returns no rating data at all → façade returns ``None``."""
    backend = MagicMock()
    backend.get_notations.return_value = None
    client = RottenTomatoesClient(backend=backend)

    assert client.get_rating("tt0468569") is None


def test_rt_client_get_rating_wraps_backend_error_as_unavailable() -> None:
    """OMDb 5xx → :exc:`ProviderFeatureUnavailable` with provider / feature set."""
    backend = MagicMock()
    backend.get_notations.side_effect = ApiError(provider="omdb", http_status=500, message="boom")
    client = RottenTomatoesClient(backend=backend)

    with pytest.raises(ProviderFeatureUnavailable) as exc_info:
        client.get_rating("tt0468569")
    assert exc_info.value.provider == "rotten_tomatoes"
    assert exc_info.value.feature == "get_rating"


def test_rt_client_get_rating_propagates_omdb_quota_exhausted() -> None:
    """``OmdbQuotaExhausted`` from the backend bypasses ``ApiError`` wrapping.

    Same contract as IMDb: the typed quota exception must reach the
    caller un-wrapped so the rating pass can stop on quota signals
    instead of degrading into generic ProviderFeatureUnavailable.
    """
    from personalscraper.api.metadata.omdb import OmdbQuotaExhausted  # noqa: PLC0415

    backend = MagicMock()
    backend.get_notations.side_effect = OmdbQuotaExhausted(pre_call=True)
    client = RottenTomatoesClient(backend=backend)

    with pytest.raises(OmdbQuotaExhausted) as exc_info:
        client.get_rating("tt0468569")
    assert exc_info.value.pre_call is True
    assert not isinstance(exc_info.value, ProviderFeatureUnavailable)
