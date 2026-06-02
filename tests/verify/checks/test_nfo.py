"""Unit tests for nfo.py check plugins."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checks import nfo as nfo_mod
from personalscraper.verify.checks.base import CheckContext, CheckStage, Severity


def _ctx(tmp_path, media_type="movie"):
    """Build a CheckContext for a freshly-created media dir.

    Args:
        tmp_path: Pytest temp dir.
        media_type: ``"movie"`` or ``"tvshow"``.

    Returns:
        A DISPATCH-stage CheckContext.
    """
    d = tmp_path / ("Fight Club (1999)" if media_type == "movie" else "Fallout (2024)")
    d.mkdir(exist_ok=True)
    return CheckContext(
        media_dir=d,
        media_type=media_type,
        stage=CheckStage.DISPATCH,
        config=MagicMock(),
        patterns=NamingPatterns(),
    )


def test_nfo_present_missing(tmp_path):
    """nfo_present is a blocking ERROR when the movie NFO is absent."""
    ctx = _ctx(tmp_path)
    results = nfo_mod.NfoPresent().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert results[0].severity == Severity.ERROR


def test_nfo_valid_returns_empty_when_absent(tmp_path):
    """nfo_valid emits no result when the NFO file is absent."""
    ctx = _ctx(tmp_path)
    assert nfo_mod.NfoValid().run(ctx) == []


def test_nfo_ids_returns_empty_when_absent(tmp_path):
    """nfo_ids emits no result when the NFO file is absent."""
    ctx = _ctx(tmp_path)
    assert nfo_mod.NfoIds().run(ctx) == []


def test_nfo_ids_dynamic_severity_movie(tmp_path):
    """nfo_ids is a WARNING (not ERROR) when only one of TMDB/IMDB is present."""
    ctx = _ctx(tmp_path)
    d = ctx.media_dir
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Fight Club"
    ET.SubElement(root, "year").text = "1999"
    u = ET.SubElement(root, "uniqueid")
    u.set("type", "tmdb")
    u.text = "550"
    ET.ElementTree(root).write(d / "Fight Club.nfo", encoding="unicode")
    results = nfo_mod.NfoIds().run(ctx)
    assert len(results) == 1
    assert results[0].severity == Severity.WARNING  # only TMDB, no IMDB
    assert not results[0].passed


def test_nfo_ids_error_when_no_ids_movie(tmp_path):
    """nfo_ids is a blocking ERROR when neither TMDB nor IMDB is present."""
    ctx = _ctx(tmp_path)
    d = ctx.media_dir
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Fight Club"
    ET.SubElement(root, "year").text = "1999"
    ET.ElementTree(root).write(d / "Fight Club.nfo", encoding="unicode")
    results = nfo_mod.NfoIds().run(ctx)
    assert len(results) == 1
    assert results[0].severity == Severity.ERROR
    assert not results[0].passed


def test_nfo_present_tvshow_missing(tmp_path):
    """nfo_present reports tvshow.nfo missing for a bare show dir."""
    ctx = _ctx(tmp_path, media_type="tvshow")
    results = nfo_mod.NfoPresent().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert results[0].message == "tvshow.nfo not found"
