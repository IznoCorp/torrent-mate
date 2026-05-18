"""Tests for the ``external_ids_json`` + ``ratings_json`` Pydantic models.

Sub-phase 7.4 of the ``provider-ids`` feature. Round-trip tests
through ``model_dump_json`` / ``model_validate_json`` to confirm the
JSON shape matches the migration 005 column schema.
"""

from __future__ import annotations

import json

import pytest

from personalscraper.indexer.external_ids import (
    ExternalIds,
    ProviderIds,
    RatingEntry,
    Ratings,
)


def test_external_ids_round_trip_empty() -> None:
    """Default-constructed ``ExternalIds`` round-trips to ``{"tvdb": {}, ...}``.

    All three provider entries are present (defaults to empty
    :class:`ProviderIds`) but every ID field is ``None``. The wire
    shape preserves the keys so json_extract paths always succeed.
    """
    eids = ExternalIds()
    payload = eids.model_dump_json()
    parsed = json.loads(payload)
    assert set(parsed) == {"tvdb", "tmdb", "imdb"}
    for family in ("tvdb", "tmdb", "imdb"):
        assert parsed[family] == {"series_id": None, "episode_id": None}

    restored = ExternalIds.model_validate_json(payload)
    assert restored == eids


def test_external_ids_round_trip_populated() -> None:
    """Populated ``ExternalIds`` survives a JSON round-trip unchanged."""
    eids = ExternalIds(
        tvdb=ProviderIds(series_id="42", episode_id="9001"),
        tmdb=ProviderIds(series_id="100"),
        imdb=ProviderIds(series_id="tt0944947"),
    )
    payload = eids.model_dump_json()
    restored = ExternalIds.model_validate_json(payload)
    assert restored.tvdb.series_id == "42"
    assert restored.tvdb.episode_id == "9001"
    assert restored.tmdb.series_id == "100"
    assert restored.tmdb.episode_id is None
    assert restored.imdb.series_id == "tt0944947"


def test_ratings_round_trip_empty() -> None:
    """Default ``Ratings`` round-trips to ``{"entries": []}``."""
    ratings = Ratings()
    payload = ratings.model_dump_json()
    assert json.loads(payload) == {"entries": []}
    assert Ratings.model_validate_json(payload) == ratings


def test_ratings_round_trip_populated() -> None:
    """Populated ``Ratings`` keeps every entry through the JSON round-trip."""
    ratings = Ratings(
        entries=[
            RatingEntry(source="imdb", score="8.5/10", votes=1_000_000),
            RatingEntry(source="rotten_tomatoes", score="87%"),
            RatingEntry(source="themoviedb", score="8.2", votes=4_321),
        ]
    )
    payload = ratings.model_dump_json()
    restored = Ratings.model_validate_json(payload)
    assert len(restored.entries) == 3
    by_source = {entry.source: entry for entry in restored.entries}
    assert by_source["imdb"].score == "8.5/10"
    assert by_source["imdb"].votes == 1_000_000
    assert by_source["rotten_tomatoes"].score == "87%"
    assert by_source["rotten_tomatoes"].votes is None
    assert by_source["themoviedb"].votes == 4_321


def test_rating_entry_rejects_unknown_source() -> None:
    """An unknown ``source`` value triggers a Pydantic validation error.

    The literal type ensures the set of allowed sources stays in sync
    with the NFO writer (DESIGN §7) — a typo at the call site fails
    loud rather than silently producing an unreadable NFO.
    """
    with pytest.raises(ValueError):
        RatingEntry(source="unknown_source", score="0")  # type: ignore[arg-type]
