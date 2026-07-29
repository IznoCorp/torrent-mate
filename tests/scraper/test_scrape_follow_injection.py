"""Scraper orchestrator injection (scrape-follow-id).

When a ``follow_tvdb_resolver`` is provided and resolves a folder to a TVDB id,
``process_tvshows`` must scrape it with ``scrape_tvshow_forced`` (that id) instead
of the free ``scrape_tvshow`` — and stay retro-compatible (no resolver ⇒ free
match) so the existing behaviour is untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.scraper import Scraper


def _make_scraper(mock_registry: Any, resolver: Any) -> Scraper:
    """Build a registry-backed Scraper with the given follow_tvdb_resolver."""
    kwargs = {"event_bus": EventBus(), "registry": mock_registry}
    if resolver is not _UNSET:
        kwargs["follow_tvdb_resolver"] = resolver
    return Scraper(MagicMock(), NamingPatterns(), **kwargs)


_UNSET = object()


def _tvshows_dir(tmp_path: Path, show: str) -> Path:
    """Create a tvshows category dir with one show subfolder holding an episode."""
    tv = tmp_path / "002-TVSHOWS"
    tv.mkdir()
    d = tv / show
    d.mkdir()
    (d / f"{show}.S01E06.MULTi.1080p.WEB.x265-GRP.mkv").write_bytes(b"")
    return tv


class TestFollowTvdbInjection:
    """process_tvshows forces the follow's TVDB id when the resolver resolves one."""

    def test_forced_scrape_when_resolver_returns_id(self, mock_registry: Any, tmp_path: Path) -> None:
        """A resolved id ⇒ scrape_tvshow_forced(show_dir, 'tvdb', id); free match not called."""
        tv = _tvshows_dir(tmp_path, "Rooster Fighter")
        scraper = _make_scraper(mock_registry, lambda _d: 457770)
        scraper.scrape_tvshow = MagicMock()  # type: ignore[method-assign]
        scraper.scrape_tvshow_forced = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda d, _s, _i: ScrapeResult(media_path=d, media_type="tvshow", action="scraped")
        )
        scraper.process_tvshows(tv)
        scraper.scrape_tvshow.assert_not_called()
        scraper.scrape_tvshow_forced.assert_called_once()
        _dir, source, provider_id = scraper.scrape_tvshow_forced.call_args[0]
        assert source == "tvdb"
        assert provider_id == 457770

    def test_free_match_when_resolver_returns_none(self, mock_registry: Any, tmp_path: Path) -> None:
        """A None resolution ⇒ the free scrape_tvshow is used; forced not called."""
        tv = _tvshows_dir(tmp_path, "Some Show")
        scraper = _make_scraper(mock_registry, lambda _d: None)
        scraper.scrape_tvshow = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda d: ScrapeResult(media_path=d, media_type="tvshow", action="scraped")
        )
        scraper.scrape_tvshow_forced = MagicMock()  # type: ignore[method-assign]
        scraper.process_tvshows(tv)
        scraper.scrape_tvshow.assert_called_once()
        scraper.scrape_tvshow_forced.assert_not_called()

    def test_retro_compat_without_resolver(self, mock_registry: Any, tmp_path: Path) -> None:
        """No resolver (legacy) ⇒ the free scrape_tvshow is used, unchanged."""
        tv = _tvshows_dir(tmp_path, "Legacy Show")
        scraper = _make_scraper(mock_registry, _UNSET)
        scraper.scrape_tvshow = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda d: ScrapeResult(media_path=d, media_type="tvshow", action="scraped")
        )
        scraper.scrape_tvshow_forced = MagicMock()  # type: ignore[method-assign]
        scraper.process_tvshows(tv)
        scraper.scrape_tvshow.assert_called_once()
        scraper.scrape_tvshow_forced.assert_not_called()

    def test_resolver_exception_falls_back_to_free_match(self, mock_registry: Any, tmp_path: Path) -> None:
        """A resolver that raises ⇒ fail-soft to the free match (never blocks)."""
        tv = _tvshows_dir(tmp_path, "Boom Show")

        def _boom(_d: Path) -> int | None:
            raise RuntimeError("resolver blew up")

        scraper = _make_scraper(mock_registry, _boom)
        scraper.scrape_tvshow = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda d: ScrapeResult(media_path=d, media_type="tvshow", action="scraped")
        )
        scraper.scrape_tvshow_forced = MagicMock()  # type: ignore[method-assign]
        scraper.process_tvshows(tv)
        scraper.scrape_tvshow.assert_called_once()
        scraper.scrape_tvshow_forced.assert_not_called()
