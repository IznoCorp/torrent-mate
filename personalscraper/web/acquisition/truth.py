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
from datetime import date
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger
from personalscraper.web.acquisition.states import (
    NO_WANTED_FACTS,
    EpisodeState,
    derive_episode_state,
    governing_facts_by_episode,
    # A FILM is never absorbed (only episode rows are), so its single unit reads
    # the plain selector — no season row can carry a movie's acquisition.
    select_wanted_facts,
)
from personalscraper.web.models.acquisition import MovieFacts

if TYPE_CHECKING:
    from personalscraper.core.identity import MediaRef
    from personalscraper.indexer.ownership import IndexerOwnershipChecker

logger = get_logger(__name__)


@dataclass(frozen=True)
class FollowTruth:
    """Per-state episode counts for one followed show, or the no-catalog sentinel.

    Attributes:
        aired_count: Aired episodes known (``None`` = no cached catalog —
            every other field is then ``None`` too and the card reads
            ``non_verifie``, never ``a_jour``).
        owned_count: Aired episodes with a live library file (``en_mediatheque``).
        a_recuperer_count: Aired, unowned episodes with a takeable candidate.
        en_acquisition_count: Aired, unowned episodes taken / in the pipeline —
            including episodes absorbed by a season wanted (season-grab R5),
            whose acquisition is in motion at the season level.
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
    today: "date | None" = None,
) -> FollowTruth:
    """Count each five-state bucket for one followed show.

    Every AIRED episode is passed through
    :func:`~personalscraper.web.acquisition.states.derive_episode_state` with
    its own facts — ownership, its open ``wanted`` row (if any) and that row's
    last search verdict — and the result is tallied. No state is inferred here.

    The FUTURE episodes the cache now stores (episode-states D1) are excluded
    from this count entirely: the card aggregates aired episodes only, so an
    announced episode never degrades a series' status — a show whose aired
    episodes are all owned stays « À jour » with futures ahead. The
    ``air_date > today`` rows are dropped at the source query below; they never
    reach the derivation, so ``annonce`` cannot leak into ``FollowStatus``.

    Which row supplies those facts is NOT decided here: every row of the follow
    is handed to
    :func:`~personalscraper.web.acquisition.states.select_wanted_facts`, the
    same selector the completeness panel calls (open rows only, latest wins).
    A ``done`` or ``abandoned`` row is not an ongoing acquisition, so its
    episode derives from « no row » facts (``non_verifie`` when the library does
    not hold it) rather than from a closed verdict.

    Args:
        acquire_conn: Open (read) connection to ``acquire.db``.
        checker: The library ownership checker (bulk ``owned_pairs``).
        followed_id: The ``followed_series`` row id.
        media_ref: The follow's provider IDs.
        today: Reference date for the aired-vs-future split (episode-states D2).
            Defaults to ``date.today()``. Cached rows with ``air_date > today``
            are future/announced and are excluded from the card tallies.

    Returns:
        The :class:`FollowTruth` counts — the all-``None`` sentinel when the
        series has no cached AIRED catalog (or the cache read failed), which the
        card reads as ``non_verifie``. A series with ONLY future episodes cached
        therefore reads ``non_verifie`` (no aired episode to be up to date on).
    """
    ref_today = (today if today is not None else date.today()).isoformat()
    try:
        aired_rows = acquire_conn.execute(
            # Aired-only: a future episode (air_date > today) is cached for the
            # matrix's ``annonce`` display but is NOT a card fact. NULL/empty
            # air_date rows are kept (legacy caches without a date read as aired,
            # the pre-episode-states behaviour).
            "SELECT season, episode FROM aired_episode "
            "WHERE followed_id = ? AND (air_date IS NULL OR air_date = '' OR air_date <= ?)",
            (followed_id, ref_today),
        ).fetchall()
    except sqlite3.Error as exc:
        logger.debug("acquisition_truth_cache_read_failed", followed_id=followed_id, error=str(exc))
        return FollowTruth()
    aired = {(int(r[0]), int(r[1])) for r in aired_rows}
    if not aired:
        return FollowTruth()

    owned = checker.owned_pairs(media_ref)

    # Every row of the follow, keyed by episode — closed ones included, because
    # WHICH row governs is decided by the shared selector below, never by a
    # WHERE clause private to this module (that private clause is exactly how
    # the card and the completeness panel could pick different rows).
    # Deciding WHICH row speaks for an episode is NOT this module's job: it hands
    # its rows to the single governing-facts seam, exactly like the completeness
    # matrix does, so the card and the matrix can never answer differently about
    # the same episode. The SEASON rows are loaded because an absorbed episode's
    # acquisition is carried by the season row that absorbed it.
    episode_rows: list[tuple[int, int, int, str | None, str | None, int | None, int | None]] = []
    season_rows: list[tuple[int, str | None, str | None, int | None]] = []
    try:
        season_rows = [
            (int(r[0]), r[1], r[2], None if r[3] is None else int(r[3]))
            for r in acquire_conn.execute(
                "SELECT id, status, last_search_outcome, last_search_found FROM wanted "
                "WHERE followed_id = ? AND kind = 'season'",
                (followed_id,),
            ).fetchall()
        ]
        episode_rows = [
            (
                int(r[0]),
                int(r[1]),
                int(r[2]),
                r[3],
                r[4],
                None if r[5] is None else int(r[5]),
                None if r[6] is None else int(r[6]),
            )
            for r in acquire_conn.execute(
                "SELECT id, season, episode, status, last_search_outcome, last_search_found, absorbed_by "
                "FROM wanted "
                "WHERE followed_id = ? AND kind = 'episode' "
                "AND season IS NOT NULL AND episode IS NOT NULL "
                "ORDER BY id",
                (followed_id,),
            ).fetchall()
        ]
    except sqlite3.Error as exc:
        logger.debug("acquisition_truth_wanted_read_failed", followed_id=followed_id, error=str(exc))
    facts_by_episode = governing_facts_by_episode(episode_rows, season_rows)

    counts: dict[EpisodeState, int] = {
        "en_mediatheque": 0,
        "a_recuperer": 0,
        "en_acquisition": 0,
        "en_attente": 0,
        "non_verifie": 0,
        "absorbed": 0,
    }
    for pair in aired:
        status, outcome, found = facts_by_episode.get(pair, NO_WANTED_FACTS)
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
        # An absorbed episode is IN MOTION — its acquisition is carried by the
        # season wanted that absorbed it (season-grab R5). It tallies with
        # « en cours d'acquisition » so a season being grabbed never degrades
        # the card to « non vérifié ».
        en_acquisition_count=counts["en_acquisition"] + counts["absorbed"],
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

    Row selection is delegated to
    :func:`~personalscraper.web.acquisition.states.select_wanted_facts` — the
    SAME selector the episode matrix uses (D3). Only OPEN rows speak (the
    statuses of :data:`~personalscraper.acquire.domain.OPEN_WANTED_STATUSES`),
    highest id first; no open row yields the never-searched facts.

    A film used to keep one exception: failing an open row, its newest row —
    closed or not — still answered. That let a closed row's stale verdict speak —
    a film whose only row was ``abandoned`` with ``no_candidates`` read « En
    attente », i.e. a queue state for an item no longer in any queue. The
    justification was that a film has no episode matrix to contradict its card,
    which explains why the divergence was invisible, not why it was true. It is
    now arbitrated the other way: one rule everywhere, a closed row is history.
    Ownership is untouched by this — the disk fact is read separately, so an
    owned film whose row was closed still reads « À jour ».

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
        rows = acquire_conn.execute(
            "SELECT id, status, last_search_outcome, last_search_found FROM wanted "
            "WHERE followed_id = ? AND kind = 'movie' ORDER BY id",
            (followed_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        logger.debug("acquisition_truth_movie_read_failed", followed_id=followed_id, error=str(exc))
        rows = []
    status, outcome, found = select_wanted_facts(
        (int(row[0]), row[1], row[2], None if row[3] is None else int(row[3])) for row in rows
    )
    return MovieFacts(
        owned=owned,
        wanted_status=status,
        last_search_outcome=outcome,
        last_search_found=found,
    )


__all__ = ["FollowTruth", "compute_follow_truth", "compute_movie_truth"]
