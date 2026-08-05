"""Detect acquisitions parked at « récupéré » that never reach the library.

product-intent §14.1 names only TWO legitimate resting states for an acquisition:
« pas encore diffusé » and « cherché, rien trouvé ». Everything else — « disponible »,
« récupéré » — is **transitory** and must advance on its own. A ``wanted`` row parked at
``grabbed`` is therefore non-conforme by construction, and it is invisible twice over:

- the search pass only reclaims ``pending`` / ``searching`` / ``available``
  (``_search_pass.py``), so a parked row is never re-searched — the media stays wanted
  forever without anyone looking for it again;
- the F4 ``stuck`` flag is **journey**-level and requires the folder to still be on disk,
  so it says nothing once the staging copy is gone, and nothing at all about a grab whose
  journey row was never written.

This module answers the wanted-level question — « qu'est-ce qui a été récupéré et n'est
jamais arrivé en médiathèque ? » — once, so every surface reads the same derivation (§13).

The detector deliberately keys on the JOURNEY to tell a finished download from a running
one: ``ingested_at`` is proof the torrent completed (the pipeline only ingests completed
torrents), which is what makes a short horizon honest. Without that proof a grab may
legitimately still be downloading for hours, so only a long safety net applies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.acquire._store_rows import _media_ref_to_json

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.acquire._provenance_store import ProvenanceRow
    from personalscraper.acquire.domain import WantedItem

#: Horizon once the download is PROVEN finished (the journey reached ``ingested``).
#: 2h outlasts a full pipeline run — dispatch alone can take ~50 min — so a normal
#: in-flight item is never flagged.
STALLED_AFTER_INGEST_SECONDS = 7200

#: Safety-net horizon when nothing proves the download finished. A big torrent
#: legitimately takes hours, so this must stay far longer than the ingested horizon;
#: it exists so a grab that never lands is caught eventually rather than never.
STALLED_WITHOUT_INGEST_SECONDS = 86400

#: Journey statuses that mean the acquisition DID reach the library — never stalled.
_TERMINAL_JOURNEY_STATUSES = frozenset({"dispatched", "reconciled"})

_REASON_RUN_LEFT_BEHIND = "un run s'est terminé depuis l'ingestion sans la ranger"
_REASON_NEVER_SHELVED = "ingéré mais jamais rangé en médiathèque"
_REASON_NOTHING_FOLLOWED = "récupéré, rien n'a suivi depuis"


@dataclass(frozen=True, kw_only=True)
class StalledGrab:
    """One acquisition parked at « récupéré », with the reason it is flagged.

    Attributes:
        wanted_id: Rowid of the parked ``wanted`` row.
        media_ref_json: The wanted item's provider IDs, for the UI deep-link.
        kind: ``"movie"`` / ``"episode"`` / ``"season"``.
        season: Season number, or ``None`` for a movie.
        episode: Episode number, or ``None``.
        info_hash: The release the row is committed to (its ``grabbed_hash``).
        release_name: The release actually grabbed, when known — the field that
            would have shown the operator a FLAC album under a film's title.
        since: Epoch of the latest known step, i.e. how long it has been parked.
        reason: Why it is flagged, in plain French (§8 — never a bare count).
    """

    wanted_id: int
    media_ref_json: str
    kind: str
    season: int | None
    episode: int | None
    info_hash: str
    release_name: str | None
    since: int
    reason: str


def _latest_step_at(wanted: "WantedItem", row: "ProvenanceRow | None") -> int:
    """The most recent instant this acquisition is known to have moved.

    Prefers the journey's own stage timestamps (they describe the pipeline, which is
    what stalls); falls back to the wanted row's clock for a grab with no journey —
    a row predating the provenance spine must not become invisible for lack of it.

    Args:
        wanted: The parked ``wanted`` row.
        row: Its journey, or ``None`` when no provenance row exists.

    Returns:
        Epoch seconds of the latest known step.
    """
    if row is not None:
        stage = row.scraped_at or row.ingested_at or row.grabbed_at
        if stage is not None:
            return stage
    return wanted.last_search_at or wanted.enqueued_at


def stalled_grab_reason(
    wanted: "WantedItem",
    row: "ProvenanceRow | None",
    *,
    now: int,
    last_run_finished_at: int | None = None,
) -> str | None:
    """Return why this grab is stalled, or ``None`` when it is progressing normally.

    Only a ``grabbed`` wanted qualifies — that is the parked state §14.1 calls out.
    A journey that already reached ``dispatched`` / ``reconciled`` is a success awaiting
    reconciliation, never a stall.

    Three triggers, most decisive first:

    1. **A run finished and left it behind** — no clock involved. If a pipeline run
       completed AFTER this item was ingested and the item is still not shelved, the
       product already knows it will not be: that run was its chance. This is the
       §14.3 rule applied to the alert — follow the run, not a horizon. It is what
       would have spoken at 20:40:24 on 2026-08-05 instead of leaving the operator to
       ask two hours later.
    2. **Ingested and idle past the short horizon** — the fallback when no run history
       is readable.
    3. **Never ingested, idle past the long horizon** — the safety net for a download
       that never lands.

    Args:
        wanted: The ``wanted`` row to judge.
        row: Its journey (matched on ``grabbed_hash``), or ``None`` if absent.
        now: Current epoch seconds.
        last_run_finished_at: Epoch the last pipeline run finished, or ``None`` when
            unknown — then trigger 1 is skipped and only the horizons apply (fail-soft:
            missing run history must never manufacture an alert).

    Returns:
        A plain-French reason, or ``None``.
    """
    if wanted.status != "grabbed":
        return None
    if row is not None and row.status in _TERMINAL_JOURNEY_STATUSES:
        return None

    if (
        row is not None
        and row.ingested_at is not None
        and last_run_finished_at is not None
        and last_run_finished_at > row.ingested_at
    ):
        return _REASON_RUN_LEFT_BEHIND

    idle = now - _latest_step_at(wanted, row)
    # ``ingested_at`` is PROOF the torrent completed: the pipeline ingests completed
    # torrents only. That proof is what licenses the short horizon — without it the
    # download may still be running and a short horizon would cry wolf.
    if row is not None and row.ingested_at is not None:
        return _REASON_NEVER_SHELVED if idle > STALLED_AFTER_INGEST_SECONDS else None
    return _REASON_NOTHING_FOLLOWED if idle > STALLED_WITHOUT_INGEST_SECONDS else None


def list_stalled_grabs(
    wanted_rows: "list[WantedItem]",
    journey_for: "Callable[[str], ProvenanceRow | None]",
    *,
    now: int,
    release_name_for: "Callable[[ProvenanceRow | None], str | None]",
    last_run_finished_at: int | None = None,
) -> list[StalledGrab]:
    """Return every parked acquisition among *wanted_rows*, most-stale first.

    Pure composition over injected lookups so the whole rule is unit-testable without a
    database, and so the caller owns the store lifetime.

    Args:
        wanted_rows: Candidate ``wanted`` rows (the ``grabbed`` queue).
        journey_for: Maps an info-hash to its journey, or ``None``.
        now: Current epoch seconds.
        release_name_for: Maps a journey to the release name actually grabbed — the
            SAME derivation the journeys surface uses (§13: one derivation per question).
        last_run_finished_at: Epoch the last pipeline run finished, or ``None``.

    Returns:
        The stalled acquisitions, oldest step first (the ones waiting longest lead).
    """
    stalled: list[StalledGrab] = []
    for wanted in wanted_rows:
        if wanted.id is None or not wanted.grabbed_hash:
            continue
        row = journey_for(wanted.grabbed_hash)
        reason = stalled_grab_reason(wanted, row, now=now, last_run_finished_at=last_run_finished_at)
        if reason is None:
            continue
        stalled.append(
            StalledGrab(
                wanted_id=wanted.id,
                media_ref_json=_media_ref_to_json(wanted.media_ref),
                kind=wanted.kind,
                season=wanted.season,
                episode=wanted.episode,
                info_hash=wanted.grabbed_hash,
                release_name=release_name_for(row),
                since=_latest_step_at(wanted, row),
                reason=reason,
            )
        )
    stalled.sort(key=lambda s: s.since)
    return stalled


__all__ = [
    "STALLED_AFTER_INGEST_SECONDS",
    "STALLED_WITHOUT_INGEST_SECONDS",
    "StalledGrab",
    "list_stalled_grabs",
    "stalled_grab_reason",
]
