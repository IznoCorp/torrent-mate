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
from pathlib import Path

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


__all__ = ["ARTWORK_KIND_RES", "SEASON_ARTWORK_RE", "artwork_flags", "has_poster"]
