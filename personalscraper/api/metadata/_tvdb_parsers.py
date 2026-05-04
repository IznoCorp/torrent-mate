"""TVDB response → typed model parsers.

Pure functions, no HTTP — testable against golden samples from
docs/reference/_samples/tvdb/. Handles TVDB envelope unwrapping,
3-char language codes, numeric artwork type IDs, and the
first_release object format.

Real-field confirmations from Phase 6 live API calls (2026-05-04).
"""

from __future__ import annotations

from typing import Any

from personalscraper.api._contracts import ApiError
from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    SearchResult,
    SeasonDetails,
    Video,
)

# -- Artwork type mapping (confirmed from /artwork/types live call) -----------

_ARTWORK_POSTER = frozenset({2, 7, 14, 27})
_ARTWORK_BACKDROP = frozenset({3, 8, 15})
_ARTWORK_CLEARLOGO = frozenset({23, 25})

# -- Language mapping (2-char pipeline → 3-char TVDB) ------------------------

_LANG_MAP: dict[str, str] = {
    "fr": "fra",
    "en": "eng",
    "es": "spa",
    "de": "deu",
    "it": "ita",
    "ja": "jpn",
    "ko": "kor",
    "pt": "por",
    "ru": "rus",
    "zh": "zho",
    "ar": "ara",
    "nl": "nld",
}


def map_language(pipeline_code: str) -> str:
    """Map a 2-char pipeline language code to a 3-char TVDB code.

    Args:
        pipeline_code: 2-char ISO code (e.g. "fr", "en").

    Returns:
        3-char TVDB code, falling back to "eng" for unknown codes.
    """
    return _LANG_MAP.get(pipeline_code, "eng")


# -- Envelope handling -------------------------------------------------------


def unwrap(data: dict[str, Any]) -> dict[str, Any] | list[Any]:
    """Strip the TVDB response envelope.

    All TVDB responses are wrapped in ``{"status": "success", "data": ...}``.
    On ``"failure"`` status, an ``ApiError`` is raised.

    Args:
        data: Full TVDB response dict.

    Returns:
        The unwrapped ``data`` payload (dict or list).

    Raises:
        ApiError: When ``status`` is ``"failure"``.
    """
    if data.get("status") == "failure":
        raise ApiError(
            provider="tvdb",
            http_status=0,
            provider_code=0,
            message=data.get("message", "Unknown TVDB error"),
        )
    return data.get("data", data)  # type: ignore[no-any-return]


# -- Search result parser ----------------------------------------------------


def parse_search_result(raw: dict[str, Any], provider: str) -> SearchResult:
    """Map a TVDB search item → SearchResult.

    Handles both series (``name``, ``first_air_time``, ``type=series``)
    and movie (``name``, ``type=movie``) search results.

    Args:
        raw: A single item from the search ``data[]`` array.
        provider: Provider name ("tvdb").

    Returns:
        Populated SearchResult.
    """
    media_type = "tv" if raw.get("type") == "series" else "movie"
    year_str = raw.get("year", "")
    year: int | None = None
    if year_str:
        try:
            year = int(str(year_str)[:4])
        except (ValueError, TypeError):
            year = None

    return SearchResult(
        provider=provider,
        provider_id=str(raw.get("tvdb_id", raw.get("id", ""))),
        title=raw.get("name", "") or "",
        year=year,
        media_type=media_type,  # type: ignore[arg-type]
        overview=raw.get("overview", "") or "",
        poster_url=raw.get("image_url", "") or "",
    )


# -- Artwork parser ----------------------------------------------------------


def parse_artwork(raw: dict[str, Any], *, season: int | None = None) -> ArtworkItem | None:
    """Map a single TVDB artwork object → ArtworkItem.

    Numeric ``type`` IDs are mapped to string types:
    - Posters (2, 7, 14, 27) → ``"poster"`` or ``"season_poster"`` when season is set
    - Backgrounds (3, 8, 15) → ``"backdrop"``
    - ClearLogos (23, 25) → ``"landscape"``
    - All other types → ``None`` (skip)

    Image URLs are full URLs — used directly.

    Args:
        raw: A single artwork object from an ``artworks[]`` array.
        season: If provided, poster type becomes ``"season_poster"``.

    Returns:
        An ArtworkItem, or ``None`` if the artwork type is not pipeline-relevant.
    """
    type_id = raw.get("type", 0)
    if type_id in _ARTWORK_POSTER:
        artwork_type = "season_poster" if season is not None else "poster"
        return ArtworkItem(
            type=artwork_type,  # type: ignore[arg-type]
            url=raw.get("image", "") or "",
            language=raw.get("language", "") or "",
            season=season,
        )
    if type_id in _ARTWORK_BACKDROP:
        return ArtworkItem(
            type="backdrop",
            url=raw.get("image", "") or "",
            language=raw.get("language", "") or "",
        )
    if type_id in _ARTWORK_CLEARLOGO:
        return ArtworkItem(
            type="landscape",
            url=raw.get("image", "") or "",
            language=raw.get("language", "") or "",
        )
    return None


def parse_artworks(artworks: list[dict[str, Any]], *, season: int | None = None) -> list[ArtworkItem]:
    """Parse a list of TVDB artwork objects into ArtworkItems, skipping irrelevant types.

    Args:
        artworks: Raw ``artworks[]`` array from a TVDB entity response.
        season: If provided, poster types become ``"season_poster"``.

    Returns:
        List of ArtworkItem (irrelevant types filtered out).
    """
    items: list[ArtworkItem] = []
    for a in artworks or []:
        item = parse_artwork(a, season=season)
        if item is not None:
            items.append(item)
    return items


# -- Media details parser ----------------------------------------------------


def parse_media_details(raw: dict[str, Any], provider: str) -> MediaDetails:
    """Map TVDB series or movie extended → MediaDetails.

    Handles field differences between series and movies:
    - Series: ``firstAired`` (string), ``averageRuntime`` (int)
    - Movies: ``first_release`` (object), ``runtime`` (int)

    Args:
        raw: Unwrapped ``data`` from series/movie extended response.
        provider: Provider name ("tvdb").

    Returns:
        Populated MediaDetails.
    """
    is_movie = "first_release" in raw

    # Year
    year: int | None = None
    if is_movie:
        fr = raw.get("first_release")
        if isinstance(fr, dict):
            date_str = fr.get("date", "")
            try:
                year = int(date_str[:4])
            except (ValueError, TypeError):
                year = None
    else:
        date_str = raw.get("firstAired", "")
        try:
            year = int(date_str[:4])
        except (ValueError, TypeError):
            year = None

    # Runtime
    runtime_minutes: int | None = None
    if is_movie:
        runtime_minutes = raw.get("runtime") or None
    else:
        runtime_minutes = raw.get("averageRuntime") or None

    # Genres (TVDB returns array of genre name strings directly)
    genres: list[str] = [g["name"] for g in raw.get("genres", []) or [] if isinstance(g, dict) and g.get("name")]

    # Artworks
    images = parse_artworks(raw.get("artworks", []) or [])

    # External IDs
    external_ids: dict[str, str] = {}
    for rid in raw.get("remoteIds", []) or []:
        if not isinstance(rid, dict):
            continue
        source = rid.get("sourceName", "")
        rid_id = rid.get("id", "")
        if source == "IMDB":
            external_ids["imdb"] = rid_id
        elif source == "TheMovieDB.com" or source == "TheMovieDB":
            external_ids["tmdb"] = rid_id
        elif source == "TVDB":
            external_ids["tvdb"] = rid_id

    title = raw.get("name", "") or ""

    return MediaDetails(
        provider=provider,
        provider_id=str(raw.get("id", "")),
        title=title,
        original_title="",
        year=year,
        overview=raw.get("overview", "") or "",
        genres=genres,
        runtime_minutes=runtime_minutes,
        rating=None,  # TVDB score is a popularity rank, not a rating
        images=images,
        external_ids=external_ids,
    )


# -- Episode parser ----------------------------------------------------------


def parse_episode(raw: dict[str, Any]) -> EpisodeInfo:
    """Map a TVDB episode object → EpisodeInfo.

    Args:
        raw: A single episode from ``episodes[]``.

    Returns:
        Populated EpisodeInfo.
    """
    return EpisodeInfo(
        episode_number=raw.get("number", 0),
        title=raw.get("name", "") or "",
        overview=raw.get("overview", "") or "",
        air_date=raw.get("aired", "") or "",
        runtime_minutes=raw.get("runtime") or None,
    )


# -- Season details parser ---------------------------------------------------


def parse_season_details(
    raw: dict[str, Any],
    provider: str,
    tv_id: str,
    season_number: int,
) -> SeasonDetails:
    """Map TVDB episodes response → SeasonDetails.

    Args:
        raw: Unwrapped ``data`` from the episodes endpoint (contains ``episodes[]``).
        provider: Provider name ("tvdb").
        tv_id: TVDB series ID.
        season_number: Season number.

    Returns:
        Populated SeasonDetails.
    """
    episodes_raw = raw.get("episodes", []) or []
    episodes = [parse_episode(ep) for ep in episodes_raw]
    return SeasonDetails(
        provider=provider,
        tv_id=tv_id,
        season_number=season_number,
        episodes=episodes,
    )


# -- Video parser ------------------------------------------------------------


def parse_video(raw: dict[str, Any]) -> Video | None:
    """Map a TVDB trailer object → Video.

    TVDB trailers are less structured than TMDB. Extracts the YouTube
    key from the URL if possible.

    Args:
        raw: A single trailer item from ``trailers[]``.

    Returns:
        A Video, or ``None`` if the trailer has no usable URL.
    """
    url = raw.get("url", "") or ""
    if not url:
        return None
    key = ""
    if "youtube.com" in url or "youtu.be" in url:
        if "v=" in url:
            key = url.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in url:
            key = url.split("youtu.be/")[-1].split("?")[0]
    return Video(
        id=str(raw.get("id", "")),
        site="youtube",
        key=key,
        type="trailer",
        official=bool(raw.get("official", False)),
        iso_639_1=raw.get("language", "") or "",
    )


def parse_videos(trailers: list[dict[str, Any]]) -> list[Video]:
    """Parse a list of TVDB trailer objects into Videos.

    Args:
        trailers: Raw ``trailers[]`` array from a TVDB entity response.

    Returns:
        List of Video (unusable trailers filtered out).
    """
    videos: list[Video] = []
    for t in trailers or []:
        v = parse_video(t)
        if v is not None and v.key:
            videos.append(v)
    return videos
