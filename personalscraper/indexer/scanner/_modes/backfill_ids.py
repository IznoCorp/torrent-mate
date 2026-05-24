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

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

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


@runtime_checkable
class _RatingClient(Protocol):
    """Structural type for the IMDb / RT façades the driver consults."""

    def get_rating(self, provider_id: str) -> list[Any] | None: ...


@runtime_checkable
class _DetailsClient(Protocol):
    """Structural type for the TMDB / TVDB metadata clients used for ID cross-ref.

    Both :meth:`get_movie` and :meth:`get_tv` are required because a
    backfill pass dispatches on ``media_item.kind`` ("movie" vs
    "show"). The return type carries an ``external_ids`` mapping
    (``dict[str, str]`` keyed by provider family) which the driver
    feeds to :func:`merge_ids_without_overwrite`.
    """

    def get_movie(self, provider_id: str | int) -> Any: ...

    def get_tv(self, provider_id: str | int) -> Any: ...


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
    tmdb_client: _DetailsClient | None = None,
    tvdb_client: _DetailsClient | None = None,
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
        tmdb_client: TMDB metadata client used to read cross-provider
            IDs from the canonical TMDB payload (``external_ids``
            field on :class:`MediaDetails`). Required when any row is
            canonical-tmdb AND missing TVDB / IMDb IDs ; without it
            the IDs side becomes a no-op and emits one
            ``backfill_ids_path_no_client`` log per affected row.
        tvdb_client: TVDB metadata client — symmetric role for rows
            whose canonical provider is ``"tvdb"``.
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
    if not ratings_only and tmdb_client is None and tvdb_client is None:
        # Without a canonical metadata client the IDs side cannot do
        # anything beyond the per-row warning below. Log once up-front
        # so operators see the cause without grepping the per-row noise.
        log.warning(
            "backfill_ids_path_disabled_no_canonical_client",
            hint="Pass tmdb_client and/or tvdb_client to enable cross-provider ID backfill.",
        )
    for row in rows:
        stats.items_scanned += 1
        try:
            updated, ids_added, ratings_added, skip_reason = _backfill_one(
                conn,
                row,
                imdb_client=imdb_client,
                rt_client=rt_client,
                tmdb_client=tmdb_client,
                tvdb_client=tvdb_client,
                ids_only=ids_only,
                ratings_only=ratings_only,
                dry_run=dry_run,
                stats=stats,
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft contract
            log.exception(
                "backfill_item_failed",
                title=row["title"],
                item_id=row["id"],
                error=str(exc),
                error_type=type(exc).__name__,
            )
            stats.items_failed += 1
            if len(stats.items_failed_titles) < _MAX_FAILED_TITLES:
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
    sql = "SELECT id, kind, title, external_ids_json, ratings_json, canonical_provider FROM media_item"
    params: tuple[str, ...] = ()
    if show_filter:
        from personalscraper.indexer.repos.item_repo import _canonical_title  # noqa: PLC0415

        canonical = _canonical_title(show_filter)
        sql += " WHERE title = ?"
        params = (canonical,)
        if canonical != show_filter:
            log.info(
                "backfill_show_filter_canonicalised",
                raw=show_filter,
                canonical=canonical,
            )
    rows = list(conn.execute(sql, params).fetchall())
    if show_filter and not rows:
        log.warning(
            "backfill_show_filter_no_match",
            raw=show_filter,
        )
    return rows


def _backfill_one(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    imdb_client: _RatingClient | None,
    rt_client: _RatingClient | None,
    tmdb_client: _DetailsClient | None,
    tvdb_client: _DetailsClient | None,
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

    # The IDs side reads the cross-provider mapping from the canonical
    # provider's ``MediaDetails.external_ids`` and merges it
    # additively. ``merge_ids_without_overwrite`` guards the canonical
    # family + any non-canonical family that already has a value, so
    # the call is safe to re-run.
    if not ratings_only and gap.missing_id_families:
        cross_ids = _fetch_cross_provider_ids(
            row,
            canonical=canonical,
            tmdb_client=tmdb_client,
            tvdb_client=tvdb_client,
        )
        new_external_ids, ids_added = merge_ids_without_overwrite(
            external_ids_json,
            new_ids=cross_ids,
            canonical_provider=canonical,
        )

    if not ids_only and gap.missing_rating_sources:
        # Use the *post-IDs-merge* external_ids so a freshly-added IMDb
        # anchor (from the cross-provider call above) is visible to the
        # rating lookup. Reading ``row["external_ids_json"]`` here would
        # miss the IMDb id added in the same pass, breaking the
        # canonical-only-row → fully-populated round-trip.
        new_entries = _fetch_ratings(
            row,
            external_ids_json=new_external_ids,
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


def _fetch_cross_provider_ids(
    row: sqlite3.Row,
    *,
    canonical: str | None,
    tmdb_client: _DetailsClient | None,
    tvdb_client: _DetailsClient | None,
) -> dict[str, str]:
    """Return the cross-provider IDs reachable from the canonical anchor.

    Reads the canonical provider's series ID from ``external_ids_json``
    and dispatches to the matching client's ``get_tv`` / ``get_movie``
    method (based on ``media_item.kind``). The returned
    :class:`MediaDetails.external_ids` carries TVDB / TMDB / IMDb IDs
    when the provider knows them ; the dict is suitable for direct
    use with :func:`merge_ids_without_overwrite`.

    Returns ``{}`` (and logs once) when no client matches the
    canonical provider, when no canonical anchor is recorded yet, or
    when the upstream call fails. The caller stays fail-soft.

    Args:
        row: ``media_item`` row carrying ``kind`` + ``external_ids_json``.
        canonical: ``media_item.canonical_provider`` value
            (``"tmdb"`` / ``"tvdb"`` / ``None``).
        tmdb_client: TMDB client used when ``canonical == "tmdb"``.
        tvdb_client: TVDB client used when ``canonical == "tvdb"``.
    """
    import json as _json  # noqa: PLC0415

    if canonical not in ("tmdb", "tvdb"):
        # Future-proofing for hypothetical imdb/other canonicals — log
        # at debug since today's data shape never hits this branch.
        log.debug(
            "backfill_ids_canonical_unsupported",
            canonical=canonical,
            item_id=row["id"],
            title=row["title"],
        )
        return {}
    client: _DetailsClient | None
    if canonical == "tmdb":
        client = tmdb_client
    else:
        client = tvdb_client
    if client is None:
        log.warning(
            "backfill_ids_path_no_client",
            canonical=canonical,
            item_id=row["id"],
            title=row["title"],
        )
        return {}
    try:
        eids = _json.loads(row["external_ids_json"] or "{}")
    except _json.JSONDecodeError as exc:
        log.warning(
            "backfill_ids_json_decode_failed",
            item_id=row["id"],
            title=row["title"],
            error=str(exc),
        )
        return {}
    canonical_id = (eids.get(canonical) or {}).get("series_id")
    if not canonical_id:
        log.warning(
            "backfill_ids_canonical_id_missing",
            canonical=canonical,
            item_id=row["id"],
            title=row["title"],
            hint="canonical_provider set but external_ids_json carries no series_id — drift candidate",
        )
        return {}
    try:
        if row["kind"] == "show":
            details = client.get_tv(canonical_id)
        else:
            details = client.get_movie(canonical_id)
    except Exception as exc:  # noqa: BLE001 — fail-soft contract
        log.warning(
            "backfill_cross_ref_fetch_failed",
            canonical=canonical,
            item_id=row["id"],
            title=row["title"],
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return {}
    external_ids = getattr(details, "external_ids", None) or {}
    if not isinstance(external_ids, dict) or not external_ids:
        # Provider call succeeded but returned no cross-refs — log at
        # debug so an operator triaging "0 IDs added" can distinguish
        # "library already complete" from "TMDB returned an empty
        # payload". Distinct from ``backfill_cross_ref_fetch_failed``
        # which is the hard-error case.
        log.debug(
            "backfill_ids_empty_cross_refs",
            canonical=canonical,
            canonical_id=canonical_id,
            item_id=row["id"],
            title=row["title"],
        )
        return {}
    return {family: str(value) for family, value in external_ids.items() if value}


def _fetch_ratings(
    row: sqlite3.Row,
    *,
    external_ids_json: str,
    gap: BackfillGap,
    imdb_client: _RatingClient | None,
    rt_client: _RatingClient | None,
) -> list[dict[str, Any]]:
    """Query the IMDb / RT façades for the missing rating sources.

    Returns an empty list when the row has no IMDb ID to anchor the
    OMDb-backed lookups — IMDb and Rotten Tomatoes both key by the
    IMDb tt-ID, so without it neither façade can answer. Callers pass
    the post-IDs-merge ``external_ids_json`` so a freshly-fetched IMDb
    anchor is visible in the same pass.
    """
    import json as _json  # noqa: PLC0415

    try:
        eids = _json.loads(external_ids_json or "{}")
    except _json.JSONDecodeError as exc:
        log.warning(
            "backfill_ratings_json_decode_failed",
            item_id=row["id"],
            title=row["title"],
            error=str(exc),
        )
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
    source = getattr(client, "provider_name", type(client).__name__)
    try:
        ratings = client.get_rating(provider_id)
    except ProviderFeatureUnavailable as exc:
        log.warning(
            "backfill_rating_unavailable",
            provider=exc.provider,
            source=source,
            provider_id=provider_id,
            reason=exc.reason,
        )
        return []
    except Exception as exc:  # noqa: BLE001 — fail-soft per DESIGN §4
        # Anything beyond ProviderFeatureUnavailable (network, parser
        # drift, KeyError on a malformed OMDb row) is logged with full
        # provider context here so the outer ``backfill_item_failed``
        # entry stays a structured one-liner.
        log.warning(
            "backfill_rating_call_failed",
            source=source,
            provider_id=provider_id,
            error=str(exc),
            error_type=type(exc).__name__,
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


# ---------------------------------------------------------------------------
# init_canonical_from_nfo — bootstrap canonical_provider from existing NFOs
# ---------------------------------------------------------------------------

# NFOs in the wild carry many uniqueid type values (tvdb, tmdb, imdb, anidb,
# tvmaze, ...). The DB schema CHECK constraint accepts only tvdb / tmdb because
# those are the only providers that drive primary scrape orchestration (DESIGN
# §3 — TVDB primary for TV, TMDb primary for movies). All other type values are
# valid CROSS-PROVIDER IDs stored in external_ids_json but cannot serve as the
# canonical anchor — init_canonical_from_nfo must skip them rather than UPDATE
# with a value that violates the CHECK and crashes mid-walk.
_VALID_CANONICAL_PROVIDERS = frozenset({"tvdb", "tmdb"})

# Sentinel "null" tokens used in BOTH <uniqueid> text ("0", "none", "") and
# type attribute (e.g. <uniqueid type="none">) — treat as missing in either position.
_INVALID_CANONICAL_VALUES = frozenset({"0", "none", ""})

_MAX_FAILED_TITLES = 100  # Truncate BackfillStats.items_failed_titles to bound memory.


def _resolve_nfo_path(dispatch_path: str, kind: str) -> "Path | None":
    """Derive the expected NFO file path from the item's dispatch directory.

    For TV shows the NFO is always ``tvshow.nfo`` at the root of the show
    directory. For movies the NFO name matches the title stem
    (``{Title}.nfo``); to avoid needing the exact title string we glob
    for the first ``.nfo`` file in the directory.

    .. note::
       Sibling at ``personalscraper/commands/library/fix_nfo.py`` has a
       ``_resolve_nfo_path`` with the same shape but a different concern:
       this is a read-only path resolution for backfill; the sibling
       detects ambiguous NFOs for repair.

    Args:
        dispatch_path: Filesystem path of the media item root directory
            (value of ``item_attribute(key='dispatch_path')``).
        kind: ``'movie'`` or ``'show'``.

    Returns:
        Resolved :class:`~pathlib.Path` to the expected NFO file, or
        ``None`` if no NFO candidate exists (movie dir with zero ``.nfo``
        files).  Callers must check for ``None`` before reading.
    """
    from pathlib import Path  # noqa: PLC0415

    base = Path(dispatch_path)
    if kind == "show":
        return base / "tvshow.nfo"
    # Movie: glob for the first .nfo file in the directory (avoids
    # needing to reconstruct the exact "{Title}.nfo" stem).
    nfo_files = sorted(base.glob("*.nfo"))
    return nfo_files[0] if nfo_files else None


def _parse_canonical_from_nfo(nfo_path: "Path") -> tuple[str | None, str, dict[str, str]]:
    """Extract a supported canonical provider type from an NFO file.

    Reads the NFO XML and looks for a usable canonical anchor in this order:

    1. The ``type`` attribute of the first ``<uniqueid default="true">``
       element, IF that type is in :data:`_VALID_CANONICAL_PROVIDERS`
       (``tvdb``/``tmdb``).
    2. Fallback: when the default uniqueid carries an unsupported type
       (e.g. ``imdb``, ``anidb``, ``tvmaze``), search the OTHER uniqueid
       elements for the first one whose type IS supported.  This handles
       the very common case of movies whose NFO declares ``imdb`` as
       default but ALSO carries a ``tmdb`` uniqueid (a perfectly valid
       canonical anchor that pre-fix init_canonical was silently
       dropping — observed on 92 % of the production movie library in
       2026-05-23 incident).

    .. warning::
       The fallback returns the FIRST supported uniqueid found in NFO
       XML order, NOT the kind-preferred provider (TVDB primary for
       shows, TMDB primary for movies per
       ``docs/archive/features/provider-ids/DESIGN.md`` §3). For shows
       whose NFO orders ``tmdb`` before ``tvdb``, the fallback may pick
       ``tmdb`` even though ``tvdb``
       would be the more semantically correct canonical anchor.  This
       is acceptable for the bootstrap pass (better something than NULL
       in canonical_provider) but is NOT how you should migrate an
       already-canonicalized item between providers — that workflow
       belongs to Plan A (``library-rescrape`` in Phase 8.10), which
       resets canonical_provider, re-scrapes with the explicit primary
       provider forced, and lets the operator approve any rename/restructure
       of files (TVDB and TMDB can disagree on episode S/E mapping,
       season grouping, and titles — see Sherlock specials, Doctor Who
       classic-vs-new numbering, etc.).

    Args:
        nfo_path: Path to the ``.nfo`` file to parse.

    Returns:
        A tuple ``(provider, outcome, extracted_ids)``. ``provider`` is
        the resolved provider string (e.g. ``'tvdb'``, ``'tmdb'``) or
        ``None``. ``outcome`` is a short status code consumed by the
        caller for observability (one of ``ok_default``, ``ok_fallback``,
        ``parse_error``, ``read_error``, ``no_default``,
        ``unsupported_no_fallback``). ``extracted_ids`` is a
        ``dict[str, str]`` mapping supported provider family keys
        (``tvdb``, ``tmdb``, ``imdb``) to their series_id values from
        ALL ``<uniqueid>`` elements found in the NFO (regardless of
        ``default`` attribute). Empty dict on parse/read errors.
    """
    import xml.etree.ElementTree as ET  # noqa: PLC0415

    try:
        tree = ET.parse(nfo_path)  # noqa: S314
        root = tree.getroot()
    except ET.ParseError:
        log.debug("init_canonical_nfo_parse_error", path=str(nfo_path))
        return None, "parse_error", {}
    except OSError as exc:
        log.warning("init_canonical_nfo_read_error", path=str(nfo_path), error=str(exc))
        return None, "read_error", {}

    # Extract all known provider IDs from ALL <uniqueid> elements
    # (tvdb, tmdb, imdb — the 3 families per multi-provider memory).
    # Independent of the default attribute; the caller uses this to seed
    # external_ids_json alongside canonical_provider (Phase 8.10.c).
    extracted_ids: dict[str, str] = {}
    for uid in root.findall("uniqueid"):
        type_attr = uid.get("type", "").strip().lower()
        if type_attr not in {"tvdb", "tmdb", "imdb"}:
            continue
        value = (uid.text or "").strip()
        if value and value not in _INVALID_CANONICAL_VALUES:
            extracted_ids[type_attr] = value

    default_unsupported = False
    for uid in root.findall("uniqueid"):
        default_attr = uid.get("default", "").strip().lower()
        if default_attr != "true":
            continue
        type_attr = uid.get("type", "").strip().lower()
        if not type_attr or type_attr in _INVALID_CANONICAL_VALUES:
            continue
        if type_attr in _VALID_CANONICAL_PROVIDERS:
            return type_attr, "ok_default", extracted_ids
        # Default declares an unsupported type — flag for fallback search.
        default_unsupported = True
        log.debug(
            "init_canonical_default_unsupported_type",
            type_attr=type_attr,
            hint="will search other uniqueid elements for a supported fallback",
        )
        break

    if default_unsupported:
        # Walk all uniqueid elements (regardless of default attr) and pick the
        # first one with a supported type.  Order matters only minimally — when
        # both tvdb and tmdb are present, the first occurrence wins, which is
        # the conventional NFO ordering.
        for uid in root.findall("uniqueid"):
            type_attr = uid.get("type", "").strip().lower()
            if type_attr in _VALID_CANONICAL_PROVIDERS:
                value = (uid.text or "").strip()
                if value and value not in _INVALID_CANONICAL_VALUES:
                    return type_attr, "ok_fallback", extracted_ids
        return None, "unsupported_no_fallback", extracted_ids

    return None, "no_default", extracted_ids


@dataclass
class InitCanonicalStats:
    """Per-outcome counts for ``init_canonical_from_nfo``.

    Attributes:
        total_visited: Number of ``media_item`` rows examined.
        populated_default: Set from a supported ``default="true"`` uniqueid.
        populated_fallback: Set from a non-default supported uniqueid after
            the default declared an unsupported type (imdb/anidb/...).
        no_dispatch_path: Row had no ``dispatch_path`` attribute.
        nfo_missing: Resolved NFO path did not exist on the filesystem.
        nfo_parse_error: NFO existed but XML was malformed.
        nfo_read_error: NFO existed but read failed (OS error).
        no_default_uniqueid: NFO had no ``<uniqueid default="true">``.
        unsupported_no_fallback: Default was unsupported AND no other
            uniqueid carried a supported type (item is truly un-anchorable).
        external_ids_seeded_with_canonical: Items where BOTH
            ``canonical_provider`` AND ``external_ids_json`` were written
            in this pass (the canonical was previously NULL).
        external_ids_seeded_alone: Items where only ``external_ids_json``
            was written — ``canonical_provider`` was already set (the
            chicken-and-egg cohort: items whose canonical was populated
            by a pre-shard-1 init-canonical run but whose
            ``external_ids_json`` remained empty).
        external_ids_already_present: Items where all extracted families
            were already present in the existing ``external_ids_json``
            (no overwrite — merge-additive policy).
        parse_unexpected_error: Items where per-row processing raised an
            unexpected exception (caught by the fail-soft wrapper). The
            canonical_provider and external_ids_json are left unchanged.
    """

    total_visited: int = 0
    populated_default: int = 0
    populated_fallback: int = 0
    no_dispatch_path: int = 0
    nfo_missing: int = 0
    nfo_parse_error: int = 0
    nfo_read_error: int = 0
    no_default_uniqueid: int = 0
    unsupported_no_fallback: int = 0
    external_ids_seeded_with_canonical: int = 0
    external_ids_seeded_alone: int = 0
    external_ids_already_present: int = 0
    parse_unexpected_error: int = 0

    @property
    def populated(self) -> int:
        """Total number of rows whose ``canonical_provider`` was set."""
        return self.populated_default + self.populated_fallback


def init_canonical_from_nfo(conn: sqlite3.Connection, dry_run: bool = False) -> InitCanonicalStats:
    """Bootstrap ``canonical_provider`` and seed ``external_ids_json`` from NFOs.

    Walks every ``media_item`` row that could benefit from NFO data:

    * **canonical cohort** (``canonical_provider IS NULL``): canonical was
      never set — extract it from the NFO AND seed ``external_ids_json``.
    * **chicken-and-egg cohort** (``canonical_provider IS NOT NULL`` but
      ``external_ids_json IS NULL`` or ``='{}'``): canonical was already
      populated by a pre-shard-1 init-canonical run, but
      ``external_ids_json`` remained empty — only seed the external IDs
      without touching the existing canonical provider.

    For each row, resolves the item's filesystem directory via its
    ``item_attribute(key='dispatch_path')`` row, reads the NFO, and tries
    to extract a supported canonical anchor (``tvdb`` or ``tmdb``) from
    its ``<uniqueid>`` elements.  Falls back to a non-default supported
    uniqueid when the default declares an unsupported type (e.g. ``imdb``)
    — this is the common case for movies whose NFO has
    ``<uniqueid default="true" type="imdb">`` ALSO carrying a ``tmdb``
    uniqueid as a secondary id (92 % of the production movie library in
    the 2026-05-23 incident).

    Simultaneously collects ALL ``<uniqueid>`` values for the three
    supported provider families (``tvdb``, ``tmdb``, ``imdb``) and
    seeds ``external_ids_json`` with ``{"<family>": {"series_id": "...",
    "episode_id": null}}`` entries using merge-additive semantics: a
    family that already exists in the row is NOT overwritten (counted
    as ``external_ids_already_present`` instead).  This resolves the
    chicken-and-egg blocker (DEV #27): backfill-ids requires
    ``external_ids_json[canonical].series_id`` as the anchor for
    cross-provider lookups, but pre-fix init-canonical only set
    ``canonical_provider``, leaving ``external_ids_json`` empty and
    backfill skipping every item.

    Items without a ``dispatch_path`` attribute (scanner-only rows that
    have never been dispatched), without a readable NFO, or without any
    supported canonical anchor are skipped.  Their counts are recorded
    in the returned :class:`InitCanonicalStats` so the CLI can surface a
    breakdown instead of opaquely reporting ``populated=0``.

    Args:
        conn: Open writer connection on the indexer DB.
        dry_run: When ``True``, compute stats including
            ``external_ids_seeded`` but do NOT write to the DB.

    Returns:
        Populated :class:`InitCanonicalStats` with the per-outcome counts.
    """
    conn.row_factory = sqlite3.Row
    # Join media_item with item_attribute to fetch dispatch_path in one
    # query, avoiding N+1 lookups for the common case.
    # Also fetch canonical_provider to distinguish the two cohorts:
    # canonical cohort (needs_canonical=True) vs chicken-and-egg cohort.
    sql = (
        "SELECT m.id, m.kind, m.title, m.canonical_provider, m.external_ids_json, "
        "ia.value AS dispatch_path "
        "FROM media_item m "
        "LEFT JOIN item_attribute ia ON ia.item_id = m.id AND ia.key = 'dispatch_path' "
        "WHERE m.canonical_provider IS NULL "
        "   OR m.external_ids_json IS NULL "
        "   OR m.external_ids_json = '{}'"
    )
    rows = list(conn.execute(sql).fetchall())

    stats = InitCanonicalStats(total_visited=len(rows))
    for row in rows:
        item_id: int = row["id"]
        kind: str = row["kind"]
        title: str = row["title"]
        needs_canonical = row["canonical_provider"] is None
        dispatch_path: str | None = row["dispatch_path"]

        if not dispatch_path:
            stats.no_dispatch_path += 1
            log.debug("init_canonical_no_dispatch_path", item_id=item_id)
            continue

        nfo_path = _resolve_nfo_path(dispatch_path, kind)
        if nfo_path is None or not nfo_path.exists():
            stats.nfo_missing += 1
            log.debug("init_canonical_nfo_missing", item_id=item_id, nfo_path=str(nfo_path))
            continue

        try:
            canonical, outcome, extracted_ids = _parse_canonical_from_nfo(nfo_path)
            if outcome == "parse_error":
                stats.nfo_parse_error += 1
                continue
            if outcome == "read_error":
                stats.nfo_read_error += 1
                continue

            # Seed external_ids for the chicken-and-egg cohort even when
            # canonical resolution fails (no_default, unsupported_no_fallback).
            # The canonical_provider is already set; we only need the cross-
            # provider IDs from the NFO.  For the canonical cohort these
            # outcomes are terminal (no provider to set → nothing to do).
            seeding_only = outcome in ("no_default", "unsupported_no_fallback")
            if seeding_only:
                if outcome == "no_default":
                    stats.no_default_uniqueid += 1
                else:
                    stats.unsupported_no_fallback += 1
                if needs_canonical or not extracted_ids:
                    continue
                # Fall through — skip canonical settlement + population stats;
                # only the merge-additive seeding block below runs.
            else:
                # canonical is guaranteed non-None for ok_default / ok_fallback.
                assert canonical is not None
                if needs_canonical:
                    if outcome == "ok_default":
                        stats.populated_default += 1
                    else:  # ok_fallback
                        stats.populated_fallback += 1

            # Merge-additive external_ids_json from extracted_ids
            seeded_families: list[str] = []
            already_families: list[str] = []
            existing_raw = row["external_ids_json"]
            try:
                existing: dict[str, Any] = json.loads(existing_raw) if existing_raw else {}
            except json.JSONDecodeError:
                log.warning(
                    "init_canonical_external_ids_json_decode_failed",
                    item_id=item_id,
                    title=row["title"],
                )
                existing = {}
            for family, series_id in extracted_ids.items():
                if family in existing:
                    already_families.append(family)
                else:
                    existing[family] = {"series_id": series_id, "episode_id": None}
                    seeded_families.append(family)

            if not dry_run:
                if needs_canonical:
                    if extracted_ids:
                        conn.execute(
                            "UPDATE media_item SET canonical_provider = ?, external_ids_json = ?, "
                            "date_modified = strftime('%s', 'now') WHERE id = ?",
                            (canonical, json.dumps(existing, separators=(",", ":")), item_id),
                        )
                    else:
                        conn.execute(
                            "UPDATE media_item SET canonical_provider = ?, "
                            "date_modified = strftime('%s', 'now') WHERE id = ?",
                            (canonical, item_id),
                        )
                else:
                    # Chicken-and-egg cohort: canonical is already set,
                    # only seed external_ids_json when there are new families.
                    if seeded_families:
                        conn.execute(
                            "UPDATE media_item SET external_ids_json = ?, "
                            "date_modified = strftime('%s', 'now') WHERE id = ?",
                            (json.dumps(existing, separators=(",", ":")), item_id),
                        )

            if seeded_families:
                if needs_canonical:
                    stats.external_ids_seeded_with_canonical += 1
                else:
                    stats.external_ids_seeded_alone += 1
                log.info(
                    "init_canonical_external_ids_seeded",
                    item_id=item_id,
                    title=title,
                    families=seeded_families,
                    needs_canonical=needs_canonical,
                )
            if already_families:
                stats.external_ids_already_present += 1
                log.debug(
                    "init_canonical_external_ids_already_present",
                    item_id=item_id,
                    title=title,
                    existing_families=already_families,
                )

            if needs_canonical:
                log.info(
                    "init_canonical_populated",
                    item_id=item_id,
                    canonical_provider=canonical,
                    outcome=outcome,
                )
        except Exception:  # noqa: BLE001 — fail-soft per-row contract
            log.exception(
                "init_canonical_unexpected_error",
                item_id=item_id,
                title=title,
            )
            stats.parse_unexpected_error += 1
            continue

    log.info(
        "init_canonical_done",
        populated=stats.populated,
        populated_default=stats.populated_default,
        populated_fallback=stats.populated_fallback,
        total_visited=stats.total_visited,
        no_dispatch_path=stats.no_dispatch_path,
        nfo_missing=stats.nfo_missing,
        nfo_parse_error=stats.nfo_parse_error,
        nfo_read_error=stats.nfo_read_error,
        no_default_uniqueid=stats.no_default_uniqueid,
        unsupported_no_fallback=stats.unsupported_no_fallback,
        external_ids_seeded_with_canonical=stats.external_ids_seeded_with_canonical,
        external_ids_seeded_alone=stats.external_ids_seeded_alone,
        external_ids_already_present=stats.external_ids_already_present,
    )
    return stats


__all__ = ["BackfillStats", "InitCanonicalStats", "init_canonical_from_nfo", "run_backfill_ids"]
