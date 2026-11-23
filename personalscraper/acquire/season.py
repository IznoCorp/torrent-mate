"""The season's exclusivity: while a season wanted is open, no episode of it goes on its own (SR3).

The one owner of that rule (K3 DESIGN § 2.8). Three doors read it: detect does not enqueue an
episode of a covered season, the search pass absorbs a ``pending`` episode row of one instead of
searching it, and the grab pass absorbs an ``available`` one instead of grabbing it.

The rule composes with the other season guards rather than overriding them: the R6 fallback
(#542) re-enqueues episodes only after it moved the season row to ``fallback_episodes``, out of
the open set, so a fallen-back season covers nothing; the R2/D1 conversion creates the covering
row and absorbs in the same call.

Import direction: ``acquire/`` only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES
from personalscraper.acquire.events import SeasonAbsorbedEpisodes
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.season")

__all__ = ["SeasonRecovery"]


class SeasonRecovery:
    """Answer whether a follow's season is under recovery, and absorb an episode it covers."""

    def __init__(self, store: AcquireStore) -> None:
        """Keep the store the cover is read from.

        Args:
            store: The acquire store.
        """
        self._store = store

    def covering(self, followed_id: int | None, season: int | None) -> WantedItem | None:
        """Return the open season wanted covering this follow's season, if any.

        A follow-less row is never covered: the store matches ``followed_id IS NULL`` across every
        follow-less row, so a season row with no follow would otherwise cover the episodes of an
        unrelated medium.

        The follow's season rows are read whole (a handful per follow) and the open one picked
        here, so the rule « open » is :data:`OPEN_WANTED_STATUSES` and nothing else.

        Args:
            followed_id: The follow the episode belongs to, or ``None``.
            season: The episode's season number, or ``None``.

        Returns:
            The oldest open season row of that follow and season, or ``None``.
        """
        if followed_id is None or season is None:
            return None
        for row in self._store.wanted.list_for_followed(followed_id, kind="season"):
            if row.season == season and row.status in OPEN_WANTED_STATUSES:
                return row
        return None

    def absorb_if_covered(self, item: WantedItem, *, event_bus: EventBus, door: str) -> bool:
        """Absorb an episode row into the open season wanted covering it, if one does.

        The search and grab passes' door: a covered episode is absorbed instead of being
        searched or grabbed. The absorption is guarded in SQL on the live statuses, so a row a
        concurrent pass already moved is left alone and nothing is announced for it.

        Args:
            item: The queued row (``item.id`` non-None). Only an ``episode`` row can be covered.
            event_bus: The bus :class:`SeasonAbsorbedEpisodes` fires on.
            door: The pass that asks (``"search"`` or ``"grab"``), logged.

        Returns:
            ``True`` when a covering season row exists — the caller must then neither search
            nor grab the item, whether this call or a concurrent one absorbed it.
        """
        if item.kind != "episode" or item.id is None:
            return False
        cover = self.covering(item.followed_id, item.season)
        if cover is None or cover.id is None or item.season is None:
            return False
        if self._store.wanted.absorb_episodes(cover.id, (item.id,)) > 0:
            event_bus.emit(
                SeasonAbsorbedEpisodes(
                    season_wanted_id=cover.id,
                    media_ref=item.media_ref,
                    season=item.season,
                    absorbed_ids=(item.id,),
                ),
            )
            log.info(
                "acquire.season.absorbed_on_pass",
                door=door,
                wanted_id=item.id,
                season=item.season,
                season_wanted_id=cover.id,
            )
        return True
