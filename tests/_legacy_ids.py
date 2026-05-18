"""Test helper — build ``external_ids_json`` from legacy flat IDs.

Migration 005 (provider-ids feature) replaced the flat ``tmdb_id`` /
``imdb_id`` / ``tvdb_id`` columns on ``media_item`` with a single
hierarchical JSON column. Many test fixtures still express IDs in the
legacy form (``tmdb_id=99``) ; rather than rewrite every fixture
mechanically, the tests build the JSON string via this helper.

This module is **test-only** — production code constructs
``external_ids_json`` from the :class:`ExternalIds` Pydantic model
introduced in sub-phase 7.4 (DESIGN §6.5).
"""

from __future__ import annotations

import json


def legacy_external_ids_json(
    *,
    tmdb_id: int | str | None = None,
    imdb_id: str | None = None,
    tvdb_id: int | str | None = None,
) -> str:
    """Build ``external_ids_json`` content from the legacy flat IDs.

    Returns ``"{}"`` when every input is ``None`` — matches the
    ``NOT NULL DEFAULT '{}'`` column constraint set by migration 005.

    Args:
        tmdb_id: Optional TMDb series ID (int or string).
        imdb_id: Optional IMDb ``tt...`` identifier.
        tvdb_id: Optional TVDB numeric series ID.

    Returns:
        JSON string with the hierarchical shape
        ``{"<provider>": {"series_id": str, "episode_id": None}, ...}``.
    """
    obj: dict[str, dict[str, str | None]] = {}
    if tvdb_id is not None:
        obj["tvdb"] = {"series_id": str(tvdb_id), "episode_id": None}
    if tmdb_id is not None:
        obj["tmdb"] = {"series_id": str(tmdb_id), "episode_id": None}
    if imdb_id is not None:
        obj["imdb"] = {"series_id": str(imdb_id), "episode_id": None}
    return json.dumps(obj) if obj else "{}"


__all__ = ["legacy_external_ids_json"]
