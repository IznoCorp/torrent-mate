"""The single five-state derivation for the acquisition surfaces (acq-states phase 4).

Every acquisition surface — the followed cards, the completeness matrix, the
episode chips — reads its state from THIS module. One derivation, fed only by
persisted facts (library ownership × the ``wanted`` row × the last search
verdict), so two surfaces can never disagree about the same episode.

Three invariants are graved here, each the direct fix of a production incident:

* **Ownership beats everything.** An episode with a live file in the library is
  ``in_library`` even when a stale ``grabbed`` row still points at it. Such
  a row is a phantom, not an acquisition in progress — it is what pinned Silo at
  « en cours d'acquisition » while every episode chip was green.
* **Panne ≠ absence.** A search that did NOT conclude (tracker outage, open
  circuit, dead swarm — the engine's ``INCONCLUSIVE_OUTCOMES``) yields
  ``unverified``, never ``pending``. Reporting an outage as « rien de
  prenable » claims knowledge about the trackers that we do not have.
* **Never searched → ``unverified``.** No verdict at all (``last_search_outcome
  is None``) means we know nothing, so we say nothing. One level up, a follow
  with no aired catalog aggregates to ``unverified`` too — NEVER ``up_to_date``.
  That fallthrough (« À jour » on zero knowledge) is the founding incident:
  Furious was followed at 09:18, the detect cron had last run at 03:00, and the
  card declared « À jour » with three aired episodes missing from the library.

Purity contract: this module imports NO provider, tracker or network client and
performs ZERO I/O — it is a pure function of facts already read from SQLite.
``INCONCLUSIVE_OUTCOMES`` is imported from the acquire orchestrator (the engine
that produces those verdicts) so the two can never drift apart; it is never
copied here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Literal

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES
from personalscraper.acquire.orchestrator import INCONCLUSIVE_OUTCOMES

#: The three ``wanted`` facts :func:`derive_episode_state` consumes:
#: ``(status, last_search_outcome, last_search_found)``.
WantedFacts = tuple[str | None, str | None, int | None]

#: The facts of a unit with NO open ``wanted`` row: no status, no verdict, so
#: the derivation reads it as « never searched » (``unverified`` unless the
#: library holds the file).
NO_WANTED_FACTS: WantedFacts = (None, None, None)

#: State of ONE episode (or of the single unit a followed film is). ``announced``
#: is the episode-states addition: a future episode (air_date > today) is known
#: to the cache but not yet aired, so it is neither owned nor searchable — it is
#: announced. It is a MATRIX-ONLY state: the card aggregation never sees it (a
#: future never degrades a series' status). ``absorbed`` is the season-grab
#: addition (R5): the episode's acquisition is carried by a season wanted, so
#: it is in motion — reading it as « never checked » (``unverified``) would be
#: untruthful for every episode of a season being grabbed.
EpisodeState = Literal[
    "announced",
    "in_library",
    "to_grab",
    "acquiring",
    "pending",
    "unverified",
    "absorbed",
]

#: State of a followed card, aggregated from its episodes. Same vocabulary as
#: :data:`EpisodeState` (``in_library`` becoming the card-level ``up_to_date``),
#: plus ``disabled`` (follow paused) and ``verifying`` (a priming
#: run is in flight — applied by the route layer, phase 6; the aggregation
#: itself never returns it).
FollowStatus = Literal[
    "disabled",
    "verifying",
    "to_grab",
    "acquiring",
    "pending",
    "unverified",
    "up_to_date",
    "ended",
]

#: Provider production-status values that mean « no further episode will come ».
#: Compared case-folded, so TVDB's ``Ended`` and TMDB's ``Ended`` / ``Canceled``
#: all land here. Any other value — and ``None`` — means the series is NOT known
#: to be finished; see :func:`series_has_ended`.
SERIES_ENDED_STATUSES = frozenset({"ended", "canceled", "cancelled"})


def series_has_ended(series_status: str | None) -> bool:
    """Whether the provider POSITIVELY states the series is finished.

    The distinction « À jour » vs « Terminé » rests on this and nothing else,
    because the obvious alternative does not hold: an absence of announced
    episodes is not the end of a series. On 2026-08-09 « House of the Dragon »
    had zero future episodes in the catalogue while airing that very day — a
    rule reading « plus rien d'annoncé ⇒ terminé » would have declared a running
    series finished, the same shape of untruth as the founding « À jour » on
    zero knowledge.

    So silence is never a verdict here: ``None`` (never polled, or a provider
    that names no status) returns ``False``.

    Args:
        series_status: The provider's raw production-status string, or ``None``.

    Returns:
        ``True`` only when the provider names a terminal status.
    """
    if series_status is None:
        return False
    return series_status.strip().casefold() in SERIES_ENDED_STATUSES


#: Card-level reading of a single-unit state (a followed film). Every value is
#: the identity except ``in_library`` — a film held by the library reads
#: « À jour » on its card, not « En médiathèque ».
_EPISODE_TO_FOLLOW_STATUS: dict[EpisodeState, FollowStatus] = {
    "in_library": "up_to_date",
    "to_grab": "to_grab",
    "acquiring": "acquiring",
    "pending": "pending",
    "unverified": "unverified",
    # Defensive: a movie row can never be 'absorbed' (only episode rows are,
    # by a season wanted), but the mapping stays total so a data anomaly
    # degrades to « in motion » instead of a KeyError on the card.
    "absorbed": "acquiring",
}


def select_wanted_facts(rows: Iterable[tuple[int, str | None, str | None, int | None]]) -> WantedFacts:
    """Select the ``wanted`` facts that govern ONE unit, out of all its rows.

    Which row speaks is as much a part of the truth as the derivation itself:
    two surfaces reading the SAME rows but picking DIFFERENT ones disagree just
    as loudly as two different derivations would. So the rule lives here, beside
    :func:`derive_episode_state`, and every surface calls it:

    1. Only OPEN rows speak — see
       :data:`~personalscraper.acquire.domain.OPEN_WANTED_STATUSES` — plus
       ``absorbed`` (season-grab R5): an absorbed episode row is terminal for
       the EPISODE row but the acquisition it describes is alive, carried by
       the season wanted that absorbed it. Silencing it read every episode of
       a season being grabbed as « never checked ». A ``done`` or ``abandoned``
       row stays HISTORY: it describes an acquisition that ended, so letting
       its stale verdict answer for the episode would claim knowledge the
       queue no longer holds.
    2. Among the admitted rows, the HIGHEST id wins — a re-follow or a crash
       between two passes can leave an older open row behind, and the latest
       one is the current intent. In particular, after an R6 fallback the
       NEWER live episode row must outrank the old absorbed one.
    3. No admitted row at all → :data:`NO_WANTED_FACTS`, which reads as « never
       searched » (``unverified`` unless the library holds the file).

    Args:
        rows: ``(id, status, last_search_outcome, last_search_found)`` tuples of
            every ``wanted`` row of one unit — any order, any status.

    Returns:
        The governing :data:`WantedFacts`.
    """
    governing_id = -1
    facts = NO_WANTED_FACTS
    for row_id, status, outcome, found in rows:
        if status not in OPEN_WANTED_STATUSES and status != "absorbed":
            continue
        # ``>=`` so that, at equal ids, the last row seen wins — matching a
        # caller that already reads its rows in id order.
        if row_id >= governing_id:
            governing_id = row_id
            facts = (status, outcome, found)
    return facts


#: One episode ``wanted`` row as the read paths load it:
#: ``(id, season, episode, status, last_search_outcome, last_search_found, absorbed_by)``.
EpisodeWantedRow = tuple[int, int, int, str | None, str | None, int | None, int | None]

#: One season ``wanted`` row: ``(id, status, last_search_outcome, last_search_found)``.
SeasonWantedRow = tuple[int, str | None, str | None, int | None]


def governing_facts_by_episode(
    episode_rows: Iterable[EpisodeWantedRow],
    season_rows: Iterable[SeasonWantedRow],
) -> dict[tuple[int, int], WantedFacts]:
    """Return the facts that GOVERN each episode, absorption already resolved.

    The single answer to « which ``wanted`` row speaks for this episode ». Every
    acquisition surface calls THIS: the card counts
    (:mod:`~personalscraper.web.acquisition.truth`) and the per-season matrix
    (:mod:`~personalscraper.web.acquisition.completeness`). They legitimately
    differ in how they READ their rows (one holds the store, the other a raw
    connection), but the RULE lives here once — two implementations of it is how
    the card and the matrix come to disagree about the same episode.

    Two things happen, in order:

    1. **Absorption is followed, not reported.** ``absorbed`` is not a state of the
       episode; it is a pointer to the season ``wanted`` row that carries its
       acquisition (season-grab R5). An absorbed row therefore takes its season's
       facts. Reporting the pointer instead of following it made four American Dad
       episodes claim « En cours d'acquisition » on 2026-08-04 while the reswitch
       had already requeued their season and emptied the torrent client (§2).
       A pointer that resolves to nothing (``None``, or a season row this caller
       did not load — ``absorbed_by`` carries no FK) keeps its ``absorbed`` facts:
       a dangling link is ignorance, and downgrading a season that IS being
       grabbed would trade one lie for another.
    2. **The governing row is selected** by :func:`select_wanted_facts` — open rows
       only, highest id wins — so a re-enqueued episode still outranks the older
       absorbed row it replaced (R6 fallback).

    Args:
        episode_rows: Every ``kind='episode'`` row of ONE follow, any order.
        season_rows: Every ``kind='season'`` row of the SAME follow.

    Returns:
        ``(season, episode)`` → its governing :data:`WantedFacts`. Episodes with no
        row at all are ABSENT from the mapping — the caller decides what « no row »
        means for its surface (it reads « jamais cherché »).
    """
    season_facts: dict[int, WantedFacts] = {
        season_id: (status, outcome, found) for season_id, status, outcome, found in season_rows
    }
    grouped: dict[tuple[int, int], list[tuple[int, str | None, str | None, int | None, int | None]]] = {}
    for row_id, season, episode, status, outcome, found, absorbed_by in episode_rows:
        grouped.setdefault((season, episode), []).append((row_id, status, outcome, found, absorbed_by))
    return {key: select_wanted_facts(substitute_absorbed_facts(rows, season_facts)) for key, rows in grouped.items()}


def substitute_absorbed_facts(
    rows: Iterable[tuple[int, str | None, str | None, int | None, int | None]],
    season_facts: Mapping[int, WantedFacts],
) -> list[tuple[int, str | None, str | None, int | None]]:
    """Redirect every ``absorbed`` row onto the season row that carries it.

    ``absorbed`` is not a state of the EPISODE — it is a pointer to the ``wanted``
    row that owns its acquisition (season-grab R5). Reading the pointer instead of
    following it made an absorbed episode claim « En cours d'acquisition » for as
    long as the row existed, whatever the season was doing.

    That produced a live lie on 2026-08-04: the reswitch declared both American Dad
    season packs dead, deleted them from the client and requeued the season rows to
    ``pending`` — and the four absorbed episodes went on reading « En cours
    d'acquisition » with nothing in flight (§2: never assert progress that is not
    happening).

    A row whose link is unknown (``None``, or pointing at a season row this caller
    did not load — ``absorbed_by`` carries no FK, the table is advisory) keeps its
    ``absorbed`` facts: a dangling pointer is ignorance, and silently downgrading a
    season that IS being grabbed would trade one lie for another.

    Args:
        rows: ``(id, status, last_search_outcome, last_search_found, absorbed_by)``
            tuples of one unit's ``wanted`` rows.
        season_facts: ``{season_wanted_id: WantedFacts}`` for the season rows of the
            same follow.

    Returns:
        The same rows, shaped for :func:`select_wanted_facts` (the ``absorbed_by``
        column dropped), with absorbed rows carrying their season's facts.
    """
    resolved: list[tuple[int, str | None, str | None, int | None]] = []
    for row_id, status, outcome, found, absorbed_by in rows:
        if status == "absorbed" and absorbed_by is not None and absorbed_by in season_facts:
            season_status, season_outcome, season_found = season_facts[absorbed_by]
            resolved.append((row_id, season_status, season_outcome, season_found))
        else:
            resolved.append((row_id, status, outcome, found))
    return resolved


def derive_episode_state(
    *,
    owned: bool,
    wanted_status: str | None,
    last_search_outcome: str | None,
    last_search_found: int | None,
    air_date: date | None = None,
    today: date | None = None,
) -> EpisodeState:
    """Derive one episode's state from persisted facts only.

    The evaluation order IS the specification — first match wins:

    0. ``air_date > today`` → ``announced``. Checked FIRST (episode-states D2): a
       future episode is not aired, so it cannot be owned, searched or waiting —
       whatever ownership or ``wanted`` facts happen to sit on it. This precedes
       the ``unverified`` no-row path deliberately: a future has no ``wanted``
       row, so its facts are the same all-None « never searched » facts a
       genuinely unknown aired episode has, and only the date tells them apart.
       Requires BOTH ``air_date`` and ``today``; when either is ``None`` (a
       caller that does not track dates) the derivation reduces to the five
       states below, unchanged.
    1. ``owned`` → ``in_library``. Ownership beats everything: a file on
       disk is the strongest fact we hold, so a stale ``grabbed`` row on an
       owned episode is a phantom (the Silo bug) and cannot pin the episode at
       « en cours d'acquisition ».
    1b. ``wanted_status == "absorbed"`` → ``absorbed`` (season-grab R5): the
       episode's acquisition is carried by a season wanted, so the episode is
       in motion — never « never checked ». Ownership still wins above.
    2. ``wanted_status == "grabbed"`` → ``acquiring`` (torrent taken, the
       pipeline is carrying it).
    3. ``wanted_status == "available"`` → ``to_grab`` (the search found a
       takeable candidate that the grab pass has not claimed yet).
    4. ``last_search_outcome is None`` → ``unverified``. Never searched: we
       have no verdict, so we assert nothing.
    5. ``last_search_outcome in INCONCLUSIVE_OUTCOMES`` → ``unverified``.
       Panne ≠ absence — an outage, an open circuit or a dead swarm is not a
       statement about what the trackers hold.
    6. ``(last_search_found or 0) > 0`` → ``to_grab``. Defensive: the last
       verdict says something takeable exists even though the row is not
       ``available`` (a claim lost to a concurrent pass, a crash between the
       verdict write and the status write).
    7. otherwise → ``pending``. Searched, concluded, nothing takeable.

    A ``searching`` status deliberately falls through to rules 4-7: a claim in
    flight tells us nothing new, so the episode still reads from its last
    verdict. Likewise an episode with NO wanted row at all and no file reads
    ``unverified`` — absence of a row is absence of knowledge.

    Args:
        owned: Whether the library holds a live file for this episode.
        wanted_status: The episode's ``wanted`` row status, or ``None`` when no
            row exists.
        last_search_outcome: The named outcome of the last search pass
            (``no_candidates`` / ``all_filtered`` / ``trackers_unavailable`` /
            …), or ``None`` when the episode was never searched.
        last_search_found: Number of TAKEABLE candidates the last search
            reported, or ``None`` when the search did not conclude.
        air_date: The episode's air date, or ``None`` when the caller does not
            track dates (films, and any pre-episode-states call site).
        today: The reference date, injected for determinism (no hidden
            ``date.today()``). ``None`` disables the ``announced`` check.

    Returns:
        The episode's :data:`EpisodeState`.
    """
    if air_date is not None and today is not None and air_date > today:
        return "announced"
    if owned:
        return "in_library"
    if wanted_status == "absorbed":
        return "absorbed"
    if wanted_status == "grabbed":
        return "acquiring"
    if wanted_status == "available":
        return "to_grab"
    if last_search_outcome is None:
        return "unverified"
    if last_search_outcome in INCONCLUSIVE_OUTCOMES:
        return "unverified"
    if (last_search_found or 0) > 0:
        return "to_grab"
    return "pending"


def derive_follow_status(
    *,
    active: bool,
    aired_count: int | None,
    to_grab_count: int | None,
    acquiring_count: int | None,
    pending_count: int | None,
    unverified_count: int | None,
    announced_count: int | None,
    series_status: str | None,
) -> FollowStatus:
    """Aggregate a followed SHOW's per-state episode counts into its card status.

    Most-actionable-first — the card must show what asks for an action, not the
    most frequent state:

    1. not ``active`` → ``disabled`` (the follow is paused; nothing else matters).
    2. ``aired_count is None`` → ``unverified``. NO catalog means no knowledge,
       and a series we know nothing about is NEVER « À jour » — this is the
       founding incident's direct fix, replacing the old fallthrough onto the
       raw ``wanted`` counters.
    3. any ``to_grab`` → ``to_grab`` (something is takeable now).
    4. any ``acquiring`` → ``acquiring``.
    5. any ``pending`` → ``pending``.
    6. any ``unverified`` → ``unverified`` (we still owe a verification).
    7. every aired episode is owned, and the series is FINISHED with nothing
       announced ahead → ``ended``.
    8. otherwise every aired episode is owned → ``up_to_date``.

    Rules 7-8 are the operator's 2026-08-09 split: « À jour » was covering two
    situations they need to tell apart — a series caught up but still running,
    and one that is over. ``announced_count`` therefore reaches this function,
    which it deliberately did not before; the invariant it was kept out for
    still holds and is what rules 3-6 above guarantee: **an announced future
    never DEGRADES a series**. It can only ever decide between ``ended`` and
    ``up_to_date``, both of which mean « nothing to do ».

    ``ended`` demands a POSITIVE end-of-series fact from the provider
    (:func:`series_has_ended`), not merely an empty announcement list — see that
    function for the running series an announcement-only rule would have
    declared finished.

    ``verifying`` is deliberately never returned here: a priming run
    in flight is a runtime fact the route layer overlays (phase 6), not a
    property of the persisted counts.

    Args:
        active: Whether the follow is active.
        aired_count: Aired episodes known from the catalog cache, or ``None``
            when no catalog has ever been written for this follow.
        to_grab_count: Aired episodes with a takeable candidate.
        acquiring_count: Aired episodes taken / carried by the pipeline.
        pending_count: Aired episodes searched with nothing takeable.
        unverified_count: Aired episodes never searched or inconclusive.
        announced_count: Future episodes (``air_date > today``) known from the
            catalog cache, or ``None`` when no catalog was read. Only ever
            distinguishes ``ended`` from ``up_to_date``.
        series_status: The provider's raw production status for this series, or
            ``None`` when never polled. Only ever distinguishes ``ended`` from
            ``up_to_date``.

    Returns:
        The card's :data:`FollowStatus`.
    """
    if not active:
        return "disabled"
    if aired_count is None:
        return "unverified"
    if (to_grab_count or 0) > 0:
        return "to_grab"
    if (acquiring_count or 0) > 0:
        return "acquiring"
    if (pending_count or 0) > 0:
        return "pending"
    if (unverified_count or 0) > 0:
        return "unverified"
    if (announced_count or 0) == 0 and series_has_ended(series_status):
        return "ended"
    return "up_to_date"


def derive_movie_status(
    *,
    active: bool,
    owned: bool,
    wanted_status: str | None,
    last_search_outcome: str | None,
    last_search_found: int | None,
) -> FollowStatus:
    """Derive a followed FILM's card status from its single unit's facts.

    A film has no aired catalog — it is a catalog of exactly one unit — so its
    card derives from the SAME :func:`derive_episode_state` applied to that unit
    (ownership × its ``wanted`` row × the last search verdict), then read at card
    level: ``in_library`` becomes ``up_to_date``, every other state keeps its
    name. Ownership still beats a phantom ``grabbed`` row, and a film we have
    never searched reads ``unverified`` rather than claiming « À jour ».

    Args:
        active: Whether the follow is active.
        owned: Whether the library holds a live file for this film.
        wanted_status: The film's ``wanted`` row status, or ``None`` when no row
            exists (or the row could not be read).
        last_search_outcome: The named outcome of the film's last search pass,
            or ``None`` when never searched.
        last_search_found: Number of takeable candidates the last search
            reported, or ``None`` when the search did not conclude.

    Returns:
        The card's :data:`FollowStatus`.
    """
    if not active:
        return "disabled"
    state = derive_episode_state(
        owned=owned,
        wanted_status=wanted_status,
        last_search_outcome=last_search_outcome,
        last_search_found=last_search_found,
    )
    return _EPISODE_TO_FOLLOW_STATUS[state]


__all__ = [
    "NO_WANTED_FACTS",
    "SERIES_ENDED_STATUSES",
    "EpisodeState",
    "FollowStatus",
    "WantedFacts",
    "series_has_ended",
    "derive_episode_state",
    "governing_facts_by_episode",
    "substitute_absorbed_facts",
    "derive_follow_status",
    "derive_movie_status",
    "select_wanted_facts",
]
