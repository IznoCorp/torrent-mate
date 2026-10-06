"""Seed-obligation sweep: the single writer of ``satisfied_at`` and ``released_at``.

One pass asks the torrent client ONCE about every unreleased obligation
(``released_at`` NULL, met or not):

* a torrent the client still holds, whose floor is reached (:func:`is_met`),
  gets ``satisfied_at`` (an obligation already satisfied is never re-stamped);
* a torrent the client does not hold is marked absent at the first pass and
  released once it has stayed absent for ``confirm_absent_after_s``, whether or
  not its obligation was met (released means the torrent is gone) — a client
  restarting and answering before its torrents are loaded must not release
  anything, because a FALSE release lets the disk cleaner delete files a
  torrent still seeds (``DeleteAuthority`` stops vetoing a released row);
* a client error ends the pass with no write (fail-soft, logged).

Pure of any clock: the caller passes ``now``. After each write that changed a row
it emits ``SeedObligationSatisfied`` / ``SeedObligationReleased`` on the bus (never
before the write, never for a pass that wrote nothing).

Import direction: acquire/ only; the client arrives through the narrow
:class:`_SweepClient` port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from personalscraper.acquire.events import SeedObligationReleased, SeedObligationSatisfied
from personalscraper.api.torrent._base import lookup_scoped
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import SeedObligation
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.conf.models.api_config import TorrentScope
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.obligations")


class _SweepClient(Protocol):
    """The slice of a torrent client the sweep reads."""

    def get_by_hashes(self, hashes: set[str]) -> list[TorrentItem]:
        """Return the torrents matching *hashes* (any state)."""
        ...


@dataclass(frozen=True)
class SeedRule:
    """How « an obligation is met » is read (the operator's O4 ruling).

    An obligation is met when the seconds really seeded reach the floor, OR when
    the torrent's ratio reaches the floor plus a safety margin.

    Attributes:
        count_ratio: Whether the ratio arm counts at all.
        grace_s: Seconds added to the seed-time floor. Always 0 from callers:
            C411's ``hit_and_run_grace`` delays the H&R clock, it is no extra
            seed time.
        ratio_margin: Added to ``min_ratio`` on the ratio arm (callers pass 0.1:
            C411's 1.0 becomes 1.1). The operator takes a margin so a torrent
            counted as met is never one the tracker still sees just under its
            ratio; the snapshot floors in ``seed_obligation`` and
            ``tracker.json5`` keep the tracker's true value.
    """

    count_ratio: bool
    grace_s: int
    ratio_margin: float


#: The rule the scheduled sweep applies (operator's O4 ruling, 2026-10-03): the
#: ratio arm counts, no grace is added to the seed-time floor, and the ratio
#: needs a 0.1 margin over the tracker's floor.
DEFAULT_SEED_RULE = SeedRule(count_ratio=True, grace_s=0, ratio_margin=0.1)


def is_met(obligation: SeedObligation, item: TorrentItem, rule: SeedRule) -> bool:
    """Say whether *obligation* is met by what the client reports for *item*.

    Args:
        obligation: The obligation, carrying its snapshot floors.
        item: The client's view of the torrent.
        rule: The reading of « met » (see :class:`SeedRule`).

    Returns:
        ``True`` when ``item.seeding_time_s >= min_seed_time_s + grace_s``
        (``None`` seeding time never counts), or when ``rule.count_ratio`` and
        ``item.ratio >= min_ratio + rule.ratio_margin``.
    """
    seeded = item.seeding_time_s
    if seeded is not None and seeded >= obligation.min_seed_time_s + rule.grace_s:
        return True
    return rule.count_ratio and item.ratio >= obligation.min_ratio + rule.ratio_margin


@dataclass(frozen=True)
class ObligationSweepReport:
    """What one sweep pass did.

    Attributes:
        open: Unreleased obligations at the start of the pass.
        satisfied: Obligations stamped ``satisfied_at``.
        marked_absent: Obligations whose torrent was seen missing for the first time.
        released: Obligations stamped ``released_at``.
        client_error: ``True`` when the client failed and nothing was written.
    """

    open: int
    satisfied: int
    marked_absent: int
    released: int
    client_error: bool


def sweep_obligations(
    store: AcquireStore,
    client: _SweepClient,
    *,
    now: int,
    rule: SeedRule,
    event_bus: EventBus,
    scope: TorrentScope | None,
    confirm_absent_after_s: int = 1800,
) -> ObligationSweepReport:
    """Run one sweep pass over the unreleased obligations.

    Args:
        store: The acquire store (``store.seed`` is read and written).
        client: A torrent client answering ``get_by_hashes``.
        now: Unix epoch seconds stamped on every write of this pass.
        rule: The reading of « met ».
        event_bus: Bus the ``SeedObligationSatisfied`` / ``SeedObligationReleased``
            events are emitted on, one per write that changed a row.
        confirm_absent_after_s: How long a torrent must stay absent before its
            obligation is released.
        scope: REQUIRED — what this instance owns in a shared client, or ``None`` (the whole
            client, as before); never defaulted, so a caller
            cannot silently act unscoped. Under a scope an obligation whose torrent sits in
            another category is left alone — neither settled, marked absent nor
            released — because that torrent is not ours to judge.

    Returns:
        The :class:`ObligationSweepReport` of the pass.
    """
    open_rows = store.seed.list_unreleased()
    if not open_rows:
        return ObligationSweepReport(0, 0, 0, 0, client_error=False)

    try:
        items, foreign = lookup_scoped(client, {o.info_hash.lower() for o in open_rows}, scope)
    except Exception:  # fail-soft: a client failure ends the pass with no write, the next tick retries
        log.warning("acquire.obligations.client_error", open=len(open_rows), exc_info=True)
        return ObligationSweepReport(len(open_rows), 0, 0, 0, client_error=True)
    by_hash = {i.hash.lower(): i for i in items}

    satisfied = marked_absent = released = 0
    for obligation in open_rows:
        if obligation.id is None:  # a row read back from the store always has one
            continue
        if obligation.info_hash.lower() in foreign:
            continue
        item = by_hash.get(obligation.info_hash.lower())
        if item is not None:
            if obligation.absent_since is not None:
                store.seed.clear_absent(obligation.id)
            if obligation.satisfied_at is None and is_met(obligation, item, rule):
                if store.seed.mark_satisfied(obligation.id, now):
                    satisfied += 1
                    event_bus.emit(
                        SeedObligationSatisfied(
                            info_hash=obligation.info_hash, source_tracker=obligation.source_tracker
                        )
                    )
        elif obligation.absent_since is None:
            marked_absent += store.seed.mark_absent(obligation.id, now)
        elif now - obligation.absent_since >= confirm_absent_after_s:
            if store.seed.mark_released(obligation.id, now):
                released += 1
                event_bus.emit(
                    SeedObligationReleased(info_hash=obligation.info_hash, source_tracker=obligation.source_tracker)
                )

    log.info(
        "acquire.obligations.swept",
        open=len(open_rows),
        satisfied=satisfied,
        marked_absent=marked_absent,
        released=released,
    )
    return ObligationSweepReport(len(open_rows), satisfied, marked_absent, released, client_error=False)
