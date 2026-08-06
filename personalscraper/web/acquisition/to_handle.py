"""« À traiter » — les médias bloqués QUI VIENNENT D'UNE ACQUISITION.

§14.3 : un parcours n'a pas de trou. Un item pris puis ingéré qui cale à
l'identification est au milieu de SON parcours ; il doit rester visible depuis
l'acquisition. Un dépôt manuel, lui, n'est pas une acquisition : il est compté
(§méthode — ne jamais sous-compter ce qui demande attention) mais jamais listé
ici, il appartient au panneau « À traiter » de Contrôle.

La corrélation n'exige AUCUNE migration : ``ProvenanceRow`` porte déjà
``decision_id``, et ``by_path()`` retrouve la ligne par son chemin de staging.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.store import AcquireStore

logger = get_logger(__name__)

# Verdict machine → raison française. NE-DOIT-PAS-4 : jamais le token brut.
_REASON: dict[str, str] = {
    "ambiguous": "titre ambigu",
    "unmatched": "aucun candidat — recherche manuelle prête",
    "verify_failed": "vérification refusée — reprise nécessaire",
}
_UNKNOWN_REASON = "identification impossible au dernier passage"


@dataclass(frozen=True)
class ToHandleItem:
    """Une décision bloquée portée par une acquisition."""

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


@dataclass(frozen=True)
class ToHandleRollup:
    """Le partage entre ce qui s'affiche ici et ce qui se compte ailleurs."""

    items: tuple[ToHandleItem, ...]
    orphan_count: int


def _stage_of(row: object) -> str:
    """L'étape réellement atteinte — jamais une valeur par défaut (§14.3)."""
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
        return ToHandleRollup(items=(), orphan_count=0)

    try:
        conn = sqlite3.connect(f"file:{indexer_db}?mode=ro", uri=True)
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
        return ToHandleRollup(items=(), orphan_count=0)

    if store is None:
        logger.warning("to_handle_store_unavailable")
        return ToHandleRollup(items=(), orphan_count=0)

    items: list[ToHandleItem] = []
    orphans = 0
    for decision_id, staging_path, kind, title, year, trigger, candidates_json, created_at in rows:
        try:
            candidates = len(json.loads(candidates_json or "[]"))
        except (TypeError, ValueError):
            candidates = 0

        prov = store.provenance.by_path(staging_path) if store is not None else None
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
            )
        )

    return ToHandleRollup(items=tuple(items), orphan_count=orphans)
