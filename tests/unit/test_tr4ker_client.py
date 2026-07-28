"""Tests for the Tr4ker tracker client — api/tracker/tr4ker.py.

Tr4ker carries no logic (the generic Torznab client does), so these tests pin
the two things a named config actually owns: its **descriptor** (base URL, API
path, auth parameter, transport tuning, dialect quirks) and its **activation**
(the single ``TR4KER_PASSKEY`` secret, gating, whose value is sent as the
Torznab ``apikey=`` query param).

No live Tr4ker capture exists yet (the feature's ACC-03 controlled search will
produce one). Rather than fabricate a fake sample, the parsing test feeds the
**C411 live capture** through the Tr4ker client: same protocol, same parser —
what it proves is that the named config decodes a real Torznab document and
tags the results with its own provider name.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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
        """``from_env`` builds a ready client from TR4KER_PASSKEY, sent as ``apikey=``."""
        client = Tr4kerClient.from_env(
            env={"TR4KER_PASSKEY": "secret"},
            event_bus=EventBus(),
            required=["TR4KER_PASSKEY"],
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

    def test_parses_a_real_torznab_document(self) -> None:
        """A real Torznab RSS document parses and is tagged with the tr4ker provider.

        The fixture is the C411 live capture (no Tr4ker capture exists before
        ACC-03) — the point is protocol conformance, not Tr4ker's own catalog.
        """
        client = _client()
        client._transport.get.return_value = _load_xml("search-inception.xml")  # type: ignore[attr-defined]

        results = client.search("Inception")

        assert len(results) == 18
        assert {r.provider for r in results} == {"tr4ker"}
        first = results[0]
        assert first.seeders == 141
        assert first.size.bytes == 7_396_633_907
        assert first.info_hash == "b08b70d0855318efa71aeccce0ae42b3e4493113"


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
    """Activation gating — API key gates, passkey never does."""

    def test_passkey_is_the_single_gating_credential(self) -> None:
        """``PROVIDER_CREDS`` requires exactly TR4KER_PASSKEY — the operator convention."""
        assert PROVIDER_CREDS["tr4ker"] == ["TR4KER_PASSKEY"]
        assert Tr4kerClient.REQUIRED_CREDS == ["TR4KER_PASSKEY"]

    def test_passkey_is_not_also_declared_optional(self) -> None:
        """The gating secret must not appear as a non-gating optional secret."""
        assert "tr4ker" not in PROVIDER_OPTIONAL_SECRETS
        assert resolve_optional_secret("tr4ker", env={"TR4KER_PASSKEY": "v"}) == {}

    def test_passkey_present_activates_the_tracker(self) -> None:
        """With TR4KER_PASSKEY set, tr4ker resolves as active."""
        active = resolve_active(
            {"tr4ker": MagicMock(enabled=True)},
            "tracker",
            env={"TR4KER_PASSKEY": "key_value"},
        )

        assert active == ["tr4ker"]

    def test_missing_passkey_deactivates_with_a_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """No TR4KER_PASSKEY ⇒ tr4ker is skipped and the reason is logged (not silent)."""
        with caplog.at_level("WARNING"):
            active = resolve_active({"tr4ker": MagicMock(enabled=True)}, "tracker", env={})

        assert active == []
        assert "TR4KER_PASSKEY" in caplog.text

    def test_login_credentials_are_not_wired(self) -> None:
        """TR4KER_USERNAME / TR4KER_PASSWORD are decommissioned-tracker leftovers — never required."""
        assert "TR4KER_USERNAME" not in PROVIDER_CREDS["tr4ker"]
        assert "TR4KER_PASSWORD" not in PROVIDER_CREDS["tr4ker"]

    def test_no_second_api_key_variable_exists(self) -> None:
        """One secret only: no ``TR4KER_API_KEY`` variable anywhere in the wiring."""
        assert "TR4KER_API_KEY" not in PROVIDER_CREDS["tr4ker"]
        assert all("TR4KER_API_KEY" not in keys for keys in PROVIDER_OPTIONAL_SECRETS.values())
