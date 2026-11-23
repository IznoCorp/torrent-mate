"""The season and episode a release name numbers (K3 DESIGN § 2.9, SR6).

Parsed ONCE, by the engine, when a search stores its candidates, so a reader of the candidates
(the release picker) never parses a name. It reads the same markers the filters do: the ``SxxEyy``
token of :func:`~personalscraper.acquire._filters.filter_to_episode`, then guessit's season and
episode list, normalised by the helper :func:`~personalscraper.acquire._filters.filter_to_season`
uses. A candidate the episode filter kept for ``(season, episode)`` is therefore numbered
``(season, episode)``.

Import direction: ``acquire/`` only.
"""

from __future__ import annotations

import re
from typing import Final

from personalscraper.acquire._filters import _episode_numbers
from personalscraper.logger import get_logger

log = get_logger("acquire.numbering")

__all__ = ["ReleaseNumbering"]

#: The ``SxxEyy`` token as ``filter_to_episode`` bounds it: the digits stand alone, so ``E5``
#: never reads as ``E51``; the zero-padding is free. A span (``S09E05-E06``, ``S09E05E06``)
#: matches on its first episode, which is the episode the filter keeps it for.
_EPISODE_TOKEN: Final = re.compile(r"(?<![0-9])s0*(\d{1,3})e0*(\d{1,4})(?![0-9])", re.IGNORECASE)


class ReleaseNumbering:
    """The numbering a release title carries: its season and its episode, each ``None`` when it has none."""

    @staticmethod
    def parse(title: str) -> tuple[int | None, int | None]:
        """Read the season and the episode a release title numbers.

        * An episode (``S02E05``, ``2x05``): both.
        * A multi-episode span (``S09E05-E06``, ``S09E05E06``): the season and the FIRST episode,
          the one ``filter_to_episode`` keeps the release for.
        * A season pack (``S02``, ``Saison 2``, ``Season 2 Complete``): the season, episode ``None``.
        * A film, a pack of several seasons (``S01-S03``), an unreadable or markerless name:
          ``(None, None)``. An episode is only numbered together with its season: an absolute
          episode number (an anime's ``- 05``) names no episode of a season.

        Args:
            title: The release's title as the tracker published it.

        Returns:
            ``(season, episode)``; each ``None`` when the title does not number it.
        """
        token = _EPISODE_TOKEN.search(title)
        if token is not None:
            return int(token.group(1)), int(token.group(2))
        info = _guess(title)
        season = _single(info.get("season"))
        if season is None:
            return None, None
        episodes = _episode_numbers(info.get("episode"))
        return season, episodes[0] if episodes else None


def _guess(title: str) -> dict[str, object]:
    """Parse a title with guessit, fail-soft.

    Args:
        title: The release's title.

    Returns:
        guessit's properties; empty when the title cannot be parsed.
    """
    from guessit import guessit  # noqa: PLC0415 — local import keeps module load light, as the filters do

    try:
        return dict(guessit(title))
    except Exception:  # noqa: BLE001 — guessit's failures are many; an unparseable name numbers nothing
        log.debug("acquire.numbering.unparseable", title=title)
        return {}


def _single(value: object) -> int | None:
    """Read one number out of a guessit property that may be a list.

    Args:
        value: guessit's raw ``season``: an int, a list of ints (a multi-season pack) or ``None``.

    Returns:
        The number; ``None`` when absent, a list (several seasons name none) or not an integer.
    """
    return value if isinstance(value, int) else None
