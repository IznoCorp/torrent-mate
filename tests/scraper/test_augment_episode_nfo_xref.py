"""Tests for ``_augment_episode_nfo_with_xref`` (phase 5.4).

When an episode NFO already exists on disk — e.g. from a pre-phase-5
scrape that only wrote the canonical ``<uniqueid>`` — the recovery
pass appends the xref rows without overwriting any tag already
present. Behaviour pins :

- A new xref row is appended when the NFO lacks it.
- An existing canonical row is never overwritten, even when the
  matched dict carries a different value.
- A NFO that already contains every available xref family is left
  untouched (no I/O when nothing would change).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from personalscraper.naming_patterns import PATTERNS, NamingPatterns
from personalscraper.scraper.tv_service import TvServiceMixin
from personalscraper.scraper.tv_service_nfo import TvServiceNfoMixin


class _TestTvMixin(TvServiceMixin, TvServiceNfoMixin):
    """Combined mixin for tests — mirrors ``Scraper`` MRO."""


def _make_mixin(*, dry_run: bool = False, patterns: NamingPatterns | None = None) -> _TestTvMixin:
    mixin = _TestTvMixin.__new__(_TestTvMixin)
    mixin.dry_run = dry_run
    mixin._tvdb = MagicMock()  # type: ignore[assignment]
    mixin._tmdb = MagicMock()  # type: ignore[assignment]
    mixin._nfo = MagicMock()  # type: ignore[assignment]
    mixin._artwork = MagicMock()  # type: ignore[assignment]
    mixin.config = None  # type: ignore[assignment]
    mixin.patterns = patterns or PATTERNS  # type: ignore[assignment]
    return mixin


def _read_uniqueids(nfo_path: Path) -> list[tuple[str, str]]:
    root = ET.parse(nfo_path).getroot()  # noqa: S314 — test fixture
    return [((u.get("type") or "").strip(), (u.text or "").strip()) for u in root.findall("uniqueid")]


def test_augment_adds_missing_xref_uniqueid(tmp_path: Path) -> None:
    """NFO carrying only canonical tvdb gets a tmdb row appended."""
    nfo = tmp_path / "S01E01 - Pilot.nfo"
    nfo.write_text(
        '<?xml version="1.0"?><episodedetails><uniqueid type="tvdb" default="true">9001</uniqueid></episodedetails>',
        encoding="utf-8",
    )
    mixin = _make_mixin()
    info: dict[str, Any] = {"tmdb_episode_id": "5001"}

    mixin._augment_episode_nfo_with_xref(nfo, info)

    ids = dict(_read_uniqueids(nfo))
    assert ids["tvdb"] == "9001"
    assert ids["tmdb"] == "5001"


def test_augment_does_not_overwrite_existing_uniqueid(tmp_path: Path) -> None:
    """An existing tmdb row wins over the matched-dict value."""
    nfo = tmp_path / "S01E01 - Pilot.nfo"
    nfo.write_text(
        '<?xml version="1.0"?>'
        "<episodedetails>"
        '<uniqueid type="tvdb" default="true">9001</uniqueid>'
        '<uniqueid type="tmdb">5001</uniqueid>'
        "</episodedetails>",
        encoding="utf-8",
    )
    mixin = _make_mixin()
    info: dict[str, Any] = {"tmdb_episode_id": "9999"}  # different value

    mixin._augment_episode_nfo_with_xref(nfo, info)

    ids = dict(_read_uniqueids(nfo))
    assert ids["tmdb"] == "5001"  # unchanged


def test_augment_noop_when_nothing_to_add(tmp_path: Path) -> None:
    """Empty ``info`` dict → file mtime unchanged, no write happens."""
    nfo = tmp_path / "S01E01 - Pilot.nfo"
    nfo.write_text(
        '<?xml version="1.0"?><episodedetails><uniqueid type="tvdb">9001</uniqueid></episodedetails>',
        encoding="utf-8",
    )
    mtime_before = nfo.stat().st_mtime
    mixin = _make_mixin()

    mixin._augment_episode_nfo_with_xref(nfo, {})

    assert nfo.stat().st_mtime == mtime_before


def test_augment_dry_run_does_not_write(tmp_path: Path) -> None:
    """Dry-run mode preserves the original on-disk content."""
    nfo = tmp_path / "S01E01 - Pilot.nfo"
    original = '<?xml version="1.0"?><episodedetails><uniqueid type="tvdb">9001</uniqueid></episodedetails>'
    nfo.write_text(original, encoding="utf-8")
    mixin = _make_mixin(dry_run=True)

    mixin._augment_episode_nfo_with_xref(nfo, {"tmdb_episode_id": "5001"})

    assert nfo.read_text(encoding="utf-8") == original


def test_augment_skips_imdb_when_value_missing(tmp_path: Path) -> None:
    """Falsy values in the matched dict do not produce empty uniqueid tags."""
    nfo = tmp_path / "S01E01 - Pilot.nfo"
    nfo.write_text(
        '<?xml version="1.0"?><episodedetails><uniqueid type="tvdb">9001</uniqueid></episodedetails>',
        encoding="utf-8",
    )
    mixin = _make_mixin()

    mixin._augment_episode_nfo_with_xref(nfo, {"imdb_episode_id": "", "tmdb_episode_id": "5001"})

    ids = dict(_read_uniqueids(nfo))
    assert "imdb" not in ids
    assert ids["tmdb"] == "5001"


def test_augment_handles_unparseable_nfo(tmp_path: Path) -> None:
    """A broken NFO is logged and left alone — no exception escapes."""
    nfo = tmp_path / "S01E01 - Pilot.nfo"
    nfo.write_text("<not_xml", encoding="utf-8")
    mixin = _make_mixin()

    # Must not raise.
    mixin._augment_episode_nfo_with_xref(nfo, {"tmdb_episode_id": "5001"})

    # File content unchanged.
    assert nfo.read_text(encoding="utf-8") == "<not_xml"
