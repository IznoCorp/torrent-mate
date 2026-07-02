"""Tests for the per-media-type priority feature (phase 12).

The registry accepts an optional ``priority_by_media_type`` map that
overrides the global ``priority`` order based on the ``media_type``
passed to :meth:`TrackerRegistry.search_all`. Unmapped media types fall
back to the global order.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import MagicMock

from personalscraper.api._contracts import MediaType
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


def _make_tracker(name: str, results: list[Any] | None = None) -> MagicMock:
    """Build a stub :class:`TorrentSearchable` returning a fixed result list."""
    m = MagicMock()
    m.search.return_value = results if results is not None else []
    return m


def _make_ranking() -> RankingConfig:
    """Build a minimal :class:`RankingConfig` for registry construction."""
    # The ranking config does not affect call-order tests ; an empty
    # config is enough since tests assert call ordering, not score.
    return RankingConfig()


def _make_side_effect(call_log: list[str], name: str) -> Callable[..., list[Any]]:
    """Build a side-effect that records *name* in *call_log* and returns [].

    Used as ``side_effect`` for mock ``search`` methods so each call is
    recorded in order without triggering a mypy ``func-returns-value``
    warning (``list.append`` returns ``None``, which compound expressions
    like ``.append(x) or []`` flag).
    """

    def side_effect(*args: Any, **kwargs: Any) -> list[Any]:
        call_log.append(name)
        return []

    return side_effect


def test_registry_uses_per_media_type_priority_when_match() -> None:
    """When the media type matches an override, that order is used."""
    call_log: list[str] = []
    lacale = _make_tracker("lacale")
    c411 = _make_tracker("c411")
    lacale.search.side_effect = _make_side_effect(call_log, "lacale")
    c411.search.side_effect = _make_side_effect(call_log, "c411")

    registry = TrackerRegistry(
        trackers={"lacale": lacale, "c411": c411},
        priority=["lacale", "c411"],
        ranking=_make_ranking(),
        priority_by_media_type={"movie": ["c411", "lacale"]},
    )
    registry.search_all("query", media_type=MediaType.MOVIE)
    assert call_log == ["c411", "lacale"]


def test_registry_falls_back_to_global_when_media_type_unmapped() -> None:
    """A media type with no override entry uses ``priority``."""
    call_log: list[str] = []
    lacale = _make_tracker("lacale")
    c411 = _make_tracker("c411")
    lacale.search.side_effect = _make_side_effect(call_log, "lacale")
    c411.search.side_effect = _make_side_effect(call_log, "c411")

    registry = TrackerRegistry(
        trackers={"lacale": lacale, "c411": c411},
        priority=["lacale", "c411"],
        ranking=_make_ranking(),
        priority_by_media_type={"tv": ["c411"]},
    )
    # MediaType.MOVIE has no override → fall back to global order.
    registry.search_all("query", media_type=MediaType.MOVIE)
    assert call_log == ["lacale", "c411"]


def test_registry_default_priority_when_map_is_none() -> None:
    """``priority_by_media_type=None`` keeps the original behaviour intact."""
    call_log: list[str] = []
    lacale = _make_tracker("lacale")
    c411 = _make_tracker("c411")
    lacale.search.side_effect = _make_side_effect(call_log, "lacale")
    c411.search.side_effect = _make_side_effect(call_log, "c411")

    registry = TrackerRegistry(
        trackers={"lacale": lacale, "c411": c411},
        priority=["lacale", "c411"],
        ranking=_make_ranking(),
        # ``priority_by_media_type`` defaults to ``None`` ; no kwarg passed.
    )
    registry.search_all("query", media_type=MediaType.MOVIE)
    assert call_log == ["lacale", "c411"]


def test_queryable_for_matches_search_candidates_queried_names() -> None:
    """``queryable_for`` returns the exact set ``search_candidates`` would query.

    Builds a real :class:`TrackerRegistry` with a ``priority_by_media_type``
    subset override and a client-None entry (tracker in priority but absent
    from the trackers dict).  Asserts that ``queryable_for("movie")`` equals
    the ``queried_names`` produced by ``search_candidates`` — the invariant the
    two share per DESIGN §6.4/6.7.
    """
    lacale = _make_tracker("lacale")
    torr9 = _make_tracker("torr9")

    # "fourth" appears in priority + the movie override but is NOT in the
    # trackers dict — simulates a client-None entry that both queryable_for
    # and search_candidates must skip.
    registry = TrackerRegistry(
        trackers={"lacale": lacale, "torr9": torr9},
        priority=["lacale", "torr9", "fourth"],
        ranking=_make_ranking(),
        priority_by_media_type={"movie": ["lacale", "torr9", "fourth"]},
    )

    # queryable_for: intersects priority with non-None trackers.
    assert registry.queryable_for("movie") == {"lacale", "torr9"}

    # search_candidates: queried_names must match queryable_for exactly.
    outcome = registry.search_candidates("test", MediaType.MOVIE)
    assert set(outcome.queried_names) == registry.queryable_for("movie")
