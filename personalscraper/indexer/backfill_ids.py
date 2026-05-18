"""Provider-IDs backfill helpers — gap detection + safe-merge.

The :mod:`personalscraper.indexer.scanner._modes.backfill_ids` driver
(sub-phase 8.2) uses these pure functions to figure out what needs to
be fetched for a given media item and how to merge the freshly fetched
data into the existing ``external_ids_json`` / ``ratings_json``
columns *without* overwriting the canonical provider IDs that the
phase-5 scrape already established.

Two invariants drive the contract :

- **No cross-contamination** (DESIGN §3) — the canonical family,
  declared by ``media_item.canonical_provider``, is *never* replaced
  by a backfill pass. The merge is strictly additive on the
  non-canonical families.
- **No rating overwrite** — once a source has a rating row, the
  backfill leaves it alone. This guards against an OMDb regression
  silently downgrading a previously-good IMDb score.

Both functions return :class:`BackfillResult` carrying what *changed*
so the caller can decide whether the row needs a DB write + NFO
rewrite, or whether the pass is a no-op (DESIGN §5 idempotence — a
second backfill pass on the same row must produce no further writes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Provider families recognised by ``external_ids_json``. ``imdb`` is
# included because the IMDb façade lives alongside TVDB and TMDb in
# the metadata family ; rating-only providers (Rotten Tomatoes,
# Metacritic) carry no series ID of their own.
_ID_FAMILIES: tuple[str, ...] = ("tvdb", "tmdb", "imdb")


@dataclass(frozen=True)
class BackfillGap:
    """What a media-item row is missing relative to a fully-populated state.

    Attributes:
        missing_id_families: Families for which the row has no series ID
            and whose façade may yet have one. Excludes the canonical
            family (already authenticated by the scrape).
        missing_rating_sources: Sources for which the row has no
            :class:`Ratings` entry — typically ``"imdb"``,
            ``"rotten_tomatoes"``.
    """

    missing_id_families: tuple[str, ...] = ()
    missing_rating_sources: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """``True`` when nothing is missing — the row is fully populated."""
        return not self.missing_id_families and not self.missing_rating_sources


@dataclass
class BackfillResult:
    """Outcome of a single-row backfill merge.

    Attributes:
        external_ids_json: New JSON string for the row's
            ``external_ids_json`` column. Identical to the input when
            nothing changed.
        ratings_json: New JSON string (or ``None``) for the row's
            ``ratings_json`` column. Identical to the input when
            nothing changed.
        ids_added: Provider families whose series ID was newly added.
        ratings_added: Rating sources whose entry was newly added.
    """

    external_ids_json: str
    ratings_json: str | None
    ids_added: list[str] = field(default_factory=list)
    ratings_added: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        """``True`` when at least one field was added by the merge."""
        return bool(self.ids_added or self.ratings_added)


def detect_gaps(
    external_ids_json: str,
    ratings_json: str | None,
    canonical_provider: str | None,
    *,
    rating_sources: tuple[str, ...] = ("imdb", "rotten_tomatoes"),
) -> BackfillGap:
    """Return the families + rating sources that a backfill pass should fetch.

    The canonical family is *excluded* from
    ``missing_id_families`` regardless of whether its series ID is
    present — the canonical scrape's authority over that family is
    absolute (DESIGN §3). A row whose canonical scrape never landed
    surfaces only the *other* families ; the row stays a candidate
    for re-scrape rather than backfill.

    Args:
        external_ids_json: Current value of the
            ``external_ids_json`` column.
        ratings_json: Current value of the ``ratings_json`` column
            (may be ``None``).
        canonical_provider: Value of ``media_item.canonical_provider``
            — ``"tvdb"`` / ``"tmdb"`` / ``None``.
        rating_sources: Rating sources the backfill considers. Defaults
            to the IMDb + Rotten Tomatoes pair which are reachable
            via the OMDb façades shipped in phase 3.

    Returns:
        Populated :class:`BackfillGap`. Empty when every field is set.
    """
    eids = _load_json(external_ids_json) or {}
    missing_ids: list[str] = []
    for family in _ID_FAMILIES:
        if family == canonical_provider:
            continue
        entry = eids.get(family) or {}
        if not entry.get("series_id"):
            missing_ids.append(family)

    ratings_obj = _load_json(ratings_json) or {}
    existing_sources = {
        entry.get("source") for entry in ratings_obj.get("entries", []) if isinstance(entry, dict)
    }
    missing_ratings = tuple(source for source in rating_sources if source not in existing_sources)

    return BackfillGap(
        missing_id_families=tuple(missing_ids),
        missing_rating_sources=missing_ratings,
    )


def merge_ids_without_overwrite(
    external_ids_json: str,
    new_ids: dict[str, str],
    *,
    canonical_provider: str | None = None,
) -> tuple[str, list[str]]:
    """Merge ``new_ids`` into ``external_ids_json`` without overwriting.

    Each ``new_ids`` entry maps a provider family
    (``"tvdb"`` / ``"tmdb"`` / ``"imdb"``) to its series ID string.
    The function refuses to overwrite the canonical family entirely,
    and refuses to overwrite a non-canonical family whose
    ``series_id`` is already populated.

    Args:
        external_ids_json: Current column value (JSON string).
        new_ids: ``{family: series_id}`` to merge in.
        canonical_provider: Family the row treats as canonical, or
            ``None`` when the row never re-scraped under the new flow.

    Returns:
        Tuple ``(updated_json, families_added)`` — ``families_added``
        lists the keys whose ``series_id`` was newly written.
    """
    eids = _load_json(external_ids_json) or {}
    added: list[str] = []
    for family, value in new_ids.items():
        if not value:
            continue
        if family == canonical_provider:
            continue
        current = eids.get(family) or {}
        if current.get("series_id"):
            continue
        merged = {"series_id": str(value), "episode_id": current.get("episode_id")}
        eids[family] = merged
        added.append(family)
    return json.dumps(eids), added


def merge_ratings_without_overwrite(
    ratings_json: str | None,
    new_entries: list[dict[str, str | int | None]],
) -> tuple[str, list[str]]:
    """Append rating rows whose ``source`` is not already present.

    The merge is *append-only* — an existing row for a given source is
    never replaced, even when the incoming row carries a higher score.
    Callers seeking to refresh a stale rating must explicitly remove
    the existing row before calling the backfill (out of scope here).

    Args:
        ratings_json: Current column value or ``None``.
        new_entries: List of dicts with at minimum a ``source`` key.

    Returns:
        Tuple ``(updated_json, sources_added)``.
    """
    payload = _load_json(ratings_json) or {}
    existing_entries = list(payload.get("entries", []))
    existing_sources = {
        entry.get("source") for entry in existing_entries if isinstance(entry, dict)
    }
    added: list[str] = []
    for entry in new_entries:
        source = entry.get("source")
        if not isinstance(source, str) or source in existing_sources:
            continue
        existing_entries.append(dict(entry))
        existing_sources.add(source)
        added.append(source)
    payload["entries"] = existing_entries
    return json.dumps(payload), added


def _load_json(raw: str | None) -> dict[str, Any] | None:
    """Parse a JSON column value, returning ``None`` on empty / malformed input."""
    if not raw:
        return None
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


__all__ = [
    "BackfillGap",
    "BackfillResult",
    "detect_gaps",
    "merge_ids_without_overwrite",
    "merge_ratings_without_overwrite",
]
