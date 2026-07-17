"""Tests for the xref enrichment pass on the TV scraper (phase 5).

After the canonical provider populates ``api_episodes`` with per-episode
IDs (TVDB-canonical → ``tvdb_episode_id`` is set), the xref pass
queries the *other* provider for the same ``(season, episode)`` tuples
and merges its episode IDs into the same payload — but only when the
key is absent. The pass must be transparent on failures : a non-200
from the xref provider logs a warning and lets the canonical scrape
continue (DESIGN §5 invariants).

These tests exercise the enrichment method directly on a bare mixin
instance, the same pattern used by ``tests/scraper/test_tv_service_extra.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata._base import EpisodeInfo, SeasonDetails
from personalscraper.naming_patterns import PATTERNS, NamingPatterns
from personalscraper.scraper.tv_service import TvServiceMixin
from personalscraper.scraper.tv_service_nfo import TvServiceNfoMixin
from personalscraper.scraper.tv_service_write import TvServiceWriteMixin


class _ScrapeTvMixin(TvServiceMixin, TvServiceNfoMixin, TvServiceWriteMixin):
    """Combined mixin mirroring ``Scraper`` MRO for the forced-scrape write path."""


def _make_mixin(
    *,
    tvdb: Any = None,
    tmdb: Any = None,
    patterns: NamingPatterns | None = None,
) -> TvServiceMixin:
    """Build a bare :class:`TvServiceMixin` for direct method calls."""
    mixin = _ScrapeTvMixin.__new__(_ScrapeTvMixin)
    mixin.dry_run = False

    _tvdb_client = tvdb if tvdb is not None else MagicMock()
    _tmdb_client = tmdb if tmdb is not None else MagicMock()
    _registry = MagicMock()
    _registry.get.side_effect = (
        lambda name,
        _cache={  # type: ignore[misc]
            "tmdb": _tmdb_client,
            "tvdb": _tvdb_client,
        }: _cache.get(name, MagicMock())
    )
    mixin._registry = _registry  # type: ignore[assignment]
    mixin._tvdb = _tvdb_client  # type: ignore[assignment]
    mixin._tmdb = _tmdb_client  # type: ignore[assignment]
    mixin._nfo = MagicMock()  # type: ignore[assignment]
    mixin._artwork = MagicMock()  # type: ignore[assignment]
    mixin.config = None  # type: ignore[assignment]
    mixin.patterns = patterns or PATTERNS  # type: ignore[assignment]
    mixin._scraper_language = "fr-FR"
    mixin._scraper_fallback_language = "en-US"
    mixin._tvdb_language = "fra"
    mixin._tvdb_fallback_language = "eng"
    return mixin


# ---------------------------------------------------------------------------
# 5.1 — _xref_enrichment populates the missing family
# ---------------------------------------------------------------------------


def test_xref_enrichment_adds_tmdb_to_tvdb_canonical_episodes() -> None:
    """TVDB-canonical scrape + TMDb xref → ``tmdb_episode_id`` lands on each episode."""
    api_episodes: dict[tuple[int, int], dict[str, Any]] = {
        (1, 1): {"title": "Pilot", "still_path": "", "tvdb_episode_id": "9001"},
        (1, 2): {"title": "Two", "still_path": "", "tvdb_episode_id": "9002"},
    }
    tmdb = MagicMock()
    tmdb.get_tv_season.return_value = SeasonDetails(
        provider="tmdb",
        tv_id="100",
        season_number=1,
        episodes=[
            EpisodeInfo(episode_number=1, external_ids={"tmdb": "5001", "imdb": "tt0000001"}),
            EpisodeInfo(episode_number=2, external_ids={"tmdb": "5002"}),
        ],
    )
    mixin = _make_mixin(tmdb=tmdb)

    mixin._xref_enrichment(api_episodes, canonical_provider="tvdb", tvdb_id=42, tmdb_id=100)

    assert api_episodes[(1, 1)]["tmdb_episode_id"] == "5001"
    assert api_episodes[(1, 1)]["imdb_episode_id"] == "tt0000001"
    assert api_episodes[(1, 2)]["tmdb_episode_id"] == "5002"
    # The canonical IDs are not touched.
    assert api_episodes[(1, 1)]["tvdb_episode_id"] == "9001"
    assert api_episodes[(1, 2)]["tvdb_episode_id"] == "9002"


def test_xref_enrichment_does_not_overwrite_existing_id() -> None:
    """If the xref key is already present, the enrichment must not overwrite it.

    The canonical scrape is the source of truth ; the xref pass only
    fills gaps. This is the cross-contamination guard from DESIGN §3.
    """
    api_episodes: dict[tuple[int, int], dict[str, Any]] = {
        (1, 1): {
            "title": "Pilot",
            "still_path": "",
            "tvdb_episode_id": "9001",
            "tmdb_episode_id": "5001",  # already set by some earlier pass
        }
    }
    tmdb = MagicMock()
    tmdb.get_tv_season.return_value = SeasonDetails(
        provider="tmdb",
        tv_id="100",
        season_number=1,
        episodes=[EpisodeInfo(episode_number=1, external_ids={"tmdb": "9999"})],
    )
    mixin = _make_mixin(tmdb=tmdb)

    mixin._xref_enrichment(api_episodes, canonical_provider="tvdb", tvdb_id=42, tmdb_id=100)

    # Unchanged — the existing tmdb_episode_id wins.
    assert api_episodes[(1, 1)]["tmdb_episode_id"] == "5001"


def test_xref_enrichment_tmdb_canonical_uses_tvdb_provider() -> None:
    """TMDb-canonical scrape calls TVDB for cross-references (and vice versa)."""
    api_episodes: dict[tuple[int, int], dict[str, Any]] = {
        (2, 5): {"title": "Five", "still_path": "", "tmdb_episode_id": "5005"},
    }
    tvdb = MagicMock()
    tvdb.get_series_episodes.return_value = SeasonDetails(
        provider="tvdb",
        tv_id="42",
        season_number=2,
        episodes=[EpisodeInfo(episode_number=5, external_ids={"tvdb": "9005", "imdb": "tt0050005"})],
    )
    mixin = _make_mixin(tvdb=tvdb)

    mixin._xref_enrichment(api_episodes, canonical_provider="tmdb", tvdb_id=42, tmdb_id=100)

    assert api_episodes[(2, 5)]["tvdb_episode_id"] == "9005"
    assert api_episodes[(2, 5)]["imdb_episode_id"] == "tt0050005"
    assert api_episodes[(2, 5)]["tmdb_episode_id"] == "5005"


def test_xref_enrichment_failure_does_not_raise() -> None:
    """A xref-provider exception is swallowed (logged) — canonical scrape keeps running."""
    api_episodes: dict[tuple[int, int], dict[str, Any]] = {
        (1, 1): {"title": "Pilot", "still_path": "", "tvdb_episode_id": "9001"},
    }
    tmdb = MagicMock()
    tmdb.get_tv_season.side_effect = RuntimeError("xref provider down")
    mixin = _make_mixin(tmdb=tmdb)

    # No raise; api_episodes unchanged (the canonical TVDB ID stays).
    mixin._xref_enrichment(api_episodes, canonical_provider="tvdb", tvdb_id=42, tmdb_id=100)
    assert api_episodes[(1, 1)]["tvdb_episode_id"] == "9001"
    assert "tmdb_episode_id" not in api_episodes[(1, 1)]


def test_xref_enrichment_skips_when_xref_id_missing() -> None:
    """When the cross-reference provider id is ``None``, the pass is a no-op.

    TMDb-canonical scrapes whose TVDB cross-reference was never
    resolved (legacy data path) call ``_xref_enrichment`` with
    ``tvdb_id=None`` ; the method must short-circuit instead of
    attempting a fetch with an invalid id.
    """
    api_episodes: dict[tuple[int, int], dict[str, Any]] = {
        (1, 1): {"title": "Pilot", "still_path": "", "tmdb_episode_id": "5001"},
    }
    tvdb = MagicMock()
    mixin = _make_mixin(tvdb=tvdb)

    mixin._xref_enrichment(api_episodes, canonical_provider="tmdb", tvdb_id=None, tmdb_id=100)

    tvdb.get_series_episodes.assert_not_called()
    assert api_episodes[(1, 1)] == {"title": "Pilot", "still_path": "", "tmdb_episode_id": "5001"}


def test_xref_enrichment_wired_between_build_map_and_match_seasons(tmp_path: Any) -> None:
    """``scrape_tvshow`` calls ``_xref_enrichment`` after ``_build_episode_map``.

    Inserts spies on the two collaborators and asserts the call
    order. The check is lightweight — the contract only requires
    that xref runs against the populated ``api_episodes`` and
    before ``_match_seasons`` consumes it.
    """
    from unittest.mock import patch  # noqa: PLC0415

    from personalscraper.scraper.confidence import MatchResult  # noqa: PLC0415

    show_dir = tmp_path / "Show"
    show_dir.mkdir()
    (show_dir / "S01E01.mkv").write_bytes(b"x")

    mixin = _make_mixin()
    mixin._classify_item = MagicMock(return_value="tv_shows")  # type: ignore[assignment]
    mixin._resolve_title = MagicMock(side_effect=lambda t, _d, _ty: t)  # type: ignore[assignment]
    mixin._strip_trailing_year = MagicMock(side_effect=lambda s: s)  # type: ignore[assignment]
    mixin._verify_existing_scrape = MagicMock(return_value=(True, ""))  # type: ignore[assignment]
    mixin._check_missing_tvshow_artwork = MagicMock(return_value=[])  # type: ignore[assignment]
    mixin._repair_tvshow_dir = MagicMock(return_value=False)  # type: ignore[assignment]

    call_log: list[str] = []

    def _build(*_a: Any, **_k: Any) -> dict[tuple[int, int], dict[str, Any]]:
        call_log.append("build")
        return {(1, 1): {"title": "X", "still_path": "", "tvdb_episode_id": "9001"}}

    def _xref(*_a: Any, **_k: Any) -> None:
        call_log.append("xref")

    def _match(*_a: Any, **_k: Any) -> tuple[int, list[str]]:
        call_log.append("match")
        return 1, []

    mixin._build_episode_map = MagicMock(side_effect=_build)  # type: ignore[assignment]
    mixin._xref_enrichment = MagicMock(side_effect=_xref)  # type: ignore[assignment]
    mixin._match_seasons = MagicMock(side_effect=_match)  # type: ignore[assignment]

    match = MatchResult(api_id=42, api_title="Show", api_year=2020, confidence=0.9, source="tvdb")
    mixin._lookup_series = MagicMock(return_value=(match, {"name": "Show"}, 100, "Show"))  # type: ignore[assignment]

    with patch("personalscraper.scraper.tv_service_write._cleanup_empty_release_dirs"):
        mixin.scrape_tvshow(show_dir)

    assert call_log == ["build", "xref", "match"]


@pytest.mark.parametrize("canonical", ["tvdb", "tmdb"])
def test_xref_enrichment_empty_api_episodes_is_noop(canonical: str) -> None:
    """Empty input → no provider call, no error."""
    tvdb = MagicMock()
    tmdb = MagicMock()
    mixin = _make_mixin(tvdb=tvdb, tmdb=tmdb)

    mixin._xref_enrichment({}, canonical_provider=canonical, tvdb_id=42, tmdb_id=100)

    tvdb.get_series_episodes.assert_not_called()
    tmdb.get_tv_season.assert_not_called()
