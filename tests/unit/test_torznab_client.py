"""Tests for the generic Torznab client — api/tracker/torznab.py.

Where ``test_c411_client.py`` pins the C411 *named config* (and must never
change), this file exercises the *generic*: the same engine driven by two
different :class:`TorznabDescriptor` instances must produce different URLs,
endpoint names and category sources — and must keep the fail-soft contract the
registry relies on (parser drift and network failures never abort a
multi-tracker search).

The XML fixtures are the very same live C411 captures the C411 tests use: the
``_load_xml`` loader is imported from ``test_c411_client`` rather than copied,
so both suites always feed the parser identical bytes.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from personalscraper.api._contracts import ApiError, MediaType, ProviderName
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.api.tracker.c411 import C411_DESCRIPTOR
from personalscraper.api.tracker.torznab import TorznabClient, TorznabDescriptor
from personalscraper.api.transport._auth import ApiKeyAuth
from personalscraper.core.event_bus import EventBus
from tests.unit.test_c411_client import _load_xml  # shared live XML fixtures — never copied

# A second, deliberately different dialect: another host, another endpoint
# path, other ``t=`` operation names, a ``cat=`` narrowing map, and the two
# quirks flipped relative to C411. ``ProviderName`` carries no test-only
# member, so an existing one stands in as the identity — only the descriptor
# under test matters here, not the real tracker it names.
OTHER_DESCRIPTOR = TorznabDescriptor(
    provider=ProviderName.TR4KER,
    display_name="Other",
    base_url="https://other.example",
    api_path="/api/torznab",
    apikey_param="api_key",
    movie_endpoint="movies",
    tv_endpoint="tv-search",
    default_endpoint="all",
    caps_endpoint="capabilities",
    search_categories={"movie": "2000", "tv": "5000"},
    item_category_element=True,
    guid_is_infohash=False,
    timeout_seconds=42,
)


class _OtherClient(TorznabClient):
    """A second named config, used to prove ``policy()`` reads the descriptor."""

    DESCRIPTOR = OTHER_DESCRIPTOR


def _client(descriptor: TorznabDescriptor) -> TorznabClient:
    """Build a generic client on the given descriptor with a mocked transport."""
    return TorznabClient(MagicMock(), descriptor)


def _item(**overrides: Any) -> dict[str, Any]:
    """One minimal Torznab ``<item>`` as xmltodict decodes it."""
    item: dict[str, Any] = {
        "title": "Some.Movie.2010.1080p.BluRay.x264-GRP",
        "guid": "f" * 40,
        "pubDate": "Tue, 13 Jan 2026 13:35:54 +0000",
        "size": "1000",
        "torznab:attr": [
            {"@name": "category", "@value": "2030"},
            {"@name": "seeders", "@value": "10"},
            {"@name": "peers", "@value": "13"},
        ],
    }
    item.update(overrides)
    return item


def _rss(*items: dict[str, Any]) -> dict[str, Any]:
    """Wrap items in the RSS envelope xmltodict produces."""
    return {"rss": {"channel": {"item": list(items)}}}


class _OkTracker:
    """Stub tracker returning a single result, to verify survival semantics."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def search(self, query: str, media_type: str = "movie", year: int | None = None) -> list[TrackerResult]:
        """Return one canned result for any query."""
        return [
            TrackerResult(
                provider=self.provider,
                tracker_id=f"{self.provider}-1",
                title="Inception",
                size=ByteSize(bytes=1_000_000_000),
                seeders=10,
                leechers=1,
            )
        ]

    def get_categories(self) -> dict[str, str]:
        """No categories — unused by these tests."""
        return {}


class TestDescriptorDrivesTheRequest:
    """Two descriptors, one engine — the request must follow the descriptor."""

    @pytest.mark.parametrize(
        ("descriptor", "path", "expected_t"),
        [
            (C411_DESCRIPTOR, "/api", "movie"),
            (OTHER_DESCRIPTOR, "/api/torznab", "movies"),
        ],
    )
    def test_movie_search_path_and_endpoint(self, descriptor: TorznabDescriptor, path: str, expected_t: str) -> None:
        """The movie search hits the descriptor's api_path with its movie endpoint."""
        client = _client(descriptor)
        client._transport.get.return_value = _rss()  # type: ignore[attr-defined]

        client.search("Inception", media_type="movie")

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == path
        assert kwargs["params"]["t"] == expected_t

    @pytest.mark.parametrize(
        ("descriptor", "expected_tv", "expected_default"),
        [
            (C411_DESCRIPTOR, "tvsearch", "search"),
            (OTHER_DESCRIPTOR, "tv-search", "all"),
        ],
    )
    def test_tv_and_fallback_endpoints(
        self, descriptor: TorznabDescriptor, expected_tv: str, expected_default: str
    ) -> None:
        """``tv`` uses the tv endpoint; any other media type falls back to the default one."""
        client = _client(descriptor)
        client._transport.get.return_value = _rss()  # type: ignore[attr-defined]

        client.search("Breaking Bad", media_type="tv")
        assert client._transport.get.call_args.kwargs["params"]["t"] == expected_tv  # type: ignore[attr-defined]

        client.search("whatever", media_type="other")
        assert client._transport.get.call_args.kwargs["params"]["t"] == expected_default  # type: ignore[attr-defined]

    def test_year_appended_to_query_for_every_dialect(self) -> None:
        """The year coalesces into ``q`` regardless of the descriptor."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss()  # type: ignore[attr-defined]

        client.search("Inception", year=2010)

        assert client._transport.get.call_args.kwargs["params"]["q"] == "Inception 2010"  # type: ignore[attr-defined]

    def test_cat_param_sent_only_when_descriptor_declares_one(self) -> None:
        """``cat=`` is descriptor-driven: sent by the dialect that maps it, absent otherwise."""
        with_cat = _client(OTHER_DESCRIPTOR)
        with_cat._transport.get.return_value = _rss()  # type: ignore[attr-defined]
        with_cat.search("Inception", media_type=MediaType.MOVIE)
        assert with_cat._transport.get.call_args.kwargs["params"]["cat"] == "2000"  # type: ignore[attr-defined]

        without_cat = _client(C411_DESCRIPTOR)
        without_cat._transport.get.return_value = _rss()  # type: ignore[attr-defined]
        without_cat.search("Inception", media_type=MediaType.MOVIE)
        assert "cat" not in without_cat._transport.get.call_args.kwargs["params"]  # type: ignore[attr-defined]

    def test_caps_endpoint_is_descriptor_driven(self) -> None:
        """``get_categories()`` hits the descriptor's api_path + caps endpoint."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _load_xml("caps.xml")  # type: ignore[attr-defined]

        cats = client.get_categories()

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/torznab"
        assert kwargs["params"]["t"] == "capabilities"
        # Same caps tree, same flattening as the C411 named config.
        assert cats["Films & Vidéos"] == "2000"

    def test_provider_name_comes_from_the_descriptor(self) -> None:
        """Parsed results are tagged with the descriptor's provider, not a hardcoded name."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(_item())  # type: ignore[attr-defined]

        assert client.provider_name == "tr4ker"
        assert client.search("Inception")[0].provider == "tr4ker"


class TestPolicyFromDescriptor:
    """``policy()`` is generic — every knob comes from the class descriptor."""

    def test_policy_reads_base_url_timeout_and_auth(self) -> None:
        """Base URL, timeout and api-key parameter follow the descriptor."""
        policy = _OtherClient.policy("k")

        assert policy.provider_name == "tr4ker"
        assert policy.base_url == "https://other.example"
        assert policy.timeout_seconds == 42
        assert isinstance(policy.auth, ApiKeyAuth)
        assert policy.auth._param == "api_key"
        assert policy.auth._location == "query"

    def test_policy_response_format_is_always_xml(self) -> None:
        """Torznab is an XML protocol — not a per-tracker knob."""
        assert _OtherClient.policy("k").response_format == "xml"

    def test_from_env_builds_a_client_of_the_named_subclass(self) -> None:
        """``from_env`` returns the concrete subclass, keyed on the first required cred."""
        client = _OtherClient.from_env(
            env={"OTHER_API_KEY": "secret"},
            event_bus=EventBus(),
            required=["OTHER_API_KEY"],
            provider_cfg=MagicMock(),
        )

        assert isinstance(client, _OtherClient)
        assert client._open_transport is client._transport
        assert client._transport._policy.auth.auth_params() == {"api_key": "secret"}


class TestAttrFlattening:
    """``torznab:attr`` elements are flattened into ``{name: value}``."""

    def test_single_attr_dict_is_accepted(self) -> None:
        """Xmltodict returns a bare dict when a single attr is present."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(  # type: ignore[attr-defined]
            _item(**{"torznab:attr": {"@name": "seeders", "@value": "7"}})
        )

        assert client.search("x")[0].seeders == 7

    def test_attrs_feed_seeders_peers_and_leechers(self) -> None:
        """Leechers are derived from peers − seeders, clamped at 0."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(_item())  # type: ignore[attr-defined]

        result = client.search("x")[0]

        assert (result.seeders, result.leechers) == (10, 3)

    def test_malformed_attrs_are_ignored_not_fatal(self) -> None:
        """Attrs missing ``@name``/``@value`` are skipped; the item still parses."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(  # type: ignore[attr-defined]
            _item(**{"torznab:attr": [{"@name": "seeders"}, {"@value": "9"}, {"@name": "peers", "@value": "4"}]})
        )

        result = client.search("x")[0]

        assert result.seeders == 0
        assert result.leechers == 4

    @pytest.mark.parametrize(
        ("factor", "freeleech", "silverleech"),
        [("0", True, False), ("0.5", False, True), ("1", False, False)],
    )
    def test_downloadvolumefactor_maps_to_leech_flags(self, factor: str, freeleech: bool, silverleech: bool) -> None:
        """``downloadvolumefactor`` is the generic freeleech / silver-leech source."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(  # type: ignore[attr-defined]
            _item(**{"torznab:attr": [{"@name": "downloadvolumefactor", "@value": factor}]})
        )

        result = client.search("x")[0]

        assert (result.is_freeleech, result.is_silverleech) == (freeleech, silverleech)


class TestTmdbIdMapping:
    """The ``tmdbid`` attr feeds ``TrackerResult.tmdb_id`` — the anti-remake guard's input."""

    def test_numeric_attr_is_mapped(self) -> None:
        """A numeric ``tmdbid`` attr lands on the result as an int."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(  # type: ignore[attr-defined]
            _item(**{"torznab:attr": [{"@name": "tmdbid", "@value": "27205"}]})
        )

        assert client.search("x")[0].tmdb_id == 27205

    def test_absent_attr_yields_none(self) -> None:
        """No ``tmdbid`` attr → None, so the identity filter stays a no-op."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(_item())  # type: ignore[attr-defined]

        assert client.search("x")[0].tmdb_id is None

    @pytest.mark.parametrize("garbage", ["", "tt1375666", "27205.0", "not-a-number"])
    def test_non_integer_attr_yields_none_not_a_crash(self, garbage: str) -> None:
        """A non-numeric id (e.g. an imdb id in the wrong attr) degrades to None."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(  # type: ignore[attr-defined]
            _item(**{"torznab:attr": [{"@name": "tmdbid", "@value": garbage}]})
        )

        assert client.search("x")[0].tmdb_id is None

    def test_live_capture_carries_the_real_id(self) -> None:
        """The captured Inception search publishes TMDB 27205 — on 16 of its 18 items.

        The two id-less items are real: the indexer does not always fill
        ``tmdbid``. They must map to ``None`` (filter no-op), never to a guess.
        """
        client = _client(C411_DESCRIPTOR)
        client._transport.get.return_value = _load_xml("search-inception.xml")  # type: ignore[attr-defined]

        ids = [r.tmdb_id for r in client.search("Inception")]

        assert ids.count(27205) == 16
        assert ids.count(None) == 2

    def test_live_tv_capture_carries_the_show_id(self) -> None:
        """The captured tvsearch publishes the show's TMDB id (Breaking Bad = 1396)."""
        client = _client(C411_DESCRIPTOR)
        client._transport.get.return_value = _load_xml("tvsearch.xml")  # type: ignore[attr-defined]

        assert {r.tmdb_id for r in client.search("Breaking Bad", media_type="tv")} == {1396}


class TestDialectQuirks:
    """The two quirk flags select the field source — exclusively."""

    def test_category_source_follows_item_category_element(self) -> None:
        """attr-only dialect reads the attr; element dialect reads ``<category>``."""
        item = _item(category="7000")

        attr_dialect = _client(C411_DESCRIPTOR)
        attr_dialect._transport.get.return_value = _rss(item)  # type: ignore[attr-defined]
        assert attr_dialect.search("x")[0].category == "2030"

        element_dialect = _client(OTHER_DESCRIPTOR)
        element_dialect._transport.get.return_value = _rss(item)  # type: ignore[attr-defined]
        assert element_dialect.search("x")[0].category == "7000"

    def test_repeated_category_elements_take_the_first(self) -> None:
        """Newznab may repeat ``<category>``; the first usable value wins."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(_item(category=["5030", "5040"]))  # type: ignore[attr-defined]

        assert client.search("x")[0].category == "5030"

    def test_guid_with_xml_attributes_yields_its_text_only(self) -> None:
        """``<guid isPermaLink="true">`` decodes to a dict — only ``#text`` may surface.

        Live-observed on Tr4ker (2026-07-28): stringifying the node put
        ``"{'@isPermaLink': 'true', '#text': 'https://…'}"`` into ``tracker_id``.
        """
        permalink = "https://indexer.example/torrent/abc"
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _rss(  # type: ignore[attr-defined]
            _item(guid={"@isPermaLink": "true", "#text": permalink})
        )

        result = client.search("x")[0]

        assert result.tracker_id == permalink

    def test_attributed_guid_can_still_back_the_infohash(self) -> None:
        """A guid-as-infohash dialect that also sets XML attributes still resolves."""
        descriptor = replace(OTHER_DESCRIPTOR, guid_is_infohash=True)
        client = _client(descriptor)
        client._transport.get.return_value = _rss(  # type: ignore[attr-defined]
            _item(
                guid={"@isPermaLink": "false", "#text": "c" * 40},
                **{"torznab:attr": [{"@name": "seeders", "@value": "1"}]},
            )
        )

        assert client.search("x")[0].info_hash == "c" * 40

    def test_guid_backs_infohash_only_when_the_descriptor_says_so(self) -> None:
        """``guid_is_infohash`` decides whether ``<guid>`` may stand in for the attr."""
        item = _item(**{"torznab:attr": [{"@name": "seeders", "@value": "1"}]})

        guid_dialect = _client(C411_DESCRIPTOR)
        guid_dialect._transport.get.return_value = _rss(item)  # type: ignore[attr-defined]
        assert guid_dialect.search("x")[0].info_hash == "f" * 40

        opaque_guid_dialect = _client(OTHER_DESCRIPTOR)
        opaque_guid_dialect._transport.get.return_value = _rss(item)  # type: ignore[attr-defined]
        assert opaque_guid_dialect.search("x")[0].info_hash is None

    def test_infohash_attr_always_wins_over_guid(self) -> None:
        """When the indexer publishes an ``infohash`` attr, the quirk is irrelevant."""
        item = _item(**{"torznab:attr": [{"@name": "infohash", "@value": "a" * 40}]})

        for descriptor in (C411_DESCRIPTOR, OTHER_DESCRIPTOR):
            client = _client(descriptor)
            client._transport.get.return_value = _rss(item)  # type: ignore[attr-defined]
            assert client.search("x")[0].info_hash == "a" * 40

    def test_error_document_uses_the_descriptor_display_name(self) -> None:
        """A root ``<error/>`` with no description falls back to ``"<display_name> error"``."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = {"error": {"@code": "100"}}  # type: ignore[attr-defined]

        with pytest.raises(ApiError) as exc_info:
            client.search("x")

        assert exc_info.value.provider == "tr4ker"
        assert exc_info.value.http_status == 100
        assert exc_info.value.message == "Other error"

    def test_error_document_description_is_surfaced(self) -> None:
        """The live C411 auth-error capture parses the same way through the generic."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = _load_xml("error-auth.xml")  # type: ignore[attr-defined]

        with pytest.raises(ApiError) as exc_info:
            client.search("x")

        assert "Invalid API Key" in exc_info.value.message


class TestFailSoftContract:
    """Drift and network failures must stay swallowable by the registry."""

    @pytest.mark.parametrize(
        "drifted_response",
        [
            {"rss": "not-a-dict"},
            {"rss": {"channel": "not-a-dict"}},
            {"rss": {"channel": {"item": 42}}},
        ],
    )
    def test_malformed_payload_becomes_apierror(self, drifted_response: dict[str, Any]) -> None:
        """Parser drift surfaces as ApiError (the registry's swallow tuple), never raw."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.return_value = drifted_response  # type: ignore[attr-defined]

        with pytest.raises(ApiError) as exc_info:
            client.search("Inception")

        assert exc_info.value.provider == "tr4ker"
        assert exc_info.value.http_status == 0
        assert "shape drift" in exc_info.value.message

    def test_transport_timeout_propagates_as_requestexception(self) -> None:
        """A timeout is left as-is: the registry catches ``requests.RequestException``."""
        client = _client(OTHER_DESCRIPTOR)
        client._transport.get.side_effect = requests.Timeout("timed out")  # type: ignore[attr-defined]

        with pytest.raises(requests.Timeout):
            client.search("Inception")

    @pytest.mark.parametrize(
        "failure",
        [{"rss": "not-a-dict"}, requests.Timeout("timed out")],
        ids=["schema-drift", "timeout"],
    )
    def test_registry_survives_a_failing_torznab_tracker(self, failure: object) -> None:
        """End-to-end: a broken Torznab tracker never aborts the other trackers' results."""
        broken = _client(OTHER_DESCRIPTOR)
        if isinstance(failure, Exception):
            broken._transport.get.side_effect = failure  # type: ignore[attr-defined]
        else:
            broken._transport.get.return_value = failure  # type: ignore[attr-defined]

        registry = TrackerRegistry(
            trackers={"tr4ker": broken, "c411": _OkTracker("c411")},  # type: ignore[dict-item]
            priority=["tr4ker", "c411"],
            ranking=RankingConfig(min_seeders=0),
        )

        ranked = registry.search_all("Inception")

        assert [r.provider for r, _ in ranked] == ["c411"]
