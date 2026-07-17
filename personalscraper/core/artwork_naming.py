"""Canonical artwork filename conventions — the ONE detection every layer uses.

Artwork on disk carries several legitimate spellings: the bare form
(``poster.jpg``, Kodi ``folder.jpg``), the scraper's title-prefixed form
(``{Title}-poster.jpg``) and MediaElch's folder-name-prefixed form
(``{Folder Name (YYYY)}-poster.png``). Exact-name checks scattered across
layers each recognized a different subset and disagreed about reality
(e2e loops 1-2: items « sans poster » with their posters on disk).

Import direction: stdlib only — usable from indexer/, maintenance/ and web/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: Completeness-relevant item-level artwork kinds, in a fixed order. The full
#: 8-kind inventory stays behind :func:`artwork_flags`; :class:`ArtworkStatus`
#: only surfaces the three kinds the completeness read-model reasons about.
_STATUS_KINDS: tuple[str, ...] = ("poster", "fanart", "landscape")

#: Item-level artwork kind → canonical filename matcher (case-insensitive,
#: jpg/jpeg/png, bare or ``{prefix}-`` forms; ``folder.*`` counts as poster).
ARTWORK_KIND_RES: dict[str, re.Pattern[str]] = {
    "poster": re.compile(r"(?:^|.+-)(?:poster|folder)\.(?:jpe?g|png)$", re.IGNORECASE),
    "fanart": re.compile(r"(?:^|.+-)fanart\.(?:jpe?g|png)$", re.IGNORECASE),
    "landscape": re.compile(r"(?:^|.+-)landscape\.(?:jpe?g|png)$", re.IGNORECASE),
    "banner": re.compile(r"(?:^|.+-)banner\.(?:jpe?g|png)$", re.IGNORECASE),
    "clearlogo": re.compile(r"(?:^|.+-)clearlogo\.(?:jpe?g|png)$", re.IGNORECASE),
    "clearart": re.compile(r"(?:^|.+-)clearart\.(?:jpe?g|png)$", re.IGNORECASE),
    "discart": re.compile(r"(?:^|.+-)discart\.(?:jpe?g|png)$", re.IGNORECASE),
    "characterart": re.compile(r"(?:^|.+-)characterart\.(?:jpe?g|png)$", re.IGNORECASE),
}

#: Season-level artwork (``seasonNN-poster.jpg``) — excluded from item flags.
SEASON_ARTWORK_RE = re.compile(r"^season\d+-", re.IGNORECASE)


def artwork_flags(directory: Path) -> dict[str, bool]:
    """Detect item-level artwork kinds from ONE directory listing.

    Args:
        directory: The media directory to inspect.

    Returns:
        Mapping ``kind -> present`` for every kind in
        :data:`ARTWORK_KIND_RES` (all ``False`` on an unreadable directory —
        fail-soft).
    """
    flags = dict.fromkeys(ARTWORK_KIND_RES, False)
    try:
        names = [c.name for c in directory.iterdir() if c.is_file()]
    except OSError:
        return flags
    for name in names:
        if SEASON_ARTWORK_RE.match(name):
            continue
        for kind, pattern in ARTWORK_KIND_RES.items():
            if not flags[kind] and pattern.match(name):
                flags[kind] = True
    return flags


def has_poster(directory: Path) -> bool:
    """Whether *directory* holds an item-level poster in any canonical spelling.

    Args:
        directory: The media directory to inspect.

    Returns:
        ``True`` iff a poster/folder image is present (season posters excluded).
    """
    return artwork_flags(directory)["poster"]


@dataclass(frozen=True)
class ArtworkStatus:
    """Canonical item-level artwork presence for the completeness read-model.

    Surfaces only the three completeness-relevant kinds (``poster``, ``fanart``,
    ``landscape``); the full 8-kind inventory stays behind :func:`artwork_flags`.
    Detection spans every legitimate spelling recognized across the codebase —
    the bare Kodi name (``poster.jpg``), the Kodi ``folder.jpg``, the scraper's
    title-prefixed form (``{Title}-poster.jpg``) and MediaElch's folder-prefixed
    form (``{Folder (YYYY)}-poster.png``), case-insensitive, ``jpg``/``jpeg``/
    ``png`` — the UNION previously split across six divergent presence checks.

    Attributes:
        poster: Whether an item-level poster/folder image is present.
        fanart: Whether an item-level fanart image is present.
        landscape: Whether an item-level landscape image is present.
        poster_name: Filename of the matched poster, or ``None`` when absent.
            Lets a consumer serve/log the concrete file without re-scanning.
        fanart_name: Filename of the matched fanart, or ``None``.
        landscape_name: Filename of the matched landscape, or ``None``.
    """

    poster: bool
    fanart: bool
    landscape: bool
    poster_name: str | None = None
    fanart_name: str | None = None
    landscape_name: str | None = None


def artwork_status(directory: Path, media_type: str = "movie") -> ArtworkStatus:
    """Detect canonical poster/fanart/landscape presence from ONE directory listing.

    The single artwork-presence owner every layer must consult (DESIGN §5 T4).
    Detection is convention-based (see :data:`ARTWORK_KIND_RES`) and identical for
    movies and TV shows at the item root — season posters (``seasonNN-*``) are
    excluded for both. *media_type* is accepted for API symmetry with the rest of
    the completeness read-model (``nfo_status`` / ``media_completeness``) and for
    forward compatibility; it does not currently change item-root detection.

    Args:
        directory: The media directory to inspect.
        media_type: ``"movie"`` or ``"tvshow"`` — accepted for symmetry; item-root
            detection is media-type-agnostic.

    Returns:
        An :class:`ArtworkStatus` (all ``False`` / ``None`` on an unreadable
        directory — fail-soft), recording the concrete matched filename per kind.
    """
    try:
        names = [c.name for c in directory.iterdir() if c.is_file()]
    except OSError:
        return ArtworkStatus(poster=False, fanart=False, landscape=False)
    found: dict[str, str] = {}
    for name in names:
        if SEASON_ARTWORK_RE.match(name):
            continue
        for kind in _STATUS_KINDS:
            if kind not in found and ARTWORK_KIND_RES[kind].match(name):
                found[kind] = name
    return ArtworkStatus(
        poster="poster" in found,
        fanart="fanart" in found,
        landscape="landscape" in found,
        poster_name=found.get("poster"),
        fanart_name=found.get("fanart"),
        landscape_name=found.get("landscape"),
    )


__all__ = [
    "ARTWORK_KIND_RES",
    "SEASON_ARTWORK_RE",
    "ArtworkStatus",
    "artwork_flags",
    "artwork_status",
    "has_poster",
]
