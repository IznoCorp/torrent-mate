"""The single five-state derivation for the acquisition surfaces (acq-states phase 4).

Every acquisition surface — the followed cards, the completeness matrix, the
episode chips — reads its state from THIS module. One derivation, fed only by
persisted facts (library ownership × the ``wanted`` row × the last search
verdict), so two surfaces can never disagree about the same episode.

Three invariants are graved here, each the direct fix of a production incident:

* **Ownership beats everything.** An episode with a live file in the library is
  ``en_mediatheque`` even when a stale ``grabbed`` row still points at it. Such
  a row is a phantom, not an acquisition in progress — it is what pinned Silo at
  « en cours d'acquisition » while every episode chip was green.
* **Panne ≠ absence.** A search that did NOT conclude (tracker outage, open
  circuit, dead swarm — the engine's ``INCONCLUSIVE_OUTCOMES``) yields
  ``non_verifie``, never ``en_attente``. Reporting an outage as « rien de
  prenable » claims knowledge about the trackers that we do not have.
* **Never searched → ``non_verifie``.** No verdict at all (``last_search_outcome
  is None``) means we know nothing, so we say nothing. One level up, a follow
  with no aired catalog aggregates to ``non_verifie`` too — NEVER ``a_jour``.
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

from typing import Literal

from personalscraper.acquire.orchestrator import INCONCLUSIVE_OUTCOMES

#: State of ONE aired episode (or of the single unit a followed film is).
EpisodeState = Literal["en_mediatheque", "a_recuperer", "en_acquisition", "en_attente", "non_verifie"]

#: State of a followed card, aggregated from its episodes. Same vocabulary as
#: :data:`EpisodeState` (``en_mediatheque`` becoming the card-level ``a_jour``),
#: plus ``disabled`` (follow paused) and ``verification_en_cours`` (a priming
#: run is in flight — applied by the route layer, phase 6; the aggregation
#: itself never returns it).
FollowStatus = Literal[
    "disabled",
    "verification_en_cours",
    "a_recuperer",
    "en_acquisition",
    "en_attente",
    "non_verifie",
    "a_jour",
]

#: Card-level reading of a single-unit state (a followed film). Every value is
#: the identity except ``en_mediatheque`` — a film held by the library reads
#: « À jour » on its card, not « En médiathèque ».
_EPISODE_TO_FOLLOW_STATUS: dict[EpisodeState, FollowStatus] = {
    "en_mediatheque": "a_jour",
    "a_recuperer": "a_recuperer",
    "en_acquisition": "en_acquisition",
    "en_attente": "en_attente",
    "non_verifie": "non_verifie",
}


def derive_episode_state(
    *,
    owned: bool,
    wanted_status: str | None,
    last_search_outcome: str | None,
    last_search_found: int | None,
) -> EpisodeState:
    """Derive one aired episode's state from persisted facts only.

    The evaluation order IS the specification — first match wins:

    1. ``owned`` → ``en_mediatheque``. Ownership beats everything: a file on
       disk is the strongest fact we hold, so a stale ``grabbed`` row on an
       owned episode is a phantom (the Silo bug) and cannot pin the episode at
       « en cours d'acquisition ».
    2. ``wanted_status == "grabbed"`` → ``en_acquisition`` (torrent taken, the
       pipeline is carrying it).
    3. ``wanted_status == "available"`` → ``a_recuperer`` (the search found a
       takeable candidate that the grab pass has not claimed yet).
    4. ``last_search_outcome is None`` → ``non_verifie``. Never searched: we
       have no verdict, so we assert nothing.
    5. ``last_search_outcome in INCONCLUSIVE_OUTCOMES`` → ``non_verifie``.
       Panne ≠ absence — an outage, an open circuit or a dead swarm is not a
       statement about what the trackers hold.
    6. ``(last_search_found or 0) > 0`` → ``a_recuperer``. Defensive: the last
       verdict says something takeable exists even though the row is not
       ``available`` (a claim lost to a concurrent pass, a crash between the
       verdict write and the status write).
    7. otherwise → ``en_attente``. Searched, concluded, nothing takeable.

    A ``searching`` status deliberately falls through to rules 4-7: a claim in
    flight tells us nothing new, so the episode still reads from its last
    verdict. Likewise an episode with NO wanted row at all and no file reads
    ``non_verifie`` — absence of a row is absence of knowledge.

    Args:
        owned: Whether the library holds a live file for this episode.
        wanted_status: The episode's ``wanted`` row status, or ``None`` when no
            row exists.
        last_search_outcome: The named outcome of the last search pass
            (``no_candidates`` / ``all_filtered`` / ``trackers_unavailable`` /
            …), or ``None`` when the episode was never searched.
        last_search_found: Number of TAKEABLE candidates the last search
            reported, or ``None`` when the search did not conclude.

    Returns:
        The episode's :data:`EpisodeState`.
    """
    if owned:
        return "en_mediatheque"
    if wanted_status == "grabbed":
        return "en_acquisition"
    if wanted_status == "available":
        return "a_recuperer"
    if last_search_outcome is None:
        return "non_verifie"
    if last_search_outcome in INCONCLUSIVE_OUTCOMES:
        return "non_verifie"
    if (last_search_found or 0) > 0:
        return "a_recuperer"
    return "en_attente"


def derive_follow_status(
    *,
    active: bool,
    aired_count: int | None,
    a_recuperer_count: int | None,
    en_acquisition_count: int | None,
    en_attente_count: int | None,
    non_verifie_count: int | None,
) -> FollowStatus:
    """Aggregate a followed SHOW's per-state episode counts into its card status.

    Most-actionable-first — the card must show what asks for an action, not the
    most frequent state:

    1. not ``active`` → ``disabled`` (the follow is paused; nothing else matters).
    2. ``aired_count is None`` → ``non_verifie``. NO catalog means no knowledge,
       and a series we know nothing about is NEVER « À jour » — this is the
       founding incident's direct fix, replacing the old fallthrough onto the
       raw ``wanted`` counters.
    3. any ``a_recuperer`` → ``a_recuperer`` (something is takeable now).
    4. any ``en_acquisition`` → ``en_acquisition``.
    5. any ``en_attente`` → ``en_attente``.
    6. any ``non_verifie`` → ``non_verifie`` (we still owe a verification).
    7. otherwise every aired episode is owned → ``a_jour``.

    ``verification_en_cours`` is deliberately never returned here: a priming run
    in flight is a runtime fact the route layer overlays (phase 6), not a
    property of the persisted counts.

    Args:
        active: Whether the follow is active.
        aired_count: Aired episodes known from the catalog cache, or ``None``
            when no catalog has ever been written for this follow.
        a_recuperer_count: Aired episodes with a takeable candidate.
        en_acquisition_count: Aired episodes taken / carried by the pipeline.
        en_attente_count: Aired episodes searched with nothing takeable.
        non_verifie_count: Aired episodes never searched or inconclusive.

    Returns:
        The card's :data:`FollowStatus`.
    """
    if not active:
        return "disabled"
    if aired_count is None:
        return "non_verifie"
    if (a_recuperer_count or 0) > 0:
        return "a_recuperer"
    if (en_acquisition_count or 0) > 0:
        return "en_acquisition"
    if (en_attente_count or 0) > 0:
        return "en_attente"
    if (non_verifie_count or 0) > 0:
        return "non_verifie"
    return "a_jour"


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
    level: ``en_mediatheque`` becomes ``a_jour``, every other state keeps its
    name. Ownership still beats a phantom ``grabbed`` row, and a film we have
    never searched reads ``non_verifie`` rather than claiming « À jour ».

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
    "EpisodeState",
    "FollowStatus",
    "derive_episode_state",
    "derive_follow_status",
    "derive_movie_status",
]
