"""Metadata family base — typed models, Protocol, and MetadataClient.

Implements DESIGN SS4.1-S4.3: SearchResult, MediaDetails, ArtworkItem,
Notations, Recommendation, Video, EpisodeInfo, SeasonDetails models,
the MetadataProvider Protocol, and the MetadataClient base class with
NotImplementedError-raising defaults for optional capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport

# -- Typed response models (DESIGN S4.2) ------------------------------------


@dataclass(frozen=True)
class SearchResult:
    """A single search result from a metadata provider.

    Attributes:
        provider: Provider name (e.g. "tmdb", "tvdb").
        provider_id: Provider-specific media identifier.
        title: Display title.
        year: Release year, if known.
        media_type: "movie" or "tv".
        overview: Short plot summary.
        poster_url: URL to poster image, if available.
    """

    provider: str
    provider_id: str
    title: str
    year: int | None = None
    media_type: Literal["movie", "tv"] = "movie"
    overview: str = ""
    poster_url: str = ""


@dataclass(frozen=True)
class ArtworkItem:
    """An artwork image associated with a media item.

    Attributes:
        type: Artwork category ("poster", "landscape", "season_poster", "backdrop").
        url: Full URL to the image.
        language: ISO 639-1 language code, if known.
        season: Season number (only for season_poster type).
    """

    type: Literal["poster", "landscape", "season_poster", "backdrop"]
    url: str
    language: str = ""
    season: int | None = None


@dataclass(frozen=True)
class MediaDetails:
    """Full details for a media item.

    Attributes:
        provider: Provider name.
        provider_id: Provider-specific media identifier.
        title: Display title.
        original_title: Title in original language.
        year: Release year.
        overview: Full plot summary.
        genres: List of genre names.
        runtime_minutes: Runtime in minutes.
        rating: Average rating (0-10 scale).
        images: List of associated artwork items.
        external_ids: External identifiers keyed by source (e.g. "imdb" → "tt1234567").
    """

    provider: str
    provider_id: str
    title: str = ""
    original_title: str = ""
    year: int | None = None
    overview: str = ""
    genres: list[str] = field(default_factory=list)
    runtime_minutes: int | None = None
    rating: float | None = None
    images: list[ArtworkItem] = field(default_factory=list)
    external_ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Notations:
    """Ratings/notations from a review source.

    Attributes:
        provider: Metadata provider that supplied this rating.
        source: Rating source ("imdb", "rotten_tomatoes", "trakt", "tmdb", "metacritic").
        score: Numerical score.
        votes_count: Number of votes, if known.
    """

    provider: str
    source: Literal["imdb", "rotten_tomatoes", "trakt", "tmdb", "metacritic"]
    score: float
    votes_count: int | None = None


@dataclass(frozen=True)
class Recommendation:
    """A content recommendation from a metadata provider.

    Attributes:
        provider: Provider that generated this recommendation.
        provider_id: Provider-specific identifier for the recommended item.
        title: Display title.
        year: Release year.
        media_type: "movie" or "tv".
        reason: Human-readable reason for the recommendation.
    """

    provider: str
    provider_id: str
    title: str
    year: int | None = None
    media_type: Literal["movie", "tv"] = "movie"
    reason: str = ""


@dataclass(frozen=True)
class Video:
    """A video (trailer, teaser, clip) associated with a media item.

    Attributes:
        id: Provider-specific video identifier.
        site: Hosting site ("youtube" or "vimeo").
        key: Video key for constructing embed URLs.
        type: Video type ("trailer", "teaser", "clip").
        official: Whether this is an official video.
        size: Video resolution (e.g. 1080).
        iso_639_1: ISO 639-1 language code.
    """

    id: str
    site: Literal["youtube", "vimeo"]
    key: str
    type: Literal["trailer", "teaser", "clip"] = "trailer"
    official: bool = False
    size: int | None = None
    iso_639_1: str = ""


@dataclass(frozen=True)
class EpisodeInfo:
    """A single episode within a TV season.

    Attributes:
        episode_number: Episode number within the season.
        title: Episode title.
        overview: Episode plot summary.
        air_date: Original air date as ISO-8601 string.
        runtime_minutes: Episode runtime in minutes.
    """

    episode_number: int
    title: str = ""
    overview: str = ""
    air_date: str = ""
    runtime_minutes: int | None = None


@dataclass(frozen=True)
class SeasonDetails:
    """Full details for a TV season.

    Attributes:
        provider: Provider name.
        tv_id: Provider-specific TV show identifier.
        season_number: Season number.
        episodes: List of episodes in this season.
    """

    provider: str
    tv_id: str
    season_number: int
    episodes: list[EpisodeInfo] = field(default_factory=list)


# -- MetadataProvider Protocol (DESIGN S4.1) --------------------------------


@runtime_checkable
class MetadataProvider(Protocol):
    """Protocol that all metadata providers must satisfy.

    Required members:
        provider_name: Human-readable provider identifier.
        REQUIRED_CREDS: List of .env variable names needed by this provider.
        search(): Find media by title + optional year.
        get_details(): Fetch full details for a known media ID.

    Optional capability methods (raise NotImplementedError by default
    via MetadataClient; providers override the ones they support).
    """

    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: str = "movie",
    ) -> list[SearchResult]: ...

    def get_details(
        self,
        media_id: str,
        media_type: str = "movie",
    ) -> MediaDetails: ...

    def get_artwork_urls(
        self,
        media_id: str,
        media_type: str = "movie",
    ) -> list[ArtworkItem]: ...

    def get_keywords(
        self,
        media_id: str,
        media_type: str,
    ) -> list[str]: ...

    def get_videos(
        self,
        media_id: str,
        media_type: str,
        language: str,
    ) -> list[Video]: ...

    def get_season(
        self,
        tv_id: str,
        season: int,
    ) -> SeasonDetails: ...

    def get_notations(
        self,
        media_id: str,
        media_type: str,
    ) -> list[Notations] | None: ...

    def get_recommendations(
        self,
        media_id: str,
        media_type: str,
    ) -> list[Recommendation]: ...


# -- MetadataClient base (DESIGN S4.1) ---------------------------------------


class MetadataClient:
    """Base class for metadata providers.

    Subclasses override capability methods they support; others raise
    NotImplementedError on call. Provides a shared transport reference
    and a default provider_name derived from the class name.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = []

    def __init__(self, transport: "HttpTransport", language: str = "fr-FR") -> None:
        self._transport = transport
        self._language = language

    @property
    def provider_name(self) -> str:
        """Derive provider name from class name (e.g. TMDBClient → 'tmdb')."""
        return type(self).__name__.replace("Client", "").lower()

    # -- Optional capability methods (override in subclasses) -----------------

    def get_artwork_urls(self, media_id: str, media_type: str = "movie") -> list[ArtworkItem]:
        raise NotImplementedError(f"{self.provider_name} does not support artwork URLs")

    def get_keywords(self, media_id: str, media_type: str) -> list[str]:
        raise NotImplementedError(f"{self.provider_name} does not support keywords")

    def get_videos(self, media_id: str, media_type: str, language: str) -> list[Video]:
        raise NotImplementedError(f"{self.provider_name} does not support videos")

    def get_season(self, tv_id: str, season: int) -> SeasonDetails:
        raise NotImplementedError(f"{self.provider_name} does not support season details")

    def get_notations(self, media_id: str, media_type: str) -> list[Notations] | None:
        raise NotImplementedError(f"{self.provider_name} does not support notations")

    def get_recommendations(self, media_id: str, media_type: str) -> list[Recommendation]:
        raise NotImplementedError(f"{self.provider_name} does not support recommendations")
