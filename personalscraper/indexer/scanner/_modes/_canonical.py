"""Kind-deterministic canonical-provider SSOT.

The single source of truth for deriving ``canonical_provider`` from a
media item's kind and known provider IDs. Replaces both
``library.scanner._normalize_canonical_provider`` and the NFO-XML-order
fallback in ``backfill_ids_canonical._parse_canonical_from_nfo``.

Rule (§4.4 DESIGN; ports library.scanner._normalize_canonical_provider):
- show  + tvdb_id present              → ``"tvdb"``
- show  + no tvdb_id, tmdb_id present   → ``"tmdb"``
- movie + tmdb_id present               → ``"tmdb"``
- movie + tvdb_id only (no tmdb_id)     → ``None``   (anomaly kept NULL)
- no usable ID                          → ``None``

The NFO ``<uniqueid default="true">`` flag is intentionally ignored for
the derivation; we WARN when it disagrees (see §3.3).
"""

from __future__ import annotations

from personalscraper.logger import get_logger

log = get_logger("indexer.scanner.canonical")


def derive_canonical_provider(
    kind: str,
    tvdb_id: str | None,
    tmdb_id: str | None,
    nfo_default: str | None,
) -> str | None:
    """Derive the canonical provider using the kind-deterministic rule.

    Args:
        kind: ``"show"`` or ``"movie"`` (case-insensitive).
        tvdb_id: TVDB numeric ID as string, or ``None``.
        tmdb_id: TMDB numeric ID as string, or ``None``.
        nfo_default: The ``<uniqueid default="true">`` type from the NFO
            (maps to the legacy ``nfo_declared`` arg), or ``None``. Used
            only for a WARN when it contradicts the deterministic result.

    Returns:
        ``"tvdb"``, ``"tmdb"``, or ``None`` when no usable ID exists.
    """
    kind_lower = (kind or "").lower()

    result: str | None
    if kind_lower == "show":
        if tvdb_id:
            result = "tvdb"
        elif tmdb_id:
            result = "tmdb"
        else:
            result = None
    else:
        # movie and all other kinds — TMDB is canonical; a tvdb-only movie
        # is an anomaly kept NULL (parity with _normalize_canonical_provider).
        if tmdb_id:
            result = "tmdb"
        else:
            result = None

    # Warn when the NFO-declared default contradicts the deterministic rule
    # (parity with the legacy "library_canonical_provider_overridden" trail).
    if nfo_default and result is not None and nfo_default != result:
        log.warning(
            "indexer_canonical_provider_overridden",
            kind=kind,
            nfo_default=nfo_default,
            computed=result,
            tvdb_id=tvdb_id,
            tmdb_id=tmdb_id,
        )

    return result
