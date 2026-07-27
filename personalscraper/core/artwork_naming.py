"""Canonical artwork filename conventions — the ONE detection every layer uses.

Artwork on disk carries several legitimate spellings: the bare form
(``poster.jpg``, Kodi ``folder.jpg``), the scraper's title-prefixed form
(``{Title}-poster.jpg``) and MediaElch's folder-name-prefixed form
(``{Folder Name (YYYY)}-poster.png``), including MediaElch's short aliases
(``-logo`` → clearlogo, ``-disc`` → discart). Exact-name checks scattered
across layers each recognized a different subset and disagreed about reality
(e2e loops 1-2: items « sans poster » with their posters on disk; INDEXER-03:
the two scan modes wrote divergent ``artwork_json``).

This module is the single owner of that detection. The full 8-kind inventory
(:func:`artwork_inventory`) is what the indexer's ``artwork_json`` column
records; the 3-kind completeness view (:class:`ArtworkStatus` /
:func:`artwork_status`) is what the completeness read-model reasons about.
Both derive from the same regex table, so every consumer sees ONE reality.

Import direction: stdlib only — usable from indexer/, maintenance/ and web/.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

#: Completeness-relevant item-level artwork kinds, in a fixed order. The full
#: 8-kind inventory stays behind :func:`artwork_inventory`; :class:`ArtworkStatus`
#: only surfaces the three kinds the completeness read-model reasons about.
_STATUS_KINDS: tuple[str, ...] = ("poster", "fanart", "landscape")

#: Item-level artwork kind → canonical filename matcher (case-insensitive,
#: jpg/jpeg/png, bare or ``{prefix}-`` forms). ``folder.*`` counts as poster
#: (Kodi). ``clearlogo`` also accepts MediaElch's ``{prefix}-logo`` alias and
#: ``discart`` its ``{prefix}-disc`` alias — the short spellings MediaElch (the
#: project's manual scraper fallback) and Plex local-art agents emit. This is
#: the UNION previously split across the enrich-mode suffix table, the
#: item-stage flags, the web read-model and the drift validator.
ARTWORK_KIND_RES: dict[str, re.Pattern[str]] = {
    "poster": re.compile(r"(?:^|.+-)(?:poster|folder)\.(?:jpe?g|png)$", re.IGNORECASE),
    "fanart": re.compile(r"(?:^|.+-)fanart\.(?:jpe?g|png)$", re.IGNORECASE),
    "landscape": re.compile(r"(?:^|.+-)landscape\.(?:jpe?g|png)$", re.IGNORECASE),
    "banner": re.compile(r"(?:^|.+-)banner\.(?:jpe?g|png)$", re.IGNORECASE),
    "clearlogo": re.compile(r"(?:(?:^|.+-)clearlogo|.+-logo)\.(?:jpe?g|png)$", re.IGNORECASE),
    "clearart": re.compile(r"(?:^|.+-)clearart\.(?:jpe?g|png)$", re.IGNORECASE),
    "discart": re.compile(r"(?:(?:^|.+-)discart|.+-disc)\.(?:jpe?g|png)$", re.IGNORECASE),
    "characterart": re.compile(r"(?:^|.+-)characterart\.(?:jpe?g|png)$", re.IGNORECASE),
}

#: Season-level artwork (``seasonNN-poster.jpg``) — excluded from item flags.
SEASON_ARTWORK_RE = re.compile(r"^season\d+-", re.IGNORECASE)


def artwork_inventory_from_names(names: Iterable[str]) -> dict[str, str | None]:
    """Classify already-listed filenames into the 8-kind artwork inventory.

    The pure (I/O-free) matcher shared by every layer, so the enrich scan mode
    (which lists via :func:`os.scandir` to keep its transient-error contract),
    the full/item-stage scan mode, the web read-model and the drift validator
    all agree on what artwork a directory holds (INDEXER-03). Season posters
    (``seasonNN-*``) are excluded — they are per-season facts, never the item's
    own poster.

    Args:
        names: The plain filenames (not paths) found directly in one directory.

    Returns:
        Mapping ``kind -> matched filename`` for every kind in
        :data:`ARTWORK_KIND_RES`, or ``None`` for a kind with no match. Names are
        scanned in sorted order so the matched filename is deterministic when
        several spellings of the same kind coexist.
    """
    inventory: dict[str, str | None] = dict.fromkeys(ARTWORK_KIND_RES, None)
    for name in sorted(names):
        if SEASON_ARTWORK_RE.match(name):
            continue
        for kind, pattern in ARTWORK_KIND_RES.items():
            if inventory[kind] is None and pattern.match(name):
                inventory[kind] = name
    return inventory


def artwork_inventory(directory: Path) -> dict[str, str | None]:
    """Detect the full 8-kind artwork inventory from ONE directory listing.

    The single artwork-presence owner the indexer's ``artwork_json`` column and
    the completeness read-model both consume (DESIGN §5 T4 / INDEXER-03).

    Args:
        directory: The media directory to inspect.

    Returns:
        Mapping ``kind -> matched filename`` (see
        :func:`artwork_inventory_from_names`); every kind maps to ``None`` on an
        unreadable directory (fail-soft). Callers that must distinguish "empty"
        from "unreadable" (the enrich pass, to avoid overwriting valid DB data
        on a transient error) list the directory themselves and call
        :func:`artwork_inventory_from_names`.
    """
    try:
        names = [child.name for child in directory.iterdir() if child.is_file()]
    except OSError:
        return dict.fromkeys(ARTWORK_KIND_RES, None)
    return artwork_inventory_from_names(names)


def artwork_flags(directory: Path) -> dict[str, bool]:
    """Detect item-level artwork kinds from ONE directory listing.

    Thin boolean view over :func:`artwork_inventory`.

    Args:
        directory: The media directory to inspect.

    Returns:
        Mapping ``kind -> present`` for every kind in
        :data:`ARTWORK_KIND_RES` (all ``False`` on an unreadable directory —
        fail-soft).
    """
    return {kind: name is not None for kind, name in artwork_inventory(directory).items()}


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
    ``landscape``); the full 8-kind inventory stays behind
    :func:`artwork_inventory`. Detection spans every legitimate spelling
    recognized across the codebase — the bare Kodi name (``poster.jpg``), the
    Kodi ``folder.jpg``, the scraper's title-prefixed form
    (``{Title}-poster.jpg``) and MediaElch's folder-prefixed form
    (``{Folder (YYYY)}-poster.png``), case-insensitive, ``jpg``/``jpeg``/
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
    Delegates detection to :func:`artwork_inventory` and surfaces only the three
    completeness-relevant kinds. Detection is convention-based (see
    :data:`ARTWORK_KIND_RES`) and identical for movies and TV shows at the item
    root — season posters (``seasonNN-*``) are excluded for both. *media_type* is
    accepted for API symmetry with the rest of the completeness read-model
    (``nfo_status`` / ``media_completeness``) and for forward compatibility; it
    does not currently change item-root detection.

    Args:
        directory: The media directory to inspect.
        media_type: ``"movie"`` or ``"tvshow"`` — accepted for symmetry; item-root
            detection is media-type-agnostic.

    Returns:
        An :class:`ArtworkStatus` (all ``False`` / ``None`` on an unreadable
        directory — fail-soft), recording the concrete matched filename per kind.
    """
    inventory = artwork_inventory(directory)
    return ArtworkStatus(
        poster=inventory["poster"] is not None,
        fanart=inventory["fanart"] is not None,
        landscape=inventory["landscape"] is not None,
        poster_name=inventory["poster"],
        fanart_name=inventory["fanart"],
        landscape_name=inventory["landscape"],
    )


__all__ = [
    "ARTWORK_KIND_RES",
    "SEASON_ARTWORK_RE",
    "ArtworkStatus",
    "artwork_flags",
    "artwork_inventory",
    "artwork_inventory_from_names",
    "artwork_status",
    "has_poster",
]
