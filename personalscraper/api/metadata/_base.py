"""Metadata family base — typed models and MetadataClient.

Implements DESIGN SS4.1-S4.3: SearchResult, MediaDetails, ArtworkItem,
Notations, Recommendation, Video, EpisodeInfo, SeasonDetails models,
and the MetadataClient base class with NotImplementedError-raising
defaults for optional capabilities. The former monolithic MetadataProvider
Protocol was dropped in 0.16.0 (MUST-14, CF-B) — use the atomic capability
Protocols in ``personalscraper.api.metadata._contracts`` instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal

from personalscraper.api._contracts import MediaType

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
        original_title: Original-language title (for matching localised
            releases against their original-name folders, e.g. matching
            'The Butterfly Effect' against 'L'Effet papillon').
    """

    provider: str
    provider_id: str
    title: str
    year: int | None = None
    media_type: MediaType = MediaType.MOVIE
    overview: str = ""
    poster_url: str = ""
    original_title: str = ""


@dataclass(frozen=True)
class ArtworkItem:
    """An artwork image associated with a media item.

    Attributes:
        type: Artwork category ("poster", "landscape", "season_poster", "backdrop").
        url: Full URL to the image.
        language: ISO 639-1 language code, if known.
        season: Season number (only for season_poster type).
        vote_average: Provider-side popularity / quality score (0.0-10.0
            range, semantics differ per provider). Used by ArtworkSelector
            as a tie-breaker when multiple candidates share the top
            language priority.
    """

    type: Literal["poster", "landscape", "season_poster", "backdrop"]
    url: str
    language: str = ""
    season: int | None = None
    vote_average: float = 0.0


@dataclass(frozen=True)
class SeasonInfo:
    """Summary of a single season in a TV show catalog.

    Lightweight per-season summary attached to MediaDetails for content-
    aware operations that need the season list without paying for the
    full episode breakdown — e.g. the matching-stage candidate veto
    (rejecting a candidate whose catalog does not cover the locally
    present seasons) and season-poster selection.

    Episode-level details still come from
    :class:`SeasonDetails` via :meth:`MetadataClient.get_season`.

    Attributes:
        season_number: Season number (1-based; 0 for specials).
        episode_count: Number of episodes in this season, when known.
        overview: Per-season summary, when provided.
        poster_url: Pre-resolved season poster URL, when provided.
    """

    season_number: int
    episode_count: int = 0
    overview: str = ""
    poster_url: str = ""


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
        seasons: For TV shows, the season catalog summary (season number,
            episode count, optional poster). Empty for movies.
        genre_ids: Provider-specific genre identifiers (TMDB IDs). Used by
            classifier rules that match on numeric genre IDs rather than
            localised genre names.
        origin_countries: ISO 3166-1 alpha-2 codes from the production
            origin (typically TMDB's ``origin_country`` for TV, single-
            element list for movies). Used by classifier country-rules
            (e.g. anime detection).
        production_countries: ISO 3166-1 alpha-2 codes for production
            countries (TMDB's ``production_countries`` block, broader
            than origin_countries on movies).
        primary_backdrop_url: Provider's top-level backdrop URL, used as
            a last-resort fallback when ``images`` contains no
            ``backdrop`` entries.
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
    seasons: list[SeasonInfo] = field(default_factory=list)
    genre_ids: list[int] = field(default_factory=list)
    origin_countries: list[str] = field(default_factory=list)
    production_countries: list[str] = field(default_factory=list)
    primary_backdrop_url: str = ""


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
    media_type: MediaType = MediaType.MOVIE
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
        season_number: Season this episode belongs to (1-based; 0 for
            specials). Mirrors the parent ``SeasonDetails.season_number``
            but is duplicated here so callers that flatten episodes from
            multiple seasons still know each episode's season without
            tracking the source separately.
        still_url: Pre-resolved still-frame image URL for the episode,
            when provided. Used by the NFO writer to embed an
            ``<thumb>`` tag.
        external_ids: Mapping of provider name (``"tvdb"`` / ``"tmdb"`` /
            ``"imdb"``) to the per-episode provider identifier. Populated
            by the provider parser when the upstream payload carries the
            ID and propagated all the way to NFO generation so that
            ``<uniqueid>`` tags can be written without round-tripping
            through the show-level identifiers (DEV #2 of the
            ``provider-ids`` feature).
    """

    episode_number: int
    title: str = ""
    overview: str = ""
    air_date: str = ""
    runtime_minutes: int | None = None
    season_number: int = 0
    still_url: str = ""
    external_ids: dict[str, str] = field(default_factory=dict)


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


# -- MetadataClient base (DESIGN S4.1) ---------------------------------------


class MetadataClient:
    """Base class for metadata providers.

    Subclasses MUST declare an explicit ``provider_name`` ClassVar — the
    base value is empty and ``__init_subclass__`` raises ``TypeError`` at
    class-definition time when a concrete subclass omits it. This prevents
    silent fallback to the lowercase class name (which would break on a
    rename like ``TMDbClient``) and surfaces the error before any instance
    is constructed, even when a subclass overrides ``__init__`` without
    calling ``super().__init__()``.

    Subclasses override capability methods they support; the base class
    raises ``NotImplementedError`` for unsupported ones.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = []
    provider_name: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Enforce that every subclass declares an explicit ``provider_name``.

        We err on the strict side: the moment a class inherits from
        ``MetadataClient`` and does not set a non-empty ``provider_name``
        ClassVar, this raises. There are no abstract intermediate bases
        in this family — concrete clients are the only valid subclasses,
        and surfacing the misconfiguration at class-definition time
        prevents silent fallback to an empty provider identifier in
        error messages and logs.

        Args:
            **kwargs: Forwarded to ``object.__init_subclass__``.

        Raises:
            TypeError: Subclass declares no (or empty) ``provider_name``.
        """
        super().__init_subclass__(**kwargs)
        if not cls.provider_name:
            raise TypeError(
                f"{cls.__name__} must declare an explicit provider_name ClassVar — "
                "see MetadataClient base class docstring."
            )

    def __init__(self, transport: "HttpTransport", language: str = "fr-FR") -> None:
        self._transport = transport
        self._language = language

    # -- Optional capability methods (override in subclasses) -----------------

    def get_artwork_urls(self, media_id: str, media_type: MediaType = MediaType.MOVIE) -> list[ArtworkItem]:
        raise NotImplementedError(f"{self.provider_name} does not support artwork URLs")

    def get_keywords(self, media_id: str, media_type: MediaType) -> list[str]:
        raise NotImplementedError(f"{self.provider_name} does not support keywords")

    def get_videos(self, media_id: str, media_type: MediaType, language: str) -> list[Video]:
        raise NotImplementedError(f"{self.provider_name} does not support videos")

    def get_season(self, tv_id: str, season: int) -> SeasonDetails:
        raise NotImplementedError(f"{self.provider_name} does not support season details")

    def get_notations(self, media_id: str, media_type: MediaType) -> list[Notations] | None:
        raise NotImplementedError(f"{self.provider_name} does not support notations")

    def get_recommendations(self, media_id: str, media_type: MediaType) -> list[Recommendation]:
        raise NotImplementedError(f"{self.provider_name} does not support recommendations")
