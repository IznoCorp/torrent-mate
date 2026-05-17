"""TMDB response → typed model parsers.

Pure functions, no HTTP — testable against golden samples from
docs/reference/_samples/tmdb/. Every parser maps raw TMDB JSON
fields to the typed models defined in api/metadata/_base.py.

Field shapes were confirmed against live TMDB API responses on 2026-05-04
and are pinned by the golden samples in docs/reference/_samples/tmdb/.
"""

from __future__ import annotations

from typing import Any

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    SearchResult,
    SeasonDetails,
    SeasonInfo,
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
    original_title = raw.get("original_name" if is_tv else "original_title", "")
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
        media_type=MediaType.TV if is_tv else MediaType.MOVIE,
        overview=raw.get("overview", "") or "",
        poster_url=_build_image_url(raw.get("poster_path"), "w500"),
        original_title=original_title or "",
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
                vote_average=float(img.get("vote_average") or 0.0),
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
                vote_average=float(img.get("vote_average") or 0.0),
            )
        )

    for img in images_raw.get("logos", []) or []:
        items.append(
            ArtworkItem(
                type="landscape",
                url=_build_image_url(img.get("file_path"), "w500"),
                language=img.get("iso_639_1") or "",
                vote_average=float(img.get("vote_average") or 0.0),
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

    # Genres (names + IDs in parallel — classifier rules consume IDs).
    raw_genres = raw.get("genres", []) or []
    genres = [g["name"] for g in raw_genres if isinstance(g, dict) and g.get("name")]
    genre_ids = [int(g["id"]) for g in raw_genres if isinstance(g, dict) and isinstance(g.get("id"), int)]

    # Images (curated artwork list)
    images = parse_artwork(raw.get("images", {}) or {})

    # Primary backdrop URL fallback (top-level ``backdrop_path`` is the
    # provider's editor-pick; consumers fall back to it when ``images``
    # carries no ``backdrop`` entries).
    primary_backdrop_url = _build_image_url(raw.get("backdrop_path"), "w1280")

    # Country lists. Movies: ``production_countries[*].iso_3166_1``.
    # TV: ``origin_country: [<code>, ...]`` (top-level) and optionally
    # ``production_countries`` too (newer TMDB responses include both).
    origin_countries: list[str] = []
    raw_origin = raw.get("origin_country") or []
    if isinstance(raw_origin, list):
        origin_countries = [c for c in raw_origin if isinstance(c, str)]
    production_countries: list[str] = []
    for pc in raw.get("production_countries", []) or []:
        if isinstance(pc, dict):
            code = pc.get("iso_3166_1")
            if isinstance(code, str):
                production_countries.append(code)

    # Seasons (TV only). Provider responses give a ``seasons[*]`` block on
    # ``/tv/{id}`` with ``season_number``, ``episode_count``, ``overview``,
    # ``poster_path``. Empty for movies.
    seasons: list[SeasonInfo] = []
    for s in raw.get("seasons", []) or []:
        if not isinstance(s, dict):
            continue
        s_num = s.get("season_number")
        if not isinstance(s_num, int):
            continue
        seasons.append(
            SeasonInfo(
                season_number=s_num,
                episode_count=int(s.get("episode_count") or 0),
                overview=s.get("overview") or "",
                poster_url=_build_image_url(s.get("poster_path"), "w500"),
            )
        )

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
        seasons=seasons,
        genre_ids=genre_ids,
        origin_countries=origin_countries,
        production_countries=production_countries,
        primary_backdrop_url=primary_backdrop_url,
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

    Populates :attr:`EpisodeInfo.external_ids` with the canonical TMDB
    episode ID (``raw["id"]``) plus any IDs the optional
    ``external_ids`` sub-object exposes (typically ``imdb_id``,
    ``tvdb_id``) when the caller fetched a per-episode endpoint with
    ``append_to_response=external_ids``. Season-level fetches do not
    return the cross-references — :class:`IDCrossRef` (DESIGN §4) and
    the phase-5 xref enrichment fill them in later.

    Args:
        raw: A single item from ``episodes[]`` in a season response.

    Returns:
        Populated EpisodeInfo.
    """
    external_ids: dict[str, str] = {}
    tmdb_episode_id = raw.get("id")
    if tmdb_episode_id:
        external_ids["tmdb"] = str(tmdb_episode_id)
    ext = raw.get("external_ids")
    if isinstance(ext, dict):
        for key in ("imdb_id", "tvdb_id"):
            value = ext.get(key)
            if not value:
                continue
            short = key.split("_id", maxsplit=1)[0]
            external_ids.setdefault(short, str(value))
    return EpisodeInfo(
        episode_number=raw["episode_number"],
        title=raw.get("name", "") or "",
        overview=raw.get("overview", "") or "",
        air_date=raw.get("air_date", "") or "",
        runtime_minutes=raw.get("runtime") or None,
        season_number=int(raw.get("season_number") or 0),
        still_url=_build_image_url(raw.get("still_path"), "w300"),
        external_ids=external_ids,
    )


def parse_keywords(raw_keywords: dict[str, Any], media_type: MediaType) -> list[str]:
    """Extract keyword name strings from a TMDB keywords response.

    Branches on envelope:
    - movie → ``raw_keywords["keywords"]``
    - tv    → ``raw_keywords["results"]`` (TMDB API inconsistency: the two
      endpoints return the same shape under different top-level keys).

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
