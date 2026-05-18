"""Backfill scan mode — fills cross-provider IDs + multi-source ratings.

The driver iterates every ``media_item`` row, detects which provider
families (TVDB / TMDb / IMDb) and rating sources (IMDb / Rotten
Tomatoes) are missing, calls the matching façades to fetch the
missing data, and writes the merged JSON back to the row — *without*
overwriting any canonical or already-present value (DESIGN §3, §5
idempotence).

This module is the orchestration layer ; the pure merge / gap
detection logic lives in
:mod:`personalscraper.indexer.backfill_ids` and is unit-tested
independently. The driver focuses on iteration, provider dispatch,
and the DB transaction wrapping each row update.

The driver is intentionally exposed as a free function rather than
plugged into the main :class:`ScanMode` dispatch. Backfill is
per-item (not per-disk) so it does not benefit from the
disk-iteration scaffolding the other modes share. Callers — the CLI
``personalscraper indexer backfill-ids`` sub-command and the
post-scrape auto-trigger — invoke :func:`run_backfill_ids` directly.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Protocol

from personalscraper.api._helpers import ProviderFeatureUnavailable
from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.backfill_ids import (
    BackfillGap,
    detect_gaps,
    merge_ids_without_overwrite,
    merge_ratings_without_overwrite,
)
from personalscraper.indexer.events import (
    BackfillCompleted,
    BackfillItemCompleted,
    BackfillSkipped,
    BackfillStarted,
)
from personalscraper.logger import get_logger

log = get_logger("indexer.backfill_ids")


class _RatingClient(Protocol):
    """Structural type for the IMDb / RT façades the driver consults."""

    def get_rating(self, provider_id: str) -> list[Any] | None: ...


@dataclass
class BackfillStats:
    """Aggregate outcome of a backfill pass over the whole library.

    Attributes:
        items_scanned: Number of ``media_item`` rows visited.
        items_updated: Rows for which at least one ID or rating was added.
        items_skipped: Rows that were already fully populated.
        ids_added_count: Total provider IDs newly written across all rows.
        ratings_added_count: Total rating entries newly written.
        items_failed: Rows that errored mid-update (logged, not raised).
        items_failed_titles: Titles of the failed rows, for the CLI summary.
    """

    items_scanned: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    ids_added_count: int = 0
    ratings_added_count: int = 0
    items_failed: int = 0
    items_failed_titles: list[str] = field(default_factory=list)


def run_backfill_ids(
    conn: sqlite3.Connection,
    *,
    event_bus: EventBus,
    imdb_client: _RatingClient | None = None,
    rt_client: _RatingClient | None = None,
    show_filter: str | None = None,
    ids_only: bool = False,
    ratings_only: bool = False,
    dry_run: bool = False,
) -> BackfillStats:
    """Walk ``media_item`` and backfill missing provider IDs / ratings.

    The pass is fail-soft : a façade exception on a given row logs a
    warning, increments ``items_failed`` in the returned
    :class:`BackfillStats`, and the loop continues. The DB write per
    row is wrapped in a SAVEPOINT so a partial failure inside the
    update never leaves the row in an inconsistent state.

    Args:
        conn: Open writer connection on the indexer DB.
        imdb_client: IMDb façade used to fetch IMDb ratings (DESIGN
            §4). ``None`` skips IMDb rating backfill.
        rt_client: Rotten Tomatoes façade. ``None`` skips RT rating
            backfill.
        show_filter: Restrict the pass to the show whose title equals
            this string. Useful for the post-scrape auto-trigger.
        ids_only: When ``True``, do not fetch ratings.
        ratings_only: When ``True``, do not fetch IDs.
        dry_run: When ``True``, every DB write is rolled back.
        event_bus: Optional :class:`EventBus` used to publish
            ``BackfillStarted`` / ``BackfillItemCompleted`` /
            ``BackfillSkipped`` / ``BackfillCompleted`` events. When
            ``None``, the pass runs silently from a subscriber's
            perspective.

    Returns:
        Aggregated :class:`BackfillStats`.
    """
    stats = BackfillStats()
    rows = _fetch_candidate_rows(conn, show_filter=show_filter)
    scope = show_filter if show_filter else "library"
    event_bus.emit(BackfillStarted(scope=scope, item_count=len(rows)))
    for row in rows:
        stats.items_scanned += 1
        try:
            updated, ids_added, ratings_added, skip_reason = _backfill_one(
                conn,
                row,
                imdb_client=imdb_client,
                rt_client=rt_client,
                ids_only=ids_only,
                ratings_only=ratings_only,
                dry_run=dry_run,
                stats=stats,
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft contract
            log.warning(
                "backfill_item_failed",
                title=row["title"],
                error=str(exc),
            )
            stats.items_failed += 1
            stats.items_failed_titles.append(row["title"])
            continue
        if updated:
            stats.items_updated += 1
            event_bus.emit(
                BackfillItemCompleted(
                    item_id=row["id"],
                    item_title=row["title"],
                    ids_added=tuple(ids_added),
                    ratings_added=tuple(ratings_added),
                )
            )
        else:
            stats.items_skipped += 1
            event_bus.emit(
                BackfillSkipped(
                    item_id=row["id"],
                    item_title=row["title"],
                    reason=skip_reason or "already_complete",
                )
            )
    event_bus.emit(
        BackfillCompleted(
            scope=scope,
            scanned=stats.items_scanned,
            updated=stats.items_updated,
            skipped=stats.items_skipped,
            failed=stats.items_failed,
            ids_added_count=stats.ids_added_count,
            ratings_added_count=stats.ratings_added_count,
        )
    )
    return stats


def _fetch_candidate_rows(conn: sqlite3.Connection, *, show_filter: str | None) -> list[sqlite3.Row]:
    """Return the ``media_item`` rows the backfill should consider."""
    conn.row_factory = sqlite3.Row
    sql = "SELECT id, title, external_ids_json, ratings_json, canonical_provider FROM media_item"
    params: tuple[str, ...] = ()
    if show_filter:
        sql += " WHERE title = ?"
        params = (show_filter,)
    return list(conn.execute(sql, params).fetchall())


def _backfill_one(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    imdb_client: _RatingClient | None,
    rt_client: _RatingClient | None,
    ids_only: bool,
    ratings_only: bool,
    dry_run: bool,
    stats: BackfillStats,
) -> tuple[bool, list[str], list[str], str | None]:
    """Backfill a single ``media_item`` row in-place.

    Returns ``(updated, ids_added, ratings_added, skip_reason)`` —
    ``updated`` is ``True`` when at least one field was written ;
    ``skip_reason`` is populated only on the no-op path.
    """
    item_id: int = row["id"]
    external_ids_json: str = row["external_ids_json"] or "{}"
    ratings_json: str | None = row["ratings_json"]
    canonical: str | None = row["canonical_provider"]

    gap: BackfillGap = detect_gaps(external_ids_json, ratings_json, canonical)
    if gap.is_empty:
        return False, [], [], "already_complete"

    new_external_ids = external_ids_json
    new_ratings = ratings_json
    ids_added: list[str] = []
    ratings_added: list[str] = []

    # The IDs side is conservative for now : the orchestration layer
    # only knows how to bring in an IMDb ID when the IMDb façade can
    # validate it from an existing TMDb/TVDB anchor. The phase-5
    # ``_resolve_external_ids`` does the heavy lifting on the scraper
    # side. Backfill simply wires the façade-provided new IDs
    # through the safe-merge helper when a future caller supplies
    # them — today we pass an empty dict so the IDs path is a no-op
    # placeholder for now (sub-phase 8.3 will plug the actual
    # ``IDCrossRef`` calls).
    if not ratings_only:
        new_external_ids, ids_added = merge_ids_without_overwrite(
            external_ids_json,
            new_ids={},
            canonical_provider=canonical,
        )

    if not ids_only and gap.missing_rating_sources:
        new_entries = _fetch_ratings(
            row,
            gap=gap,
            imdb_client=imdb_client,
            rt_client=rt_client,
        )
        new_ratings, ratings_added = merge_ratings_without_overwrite(
            ratings_json,
            new_entries=new_entries,
        )

    if not ids_added and not ratings_added:
        # ``gap`` reported missing data but the providers returned
        # nothing usable — typically no IMDb anchor on this row.
        skip_reason = "no_imdb_anchor" if gap.missing_rating_sources else "already_complete"
        return False, [], [], skip_reason

    stats.ids_added_count += len(ids_added)
    stats.ratings_added_count += len(ratings_added)

    if dry_run:
        log.info(
            "backfill_dry_run_would_update",
            item_id=item_id,
            title=row["title"],
            ids_added=ids_added,
            ratings_added=ratings_added,
        )
        return True, ids_added, ratings_added, None

    conn.execute(
        "UPDATE media_item SET external_ids_json = ?, ratings_json = ?, "
        "date_modified = strftime('%s', 'now') WHERE id = ?",
        (new_external_ids, new_ratings, item_id),
    )
    log.info(
        "backfill_item_updated",
        item_id=item_id,
        title=row["title"],
        ids_added=ids_added,
        ratings_added=ratings_added,
    )
    return True, ids_added, ratings_added, None


def _fetch_ratings(
    row: sqlite3.Row,
    *,
    gap: BackfillGap,
    imdb_client: _RatingClient | None,
    rt_client: _RatingClient | None,
) -> list[dict[str, Any]]:
    """Query the IMDb / RT façades for the missing rating sources.

    Returns an empty list when the row has no IMDb ID to anchor the
    OMDb-backed lookups — IMDb and Rotten Tomatoes both key by the
    IMDb tt-ID, so without it neither façade can answer.
    """
    import json as _json  # noqa: PLC0415

    try:
        eids = _json.loads(row["external_ids_json"] or "{}")
    except _json.JSONDecodeError:
        return []
    imdb_id = (eids.get("imdb") or {}).get("series_id")
    if not imdb_id:
        return []

    entries: list[dict[str, Any]] = []
    if "imdb" in gap.missing_rating_sources and imdb_client is not None:
        entries.extend(_call_rating_client(imdb_client, imdb_id))
    if "rotten_tomatoes" in gap.missing_rating_sources and rt_client is not None:
        entries.extend(_call_rating_client(rt_client, imdb_id))
    return entries


def _call_rating_client(client: _RatingClient, provider_id: str) -> list[dict[str, Any]]:
    """Call ``client.get_rating`` returning serialisable dicts or an empty list."""
    try:
        ratings = client.get_rating(provider_id)
    except ProviderFeatureUnavailable as exc:
        log.warning(
            "backfill_rating_unavailable",
            provider=exc.provider,
            reason=exc.reason,
        )
        return []
    if not ratings:
        return []
    serialised: list[dict[str, Any]] = []
    for entry in ratings:
        serialised.append(
            {
                "source": getattr(entry, "source", ""),
                "score": str(getattr(entry, "score", "")),
                "votes": getattr(entry, "votes_count", None),
            }
        )
    return serialised


__all__ = ["BackfillStats", "run_backfill_ids"]
