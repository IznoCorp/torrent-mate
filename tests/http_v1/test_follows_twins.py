"""The v0 follows routes say they are replaced: their ``Deprecation`` header and the v1 successor they name.

v0 names a follow by its rowid and v1 by the medium's key; the rowid cannot be turned into the key
without the store, so the item routes' ``Link`` names the v1 collection (where each follow answers by
its key) and never a successor filled with a rowid, which would name no follow.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from personalscraper.conf.models.config import Config
from personalscraper.http_v1 import deprecations
from personalscraper.http_v1.deprecations import V0_TWINS
from tests.http_v1.test_deprecations import _client

#: The v0 route → the v1 operation that replaces it.
TWINS = {
    ("GET", "/api/acquisition/followed"): "readFollows",
    ("POST", "/api/acquisition/followed"): "createFollow",
    ("PATCH", "/api/acquisition/followed/{followed_id}"): "updateFollow",
    ("DELETE", "/api/acquisition/followed/{followed_id}"): "deleteFollow",
    ("GET", "/api/acquisition/followed/{followed_id}/completeness"): "readFollowCompleteness",
}


def test_every_v0_follows_route_with_a_v1_twin_is_registered() -> None:
    """The five v0 routes the nine operations replace are in the register, under their v1 operation."""
    assert {route: V0_TWINS[route].operation_id for route in TWINS} == TWINS


def test_a_v0_route_without_a_v1_twin_is_not_registered() -> None:
    """v0 has no restore, quality, pause nor reassign: nothing is registered for them."""
    assert [route for route in V0_TWINS if "restore" in route[1] or "requesters" in route[1]] == []


def test_the_collection_twins_name_the_v1_collection() -> None:
    """``GET`` and ``POST /followed`` name ``/api/v1/acquisition/followed`` as their successor."""
    for method in ("GET", "POST"):
        twin = V0_TWINS[(method, "/api/acquisition/followed")]
        assert deprecations._successor_uri(twin, {}) == "/api/v1/acquisition/followed"


@pytest.mark.parametrize(
    "route",
    [
        ("PATCH", "/api/acquisition/followed/{followed_id}"),
        ("DELETE", "/api/acquisition/followed/{followed_id}"),
        ("GET", "/api/acquisition/followed/{followed_id}/completeness"),
    ],
)
def test_an_item_twin_never_fills_the_key_with_a_v0_rowid(route: tuple[str, str]) -> None:
    """A rowid in a v1 key's place would name no follow: the ``Link`` is the collection the key is read from."""
    twin = V0_TWINS[route]

    assert deprecations._link_target(twin, {"followed_id": 17}) == "/api/v1/acquisition/followed"


def test_a_v0_follows_response_carries_the_deprecation_and_its_successor(test_config: Config) -> None:
    """v1 mounted: ``GET /api/acquisition/followed`` says it is deprecated and names the v1 operation."""
    client: TestClient = _client(test_config, v1_enabled=True)

    response = client.get("/api/acquisition/followed")

    assert response.headers["deprecation"] == "@1795737600"  # 2026-11-27 00:00 UTC
    assert response.headers["link"] == '</api/v1/acquisition/followed>; rel="successor-version"'
