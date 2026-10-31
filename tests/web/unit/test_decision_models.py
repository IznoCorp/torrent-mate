"""Unit tests for decisions API Pydantic models (scrape-arbiter feature).

Mirrors conventions from tests/test_config_models.py and
tests/web/test_pipeline_maintenance_models.py.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from personalscraper.scraper.decision_candidate import DecisionCandidate
from personalscraper.web.models.decisions import (
    DecisionDetail,
    DecisionListItem,
    DecisionsResponse,
    ResolveRequest,
    ResolveResponse,
    SearchRequest,
    SearchResponse,
)

# ---------------------------------------------------------------------------
# DecisionCandidate (re-exported from personalscraper.scraper.decision_candidate)
# ---------------------------------------------------------------------------


class TestDecisionCandidate:
    """Tests for ``DecisionCandidate`` — the shared candidate model."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly with all fields populated."""
        obj = DecisionCandidate(
            provider="tmdb",
            provider_id=12345,
            title="The Matrix",
            year=1999,
            score=0.95,
            poster_url="https://image.tmdb.org/t/p/w500/matrix.jpg",
            overview="A computer hacker learns about the true nature of reality.",
        )
        d = obj.model_dump()
        assert d["provider"] == "tmdb"
        assert d["provider_id"] == 12345
        assert d["title"] == "The Matrix"
        assert d["year"] == 1999
        assert d["score"] == 0.95
        assert d["poster_url"] == "https://image.tmdb.org/t/p/w500/matrix.jpg"
        assert d["overview"] == "A computer hacker learns about the true nature of reality."
        assert DecisionCandidate.model_validate(d) == obj

    def test_minimal_fields(self) -> None:
        """Only ``provider``, ``provider_id``, ``title``, and ``score`` are required."""
        obj = DecisionCandidate(
            provider="tvdb",
            provider_id=67890,
            title="Breaking Bad",
            score=1.0,
        )
        d = obj.model_dump()
        assert d == {
            "provider": "tvdb",
            "provider_id": 67890,
            "title": "Breaking Bad",
            "year": None,
            "score": 1.0,
            "poster_url": None,
            "overview": None,
        }
        assert DecisionCandidate.model_validate(d) == obj

    def test_provider_literal_rejects_invalid(self) -> None:
        """``provider`` must be ``'tmdb'`` or ``'tvdb'`` — anything else is rejected."""
        with pytest.raises(ValidationError):
            DecisionCandidate(
                provider="imdb",  # type: ignore[arg-type]
                provider_id=111,
                title="Test",
                score=0.5,
            )

    def test_provider_literal_accepts_tmdb(self) -> None:
        """``provider='tmdb'`` is valid (Literal check)."""
        obj = DecisionCandidate(provider="tmdb", provider_id=1, title="T", score=0.5)
        assert obj.provider == "tmdb"

    def test_provider_literal_accepts_tvdb(self) -> None:
        """``provider='tvdb'`` is valid (Literal check)."""
        obj = DecisionCandidate(provider="tvdb", provider_id=1, title="T", score=0.5)
        assert obj.provider == "tvdb"

    def test_nullable_fields_default_none(self) -> None:
        """``year``, ``poster_url``, and ``overview`` default to ``None``."""
        obj = DecisionCandidate(provider="tmdb", provider_id=1, title="T", score=0.5)
        assert obj.year is None
        assert obj.poster_url is None
        assert obj.overview is None


# ---------------------------------------------------------------------------
# DecisionListItem
# ---------------------------------------------------------------------------


class TestDecisionListItem:
    """Tests for ``DecisionListItem`` — summary row in the list endpoint."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly with all fields populated."""
        obj = DecisionListItem(
            id=1,
            staging_path="/Volumes/staging/002-TVSHOWS/Breaking Bad",
            media_kind="tvshow",
            extracted_title="Breaking Bad",
            extracted_year=2008,
            trigger="below_threshold",
            candidates_count=5,
            status="pending",
            created_at=1719000000.0,
        )
        d = obj.model_dump()
        assert d["id"] == 1
        assert d["staging_path"] == "/Volumes/staging/002-TVSHOWS/Breaking Bad"
        assert d["media_kind"] == "tvshow"
        assert d["extracted_title"] == "Breaking Bad"
        assert d["extracted_year"] == 2008
        assert d["trigger"] == "below_threshold"
        assert d["candidates_count"] == 5
        assert d["status"] == "pending"
        assert d["created_at"] == 1719000000.0
        assert DecisionListItem.model_validate(d) == obj

    def test_nullable_extracted_year(self) -> None:
        """``extracted_year`` defaults to ``None`` when no year is extractable."""
        obj = DecisionListItem(
            id=2,
            staging_path="/tmp/movie",
            media_kind="movie",
            extracted_title="Unknown Title",
            trigger="mid_band",
            candidates_count=0,
            status="pending",
            created_at=0.0,
        )
        assert obj.extracted_year is None
        d = obj.model_dump()
        assert d["extracted_year"] is None

    def test_status_literals(self) -> None:
        """All four status values are accepted."""
        for status in ("pending", "resolved", "dismissed", "superseded"):
            obj = DecisionListItem(
                id=1,
                staging_path="/tmp/x",
                media_kind="movie",
                extracted_title="X",
                trigger="ambiguous",
                candidates_count=1,
                status=status,
                created_at=0.0,
            )
            assert obj.status == status

    def test_trigger_literals(self) -> None:
        """All three trigger values are accepted."""
        for trigger in ("below_threshold", "mid_band", "ambiguous"):
            obj = DecisionListItem(
                id=1,
                staging_path="/tmp/x",
                media_kind="movie",
                extracted_title="X",
                trigger=trigger,
                candidates_count=1,
                status="pending",
                created_at=0.0,
            )
            assert obj.trigger == trigger


# ---------------------------------------------------------------------------
# DecisionsResponse
# ---------------------------------------------------------------------------


class TestDecisionsResponse:
    """Tests for ``DecisionsResponse`` — paginated list envelope."""

    def test_roundtrip(self) -> None:
        """Wraps a list of ``DecisionListItem`` and round-trips correctly."""
        item = DecisionListItem(
            id=1,
            staging_path="/tmp/x",
            media_kind="movie",
            extracted_title="X",
            trigger="ambiguous",
            candidates_count=3,
            status="pending",
            created_at=1719000000.0,
        )
        resp = DecisionsResponse(
            items=[item],
            pending_count=1,
            total=1,
            page=1,
            page_size=50,
        )
        d = resp.model_dump()
        assert len(d["items"]) == 1
        assert d["items"][0]["id"] == 1
        assert d["pending_count"] == 1
        assert d["total"] == 1
        assert d["page"] == 1
        assert d["page_size"] == 50
        assert DecisionsResponse.model_validate(d) == resp

    def test_empty_list(self) -> None:
        """Zero items and zero pending count."""
        resp = DecisionsResponse(items=[], pending_count=0, total=0, page=1, page_size=50)
        d = resp.model_dump()
        assert d["items"] == []
        assert d["pending_count"] == 0
        assert d["total"] == 0


# ---------------------------------------------------------------------------
# DecisionDetail
# ---------------------------------------------------------------------------


class TestDecisionDetail:
    """Tests for ``DecisionDetail`` — full row with candidates and resolution."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly with candidates and resolution_json."""
        candidate = DecisionCandidate(provider="tmdb", provider_id=100, title="Test Movie", score=0.9)
        detail = DecisionDetail(
            id=1,
            staging_path="/tmp/movie",
            media_kind="movie",
            extracted_title="Test Movie",
            extracted_year=2025,
            trigger="mid_band",
            candidates_count=1,
            status="resolved",
            created_at=1719000000.0,
            candidates=[candidate],
            resolution_json={
                "provider": "tmdb",
                "provider_id": 100,
                "via": "pick",
            },
        )
        d = detail.model_dump()
        assert d["id"] == 1
        assert len(d["candidates"]) == 1
        assert d["candidates"][0]["provider"] == "tmdb"
        assert d["resolution_json"] == {
            "provider": "tmdb",
            "provider_id": 100,
            "via": "pick",
        }
        reloaded = DecisionDetail.model_validate(d)
        assert reloaded.candidates[0].provider == "tmdb"
        assert reloaded.resolution_json == {"provider": "tmdb", "provider_id": 100, "via": "pick"}

    def test_resolution_json_none_for_pending(self) -> None:
        """``resolution_json`` is ``None`` for pending decisions."""
        candidate = DecisionCandidate(provider="tvdb", provider_id=200, title="Test Show", score=0.5)
        detail = DecisionDetail(
            id=2,
            staging_path="/tmp/show",
            media_kind="tvshow",
            extracted_title="Test Show",
            trigger="below_threshold",
            candidates_count=1,
            status="pending",
            created_at=0.0,
            candidates=[candidate],
        )
        assert detail.resolution_json is None
        d = detail.model_dump()
        assert d["resolution_json"] is None

    def test_inherits_list_item_fields(self) -> None:
        """``DecisionDetail`` carries all ``DecisionListItem`` fields."""
        detail = DecisionDetail(
            id=3,
            staging_path="/tmp/z",
            media_kind="movie",
            extracted_title="Z",
            trigger="ambiguous",
            candidates_count=5,
            status="pending",
            created_at=1.0,
            candidates=[],
        )
        assert detail.id == 3
        assert detail.staging_path == "/tmp/z"
        assert detail.media_kind == "movie"
        assert detail.extracted_title == "Z"
        assert detail.extracted_year is None
        assert detail.trigger == "ambiguous"
        assert detail.candidates_count == 5
        assert detail.status == "pending"
        assert detail.created_at == 1.0


# ---------------------------------------------------------------------------
# SearchRequest
# ---------------------------------------------------------------------------


class TestSearchRequest:
    """Tests for ``SearchRequest`` — live provider search body."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = SearchRequest(title="Inception", year=2010)
        d = obj.model_dump()
        assert d["title"] == "Inception"
        assert d["year"] == 2010
        assert SearchRequest.model_validate(d) == obj

    def test_year_optional_defaults_none(self) -> None:
        """``year`` is optional and defaults to ``None``."""
        obj = SearchRequest(title="Inception")
        assert obj.year is None
        d = obj.model_dump()
        assert d == {"title": "Inception", "year": None}


# ---------------------------------------------------------------------------
# SearchResponse
# ---------------------------------------------------------------------------


class TestSearchResponse:
    """Tests for ``SearchResponse`` — live search result envelope."""

    def test_roundtrip(self) -> None:
        """Wraps a list of ``DecisionCandidate`` and round-trips correctly."""
        c = DecisionCandidate(provider="tmdb", provider_id=1, title="T", score=0.5)
        resp = SearchResponse(candidates=[c])
        d = resp.model_dump()
        assert len(d["candidates"]) == 1
        assert d["candidates"][0]["provider"] == "tmdb"
        assert SearchResponse.model_validate(d) == resp

    def test_empty_candidates(self) -> None:
        """Zero candidates when the search returns nothing."""
        resp = SearchResponse(candidates=[])
        d = resp.model_dump()
        assert d["candidates"] == []
        assert SearchResponse.model_validate(d) == resp


# ---------------------------------------------------------------------------
# ResolveRequest
# ---------------------------------------------------------------------------


class TestResolveRequest:
    """Tests for ``ResolveRequest`` — targeted re-scrape body."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = ResolveRequest(provider="tmdb", provider_id=550)
        d = obj.model_dump()
        assert d["provider"] == "tmdb"
        assert d["provider_id"] == 550
        assert ResolveRequest.model_validate(d) == obj

    def test_roundtrip_tvdb(self) -> None:
        """``provider='tvdb'`` is valid."""
        obj = ResolveRequest(provider="tvdb", provider_id=255968)
        d = obj.model_dump()
        assert d["provider"] == "tvdb"
        assert ResolveRequest.model_validate(d) == obj

    def test_provider_literal_rejects_invalid(self) -> None:
        """``provider`` must be ``'tmdb'`` or ``'tvdb'``."""
        with pytest.raises(ValidationError):
            ResolveRequest(provider="imdb", provider_id=1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ResolveResponse
# ---------------------------------------------------------------------------


class TestResolveResponse:
    """Tests for ``ResolveResponse`` — 202 Accepted response."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = ResolveResponse(run_uid="abc123-def456")
        d = obj.model_dump()
        assert d == {"run_uid": "abc123-def456"}
        assert ResolveResponse.model_validate(d) == obj
