"""Regression test for §12.3: rescrape_drift always triggers episode-rename phase.

When ``_verify_existing_scrape`` returns any episode-level drift reason
(``episode_naming_drift``, ``episode_nfo_missing``,
``episode_nfo_missing_canonical_uniqueid``), the ``drift_rescrape_episode_nfo``
gate must flip True so that ``video_files`` includes files already organised in
``Saison NN/``. Otherwise only tvshow.nfo is regenerated and episodes keep
their raw release names — DEV #2 (Top Chef LCP S17E10 incident).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.naming_patterns import PATTERNS
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.tv_service import TvServiceMixin
from personalscraper.scraper.tv_service_nfo import TvServiceNfoMixin
from personalscraper.scraper.tv_service_write import TvServiceWriteMixin


class _ScrapeTvMixin(TvServiceMixin, TvServiceNfoMixin, TvServiceWriteMixin):
    """Combined mixin mirroring ``Scraper`` MRO for the forced-scrape write path."""


def _make_mixin(**kwargs: Any) -> TvServiceMixin:
    """Build a ``TvServiceMixin`` with the minimum attributes the methods touch."""
    mixin = _ScrapeTvMixin.__new__(_ScrapeTvMixin)
    mixin.dry_run = kwargs.get("dry_run", False)
    mixin._tvdb = kwargs.get("tvdb", MagicMock())
    mixin._tmdb = kwargs.get("tmdb", MagicMock())
    mixin._nfo = kwargs.get("nfo", MagicMock())
    mixin._artwork = kwargs.get("artwork", MagicMock())
    mixin.config = kwargs.get("config")
    mixin.patterns = kwargs.get("patterns", PATTERNS)
    mixin._scraper_language = "fr-FR"
    mixin._scraper_fallback_language = "en-US"
    mixin._tvdb_language = "fra"
    mixin._tvdb_fallback_language = "eng"
    mixin._classify_item = MagicMock(return_value=kwargs.get("classify_return", "tv_shows"))
    mixin._resolve_title = MagicMock(side_effect=lambda api_title, _data, _typ: api_title)
    mixin._strip_trailing_year = MagicMock(side_effect=lambda s: s)
    mixin._verify_existing_scrape = MagicMock(return_value=kwargs.get("verify_return", (True, "")))
    mixin._check_missing_tvshow_artwork = MagicMock(return_value=[])
    mixin._recover_tvshow_artwork = MagicMock()
    mixin._repair_tvshow_dir = MagicMock(return_value=False)
    return mixin


def _make_scrape_mixin(**kwargs: Any) -> TvServiceMixin:
    """Create a mixin with a config object so ``scrape_tvshow`` runs end-to-end."""
    cfg = MagicMock()
    cfg.scraper.episode_default_name = "Episode"
    cfg.metadata.priorities.episode_scraping = {"tvdb": 1, "tmdb": 2}
    return _make_mixin(config=cfg, **kwargs)


# ---------------------------------------------------------------------------
# Parametrized: every episode-level drift reason must trigger the sweep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "drift_reason",
    [
        "episode_naming_drift:Top.Chef.S17E10.FRENCH.1080p.mkv",
        "episode_nfo_missing:S01E01 - Pilot.nfo",
        "episode_nfo_missing_canonical_uniqueid:S01E01 - Pilot.nfo",
    ],
)
def test_rescrape_drift_episode_triggers_rename_sweep(
    tmp_path: Path,
    drift_reason: str,
) -> None:
    """Any episode-level drift reason must include Saison NN/ files in video_files.

    The assertion that ``_build_episode_map`` was called proves that the
    file inside ``Saison 17/`` was included in the ``video_files`` sweep —
    without ``drift_rescrape_episode_nfo=True``, the ``_is_in_season_dir``
    filter at line 316 would exclude it, ``video_files`` would be empty,
    and ``_build_episode_map`` would never fire.
    """
    show = tmp_path / "Top.Chef.Le.Concours.Parallele (2026)"
    show.mkdir()
    (show / "tvshow.nfo").write_text(
        "<tvshow><title>Top Chef Le Concours Parallele</title>"
        "<year>2026</year>"
        '<uniqueid type="tvdb" default="true">475278</uniqueid>'
        "</tvshow>",
    )
    (show / "poster.jpg").write_bytes(b"\xff")
    (show / "landscape.jpg").write_bytes(b"\xff")
    season_dir = show / "Saison 17"
    season_dir.mkdir()
    ep_file = season_dir / "Top.Chef.Le.Concours.Parallele.S17E10.FRENCH.1080p.WEB.H264-laRoulade.mkv"
    ep_file.write_bytes(b"\x00")

    mixin = _make_scrape_mixin(verify_return=(False, drift_reason))

    match = MatchResult(
        api_id=475278,
        api_title="Top Chef Le Concours Parallele",
        api_year=2026,
        confidence=1.0,
        source="tvdb",
    )
    mixin._lookup_series = MagicMock(
        return_value=(
            match,
            {"name": "Top Chef Le Concours Parallele"},
            None,
            "Top Chef Le Concours Parallele",
        )
    )
    mixin._build_episode_map = MagicMock(return_value={})
    mixin._generate_episode_nfos = MagicMock()
    mixin._nfo.generate_tvshow_nfo.return_value = "<xml/>"

    with patch(
        "personalscraper.scraper.tv_service._is_nfo_complete",
        return_value=True,
    ):
        res = mixin.scrape_tvshow(show)

    mixin._build_episode_map.assert_called_once()
    assert res.action == "scraped"
