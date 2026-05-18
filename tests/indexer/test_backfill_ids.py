"""Tests for the provider-IDs backfill helpers (phase 8.1).

The helpers are pure functions — gap detection + safe-merge — that
the future scanner driver (sub-phase 8.2) will call once per row.
These tests pin the no-overwrite + no-cross-contamination invariants
that DESIGN §3 demands.
"""

from __future__ import annotations

import json

from personalscraper.indexer.backfill_ids import (
    detect_gaps,
    merge_ids_without_overwrite,
    merge_ratings_without_overwrite,
)

# ---------------------------------------------------------------------------
# detect_gaps
# ---------------------------------------------------------------------------


def test_detect_gaps_empty_row_returns_two_non_canonical_families() -> None:
    """A row with an empty ``external_ids_json`` flags the two non-canonical families.

    A TVDB-canonical row whose JSON is ``"{}"`` is still missing
    its TMDb + IMDb IDs — the backfill should fetch both.
    """
    gap = detect_gaps("{}", None, canonical_provider="tvdb")
    assert gap.missing_id_families == ("tmdb", "imdb")
    assert "imdb" in gap.missing_rating_sources
    assert "rotten_tomatoes" in gap.missing_rating_sources


def test_detect_gaps_omits_canonical_family() -> None:
    """Canonical family is never reported as a gap even if its ID is missing.

    The canonical scrape's authority is absolute — a missing canonical
    ID means the row needs a re-scrape, not a backfill. The backfill
    therefore never touches the canonical slot.
    """
    payload = json.dumps({"tmdb": {"series_id": "5005"}, "imdb": {"series_id": "tt0001"}})
    gap = detect_gaps(payload, None, canonical_provider="tvdb")
    assert "tvdb" not in gap.missing_id_families


def test_detect_gaps_returns_empty_when_full_population() -> None:
    """Fully-populated row → ``is_empty`` is ``True`` (no work to do)."""
    eids = json.dumps(
        {
            "tvdb": {"series_id": "9001"},
            "tmdb": {"series_id": "5005"},
            "imdb": {"series_id": "tt0001"},
        }
    )
    ratings = json.dumps(
        {
            "entries": [
                {"source": "imdb", "score": "8.5/10", "votes": 10},
                {"source": "rotten_tomatoes", "score": "91%", "votes": 0},
            ]
        }
    )
    gap = detect_gaps(eids, ratings, canonical_provider="tvdb")
    assert gap.is_empty


def test_detect_gaps_handles_missing_canonical_marker() -> None:
    """No ``canonical_provider`` → every family with a missing ID is reported."""
    gap = detect_gaps("{}", None, canonical_provider=None)
    assert set(gap.missing_id_families) == {"tvdb", "tmdb", "imdb"}


def test_detect_gaps_handles_malformed_json() -> None:
    """Malformed JSON falls back to "everything missing" rather than raising."""
    gap = detect_gaps("not json", "<broken>", canonical_provider="tvdb")
    # Same as empty payload.
    assert gap.missing_id_families == ("tmdb", "imdb")


# ---------------------------------------------------------------------------
# merge_ids_without_overwrite
# ---------------------------------------------------------------------------


def test_merge_ids_fills_missing_family() -> None:
    """An empty payload accepts the new IDs."""
    payload, added = merge_ids_without_overwrite(
        "{}",
        new_ids={"tmdb": "5005", "imdb": "tt0001"},
        canonical_provider="tvdb",
    )
    eids = json.loads(payload)
    assert eids["tmdb"]["series_id"] == "5005"
    assert eids["imdb"]["series_id"] == "tt0001"
    assert sorted(added) == ["imdb", "tmdb"]


def test_merge_ids_refuses_to_overwrite_canonical_family() -> None:
    """Canonical family is never replaced even when ``new_ids`` carries a value."""
    original = json.dumps({"tvdb": {"series_id": "9001"}})
    payload, added = merge_ids_without_overwrite(
        original,
        new_ids={"tvdb": "9999", "imdb": "tt0001"},
        canonical_provider="tvdb",
    )
    eids = json.loads(payload)
    assert eids["tvdb"]["series_id"] == "9001"  # untouched
    assert "tvdb" not in added
    assert "imdb" in added


def test_merge_ids_refuses_to_overwrite_existing_non_canonical() -> None:
    """A non-canonical family already populated is preserved."""
    original = json.dumps({"tmdb": {"series_id": "5005"}})
    payload, added = merge_ids_without_overwrite(
        original,
        new_ids={"tmdb": "9999"},
        canonical_provider="tvdb",
    )
    eids = json.loads(payload)
    assert eids["tmdb"]["series_id"] == "5005"
    assert added == []


def test_merge_ids_skips_empty_values() -> None:
    """Falsy / empty IDs are ignored — no empty rows leak into the JSON."""
    payload, added = merge_ids_without_overwrite(
        "{}",
        new_ids={"tmdb": "", "imdb": None},  # type: ignore[dict-item]
        canonical_provider="tvdb",
    )
    assert added == []
    assert json.loads(payload) == {}


# ---------------------------------------------------------------------------
# merge_ratings_without_overwrite
# ---------------------------------------------------------------------------


def test_merge_ratings_appends_missing_sources() -> None:
    """Sources not yet present land in the ``entries`` list."""
    payload, added = merge_ratings_without_overwrite(
        None,
        new_entries=[
            {"source": "imdb", "score": "8.5/10", "votes": 10},
            {"source": "rotten_tomatoes", "score": "91%", "votes": 0},
        ],
    )
    ratings = json.loads(payload)
    sources = sorted(e["source"] for e in ratings["entries"])
    assert sources == ["imdb", "rotten_tomatoes"]
    assert sorted(added) == ["imdb", "rotten_tomatoes"]


def test_merge_ratings_refuses_to_overwrite_existing_source() -> None:
    """An incoming row whose source is already present is silently skipped."""
    existing = json.dumps({"entries": [{"source": "imdb", "score": "8.5/10", "votes": 10}]})
    payload, added = merge_ratings_without_overwrite(
        existing,
        new_entries=[{"source": "imdb", "score": "9.9/10", "votes": 999}],  # would-be overwrite
    )
    ratings = json.loads(payload)
    assert len(ratings["entries"]) == 1
    assert ratings["entries"][0]["score"] == "8.5/10"  # untouched
    assert added == []


def test_merge_ratings_idempotent_on_second_pass() -> None:
    """Running the merge twice with the same payload yields no further changes."""
    entries = [{"source": "imdb", "score": "8.5/10", "votes": 10}]
    payload_v1, _ = merge_ratings_without_overwrite(None, new_entries=entries)
    payload_v2, added_v2 = merge_ratings_without_overwrite(payload_v1, new_entries=entries)
    assert json.loads(payload_v1) == json.loads(payload_v2)
    assert added_v2 == []
