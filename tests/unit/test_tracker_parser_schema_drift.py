"""Regression tests for tracker parser schema-drift wrapping.

PR #19 review finding I: the registry's narrowed except-tuple does NOT catch
``KeyError`` / ``IndexError`` / ``AttributeError`` (those are programming bugs
that should propagate). But trackers' parsers naturally surface those exact
exceptions when an upstream provider changes its response shape — which is an
*operational* failure, not a code bug. The fix is to wrap the parse call in
each tracker's ``search()`` and re-raise as ``ApiError`` so the registry can
swallow it and other trackers' results still rank.

This file pins both halves of the contract for the live tracker clients
(c411 and tr4ker; the generic Torznab engine behind them is covered the same
way in ``test_torznab_client.py``):
1. Schema drift surfacing as KeyError/IndexError/TypeError/AttributeError must
   become ``ApiError`` carrying provider name and a useful message.
2. The wrapped ApiError must be in the registry's swallow tuple — i.e. the
   end-to-end multi-tracker scenario continues to return surviving results.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.api.tracker.c411 import C411Client
from personalscraper.api.tracker.tr4ker import Tr4kerClient

# -- C411 -----------------------------------------------------------------


class TestC411SchemaDriftReRaisedAsApiError:
    """c411.search() must re-raise parser exceptions as ApiError."""

    @pytest.mark.parametrize(
        "drifted_response",
        [
            # rss with non-dict channel — _parse_rss expects channel.get(...)
            {"rss": {"channel": "not-a-dict"}},
            # rss.channel.item is a single dict whose 'guid' is missing
            # but the code uses .get(...) — instead force a TypeError on
            # nested attribute access via a non-dict where dict is expected.
            {"rss": "not-a-dict"},
        ],
    )
    def test_drift_in_root_shape(self, drifted_response: dict[str, Any]) -> None:
        """A response shape mismatch surfaces as ApiError, not raw TypeError/AttributeError."""
        transport = MagicMock()
        transport.get.return_value = drifted_response
        client = C411Client(transport)

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "c411"
        assert exc.value.http_status == 0
        assert "shape drift" in exc.value.message

    def test_drift_inside_item(self) -> None:
        """Per-item drift (e.g. attrs not a list) surfaces as ApiError."""
        # _attrs_to_dict expects a list/dict shape; passing an int triggers
        # parser failure inside _parse_item.
        drifted: dict[str, Any] = {
            "rss": {
                "channel": {
                    "item": [
                        {"title": "x", "torznab:attr": 12345, "guid": "g"},
                    ]
                }
            }
        }
        transport = MagicMock()
        transport.get.return_value = drifted
        client = C411Client(transport)

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "c411"
        assert "shape drift" in exc.value.message


# -- Tr4ker ---------------------------------------------------------------


class TestTr4kerSchemaDriftReRaisedAsApiError:
    """tr4ker.search() must re-raise parser exceptions as ApiError."""

    def test_response_root_shape_drift(self) -> None:
        """A non-dict RSS envelope surfaces as ApiError, not raw TypeError/AttributeError."""
        transport = MagicMock()
        transport.get.return_value = {"rss": "not-a-dict"}
        client = Tr4kerClient(transport)

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "tr4ker"
        assert exc.value.http_status == 0
        assert "shape drift" in exc.value.message


# -- Registry-level integration ------------------------------------------


def _result(provider: str) -> TrackerResult:
    return TrackerResult(
        provider=provider,
        tracker_id=f"{provider}-1",
        title="Inception",
        size=ByteSize(bytes=1_000_000_000),
        seeders=10,
        leechers=1,
    )


class _OkTracker:
    """Stub tracker returning a single result so we can verify survival semantics."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def search(self, query: str, media_type: str = "movie", year: int | None = None) -> list[TrackerResult]:
        return [_result(self.provider)]

    def get_categories(self) -> dict[str, str]:
        return {}


def test_c411_schema_drift_does_not_abort_multi_tracker_search() -> None:
    """End-to-end: c411 parser blowing up must not kill other trackers' results."""
    transport = MagicMock()
    transport.get.return_value = {"rss": "not-a-dict"}
    bad_c411 = C411Client(transport)
    good = _OkTracker("tr4ker")

    registry = TrackerRegistry(
        trackers={"c411": bad_c411, "tr4ker": good},  # type: ignore[dict-item]
        priority=["c411", "tr4ker"],
        ranking=RankingConfig(min_seeders=0),
    )

    ranked = registry.search_all("Inception")

    assert len(ranked) == 1, f"Expected tr4ker's result to survive c411 schema drift; got {ranked!r}"
    assert ranked[0][0].provider == "tr4ker"


def test_tr4ker_schema_drift_does_not_abort_multi_tracker_search() -> None:
    """End-to-end: tr4ker parser blowing up must not kill other trackers' results."""
    transport = MagicMock()
    transport.get.return_value = {"rss": "not-a-dict"}
    bad_tr4ker = Tr4kerClient(transport)
    good = _OkTracker("c411")

    registry = TrackerRegistry(
        trackers={"tr4ker": bad_tr4ker, "c411": good},  # type: ignore[dict-item]
        priority=["tr4ker", "c411"],
        ranking=RankingConfig(min_seeders=0),
    )

    ranked = registry.search_all("Inception")

    assert len(ranked) == 1, f"Expected c411's result to survive tr4ker schema drift; got {ranked!r}"
    assert ranked[0][0].provider == "c411"
