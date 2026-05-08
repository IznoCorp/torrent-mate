"""Tests for C411 tracker client — api/tracker/c411.py.

Fixtures load real captures from docs/reference/_samples/c411/. Live samples
were taken 2026-05-07 against https://c411.org via Torznab/Newznab; api keys
are redacted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
import xmltodict  # type: ignore[import-untyped]

from personalscraper.api._contracts import ApiError
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker.c411 import C411Client
from personalscraper.api.transport._auth import ApiKeyAuth

_SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "reference" / "_samples" / "c411"


def _load_xml(name: str) -> dict[str, object]:
    """Load a captured XML sample and decode through xmltodict (matches HttpTransport)."""
    with (_SAMPLES / name).open() as f:
        return cast("dict[str, object]", xmltodict.parse(f.read()))


def _make_client() -> C411Client:
    """Build a C411Client with a mocked HttpTransport."""
    transport = MagicMock()
    return C411Client(transport)


class TestC411Policy:
    """C411Client.policy() builds a sensible TransportPolicy."""

    def test_policy_uses_query_apikey(self) -> None:
        """Torznab convention requires apikey in query (not header)."""
        policy = C411Client.policy("k")
        assert policy.provider_name == "c411"
        assert policy.base_url == "https://c411.org"
        assert isinstance(policy.auth, ApiKeyAuth)
        assert policy.auth._param == "apikey"
        assert policy.auth._location == "query"

    def test_policy_xml_response(self) -> None:
        """C411 returns XML — TransportPolicy must declare response_format='xml'."""
        policy = C411Client.policy("k")
        assert policy.response_format == "xml"

    def test_policy_defensive_rate_limit(self) -> None:
        """Rate limit set to 0.5 rps (same defensive default as LaCale)."""
        assert C411Client.policy("k").rate_limit.requests_per_second == 0.5

    def test_required_creds(self) -> None:
        """REQUIRED_CREDS lists exactly C411_API_KEY."""
        assert C411Client.REQUIRED_CREDS == ["C411_API_KEY"]


class TestC411SearchAgainstLiveSamples:
    """C411Client.search() — fed with the captured live XML."""

    def test_search_parses_18_items(self) -> None:
        """Real Inception search returns 18 typed TrackerResult."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("search-inception.xml")  # type: ignore[attr-defined]

        results = client.search("Inception")

        assert len(results) == 18
        assert all(isinstance(r, TrackerResult) for r in results)
        assert all(r.provider == "c411" for r in results)

    def test_first_item_field_mapping(self) -> None:
        """First captured Inception item maps to expected TrackerResult fields."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("search-inception.xml")  # type: ignore[attr-defined]

        first = client.search("Inception")[0]

        assert first.title.startswith("Inception.2010")
        assert first.tracker_id == "b08b70d0855318efa71aeccce0ae42b3e4493113"
        assert first.info_hash == "b08b70d0855318efa71aeccce0ae42b3e4493113"
        assert isinstance(first.size, ByteSize)
        assert first.size.bytes == 7_396_633_907
        assert first.seeders == 141
        assert first.leechers == 0  # peers == seeders → leechers clamped to 0
        assert first.category == "2030"
        assert first.is_freeleech is False
        assert first.is_silverleech is False
        assert isinstance(first.upload_date, datetime)
        assert first.upload_date.tzinfo == timezone.utc
        assert first.upload_date.year == 2026

    def test_quality_fields_extracted_from_title(self) -> None:
        """Title regex (reused from LaCale) extracts resolution/codec/audio."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("search-inception.xml")  # type: ignore[attr-defined]

        first = client.search("Inception")[0]
        # Title: ...2160p.BluRay.4KLight.HDR.10bit.DTS.5.1.x265-QTZ
        assert first.resolution == "2160p"
        assert first.codec == "x265"
        assert first.audio == "DTS"
        assert first.source is not None and "bluray" in first.source.lower()

    def test_search_routes_movie_mediatype_to_t_movie(self) -> None:
        """media_type='movie' selects t=movie endpoint."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("movie-imdbid.xml")  # type: ignore[attr-defined]

        client.search("Inception", media_type="movie")

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api"
        assert kwargs["params"]["t"] == "movie"

    def test_search_routes_tv_mediatype_to_tvsearch(self) -> None:
        """media_type='tv' selects t=tvsearch endpoint."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("tvsearch.xml")  # type: ignore[attr-defined]

        client.search("Breaking Bad", media_type="tv")

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["params"]["t"] == "tvsearch"

    def test_search_default_falls_back_to_t_search(self) -> None:
        """Unknown media_type falls back to general t=search."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("search-inception.xml")  # type: ignore[attr-defined]

        client.search("anything", media_type="other")

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["params"]["t"] == "search"

    def test_search_year_appended_to_query(self) -> None:
        """Year coalesces into the q parameter."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("search-empty.xml")  # type: ignore[attr-defined]

        client.search("Inception", year=2010)

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["params"]["q"] == "Inception 2010"

    def test_empty_response_returns_empty_list(self) -> None:
        """Channel with no <item> children returns []."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("search-empty.xml")  # type: ignore[attr-defined]

        assert client.search("zzzz_no_match_xyz") == []

    def test_auth_error_raises_apierror(self) -> None:
        """Document with root <error> raises ApiError with the description."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("error-auth.xml")  # type: ignore[attr-defined]

        with pytest.raises(ApiError) as exc_info:
            client.search("anything")

        err = exc_info.value
        assert err.provider == "c411"
        assert err.http_status == 100  # @code from <error/>
        assert "Invalid API Key" in err.message


class TestC411Categories:
    """C411Client.get_categories() — fed with the captured caps XML."""

    def test_categories_indexed_by_description(self) -> None:
        """Categories key by description (canonical), value is Newznab id.

        Note: descriptions are unique only **within a parent**, not globally.
        E.g. "Applications" appears as both a top-level category (id=4000)
        and a subcat under "GPS" (id=4060). On collision, last-write-wins.
        """
        client = _make_client()
        client._transport.get.return_value = _load_xml("caps.xml")  # type: ignore[attr-defined]

        cats = client.get_categories()

        # Globally-unique top-level descriptions
        assert cats["Films & Vidéos"] == "2000"
        assert cats["Audio"] == "3000"
        # Globally-unique subcat descriptions
        assert cats["Animation"] == "2060"  # Movies/Anime
        assert cats["Film"] == "2030"  # Movies/Foreign
        assert cats["Série TV"] == "5000"  # TV
        assert cats["Documentaire"] == "2070"
        # Many descriptions exist (~50+ entries in real caps tree)
        assert len(cats) > 30

    def test_categories_endpoint_invocation(self) -> None:
        """get_categories() hits /api?t=caps."""
        client = _make_client()
        client._transport.get.return_value = _load_xml("caps.xml")  # type: ignore[attr-defined]

        client.get_categories()

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api"
        assert kwargs["params"]["t"] == "caps"


class TestC411InternalShape:
    """Edge cases that don't need a full sample to verify."""

    def test_torznab_attr_single_dict_handled(self) -> None:
        """Xmltodict returns a single dict (not a list) when only one attr present."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "rss": {
                "channel": {
                    "item": {
                        "title": "Solo.attr.test.1080p.x264-FOO",
                        "guid": "abc123",
                        "pubDate": "Tue, 13 Jan 2026 13:35:54 +0000",
                        "size": "1000",
                        "torznab:attr": {"@name": "seeders", "@value": "5"},
                    },
                },
            },
        }
        results = client.search("anything")
        assert len(results) == 1
        assert results[0].seeders == 5

    def test_freeleech_factor_zero(self) -> None:
        """downloadvolumefactor=0 marks the result as freeleech."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "rss": {
                "channel": {
                    "item": {
                        "title": "Free.movie.1080p.x264-FREE",
                        "guid": "h1",
                        "pubDate": "Tue, 13 Jan 2026 13:35:54 +0000",
                        "size": "1000",
                        "torznab:attr": [
                            {"@name": "seeders", "@value": "10"},
                            {"@name": "peers", "@value": "10"},
                            {"@name": "downloadvolumefactor", "@value": "0"},
                        ],
                    },
                },
            },
        }
        r = client.search("anything")[0]
        assert r.is_freeleech is True
        assert r.is_silverleech is False

    def test_silver_leech_factor_half(self) -> None:
        """downloadvolumefactor=0.5 marks the result as silver-leech."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "rss": {
                "channel": {
                    "item": {
                        "title": "Silver.movie.720p.x264-HALF",
                        "guid": "h2",
                        "pubDate": "Tue, 13 Jan 2026 13:35:54 +0000",
                        "size": "1000",
                        "torznab:attr": [
                            {"@name": "seeders", "@value": "5"},
                            {"@name": "peers", "@value": "8"},
                            {"@name": "downloadvolumefactor", "@value": "0.5"},
                        ],
                    },
                },
            },
        }
        r = client.search("anything")[0]
        assert r.is_silverleech is True
        assert r.is_freeleech is False
        assert r.leechers == 3  # peers - seeders = 8 - 5
