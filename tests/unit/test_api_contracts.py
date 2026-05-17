"""Tests for the API contracts of the ``provider-ids`` feature.

Covers the global ``HasName`` protocol in
``personalscraper.api._contracts`` and the 11 atomic metadata
capability protocols in ``personalscraper.api.metadata._contracts``.

The 11 metadata capabilities are exercised via structural stubs that
expose only the method declared by each protocol, confirming that
``@runtime_checkable`` honours the structural-subtyping contract: a
stub satisfies a capability when (and only when) it carries the
expected method name.
"""

from __future__ import annotations

import pytest

from personalscraper.api._contracts import HasName, MediaType
from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    Notations,
    Recommendation,
    SearchResult,
    Video,
)
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

# -- Sub-phase 1.1 — HasName --------------------------------------------------


class _ProviderWithName:
    """Stub with the canonical ``provider_name`` attribute."""

    provider_name = "tmdb"


class _ProviderWithoutName:
    """Stub missing ``provider_name`` to confirm rejection."""


def test_has_name_protocol_isinstance_check() -> None:
    """``HasName`` is runtime-checkable and matches duck-typed objects.

    A class exposing a ``provider_name`` attribute satisfies the protocol
    without inheriting from it (structural subtyping). A class lacking the
    attribute is rejected.
    """
    assert isinstance(_ProviderWithName(), HasName)
    assert not isinstance(_ProviderWithoutName(), HasName)


# -- Sub-phase 1.2 — Metadata capability stubs --------------------------------


class _SearchableStub:
    """Stub exposing only ``search``."""

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]:
        return []


class _MovieDetailsStub:
    """Stub exposing only ``get_movie``."""

    def get_movie(self, provider_id: str) -> MediaDetails:
        raise NotImplementedError


class _TvDetailsStub:
    """Stub exposing only ``get_tv``."""

    def get_tv(self, provider_id: str) -> MediaDetails:
        raise NotImplementedError


class _EpisodeFetcherStub:
    """Stub exposing only ``get_episodes``."""

    def get_episodes(self, series_id: str, season: int) -> list[EpisodeInfo]:
        return []


class _RatingProviderStub:
    """Stub exposing only ``get_rating``."""

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        return None


class _IDValidatorStub:
    """Stub exposing only ``validate_id``."""

    def validate_id(
        self,
        provider_id: str,
        expected_title: str,
        expected_year: int | None,
    ) -> bool:
        return True


class _IDCrossRefStub:
    """Stub exposing only ``get_cross_refs``."""

    def get_cross_refs(self, provider_id: str) -> dict[str, str]:
        return {}


class _ArtworkProviderStub:
    """Stub exposing only ``get_artwork_urls``."""

    def get_artwork_urls(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[ArtworkItem]:
        return []


class _KeywordProviderStub:
    """Stub exposing only ``get_keywords``."""

    def get_keywords(self, media_id: str, media_type: MediaType) -> list[str]:
        return []


class _VideoProviderStub:
    """Stub exposing only ``get_videos``."""

    def get_videos(
        self,
        media_id: str,
        media_type: MediaType,
        language: str,
    ) -> list[Video]:
        return []


class _RecommendationProviderStub:
    """Stub exposing only ``get_recommendations``."""

    def get_recommendations(
        self,
        media_id: str,
        media_type: MediaType,
    ) -> list[Recommendation]:
        return []


class _BareProvider:
    """Provider with no capability methods — must reject every protocol."""


@pytest.mark.parametrize(
    "protocol, stub_cls",
    [
        (Searchable, _SearchableStub),
        (MovieDetailsProvider, _MovieDetailsStub),
        (TvDetailsProvider, _TvDetailsStub),
        (EpisodeFetcher, _EpisodeFetcherStub),
        (RatingProvider, _RatingProviderStub),
        (IDValidator, _IDValidatorStub),
        (IDCrossRef, _IDCrossRefStub),
        (ArtworkProvider, _ArtworkProviderStub),
        (KeywordProvider, _KeywordProviderStub),
        (VideoProvider, _VideoProviderStub),
        (RecommendationProvider, _RecommendationProviderStub),
    ],
)
def test_metadata_capability_protocols_runtime_checkable(
    protocol: type,
    stub_cls: type,
) -> None:
    """Each metadata capability accepts its matching stub and rejects a bare object.

    Verifies the two structural-subtyping branches in one go:
    1. A stub that exposes only the protocol's method passes the isinstance check.
    2. A class with no methods at all fails the same check.
    """
    assert isinstance(stub_cls(), protocol)
    assert not isinstance(_BareProvider(), protocol)
