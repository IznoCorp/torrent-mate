"""Tests for the media sheet response models (media-sheet feature D1-D9).

Validates model instantiation, serialization roundtrip, and the D4/D9 invariant:
a field the provider does not supply must stay ``None``, never an empty string.
"""

from __future__ import annotations

from personalscraper.web.models.media import (
    MediaSheetResponse,
    OwnershipBlock,
    SeasonOwnership,
)


class TestSeasonOwnership:
    """Unit tests for :class:`SeasonOwnership`."""

    def test_instantiation(self) -> None:
        """All fields are populated from constructor args."""
        so = SeasonOwnership(
            season_number=1,
            episode_count=10,
            owned_count=8,
            aired_count=10,
        )
        assert so.season_number == 1
        assert so.episode_count == 10
        assert so.owned_count == 8
        assert so.aired_count == 10

    def test_serialization_roundtrip(self) -> None:
        """Model serializes to dict and deserializes back losslessly."""
        so = SeasonOwnership(
            season_number=2,
            episode_count=22,
            owned_count=0,
            aired_count=22,
        )
        data = so.model_dump()
        assert data == {
            "season_number": 2,
            "episode_count": 22,
            "owned_count": 0,
            "aired_count": 22,
        }
        so2 = SeasonOwnership(**data)
        assert so2 == so


class TestOwnershipBlock:
    """Unit tests for :class:`OwnershipBlock`."""

    def test_defaults(self) -> None:
        """Default block: not owned, empty seasons list."""
        block = OwnershipBlock(owned=False)
        assert block.owned is False
        assert block.seasons == []

    def test_with_seasons(self) -> None:
        """Seasons list is populated from constructor."""
        block = OwnershipBlock(
            owned=True,
            seasons=[
                SeasonOwnership(
                    season_number=1,
                    episode_count=10,
                    owned_count=10,
                    aired_count=10,
                ),
            ],
        )
        assert block.owned is True
        assert len(block.seasons) == 1
        assert block.seasons[0].season_number == 1

    def test_serialization_roundtrip(self) -> None:
        """Roundtrip through JSON preserves nested seasons."""
        block = OwnershipBlock(
            owned=True,
            seasons=[
                SeasonOwnership(
                    season_number=1,
                    episode_count=8,
                    owned_count=5,
                    aired_count=8,
                ),
            ],
        )
        data = block.model_dump()
        block2 = OwnershipBlock(**data)
        assert block2.owned is True
        assert len(block2.seasons) == 1
        assert block2.seasons[0].episode_count == 8


class TestMediaSheetResponse:
    """Unit tests for :class:`MediaSheetResponse`."""

    def test_minimal_movie_response(self) -> None:
        """A movie response with only identity fields filled."""
        resp = MediaSheetResponse(
            provider="tmdb",
            provider_id="550",
            title="Fight Club",
            year=1999,
            poster_url="https://image.tmdb.org/t/p/w500/abc.jpg",
            overview="First rule: you do not talk about it.",
            director="David Fincher",
            genres=["Drama", "Thriller"],
            trailer_url=None,
            series_status=None,
            seasons=[],
            ownership=OwnershipBlock(owned=True),
            degraded_reason=None,
        )
        assert resp.provider == "tmdb"
        assert resp.provider_id == "550"
        assert resp.title == "Fight Club"
        assert resp.director == "David Fincher"
        # DESIGN D4/D9: movie has no series_status
        assert resp.series_status is None
        assert resp.trailer_url is None

    def test_full_tv_response(self) -> None:
        """A TV show response with seasons and ownership."""
        resp = MediaSheetResponse(
            provider="tvdb",
            provider_id="255968",
            title="Top Chef",
            year=2010,
            poster_url="https://artworks.thetvdb.com/abc.jpg",
            overview="Cooking competition.",
            director=None,
            genres=["Reality"],
            trailer_url=None,
            series_status="Returning Series",
            seasons=[
                {"season_number": 1, "episode_count": 12},
                {"season_number": 2, "episode_count": 14},
            ],
            ownership=OwnershipBlock(
                owned=True,
                seasons=[
                    SeasonOwnership(
                        season_number=1,
                        episode_count=12,
                        owned_count=12,
                        aired_count=12,
                    ),
                    SeasonOwnership(
                        season_number=2,
                        episode_count=14,
                        owned_count=8,
                        aired_count=14,
                    ),
                ],
            ),
            degraded_reason=None,
        )
        assert resp.series_status == "Returning Series"
        assert resp.seasons == [
            {"season_number": 1, "episode_count": 12},
            {"season_number": 2, "episode_count": 14},
        ]
        assert resp.ownership is not None
        assert resp.ownership.owned is True
        assert len(resp.ownership.seasons) == 2
        assert resp.ownership.seasons[1].owned_count == 8

    def test_director_none_not_empty_string(self) -> None:
        """DESIGN D4/D9: unknown director is None, never an empty string."""
        resp = MediaSheetResponse(
            provider="tvdb",
            provider_id="123",
            title="Some Show",
            year=None,
            poster_url="",
            overview="",
            director=None,
            genres=[],
            trailer_url=None,
            series_status=None,
            seasons=[],
            ownership=None,
            degraded_reason=None,
        )
        assert resp.director is None
        # The field is None, not an empty string — these are different facts.
        assert resp.director != ""

    def test_degraded_reason_when_set(self) -> None:
        """degraded_reason is populated when the provider failed."""
        resp = MediaSheetResponse(
            provider="tmdb",
            provider_id="999",
            title="Unknown Movie",
            year=None,
            poster_url="",
            overview="",
            director=None,
            genres=[],
            trailer_url=None,
            series_status=None,
            seasons=[],
            ownership=None,
            degraded_reason="TMDB n'a pas répondu dans le délai imparti.",
        )
        assert resp.degraded_reason == "TMDB n'a pas répondu dans le délai imparti."
        # Identity fields still present even under degradation (D9).
        assert resp.provider == "tmdb"
        assert resp.provider_id == "999"
        assert resp.title == "Unknown Movie"

    def test_ownership_none_when_library_unavailable(self) -> None:
        """Ownership is None when the library DB is absent (fail-soft)."""
        resp = MediaSheetResponse(
            provider="tmdb",
            provider_id="550",
            title="Fight Club",
            year=1999,
            poster_url="https://image.tmdb.org/t/p/w500/abc.jpg",
            overview="...",
            director="David Fincher",
            genres=["Drama"],
            trailer_url=None,
            series_status=None,
            seasons=[],
            ownership=None,
            degraded_reason=None,
        )
        assert resp.ownership is None

    def test_serialization_roundtrip(self) -> None:
        """Full response survives JSON serialization roundtrip."""
        resp = MediaSheetResponse(
            provider="tmdb",
            provider_id="27205",
            title="Inception",
            year=2010,
            poster_url="https://image.tmdb.org/t/p/w500/inception.jpg",
            overview="A thief who steals corporate secrets...",
            director="Christopher Nolan",
            genres=["Action", "Science Fiction", "Thriller"],
            trailer_url="https://www.youtube.com/watch?v=YoHD9XEInc0",
            series_status=None,
            seasons=[],
            ownership=OwnershipBlock(owned=True),
            degraded_reason=None,
        )
        data = resp.model_dump()
        # Verify the data dict is serializable
        import json as _json

        json_str = _json.dumps(data, default=str)
        loaded = _json.loads(json_str)
        assert loaded["provider"] == "tmdb"
        assert loaded["director"] == "Christopher Nolan"
        assert loaded["trailer_url"] == "https://www.youtube.com/watch?v=YoHD9XEInc0"
        assert loaded["series_status"] is None

    def test_degraded_reason_none_when_full_response(self) -> None:
        """degraded_reason is None on a full provider response."""
        resp = MediaSheetResponse(
            provider="tmdb",
            provider_id="27205",
            title="Inception",
            year=2010,
            poster_url="...",
            overview="...",
            director="Christopher Nolan",
            genres=["Action"],
            trailer_url=None,
            series_status=None,
            seasons=[],
            ownership=OwnershipBlock(owned=False),
            degraded_reason=None,
        )
        assert resp.degraded_reason is None
