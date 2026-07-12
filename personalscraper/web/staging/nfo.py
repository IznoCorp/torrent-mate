"""Minimal read-only NFO metadata extraction for the staging read-model.

The scraper writes Kodi/Plex-style ``movie.nfo`` / ``tvshow.nfo`` files into
each staged media folder. This module reads the handful of fields the staging
library grid + timeline need — title, year, plot, and the ``<uniqueid>``
provider ids — without pulling in the full scraper stack. The heavier NFO
writers/validators live under ``personalscraper.scraper`` and
``personalscraper.verify``; this reader is deliberately tiny and dependency-free
so the web layer can call it on a hot list endpoint.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405 — trusted local NFO we wrote
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.logger import get_logger

logger = get_logger(__name__)

#: NFO file names, by media kind, in the order the scraper emits them.
_NFO_NAMES: dict[str, str] = {"movie": "movie.nfo", "tvshow": "tvshow.nfo"}


@dataclass(slots=True)
class NfoMetadata:
    """The subset of NFO fields the staging read-model surfaces.

    Attributes:
        title: ``<title>`` text, or ``None`` when absent/empty.
        year: ``<year>`` parsed to ``int``, or ``None``.
        overview: ``<plot>`` text, or ``None``.
        provider_ids: ``<uniqueid type=...>`` rows keyed by lowercased family
            (e.g. ``{"tvdb": "475278", "tmdb": "315820"}``) — empty values are
            dropped so an ``<uniqueid type="imdb" />`` placeholder is ignored.
        category_id: The scraper's storage ``<category>`` id (e.g.
            ``"tv_shows"``, ``"movies_animation"``) when present — lets the
            dispatch preview resolve the exact target category instead of a
            kind-based guess.
    """

    title: str | None = None
    year: int | None = None
    overview: str | None = None
    provider_ids: dict[str, str] = field(default_factory=dict)
    category_id: str | None = None


def nfo_path_for(media_dir: Path, media_kind: str) -> Path | None:
    """Return the expected NFO path for a media kind, or ``None`` if unsupported.

    Args:
        media_dir: The media folder in staging.
        media_kind: ``"movie"`` or ``"tvshow"`` (other kinds have no NFO).

    Returns:
        The ``media.nfo`` / ``tvshow.nfo`` path (existence not checked), or
        ``None`` when the kind carries no NFO.
    """
    name = _NFO_NAMES.get(media_kind)
    return media_dir / name if name is not None else None


def _clean_text(value: str | None) -> str | None:
    """Strip an XML text value, returning ``None`` for empty/whitespace.

    Args:
        value: Raw ``element.text`` (may be ``None``).

    Returns:
        The stripped string, or ``None`` when empty.
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def read_nfo_metadata(nfo_path: Path) -> NfoMetadata:
    """Parse a staged NFO into an :class:`NfoMetadata`, fail-soft.

    Never raises: a missing file, a parse error, or a malformed year all
    degrade to an empty/partial :class:`NfoMetadata` (logged at debug), so the
    caller can still list the media with whatever it could recover.

    Args:
        nfo_path: Absolute path to ``movie.nfo`` / ``tvshow.nfo``.

    Returns:
        The extracted metadata (empty when nothing could be read).
    """
    if not nfo_path.is_file():
        return NfoMetadata()

    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314 — trusted local NFO
    except (ET.ParseError, OSError) as exc:
        logger.debug("staging_nfo_parse_failed", nfo_path=str(nfo_path), error=str(exc))
        return NfoMetadata()

    year: int | None = None
    raw_year = _clean_text(root.findtext("year"))
    if raw_year is not None:
        try:
            year = int(raw_year)
        except ValueError:
            year = None

    provider_ids: dict[str, str] = {}
    for uid in root.findall("uniqueid"):
        family = (uid.get("type") or "").strip().lower()
        value = _clean_text(uid.text)
        if family and value:
            provider_ids[family] = value

    return NfoMetadata(
        title=_clean_text(root.findtext("title")),
        year=year,
        overview=_clean_text(root.findtext("plot")),
        provider_ids=provider_ids,
        category_id=_clean_text(root.findtext("category")),
    )
