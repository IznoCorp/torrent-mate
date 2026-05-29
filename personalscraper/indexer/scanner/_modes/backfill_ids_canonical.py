"""Canonical-provider bootstrap from existing NFO files.

Extracted from :mod:`personalscraper.indexer.scanner._modes.backfill_ids`
in Phase 18 to bring the parent module below the 1000 non-blank LOC hard
ceiling (``scripts/check-module-size.py``).

The :func:`init_canonical_from_nfo` driver walks ``media_item`` rows that
need a canonical provider or external-ids seeding, reads each row's NFO,
and extracts:

* a supported canonical anchor (``tvdb`` / ``tmdb``) from
  ``<uniqueid default="true">``, falling back to any other supported
  ``<uniqueid>`` when the default declares an unsupported type
  (``imdb`` / ``anidb`` / ``tvmaze`` / ...);
* every ``<uniqueid>`` value for the three supported families
  (``tvdb``, ``tmdb``, ``imdb``) to seed ``external_ids_json`` using
  merge-additive semantics.

The original module re-exports every symbol below so existing imports
(``from personalscraper.indexer.scanner._modes.backfill_ids import
init_canonical_from_nfo`` / ``InitCanonicalStats`` / ``_resolve_nfo_path``
/ ``_parse_canonical_from_nfo``) keep working unchanged.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger("indexer.backfill_ids")


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
            # Indirect lookup via the ``backfill_ids`` module so existing
            # tests that monkeypatch the re-exported symbol
            # (``personalscraper.indexer.scanner._modes.backfill_ids._parse_canonical_from_nfo``)
            # keep intercepting the call after the Phase 18 extraction.
            from personalscraper.indexer.scanner._modes import backfill_ids as _bf  # noqa: PLC0415

            canonical, outcome, extracted_ids = _bf._parse_canonical_from_nfo(nfo_path)
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


__all__ = [
    "InitCanonicalStats",
    "_INVALID_CANONICAL_VALUES",
    "_VALID_CANONICAL_PROVIDERS",
    "_parse_canonical_from_nfo",
    "_resolve_nfo_path",
    "init_canonical_from_nfo",
]
