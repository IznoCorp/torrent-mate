"""§5 truth-table facts per followed series (P0-B.2).

One derivation feeds the series card status: the aired catalog (detect-written
``aired_episode`` cache) × library ownership (bulk provider-ID query, live
files only) × the wanted queue. Never a raw wanted counter — a ``grabbed``
row whose episode is already in the library is a phantom, not an acquisition
in progress (the Silo « en cours » -while-all-green bug).

Read-only and fail-soft everywhere: a missing cache yields ``None`` facts (the
card degrades to the legacy counter status), a broken library read yields an
empty owned set through the checker's own fail-soft.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.identity import MediaRef
    from personalscraper.indexer.ownership import IndexerOwnershipChecker

logger = get_logger(__name__)


@dataclass(frozen=True)
class FollowTruth:
    """Truth-table counts for one followed show, or the no-catalog sentinel.

    Attributes:
        aired_count: Aired episodes known (``None`` = no cached catalog —
            every other field is then ``None`` too and the caller falls back
            to the raw counters).
        owned_count: Aired episodes with a live library file.
        inflight_count: Aired, unowned episodes with a ``grabbed`` row.
        queued_count: Aired, unowned episodes with a ``pending``/``searching``
            row.
        missing_count: Aired, unowned episodes with no open wanted row.
    """

    aired_count: int | None = None
    owned_count: int | None = None
    inflight_count: int | None = None
    queued_count: int | None = None
    missing_count: int | None = None


def compute_follow_truth(
    acquire_conn: sqlite3.Connection,
    checker: "IndexerOwnershipChecker",
    *,
    followed_id: int,
    media_ref: "MediaRef",
) -> FollowTruth:
    """Compute the §5 truth-table counts for one followed show.

    Args:
        acquire_conn: Open (read) connection to ``acquire.db``.
        checker: The library ownership checker (bulk ``owned_pairs``).
        followed_id: The ``followed_series`` row id.
        media_ref: The follow's provider IDs.

    Returns:
        The :class:`FollowTruth` counts — all-``None`` when the series has no
        cached aired catalog (or the cache read failed).
    """
    try:
        aired_rows = acquire_conn.execute(
            "SELECT season, episode FROM aired_episode WHERE followed_id = ?",
            (followed_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        logger.debug("acquisition_truth_cache_read_failed", followed_id=followed_id, error=str(exc))
        return FollowTruth()
    aired = {(int(r[0]), int(r[1])) for r in aired_rows}
    if not aired:
        return FollowTruth()

    owned = checker.owned_pairs(media_ref)

    grabbed_pairs: set[tuple[int, int]] = set()
    queued_pairs: set[tuple[int, int]] = set()
    try:
        for r in acquire_conn.execute(
            "SELECT season, episode, status FROM wanted "
            "WHERE followed_id = ? AND kind = 'episode' "
            "AND season IS NOT NULL AND episode IS NOT NULL "
            "AND status IN ('pending', 'searching', 'grabbed')",
            (followed_id,),
        ).fetchall():
            pair = (int(r[0]), int(r[1]))
            if r[2] == "grabbed":
                grabbed_pairs.add(pair)
            else:
                queued_pairs.add(pair)
    except sqlite3.Error as exc:
        logger.debug("acquisition_truth_wanted_read_failed", followed_id=followed_id, error=str(exc))

    remaining = aired - owned
    inflight = len(remaining & grabbed_pairs)
    queued = len((remaining & queued_pairs) - grabbed_pairs)
    missing = len(remaining - grabbed_pairs - queued_pairs)

    return FollowTruth(
        aired_count=len(aired),
        owned_count=len(aired & owned),
        inflight_count=inflight,
        queued_count=queued,
        missing_count=missing,
    )


__all__ = ["FollowTruth", "compute_follow_truth"]
