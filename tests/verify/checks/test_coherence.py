"""Unit tests for coherence.py STAGING check plugins."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checks import coherence as coh_mod
from personalscraper.verify.checks.base import CheckContext, CheckStage, Severity


def _ctx(tmp_path, media_type="movie", stage=CheckStage.STAGING):
    """Build a CheckContext for a freshly-created media dir.

    Args:
        tmp_path: Pytest temp dir.
        media_type: ``"movie"`` or ``"tvshow"``.
        stage: CheckStage (default STAGING).

    Returns:
        A CheckContext with the given stage.
    """
    d = tmp_path / ("Fight Club (1999)" if media_type == "movie" else "Fallout (2024)")
    d.mkdir(exist_ok=True)
    return CheckContext(
        media_dir=d,
        media_type=media_type,
        stage=stage,
        config=MagicMock(),
        patterns=NamingPatterns(),
    )


# ── SortProcessCoherence ────────────────────────────────────────────────────


def test_sort_process_coherence_wrong_category_movie(tmp_path):
    """A tvshow.nfo in a movie dir means the item is mis-sorted."""
    ctx = _ctx(tmp_path, "movie")
    (ctx.media_dir / "tvshow.nfo").write_text("<tvshow></tvshow>")
    results = coh_mod.SortProcessCoherence().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert results[0].severity == Severity.WARNING
    assert "tvshow.nfo but is in MOVIES" in results[0].message


def test_sort_process_coherence_wrong_category_tvshow(tmp_path):
    """A movie NFO in a tvshow dir (without tvshow.nfo) means mis-sorted."""
    ctx = _ctx(tmp_path, "tvshow")
    (ctx.media_dir / "Fight Club (1999).nfo").write_text("<movie></movie>")
    results = coh_mod.SortProcessCoherence().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert results[0].severity == Severity.WARNING
    assert "movie NFO but is in TVSHOWS" in results[0].message


def test_sort_process_coherence_correct_movie(tmp_path):
    """A movie dir without tvshow.nfo passes."""
    ctx = _ctx(tmp_path, "movie")
    results = coh_mod.SortProcessCoherence().run(ctx)
    assert len(results) == 1
    assert results[0].passed


def test_sort_process_coherence_correct_tvshow_with_nfo(tmp_path):
    """A tvshow dir with tvshow.nfo passes."""
    ctx = _ctx(tmp_path, "tvshow")
    (ctx.media_dir / "tvshow.nfo").write_text("<tvshow></tvshow>")
    results = coh_mod.SortProcessCoherence().run(ctx)
    assert len(results) == 1
    assert results[0].passed


# ── NfoIdsCoherence ─────────────────────────────────────────────────────────


def test_nfo_ids_no_nfo_movie(tmp_path):
    """Returns [] when a movie dir has no NFO."""
    ctx = _ctx(tmp_path, "movie")
    assert coh_mod.NfoIdsCoherence().run(ctx) == []


def test_nfo_ids_no_nfo_tvshow(tmp_path):
    """Returns [] when a tvshow dir has no tvshow.nfo."""
    ctx = _ctx(tmp_path, "tvshow")
    assert coh_mod.NfoIdsCoherence().run(ctx) == []


def test_nfo_ids_parse_error(tmp_path):
    """Returns a fail result when the NFO is not valid XML."""
    ctx = _ctx(tmp_path, "movie")
    (ctx.media_dir / "Fight Club (1999).nfo").write_text("not valid xml <<<")
    results = coh_mod.NfoIdsCoherence().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert "Cannot parse NFO" in results[0].message


def test_nfo_ids_missing_both_ids(tmp_path):
    """Fails when the NFO contains no TMDB or IMDB uniqueid."""
    ctx = _ctx(tmp_path, "movie")
    nfo = ctx.media_dir / "Fight Club (1999).nfo"
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Fight Club"
    nfo.write_text(ET.tostring(root, encoding="unicode"))
    results = coh_mod.NfoIdsCoherence().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert "Missing IDs" in results[0].message


def test_nfo_ids_pass_with_tmdb(tmp_path):
    """Passes when the NFO has a TMDB uniqueid."""
    ctx = _ctx(tmp_path, "movie")
    nfo = ctx.media_dir / "Fight Club (1999).nfo"
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Fight Club"
    uid = ET.SubElement(root, "uniqueid", type="tmdb")
    uid.text = "550"
    nfo.write_text(ET.tostring(root, encoding="unicode"))
    results = coh_mod.NfoIdsCoherence().run(ctx)
    assert len(results) == 1
    assert results[0].passed


# ── GenreCoherence ──────────────────────────────────────────────────────────


def test_genre_coherence_no_tvshow_nfo(tmp_path):
    """Returns [] when tvshow.nfo is absent."""
    ctx = _ctx(tmp_path, "tvshow")
    assert coh_mod.GenreCoherence().run(ctx) == []


def test_genre_coherence_tv_programs(tmp_path):
    """Fails when classify_from_nfo returns TV_PROGRAMS."""
    ctx = _ctx(tmp_path, "tvshow")
    (ctx.media_dir / "tvshow.nfo").write_text("<tvshow></tvshow>")
    with patch(
        "personalscraper.verify.checks.coherence.classify_from_nfo",
        return_value=("tv_programs", "genre=Talk Show"),
    ):
        results = coh_mod.GenreCoherence().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert "Genre suggests TV program" in results[0].message


def test_genre_coherence_pass(tmp_path):
    """Passes when classify_from_nfo returns a non-TV_PROGRAMS category."""
    ctx = _ctx(tmp_path, "tvshow")
    (ctx.media_dir / "tvshow.nfo").write_text("<tvshow></tvshow>")
    with patch("personalscraper.verify.checks.coherence.classify_from_nfo", return_value=("tv_shows", "genre=Drama")):
        results = coh_mod.GenreCoherence().run(ctx)
    assert len(results) == 1
    assert results[0].passed


def test_genre_coherence_classify_error(tmp_path):
    """Fails when classify_from_nfo raises an exception."""
    ctx = _ctx(tmp_path, "tvshow")
    (ctx.media_dir / "tvshow.nfo").write_text("<tvshow></tvshow>")
    with patch("personalscraper.verify.checks.coherence.classify_from_nfo", side_effect=ValueError("bad genre")):
        results = coh_mod.GenreCoherence().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert "Genre check failed" in results[0].message
