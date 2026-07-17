"""Tests for LaCale tracker client — api/tracker/lacale.py.

Fixtures load real captures from docs/reference/_samples/lacale/. Live samples
were taken 2026-05-07 against https://la-cale.space; api keys and per-request
JWT tokens are redacted.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._quality import parse_title_quality
from personalscraper.api.tracker.lacale import LaCaleClient
from personalscraper.api.transport._auth import ApiKeyAuth

_SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "reference" / "_samples" / "lacale"


def _load(name: str) -> object:
    """Load a redacted live sample."""
    with (_SAMPLES / name).open() as f:
        return json.load(f)


def _make_client() -> LaCaleClient:
    """Build a LaCaleClient with a mocked HttpTransport."""
    transport = MagicMock()
    return LaCaleClient(transport)


class TestLaCalePolicy:
    """LaCaleClient.policy() builds a sensible TransportPolicy."""

    def test_policy_uses_header_apikey(self) -> None:
        """API key sent as X-Api-Key header — confirmed live (query path also accepted but header preferred)."""
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
        """REQUIRED_CREDS lists exactly LACALE_API_KEY (distinct from passkey)."""
        assert LaCaleClient.REQUIRED_CREDS == ["LACALE_API_KEY"]


class TestLaCaleSearchAgainstLiveSamples:
    """LaCaleClient.search() — fed with the captured live JSON."""

    def test_search_returns_typed_results_with_real_payload(self) -> None:
        """Real Inception search payload parses cleanly into 14 TrackerResult."""
        client = _make_client()
        client._transport.get.return_value = _load("search-inception.json")  # type: ignore[attr-defined]

        results = client.search("Inception")

        assert len(results) == 14
        assert all(isinstance(r, TrackerResult) for r in results)
        assert all(r.provider == "lacale" for r in results)

    def test_first_item_field_mapping(self) -> None:
        """First captured Inception item maps to expected TrackerResult fields."""
        client = _make_client()
        client._transport.get.return_value = _load("search-inception.json")  # type: ignore[attr-defined]

        first = client.search("Inception")[0]

        assert first.title == "Inception.2010.MULTi.VFF.1080p.HDLight.DTS.5.1.x264-PATOMiEL"
        assert first.tracker_id == "d7hai97v871c73dbcaq0"
        assert isinstance(first.size, ByteSize)
        assert first.size.bytes == 7_549_978_849
        assert first.seeders == 0
        assert first.leechers == 0
        assert first.category == "Films"
        assert first.info_hash == "c1a7d929f62919b72f58f08da62fc3e0e5ceb820"
        assert first.source_url == "https://la-cale.space/torrents/dhvr9hpmlflp"
        assert first.download_url is not None
        assert "/api/download/c1a7d929f62919b72f58f08da62fc3e0e5ceb820" in first.download_url
        assert isinstance(first.upload_date, datetime)
        assert first.upload_date.tzinfo == timezone.utc

    def test_quality_fields_extracted_from_title(self) -> None:
        """Quality fields are regex-extracted from the title (no JSON columns)."""
        client = _make_client()
        client._transport.get.return_value = _load("search-inception.json")  # type: ignore[attr-defined]

        first = client.search("Inception")[0]
        # Title: ...1080p.HDLight.DTS.5.1.x264-PATOMiEL
        assert first.resolution == "1080p"
        assert first.codec == "x264"
        assert first.audio == "DTS"

    def test_freeleech_always_false(self) -> None:
        """LaCale exposes no freeleech signal — every result has False flags."""
        client = _make_client()
        client._transport.get.return_value = _load("search-inception.json")  # type: ignore[attr-defined]

        results = client.search("Inception")
        assert all(r.is_freeleech is False for r in results)
        assert all(r.is_silverleech is False for r in results)

    def test_search_handles_empty_response(self) -> None:
        """Empty result is `[]` (live-confirmed)."""
        client = _make_client()
        client._transport.get.return_value = _load("search-empty.json")  # type: ignore[attr-defined]
        assert client.search("zzzz_no_match_xyz") == []

    def test_year_appended_to_query(self) -> None:
        """When year is given, it is concatenated to the q parameter."""
        client = _make_client()
        client._transport.get.return_value = []  # type: ignore[attr-defined]

        client.search("Inception", year=2010)

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/external"
        assert kwargs["params"]["q"] == "Inception 2010"

    def test_no_year_passes_query_as_is(self) -> None:
        """Without year, q parameter equals the raw query."""
        client = _make_client()
        client._transport.get.return_value = []  # type: ignore[attr-defined]

        client.search("Inception")

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["params"]["q"] == "Inception"

    def test_pubdate_milliseconds_parsed(self) -> None:
        """ISO 8601 with milliseconds + Z parses to an aware UTC datetime."""
        client = _make_client()
        client._transport.get.return_value = _load("search-inception.json")  # type: ignore[attr-defined]

        first = client.search("Inception")[0]
        assert first.upload_date is not None
        assert first.upload_date.year == 2026
        assert first.upload_date.month == 4
        assert first.upload_date.day == 17
        assert first.upload_date.microsecond == 126_000


class TestLaCaleCategoriesAgainstLiveSamples:
    """LaCaleClient.get_categories() — fed with the captured live meta payload."""

    def test_get_categories_flattens_real_tree(self) -> None:
        """Real meta payload flattens to slug → human-label map."""
        client = _make_client()
        client._transport.get.return_value = _load("meta.json")  # type: ignore[attr-defined]

        cats = client.get_categories()

        # Top-level slugs (Vidéo / Audio / Autres) are present
        assert cats["video"] == "Vidéo"
        assert cats["audio"] == "Audio"
        assert cats["autres"] == "Autres"
        # Nested children are walked
        assert cats["films"] == "Films"
        assert cats["series"] == "Séries TV"
        assert cats["music"] == "Musique"
        # Deep-nested children (Musique > FLAC) are walked too
        assert cats["flac"] == "FLAC"

    def test_get_categories_calls_meta_endpoint(self) -> None:
        """get_categories() hits /api/external/meta."""
        client = _make_client()
        client._transport.get.return_value = {"categories": []}  # type: ignore[attr-defined]

        client.get_categories()

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/external/meta"

    def test_get_categories_handles_null_children(self) -> None:
        """Nodes with `children: null` (leaf) do not crash the recursive walk."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "categories": [
                {"id": "1", "name": "Top", "slug": "top", "children": None},
            ],
        }
        assert client.get_categories() == {"top": "Top"}


class TestLaCaleParseTitle:
    """Shared ``parse_title_quality`` against live LaCale title samples.

    LaCale (like c411/torr9) feeds the shared
    :func:`personalscraper.api.tracker._quality.parse_title_quality` — the
    per-client ``_parse_title`` static method was extracted into that module.
    """

    def test_full_quality_title(self) -> None:
        """Live title with resolution+codec+source+audio markers extracts all four."""
        out = parse_title_quality("Inception.2010.MULTi.TRUEFRENCH.HDR.2160p.UHD.BluRay.DTS-HD.MA.5.1.H265-XANTAR")
        assert out["resolution"] == "2160p"
        assert out["codec"] == "H265"
        assert out["source"] is not None
        assert "bluray" in out["source"].lower()
        assert out["audio"] == "DTS-HD"

    def test_minimal_title_returns_nones(self) -> None:
        """A title without recognizable quality markers yields None fields."""
        out = parse_title_quality("Random.title.no.metadata")
        assert out["resolution"] is None
        assert out["codec"] is None
        assert out["source"] is None
        assert out["audio"] is None
        assert out["format"] is None

    def test_no_freeleech_keys_in_output(self) -> None:
        """Phase 18 revisit: the parser no longer returns freeleech flags."""
        out = parse_title_quality("[FreeLeech] Movie.1080p.x264")
        assert "is_freeleech" not in out
        assert "is_silverleech" not in out

    def test_format_extension_optional(self) -> None:
        """Live LaCale titles do NOT carry a file extension — format is None."""
        out = parse_title_quality("Inception.2010.MULTi.VFF.1080p.HDLight.DTS.5.1.x264-PATOMiEL")
        assert out["format"] is None
