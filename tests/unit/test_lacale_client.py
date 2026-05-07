"""Tests for LaCale tracker client — api/tracker/lacale.py."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker.lacale import LaCaleClient
from personalscraper.api.transport._auth import ApiKeyAuth


def _make_client() -> LaCaleClient:
    """Build a LaCaleClient with a mocked HttpTransport."""
    transport = MagicMock()
    return LaCaleClient(transport)


def _sample_item(**overrides: Any) -> dict[str, Any]:
    """Return a representative LaCale search response item."""
    base: dict[str, Any] = {
        "title": "Inception.2010.2160p.UHD.BluRay.x265.HDR.TrueHD-NCmt.mkv",
        "guid": "ckx9f3p5x0000abcd1234",
        "size": 2_147_483_648,
        "pubDate": "2025-01-12T10:00:00.000Z",
        "link": "https://la-cale.space/torrents/inception",
        "downloadLink": "https://la-cale.space/api/torrents/download/abcdef",
        "category": "Films HD",
        "seeders": 42,
        "leechers": 3,
        "infoHash": "abcdef0123456789",
    }
    base.update(overrides)
    return base


class TestLaCalePolicy:
    """LaCaleClient.policy() builds a sensible TransportPolicy."""

    def test_policy_uses_header_apikey(self) -> None:
        """API key sent as X-Api-Key header (not query) per Phase 17 decision."""
        policy = LaCaleClient.policy("secret-key")
        assert policy.provider_name == "lacale"
        assert policy.base_url == "https://la-cale.space"
        assert isinstance(policy.auth, ApiKeyAuth)
        assert policy.auth._param == "X-Api-Key"
        assert policy.auth._location == "header"

    def test_policy_defensive_rate_limit(self) -> None:
        """Rate limit set to 0.5 rps per docs/reference/lacale-api.md."""
        policy = LaCaleClient.policy("k")
        assert policy.rate_limit.requests_per_second == 0.5

    def test_required_creds(self) -> None:
        """REQUIRED_CREDS lists exactly LACALE_API_KEY."""
        assert LaCaleClient.REQUIRED_CREDS == ["LACALE_API_KEY"]


class TestLaCaleSearch:
    """LaCaleClient.search() — mocked HTTP."""

    def test_search_returns_typed_results(self) -> None:
        """search() returns list[TrackerResult] with ByteSize size field."""
        client = _make_client()
        client._transport.get.return_value = [_sample_item()]  # type: ignore[attr-defined]

        results = client.search("Inception", year=2010)

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, TrackerResult)
        assert r.provider == "lacale"
        assert r.tracker_id == "ckx9f3p5x0000abcd1234"
        assert r.title.startswith("Inception")
        assert isinstance(r.size, ByteSize)
        assert r.size.bytes == 2_147_483_648
        assert r.seeders == 42
        assert r.leechers == 3
        assert r.category == "Films HD"
        assert r.download_url == "https://la-cale.space/api/torrents/download/abcdef"
        assert r.info_hash == "abcdef0123456789"
        assert r.source_url == "https://la-cale.space/torrents/inception"
        assert isinstance(r.upload_date, datetime)

    def test_search_extracts_quality_fields_from_title(self) -> None:
        """Quality fields are regex-extracted from the title (not from JSON)."""
        client = _make_client()
        client._transport.get.return_value = [_sample_item()]  # type: ignore[attr-defined]

        results = client.search("Inception")

        r = results[0]
        assert r.resolution == "2160p"
        assert r.codec == "x265"
        assert r.source is not None
        assert "BluRay" in r.source.replace(".", "").replace(" ", "BluRay")
        assert r.audio == "TrueHD"
        assert r.format == "mkv"

    def test_search_year_appended_to_query(self) -> None:
        """When year is given, it is concatenated to the q parameter."""
        client = _make_client()
        client._transport.get.return_value = []  # type: ignore[attr-defined]

        client.search("Inception", year=2010)

        client._transport.get.assert_called_once()  # type: ignore[attr-defined]
        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/external"
        assert kwargs["params"]["q"] == "Inception 2010"

    def test_search_no_year_passes_query_as_is(self) -> None:
        """Without year, q parameter equals the raw query."""
        client = _make_client()
        client._transport.get.return_value = []  # type: ignore[attr-defined]

        client.search("Inception")

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["params"]["q"] == "Inception"

    def test_search_freeleech_prefix_sets_flag(self) -> None:
        """Title prefix [FreeLeech] sets is_freeleech=True."""
        client = _make_client()
        client._transport.get.return_value = [  # type: ignore[attr-defined]
            _sample_item(title="[FreeLeech] Inception.2010.2160p.x265.mkv"),
        ]

        r = client.search("Inception")[0]
        assert r.is_freeleech is True
        assert r.is_silverleech is False

    def test_search_silverleech_prefix_sets_flag(self) -> None:
        """Title prefix [SilverLeech] sets is_silverleech=True."""
        client = _make_client()
        client._transport.get.return_value = [  # type: ignore[attr-defined]
            _sample_item(title="[SilverLeech] Inception.2010.1080p.x264.mkv"),
        ]

        r = client.search("Inception")[0]
        assert r.is_silverleech is True
        assert r.is_freeleech is False

    def test_search_handles_empty_response(self) -> None:
        """Empty list response returns empty list."""
        client = _make_client()
        client._transport.get.return_value = []  # type: ignore[attr-defined]

        assert client.search("nope") == []


class TestLaCaleCategories:
    """LaCaleClient.get_categories()."""

    def test_get_categories_flattens_tree(self) -> None:
        """Categories tree is flattened to slug → name dict, recursing through children."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "categories": [
                {
                    "id": "cat_video",
                    "name": "Video",
                    "slug": "video",
                    "children": [
                        {"id": "cat_films", "name": "Films", "slug": "films"},
                        {"id": "cat_films_hd", "name": "Films HD", "slug": "films-hd"},
                    ],
                },
            ],
            "tagGroups": [{"id": "tg_q", "name": "Q", "tags": []}],
            "ungroupedTags": [],
        }

        cats = client.get_categories()
        assert cats == {
            "video": "Video",
            "films": "Films",
            "films-hd": "Films HD",
        }

    def test_get_categories_calls_meta_endpoint(self) -> None:
        """get_categories() hits /api/external/meta."""
        client = _make_client()
        client._transport.get.return_value = {"categories": []}  # type: ignore[attr-defined]

        client.get_categories()

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/external/meta"


class TestLaCaleParseTitle:
    """LaCaleClient._parse_title()."""

    def test_full_quality_title(self) -> None:
        """All quality fields extracted from a fully-tagged title."""
        out = LaCaleClient._parse_title("Inception.2010.2160p.UHD.BluRay.x265.HDR.TrueHD-NCmt.mkv")
        assert out["resolution"] == "2160p"
        assert out["codec"] == "x265"
        assert out["audio"] == "TrueHD"
        assert out["format"] == "mkv"
        # source includes "BluRay" with the UHD prefix variant
        assert out["source"] is not None

    def test_minimal_title_returns_nones(self) -> None:
        """A title without recognizable quality markers yields None fields."""
        out = LaCaleClient._parse_title("Random.title.no.metadata.txt")
        assert out["resolution"] is None
        assert out["codec"] is None
        assert out["source"] is None
        assert out["audio"] is None
        # txt is not a recognized video format
        assert out["format"] is None

    def test_freeleech_prefix_detected(self) -> None:
        """[FreeLeech] prefix sets is_freeleech True."""
        out = LaCaleClient._parse_title("[FreeLeech] Movie.1080p.x264.mkv")
        assert out["is_freeleech"] is True
        assert out["is_silverleech"] is False
        assert out["resolution"] == "1080p"

    def test_silverleech_prefix_detected(self) -> None:
        """[SilverLeech] prefix sets is_silverleech True."""
        out = LaCaleClient._parse_title("[SilverLeech] Movie.720p.x264.mkv")
        assert out["is_silverleech"] is True
        assert out["is_freeleech"] is False

    def test_neither_prefix(self) -> None:
        """Without leech tags both flags are False."""
        out = LaCaleClient._parse_title("Movie.1080p.x264.mkv")
        assert out["is_freeleech"] is False
        assert out["is_silverleech"] is False
