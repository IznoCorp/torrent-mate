"""Metadata client capability composition tests (provider-ids feature).

Pins explicit Protocol inheritance for every concrete metadata client
(``TMDBClient``, ``TVDBClient``, ``TraktClient``, ``IMDbClient``,
``RottenTomatoesClient``).

Two flavors of assertion are used:

- **isinstance** — for capabilities the class genuinely composes. Proves
  the runtime ``@runtime_checkable`` Protocol check returns ``True``.
- **MRO inspection** — for capabilities the class deliberately omits.
  Cannot use ``isinstance`` here because :class:`MetadataClient` ships
  ``NotImplementedError``-raising stubs for several optional methods
  (``get_artwork_urls``, ``get_keywords``, ``get_videos``,
  ``get_recommendations``), so any subclass *structurally* satisfies
  those Protocols even when the capability is missing in spirit. The
  source of truth is the explicit inheritance list, captured by
  ``__mro__``.
"""

from __future__ import annotations

from typing import Protocol
from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata._contracts import (
    ArtworkProvider,
    EpisodeFetcher,
    IDCrossRef,
    IDValidator,
    KeywordProvider,
    MovieDetailsProvider,
    RatingProvider,
    RecommendationProvider,
    Searchable,
    TvDetailsProvider,
    VideoProvider,
)
from personalscraper.api.metadata.imdb import IMDbClient
from personalscraper.api.metadata.rotten_tomatoes import RottenTomatoesClient
from personalscraper.api.metadata.tmdb import TMDBClient
from personalscraper.api.metadata.trakt import TraktClient
from personalscraper.api.metadata.tvdb import TVDBClient


def _tmdb() -> TMDBClient:
    """Build a :class:`TMDBClient` with a mock HTTP transport."""
    return TMDBClient(transport=MagicMock())


def _trakt() -> TraktClient:
    """Build a :class:`TraktClient` with a mock HTTP transport."""
    return TraktClient(transport=MagicMock())


def _imdb() -> IMDbClient:
    """Build an :class:`IMDbClient` over a mock OMDb backend."""
    return IMDbClient(backend=MagicMock())


def _rt() -> RottenTomatoesClient:
    """Build a :class:`RottenTomatoesClient` over a mock OMDb backend."""
    return RottenTomatoesClient(backend=MagicMock())


def _declares(cls: type, protocol: type[Protocol]) -> bool:
    """``True`` iff ``protocol`` is in ``cls.__mro__`` (explicit inheritance)."""
    return protocol in cls.__mro__


# ---------------------------------------------------------------------------
# TMDBClient — composes Searchable, MovieDetailsProvider, TvDetailsProvider,
# EpisodeFetcher, ArtworkProvider, KeywordProvider, VideoProvider.
# Deliberately omits IDValidator, IDCrossRef, RecommendationProvider,
# RatingProvider.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "protocol",
    [
        Searchable,
        MovieDetailsProvider,
        TvDetailsProvider,
        EpisodeFetcher,
        ArtworkProvider,
        KeywordProvider,
        VideoProvider,
    ],
)
def test_tmdb_client_satisfies_capability(protocol: type[Protocol]) -> None:
    """``TMDBClient`` satisfies each declared capability via runtime_checkable."""
    assert isinstance(_tmdb(), protocol)


def test_tmdb_client_does_not_declare_id_validator() -> None:
    """``TMDBClient`` does not inherit :class:`IDValidator` (no ``validate_id``)."""
    assert not _declares(TMDBClient, IDValidator)


def test_tmdb_client_does_not_declare_id_cross_ref() -> None:
    """``TMDBClient`` does not inherit :class:`IDCrossRef` (no ``get_cross_refs``)."""
    assert not _declares(TMDBClient, IDCrossRef)


def test_tmdb_client_does_not_declare_recommendation_provider() -> None:
    """``TMDBClient`` does not inherit :class:`RecommendationProvider` (no real impl)."""
    assert not _declares(TMDBClient, RecommendationProvider)


def test_tmdb_client_does_not_declare_rating_provider() -> None:
    """``TMDBClient`` does not inherit :class:`RatingProvider` (no ``get_rating``)."""
    assert not _declares(TMDBClient, RatingProvider)


# ---------------------------------------------------------------------------
# TVDBClient — composes Searchable, MovieDetailsProvider, TvDetailsProvider,
# EpisodeFetcher, ArtworkProvider, VideoProvider. Deliberately omits
# KeywordProvider (TVDB raises NotImplementedError on get_keywords),
# IDValidator, IDCrossRef, RatingProvider, RecommendationProvider.
# ---------------------------------------------------------------------------


def test_tvdb_client_declares_expected_capabilities() -> None:
    """``TVDBClient`` MRO contains the declared atomic Protocols."""
    expected = (
        Searchable,
        MovieDetailsProvider,
        TvDetailsProvider,
        EpisodeFetcher,
        ArtworkProvider,
        VideoProvider,
    )
    for protocol in expected:
        assert _declares(TVDBClient, protocol), f"TVDBClient missing {protocol.__name__}"


def test_tvdb_client_omits_unsupported_protocols() -> None:
    """``TVDBClient`` MRO does NOT inherit Protocols whose methods raise NotImplementedError or are absent."""
    for protocol in (KeywordProvider, IDValidator, IDCrossRef, RatingProvider, RecommendationProvider):
        assert not _declares(TVDBClient, protocol), f"TVDBClient must not declare {protocol.__name__}"


# ---------------------------------------------------------------------------
# TraktClient — composes Searchable, MovieDetailsProvider,
# TvDetailsProvider, RecommendationProvider. Deliberately omits
# EpisodeFetcher, ArtworkProvider, KeywordProvider, VideoProvider,
# RatingProvider (method name differs — ``get_notations`` not
# ``get_rating``), IDValidator, IDCrossRef.
# ---------------------------------------------------------------------------


def test_trakt_client_is_searchable() -> None:
    """``TraktClient`` satisfies :class:`Searchable`."""
    assert isinstance(_trakt(), Searchable)


def test_trakt_client_is_movie_details_provider() -> None:
    """``TraktClient`` satisfies :class:`MovieDetailsProvider`."""
    assert isinstance(_trakt(), MovieDetailsProvider)


def test_trakt_client_is_tv_details_provider() -> None:
    """``TraktClient`` satisfies :class:`TvDetailsProvider`."""
    assert isinstance(_trakt(), TvDetailsProvider)


def test_trakt_client_is_recommendation_provider() -> None:
    """``TraktClient`` satisfies :class:`RecommendationProvider`."""
    assert isinstance(_trakt(), RecommendationProvider)


def test_trakt_client_does_not_declare_episode_fetcher() -> None:
    """``TraktClient`` does not inherit :class:`EpisodeFetcher`."""
    assert not _declares(TraktClient, EpisodeFetcher)


def test_trakt_client_does_not_declare_artwork_provider() -> None:
    """``TraktClient`` does not inherit :class:`ArtworkProvider`."""
    assert not _declares(TraktClient, ArtworkProvider)


def test_trakt_client_does_not_declare_keyword_provider() -> None:
    """``TraktClient`` does not inherit :class:`KeywordProvider`."""
    assert not _declares(TraktClient, KeywordProvider)


def test_trakt_client_does_not_declare_id_validator() -> None:
    """``TraktClient`` does not inherit :class:`IDValidator`."""
    assert not _declares(TraktClient, IDValidator)


# ---------------------------------------------------------------------------
# IMDb façade — composes IDValidator, RatingProvider, IDCrossRef.
# Deliberately omits Searchable, Movie/TvDetailsProvider, etc.
# (façade only exposes canonical-ID and rating capabilities — bulk
# search happens via TMDB/TVDB).
# ---------------------------------------------------------------------------


def test_imdb_client_is_id_validator() -> None:
    """``IMDbClient`` satisfies :class:`IDValidator`."""
    assert isinstance(_imdb(), IDValidator)


def test_imdb_client_is_rating_provider() -> None:
    """``IMDbClient`` satisfies :class:`RatingProvider`."""
    assert isinstance(_imdb(), RatingProvider)


def test_imdb_client_is_id_cross_ref() -> None:
    """``IMDbClient`` satisfies :class:`IDCrossRef`."""
    assert isinstance(_imdb(), IDCrossRef)


def test_imdb_client_does_not_declare_searchable() -> None:
    """``IMDbClient`` does not inherit :class:`Searchable`."""
    assert not _declares(IMDbClient, Searchable)


def test_imdb_client_does_not_declare_movie_details_provider() -> None:
    """``IMDbClient`` does not inherit :class:`MovieDetailsProvider`."""
    assert not _declares(IMDbClient, MovieDetailsProvider)


# ---------------------------------------------------------------------------
# Rotten Tomatoes façade — composes RatingProvider only. OMDb does not
# expose a separate RT ID so :class:`IDValidator` / :class:`IDCrossRef`
# are deliberately absent.
# ---------------------------------------------------------------------------


def test_rt_client_is_rating_provider() -> None:
    """``RottenTomatoesClient`` satisfies :class:`RatingProvider`."""
    assert isinstance(_rt(), RatingProvider)


def test_rt_client_does_not_declare_id_validator() -> None:
    """``RottenTomatoesClient`` does not inherit :class:`IDValidator`."""
    assert not _declares(RottenTomatoesClient, IDValidator)


def test_rt_client_does_not_declare_id_cross_ref() -> None:
    """``RottenTomatoesClient`` does not inherit :class:`IDCrossRef`."""
    assert not _declares(RottenTomatoesClient, IDCrossRef)


def test_rt_client_does_not_declare_searchable() -> None:
    """``RottenTomatoesClient`` does not inherit :class:`Searchable`."""
    assert not _declares(RottenTomatoesClient, Searchable)
