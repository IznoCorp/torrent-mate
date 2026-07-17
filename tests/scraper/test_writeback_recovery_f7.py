"""Regression F7 — a TVDB-only show (no TMDB id) must recover missing artwork.

Solidify P4.4 (SCRAPER-09): the artwork-recovery path was **TMDB-hardwired** —
``_recover_tvshow_artwork`` read only the ``<uniqueid type="tmdb">`` element, so
a show whose NFO carries a TVDB id but **no** TMDB id (a legitimate TVDB-only
series) silently recovered nothing: the ``if not tmdb_id: return`` short-circuit
fired before any fetch. This pins the fix: recovery resolves the provider from
the item's *canonical family* (TVDB-primary for TV when a TVDB id is present)
and downloads the missing artwork from that family — never falling through to
TMDB for a TVDB-only show.

Written test-first (Cocktail A): this file is committed RED against the pre-fix
TMDB-hardwired path and turns GREEN once ``_writeback.recover_artwork`` resolves
the canonical family. The mixin delegate that once wrapped it was removed in
P4.6 (SCRAPER-11); the test now calls ``recover_artwork`` directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper._writeback import recover_artwork
from personalscraper.scraper.artwork import ArtworkDownloader
from personalscraper.scraper.existing_validator import ExistingValidatorMixin

# NFO with a TVDB id and NO TMDB id — the shape that exposed F7.
_TVDB_ONLY_NFO = (
    '<?xml version="1.0" ?>\n'
    "<tvshow>\n"
    "  <title>Robot Wars</title>\n"
    '  <uniqueid type="tvdb" default="true">420001</uniqueid>\n'
    "</tvshow>\n"
)

_SHOW_TVDB_ID = 420001

# TMDB-shaped show_data the TVDB family fetch returns (already converted by
# ``fetch_show_data``): one poster + one backdrop so the downloader has work.
_SHOW_DATA: dict[str, Any] = {
    "id": _SHOW_TVDB_ID,
    "name": "Robot Wars",
    "images": {
        "posters": [{"file_path": "https://tvdb.example/robot-poster.jpg", "iso_639_1": "en", "vote_average": 6.0}],
        "backdrops": [{"file_path": "https://tvdb.example/robot-backdrop.jpg", "iso_639_1": None, "vote_average": 7.0}],
        "logos": [],
    },
    "seasons": [],
}


def _fake_download_image(url: str, dest: Path) -> bool:
    """Offline stand-in for ``ArtworkDownloader.download_image`` (writes bytes)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"stub-image")
    return True


def _make_validator(artwork: ArtworkDownloader) -> ExistingValidatorMixin:
    """A bare ``ExistingValidatorMixin`` wired with a real downloader.

    ``registry.get("tmdb")`` yields a client whose ``get_tv`` explodes: a
    TVDB-only show must NEVER reach TMDB for artwork recovery, so any such call
    is an outright provider-separation violation.
    """
    instance = ExistingValidatorMixin.__new__(ExistingValidatorMixin)
    instance.patterns = NamingPatterns()
    instance.dry_run = False

    tmdb = MagicMock()
    tmdb.get_tv.side_effect = AssertionError("TVDB-only show must NOT hit TMDB for artwork recovery")
    tvdb = MagicMock()
    registry = MagicMock()
    registry.get.side_effect = lambda name, _c={"tmdb": tmdb, "tvdb": tvdb}: _c.get(name, MagicMock())
    instance._registry = registry  # type: ignore[assignment]
    instance._artwork = artwork  # type: ignore[assignment]
    return instance


def test_tvdb_only_show_recovers_artwork_f7(tmp_path: Path) -> None:
    """A TVDB-only tvshow.nfo recovers poster + landscape from the TVDB family."""
    show_dir = tmp_path / "Robot Wars (2016)"
    show_dir.mkdir()
    nfo = show_dir / "tvshow.nfo"
    nfo.write_text(_TVDB_ONLY_NFO)

    artwork = ArtworkDownloader(dry_run=False)
    validator = _make_validator(artwork)
    result = ScrapeResult(media_path=show_dir, media_type="tvshow")

    with (
        patch(
            "personalscraper.scraper._tvdb_convert.fetch_show_data",
            return_value=(_SHOW_DATA, None),
        ) as fake_fetch,
        patch.object(artwork, "download_image", side_effect=_fake_download_image),
    ):
        recover_artwork(
            nfo,
            show_dir,
            result,
            kind="tvshow",
            registry=validator._registry,
            artwork=validator._artwork,
            patterns=validator.patterns,
        )

    # The canonical family for a TVDB-only show is TVDB — artwork must land.
    assert (show_dir / "poster.jpg").exists(), "F7: TVDB-only show must recover its poster from the TVDB family"
    assert (show_dir / "landscape.jpg").exists(), "F7: TVDB-only show must recover its landscape from the TVDB family"
    assert result.action == "artwork_recovered"
    assert "poster.jpg" in result.artwork_downloaded

    # And the fetch that fed it must be the TVDB family with the NFO's TVDB id.
    fake_fetch.assert_called_once()
    call_args = fake_fetch.call_args
    assert call_args.args[0] == "tvdb", "recovery must resolve the TVDB family, not TMDB"
    assert call_args.args[1] == _SHOW_TVDB_ID
