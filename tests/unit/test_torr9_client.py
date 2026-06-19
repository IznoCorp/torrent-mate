"""Tests for torr9 tracker client — api/tracker/torr9.py.

Fixtures load real captures from docs/reference/_samples/torr9/.
Live samples captured 2026-06-19. Credentials and passkeys are redacted.
Tests NEVER hit the live torr9 API — transport is always mocked.
"""

from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker.torr9 import Torr9Client
from personalscraper.api.transport._auth import BearerAuth

_SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "reference" / "_samples" / "torr9"


def _load(name: str) -> object:
    """Load a real captured sample from the fixture directory."""
    with (_SAMPLES / name).open() as f:
        return json.load(f)


def _make_client() -> Torr9Client:
    """Build a Torr9Client with a mock transport injected via the setter.

    Assigning ``client._transport = MagicMock()`` caches the mock on the backing
    field, which short-circuits ``_ensure_transport`` — so no bootstrap login
    fires and ``client._transport.get`` returns the cached mock.
    """
    client = Torr9Client(username="user", password="pass", event_bus=MagicMock())
    client._transport = MagicMock()
    return client


def test_module_importable() -> None:
    """torr9 module imports cleanly."""
    from personalscraper.api.tracker.torr9 import Torr9Client  # noqa: F401


# ---------------------------------------------------------------------------
# Policy tests
# ---------------------------------------------------------------------------


class TestTorr9Policy:
    """Torr9Client.policy() builds a valid authed TransportPolicy."""

    def test_policy_uses_bearer_auth(self) -> None:
        """The main policy carries BearerAuth(token) — applied at transport init."""
        policy = Torr9Client.policy("jwt-token")
        assert isinstance(policy.auth, BearerAuth)
        assert policy.auth._token == "jwt-token"

    def test_policy_base_url(self) -> None:
        """Base URL points to the torr9 JSON API host."""
        policy = Torr9Client.policy("t")
        assert policy.base_url == "https://api.torr9.net"

    def test_policy_provider_name(self) -> None:
        """provider_name matches the registry key."""
        policy = Torr9Client.policy("t")
        assert policy.provider_name == "torr9"

    def test_policy_defensive_rate_limit(self) -> None:
        """Rate limit set to 0.5 rps (torr9 rate-limits aggressively)."""
        policy = Torr9Client.policy("t")
        assert policy.rate_limit.requests_per_second == 0.5

    def test_bootstrap_policy_uses_no_auth(self) -> None:
        """The one-shot bootstrap policy uses NoAuth (login exchange is credentialed in body)."""
        from personalscraper.api.transport._auth import NoAuth  # noqa: PLC0415

        policy = Torr9Client._bootstrap_policy()
        assert isinstance(policy.auth, NoAuth)
        assert policy.provider_name == "torr9-bootstrap"

    def test_required_creds(self) -> None:
        """REQUIRED_CREDS lists username + password for JWT login."""
        assert Torr9Client.REQUIRED_CREDS == ["TORR9_USERNAME", "TORR9_PASSWORD"]


# ---------------------------------------------------------------------------
# Bootstrap / lazy-transport tests (TVDB pattern)
# ---------------------------------------------------------------------------


class TestTorr9Bootstrap:
    """_ensure_transport bootstraps the login and builds the authed transport."""

    def test_bootstrap_posts_creds_and_builds_authed_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """First _ensure_transport POSTs creds and builds a BearerAuth main transport."""
        built_policies = []
        posted: dict[str, object] = {}

        class _FakeTransport:
            def __init__(self, policy: object, *, event_bus: object) -> None:
                built_policies.append(policy)

            def __enter__(self) -> _FakeTransport:
                return self

            def __exit__(self, *a: object) -> bool:
                return False

            def post(self, path: str, data: dict[str, str]) -> dict[str, str]:
                posted.update(path=path, data=data)
                return {"token": "jwt-xyz"}

            def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, object]:
                return {"torrents": []}

        monkeypatch.setattr("personalscraper.api.tracker.torr9.HttpTransport", _FakeTransport)
        client = Torr9Client(username="u", password="p", event_bus=MagicMock())

        transport = client._ensure_transport()

        assert posted["path"] == "/api/v1/auth/login"
        assert posted["data"] == {"username": "u", "password": "p"}
        # The bootstrap policy is built first (NoAuth), the main policy second (Bearer).
        assert isinstance(built_policies[-1].auth, BearerAuth)
        assert built_policies[-1].auth._token == "jwt-xyz"
        assert transport is not None

    def test_bootstrap_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A second _ensure_transport returns the cached transport (no second login POST)."""
        post_calls = 0

        class _FakeTransport:
            def __init__(self, policy: object, *, event_bus: object) -> None:
                pass

            def __enter__(self) -> _FakeTransport:
                return self

            def __exit__(self, *a: object) -> bool:
                return False

            def post(self, path: str, data: dict[str, str]) -> dict[str, str]:
                nonlocal post_calls
                post_calls += 1
                return {"token": "jwt-xyz"}

            def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, object]:
                return {"torrents": []}

        monkeypatch.setattr("personalscraper.api.tracker.torr9.HttpTransport", _FakeTransport)
        client = Torr9Client(username="u", password="p", event_bus=MagicMock())

        first = client._ensure_transport()
        second = client._ensure_transport()

        assert first is second
        assert post_calls == 1

    def test_bootstrap_missing_token_raises_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A login response without 'token' raises ApiError (fail-loud, RP7)."""

        class _FakeTransport:
            def __init__(self, policy: object, *, event_bus: object) -> None:
                pass

            def __enter__(self) -> _FakeTransport:
                return self

            def __exit__(self, *a: object) -> bool:
                return False

            def post(self, path: str, data: dict[str, str]) -> dict[str, str]:
                return {"error": "Identifiant ou mot de passe invalide"}

            def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, object]:
                return {}

        monkeypatch.setattr("personalscraper.api.tracker.torr9.HttpTransport", _FakeTransport)
        client = Torr9Client(username="u", password="p", event_bus=MagicMock())

        with pytest.raises(ApiError) as exc:
            client._ensure_transport()
        assert exc.value.provider == "torr9"
        assert "token" in exc.value.message

    def test_bootstrap_login_401_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 401 from the login POST (bad creds) propagates as ApiError."""

        class _FakeTransport:
            def __init__(self, policy: object, *, event_bus: object) -> None:
                pass

            def __enter__(self) -> _FakeTransport:
                return self

            def __exit__(self, *a: object) -> bool:
                return False

            def post(self, path: str, data: dict[str, str]) -> dict[str, str]:
                raise ApiError(provider="torr9", http_status=401, message="Identifiant ou mot de passe invalide")

            def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, object]:
                return {}

        monkeypatch.setattr("personalscraper.api.tracker.torr9.HttpTransport", _FakeTransport)
        client = Torr9Client(username="u", password="p", event_bus=MagicMock())

        with pytest.raises(ApiError) as exc:
            client._ensure_transport()
        assert exc.value.http_status == 401


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


class TestTorr9Search:
    """Torr9Client.search() — query param and re-login-on-401 behaviour."""

    def test_search_calls_correct_path_and_param(self) -> None:
        """search() hits /api/v1/torrents with q= param."""
        client = _make_client()
        client._transport.get.return_value = {"torrents": [], "limit": 20, "page": 1}  # type: ignore[attr-defined]

        client.search("Inception")

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/v1/torrents"
        assert kwargs["params"]["q"] == "Inception"

    def test_year_appended_to_query(self) -> None:
        """When year is given it is concatenated to q."""
        client = _make_client()
        client._transport.get.return_value = {"torrents": []}  # type: ignore[attr-defined]

        client.search("Inception", year=2010)

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["params"]["q"] == "Inception 2010"

    def test_search_relogin_on_401_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 401 from the search GET drops the transport, rebuilds it, and retries once."""
        client = _make_client()
        t1 = client._transport
        t1.get.side_effect = ApiError(  # type: ignore[attr-defined]
            provider="torr9", http_status=401, message="Missing authorization token"
        )

        # The rebuild returns a fresh transport whose GET succeeds.
        t2 = MagicMock()
        t2.get.return_value = {"torrents": [], "page": 1, "limit": 20}
        monkeypatch.setattr(client, "_ensure_transport", lambda: t2)

        results = client.search("Inception")

        assert results == []
        assert t2.get.call_count == 1  # the retry hit the rebuilt transport

    def test_search_second_consecutive_401_fails_loud(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A second 401 after re-login (persistently bad creds) propagates (RP7 fail-loud)."""
        client = _make_client()
        t1 = client._transport
        t1.get.side_effect = ApiError(  # type: ignore[attr-defined]
            provider="torr9", http_status=401, message="Missing authorization token"
        )

        t2 = MagicMock()
        t2.get.side_effect = ApiError(provider="torr9", http_status=401, message="Missing authorization token")
        monkeypatch.setattr(client, "_ensure_transport", lambda: t2)

        with pytest.raises(ApiError) as exc:
            client.search("Inception")
        assert exc.value.http_status == 401

    def test_search_empty_returns_empty_list(self) -> None:
        """An empty torrents array parses cleanly to []."""
        client = _make_client()
        client._transport.get.return_value = {"torrents": [], "limit": 20, "page": 1}  # type: ignore[attr-defined]

        assert client.search("zzzz_no_match") == []


# ---------------------------------------------------------------------------
# Golden fixture tests
# ---------------------------------------------------------------------------


class TestTorr9SearchGoldenFixture:
    """Golden-fixture parse tests against the real captured torr9_search.json.

    These tests are ANTI-VACUITY: they assert concrete values from the real
    payload, not just 'isinstance' or 'not None'. A stub-passable test that
    checks nothing specific will not catch real parse bugs (project memory:
    DeepSeek-written parsers pass make check while hiding real bugs).
    """

    def test_search_parses_two_results_from_golden_fixture(self) -> None:
        """Real payload has exactly 2 torrents in the captured slice."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        results = client.search("Oasis")

        assert len(results) == 2
        assert all(isinstance(r, TrackerResult) for r in results)
        assert all(r.provider == "torr9" for r in results)

    def test_first_item_title(self) -> None:
        """First result title matches exactly the golden fixture."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.title == "Oasis.2026.S01.MULTi.AD.1080p.NF.WEB.X264-THESYNDiCATE"

    def test_first_item_size_bytes(self) -> None:
        """Size parsed from file_size_bytes (exact bytes, not KB/MB)."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert isinstance(first.size, ByteSize)
        assert first.size.bytes == 20_827_331_134

    def test_first_item_magnet_link_as_download_url(self) -> None:
        """download_url is the magnet_link (auth-free, preferred)."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.download_url is not None
        assert first.download_url.startswith("magnet:?xt=urn:btih:")
        assert "d5638677f9986adc3ea155e7b753c36321cc30af" in first.download_url

    def test_first_item_info_hash(self) -> None:
        """info_hash matches the golden fixture value."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.info_hash == "d5638677f9986adc3ea155e7b753c36321cc30af"

    def test_first_item_is_not_freeleech(self) -> None:
        """is_freeleech is False for the first golden fixture item."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.is_freeleech is False

    def test_first_item_seeders_none_because_torr9_does_not_expose_swarm(self) -> None:
        """torr9 has no seeder data — seeders=0 on all results."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.seeders == 0
        assert first.leechers == 0

    def test_first_item_upload_date_iso(self) -> None:
        """upload_date parses from ISO 8601 with microseconds and Z suffix."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.upload_date is not None
        assert first.upload_date.tzinfo == timezone.utc
        assert first.upload_date.year == 2026
        assert first.upload_date.month == 6
        assert first.upload_date.day == 19

    def test_first_item_category_from_id_map(self) -> None:
        """category_id 5 maps to 'Séries TV' via _CATEGORY_MAP."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.category == "Séries TV"

    def test_second_item_category_from_id_map(self) -> None:
        """category_id 51 maps to 'Films' via _CATEGORY_MAP."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        second = client.search("Oasis")[1]
        assert second.title == "The.Fantastic.Four.1994.VOSTFR.DVDRip.x264.AC3-TeamLampion"
        assert second.category == "Films"
        assert second.size.bytes == 1_000_504_347

    def test_second_item_tracker_id(self) -> None:
        """tracker_id is the string of the JSON 'id' field."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        second = client.search("Oasis")[1]
        assert second.tracker_id == "305289"


# ---------------------------------------------------------------------------
# Parse-branch gap tests (download_url=None, category=None)
# ---------------------------------------------------------------------------


class TestTorr9ParseBranches:
    """_parse_item branch coverage for missing magnet and unmapped category."""

    def test_missing_magnet_leaves_download_url_none(self) -> None:
        """An item without magnet_link yields download_url=None (no torrent_file_url leak)."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "torrents": [
                {
                    "id": 7,
                    "title": "No Magnet Release",
                    "file_size_bytes": 1000,
                    # magnet_link intentionally absent
                    "torrent_file_url": "/dl/7.torrent",  # relative, must NOT leak
                    "is_freeleech": False,
                    "category_id": 5,
                    "info_hash": "abc",
                    "upload_date": None,
                }
            ]
        }

        result = client.search("x")[0]
        assert result.download_url is None

    def test_missing_magnet_emits_warning_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The None download_url path emits a torr9_missing_magnet warning breadcrumb."""
        warnings: list[tuple[str, dict[str, object]]] = []
        monkeypatch.setattr(
            "personalscraper.api.tracker.torr9.log.warning",
            lambda event, **kw: warnings.append((event, kw)),
        )
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "torrents": [{"id": 7, "title": "No Magnet", "file_size_bytes": 1, "category_id": 5}]
        }

        client.search("x")
        assert any(event == "torr9_missing_magnet" for event, _ in warnings)

    def test_unmapped_category_id_yields_none(self) -> None:
        """An item with an unmapped category_id (99999) yields category=None."""
        client = _make_client()
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "torrents": [
                {
                    "id": 8,
                    "title": "Mystery Category",
                    "file_size_bytes": 1000,
                    "magnet_link": "magnet:?xt=urn:btih:bbb",
                    "is_freeleech": False,
                    "category_id": 99999,  # not in _CATEGORY_MAP
                    "info_hash": "bbb",
                    "upload_date": None,
                }
            ]
        }

        result = client.search("x")[0]
        assert result.category is None


# ---------------------------------------------------------------------------
# Categories tests
# ---------------------------------------------------------------------------


class TestTorr9Categories:
    """Torr9Client.get_categories() — static map."""

    def test_get_categories_returns_str_keyed_map(self) -> None:
        """get_categories() returns string keys (str(category_id))."""
        client = _make_client()
        cats = client.get_categories()
        assert isinstance(cats, dict)
        assert all(isinstance(k, str) for k in cats)

    def test_get_categories_includes_known_ids(self) -> None:
        """Known category ids from golden fixture are present."""
        client = _make_client()
        cats = client.get_categories()
        assert cats["5"] == "Séries TV"
        assert cats["51"] == "Films"

    def test_get_categories_no_live_call(self) -> None:
        """get_categories() never calls the transport (static map)."""
        client = _make_client()
        client.get_categories()
        client._transport.get.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Malformed payload tests
# ---------------------------------------------------------------------------


class TestTorr9MalformedPayload:
    """Malformed response paths surface as ApiError via wrap_parser_drift."""

    def test_torrents_key_missing_raises_api_error(self) -> None:
        """Response missing 'torrents' key results in empty list (graceful .get)."""
        client = _make_client()
        client._transport.get.return_value = {"limit": 20, "page": 1}  # type: ignore[attr-defined]

        # .get("torrents") or [] gracefully handles missing key — no error.
        results = client.search("Oasis")
        assert results == []

    def test_item_with_wrong_size_type_raises_api_error(self) -> None:
        """An item with file_size_bytes of non-numeric type triggers ApiError via drift."""
        client = _make_client()
        # Force a parse error: file_size_bytes is a nested dict (unexpected type).
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "torrents": [
                {
                    "id": 1,
                    "title": "x",
                    "file_size_bytes": {"nested": "object"},  # wrong type → int() fails
                    "magnet_link": "magnet:?xt=urn:btih:aaa",
                    "is_freeleech": False,
                    "upload_date": None,
                    "category_id": 5,
                    "info_hash": "aaa",
                }
            ]
        }
        # int({"nested": "object"}) raises TypeError → wrap_parser_drift → ApiError
        with pytest.raises(ApiError) as exc:
            client.search("x")
        assert exc.value.provider == "torr9"
        assert "shape drift" in exc.value.message


# ---------------------------------------------------------------------------
# FreeleechAware re-check tests
# ---------------------------------------------------------------------------


class TestTorr9FreeleechRecheck:
    """is_freeleech(torrent_id) — pre-download re-check via GET /torrents/{id}.

    Anti-vacuity: asserts the re-check reads the real detail payload's
    is_freeleech field (golden fixture), the correct path, and the re-login path.
    """

    def test_is_freeleech_false_from_detail_fixture(self) -> None:
        """Re-check returns False from the real torr9_detail.json (id 305292)."""
        client = _make_client()
        client._transport.get.return_value = _load("torr9_detail.json")  # type: ignore[attr-defined]
        assert client.is_freeleech("305292") is False

    def test_is_freeleech_true_when_detail_flag_true(self) -> None:
        """Re-check returns True when the detail payload reports freeleech."""
        client = _make_client()
        detail = _load("torr9_detail.json")
        assert isinstance(detail, dict)  # narrow for mypy before mutating
        detail["is_freeleech"] = True
        client._transport.get.return_value = detail  # type: ignore[attr-defined]
        assert client.is_freeleech("305292") is True

    def test_is_freeleech_hits_detail_path(self) -> None:
        """Re-check calls GET /api/v1/torrents/{id}."""
        client = _make_client()
        client._transport.get.return_value = {"id": 999, "is_freeleech": False}  # type: ignore[attr-defined]
        client.is_freeleech("999")
        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/v1/torrents/999"

    def test_is_freeleech_missing_field_defaults_false(self) -> None:
        """A detail payload without is_freeleech defaults to False (graceful)."""
        client = _make_client()
        client._transport.get.return_value = {"id": 1, "title": "x"}  # type: ignore[attr-defined]
        assert client.is_freeleech("1") is False

    def test_is_freeleech_relogin_on_401_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 401 on the detail GET drops the transport, rebuilds it, and retries once."""
        client = _make_client()
        t1 = client._transport
        t1.get.side_effect = ApiError(  # type: ignore[attr-defined]
            provider="torr9", http_status=401, message="Missing authorization token"
        )

        t2 = MagicMock()
        t2.get.return_value = {"id": 1, "is_freeleech": True}
        monkeypatch.setattr(client, "_ensure_transport", lambda: t2)

        assert client.is_freeleech("305292") is True
        assert t2.get.call_count == 1

    def test_is_freeleech_second_consecutive_401_fails_loud(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A second 401 after re-login on the detail GET propagates (RP7 fail-loud)."""
        client = _make_client()
        t1 = client._transport
        t1.get.side_effect = ApiError(  # type: ignore[attr-defined]
            provider="torr9", http_status=401, message="Missing authorization token"
        )

        t2 = MagicMock()
        t2.get.side_effect = ApiError(provider="torr9", http_status=401, message="Missing authorization token")
        monkeypatch.setattr(client, "_ensure_transport", lambda: t2)

        with pytest.raises(ApiError) as exc:
            client.is_freeleech("305292")
        assert exc.value.http_status == 401

    def test_is_freeleech_non_dict_payload_raises_api_error(self) -> None:
        """A non-dict detail payload surfaces as ApiError via wrap_parser_drift."""
        client = _make_client()
        client._transport.get.return_value = [1, 2, 3]  # type: ignore[attr-defined]
        with pytest.raises(ApiError) as exc:
            client.is_freeleech("1")
        assert exc.value.provider == "torr9"
        assert "shape drift" in exc.value.message
