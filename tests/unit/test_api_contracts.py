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

from pathlib import Path

import pytest

from personalscraper.api._contracts import HasName, MediaType
from personalscraper.api._helpers import (
    ProviderFeatureUnavailable,
    gather_cross_refs,
    gather_ratings,
)
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
from personalscraper.api.notify._base import HealthChecker as HealthCheckerBaseReexport
from personalscraper.api.notify._base import Notifier as NotifierBaseReexport
from personalscraper.api.notify._contracts import HealthChecker, Notifier
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.api.torrent._contracts import (
    AuthenticatedClient,
    TorrentController,
    TorrentInspector,
    TorrentLister,
    TorrentStateInspector,
)
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._contracts import (
    CategoryListable,
    FreeleechAware,
    TorrentDetailsProvider,
    TorrentSearchable,
)
from personalscraper.models import PipelineReport  # for _NotifierStub.send_report typing

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


# -- Sub-phase 1.3 — Tracker capability stubs ---------------------------------


class _TorrentSearchableStub:
    """Stub exposing only ``search`` for trackers."""

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]:
        return []


class _CategoryListableStub:
    """Stub exposing only ``get_categories``."""

    def get_categories(self) -> dict[str, str]:
        return {}


class _FreeleechAwareStub:
    """Stub exposing only ``is_freeleech``."""

    def is_freeleech(self, torrent_id: str) -> bool:
        return False


class _TorrentDetailsProviderStub:
    """Stub exposing only ``get_details`` for trackers."""

    def get_details(self, torrent_id: str) -> TrackerResult:
        raise NotImplementedError


@pytest.mark.parametrize(
    "protocol, stub_cls",
    [
        (TorrentSearchable, _TorrentSearchableStub),
        (CategoryListable, _CategoryListableStub),
        (FreeleechAware, _FreeleechAwareStub),
        (TorrentDetailsProvider, _TorrentDetailsProviderStub),
    ],
)
def test_tracker_capability_protocols_runtime_checkable(
    protocol: type,
    stub_cls: type,
) -> None:
    """Each tracker capability accepts its stub and rejects an empty object."""
    assert isinstance(stub_cls(), protocol)
    assert not isinstance(_BareProvider(), protocol)


# -- Sub-phase 1.4 — Torrent capability stubs ---------------------------------


class _TorrentListerStub:
    """Stub exposing ``get_completed`` + ``get_all_hashes`` + ``get_by_hashes``."""

    def get_completed(self) -> list[TorrentItem]:
        return []

    def get_all_hashes(self) -> set[str]:
        return set()

    def get_by_hashes(self, hashes: set[str]) -> list[TorrentItem]:
        return []


class _TorrentInspectorStub:
    """Stub exposing only ``get_content_path``."""

    def get_content_path(self, torrent: TorrentItem) -> Path:
        return Path("/tmp")


class _AuthenticatedClientStub:
    """Stub exposing only ``login``."""

    def login(self) -> None:
        return None


class _TorrentStateInspectorStub:
    """Stub exposing only ``is_seeding``."""

    def is_seeding(self, torrent: TorrentItem) -> bool:
        return False


class _TorrentControllerStub:
    """Stub exposing the three write actions (``pause`` / ``resume`` / ``delete``)."""

    def pause(self, hash: str) -> None:
        return None

    def resume(self, hash: str) -> None:
        return None

    def delete(self, hash: str, *, delete_files: bool = False) -> None:
        return None


def test_torrent_lister_requires_both_methods() -> None:
    """``TorrentLister`` rejects a stub that only declares one of the two methods.

    The capability bundles ``get_completed`` and ``get_all_hashes``
    because every realistic implementation supports them together
    (DESIGN §4). A class with only one of the two MUST NOT pass the
    isinstance check.
    """

    class _PartialLister:
        def get_completed(self) -> list[TorrentItem]:
            return []

    assert not isinstance(_PartialLister(), TorrentLister)


def test_torrent_controller_requires_all_three_methods() -> None:
    """``TorrentController`` rejects a stub missing any of pause/resume/delete."""

    class _PartialController:
        def pause(self, hash: str) -> None:
            return None

        def resume(self, hash: str) -> None:
            return None

    assert not isinstance(_PartialController(), TorrentController)


@pytest.mark.parametrize(
    "protocol, stub_cls",
    [
        (TorrentLister, _TorrentListerStub),
        (TorrentInspector, _TorrentInspectorStub),
        (AuthenticatedClient, _AuthenticatedClientStub),
        (TorrentStateInspector, _TorrentStateInspectorStub),
        (TorrentController, _TorrentControllerStub),
    ],
)
def test_torrent_capability_protocols_runtime_checkable(
    protocol: type,
    stub_cls: type,
) -> None:
    """Each torrent capability accepts its stub and rejects an empty object."""
    assert isinstance(stub_cls(), protocol)
    assert not isinstance(_BareProvider(), protocol)


# -- Sub-phase 1.5 — Notify capability stubs ----------------------------------


class _NotifierStub:
    """Stub satisfying the ``Notifier`` protocol."""

    provider_name = "stub-notifier"
    REQUIRED_CREDS: list[str] = []

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        return True

    def send_report(self, report: PipelineReport) -> bool:
        return True


class _HealthCheckerStub:
    """Stub satisfying the ``HealthChecker`` protocol."""

    provider_name = "stub-healthcheck"
    REQUIRED_CREDS: list[str] = []

    def ping_start(self) -> None:
        return None

    def ping_success(self) -> None:
        return None

    def ping_fail(self) -> None:
        return None


@pytest.mark.parametrize(
    "protocol, stub_cls",
    [
        (Notifier, _NotifierStub),
        (HealthChecker, _HealthCheckerStub),
    ],
)
def test_notify_capability_protocols_runtime_checkable(
    protocol: type,
    stub_cls: type,
) -> None:
    """Each notify capability accepts its stub and rejects an empty object."""
    assert isinstance(stub_cls(), protocol)
    assert not isinstance(_BareProvider(), protocol)


# -- Sub-phase 1.6 — Helpers + ProviderFeatureUnavailable ---------------------


class _RatingProviderWithName:
    """Stub satisfying ``RatingProvider`` + carrying ``provider_name``."""

    provider_name = "fakerating"

    def __init__(self, ratings: list[Notations] | None) -> None:
        self._ratings = ratings

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        return self._ratings


class _RatingProviderRaising:
    """Stub satisfying ``RatingProvider`` but raising ``ProviderFeatureUnavailable``."""

    provider_name = "broken"

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        raise ProviderFeatureUnavailable("broken", "get_rating", "missing field")


class _IDCrossRefWithName:
    """Stub satisfying ``IDCrossRef`` + carrying ``provider_name``."""

    provider_name = "tvdb"

    def __init__(self, refs: dict[str, str]) -> None:
        self._refs = refs

    def get_cross_refs(self, provider_id: str) -> dict[str, str]:
        return self._refs


class _IDCrossRefRaising:
    """Stub satisfying ``IDCrossRef`` but raising ``ProviderFeatureUnavailable``."""

    provider_name = "down"

    def get_cross_refs(self, provider_id: str) -> dict[str, str]:
        raise ProviderFeatureUnavailable("down", "get_cross_refs", "endpoint deprecated")


def test_gather_ratings_filters_non_rating_providers() -> None:
    """``gather_ratings`` ignores providers without the capability.

    Mixed list with a rating provider + a bare provider + a non-rating
    capability provider returns only the rating provider's results.
    """
    notation = Notations(provider="fakerating", source="imdb", score=8.0, votes_count=100)
    providers = [
        _RatingProviderWithName([notation]),
        _BareProvider(),
        _IDCrossRefWithName({"tmdb": "42"}),
    ]
    result = gather_ratings(providers, provider_id="tt0000001")
    assert result == [notation]


def test_gather_ratings_swallows_none_and_empty_lists() -> None:
    """``gather_ratings`` skips providers that return ``None`` or empty list.

    Both shapes mean "queried successfully, no rating available" and
    must not pollute the aggregate.
    """
    providers = [
        _RatingProviderWithName(None),
        _RatingProviderWithName([]),
    ]
    assert gather_ratings(providers, provider_id="tt0000001") == []


def test_gather_ratings_swallows_provider_feature_unavailable() -> None:
    """A raising provider does not abort the aggregation."""
    notation = Notations(provider="ok", source="imdb", score=7.0, votes_count=10)
    providers = [
        _RatingProviderRaising(),
        _RatingProviderWithName([notation]),
    ]
    assert gather_ratings(providers, provider_id="tt0000002") == [notation]


def test_gather_cross_refs_returns_dict_by_provider_name() -> None:
    """``gather_cross_refs`` indexes per provider name and skips non-capable entries."""
    providers = [
        _IDCrossRefWithName({"tmdb": "1", "imdb": "tt001"}),
        _BareProvider(),
        _RatingProviderWithName(None),
    ]
    result = gather_cross_refs(providers, canonical_id="121361")
    assert result == {"tvdb": {"tmdb": "1", "imdb": "tt001"}}


def test_gather_cross_refs_skips_empty_dicts_and_unavailable() -> None:
    """Providers returning an empty dict or raising are silently skipped."""

    class _EmptyCrossRef:
        provider_name = "empty"

        def get_cross_refs(self, provider_id: str) -> dict[str, str]:
            return {}

    providers = [
        _EmptyCrossRef(),
        _IDCrossRefRaising(),
        _IDCrossRefWithName({"tmdb": "42"}),
    ]
    result = gather_cross_refs(providers, canonical_id="999")
    assert result == {"tvdb": {"tmdb": "42"}}


def test_provider_feature_unavailable_carries_provider_and_feature() -> None:
    """``ProviderFeatureUnavailable`` exposes ``provider`` + ``feature`` + ``reason``.

    The string form embeds all three so logs are self-contained.
    """
    exc = ProviderFeatureUnavailable("omdb", "get_rating", "no rt entry")
    assert exc.provider == "omdb"
    assert exc.feature == "get_rating"
    assert exc.reason == "no rt entry"
    assert "omdb" in str(exc)
    assert "get_rating" in str(exc)
    assert "no rt entry" in str(exc)


def test_notify_protocols_are_re_exported_from_base() -> None:
    """``api.notify._base`` re-exports the canonical Protocols from ``_contracts``.

    Sub-phase 1.5 moves the definitions but preserves the legacy import
    path. ``Notifier`` imported from ``_base`` must be the same object as
    ``Notifier`` imported from ``_contracts`` — likewise for
    ``HealthChecker``.
    """
    assert NotifierBaseReexport is Notifier
    assert HealthCheckerBaseReexport is HealthChecker
