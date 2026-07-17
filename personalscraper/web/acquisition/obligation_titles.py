"""Obligation title resolution from ``acquire.db`` (E4 — titled obligations).

Extracted from ``web/routes/acquisition.py`` (module-size hard ceiling) —
behavior unchanged. See :func:`resolve_obligation_titles` for the resolution
order (join → dispatched_path basename → None) and the fail-soft contract.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.logger import get_logger
from personalscraper.web.models.acquisition import ObligationItem

logger = get_logger(__name__)


def resolve_obligation_titles(items: list[ObligationItem], conn: sqlite3.Connection) -> None:
    """Resolve each obligation's ``title`` from ``acquire.db``, fail-soft.

    Resolution order (ground-truth corrected 2026-07-17):

    1. **acquire.db join** (primary, case-insensitive): ``wanted.grabbed_hash`` =
       ``seed_obligation.info_hash`` → ``followed_series.title``, composed
       with the wanted row's scope:
         - episode (season + episode non-NULL) → ``"{title} S{ss:02d}E{ee:02d}"``
         - season pack (season only) → ``"{title} S{ss:02d}"``
         - bare → title verbatim

    2. **dispatched_path basename** (fallback): when the join misses and
       ``dispatched_path`` is set. Strips common video extensions (``.mkv``,
       ``.mp4``, ``.avi``) from file names; bare directory names verbatim.

    3. **None**: the frontend falls back to truncated ``info_hash``.

    Every row is individually guarded in both the composition loop and the
    apply pass — a single malformed row can never blank the whole listing.

    Args:
        items: The obligation items to enrich (mutated in-place).
        conn: An open ``acquire.db`` connection.
    """
    if not items:
        return

    # ── Step 1: acquire.db join ──────────────────────────────────────
    hashes = [it.info_hash for it in items]
    # Bind one placeholder per hash.
    placeholders = ",".join("?" for _ in hashes)
    title_map: dict[str, str] = {}
    try:
        rows = conn.execute(
            f"""
            SELECT DISTINCT so.info_hash, fs.title, w.season, w.episode
            FROM seed_obligation so
            JOIN wanted w ON lower(w.grabbed_hash) = lower(so.info_hash)
            JOIN followed_series fs ON w.followed_id = fs.id
            WHERE so.info_hash IN ({placeholders})
            """,
            hashes,
        ).fetchall()
    except sqlite3.Error:
        logger.warning("obligation_title_join_failed", exc_info=True)
        rows = []

    for row in rows:
        try:
            info_hash = row["info_hash"]
            title = row["title"]
            season = row["season"]
            episode = row["episode"]
            if season is not None and episode is not None:
                composed = f"{title} S{season:02d}E{episode:02d}"
            elif season is not None:
                composed = f"{title} S{season:02d}"
            else:
                composed = title
            # First match wins (DISTINCT + deterministic ordering not
            # guaranteed; on multiple wanted rows for the same hash the
            # first result is as good as any).
            if info_hash not in title_map:
                title_map[info_hash] = composed
        except Exception:
            # Safe extraction for logging — if the row is malformed we
            # may not even have a hash to report.
            hash_snippet = "?"
            try:
                hash_snippet = row["info_hash"][:12]
            except Exception:
                pass
            logger.warning(
                "obligation_title_composition_failed",
                info_hash=hash_snippet,
                exc_info=True,
            )

    # ── Step 2 & 3: apply to each item ───────────────────────────────
    for item in items:
        try:
            joined = title_map.get(item.info_hash)
            if joined is not None:
                item.title = joined
                continue
            if item.dispatched_path is not None:
                raw = Path(item.dispatched_path).name
                # Strip video extension from bare file names (directories
                # pass through unchanged — Path.name already has no ext).
                if raw.lower().endswith((".mkv", ".mp4", ".avi")):
                    raw = Path(raw).stem
                item.title = raw
                continue
            # Else: title stays None (frontend fallback to truncated hash).
        except Exception:
            logger.warning(
                "obligation_title_resolve_item_failed",
                info_hash=item.info_hash[:12],
                exc_info=True,
            )
            item.title = None
