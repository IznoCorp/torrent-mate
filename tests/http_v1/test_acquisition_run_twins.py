"""The v0 run routes say they are replaced: their ``Deprecation`` header and the v1 successor they name.

The routes keyed by a v0 rowid name the v1 collection in their ``Link`` (a rowid in a key's place
would name no follow), as the follows' twins do.
"""

from __future__ import annotations

import pytest

from personalscraper.http_v1 import deprecations
from personalscraper.http_v1.deprecations import V0_TWINS

#: The v0 route → the v1 operation that replaces it.
TWINS = {
    ("GET", "/api/acquisition/status"): "readAcquisitionStatus",
    ("POST", "/api/acquisition/detect"): "runDetection",
    ("POST", "/api/acquisition/followed/{followed_id}/search"): "searchForFollow",
    ("POST", "/api/acquisition/followed/{followed_id}/grab"): "grabForFollow",
    ("POST", "/api/acquisition/follows/{followed_id}/seasons/{season}/grab"): "grabSeasonForFollow",
}


def test_every_v0_run_route_with_a_v1_twin_is_registered() -> None:
    """The five v0 routes the run operations replace are in the register, under their v1 operation."""
    assert {route: V0_TWINS[route].operation_id for route in TWINS if route in V0_TWINS} == TWINS


@pytest.mark.parametrize("route", [route for route in TWINS if "{followed_id}" in route[1]])
def test_a_keyed_twin_never_fills_the_key_with_a_v0_rowid(route: tuple[str, str]) -> None:
    """The ``Link`` of a route keyed by a rowid is the collection the key is read from."""
    twin = V0_TWINS[route]

    assert deprecations._link_target(twin, {"followed_id": 17, "season": 2}) == "/api/v1/acquisition/followed"


@pytest.mark.parametrize(
    ("route", "successor"),
    [
        (("GET", "/api/acquisition/status"), "/api/v1/acquisition/status"),
        (("POST", "/api/acquisition/detect"), "/api/v1/acquisition/detect"),
    ],
)
def test_an_unkeyed_twin_names_its_successor(route: tuple[str, str], successor: str) -> None:
    """A route with no key names the v1 route itself."""
    assert deprecations._link_target(V0_TWINS[route], {}) == successor
