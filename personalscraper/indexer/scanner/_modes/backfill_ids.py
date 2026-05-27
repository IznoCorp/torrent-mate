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

Provider dispatch is delegated to the :class:`ProviderRegistry`
(registry feature, DESIGN §6). The driver no longer accepts individual
typed clients: cross-provider ID lookups iterate
``registry.chain(MovieDetailsProvider | TvDetailsProvider)`` filtered
to the canonical provider name (DESIGN §3 — the canonical scrape owns
authority over its family; non-canonical chain peers cannot stand in
for the canonical provider here), and rating aggregation uses
``registry.fan_out(RatingProvider)`` (DESIGN §6.3).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api._helpers import ProviderFeatureUnavailable
from personalscraper.api.metadata._contracts import (
    MovieDetailsProvider,
    RatingProvider,
    TvDetailsProvider,
)
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

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import ProviderRegistry

log = get_logger("indexer.backfill_ids")


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
    registry: ProviderRegistry | None = None,
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
        event_bus: :class:`EventBus` used to publish
            ``BackfillStarted`` / ``BackfillItemCompleted`` /
            ``BackfillSkipped`` / ``BackfillCompleted`` events.
        registry: :class:`ProviderRegistry` from which the driver
            obtains rating providers (``fan_out(RatingProvider)``) and
            canonical details providers (``chain(MovieDetailsProvider)``
            / ``chain(TvDetailsProvider)``). ``None`` is accepted only
            for ``dry_run=True`` smoke paths where no provider call
            occurs; otherwise the IDs side becomes a no-op and the
            ratings side returns an empty list.
        show_filter: Restrict the pass to the show whose title equals
            this string. Useful for the post-scrape auto-trigger.
            The filter is normalised via ``_canonical_title`` (trailing
            `` (YYYY)`` suffix stripped) so it matches the canonical
            titles stored after migration 007.
        ids_only: When ``True``, do not fetch ratings.
        ratings_only: When ``True``, do not fetch IDs.
        dry_run: When ``True``, every DB write is rolled back.

    Returns:
        Aggregated :class:`BackfillStats`.
    """
    stats = BackfillStats()
    rows = _fetch_candidate_rows(conn, show_filter=show_filter)
    scope = show_filter if show_filter else "library"
    event_bus.emit(BackfillStarted(scope=scope, item_count=len(rows)))
    if not ratings_only and registry is None:
        # Without a registry the IDs side cannot do anything beyond the
        # per-row warning below. Log once up-front so operators see the
        # cause without grepping the per-row noise.
        log.warning(
            "backfill_ids_path_disabled_no_registry",
            hint="Pass registry=<ProviderRegistry> to enable cross-provider ID + rating backfill.",
        )
    from personalscraper.api.metadata.omdb import OmdbQuotaExhausted  # noqa: PLC0415

    # Local flag, not mutation of the function arguments — once OMDB
    # quota signals exhaustion, every subsequent row's rating fetch is
    # skipped without forcing the caller to reconstruct a registry.
    ratings_disabled = False

    for row in rows:
        stats.items_scanned += 1
        try:
            updated, ids_added, ratings_added, skip_reason = _backfill_one(
                conn,
                row,
                registry=registry,
                ratings_disabled=ratings_disabled,
                ids_only=ids_only,
                ratings_only=ratings_only,
                dry_run=dry_run,
                stats=stats,
            )
        except OmdbQuotaExhausted as exc:
            # OMDB daily budget gone — every subsequent row would hit
            # the same exception (one wasted HTTP per row for the
            # runtime-detected branch). Disable the rating side for the
            # remainder of the pass; the IDs side keeps going since it
            # uses TMDB/TVDB, not OMDB.
            log.warning(
                "backfill_ratings_disabled_quota_exhausted",
                pre_call=exc.pre_call,
                item_id=row["id"],
                title=row["title"],
            )
            ratings_disabled = True
            stats.items_skipped += 1
            event_bus.emit(
                BackfillSkipped(
                    item_id=row["id"],
                    item_title=row["title"],
                    reason="omdb_quota_exhausted",
                )
            )
            continue
        except (TypeError, AttributeError, KeyError):
            # Programmer-class exceptions indicate a refactor regression
            # (renamed dataclass field, deleted column, signature drift).
            # Fail-soft would mask the bug behind a per-row warning — let
            # it surface to handle_cli_errors instead.
            raise
        except Exception as exc:  # noqa: BLE001 — fail-soft contract per DESIGN §4
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
    registry: ProviderRegistry | None,
    ratings_disabled: bool,
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
            registry=registry,
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
            registry=None if ratings_disabled else registry,
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

    if dry_run:
        # dry_run reports expected effect without actual DB write.
        log.info(
            "backfill_dry_run_would_update",
            item_id=item_id,
            title=row["title"],
            ids_added=ids_added,
            ratings_added=ratings_added,
        )
        stats.ids_added_count += len(ids_added)
        stats.ratings_added_count += len(ratings_added)
        return True, ids_added, ratings_added, None

    conn.execute(
        "UPDATE media_item SET external_ids_json = ?, ratings_json = ?, "
        "date_modified = strftime('%s', 'now') WHERE id = ?",
        (new_external_ids, new_ratings, item_id),
    )
    # Counters reflect actual DB writes — incremented AFTER conn.execute
    # so stats are accurate on OperationalError (11.2, M3).
    stats.ids_added_count += len(ids_added)
    stats.ratings_added_count += len(ratings_added)
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
    registry: ProviderRegistry | None,
) -> dict[str, str]:
    """Return the cross-provider IDs reachable from the canonical anchor.

    Reads the canonical provider's series ID from ``external_ids_json``
    and routes the lookup through ``registry.chain()``: iterates the
    movie / TV details chain (depending on ``media_item.kind``),
    selects the provider whose ``provider_name`` matches ``canonical``,
    and calls its ``get_tv`` / ``get_movie`` method. The returned
    :class:`MediaDetails.external_ids` carries TVDB / TMDB / IMDb IDs
    when the provider knows them ; the dict is suitable for direct
    use with :func:`merge_ids_without_overwrite`.

    The canonical-name filter preserves DESIGN §3 "canonical's
    authority is absolute": non-canonical chain peers cannot stand in
    for the canonical provider here — falling back to a peer would
    create cross-contamination. Per-provider failures
    (CircuitOpenError, network) emit ``ProviderFallbackTriggered`` and
    return ``{}``; full chain exhaustion (the canonical provider not
    eligible) emits ``ProviderExhaustedEvent``.

    Returns ``{}`` (and logs once) when no chain provider matches the
    canonical, when no canonical anchor is recorded yet, or when the
    upstream call fails. The caller stays fail-soft.

    Args:
        row: ``media_item`` row carrying ``kind`` + ``external_ids_json``.
        canonical: ``media_item.canonical_provider`` value
            (``"tmdb"`` / ``"tvdb"`` / ``None``).
        registry: Provider registry to source the canonical details
            client from. ``None`` short-circuits to ``{}`` after a
            single warning (mirrors the legacy "no client passed"
            branch).
    """
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
    if registry is None:
        log.warning(
            "backfill_ids_path_no_registry",
            canonical=canonical,
            item_id=row["id"],
            title=row["title"],
        )
        return {}
    try:
        eids = json.loads(row["external_ids_json"] or "{}")
    except json.JSONDecodeError as exc:
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

    # Resolve the chain capability based on the row's kind. The
    # canonical-name filter preserves DESIGN §3: only the canonical
    # provider's details are authoritative for the cross-refs lookup.
    is_show = row["kind"] == "show"
    capability_name: str
    providers: list[Any]
    if is_show:
        providers = list(registry.chain(TvDetailsProvider))  # type: ignore[type-abstract]
        capability_name = "TvDetailsProvider"
    else:
        providers = list(registry.chain(MovieDetailsProvider))  # type: ignore[type-abstract]
        capability_name = "MovieDetailsProvider"

    item_context: dict[str, Any] = {
        "title": row["title"],
        "kind": row["kind"],
        "item_id": row["id"],
    }
    canonical_match: Any = None
    for provider in providers:
        if getattr(provider, "provider_name", None) == canonical:
            canonical_match = provider
            break

    if canonical_match is None:
        # The canonical provider is either absent from the chain
        # (registry config doesn't list it under this capability) or
        # filtered out by the circuit breaker (CIRCUIT_OPEN). The
        # legacy "client is None" branch logged a warning — match
        # that behaviour and emit an exhausted event for observers.
        log.warning(
            "backfill_ids_canonical_not_in_chain",
            canonical=canonical,
            capability=capability_name,
            item_id=row["id"],
            title=row["title"],
        )
        registry._emit_provider_exhausted(  # noqa: SLF001 — chain-iteration site
            capability=capability_name,
            attempted=[],
            item=item_context,
        )
        return {}

    try:
        if is_show:
            details = canonical_match.get_tv(canonical_id)
        else:
            details = canonical_match.get_movie(canonical_id)
    except CircuitOpenError:
        registry._emit_provider_fallback(  # noqa: SLF001
            capability=capability_name,
            from_provider=canonical,
            reason="circuit_open",
            item=item_context,
        )
        log.debug(
            "registry_provider_skip",
            provider=canonical,
            capability=capability_name,
            reason="circuit_open",
        )
        registry._emit_provider_exhausted(  # noqa: SLF001
            capability=capability_name,
            attempted=[],
            item=item_context,
        )
        return {}
    except (ApiError, requests.RequestException, OSError) as exc:
        registry._emit_provider_fallback(  # noqa: SLF001
            capability=capability_name,
            from_provider=canonical,
            reason="network",
            exc_type=type(exc).__name__,
            item=item_context,
        )
        log.warning(
            "backfill_cross_ref_fetch_failed",
            canonical=canonical,
            item_id=row["id"],
            title=row["title"],
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return {}
    except (TypeError, AttributeError, KeyError):
        # Programmer-class — let it surface (signature drift, renamed
        # field on the response model). The fail-soft handler above is
        # for transport / parse failures, not refactor regressions.
        raise
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
        registry._emit_provider_fallback(  # noqa: SLF001
            capability=capability_name,
            from_provider=canonical,
            reason="empty_result",
            item=item_context,
        )
        return {}
    return {family: str(value) for family, value in external_ids.items() if value}


def _fetch_ratings(
    row: sqlite3.Row,
    *,
    external_ids_json: str,
    gap: BackfillGap,
    registry: ProviderRegistry | None,
) -> list[dict[str, Any]]:
    """Query rating providers via ``registry.fan_out`` for missing sources.

    Returns an empty list when the row has no IMDb ID to anchor the
    rating lookups — IMDb and Rotten Tomatoes both key by the IMDb
    tt-ID, so without it neither façade can answer. Callers pass the
    post-IDs-merge ``external_ids_json`` so a freshly-fetched IMDb
    anchor is visible in the same pass.

    Iterates ``registry.fan_out(RatingProvider).values`` (DESIGN §6.3)
    in priority order. Each provider whose ``provider_name`` matches a
    source in ``gap.missing_rating_sources`` is queried with the IMDb
    anchor; the returned :class:`Notations` rows are serialised to
    dicts suitable for :func:`merge_ratings_without_overwrite`. The
    merge layer dedupes by ``source`` so providers that surface
    multiple sources (the OMDb façades each surface their own source)
    compose without duplication.

    Args:
        row: ``media_item`` row used only for log context.
        external_ids_json: Post-IDs-merge external IDs payload — read
            to extract the IMDb anchor.
        gap: Detected gap; used to filter eligible providers by
            ``source`` and to short-circuit when no rating source is
            missing.
        registry: :class:`ProviderRegistry`. ``None`` (when
            ``ratings_disabled`` is set or no registry was passed)
            short-circuits to ``[]``.

    Returns:
        Serialised rating entries (dicts), one per provider call that
        returned at least one notation.
    """
    if registry is None:
        return []
    try:
        eids = json.loads(external_ids_json or "{}")
    except json.JSONDecodeError as exc:
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

    fan_out_result = registry.fan_out(RatingProvider)  # type: ignore[type-abstract]
    entries: list[dict[str, Any]] = []
    for provider in fan_out_result.values:
        source = getattr(provider, "provider_name", type(provider).__name__)
        if source not in gap.missing_rating_sources:
            continue
        entries.extend(_call_rating_provider(provider, imdb_id, source))
    return entries


def _call_rating_provider(provider: RatingProvider, provider_id: str, source: str) -> list[dict[str, Any]]:
    """Call ``provider.get_rating`` returning serialisable dicts or an empty list.

    Args:
        provider: A :class:`RatingProvider` instance obtained from
            ``registry.fan_out(RatingProvider)``.
        provider_id: The IMDb tt-ID used as anchor for OMDb-backed
            façades.
        source: The provider's ``provider_name`` (cached by the caller
            to avoid the attribute lookup twice).

    Raises:
        OmdbQuotaExhausted: Propagated unchanged so the outer loop can
            disable the rating side for the remainder of the pass
            instead of swallowing one-quota-error-per-remaining-row.
    """
    from personalscraper.api.metadata.omdb import OmdbQuotaExhausted  # noqa: PLC0415

    try:
        ratings = provider.get_rating(provider_id)
    except OmdbQuotaExhausted:
        raise
    except ProviderFeatureUnavailable as exc:
        log.warning(
            "backfill_rating_unavailable",
            provider=exc.provider,
            source=source,
            provider_id=provider_id,
            reason=exc.reason,
        )
        return []
    except CircuitOpenError:
        # Circuit breaker tripped between fan_out eligibility check
        # and call — count as an empty rating contribution, no raise.
        log.debug(
            "backfill_rating_circuit_open",
            source=source,
            provider_id=provider_id,
        )
        return []
    except (TypeError, AttributeError):
        # Programmer-class — let signature drift / refactor regressions
        # surface. KeyError is intentionally NOT in this list because a
        # malformed OMDb payload can produce one and that IS the
        # transport-shape failure the broad except is for.
        raise
    except Exception as exc:  # noqa: BLE001 — fail-soft per DESIGN §4
        # Anything beyond ProviderFeatureUnavailable / programmer bugs
        # (network, parser drift, KeyError on a malformed OMDb row) is
        # logged with full provider context here so the outer
        # ``backfill_item_failed`` entry stays a structured one-liner.
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
    (``{Title}.nfo``); we glob via
    :func:`personalscraper.nfo_utils.glob_nfo_candidates` (which skips
    macOS AppleDouble ``._`` sidecars — without that filter the resolver
    could pick a stale ``._<title>.nfo`` binary blob on NTFS volumes and
    fail every downstream XML parse).

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

    from personalscraper.nfo_utils import glob_nfo_candidates  # noqa: PLC0415

    base = Path(dispatch_path)
    if kind == "show":
        return base / "tvshow.nfo"
    nfo_files = glob_nfo_candidates(base)
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
            # Classification counters reflect NFO content analysis, not DB
            # writes — incremented before conn.execute by design (11.2, M2).
            seeding_only = outcome in ("no_default", "unsupported_no_fallback")
            if seeding_only:
                if outcome == "no_default":
                    stats.no_default_uniqueid += 1
                else:
                    stats.unsupported_no_fallback += 1
                if needs_canonical or not extracted_ids:
                    continue
                # Skip the else-branch (canonical settlement + population
                # stats) and proceed straight to the merge-additive
                # seeding block below.
            else:
                # canonical is guaranteed non-None for ok_default / ok_fallback.
                assert canonical is not None
                # populated_default / populated_fallback incremented AFTER
                # conn.execute below (11.2, M2) — counters reflect actual DB writes.

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

            # populated_default / populated_fallback reflect actual DB writes
            # (or expected effect for dry_run). Incremented AFTER conn.execute
            # so stats are accurate on OperationalError (11.2, M2).
            if not seeding_only and needs_canonical:
                if outcome == "ok_default":
                    stats.populated_default += 1
                else:  # ok_fallback
                    stats.populated_fallback += 1

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
        parse_unexpected_error=stats.parse_unexpected_error,
    )
    return stats


__all__ = ["BackfillStats", "InitCanonicalStats", "init_canonical_from_nfo", "run_backfill_ids"]
