"""The ``auth`` taxon must be reachable from a REAL tracker search (D4).

``SearchOutcome.errors`` classifies each per-tracker failure as ``auth`` /
``circuit`` / ``api``, and a UNANIMOUS ``auth`` set is what lets the grab chain
state the terminal ``tracker_auth`` verdict instead of retrying a broken passkey
forever. That whole chain is worth nothing if no real client can produce the
``auth`` taxon in the first place.

It could not: :exc:`TrackerAuthError` was raised in exactly ONE place —
``fetch_torrent_source``, on the GRAB stage's torrent download — while every
tracker ``search()`` surfaced a broken key as a plain :exc:`ApiError`, taxon
``api``, verdict ``trackers_unavailable``. The registry's ``except
TrackerAuthError`` clause was dead code and the D4 verdict was unreachable, for
100 % of the configured trackers.

These tests therefore drive the REAL :class:`C411Client` and
:class:`Tr4kerClient` — the two enabled trackers — with the auth responses the
trackers really return, and assert the taxon and the exit path. A stub whose
``search()`` raises :exc:`TrackerAuthError` directly cannot prove this: it
asserts the classification of an exception nothing produced.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.orchestrator import _all_errored_exit_path
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.tracker._errors import TrackerAuthError
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.api.tracker.c411 import C411Client
from personalscraper.api.tracker.tr4ker import Tr4kerClient

#: The document C411 / Tr4ker return on a broken API key, as ``HttpTransport``
#: hands it over (xmltodict-decoded ``<error code="100" description="..."/>``).
_AUTH_ERROR_DOC = {"error": {"@code": "100", "@description": "Invalid API Key"}}


def _client(cls: type, *, raises: Exception | None = None, returns: object = None) -> object:
    """Build a REAL tracker client over a mocked transport."""
    transport = MagicMock()
    if raises is not None:
        transport.get.side_effect = raises
    else:
        transport.get.return_value = returns
    return cls(transport)


def _registry(**trackers: object) -> TrackerRegistry:
    """Build a registry over the given REAL clients, in declaration order."""
    return TrackerRegistry(
        trackers=trackers,  # type: ignore[arg-type]
        priority=list(trackers),
        ranking=RankingConfig(min_seeders=0),
    )


class TestRealClientsRaiseTheAuthError:
    """A broken key must surface as :exc:`TrackerAuthError` from ``search()``."""

    @pytest.mark.parametrize("cls", [C411Client, Tr4kerClient], ids=["c411", "tr4ker"])
    def test_auth_error_document(self, cls: type) -> None:
        """The ``<error code="100"/>`` document is an AUTH failure, not a generic one."""
        client = _client(cls, returns=_AUTH_ERROR_DOC)

        with pytest.raises(TrackerAuthError):
            client.search("Inception", MediaType.MOVIE, None)  # type: ignore[attr-defined]

    @pytest.mark.parametrize("status", [401, 403])
    def test_http_auth_status(self, status: int) -> None:
        """A transport-level 401/403 is an AUTH failure too (same rule as the fetch path)."""
        client = _client(
            C411Client,
            raises=ApiError(provider="c411", http_status=status, message="Forbidden"),
        )

        with pytest.raises(TrackerAuthError):
            client.search("Inception", MediaType.MOVIE, None)  # type: ignore[attr-defined]

    def test_a_non_auth_api_error_stays_generic(self) -> None:
        """A 500 must NOT be promoted to auth — that would abandon on an outage."""
        client = _client(
            C411Client,
            raises=ApiError(provider="c411", http_status=500, message="Boom"),
        )

        with pytest.raises(ApiError) as exc_info:
            client.search("Inception", MediaType.MOVIE, None)  # type: ignore[attr-defined]

        assert not isinstance(exc_info.value, TrackerAuthError)


class TestUnanimousAuthReachesTheTerminalVerdict:
    """End to end: real clients → taxa → exit path."""

    def test_all_trackers_broken_key_yields_tracker_auth(self) -> None:
        """The D4 headline, proven on the two enabled trackers."""
        registry = _registry(
            c411=_client(C411Client, returns=_AUTH_ERROR_DOC),
            tr4ker=_client(Tr4kerClient, returns=_AUTH_ERROR_DOC),
        )

        outcome = registry.search_candidates("Inception", MediaType.MOVIE, None)

        assert outcome.all_errored is True
        assert outcome.errors == {"c411": "auth", "tr4ker": "auth"}
        assert _all_errored_exit_path(outcome) == "tracker_auth"

    def test_a_mixed_failure_set_is_not_a_diagnosis(self) -> None:
        """One broken key plus one outage stays the historical label."""
        registry = _registry(
            c411=_client(C411Client, returns=_AUTH_ERROR_DOC),
            tr4ker=_client(
                Tr4kerClient,
                raises=ApiError(provider="tr4ker", http_status=500, message="Boom"),
            ),
        )

        outcome = registry.search_candidates("Inception", MediaType.MOVIE, None)

        assert outcome.errors == {"c411": "auth", "tr4ker": "api"}
        assert _all_errored_exit_path(outcome) == "trackers_unavailable"

    def test_errored_names_still_carries_both(self) -> None:
        """The historical view its consumers use (cross_seed) is unchanged."""
        registry = _registry(
            c411=_client(C411Client, returns=_AUTH_ERROR_DOC),
            tr4ker=_client(Tr4kerClient, returns=_AUTH_ERROR_DOC),
        )

        outcome = registry.search_candidates("Inception", MediaType.MOVIE, None)

        assert sorted(outcome.errored_names) == ["c411", "tr4ker"]
        assert sorted(outcome.queried_names) == ["c411", "tr4ker"]
        assert outcome.trackers_errored == 2


class TestExitPathTaxonomy:
    """``_all_errored_exit_path`` over the taxa sets it can receive."""

    @pytest.mark.parametrize(
        ("errors", "expected"),
        [
            ({"a": "auth", "b": "auth"}, "tracker_auth"),
            ({"a": "circuit", "b": "circuit"}, "circuit_open"),
            ({"a": "api", "b": "api"}, "trackers_unavailable"),
            ({"a": "auth", "b": "circuit"}, "trackers_unavailable"),
            ({}, "trackers_unavailable"),
        ],
        ids=["all-auth", "all-circuit", "all-api", "mixed", "empty"],
    )
    def test_only_a_unanimous_set_earns_a_specific_name(self, errors: dict[str, str], expected: str) -> None:
        """A partial failure is not a diagnosis."""
        outcome = SearchOutcome(
            results=[],
            trackers_queried=len(errors) or 1,
            trackers_errored=len(errors),
            errored_names=list(errors),
            queried_names=list(errors),
            errors=errors,
        )

        assert _all_errored_exit_path(outcome) == expected
