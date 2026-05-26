"""TVDB → TMDB-shaped show_data conversion.

Extracted from :mod:`personalscraper.scraper.tv_service` (sub-phase 11.6 / S5)
to keep ``tv_service.py`` below the 1000-LOC hard ceiling. The public symbol
:func:`_tvdb_series_to_show_data` is re-exported from ``tv_service`` so all
existing import paths (``from personalscraper.scraper.tv_service import
_tvdb_series_to_show_data``) and ``unittest.mock.patch`` targets keep working
unchanged.

This module owns the conversion logic — both the typed
:class:`~personalscraper.api.metadata._base.MediaDetails` branch and the legacy
raw-dict branch.
"""

from __future__ import annotations

from typing import Any

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._base import MediaDetails
from personalscraper.api.metadata._tvdb_parsers import map_language
from personalscraper.logger import get_logger
from personalscraper.scraper.models import ScraperExternalIds

log = get_logger("scraper")


def _tvdb_series_to_show_data(
    tvdb_data: "MediaDetails | dict[str, Any]",
    tvdb_id: int,
    tvdb_client: Any = None,
    preferred_language: str = "fr-FR",
    fallback_language: str = "en-US",
    *,
    external_ids: "ScraperExternalIds | None" = None,
) -> dict[str, Any]:
    """Convert TVDB series data to a TMDB-like show_data dict.

    Builds a show_data compatible with generate_tvshow_nfo() and
    download_tvshow_artwork() using TVDB fields. Whenever a TV show is
    matched via TVDB, this is the source of truth for folder naming,
    NFO content, artwork, and episode lookups — the TMDB id is only
    embedded as a secondary uniqueid cross-reference and never queried
    for content.

    Phase 27: ``tvdb_data`` is now ``MediaDetails`` in production
    (api-unify ``TVDBClient.get_series`` returns the typed model). The
    function preserves backward compatibility by also accepting the raw
    TVDB extended dict — useful for tests that have not migrated and for
    rare callers that still hold the unparsed payload. Internally, the
    typed branch derives the same TMDB-flavoured output by reading
    ``MediaDetails`` fields populated by ``_tvdb_parsers.parse_media_details``.

    Lossy fields when the input is ``MediaDetails``:
    - ``status`` (TVDB extended ``status.name``) — not in MediaDetails;
      empty string in the output. Affects only the NFO ``<status>`` tag.
    - ``contentRatings`` — not in MediaDetails; empty list in the output.
      Affects only the NFO ``<mpaa>`` tag.
    - language-specific translations — MediaDetails carries the
      provider-default name + ``original_title``; per-locale translations
      are not preserved. ``preferred_language`` / ``fallback_language``
      become no-ops in the typed branch.

    Args:
        tvdb_data: Either the typed ``MediaDetails`` from
            ``TVDBClient.get_series`` (api-unify) or the raw TVDB extended
            series dict (legacy callers / fixtures).
        tvdb_id: TVDB series ID (embedded in external_ids for NFO generation).
        tvdb_client: Optional TVDB client used to fetch artworks. When None, the
            returned dict has empty ``images`` (legacy call sites that don't
            need artwork).
        preferred_language: Configured scraping language. Used to select TVDB
            translated titles when available (legacy dict path only).
        fallback_language: Fallback scraping language (legacy dict path only).
        external_ids: Optional Pydantic ScraperExternalIds carrying TMDB/IMDB
            cross-references. When ``None`` an empty instance is used (no
            cross-refs).

    Returns:
        Dict with TMDB-compatible fields for NFO/artwork generation.
    """
    eff_ids = external_ids if external_ids is not None else ScraperExternalIds()
    _resolved_tmdb_id = eff_ids.tmdb_id or 0
    _resolved_imdb_id = eff_ids.imdb_id

    if isinstance(tvdb_data, MediaDetails):
        # api-unify path — read the typed model directly.
        display_name = tvdb_data.title
        original_name = tvdb_data.original_title or tvdb_data.title
        overview_text = tvdb_data.overview
        status_name = ""  # MediaDetails does not preserve TVDB ``status.name``.
        content_ratings_results: list[dict[str, str]] = []
        seasons = [
            {"season_number": s.season_number, "poster_path": s.poster_url}
            for s in tvdb_data.seasons
            if s.season_number > 0
        ]
        # Genre names are available; IDs are dropped at this boundary because
        # the legacy dict shape only exposes ``[{"name": ...}]``.
        genres = [{"name": g} for g in tvdb_data.genres if g]
        # first_air_date built from MediaDetails.year when present.
        first_air = f"{tvdb_data.year}-01-01" if tvdb_data.year else ""
        # Build external_ids dict from the resolved ScraperExternalIds.
        # tvdb_id is always present (it is the canonical provider here).
        external_ids_typed: dict[str, str | int] = {"tvdb_id": tvdb_id}
        if _resolved_tmdb_id:
            external_ids_typed["tmdb_id"] = _resolved_tmdb_id
        if _resolved_imdb_id:
            external_ids_typed["imdb_id"] = _resolved_imdb_id
    else:
        # Legacy dict path — preserved for tests + rare callers.
        status_raw = tvdb_data.get("status", {})
        status_name = status_raw.get("name", "") if isinstance(status_raw, dict) else str(status_raw)

        # Build content_ratings in TMDB format: {results: [{rating, iso_3166_1}]}
        content_ratings_results = []
        for cr in tvdb_data.get("contentRatings", []) or []:
            rating = cr.get("name", "")
            country = cr.get("country", "")
            if rating:
                content_ratings_results.append({"rating": rating, "iso_3166_1": country})

        # Build seasons list in TMDB format: [{season_number, poster_path}]
        seasons = []
        for s in tvdb_data.get("seasons", []) or []:
            s_num = s.get("number", s.get("season_number", 0))
            if s_num and s_num > 0:
                seasons.append({"season_number": s_num, "poster_path": ""})

        # Genres in legacy dict shape (already TVDB-style)
        genres = [{"name": g.get("name", "")} for g in (tvdb_data.get("genres") or [])]

        # first_air_date: TVDB uses firstAired ("YYYY-MM-DD"); fallback to year field.
        first_air = tvdb_data.get("firstAired") or ""
        if not first_air:
            year_val = tvdb_data.get("year")
            if isinstance(year_val, int) and year_val > 0:
                first_air = f"{year_val}-01-01"
            elif isinstance(year_val, str) and year_val.isdigit():
                first_air = f"{year_val}-01-01"

        raw_name = tvdb_data.get("name", "")
        lang_code = preferred_language.split("-", 1)[0].lower()
        tvdb_lang_code = map_language(lang_code)
        translations = tvdb_data.get("translations") or {}
        translated_overview: str | None = None
        translated_name = None
        if isinstance(translations, dict):
            translated_name = translations.get(lang_code) or translations.get(tvdb_lang_code)
        if not translated_name:
            fallback_code = fallback_language.split("-", 1)[0].lower()
            fallback_tvdb_code = map_language(fallback_code)
            if isinstance(translations, dict):
                translated_name = translations.get(fallback_code) or translations.get(fallback_tvdb_code)
        display_name = translated_name or raw_name
        original_name = tvdb_data.get("originalName") or raw_name
        overview_text = translated_overview or tvdb_data.get("overview", "")
        external_ids_typed = {"tvdb_id": tvdb_id}
        if _resolved_tmdb_id:
            external_ids_typed["tmdb_id"] = _resolved_tmdb_id
        if _resolved_imdb_id:
            external_ids_typed["imdb_id"] = _resolved_imdb_id

    # Fetch TVDB artworks via the typed API when a client is provided.
    posters: list[dict[str, Any]] = []
    backdrops: list[dict[str, Any]] = []
    if tvdb_client is not None:
        try:
            all_artworks = tvdb_client.get_artwork_urls(str(tvdb_id), media_type=MediaType.TV)
            posters = [
                {"file_path": a.url, "iso_639_1": a.language or ""}
                for a in all_artworks
                if a.type == "poster" and a.url
            ]
            backdrops = [
                {"file_path": a.url, "iso_639_1": a.language or ""}
                for a in all_artworks
                if a.type == "backdrop" and a.url
            ]
        except Exception as exc:  # noqa: BLE001 — artwork fetch is best-effort
            log.warning("tvdb_artwork_fetch_failed", tvdb_id=tvdb_id, error=str(exc))

    return {
        "id": _resolved_tmdb_id,  # Cross-ref TMDB id (0 when none) — NFO-only, never queried
        "name": display_name,
        "original_name": original_name,
        "overview": overview_text,
        "status": status_name,
        "genres": genres,
        "networks": [],
        "first_air_date": first_air,
        "vote_average": 0.0,
        "vote_count": 0,
        "number_of_episodes": 0,
        "number_of_seasons": len(seasons),
        "external_ids": external_ids_typed,
        "content_ratings": {"results": content_ratings_results},
        "seasons": seasons,
        "images": {"posters": posters, "backdrops": backdrops},
        "aggregate_credits": {"cast": []},
    }
