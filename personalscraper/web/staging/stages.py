"""Stage taxonomy + single-position axiom for the staging read-model (P0-A).

This module is the ONE source of truth for the Flow Board stage taxonomy and
for a staged media's **position** in the pipeline. The taxonomy mirrors the
real engine steps the operator understands (product-intent.md §2 — honest
labels, no invented "Staging" step: the staging area is the *place* where the
whole flow happens, not a step of it):

    Arrivée (ingest) · Tri (sort/enforce) · Nettoyage (clean/cleanup) ·
    Identification (matching/decisions) · Scraping · Trailers ·
    Vérification · Dispatch

The **position axiom** (P0-A.1): a media sitting in the staging area is at
*exactly one* position — either awaiting one stage, or blocked at one stage
(with a reason). Never two stations at once. Board stocks, the per-stage
media list and the per-item timeline are all derived from the same
:func:`compute_position` verdict, so they can never disagree.

A dispatched media leaves the staging tree and therefore has no position —
it simply disappears from the scan (its home is the library, not the board).
"""

from __future__ import annotations

from typing import Literal

from personalscraper.web.models.staging import StagingStageStep

#: The eight Flow Board stages, in board (left-to-right) order, with French
#: labels. One station per *real* engine concern — "Staging" is not a step.
STAGE_DEFS: tuple[tuple[str, str], ...] = (
    ("arrival", "Arrivée"),
    ("sorting", "Tri"),
    ("cleaning", "Nettoyage"),
    ("matching", "Identification"),
    ("scraping", "Scraping"),
    ("trailers", "Trailers"),
    ("verify", "Vérification"),
    ("dispatch", "Dispatch"),
)

#: Stage keys in board order (for index lookups / validation).
STAGE_KEYS: tuple[str, ...] = tuple(key for key, _ in STAGE_DEFS)

#: Real pipeline step name → stage key, so a live run lights up the station
#: (and the item positions) its current step belongs to.
STEP_TO_STAGE: dict[str, str] = {
    "ingest": "arrival",
    "sort": "sorting",
    "enforce": "sorting",
    "clean": "cleaning",
    "cleanup": "cleaning",
    "scrape": "scraping",
    "trailers": "trailers",
    "verify": "verify",
    "dispatch": "dispatch",
}

#: Position state: a media awaits its stage (``pending``), the live run is
#: processing it there (``active``), or an operator/repair is needed (``blocked``).
PositionState = Literal["pending", "active", "blocked"]

#: Timeline stages that do not apply to kinds outside the scrape flow.
_SKIP_FOR_NON_SCRAPABLE: frozenset[str] = frozenset({"matching", "scraping", "trailers", "verify"})

#: Timeline stages that do not apply to an AUTRES/unknown item (it *is*
#: actionable at Identification — the operator qualifies its kind there).
_SKIP_FOR_OTHER: frozenset[str] = frozenset({"scraping", "trailers", "verify"})

#: French blocked reasons for the non-verify block causes (verify blocks carry
#: the real verify-gate reason computed by the read-model).
REASON_AMBIGUOUS = "À identifier : décision en attente dans la file de résolution"
REASON_ABSENT = "Non identifié : à envoyer en résolution"
REASON_OTHER = "À qualifier : type de média à préciser (film ou série)"
REASON_VERIFY_UNAVAILABLE = "Bloqué : vérification indisponible"


def compute_position(
    *,
    media_kind: str,
    in_ingest: bool,
    scrapable: bool,
    is_ambiguous: bool,
    is_matched: bool,
    verify_ok: bool,
    live_stage_key: str | None,
) -> tuple[str, PositionState]:
    """Derive the single position of a staged media — the P0-A.1 axiom.

    Exactly one ``(stage, state)`` per item, derived from the same signals the
    timeline uses. The rules, in order:

    - still in the ingest dir → at ``arrival`` (integrated, awaiting sort);
    - an AUTRES/unknown kind → blocked at ``matching`` (operator qualifies it);
    - a non-scrapable kind (ebook/audio/app) → awaiting ``dispatch``;
    - a pending decision → blocked at ``matching`` (resolution deck);
    - no confident match → blocked at ``matching`` (needs enqueue);
    - scraped but refused by the real verify gate → blocked at ``verify``;
    - scraped and verified → awaiting ``dispatch``.

    A ``pending`` position flips to ``active`` when the live run's current
    step maps to that stage.

    Args:
        media_kind: The read-model media kind (``movie`` … ``unsorted``).
        in_ingest: Whether the item still sits in the ingest dir (pre-sort).
        scrapable: Whether the kind flows through match/scrape/trailer/verify.
        is_ambiguous: Whether a pending decision blocks identification.
        is_matched: Whether the media has a confident match (NFO + ids).
        verify_ok: Whether the real pipeline ``verify`` gate passes this item.
        live_stage_key: Stage key of the live run's current step, or ``None``.

    Returns:
        The ``(stage_key, state)`` position tuple.
    """
    stage: str
    state: PositionState
    if in_ingest:
        stage, state = "arrival", "pending"
    elif media_kind == "other":
        stage, state = "matching", "blocked"
    elif not scrapable:
        stage, state = "dispatch", "pending"
    elif is_ambiguous:
        stage, state = "matching", "blocked"
    elif not is_matched:
        stage, state = "matching", "blocked"
    elif not verify_ok:
        stage, state = "verify", "blocked"
    else:
        stage, state = "dispatch", "pending"

    if state == "pending" and live_stage_key == stage:
        state = "active"
    return stage, state


def position_blocked_reason(
    *,
    media_kind: str,
    stage: str,
    state: PositionState,
    is_ambiguous: bool,
    verify_reason: str | None,
) -> str | None:
    """Return the French reason for a blocked position, or ``None``.

    Verify blocks carry the real verify-gate reason (computed by the
    read-model from the same checks that authorize dispatch); identification
    blocks carry a fixed actionable phrase.

    Args:
        media_kind: The read-model media kind.
        stage: The position stage from :func:`compute_position`.
        state: The position state from :func:`compute_position`.
        is_ambiguous: Whether a pending decision blocks identification.
        verify_reason: The verify-gate reason (``"Bloqué : …"``), or ``None``.

    Returns:
        The operator-facing reason, or ``None`` for a non-blocked position.
    """
    if state != "blocked":
        return None
    if stage == "verify":
        return verify_reason or REASON_VERIFY_UNAVAILABLE
    if media_kind == "other":
        return REASON_OTHER
    if is_ambiguous:
        return REASON_AMBIGUOUS
    return REASON_ABSENT


def compute_stages(
    *,
    media_kind: str,
    scrapable: bool,
    position_stage: str,
    position_state: PositionState,
) -> list[StagingStageStep]:
    """Build the per-item eight-stage timeline from its single position.

    The timeline is the position, unrolled: every stage before the position is
    ``done``, the position stage carries the position state, and every stage
    after is ``pending``. Stages that do not apply to the kind are ``skipped``.
    Because it derives from :func:`compute_position`, the timeline can never
    disagree with the board or the stage lists (P0-A.1).

    Args:
        media_kind: The read-model media kind.
        scrapable: Whether the kind flows through match/scrape/trailer/verify.
        position_stage: The stage key from :func:`compute_position`.
        position_state: The state from :func:`compute_position`.

    Returns:
        The ordered list of :class:`StagingStageStep` for the timeline.
    """
    if media_kind == "other":
        skipped = _SKIP_FOR_OTHER
    elif not scrapable:
        skipped = _SKIP_FOR_NON_SCRAPABLE
    else:
        skipped = frozenset()

    position_index = STAGE_KEYS.index(position_stage)
    steps: list[StagingStageStep] = []
    for index, (key, label) in enumerate(STAGE_DEFS):
        if key in skipped:
            state = "skipped"
        elif index < position_index:
            state = "done"
        elif index == position_index:
            state = position_state
        else:
            state = "pending"
        steps.append(StagingStageStep(key=key, label=label, state=state))  # type: ignore[arg-type]
    return steps
