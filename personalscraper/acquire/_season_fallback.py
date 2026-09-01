"""The R6 season → episodes fallback, shared by its two triggers.

A season ``wanted`` row is an all-or-nothing bet on one release carrying a whole
season. When that bet is over and the season is still incomplete, the row goes
terminal (``fallback_episodes``) and the episodes it did not bring are re-queued
individually, so the per-episode retry loop can still resolve them.

Two things end the bet, and they are unrelated:

- **the cadence cutoff** — the season row aged out without ever finding a pack
  (:meth:`~personalscraper.acquire._pass_gates.PassGatesMixin._apply_cutoff_gate`);
- **a landed but incomplete pack** — the grab was dispatched to the library and
  did not carry every aired episode
  (:func:`~personalscraper.acquire.reconcile.reconcile_wanted`).

The transition itself is identical in both, which is why it lives here and not
in either caller. The difference is WHICH episodes get re-queued: the cutoff
path knows nothing about ownership and re-enqueues the whole aired season (the
detect pass skips the owned ones), while the landed path has just computed the
missing set episode by episode and passes exactly that — re-queuing the twelve
episodes a pack DID deliver would churn twelve rows the very next sweep closes.

Import direction: acquire/ inward only — ports and domain, never a pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES, WantedItem
from personalscraper.acquire.events import SeasonFellBackToEpisodes

if TYPE_CHECKING:
    from collections.abc import Iterable

    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.core.event_bus import EventBus


@dataclass(frozen=True)
class SeasonFallback:
    """What one call to :func:`fall_back_to_episodes` actually did.

    Two zeros need telling apart and a bare count cannot do it: « I transitioned
    the row and every gap already had an open row » and « another pass got there
    first » both re-queue nothing, and only the first is this pass's work.

    Attributes:
        claimed: Whether THIS call transitioned the season row. ``False`` means
            a concurrent pass won the guarded UPDATE; nothing was announced.
        reenqueued: Episode rows actually created by this call.
    """

    claimed: bool
    reenqueued: int


def fall_back_to_episodes(
    store: "AcquireStore",
    item: "WantedItem",
    *,
    now: int,
    event_bus: "EventBus",
    episodes: "Iterable[int] | None" = None,
) -> SeasonFallback:
    """Re-queue a season's episodes individually and close the season row (R6).

    Re-enqueues each requested episode that does not already hold an OPEN row
    (a live row is reused as-is — a duplicate ``(follow, season, episode)``
    would double-search and double-grab), transitions the season row to
    ``fallback_episodes``, then emits :class:`SeasonFellBackToEpisodes` — but
    only if the transition was actually THIS call's to make.

    Emit-after-persist, as everywhere else: the status write lands first, so a
    crash between the two loses the announcement rather than announcing a
    transition that did not happen.

    The episodes are queued BEFORE the season row goes terminal, and that order
    is load-bearing the other way round: a crash in the gap leaves the gaps
    queued under a season row still open, which the next pass re-runs
    idempotently (the ``find`` skips them) — where the reverse order would leave
    a terminal season whose gaps were never queued at all, and nothing walks a
    terminal row again.

    A row that already holds a terminal/absorbed status DOES get a fresh one:
    absorption is irreversible by design, so the fallback re-mints it.

    Args:
        store: The acquire store.
        item: The season ``wanted`` row (``id``, ``followed_id`` and ``season``
            non-None — the callers assert it).
        now: Unix epoch seconds, stamped on the re-enqueued rows.
        event_bus: The bus the announcement fires on (REQUIRED — project
            contract: every emission site takes the bus explicitly).
        episodes: The episode numbers to re-queue. ``None`` means « every aired
            episode of the season », read from the follow's catalog cache.

    Returns:
        Whether this call claimed the transition, and how many episode rows it
        created. Each caller logs its own line from it, so the two triggers stay
        distinguishable in the journal.
    """
    assert item.id is not None  # noqa: S101 — ensured by the callers' SELECTs
    assert item.followed_id is not None  # noqa: S101
    assert item.season is not None  # noqa: S101
    season_wanted_id = item.id
    followed_id = item.followed_id
    season_number = item.season

    if episodes is None:
        aired_rows = store.aired.list_for_followed(followed_id)
        episode_numbers = sorted(int(r.episode) for r in aired_rows if r.season == season_number)
    else:
        episode_numbers = sorted(set(episodes))

    open_statuses = tuple(sorted(OPEN_WANTED_STATUSES))
    reenqueued = 0
    for episode_number in episode_numbers:
        existing = store.wanted.find(
            followed_id=followed_id,
            kind="episode",
            season=season_number,
            episode=episode_number,
            statuses=open_statuses,
        )
        if existing is not None:
            continue
        store.wanted.add(
            WantedItem(
                media_ref=item.media_ref,
                kind="episode",
                status="pending",
                enqueued_at=now,
                followed_id=followed_id,
                season=season_number,
                episode=episode_number,
            ),
        )
        reenqueued += 1

    # The CLAIM, and the whole reason it is read: ``fallback_season`` is guarded
    # in SQL on kind + open status, so of two passes racing on one row exactly
    # one transitions it. Announcing without reading that answer let the LOSER
    # fire a second operator notification for a single transition — saying
    # « 0 re-mis en file », which is the loser describing the winner's work.
    if not store.wanted.fallback_season(season_wanted_id):
        return SeasonFallback(claimed=False, reenqueued=reenqueued)

    event_bus.emit(
        SeasonFellBackToEpisodes(
            season_wanted_id=season_wanted_id,
            media_ref=item.media_ref,
            season=season_number,
            reenqueued_count=reenqueued,
        ),
    )
    return SeasonFallback(claimed=True, reenqueued=reenqueued)


__all__ = ["SeasonFallback", "fall_back_to_episodes"]
