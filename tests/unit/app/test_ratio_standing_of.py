"""``ratio_standing_of``: the preview's standing resolver, reading ``ratio_state`` on every call.

The grab fills ``TrackerResult.tracker_ratio_state`` from ``RatioStanding``; the preview must read the
same derivation, never off a ranked result. Dormant until K5 writes ``ratio_state`` (O-8 A).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import RatioState
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.composition import ratio_standing_of
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import TrackerEconomyConfig

_ECONOMY = TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time="72h")


@pytest.fixture
def opened(tmp_path: Path) -> Iterator[list[ConcreteAcquireStore]]:
    """Collect the stores the resolver opens, and close any left at teardown.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        The list the opener appends to.
    """
    stores: list[ConcreteAcquireStore] = []
    yield stores
    for store in stores:
        store.close()


def _opener(tmp_path: Path, opened: list[ConcreteAcquireStore]):  # noqa: ANN202 — a test helper returning a lambda
    """Build an opener over the temp ``acquire.db`` that records each store it hands out.

    Args:
        tmp_path: Pytest temp directory.
        opened: Where each opened store is noted.

    Returns:
        The opener.
    """

    def open_store() -> ConcreteAcquireStore:
        store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
        opened.append(store)
        return store

    return open_store


def test_a_tracker_without_an_economy_has_no_standing_and_opens_nothing(
    tmp_path: Path, opened: list[ConcreteAcquireStore]
) -> None:
    """No policy, no standing: a ratio alone says nothing without a floor, so the store is not touched."""
    standing_of = ratio_standing_of(_opener(tmp_path, opened), {})

    assert standing_of("c411") is None
    assert opened == []


def test_a_tracker_with_an_economy_and_no_recorded_ratio_has_no_standing(
    tmp_path: Path, opened: list[ConcreteAcquireStore]
) -> None:
    """Until K5 writes ``ratio_state`` every standing reads ``None``."""
    assert ratio_standing_of(_opener(tmp_path, opened), {"tr4ker": _ECONOMY})("tr4ker") is None


def test_a_recorded_ratio_is_read_against_the_trackers_own_economy(
    tmp_path: Path, opened: list[ConcreteAcquireStore]
) -> None:
    """The standing follows the ratio as written, read afresh at each call."""
    standing_of = ratio_standing_of(_opener(tmp_path, opened), {"tr4ker": _ECONOMY})
    writer = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    opened.append(writer)

    writer.ratio.upsert(RatioState("tr4ker", 0.4, 0, 0, 1))
    assert standing_of("tr4ker") == "under_floor"
    writer.ratio.upsert(RatioState("tr4ker", 1.5, 0, 0, 2))
    assert standing_of("tr4ker") == "under_target"
    writer.ratio.upsert(RatioState("tr4ker", 3.0, 0, 0, 3))
    assert standing_of("tr4ker") == "comfortable"
