"""The aired catalogue's read side: what a show has aired, what the library lacks, what lies beyond.

The store (``acquire/catalogue.py``) holds each show's announced episodes under the
show's canonical provider id. A show never fetched reads « unknown » (``None``) on
every derived figure, never « complete ». Specials (season 0) are never counted as
aired, the rule the follows apply.

A « missing » episode is an episode that has AIRED and is not held: an episode held
beyond the catalogue never offsets one missing inside it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from personalscraper.acquire.catalogue import CatalogueEpisode

# The providers a show's catalogue is keyed by, in the order ``library_shows`` tries
# them (TVDB first for TV) after the row's own canonical provider.
_CATALOGUE_PROVIDERS = ("tvdb", "tmdb")


def catalogue_key(ids: Mapping[str, int | str], canonical_provider: str | None) -> tuple[str, str] | None:
    """The key a show's catalogue is stored under, as ``library-catalogue-refresh`` writes it.

    Mirrors ``acquire.catalogue.library_shows``: the row's canonical provider when it is
    TVDB or TMDB and the row carries that id, else TVDB, then TMDB.

    Args:
        ids: The show's provider ids.
        canonical_provider: The row's ``canonical_provider``, or ``None``.

    Returns:
        ``(provider, id as text)``, or ``None`` when the show carries neither id.
    """
    order = ([canonical_provider] if canonical_provider in _CATALOGUE_PROVIDERS else []) + list(_CATALOGUE_PROVIDERS)
    for provider in order:
        if provider in ids:
            return provider, str(ids[provider])
    return None


def aired_pairs(episodes: Sequence[CatalogueEpisode], today: date) -> set[tuple[int, int]]:
    """The ``(season, episode)`` pairs that have aired, specials excluded.

    Args:
        episodes: A show's catalogue.
        today: The reference date; an episode airing today has aired.

    Returns:
        The aired pairs.
    """
    return {
        (ep.season, ep.episode)
        for ep in episodes
        if ep.season >= 1 and ep.air_date is not None and ep.air_date <= today
    }


@dataclass(frozen=True)
class Completeness:
    """How much of what a show has aired the library holds.

    Attributes:
        aired: Episodes aired (specials excluded).
        owned: Of those, the episodes held.
    """

    aired: int
    owned: int

    @property
    def missing(self) -> int:
        """Aired episodes the library does not hold."""
        return self.aired - self.owned


def completeness(
    episodes: Sequence[CatalogueEpisode] | None, owned: set[tuple[int, int]], today: date
) -> Completeness | None:
    """Measure a show against its catalogue.

    Args:
        episodes: The show's catalogue, or ``None`` when it was never fetched.
        owned: The ``(season, episode)`` pairs the library holds.
        today: The reference date.

    Returns:
        The aired and owned-of-aired counts, or ``None`` when the catalogue is unknown.
    """
    if episodes is None:
        return None
    aired = aired_pairs(episodes, today)
    return Completeness(aired=len(aired), owned=len(aired & owned))


def aired_of_season(episodes: Sequence[CatalogueEpisode], today: date) -> int | None:
    """How many episodes of ONE season have aired.

    Args:
        episodes: The season's catalogued episodes.
        today: The reference date.

    Returns:
        The aired count, or ``None`` when no episode of the season carries a date to count
        (a total with no dates, or the specials, which never count).
    """
    dated = [ep for ep in episodes if ep.air_date is not None and ep.season >= 1]
    if not dated:
        return None
    return sum(1 for ep in dated if ep.air_date is not None and ep.air_date <= today)


def off_catalogue(held: Sequence[int], catalogued: Sequence[int]) -> tuple[int, ...]:
    """The held episode numbers of a season above the last one the catalogue lists.

    Args:
        held: The season's held episode numbers.
        catalogued: The season's catalogued episode numbers (empty when it lists none).

    Returns:
        Those above ``max(catalogued)`` (every held one when the catalogue lists none), ascending.
    """
    last = max(catalogued, default=0)
    return tuple(sorted(number for number in set(held) if number > last))
