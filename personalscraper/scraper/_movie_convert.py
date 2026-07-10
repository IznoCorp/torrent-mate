"""Typed-to-legacy metadata conversion shims (phase 27).

Extracted verbatim from ``movie_service.py`` to keep that module under the
1000-LOC hard ceiling (the S5 scrape-arbiter changes pushed it over). These are
pure ``MediaDetails → dict`` adapters with no dependency on the scraper service
class, so they live cleanly on their own.

The downstream NFO generator and artwork downloader still expect the historical
TMDB-flavoured raw dict, so these helpers render the typed model into that dict
at the boundary, leaving the consumers untouched until they migrate.
"""

from __future__ import annotations

from itertools import zip_longest
from typing import Any

from personalscraper.api.metadata._base import MediaDetails


def _media_details_to_movie_data(details: MediaDetails) -> dict[str, Any]:
    """Adapt typed MediaDetails into the legacy movie_data dict shape.

    Phase 27 transitional shim — mirrors the TV equivalent
    (``_tvdb_series_to_show_data``) for movies. The downstream NFO
    generator and artwork downloader still expect the historical
    TMDB-flavoured raw dict, so this helper renders the typed model
    into that dict at the boundary, leaving the consumers untouched
    until they migrate.

    Mapping:
    - title / original_title / overview / year → top-level fields
    - genres + genre_ids → ``genres: [{"id", "name"}]`` zipped
    - rating → ``vote_average``
    - runtime_minutes → ``runtime``
    - origin_countries / production_countries → both lists, dict shape
    - external_ids → ``external_ids: {"imdb_id", "tvdb_id", ...}``
    - images (curated ArtworkItem list) split by type into ``posters``
      and ``backdrops`` arrays under ``images: {posters, backdrops}``
    - primary_backdrop_url surfaces as top-level ``backdrop_path`` for
      the legacy fallback path in ``ArtworkDownloader``.

    Args:
        details: Typed metadata payload from a TMDB ``get_movie`` call.

    Returns:
        Dict whose keys match the legacy TMDB movie response shape used
        by NFO + artwork consumers.
    """
    posters = [
        {"file_path": a.url, "iso_639_1": a.language, "vote_average": a.vote_average}
        for a in details.images
        if a.type == "poster" and a.url
    ]
    backdrops = [
        {"file_path": a.url, "iso_639_1": a.language, "vote_average": a.vote_average}
        for a in details.images
        if a.type == "backdrop" and a.url
    ]
    logos = [
        {"file_path": a.url, "iso_639_1": a.language, "vote_average": a.vote_average}
        for a in details.images
        if a.type == "landscape" and a.url
    ]

    # Provider id is a string in the typed model; downstream often expects int
    # for ``id`` (TMDB numeric). Coerce when it parses cleanly.
    raw_id = details.provider_id
    pid: int | str = int(raw_id) if raw_id.isdigit() else raw_id

    return {
        "id": pid,
        "title": details.title,
        "original_title": details.original_title,
        "name": details.title,  # alias for code paths that branch on TV-style "name"
        "original_name": details.original_title,
        "overview": details.overview,
        "release_date": f"{details.year}-01-01" if details.year else "",
        "first_air_date": f"{details.year}-01-01" if details.year else "",
        "runtime": details.runtime_minutes,
        "vote_average": details.rating or 0.0,
        "vote_count": 0,
        "genres": [
            {"id": gid, "name": gname}
            for gid, gname in zip_longest(details.genre_ids, details.genres, fillvalue=None)
            if gid is not None or gname
        ],
        "origin_country": list(details.origin_countries),
        "production_countries": [{"iso_3166_1": c} for c in details.production_countries],
        "production_companies": [],
        "external_ids": {f"{k}_id": v for k, v in details.external_ids.items()},
        "imdb_id": details.external_ids.get("imdb", ""),
        "images": {"posters": posters, "backdrops": backdrops, "logos": logos},
        "backdrop_path": details.primary_backdrop_url,
        "credits": {"cast": [], "crew": []},
        "release_dates": {"results": []},
    }


def _coerce_to_movie_data(data: MediaDetails | dict[str, Any]) -> dict[str, Any]:
    """Return ``data`` as a movie_data-shaped dict.

    Accepts the typed MediaDetails emitted by api-unify clients or a
    legacy raw-dict from older callers / test fixtures.
    """
    if isinstance(data, MediaDetails):
        return _media_details_to_movie_data(data)
    return data


def _media_details_to_show_data(details: MediaDetails) -> dict[str, Any]:
    """Adapt typed MediaDetails into the legacy show_data dict for TV shows.

    Phase 27 transitional shim — extension of ``_media_details_to_movie_data``
    that also surfaces the ``seasons`` summary array. The artwork downloader
    uses ``show_data["seasons"]`` to find per-season posters keyed on
    ``season_number``; without this the season-poster path silently degrades
    to "show poster only" on every TMDB-resolved TV show repair.

    Args:
        details: Typed metadata from a TMDB ``get_tv`` call.

    Returns:
        Dict whose keys match the legacy TMDB TV-show response shape used by
        NFO + artwork consumers.
    """
    base = _media_details_to_movie_data(details)
    base["seasons"] = [
        {
            "season_number": s.season_number,
            "episode_count": s.episode_count,
            "poster_path": s.poster_url,
            "name": "",
            "overview": "",
        }
        for s in details.seasons
    ]
    return base


def _coerce_to_show_data(data: MediaDetails | dict[str, Any]) -> dict[str, Any]:
    """Return ``data`` as a show_data-shaped dict for TV consumers."""
    if isinstance(data, MediaDetails):
        return _media_details_to_show_data(data)
    return data
