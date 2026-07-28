"""Tests for the Tr4ker tracker client — api/tracker/tr4ker.py.

Tr4ker carries no logic (the generic Torznab client does), so these tests pin
the two things a named config actually owns: its **descriptor** (base URL, API
path, auth parameter, transport tuning, dialect quirks) and its **activation**
(``TR4KER_API_KEY`` gates and is sent as the Torznab ``apikey=`` query param;
``TR4KER_PASSKEY`` is the announce passkey — a separate, non-gating secret).

The parsing tests run on the **real Tr4ker capture** taken by the ACC-03
controlled search on 2026-07-28
(``docs/reference/_samples/tr4ker/search-tvsearch.xml``, api keys redacted) —
which is also what settled the two dialect quirks below.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
import xmltodict  # type: ignore[import-untyped]

from personalscraper.api._activation import (
    PROVIDER_CREDS,
    PROVIDER_OPTIONAL_SECRETS,
    resolve_active,
    resolve_optional_secret,
)
from personalscraper.api._contracts import ProviderName
from personalscraper.api.tracker._contracts import (
    CategoryListable,
    FreeleechAware,
    TorrentDetailsProvider,
    TorrentSearchable,
)
from personalscraper.api.tracker.c411 import C411_DESCRIPTOR
from personalscraper.api.tracker.tr4ker import TR4KER_DESCRIPTOR, Tr4kerClient
from personalscraper.api.transport._auth import ApiKeyAuth
from personalscraper.core.event_bus import EventBus
from tests.unit.test_c411_client import _load_xml  # shared live Torznab capture — never copied

_TR4KER_SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "reference" / "_samples" / "tr4ker"


def _load_tr4ker_xml(name: str) -> dict[str, object]:
    """Load the captured Tr4ker XML and decode it through xmltodict (as HttpTransport does)."""
    with (_TR4KER_SAMPLES / name).open() as f:
        return cast("dict[str, object]", xmltodict.parse(f.read()))


def _client() -> Tr4kerClient:
    """Build a Tr4kerClient with a mocked HttpTransport."""
    return Tr4kerClient(MagicMock())


class TestTr4kerDescriptor:
    """The descriptor is the whole tracker — pin every field that reaches the wire."""

    def test_identity_and_endpoint(self) -> None:
        """Tr4ker is https://tr4ker.net with the /api/torznab Torznab path."""
        assert TR4KER_DESCRIPTOR.provider is ProviderName.TR4KER
        assert TR4KER_DESCRIPTOR.provider_name == "tr4ker"
        assert TR4KER_DESCRIPTOR.base_url == "https://tr4ker.net"
        assert TR4KER_DESCRIPTOR.api_path == "/api/torznab"

    def test_auth_is_the_api_key_query_param(self) -> None:
        """Auth is ``apikey=`` in query — the profile API key, never the passkey."""
        assert TR4KER_DESCRIPTOR.apikey_param == "apikey"
        assert TR4KER_DESCRIPTOR.apikey_location == "query"

    def test_dialect_quirks_match_the_live_capture(self) -> None:
        """Both quirks are what the ACC-03 capture shows, not the Torznab norm guess.

        The capture carries no per-item ``<category>`` element (the category is
        a ``torznab:attr``) and its ``<guid isPermaLink="true">`` holds a torrent
        permalink URL — so ``guid_is_infohash`` must be False for Tr4ker, unlike
        C411 whose guid IS the raw infohash.
        """
        assert TR4KER_DESCRIPTOR.item_category_element is False
        assert TR4KER_DESCRIPTOR.guid_is_infohash is False
        assert C411_DESCRIPTOR.guid_is_infohash is True, "the two dialects must stay distinguishable"

    def test_no_invented_category_ids(self) -> None:
        """No caps capture ⇒ no ``cat=`` narrowing (the RSS slugs are a different API)."""
        assert dict(TR4KER_DESCRIPTOR.search_categories) == {}

    def test_transport_tuning_matches_the_defensive_c411_profile(self) -> None:
        """Tr4ker documents only qualitative limits → reuse C411's defensive tuning."""
        assert TR4KER_DESCRIPTOR.timeout_seconds == C411_DESCRIPTOR.timeout_seconds
        assert TR4KER_DESCRIPTOR.retry == C411_DESCRIPTOR.retry
        assert TR4KER_DESCRIPTOR.circuit == C411_DESCRIPTOR.circuit
        assert TR4KER_DESCRIPTOR.rate_limit == C411_DESCRIPTOR.rate_limit

    def test_class_is_pure_configuration(self) -> None:
        """The named class adds no behaviour — only ClassVars over the generic."""
        own_callables = [
            name
            for name, value in vars(Tr4kerClient).items()
            if not name.startswith("__") and callable(getattr(value, "__func__", value))
        ]
        assert own_callables == [], f"Tr4kerClient must stay logic-free, found {own_callables}"


class TestTr4kerPolicy:
    """``policy()`` is the generic's, driven by the Tr4ker descriptor."""

    def test_policy_targets_tr4ker_over_xml(self) -> None:
        """Provider name, base URL and XML response format come from the descriptor."""
        policy = Tr4kerClient.policy("k")

        assert policy.provider_name == "tr4ker"
        assert policy.base_url == "https://tr4ker.net"
        assert policy.response_format == "xml"

    def test_policy_sends_the_key_as_apikey_query_param(self) -> None:
        """The API key travels as ``apikey=`` in the query string."""
        policy = Tr4kerClient.policy("secret")

        assert isinstance(policy.auth, ApiKeyAuth)
        assert policy.auth.auth_params() == {"apikey": "secret"}

    def test_policy_is_defensive(self) -> None:
        """15 s timeout, 3 attempts, 5-fail/300 s circuit, 0.5 rps (NE-DOIT-PAS-8)."""
        policy = Tr4kerClient.policy("k")

        assert policy.timeout_seconds == 15
        assert policy.retry.max_attempts == 3
        assert policy.circuit.failure_threshold == 5
        assert policy.circuit.cooldown_seconds == 300.0
        assert policy.rate_limit.requests_per_second == 0.5

    def test_from_env_builds_a_client_without_network(self) -> None:
        """``from_env`` builds a ready client from TR4KER_API_KEY, sent as ``apikey=``."""
        client = Tr4kerClient.from_env(
            env={"TR4KER_API_KEY": "secret"},
            event_bus=EventBus(),
            required=["TR4KER_API_KEY"],
            provider_cfg=MagicMock(),
        )

        assert isinstance(client, Tr4kerClient)
        assert client._open_transport._policy.auth.auth_params() == {"apikey": "secret"}


class TestTr4kerRequests:
    """URL + params construction, through the real generic engine."""

    @pytest.mark.parametrize(
        ("media_type", "expected_t"),
        [("movie", "movie"), ("tv", "tvsearch"), ("other", "search")],
    )
    def test_search_hits_the_torznab_path(self, media_type: str, expected_t: str) -> None:
        """Every search goes to /api/torznab with the Torznab ``t=`` operation."""
        client = _client()
        client._transport.get.return_value = {"rss": {"channel": {}}}  # type: ignore[attr-defined]

        client.search("Inception", media_type=media_type)  # type: ignore[arg-type]

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/torznab"
        assert kwargs["params"]["t"] == expected_t

    def test_search_sends_no_cat_filter(self) -> None:
        """Without a captured caps document, no ``cat=`` is invented."""
        client = _client()
        client._transport.get.return_value = {"rss": {"channel": {}}}  # type: ignore[attr-defined]

        client.search("Inception", media_type="movie")

        assert "cat" not in client._transport.get.call_args.kwargs["params"]  # type: ignore[attr-defined]

    def test_year_is_appended_to_the_query(self) -> None:
        """The year coalesces into ``q`` (shared generic behaviour)."""
        client = _client()
        client._transport.get.return_value = {"rss": {"channel": {}}}  # type: ignore[attr-defined]

        client.search("Inception", year=2010)

        assert client._transport.get.call_args.kwargs["params"]["q"] == "Inception 2010"  # type: ignore[attr-defined]

    def test_get_categories_hits_the_caps_endpoint(self) -> None:
        """``get_categories()`` asks /api/torznab?t=caps."""
        client = _client()
        client._transport.get.return_value = _load_xml("caps.xml")  # type: ignore[attr-defined]

        client.get_categories()

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/torznab"
        assert kwargs["params"]["t"] == "caps"

    def test_parses_the_live_capture(self) -> None:
        """The real ACC-03 ``t=tvsearch`` capture parses into six typed results."""
        client = _client()
        client._transport.get.return_value = _load_tr4ker_xml("search-tvsearch.xml")  # type: ignore[attr-defined]

        results = client.search("Furious S01E01", media_type="tv")

        assert len(results) == 6
        assert {r.provider for r in results} == {"tr4ker"}
        first = results[0]
        assert first.title == "Furious.S01E01.MULTi.1080p.WEB.EAC3.5.1.H264-SUPPLY"
        assert first.seeders == 34
        assert first.leechers == 3  # peers(37) - seeders(34); matches the published leechers attr
        assert first.size.bytes == 2_073_464_381
        assert first.category == "5000"
        assert first.tmdb_id == 287238
        assert first.resolution == "1080p"
        assert first.codec == "H264"

    def test_infohash_comes_from_the_attr_not_the_guid(self) -> None:
        """Tr4ker's guid is a permalink, so the infohash MUST come from the attr."""
        client = _client()
        client._transport.get.return_value = _load_tr4ker_xml("search-tvsearch.xml")  # type: ignore[attr-defined]

        first = client.search("Furious S01E01", media_type="tv")[0]

        assert first.info_hash == "b4e83b4ef9356f86a1469bfdd73e718347d9f153"

    def test_tracker_id_is_the_guid_text_not_a_dict_repr(self) -> None:
        """``<guid isPermaLink="true">`` decodes to a dict — only its text may surface.

        Regression: stringifying the node produced
        ``"{'@isPermaLink': 'true', '#text': 'https://…'}"`` as ``tracker_id``
        (live-observed on the ACC-03 capture before the fix).
        """
        client = _client()
        client._transport.get.return_value = _load_tr4ker_xml("search-tvsearch.xml")  # type: ignore[attr-defined]

        first = client.search("Furious S01E01", media_type="tv")[0]

        assert first.tracker_id.startswith("https://tr4ker.net/torrent/")
        assert "@isPermaLink" not in first.tracker_id
        assert "#text" not in first.tracker_id


class TestTr4kerCapabilities:
    """Capability composition — same accurate shape as C411 (DESIGN §4)."""

    def test_is_torrent_searchable(self) -> None:
        """``Tr4kerClient`` satisfies the ``TorrentSearchable`` capability."""
        assert isinstance(_client(), TorrentSearchable)

    def test_is_category_listable(self) -> None:
        """``Tr4kerClient`` satisfies the ``CategoryListable`` capability."""
        assert isinstance(_client(), CategoryListable)

    def test_is_not_freeleech_aware(self) -> None:
        """Torznab has no freeleech re-check endpoint — the capability is not advertised."""
        assert not isinstance(_client(), FreeleechAware)

    def test_is_not_details_provider(self) -> None:
        """Torznab has no per-torrent detail endpoint."""
        assert not isinstance(_client(), TorrentDetailsProvider)


class TestTr4kerActivation:
    """Activation gating — the API key gates, the announce passkey never does."""

    def test_api_key_is_the_gating_credential(self) -> None:
        """``PROVIDER_CREDS`` requires exactly TR4KER_API_KEY (it authenticates the API)."""
        assert PROVIDER_CREDS["tr4ker"] == ["TR4KER_API_KEY"]
        assert Tr4kerClient.REQUIRED_CREDS == ["TR4KER_API_KEY"]

    def test_passkey_is_declared_optional_and_non_gating(self) -> None:
        """The announce passkey is a separate, NON-gating secret (RSS radar R1)."""
        assert PROVIDER_OPTIONAL_SECRETS["tr4ker"] == ["TR4KER_PASSKEY"]
        assert resolve_optional_secret("tr4ker", env={"TR4KER_PASSKEY": "v"}) == {"TR4KER_PASSKEY": "v"}
        assert resolve_optional_secret("tr4ker", env={}) == {"TR4KER_PASSKEY": None}

    def test_api_key_present_activates_the_tracker_without_the_passkey(self) -> None:
        """The API key alone activates tr4ker — a missing passkey never deactivates it."""
        env = {"TR4KER_API_KEY": "key_value"}  # passkey intentionally absent

        active = resolve_active({"tr4ker": MagicMock(enabled=True)}, "tracker", env=env)

        assert active == ["tr4ker"]
        assert resolve_optional_secret("tr4ker", env=env) == {"TR4KER_PASSKEY": None}

    def test_passkey_alone_does_not_activate_the_tracker(self) -> None:
        """The two secrets are NOT interchangeable: the passkey cannot stand in for the key."""
        active = resolve_active(
            {"tr4ker": MagicMock(enabled=True)},
            "tracker",
            env={"TR4KER_PASSKEY": "announce_only"},
        )

        assert active == []

    def test_missing_api_key_deactivates_with_a_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """No TR4KER_API_KEY ⇒ tr4ker is skipped and the reason is logged (not silent)."""
        with caplog.at_level("WARNING"):
            active = resolve_active({"tr4ker": MagicMock(enabled=True)}, "tracker", env={})

        assert active == []
        assert "TR4KER_API_KEY" in caplog.text

    def test_login_credentials_are_not_wired(self) -> None:
        """TR4KER_USERNAME / TR4KER_PASSWORD are decommissioned-tracker leftovers — never required."""
        assert "TR4KER_USERNAME" not in PROVIDER_CREDS["tr4ker"]
        assert "TR4KER_PASSWORD" not in PROVIDER_CREDS["tr4ker"]

    def test_the_two_secrets_have_distinct_roles(self) -> None:
        """Both variables exist and never cross: key gates the API, passkey stays optional."""
        assert PROVIDER_CREDS["tr4ker"] == ["TR4KER_API_KEY"]
        assert PROVIDER_OPTIONAL_SECRETS["tr4ker"] == ["TR4KER_PASSKEY"]
        assert "TR4KER_PASSKEY" not in PROVIDER_CREDS["tr4ker"]
        assert "TR4KER_API_KEY" not in PROVIDER_OPTIONAL_SECRETS["tr4ker"]
