"""Trailer download feature config models."""

from typing import Annotated

from pydantic import Field

from personalscraper.conf.models._base import _StrictModel


class TrailersCircuitBreakerConfig(_StrictModel):
    """One circuit breaker config (per external service).

    Attributes:
        errors_threshold: Number of consecutive errors that trip the breaker.
        cooldown_sec: Seconds the breaker stays open before half-opening.
    """

    errors_threshold: int = Field(default=5, ge=1)
    cooldown_sec: int = Field(default=1800, ge=0)


class TrailersCircuitBreakersConfig(_StrictModel):
    """Two independent breakers: one per external service.

    A YouTube outage must never trip the TMDB breaker used by the rest of the
    scraper (and vice-versa).

    Attributes:
        tmdb_videos: Circuit breaker for TMDB /videos API calls.
        youtube: Circuit breaker for YouTube Data API / yt-dlp calls.
    """

    tmdb_videos: TrailersCircuitBreakerConfig = Field(
        default_factory=lambda: TrailersCircuitBreakerConfig(errors_threshold=5, cooldown_sec=1800)
    )
    youtube: TrailersCircuitBreakerConfig = Field(
        default_factory=lambda: TrailersCircuitBreakerConfig(errors_threshold=5, cooldown_sec=3600)
    )


class TrailersFiltersConfig(_StrictModel):
    """Trailer download and verification filters.

    Attributes:
        min_file_size_bytes: Minimum file size in bytes for a valid trailer.
        max_filesize_mb: Maximum trailer file size passed to yt-dlp as a download cap.
        allowed_extensions: File extensions accepted by the verify subcommand.
    """

    min_file_size_bytes: int = Field(default=102400, ge=0)
    max_filesize_mb: int = Field(default=500, gt=0)
    # Per-element pattern rejects empty strings, leading dots, and whitespace —
    # otherwise typos like "" or "mp4 " would silently disable the verify gate.
    allowed_extensions: Annotated[
        list[Annotated[str, Field(pattern=r"^[a-z0-9]+$")]],
        Field(min_length=1),
    ] = Field(default_factory=lambda: ["mp4", "mkv", "webm"])


class TrailersYoutubeApiConfig(_StrictModel):
    """YouTube Data API v3 quota accounting defaults.

    Attributes:
        daily_quota_units: Total daily quota units allocated by Google.
        search_list_cost_units: Quota cost per search.list call.
    """

    daily_quota_units: int = Field(default=10_000, gt=0)
    search_list_cost_units: int = Field(default=100, gt=0)


class TrailersYtdlpConfig(_StrictModel):
    """yt-dlp download options.

    Attributes:
        format: yt-dlp format selector string. Capped at 1080p.
        socket_timeout_sec: Socket timeout in seconds.
        retries: Number of download retries on transient error.
    """

    format: str = Field(default="bestvideo[height<=1080]+bestaudio/best[height<=1080]", min_length=1)
    socket_timeout_sec: int = Field(default=30, gt=0)
    retries: int = Field(default=3, ge=0)


class TrailersSeasonsConfig(_StrictModel):
    """Opt-in season-level trailer download (DESIGN section 4 extension).

    Default off: most shows lack TMDB season-level trailers.

    Attributes:
        enabled: Master switch.
    """

    enabled: bool = False


class TrailersStepConfig(_StrictModel):
    """Operational safeguards for the pipeline step (DESIGN section 12).

    Attributes:
        max_duration_sec: Step-level time budget in seconds. Default 1800 (30 min).
    """

    max_duration_sec: int = Field(default=1800, gt=0)  # 30-minute step-level budget


class TrailersPipelineConfig(_StrictModel):
    """Defaults for pipeline-level flags. CLI flags take precedence at runtime.

    Attributes:
        skip: When True, the trailers step is silently skipped by the orchestrator.
        continue_on_error: When True, a trailer failure does not abort the pipeline.
    """

    skip: bool = False
    continue_on_error: bool = False


class TrailersLibraryCheckConfig(_StrictModel):
    """Library-aware SOT recheck toggles (DESIGN section 8 extension).

    Attributes:
        movies: Enable library scan before trailer discovery for movies.
        tv_shows: Enable library scan before trailer discovery for TV shows.
    """

    movies: bool = False
    tv_shows: bool = True


class TrailersConfig(_StrictModel):
    """Top-level trailers feature configuration (DESIGN section 9).

    Attributes:
        enabled: Master switch. Default False.
        languages: Ordered language codes for TMDB video lookups. First match wins.
        search_query_format: YouTube search query template when TMDB yields nothing.
        filters: Download filters (file size, extension allow-list).
        state_file: Path to the per-media-item state JSON.
        retry_after_days: Days after a failed attempt before retrying.
        circuit_breakers: Per-service circuit breaker configuration.
        youtube_api: YouTube Data API v3 quota and cache settings.
        ytdlp: yt-dlp download options.
        step: Pipeline step-level operational safeguards.
        pipeline: Pipeline-level flag defaults.
        seasons: Season-level trailer discovery (opt-in, off by default).
        library_check: Per-media-type library-aware idempotence toggles.
        fallback_youtube_search: When True, a failed TMDB-found download triggers
            a same-run YouTube search for an alternative upload and one re-download.
    """

    enabled: bool = False
    languages: Annotated[list[str], Field(min_length=1)] = Field(default_factory=lambda: ["fr-FR", "en-US"])
    search_query_format: str = Field(default="{title} {year} bande annonce", min_length=1)
    filters: TrailersFiltersConfig = Field(default_factory=TrailersFiltersConfig)
    state_file: str | None = Field(
        default=None,
        description="Path to the per-media-item state JSON. Defaults to paths.data_dir / 'trailers_state.json'.",
    )
    # Per-element ge=0 prevents a negative day from collapsing the back-off
    # ladder into immediate-retry (which would defeat the throttling intent).
    retry_after_days: Annotated[
        list[Annotated[int, Field(ge=0)]],
        Field(min_length=1),
    ] = Field(default_factory=lambda: [1, 7, 30])
    circuit_breakers: TrailersCircuitBreakersConfig = Field(default_factory=TrailersCircuitBreakersConfig)
    youtube_api: TrailersYoutubeApiConfig = Field(default_factory=TrailersYoutubeApiConfig)
    ytdlp: TrailersYtdlpConfig = Field(default_factory=TrailersYtdlpConfig)
    step: TrailersStepConfig = Field(default_factory=TrailersStepConfig)
    pipeline: TrailersPipelineConfig = Field(default_factory=TrailersPipelineConfig)
    # DESIGN section 4 extension: opt-in season-level trailer discovery.
    seasons: TrailersSeasonsConfig = Field(default_factory=TrailersSeasonsConfig)
    # DESIGN section 8 extension: library-aware idempotence per-media-type toggles.
    library_check: TrailersLibraryCheckConfig = Field(default_factory=TrailersLibraryCheckConfig)
    # Same-run fallback: when a TMDB-found URL fails to download, attempt a
    # YouTube search for an alternative upload and re-download once.
    # Default True (opt-in by default); set False to disable.
    fallback_youtube_search: bool = True
