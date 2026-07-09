"""Tests for the DecisionCandidate Pydantic model (scrape-arbiter feature).

Covers round-trip serialization, nullable fields, and type validation
rejection of invalid provider literals.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from personalscraper.scraper.decision_candidate import DecisionCandidate


class TestDecisionCandidateRoundTrip:
    """Round-trip serialization: model_dump → model_validate round-trips faithfully."""

    def test_round_trip_full(self) -> None:
        """All fields populated → dump → validate produces an equal model."""
        original = DecisionCandidate(
            provider="tmdb",
            provider_id=27205,
            title="Inception",
            year=2010,
            score=0.92,
            poster_url="https://image.tmdb.org/t/p/w500/abc123.jpg",
            overview="A thief who steals corporate secrets through dream-sharing.",
        )
        dumped = original.model_dump()
        restored = DecisionCandidate.model_validate(dumped)
        assert restored == original
        assert restored.provider == "tmdb"
        assert restored.provider_id == 27205
        assert restored.title == "Inception"
        assert restored.year == 2010
        assert restored.score == 0.92
        assert restored.poster_url == "https://image.tmdb.org/t/p/w500/abc123.jpg"

    def test_json_round_trip(self) -> None:
        """model_dump_json → model_validate_json preserves all fields."""
        original = DecisionCandidate(
            provider="tvdb",
            provider_id=78901,
            title="Breaking Bad",
            year=2008,
            score=0.78,
        )
        json_str = original.model_dump_json()
        restored = DecisionCandidate.model_validate_json(json_str)
        assert restored == original


class TestDecisionCandidateNullables:
    """Nullable fields (year, poster_url, overview) accept None and omit from defaults."""

    def test_minimal_fields_only(self) -> None:
        """Only required fields populated; optionals default to None."""
        candidate = DecisionCandidate(
            provider="tmdb",
            provider_id=42,
            title="Minimal",
            score=0.55,
        )
        assert candidate.year is None
        assert candidate.poster_url is None
        assert candidate.overview is None

    def test_year_none_explicit(self) -> None:
        """Explicit None for year is accepted and round-trips."""
        candidate = DecisionCandidate(
            provider="tvdb",
            provider_id=100,
            title="No Year Show",
            score=0.60,
            year=None,
        )
        assert candidate.year is None
        restored = DecisionCandidate.model_validate(candidate.model_dump())
        assert restored.year is None

    def test_poster_url_none(self) -> None:
        """Explicit None for poster_url round-trips."""
        candidate = DecisionCandidate(
            provider="tmdb",
            provider_id=200,
            title="No Poster",
            score=0.70,
            poster_url=None,
        )
        assert candidate.poster_url is None
        restored = DecisionCandidate.model_validate(candidate.model_dump())
        assert restored.poster_url is None

    def test_overview_none(self) -> None:
        """Explicit None for overview round-trips."""
        candidate = DecisionCandidate(
            provider="tvdb",
            provider_id=300,
            title="No Overview",
            score=0.80,
            overview=None,
        )
        assert candidate.overview is None
        restored = DecisionCandidate.model_validate(candidate.model_dump())
        assert restored.overview is None

    def test_year_int_when_known(self) -> None:
        """Year field accepts an integer value and preserves it."""
        candidate = DecisionCandidate(
            provider="tmdb",
            provider_id=550,
            title="Fight Club",
            year=1999,
            score=0.88,
        )
        assert candidate.year == 1999
        restored = DecisionCandidate.model_validate(candidate.model_dump())
        assert restored.year == 1999


class TestDecisionCandidateTypeValidation:
    """Type validation: invalid provider, wrong field types, missing required fields."""

    def test_bad_provider_literal_rejected(self) -> None:
        """A string outside the tmdb/tvdb literal must raise ValidationError."""
        with pytest.raises(ValidationError) as excinfo:
            DecisionCandidate(
                provider="imdb",  # type: ignore[arg-type]  # not in Literal["tmdb", "tvdb"]
                provider_id=1,
                title="X",
                score=0.5,
            )
        errors = excinfo.value.errors()
        assert len(errors) >= 1
        assert any(e["type"] == "literal_error" and e["loc"] == ("provider",) for e in errors)

    def test_provider_id_must_be_int(self) -> None:
        """A float provider_id must raise ValidationError (strict int)."""
        with pytest.raises(ValidationError) as excinfo:
            DecisionCandidate(
                provider="tmdb",
                provider_id=1.5,  # type: ignore[arg-type]
                title="X",
                score=0.5,
            )
        errors = excinfo.value.errors()
        assert any(e["loc"] == ("provider_id",) for e in errors)

    def test_score_must_be_float(self) -> None:
        """A string score must raise ValidationError."""
        with pytest.raises(ValidationError) as excinfo:
            DecisionCandidate(
                provider="tmdb",
                provider_id=1,
                title="X",
                score="high",  # type: ignore[arg-type]
            )
        errors = excinfo.value.errors()
        assert any(e["loc"] == ("score",) for e in errors)

    def test_missing_title_raises(self) -> None:
        """Omitting the required title field must raise ValidationError."""
        with pytest.raises(ValidationError) as excinfo:
            DecisionCandidate(
                provider="tmdb",
                provider_id=1,
                score=0.5,
            )  # type: ignore[call-arg]
        errors = excinfo.value.errors()
        assert any(e["type"] == "missing" and e["loc"] == ("title",) for e in errors)
