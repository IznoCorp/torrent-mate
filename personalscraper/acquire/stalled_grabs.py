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

A THIRD shape hid behind that same journey reading, and it hid for as long as it was
looked at: an acquisition that DID reach the library while its ``wanted`` row stayed
open. A landed journey was excluded from the check unconditionally — « a success awaiting
reconciliation » — which is true for a pass or two and false forever after. « Les Groos »
S01 was dispatched on 2026-08-28 and still read ``grabbed`` four days later, because the
pack carried 12 of the 13 aired episodes and ownership-based closure is all-or-nothing.
The row had no other reader: neither pass walks ``grabbed``. That exemption is now
bounded by a horizon like every other, so the case is audible even when the closure
itself is repaired elsewhere (``reconcile``) — a rule that cannot fire is a rule that
tells you nothing about the day it was needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.acquire._provenance_store import LANDED_JOURNEY_STATUSES
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

#: Horizon for a journey that reached the library while its ``wanted`` row stayed open.
#: Reconciliation runs on every detect/grab pass, so a row still ``grabbed`` two hours
#: after its media was shelved is not « awaiting reconciliation »: it is a closure that
#: is not coming. Same two hours as the ingested horizon, for the same reason — far
#: longer than the passes that should have closed it, far shorter than a day of silence.
STALLED_AFTER_DISPATCH_SECONDS = 7200

_REASON_RUN_LEFT_BEHIND = "un run s'est terminé depuis l'ingestion sans la ranger"
_REASON_NEVER_SHELVED = "ingéré mais jamais rangé en médiathèque"
_REASON_NOTHING_FOLLOWED = "récupéré, rien n'a suivi depuis"
_REASON_LANDED_NEVER_CLOSED = "rangé en médiathèque, mais l'acquisition ne s'est jamais refermée"


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

    ``dispatched_at`` leads the preference order. It used to be absent entirely, which
    was coherent while a dispatched journey could never be stalled; now that one can
    be, omitting it would date a landed stall from its SCRAPE and tell the operator it
    has been waiting since a step it left behind.

    Args:
        wanted: The parked ``wanted`` row.
        row: Its journey, or ``None`` when no provenance row exists.

    Returns:
        Epoch seconds of the latest known step.
    """
    if row is not None:
        stage = row.dispatched_at or row.scraped_at or row.ingested_at or row.grabbed_at
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

    Four triggers, most decisive first:

    0. **The media landed and the row never closed** — decided first because it
       overrides everything below: the item is not « ingested and idle », it is
       SHELVED, and the only thing owed is the reconciliation that closes its row.
       That wait is bounded (:data:`STALLED_AFTER_DISPATCH_SECONDS`), where it used
       to be an unconditional exemption — which is how « Les Groos » S01 read
       « en vol » for four days with its episodes on the disk, silent to this
       function because its journey said ``dispatched``.

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

    # The media IS on the shelf. Reconciliation is what closes the row now, and it
    # runs on every detect/grab pass — so this is a SHORT, bounded wait, not a
    # permanent exemption. Excluding a landed journey outright is what made the
    # « Les Groos » stall mute for four days: the pack was one episode short of the
    # aired catalog, so ownership could never close the season row, and this
    # function answered « merely awaiting reconciliation » every time it was asked.
    # A row still open long after its media landed is the anomaly, whichever of the
    # two terminal names the journey carries.
    if row is not None and row.status in LANDED_JOURNEY_STATUSES:
        if row.dispatched_at is None:
            # A RECONSTRUCTED journey (§14.3) carries the stage but not its instant:
            # « unknown », never « long ago ». Absence of a date must not manufacture
            # an alert.
            return None
        idle_since_landing = now - row.dispatched_at
        return _REASON_LANDED_NEVER_CLOSED if idle_since_landing > STALLED_AFTER_DISPATCH_SECONDS else None

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
    "STALLED_AFTER_DISPATCH_SECONDS",
    "STALLED_AFTER_INGEST_SECONDS",
    "STALLED_WITHOUT_INGEST_SECONDS",
    "StalledGrab",
    "list_stalled_grabs",
    "stalled_grab_reason",
]
