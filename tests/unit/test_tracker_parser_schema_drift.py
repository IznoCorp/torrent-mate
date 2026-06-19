"""Regression tests for c411 / lacale parser schema-drift wrapping.

PR #19 review finding I: the registry's narrowed except-tuple does NOT catch
``KeyError`` / ``IndexError`` / ``AttributeError`` (those are programming bugs
that should propagate). But trackers' parsers naturally surface those exact
exceptions when an upstream provider changes its response shape — which is an
*operational* failure, not a code bug. The fix is to wrap the parse call in
each tracker's ``search()`` and re-raise as ``ApiError`` so the registry can
swallow it and other trackers' results still rank.

This file pins both halves of the contract for c411 and lacale:
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
from personalscraper.api.tracker.lacale import LaCaleClient
from personalscraper.api.tracker.torr9 import Torr9Client

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


# -- LaCale ---------------------------------------------------------------


class TestLaCaleSchemaDriftReRaisedAsApiError:
    """lacale.search() must re-raise parser exceptions as ApiError."""

    def test_response_not_a_list(self) -> None:
        """LaCale always returns a JSON array; receiving a dict surfaces as ApiError."""
        transport = MagicMock()
        # LaCale parser expects list[dict]; receiving a dict triggers AttributeError
        # in [self._parse_item(item) for item in items] when item is the str key.
        transport.get.return_value = {"unexpected": "shape"}
        client = LaCaleClient(transport)

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "lacale"
        assert exc.value.http_status == 0
        assert "shape drift" in exc.value.message

    def test_item_missing_required_field(self) -> None:
        """Item with a structurally wrong sub-field surfaces as ApiError."""
        # 'size' is iterated through int/float/str; passing an object that
        # int() rejects after isinstance triggers a ValueError inside _parse_item.
        bad_items = [{"title": "x", "size": "not-a-number", "guid": "g"}]
        transport = MagicMock()
        transport.get.return_value = bad_items
        client = LaCaleClient(transport)

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "lacale"


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
    good = _OkTracker("lacale")

    registry = TrackerRegistry(
        trackers={"c411": bad_c411, "lacale": good},  # type: ignore[dict-item]
        priority=["c411", "lacale"],
        ranking=RankingConfig(min_seeders=0),
    )

    ranked = registry.search_all("Inception")

    assert len(ranked) == 1, f"Expected lacale's result to survive c411 schema drift; got {ranked!r}"
    assert ranked[0][0].provider == "lacale"


def test_lacale_schema_drift_does_not_abort_multi_tracker_search() -> None:
    """End-to-end: lacale parser blowing up must not kill other trackers' results."""
    transport = MagicMock()
    transport.get.return_value = {"unexpected": "shape"}
    bad_lacale = LaCaleClient(transport)
    good = _OkTracker("c411")

    registry = TrackerRegistry(
        trackers={"lacale": bad_lacale, "c411": good},  # type: ignore[dict-item]
        priority=["lacale", "c411"],
        ranking=RankingConfig(min_seeders=0),
    )

    ranked = registry.search_all("Inception")

    assert len(ranked) == 1, f"Expected c411's result to survive lacale schema drift; got {ranked!r}"
    assert ranked[0][0].provider == "c411"


# -- torr9 ----------------------------------------------------------------


class TestTorr9SchemaDriftReRaisedAsApiError:
    """torr9.search() must re-raise parser exceptions as ApiError."""

    def test_response_envelope_not_dict_raises_api_error(self) -> None:
        """A response that is a list (not a dict) → AttributeError → ApiError."""
        transport = MagicMock()
        transport.get.return_value = [{"id": 1}]  # list, not dict
        client = Torr9Client(transport, username="u", password="p")
        client._token = "t"

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "torr9"
        assert exc.value.http_status == 0
        assert "shape drift" in exc.value.message

    def test_item_file_size_bytes_wrong_type_raises_api_error(self) -> None:
        """An item where file_size_bytes is a dict → TypeError → ApiError."""
        transport = MagicMock()
        transport.get.return_value = {
            "torrents": [
                {
                    "id": 1,
                    "title": "x",
                    "file_size_bytes": {"nested": "object"},
                    "magnet_link": "magnet:?xt=urn:btih:aaa",
                    "is_freeleech": False,
                    "upload_date": None,
                    "category_id": 5,
                    "info_hash": "aaa",
                }
            ],
            "page": 1,
            "limit": 20,
        }
        client = Torr9Client(transport, username="u", password="p")
        client._token = "t"

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "torr9"
        assert "shape drift" in exc.value.message


def test_torr9_schema_drift_does_not_abort_multi_tracker_search() -> None:
    """End-to-end: torr9 parser blowing up must not kill other trackers' results."""
    transport = MagicMock()
    transport.get.return_value = [{"id": 1}]  # list, not dict → ApiError
    bad_torr9 = Torr9Client(transport, username="u", password="p")
    bad_torr9._token = "t"
    good = _OkTracker("lacale")

    registry = TrackerRegistry(
        trackers={"torr9": bad_torr9, "lacale": good},  # type: ignore[dict-item]
        priority=["torr9", "lacale"],
        ranking=RankingConfig(min_seeders=0),
    )

    ranked = registry.search_all("Inception")

    assert len(ranked) == 1, f"Expected lacale's result to survive torr9 drift; got {ranked!r}"
    assert ranked[0][0].provider == "lacale"
