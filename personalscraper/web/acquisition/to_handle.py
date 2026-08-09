"""« À traiter » — blocked media THAT CAME FROM AN ACQUISITION.

§14.3: a journey has no hole. An item grabbed then ingested that stalls at
identification is in the middle of ITS journey; it must stay visible from the
acquisition surface. A manual deposit is not an acquisition: it is counted
(§méthode — never under-count what needs attention) but never listed here;
it belongs on the « À traiter » panel in Contrôle.

The correlation requires NO migration: ``ProvenanceRow`` already carries
``decision_id``, and ``by_path()`` finds the row by its staging path.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.store import AcquireStore

logger = get_logger(__name__)

# Verdict machine → French reason label. NE-DOIT-PAS-4: never the raw token.
_REASON: dict[str, str] = {
    "ambiguous": "titre ambigu",
    "unmatched": "aucun candidat — recherche manuelle prête",
    "verify_failed": "vérification refusée — reprise nécessaire",
}
_UNKNOWN_REASON = "identification impossible au dernier passage"


@dataclass(frozen=True)
class ToHandleItem:
    """A blocked decision carried by an acquisition."""

    decision_id: int
    title: str
    year: int | None
    kind: str
    reason: str
    candidates_count: int
    created_at: int
    followed_id: int | None
    info_hash: str | None
    stage: str
    # Episode identity from the provenance spine (migration 017) — lets the
    # blocked card say « S16E12 » (maquette); None when the grab carried none.
    season: int | None = None
    episode: int | None = None


@dataclass(frozen=True)
class ToHandleRollup:
    """The split between what is shown here and what is counted elsewhere.

    Attributes:
        items: The blocked items carried by an acquisition, oldest first.
        orphan_count: Blocked items with no acquisition provenance.
        degraded: ``True`` when this reading could NOT complete. Every failure
            path here returns an empty rollup so the page never 500s — but an
            empty rollup and a failed one are different facts, and rendering
            the second as the first tells the operator there is nothing to
            handle when the truth is that we cannot tell. The flag is what
            keeps that distinction alive across the wire; without it the
            warning only reaches the server log, which the operator never
            reads.
    """

    items: tuple[ToHandleItem, ...]
    orphan_count: int
    degraded: bool = False


def _stage_of(row: object) -> str:
    """The stage actually reached — never a default value (§14.3)."""
    if getattr(row, "dispatched_at", None):
        return "range"
    if getattr(row, "scraped_at", None):
        return "scrape"
    if getattr(row, "ingested_at", None):
        return "ingere"
    if getattr(row, "grabbed_at", None):
        return "telech"
    return "pris"


def _reason_of(trigger: str, candidates: int) -> str:
    base = _REASON.get(trigger, _UNKNOWN_REASON)
    if trigger == "ambiguous":
        return f"{base} — {candidates} candidat{'s' if candidates > 1 else ''} proposé{'s' if candidates > 1 else ''}"
    return base


def build_to_handle(*, indexer_db: Path | None, store: AcquireStore | None) -> ToHandleRollup:
    """Build the « À traiter » rollup.

    Args:
        indexer_db: Path to ``library.db``, or ``None`` when unconfigured.
        store: The acquisition store whose provenance spine carries the journeys,
            or ``None``.

    Returns:
        The rollup. Fail-soft: an unreadable database yields an empty rollup and a
        warning, never an exception — a broken read model must not take the page
        down with it.
    """
    if indexer_db is None or not Path(indexer_db).exists():
        return ToHandleRollup(items=(), orphan_count=0, degraded=True)

    try:
        conn = sqlite3.connect(f"file:{indexer_db}?mode=ro", uri=True)
        try:
            apply_pragmas(conn)
        except sqlite3.Error:
            pass  # Read-only connection — pragmas that require writes are harmless to skip.
        try:
            rows = conn.execute(
                "SELECT id, staging_path, media_kind, extracted_title, extracted_year, "
                "trigger, candidates_json, created_at FROM scrape_decision "
                "WHERE status = 'pending' ORDER BY created_at ASC"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.warning("to_handle_read_failed", db=str(indexer_db))
        return ToHandleRollup(items=(), orphan_count=0, degraded=True)

    if store is None:
        logger.warning("to_handle_store_unavailable")
        return ToHandleRollup(items=(), orphan_count=0, degraded=True)

    items: list[ToHandleItem] = []
    orphans = 0
    try:
        for decision_id, staging_path, kind, title, year, trigger, candidates_json, created_at in rows:
            try:
                candidates = len(json.loads(candidates_json or "[]"))
            except (TypeError, ValueError):
                candidates = 0

            prov = store.provenance.by_path(staging_path)
            if prov is None:
                orphans += 1
                continue

            items.append(
                ToHandleItem(
                    decision_id=int(decision_id),
                    title=str(title or ""),
                    year=int(year) if year is not None else None,
                    kind=str(kind or ""),
                    reason=_reason_of(str(trigger or ""), candidates),
                    candidates_count=candidates,
                    created_at=int(created_at or 0),
                    followed_id=getattr(prov, "followed_id", None),
                    info_hash=getattr(prov, "info_hash", None),
                    stage=_stage_of(prov),
                    season=getattr(prov, "season", None),
                    episode=getattr(prov, "episode", None),
                )
            )
    except Exception as exc:  # noqa: BLE001 — fail-soft: the page must never 500
        # §méthode — « outage ≠ absence »: if the provenance store is broken, we
        # can assert nothing about any media. This is not a silent fail-soft
        # (§8 forbids it): the warning is what distinguishes it from a silent
        # « nothing to handle ».
        logger.warning("to_handle_correlation_failed", error=str(exc))
        return ToHandleRollup(items=(), orphan_count=0, degraded=True)

    return ToHandleRollup(items=tuple(items), orphan_count=orphans)
