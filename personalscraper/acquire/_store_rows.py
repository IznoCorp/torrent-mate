"""Row → frozen domain converters for the acquire store (extracted for module size).

Pure ``sqlite3.Row`` → value-object mappers + MediaRef JSON (de)serialization,
split out of ``store.py`` so that module stays under the 1000-LOC ceiling.
No store/connection coupling — safe to import from any acquire store module.
"""

from __future__ import annotations

import json
import sqlite3
from typing import cast

from personalscraper.acquire.domain import (
    FollowedSeries,
    RatioState,
    SeedObligation,
    WantedItem,
    WantedKind,
    WantedStatus,
)
from personalscraper.core.identity import MediaRef


def _media_ref_to_json(ref: MediaRef) -> str:
    """Serialize a :class:`MediaRef` to a compact JSON string.

    Args:
        ref: The provider-ID value object.

    Returns:
        A JSON object string with ``tvdb_id`` / ``tmdb_id`` / ``imdb_id`` keys.
    """
    return json.dumps({"tvdb_id": ref.tvdb_id, "tmdb_id": ref.tmdb_id, "imdb_id": ref.imdb_id})


def _media_ref_from_json(blob: str) -> MediaRef:
    """Deserialize a :class:`MediaRef` from its JSON string.

    Args:
        blob: A JSON object string produced by :func:`_media_ref_to_json`.

    Returns:
        The reconstructed :class:`MediaRef`.
    """
    data = json.loads(blob)
    return MediaRef(
        tvdb_id=data.get("tvdb_id"),
        tmdb_id=data.get("tmdb_id"),
        imdb_id=data.get("imdb_id"),
    )


def _row_to_followed(row: sqlite3.Row) -> FollowedSeries:
    """Map a ``followed_series`` row to a :class:`FollowedSeries`.

    Args:
        row: A :class:`sqlite3.Row` from a ``followed_series`` SELECT.
            Must include the ``id`` column.

    Returns:
        The frozen :class:`FollowedSeries` value object with ``id`` set.
    """
    return FollowedSeries(
        id=row["id"],
        media_ref=_media_ref_from_json(row["media_ref_json"]),
        title=row["title"],
        added_at=row["added_at"],
        active=bool(row["active"]),
        quality_profile_json=row["quality_profile_json"],
        cadence_json=row["cadence_json"],
    )


def _row_to_wanted(row: sqlite3.Row) -> WantedItem:
    """Map a ``wanted`` row to a :class:`WantedItem`.

    Args:
        row: A :class:`sqlite3.Row` from a ``wanted`` SELECT.

    Returns:
        The frozen :class:`WantedItem` value object.
    """
    return WantedItem(
        media_ref=_media_ref_from_json(row["media_ref_json"]),
        # kind/status are CHECK-constrained columns; cast the raw string to the
        # Literal alias (WantedItem.__post_init__ re-validates at construction).
        kind=cast(WantedKind, row["kind"]),
        status=cast(WantedStatus, row["status"]),
        enqueued_at=row["enqueued_at"],
        followed_id=row["followed_id"],
        season=row["season"],
        episode=row["episode"],
        criteria_json=row["criteria_json"],
        last_search_at=row["last_search_at"],
        attempts=row["attempts"],
        id=row["id"],
        grabbed_hash=row["grabbed_hash"],
    )


def _row_to_seed(row: sqlite3.Row) -> SeedObligation:
    """Map a ``seed_obligation`` row to a :class:`SeedObligation`.

    Args:
        row: A :class:`sqlite3.Row` from a ``seed_obligation`` SELECT.

    Returns:
        The frozen :class:`SeedObligation` value object.
    """
    return SeedObligation(
        info_hash=row["info_hash"],
        source_tracker=row["source_tracker"],
        min_seed_time_s=row["min_seed_time_s"],
        min_ratio=row["min_ratio"],
        added_at=row["added_at"],
        dispatched_path=row["dispatched_path"],
        satisfied_at=row["satisfied_at"],
        breached_at=row["breached_at"],
        released_at=row["released_at"],
    )


def _row_to_ratio(row: sqlite3.Row) -> RatioState:
    """Map a ``ratio_state`` row to a :class:`RatioState`.

    Args:
        row: A :class:`sqlite3.Row` from a ``ratio_state`` SELECT.

    Returns:
        The frozen :class:`RatioState` value object.
    """
    return RatioState(
        tracker_name=row["tracker_name"],
        observed_ratio=row["observed_ratio"],
        accumulated_seed_time_s=row["accumulated_seed_time_s"],
        hnr_count=row["hnr_count"],
        updated_at=row["updated_at"],
    )
