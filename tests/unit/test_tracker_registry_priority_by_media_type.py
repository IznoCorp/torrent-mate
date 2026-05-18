"""Tests for the per-media-type priority feature (phase 12).

The registry accepts an optional ``priority_by_media_type`` map that
overrides the global ``priority`` order based on the ``media_type``
passed to :meth:`TrackerRegistry.search_all`. Unmapped media types fall
back to the global order.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api._contracts import MediaType
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


def _make_tracker(name: str, results: list = None) -> MagicMock:  # type: ignore[no-untyped-def]
    """Build a stub :class:`TorrentSearchable` returning a fixed result list."""
    m = MagicMock()
    m.search.return_value = results or []
    return m


def _make_ranking() -> RankingConfig:
    """Build a minimal :class:`RankingConfig` for registry construction."""
    # The ranking config does not affect call-order tests ; an empty
    # config is enough since tests assert call ordering, not score.
    return RankingConfig()


def test_registry_uses_per_media_type_priority_when_match() -> None:
    """When the media type matches an override, that order is used."""
    call_log: list[str] = []
    lacale = _make_tracker("lacale")
    c411 = _make_tracker("c411")

    def _record(name: str, m: MagicMock) -> MagicMock:
        m.search.side_effect = lambda *args, **kwargs: call_log.append(name) or []
        return m

    _record("lacale", lacale)
    _record("c411", c411)

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
    lacale.search.side_effect = lambda *args, **kwargs: call_log.append("lacale") or []
    c411.search.side_effect = lambda *args, **kwargs: call_log.append("c411") or []

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
    lacale.search.side_effect = lambda *args, **kwargs: call_log.append("lacale") or []
    c411.search.side_effect = lambda *args, **kwargs: call_log.append("c411") or []

    registry = TrackerRegistry(
        trackers={"lacale": lacale, "c411": c411},
        priority=["lacale", "c411"],
        ranking=_make_ranking(),
        # ``priority_by_media_type`` defaults to ``None`` ; no kwarg passed.
    )
    registry.search_all("query", media_type=MediaType.MOVIE)
    assert call_log == ["lacale", "c411"]
