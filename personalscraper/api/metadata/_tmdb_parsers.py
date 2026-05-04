"""TMDB response → typed model parsers.

Pure functions, no HTTP — testable against golden samples from
docs/reference/_samples/tmdb/. Every parser maps raw TMDB JSON
fields to the typed models defined in api/metadata/_base.py.

Real-field confirmations from Phase 4 live API calls (2026-05-04).
"""

from __future__ import annotations

from typing import Any

from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    SearchResult,
    SeasonDetails,
    Video,
)

IMAGE_BASE = "https://image.tmdb.org/t/p/"


def _build_image_url(path: str | None, size: str) -> str:
    """Build a full TMDB image URL from a file_path and size.

    Args:
        path: Image file_path from TMDB (e.g. "/abc.jpg").
        size: Width code (e.g. "w500", "w780", "original").

    Returns:
        Full URL, or empty string if path is None/empty.
    """
    if not path:
        return ""
    return f"{IMAGE_BASE}{size}{path}"


def parse_search_result(raw: dict[str, Any], provider: str) -> SearchResult:
    """Map a single TMDB search result → SearchResult.

    Handles both movie (``title``, ``release_date``) and TV
    (``name``, ``first_air_date``) field naming.

    Args:
        raw: A single item from ``results[]``.
        provider: Provider name (always "tmdb").

    Returns:
        Populated SearchResult.
    """
    is_tv = "name" in raw and "title" not in raw
    title = raw.get("name" if is_tv else "title", "")
    date_str = raw.get("first_air_date" if is_tv else "release_date", "")

    year: int | None = None
    if date_str:
        try:
            year = int(date_str[:4])
        except (ValueError, TypeError):
            year = None

    return SearchResult(
        provider=provider,
        provider_id=str(raw["id"]),
        title=title or "",
        year=year,
        media_type="tv" if is_tv else "movie",
        overview=raw.get("overview", "") or "",
        poster_url=_build_image_url(raw.get("poster_path"), "w500"),
    )


def parse_artwork(images_raw: dict[str, Any], *, season: int | None = None) -> list[ArtworkItem]:
    """Merge TMDB backdrops + posters + logos → list[ArtworkItem].

    Mapping:
    - ``backdrops[*]`` → ``ArtworkItem(type="backdrop")`` at w1280
    - ``posters[*]``  → ``ArtworkItem(type="poster")`` at w780
    - ``logos[*]``    → ``ArtworkItem(type="landscape")`` at w500
    - When ``season`` is provided, ``type="season_poster"`` for posters.

    Args:
        images_raw: The ``images`` sub-object from a details response.
        season: Season number for season-poster context (None for movie/main).

    Returns:
        Merged list of ArtworkItem, ordered backdrops → posters → logos.
    """
    items: list[ArtworkItem] = []

    for img in images_raw.get("backdrops", []) or []:
        items.append(
            ArtworkItem(
                type="backdrop",
                url=_build_image_url(img.get("file_path"), "w1280"),
                language=img.get("iso_639_1") or "",
            )
        )

    poster_type = "season_poster" if season is not None else "poster"
    for img in images_raw.get("posters", []) or []:
        items.append(
            ArtworkItem(
                type=poster_type,  # type: ignore[arg-type]
                url=_build_image_url(img.get("file_path"), "w780"),
                language=img.get("iso_639_1") or "",
                season=season,
            )
        )

    for img in images_raw.get("logos", []) or []:
        items.append(
            ArtworkItem(
                type="landscape",
                url=_build_image_url(img.get("file_path"), "w500"),
                language=img.get("iso_639_1") or "",
            )
        )

    return items


def parse_media_details(raw: dict[str, Any], provider: str) -> MediaDetails:
    """Map TMDB movie or TV details → MediaDetails.

    Handles both movie-specific fields (``title``, ``release_date``, ``runtime``,
    ``imdb_id``) and TV-specific fields (``name``, ``first_air_date``,
    ``episode_run_time``, ``external_ids.tvdb_id``).

    ``runtime_minutes``: for movies → ``raw["runtime"]`` (may be null);
    for TV → ``max(raw["episode_run_time"])`` if array is non-empty, else None.

    Args:
        raw: Full movie or TV details response.
        provider: Provider name ("tmdb").

    Returns:
        Populated MediaDetails.
    """
    is_tv = "name" in raw and "title" not in raw

    # Runtime
    runtime_minutes: int | None = None
    if is_tv:
        runtimes = raw.get("episode_run_time") or []
        runtime_minutes = max(runtimes) if runtimes else None
    else:
        runtime_minutes = raw.get("runtime") or None

    # Genres
    genres = [g["name"] for g in raw.get("genres", []) or []]

    # Images
    images = parse_artwork(raw.get("images", {}) or {})

    # External IDs
    external_ids: dict[str, str] = {}
    imdb = raw.get("imdb_id")
    if imdb:
        external_ids["imdb"] = imdb
    ext = raw.get("external_ids")
    if ext and isinstance(ext, dict):
        for src in ("tvdb_id", "imdb_id", "wikidata_id", "facebook_id", "instagram_id", "twitter_id"):
            v = ext.get(src)
            if v and isinstance(v, str):
                key = src.replace("_id", "")
                if key not in external_ids:
                    external_ids[key] = v

    # Year
    date_str = raw.get("first_air_date" if is_tv else "release_date", "")
    year: int | None = None
    if date_str:
        try:
            year = int(date_str[:4])
        except (ValueError, TypeError):
            year = None

    return MediaDetails(
        provider=provider,
        provider_id=str(raw["id"]),
        title=raw.get("name" if is_tv else "title", "") or "",
        original_title=raw.get("original_name" if is_tv else "original_title", "") or "",
        year=year,
        overview=raw.get("overview", "") or "",
        genres=genres,
        runtime_minutes=runtime_minutes,
        rating=raw.get("vote_average"),
        images=images,
        external_ids=external_ids,
    )


def parse_video(raw: dict[str, Any]) -> Video:
    """Map a single TMDB video object → Video.

    Args:
        raw: A single item from ``videos.results[]``.

    Returns:
        Populated Video.
    """
    site = raw.get("site", "").lower()
    if site not in ("youtube", "vimeo"):
        site = "youtube"

    vtype = raw.get("type", "").lower()
    if vtype not in ("trailer", "teaser", "clip"):
        vtype = "trailer"

    return Video(
        id=str(raw.get("id", "")),
        site=site,
        key=raw.get("key", ""),
        type=vtype,
        official=bool(raw.get("official", False)),
        size=raw.get("size"),
        iso_639_1=raw.get("iso_639_1", "") or "",
    )


def parse_episode(raw: dict[str, Any]) -> EpisodeInfo:
    """Map a single TMDB episode object → EpisodeInfo.

    Args:
        raw: A single item from ``episodes[]`` in a season response.

    Returns:
        Populated EpisodeInfo.
    """
    return EpisodeInfo(
        episode_number=raw["episode_number"],
        title=raw.get("name", "") or "",
        overview=raw.get("overview", "") or "",
        air_date=raw.get("air_date", "") or "",
        runtime_minutes=raw.get("runtime") or None,
    )


def parse_keywords(raw_keywords: dict[str, Any], media_type: str) -> list[str]:
    """Extract keyword name strings from a TMDB keywords response.

    Branches on envelope:
    - movie → ``raw_keywords["keywords"]``
    - tv    → ``raw_keywords["results"]`` (TMDB inconsistency — Phase 4 confirmed)

    Args:
        raw_keywords: Response from /movie/{id}/keywords or /tv/{id}/keywords.
        media_type: "movie" or "tv".

    Returns:
        List of keyword name strings.
    """
    if media_type == "tv":
        items = raw_keywords.get("results", []) or []
    else:
        items = raw_keywords.get("keywords", []) or []
    return [kw["name"] for kw in items if kw.get("name")]


def parse_season_details(raw: dict[str, Any], provider: str) -> SeasonDetails:
    """Map TMDB season response → SeasonDetails.

    Args:
        raw: Response from /tv/{id}/season/{n}.
        provider: Provider name ("tmdb").

    Returns:
        Populated SeasonDetails with episodes parsed.
    """
    episodes = [parse_episode(ep) for ep in raw.get("episodes", []) or []]
    return SeasonDetails(
        provider=provider,
        tv_id=str(raw.get("_tv_id", raw.get("id", ""))),
        season_number=raw["season_number"],
        episodes=episodes,
    )
