"""Seed-obligation sweep: the single writer of ``satisfied_at`` and ``released_at``.

One pass asks the torrent client ONCE about every open obligation
(``satisfied_at`` and ``released_at`` both NULL):

* a torrent the client still holds, whose floor is reached (:func:`is_met`),
  gets ``satisfied_at``;
* a torrent the client does not hold is marked absent at the first pass and
  released once it has stayed absent for ``confirm_absent_after_s`` — a client
  restarting and answering before its torrents are loaded must not release
  anything, because a FALSE release lets the disk cleaner delete files a
  torrent still seeds (``DeleteAuthority`` stops vetoing a released row);
* a client error ends the pass with no write (fail-soft, logged).

Pure of any clock: the caller passes ``now``. No event is emitted.

Import direction: acquire/ only; the client arrives through the narrow
:class:`_SweepClient` port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import SeedObligation
    from personalscraper.api.torrent._base import TorrentItem

log = get_logger("acquire.obligations")


class _SweepClient(Protocol):
    """The slice of a torrent client the sweep reads."""

    def get_by_hashes(self, hashes: set[str]) -> "list[TorrentItem]":
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


def is_met(obligation: "SeedObligation", item: "TorrentItem", rule: SeedRule) -> bool:
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
        open: Open obligations at the start of the pass.
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
    store: "AcquireStore",
    client: _SweepClient,
    *,
    now: int,
    rule: SeedRule,
    confirm_absent_after_s: int = 1800,
) -> ObligationSweepReport:
    """Run one sweep pass over the open obligations.

    Args:
        store: The acquire store (``store.seed`` is read and written).
        client: A torrent client answering ``get_by_hashes``.
        now: Unix epoch seconds stamped on every write of this pass.
        rule: The reading of « met ».
        confirm_absent_after_s: How long a torrent must stay absent before its
            obligation is released.

    Returns:
        The :class:`ObligationSweepReport` of the pass.
    """
    open_rows = store.seed.list_open()
    if not open_rows:
        return ObligationSweepReport(0, 0, 0, 0, client_error=False)

    try:
        items = client.get_by_hashes({o.info_hash.lower() for o in open_rows})
    except Exception:
        log.warning("acquire.obligations.client_error", open=len(open_rows), exc_info=True)
        return ObligationSweepReport(len(open_rows), 0, 0, 0, client_error=True)
    by_hash = {i.hash.lower(): i for i in items}

    satisfied = marked_absent = released = 0
    for obligation in open_rows:
        if obligation.id is None:  # a row read back from the store always has one
            continue
        item = by_hash.get(obligation.info_hash.lower())
        if item is not None:
            if obligation.absent_since is not None:
                store.seed.clear_absent(obligation.id)
            if is_met(obligation, item, rule):
                satisfied += store.seed.mark_satisfied(obligation.id, now)
        elif obligation.absent_since is None:
            marked_absent += store.seed.mark_absent(obligation.id, now)
        elif now - obligation.absent_since >= confirm_absent_after_s:
            released += store.seed.mark_released(obligation.id, now)

    log.info(
        "acquire.obligations.swept",
        open=len(open_rows),
        satisfied=satisfied,
        marked_absent=marked_absent,
        released=released,
    )
    return ObligationSweepReport(len(open_rows), satisfied, marked_absent, released, client_error=False)
