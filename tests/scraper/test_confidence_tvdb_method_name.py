"""Regression guard for confidence.get_episode_titles — TVDB method name.

Bug detected during PR #19 review: ``confidence.py`` called
``tvdb_client.get_season_episodes(...)`` which does NOT exist on
``TVDBClient`` — the real method is ``get_series_episodes``. The bug was
masked by ``# type: ignore[attr-defined]`` (since the parameter is typed
``object``) and by ``MagicMock`` in tests, which auto-creates any attribute.
Against the real client at runtime, the call would raise ``AttributeError``.

Behavioural pins:
- ``TVDBClient.get_series_episodes`` exists and accepts (series_id, season).
- ``TVDBClient.get_season_episodes`` does NOT exist (would be the buggy name).
- ``get_episode_titles`` invokes the real method on a non-Mock fake — Mock
  would mask the wrong-name regression by auto-creating any attribute.
"""

from __future__ import annotations

import inspect

import pytest

from personalscraper.api.metadata._base import EpisodeInfo, SeasonDetails
from personalscraper.api.metadata.tvdb import TVDBClient
from personalscraper.scraper.confidence import MatchResult, get_episode_titles


def test_tvdb_client_exposes_get_series_episodes() -> None:
    """``TVDBClient.get_series_episodes`` must exist and be callable."""
    assert hasattr(TVDBClient, "get_series_episodes"), (
        "TVDBClient must expose get_series_episodes — used by confidence.get_episode_titles "
        "and tv_service._build_episode_map."
    )
    assert not hasattr(TVDBClient, "get_season_episodes"), (
        "TVDBClient must NOT expose get_season_episodes — that was the bug masked by type:ignore."
    )


def test_tvdb_client_get_series_episodes_signature_matches_call() -> None:
    """The (series_id, season) shape used by callers must match the method."""
    sig = inspect.signature(TVDBClient.get_series_episodes)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    assert len(params) == 2, (
        f"TVDBClient.get_series_episodes must accept (series_id, season); got {[p.name for p in params]}"
    )


class _StrictTVDBStub:
    """Non-Mock TVDB stub — accessing an undefined attribute raises ``AttributeError``.

    The original bug went undetected because ``MagicMock`` auto-creates any
    attribute access. A strict stub forces the test to fail if confidence.py
    ever again invokes a method that does not exist on the real client.
    """

    def __init__(self, *, season_payload: SeasonDetails) -> None:
        self._payload = season_payload
        self.calls: list[tuple[int, int]] = []

    def get_series_episodes(self, series_id: int, season: int) -> SeasonDetails:
        self.calls.append((series_id, season))
        return self._payload


def test_get_episode_titles_calls_real_method_on_strict_stub() -> None:
    """Behavioural pin: confidence calls the real method, not the buggy name."""
    stub = _StrictTVDBStub(
        season_payload=SeasonDetails(
            provider="tvdb",
            tv_id="81189",
            season_number=1,
            episodes=[
                EpisodeInfo(episode_number=1, title="Pilot", overview="", air_date="", runtime_minutes=None),
                EpisodeInfo(episode_number=2, title="Cat's in the Bag", overview="", air_date="", runtime_minutes=None),
            ],
        ),
    )
    match = MatchResult(api_id=81189, api_title="Breaking Bad", api_year=2008, confidence=0.95, source="tvdb")

    titles = get_episode_titles(match, season=1, tvdb_client=stub, tmdb_client=object())

    assert titles == {1: "Pilot", 2: "Cat's in the Bag"}
    assert stub.calls == [(81189, 1)], "confidence.get_episode_titles must call get_series_episodes(series_id, season)."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
