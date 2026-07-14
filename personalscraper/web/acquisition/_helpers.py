"""Pure read-side helpers for the acquisition routes.

Extracted verbatim from ``web/routes/acquisition.py`` to keep that module under
the 1000-LOC ceiling: JSON column parsers, the pre-migration-tolerant row
reader, the indexer card-metadata backfill, and the cadence readout. No route
logic lives here — every function is a pure(ish) helper over rows/paths.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from personalscraper.acquire.cadence import Cadence, next_search_at, tier_name
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.web.models.acquisition import MediaRefResponse

logger = get_logger(__name__)


def _parse_media_ref(media_ref_json: str | None) -> MediaRefResponse:
    """Parse a ``media_ref_json`` column into a :class:`MediaRefResponse`.

    Args:
        media_ref_json: The raw JSON string from the DB, or ``None``.

    Returns:
        A ``MediaRefResponse`` with the parsed fields, or an empty one on
        parse failure / ``None``.
    """
    if not media_ref_json:
        return MediaRefResponse()
    try:
        data = json.loads(media_ref_json)
    except (json.JSONDecodeError, TypeError):
        return MediaRefResponse()
    return MediaRefResponse(
        tvdb_id=data.get("tvdb_id"),
        tmdb_id=data.get("tmdb_id"),
        imdb_id=data.get("imdb_id"),
    )


def _parse_json_dict(raw: str | None) -> dict[str, object] | None:
    """Parse a JSON text column into a dict, or ``None`` on failure.

    Args:
        raw: The raw JSON string from the DB, or ``None``.

    Returns:
        The parsed dict, or ``None``.
    """
    if not raw:
        return None
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def _row_col(row: sqlite3.Row, name: str) -> object | None:
    """Return a row column by name, or ``None`` when the column is absent.

    Tolerates a pre-migration ``followed_series`` (the OBJ3 metadata columns
    may not exist yet on the shared acquire.db until the first write applies
    migration 005) so a read never raises.

    Args:
        row: A ``sqlite3.Row``.
        name: The column name to read.

    Returns:
        The column value, or ``None`` when the column does not exist.
    """
    return row[name] if name in row.keys() else None


def _backfill_from_indexer(
    indexer_db_path: Path | None,
    tvdb_id: int | None,
    tmdb_id: int | None,
) -> tuple[int | None, int | None]:
    """Look up ``(year, season_count)`` for a followed series in the indexer.

    Matches a ``media_item`` (kind='show') by its TVDB or TMDB series id
    (``external_ids_json`` → ``$.<provider>.series_id``) and counts its seasons.
    Fail-soft: any error / no match yields ``(None, None)`` — the card simply
    shows less.

    Args:
        indexer_db_path: Absolute path to ``library.db``, or ``None``.
        tvdb_id: The followed series' TVDB id, or ``None``.
        tmdb_id: The followed series' TMDB id, or ``None``.

    Returns:
        ``(year, season_count)`` — either may be ``None``.
    """
    if indexer_db_path is None or not Path(indexer_db_path).exists():
        return None, None
    lookups: list[tuple[str, str]] = []
    if tvdb_id is not None:
        lookups.append(("$.tvdb.series_id", str(tvdb_id)))
    if tmdb_id is not None:
        lookups.append(("$.tmdb.series_id", str(tmdb_id)))
    if not lookups:
        return None, None
    try:
        with closing(sqlite3.connect(str(indexer_db_path))) as conn:
            apply_pragmas(conn)
            for path_expr, value in lookups:
                row = conn.execute(
                    "SELECT id, year FROM media_item "
                    "WHERE kind = 'show' AND json_extract(external_ids_json, ?) = ? LIMIT 1",
                    (path_expr, value),
                ).fetchone()
                if row is None:
                    continue
                item_id, year = row[0], row[1]
                season_count = conn.execute("SELECT COUNT(*) FROM season WHERE item_id = ?", (item_id,)).fetchone()[0]
                return year, season_count
    except sqlite3.Error:
        logger.warning("acquisition_indexer_backfill_failed", exc_info=True)
    return None, None


#: Temperature ranks used to pick a series' governing (hottest) tier.
_TIER_RANK: dict[str, int] = {"hot": 0, "warm": 1, "cold": 2, "cutoff": 3}


def _cadence_readout(
    timings: list[tuple[int, int | None]],
    cadence: Cadence,
    now: int,
) -> tuple[float | None, str | None]:
    """Derive a series' ``(next_search_at, cadence_tier)`` from its pending items.

    The next automatic search for the series is the soonest next-due among its
    pending wanted items; the reported tier is the hottest (most-active) tier
    across them. Past-cutoff items are ignored. Returns ``(None, None)`` when the
    series has no pending/searchable item (it is up to date).

    Args:
        timings: ``(enqueued_at, last_search_at)`` pairs for the series' pending
            wanted items.
        cadence: The effective cadence policy for the series.
        now: Current unix epoch seconds.

    Returns:
        A ``(next_search_at, cadence_tier)`` tuple, either element ``None``.
    """
    soonest: int | None = None
    best_tier: str | None = None
    best_rank = 99
    for enqueued_at, last_search_at in timings:
        due = next_search_at(cadence, now=now, enqueued_at=enqueued_at, last_search_at=last_search_at)
        if due is None:  # past cutoff — no longer searched
            continue
        if soonest is None or due < soonest:
            soonest = due
        tier = tier_name(cadence, now=now, enqueued_at=enqueued_at)
        rank = _TIER_RANK.get(tier, 99)
        if rank < best_rank:
            best_rank = rank
            best_tier = tier
    return (float(soonest) if soonest is not None else None, best_tier)
