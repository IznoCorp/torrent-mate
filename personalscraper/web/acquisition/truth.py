"""Five-state truth facts per followed series (acq-states phase 4).

One derivation feeds the series card status: the aired catalog (detect-written
``aired_episode`` cache) × library ownership (bulk provider-ID query, live
files only) × the wanted queue × the last search verdict. Every aired episode
goes through the SAME
:func:`~personalscraper.web.acquisition.states.derive_episode_state` the cards
and the completeness panel use — there is no local re-derivation here, only
counting.

Never a raw wanted counter — a ``grabbed`` row whose episode is already in the
library is a phantom, not an acquisition in progress (the Silo « en cours »
-while-all-green bug) — and never an assumption: an episode we never searched,
or whose search did not conclude, counts as ``non_verifie``, never as « rien à
prendre ».

Read-only and fail-soft everywhere: a missing cache yields the all-``None``
sentinel (the card then reads ``non_verifie`` — no catalog is no knowledge), a
broken library read yields an empty owned set through the checker's own
fail-soft.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.web.acquisition.states import EpisodeState, derive_episode_state
from personalscraper.web.models.acquisition import MovieFacts

if TYPE_CHECKING:
    from personalscraper.core.identity import MediaRef
    from personalscraper.indexer.ownership import IndexerOwnershipChecker

logger = get_logger(__name__)

#: Facts of one episode's wanted row: (status, last_search_outcome, last_search_found).
_WantedFacts = tuple[str | None, str | None, int | None]

#: The facts of an episode with no open wanted row — no status, no verdict, so
#: the derivation reads it as « never searched ».
_NO_WANTED_ROW: _WantedFacts = (None, None, None)


@dataclass(frozen=True)
class FollowTruth:
    """Per-state episode counts for one followed show, or the no-catalog sentinel.

    Attributes:
        aired_count: Aired episodes known (``None`` = no cached catalog —
            every other field is then ``None`` too and the card reads
            ``non_verifie``, never ``a_jour``).
        owned_count: Aired episodes with a live library file (``en_mediatheque``).
        a_recuperer_count: Aired, unowned episodes with a takeable candidate.
        en_acquisition_count: Aired, unowned episodes taken / in the pipeline.
        en_attente_count: Aired, unowned episodes searched with nothing takeable.
        non_verifie_count: Aired, unowned episodes never searched or whose last
            search did not conclude.
    """

    aired_count: int | None = None
    owned_count: int | None = None
    a_recuperer_count: int | None = None
    en_acquisition_count: int | None = None
    en_attente_count: int | None = None
    non_verifie_count: int | None = None


def compute_follow_truth(
    acquire_conn: sqlite3.Connection,
    checker: "IndexerOwnershipChecker",
    *,
    followed_id: int,
    media_ref: "MediaRef",
) -> FollowTruth:
    """Count each five-state bucket for one followed show.

    Every aired episode is passed through
    :func:`~personalscraper.web.acquisition.states.derive_episode_state` with
    its own facts — ownership, its open ``wanted`` row (if any) and that row's
    last search verdict — and the result is tallied. No state is inferred here.

    Only OPEN wanted rows (``pending`` / ``searching`` / ``available`` /
    ``grabbed``) are read: a ``done`` or ``abandoned`` row is not an ongoing
    acquisition, so its episode derives from « no row » facts (``non_verifie``
    when the library does not hold it) rather than from a closed verdict.

    Args:
        acquire_conn: Open (read) connection to ``acquire.db``.
        checker: The library ownership checker (bulk ``owned_pairs``).
        followed_id: The ``followed_series`` row id.
        media_ref: The follow's provider IDs.

    Returns:
        The :class:`FollowTruth` counts — the all-``None`` sentinel when the
        series has no cached aired catalog (or the cache read failed), which the
        card reads as ``non_verifie``.
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

    # Facts of the open wanted rows, keyed by episode. Ordered by id so that a
    # duplicate row for the same episode leaves the LATEST one in place.
    wanted_facts: dict[tuple[int, int], _WantedFacts] = {}
    try:
        for r in acquire_conn.execute(
            "SELECT season, episode, status, last_search_outcome, last_search_found FROM wanted "
            "WHERE followed_id = ? AND kind = 'episode' "
            "AND season IS NOT NULL AND episode IS NOT NULL "
            "AND status IN ('pending', 'searching', 'available', 'grabbed') "
            "ORDER BY id",
            (followed_id,),
        ).fetchall():
            found = None if r[4] is None else int(r[4])
            wanted_facts[(int(r[0]), int(r[1]))] = (r[2], r[3], found)
    except sqlite3.Error as exc:
        logger.debug("acquisition_truth_wanted_read_failed", followed_id=followed_id, error=str(exc))

    counts: dict[EpisodeState, int] = {
        "en_mediatheque": 0,
        "a_recuperer": 0,
        "en_acquisition": 0,
        "en_attente": 0,
        "non_verifie": 0,
    }
    for pair in aired:
        status, outcome, found = wanted_facts.get(pair, _NO_WANTED_ROW)
        state = derive_episode_state(
            owned=pair in owned,
            wanted_status=status,
            last_search_outcome=outcome,
            last_search_found=found,
        )
        counts[state] += 1

    return FollowTruth(
        aired_count=len(aired),
        owned_count=counts["en_mediatheque"],
        a_recuperer_count=counts["a_recuperer"],
        en_acquisition_count=counts["en_acquisition"],
        en_attente_count=counts["en_attente"],
        non_verifie_count=counts["non_verifie"],
    )


def compute_movie_truth(
    acquire_conn: sqlite3.Connection,
    checker: "IndexerOwnershipChecker",
    *,
    followed_id: int,
    media_ref: "MediaRef",
) -> MovieFacts:
    """Read the single unit's facts a followed FILM derives its status from (D2-B).

    A film has no aired catalog — it is a catalog of exactly one unit — so
    instead of per-state counts it yields the raw facts that unit is made of:
    library ownership (real disk presence by provider ID) plus its ``wanted``
    row's status and last search verdict. The card then runs the SAME
    :func:`~personalscraper.web.acquisition.states.derive_episode_state` a
    series episode runs, so ownership still beats a phantom ``grabbed`` row and
    a film nobody ever searched reads ``non_verifie`` instead of « À jour ».

    Row selection: a film follow carries ONE wanted row, but a re-follow can
    leave a closed row behind — so the OPEN row wins (``pending`` / ``searching``
    / ``available`` / ``grabbed``), and only failing that the most recent row of
    any status. No row at all yields the never-searched facts.

    Args:
        acquire_conn: Open (read) connection to ``acquire.db``.
        checker: The library ownership checker (fail-soft ``owns``).
        followed_id: The ``followed_series`` row id.
        media_ref: The film's provider IDs.

    Returns:
        The :class:`~personalscraper.web.models.acquisition.MovieFacts` carried
        by the film's card.
    """
    owned = checker.owns(media_ref, kind="movie")
    try:
        row = acquire_conn.execute(
            "SELECT status, last_search_outcome, last_search_found FROM wanted "
            "WHERE followed_id = ? AND kind = 'movie' "
            "ORDER BY (status IN ('pending', 'searching', 'available', 'grabbed')) DESC, id DESC "
            "LIMIT 1",
            (followed_id,),
        ).fetchone()
    except sqlite3.Error as exc:
        logger.debug("acquisition_truth_movie_read_failed", followed_id=followed_id, error=str(exc))
        row = None
    if row is None:
        return MovieFacts(owned=owned)
    return MovieFacts(
        owned=owned,
        wanted_status=row[0],
        last_search_outcome=row[1],
        last_search_found=None if row[2] is None else int(row[2]),
    )


__all__ = ["FollowTruth", "compute_follow_truth", "compute_movie_truth"]
