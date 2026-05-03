"""Classification pipeline multi-niveaux.

Priorité (plus fort → plus faible):
1. NFO ``<category source="personalscraper">X</category>`` — override explicite
2. ``Config.anime_rule`` — détection anime (ID ou string "animation") + origin JP,
   évalué AVANT category_rules pour ne pas être masqué par des règles "animation → tv_shows_animation"
3. ``Config.category_rules`` — patterns user (path, title, genre-string, keyword)
4. ``Config.genre_mapping`` — ID genre → category_id
5. ``default_movies_category`` / ``default_tv_category`` — fallback
6. ``None`` — caller doit skip + reporter (unreachable en pratique)

Note: The anime_rule runs before category_rules (unlike the conceptual design order)
because origin-country-gated anime detection is a stronger signal than a generic
"animation" genre string match. This mirrors the legacy GenreMapper behavior where
origin_country is checked before the string-based genre fallback.
"""

import re
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from personalscraper.conf.models.categories import CategoryRule
from personalscraper.conf.models.config import Config
from personalscraper.logger import get_logger

log = get_logger("personalscraper.conf.classifier")

MediaType = Literal["movie", "tv"]


def classify(
    config: Config,
    *,
    media_type: MediaType,
    path: Path | None = None,
    title: str | None = None,
    tmdb_genres: list[str] | None = None,
    tmdb_genre_ids: list[int] | None = None,
    tvdb_genre_ids: list[int] | None = None,
    tmdb_keywords: list[str] | None = None,
    origin_country: list[str] | None = None,
    nfo_path: Path | None = None,
) -> tuple[str | None, str]:
    """Classify a media item and return (category_id, reason_str).

    Evaluates six priority levels in order, returning as soon as a level
    produces a result. The reason string identifies which layer fired,
    useful for logs and skip-reports. See module docstring for the full
    priority chain.

    Args:
        config: Validated Config instance containing all classification rules.
        media_type: Either "movie" or "tv".
        path: Source path of the media item (used by path_contains / path_regex rules).
        title: Media title (used by title_regex rules).
        tmdb_genres: Genre name strings from TMDB API (used by tmdb_genre_contains rules).
        tmdb_genre_ids: TMDB genre IDs (used by genre_mapping and anime_rule).
        tvdb_genre_ids: TVDB genre IDs (used by genre_mapping).
        tmdb_keywords: TMDB keyword strings (used by tmdb_keyword rules).
        origin_country: ISO 3166 country codes (used by anime_rule).
        nfo_path: Path to an existing NFO file for priority-1 override.

    Returns:
        A ``(category_id | None, reason_str)`` tuple. ``reason_str`` is a short
        string such as ``"nfo_override"``, ``"anime_rule"``, ``"default_movies"``,
        etc. Returns ``(None, "no_match")`` only if all levels fail (unreachable
        in practice when defaults are configured).
    """
    # ------------------------------------------------------------------
    # Level 1 — NFO override
    # ------------------------------------------------------------------
    if nfo_path and nfo_path.exists():
        cid = _read_nfo_category(nfo_path)
        if cid:
            if cid in config.all_category_ids:
                return cid, "nfo_override"
            # Unknown / obsolete ID written in NFO — fall through to next layers
            log.warning(
                "nfo_invalid_category",
                nfo_path=str(nfo_path),
                category=cid,
                message="Falling through to next classification layer",
            )

    # ------------------------------------------------------------------
    # Level 2 — anime_rule (before category_rules)
    # ------------------------------------------------------------------
    # Anime detection runs BEFORE category_rules so that a config rule like
    # "animation → tv_shows_animation" does not shadow the more-specific
    # "Animation genre + JP origin → anime" signal. The legacy GenreMapper used
    # the same priority: origin-country-gated anime detection takes precedence
    # over the generic animation string/ID match.
    #
    # Both ID-based and string-based checks are consolidated here:
    # - ID path: TMDB genre_id == requires_genre_id (e.g. 16) + JP origin.
    # - String path: "animation" in genre name strings + JP origin (no IDs).
    ar = config.anime_rule
    if ar.enabled and ar.applies_to in (media_type, "both"):
        _anim_keyword = "animation"
        _id_anime = bool(tmdb_genre_ids and ar.requires_genre_id in tmdb_genre_ids)
        _str_anime = not tmdb_genre_ids and bool(tmdb_genres and any(_anim_keyword in g.lower() for g in tmdb_genres))
        if (
            (_id_anime or _str_anime)
            and origin_country
            and any(c in ar.requires_origin_country for c in origin_country)
        ):
            return ar.maps_to, "anime_rule"

    # ------------------------------------------------------------------
    # Level 3 — category_rules (first match wins)
    # ------------------------------------------------------------------
    for i, rule in enumerate(config.category_rules):
        # Skip rules that don't apply to this media type
        if rule.applies_to != "both" and rule.applies_to != media_type:
            continue
        if _rule_matches(
            rule,
            path=path,
            title=title,
            tmdb_genres=tmdb_genres,
            tmdb_keywords=tmdb_keywords,
        ):
            return rule.category, f"category_rules[{i}]"

    # ------------------------------------------------------------------
    # Level 4 — genre_mapping by provider IDs
    # ------------------------------------------------------------------
    if media_type == "movie":
        if tmdb_genre_ids:
            for gid in tmdb_genre_ids:
                cid = config.genre_mapping.tmdb_movies.get(gid)
                if cid:
                    return cid, f"genre_mapping.tmdb_movies[{gid}]"
    elif media_type == "tv":
        # TVDB IDs take priority over TMDB IDs for TV shows
        if tvdb_genre_ids:
            for gid in tvdb_genre_ids:
                cid = config.genre_mapping.tvdb.get(gid)
                if cid:
                    return cid, f"genre_mapping.tvdb[{gid}]"
        if tmdb_genre_ids:
            for gid in tmdb_genre_ids:
                cid = config.genre_mapping.tmdb_tv.get(gid)
                if cid:
                    return cid, f"genre_mapping.tmdb_tv[{gid}]"

    # ------------------------------------------------------------------
    # Level 5 — defaults
    # ------------------------------------------------------------------
    if media_type == "movie":
        return config.genre_mapping.default_movies_category, "default_movies"
    if media_type == "tv":
        return config.genre_mapping.default_tv_category, "default_tv"

    # ------------------------------------------------------------------
    # Level 6 — unreachable in practice (defaults are always configured)
    # ------------------------------------------------------------------
    return None, "no_match"


def classify_from_nfo(
    config: Config,
    nfo_path: Path,
    media_type: str,
) -> tuple[str | None, str]:
    """Classify a media item by parsing its NFO file.

    Extracts genres and origin_country from the NFO, then delegates to
    :func:`classify`. The ``media_type`` argument accepts the legacy
    convention ``"tvshow"`` in addition to the current ``"tv"`` because
    callers (verify/dispatch/enforce) still speak that dialect.

    A sibling ``.category`` file acts as a manual override and must
    contain a canonical category ID (e.g. ``"movies"``, ``"anime"``) —
    the legacy French-label fallback was removed with the rest of the
    V14 compat layer. Unknown IDs are logged and ignored.

    Args:
        config: Validated Config instance.
        nfo_path: Path to the NFO file to classify from.
        media_type: ``"movie"`` or ``"tvshow"`` (legacy) or ``"tv"`` (current).

    Returns:
        A ``(category_id, reason)`` tuple. ``category_id`` is either a known
        ID present in ``config.all_category_ids`` or ``None``. ``reason`` is a
        short human-readable tag (``"category_file"``, ``"nfo_parse_error"``,
        or the reason produced by :func:`classify`).
    """
    # Manual .category override — content must already be a canonical ID.
    category_file = nfo_path.parent / ".category"
    if category_file.is_file():
        try:
            content = category_file.read_text(encoding="utf-8").strip().lower()
        except OSError as exc:
            log.warning("category_file_read_error", folder=nfo_path.parent.name, error=str(exc))
            content = ""
        if content:
            if content in config.all_category_ids:
                return content, "category_file"
            log.warning(
                "category_file_invalid_id",
                content=content,
                folder=nfo_path.parent.name,
                message="Not a known category ID",
            )

    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314
    except (ET.ParseError, OSError) as exc:
        log.warning("nfo_parse_failed", nfo_file=nfo_path.name, error=str(exc))
        return None, "nfo_parse_error"

    genres = [g.text for g in root.findall("genre") if g.text]
    country_elem = root.find("country")
    country = country_elem.text if country_elem is not None and country_elem.text else None
    origin_country = [country] if country else None
    title_elem = root.find("title")
    title = title_elem.text if title_elem is not None and title_elem.text else None

    normalized: MediaType = "tv" if media_type == "tvshow" else "movie"

    return classify(
        config,
        media_type=normalized,
        path=nfo_path.parent,
        title=title,
        tmdb_genres=genres,
        origin_country=origin_country,
        nfo_path=nfo_path,
    )


def _read_nfo_category(nfo_path: Path) -> str | None:
    """Read a ``<category>`` element from an NFO file.

    Prefer ``<category source="personalscraper">`` (written by this pipeline)
    over bare ``<category>`` elements (legacy hand-edited NFOs or third-party
    tools). Returns ``None`` on parse error or if no suitable element exists.

    Priority:
    1. First ``<category>`` with ``source="personalscraper"`` attribute.
    2. First ``<category>`` with no ``source`` attribute (legacy fallback).

    Args:
        nfo_path: Path to the NFO XML file to parse.

    Returns:
        The stripped text content of the found element, or ``None``.
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314
    except (ET.ParseError, OSError):
        return None

    # Priority 1 — element written by personalscraper (disambiguates from Kodi/Plex)
    for el in root.iter("category"):
        if el.get("source") == "personalscraper" and el.text:
            return el.text.strip()

    # Priority 2 — bare <category> element (legacy / hand-edited NFOs)
    for el in root.iter("category"):
        if el.get("source") is None and el.text:
            return el.text.strip()

    return None


def _rule_matches(
    rule: CategoryRule,
    *,
    path: Path | None,
    title: str | None,
    tmdb_genres: list[str] | None,
    tmdb_keywords: list[str] | None,
) -> bool:
    """Test whether a single CategoryRule matches the provided media attributes.

    Each rule has exactly one active pattern field (enforced by Pydantic).
    Returns False if the required input for the pattern type is absent
    (e.g., path_contains rule when path is None).

    Args:
        rule: The CategoryRule to evaluate.
        path: Source path of the media item (may be None).
        title: Media title string (may be None).
        tmdb_genres: List of TMDB genre name strings (may be None or empty).
        tmdb_keywords: List of TMDB keyword strings (may be None or empty).

    Returns:
        True if the rule matches, False otherwise.
    """
    if rule.path_contains is not None:
        return path is not None and rule.path_contains in str(path)

    if rule.path_regex is not None:
        return path is not None and bool(re.search(rule.path_regex, str(path)))

    if rule.title_regex is not None:
        return title is not None and bool(re.search(rule.title_regex, title))

    if rule.tmdb_genre_contains is not None:
        if not tmdb_genres:
            return False
        needle = rule.tmdb_genre_contains.lower()
        return any(needle in g.lower() for g in tmdb_genres)

    if rule.tmdb_keyword is not None:
        if not tmdb_keywords:
            return False
        kws = rule.tmdb_keyword if isinstance(rule.tmdb_keyword, list) else [rule.tmdb_keyword]
        return any(kw in tmdb_keywords for kw in kws)

    return False
