"""Unit tests for the core completeness read-model (core/completeness).

Covers each component in isolation — ``nfo_status`` (missing / invalid / valid +
equivalence to the canonical ``is_nfo_complete``), the movie renamed-video check,
the trailer filesystem check — and their composition via ``media_completeness``
for both movies and TV shows. Also pins the layering invariant: importing the
module must not drag ``indexer`` / ``web`` / ``acquire`` into ``sys.modules``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from personalscraper.core.completeness import (
    Completeness,
    NfoStatus,
    media_completeness,
    nfo_status,
)
from personalscraper.nfo_utils import is_nfo_complete

_VALID_NFO = '<movie><title>Fight Club</title><uniqueid type="tmdb" default="true">550</uniqueid></movie>'
_NFO_NO_UNIQUEID = "<movie><title>Fight Club</title></movie>"
_NFO_PLACEHOLDER_UNIQUEID = '<movie><title>Fight Club</title><uniqueid type="tmdb">0</uniqueid></movie>'
_NFO_NO_TITLE = '<movie><uniqueid type="tmdb">550</uniqueid></movie>'


def _write(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, creating parent directories.

    Args:
        path: Target file path.
        text: File content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# nfo_status
# ---------------------------------------------------------------------------


def test_nfo_status_missing(tmp_path: Path) -> None:
    """An absent NFO is ``missing`` and not complete."""
    status = nfo_status(tmp_path / "nope.nfo")
    assert status == NfoStatus(present=False, complete=False, has_title=False)
    assert status.status == "missing"


def test_nfo_status_valid(tmp_path: Path) -> None:
    """A parseable NFO with a real uniqueid + title is ``valid`` and complete."""
    nfo = tmp_path / "Fight Club.nfo"
    _write(nfo, _VALID_NFO)
    status = nfo_status(nfo)
    assert status.present is True
    assert status.complete is True
    assert status.has_title is True
    assert status.status == "valid"


def test_nfo_status_invalid_no_uniqueid(tmp_path: Path) -> None:
    """A parseable NFO without a uniqueid is present-but-``invalid``."""
    nfo = tmp_path / "Fight Club.nfo"
    _write(nfo, _NFO_NO_UNIQUEID)
    status = nfo_status(nfo)
    assert status.present is True
    assert status.complete is False
    assert status.has_title is True
    assert status.status == "invalid"


def test_nfo_status_invalid_placeholder_uniqueid(tmp_path: Path) -> None:
    """A placeholder uniqueid (``0``) does not satisfy completeness."""
    nfo = tmp_path / "Fight Club.nfo"
    _write(nfo, _NFO_PLACEHOLDER_UNIQUEID)
    status = nfo_status(nfo)
    assert status.complete is False
    assert status.status == "invalid"


def test_nfo_status_has_title_false(tmp_path: Path) -> None:
    """A valid-uniqueid NFO with no title is complete but ``has_title`` is False."""
    nfo = tmp_path / "movie.nfo"
    _write(nfo, _NFO_NO_TITLE)
    status = nfo_status(nfo)
    assert status.complete is True  # title is NOT part of the strict definition
    assert status.has_title is False


def test_nfo_status_unparseable_is_invalid(tmp_path: Path) -> None:
    """A present but unparseable NFO is ``invalid`` (fail-soft, no raise)."""
    nfo = tmp_path / "broken.nfo"
    _write(nfo, "<movie><title>trunc")
    status = nfo_status(nfo)
    assert status.present is True
    assert status.complete is False
    assert status.has_title is False
    assert status.status == "invalid"


def test_nfo_status_complete_matches_is_nfo_complete(tmp_path: Path) -> None:
    """``nfo_status(...).complete`` is exactly ``is_nfo_complete`` (single definition)."""
    cases = {
        "valid.nfo": _VALID_NFO,
        "no_uid.nfo": _NFO_NO_UNIQUEID,
        "placeholder.nfo": _NFO_PLACEHOLDER_UNIQUEID,
        "no_title.nfo": _NFO_NO_TITLE,
        "broken.nfo": "<movie><title>trunc",
    }
    for name, text in cases.items():
        nfo = tmp_path / name
        _write(nfo, text)
        assert nfo_status(nfo).complete == is_nfo_complete(nfo), name
    # And the missing case agrees too.
    missing = tmp_path / "absent.nfo"
    assert nfo_status(missing).complete == is_nfo_complete(missing) is False


# ---------------------------------------------------------------------------
# renamed-video component (movies only)
# ---------------------------------------------------------------------------


def _movie_dir(tmp_path: Path, folder: str = "Fight Club (1999)") -> Path:
    """Create and return an empty movie folder under ``tmp_path``.

    Args:
        tmp_path: pytest temp dir.
        folder: Movie folder name (``Title (Year)``).

    Returns:
        The created movie directory.
    """
    d = tmp_path / folder
    d.mkdir()
    return d


def test_renamed_video_present_true(tmp_path: Path) -> None:
    """A movie whose main video is renamed to ``{Title}.<ext>`` reports renamed."""
    d = _movie_dir(tmp_path)
    (d / "Fight Club.mkv").write_bytes(b"x" * 10)
    result = media_completeness(d, "movie")
    assert result.has_renamed_video is True


def test_renamed_video_present_false_when_misnamed(tmp_path: Path) -> None:
    """A raw-release-named video reports NOT renamed."""
    d = _movie_dir(tmp_path)
    (d / "Fight.Club.1999.1080p.BluRay.x264-GROUP.mkv").write_bytes(b"x" * 10)
    result = media_completeness(d, "movie")
    assert result.has_renamed_video is False


def test_renamed_video_false_when_absent(tmp_path: Path) -> None:
    """A movie folder with no video reports NOT renamed."""
    d = _movie_dir(tmp_path)
    result = media_completeness(d, "movie")
    assert result.has_renamed_video is False


def test_renamed_video_ignores_trailer(tmp_path: Path) -> None:
    """A trailer sidecar is not mistaken for the main (misnamed) video."""
    d = _movie_dir(tmp_path)
    (d / "Fight Club.mkv").write_bytes(b"x" * 100)
    (d / "Fight Club (1999)-trailer.mp4").write_bytes(b"x" * 5)
    result = media_completeness(d, "movie")
    assert result.has_renamed_video is True


def test_renamed_video_not_applicable_for_tvshow(tmp_path: Path) -> None:
    """The renamed-video component is ``None`` (N/A) for TV shows."""
    d = tmp_path / "Breaking Bad (2008)"
    d.mkdir()
    result = media_completeness(d, "tvshow")
    assert result.has_renamed_video is None
    assert "renamed_video" not in result.missing


# ---------------------------------------------------------------------------
# trailer component
# ---------------------------------------------------------------------------


def test_trailer_present_movie_flat(tmp_path: Path) -> None:
    """A movie flat ``{name}-trailer.{ext}`` file is detected."""
    d = _movie_dir(tmp_path)
    (d / "Fight Club (1999)-trailer.mp4").write_bytes(b"x")
    assert media_completeness(d, "movie").has_trailer is True


def test_trailer_present_tvshow_subfolder(tmp_path: Path) -> None:
    """A TV show ``Trailers/{name}.{ext}`` file is detected."""
    d = tmp_path / "Breaking Bad (2008)"
    (d / "Trailers").mkdir(parents=True)
    (d / "Trailers" / "Breaking Bad (2008).mkv").write_bytes(b"x")
    assert media_completeness(d, "tvshow").has_trailer is True


def test_trailer_absent(tmp_path: Path) -> None:
    """No trailer file → has_trailer False."""
    d = _movie_dir(tmp_path)
    assert media_completeness(d, "movie").has_trailer is False


# ---------------------------------------------------------------------------
# composition
# ---------------------------------------------------------------------------


def test_media_completeness_movie_fully_complete(tmp_path: Path) -> None:
    """A movie with NFO + poster + landscape + renamed video + trailer is complete."""
    d = _movie_dir(tmp_path)
    _write(d / "Fight Club.nfo", _VALID_NFO)
    (d / "Fight Club.mkv").write_bytes(b"x" * 10)
    (d / "poster.jpg").write_bytes(b"x")
    (d / "landscape.jpg").write_bytes(b"x")
    (d / "Fight Club (1999)-trailer.mp4").write_bytes(b"x")
    result = media_completeness(d, "movie")
    assert isinstance(result, Completeness)
    assert result.nfo.complete is True
    assert result.artwork.poster is True
    assert result.artwork.landscape is True
    assert result.has_renamed_video is True
    assert result.has_trailer is True
    assert result.missing == ()
    assert result.complete is True


def test_media_completeness_movie_reports_each_gap(tmp_path: Path) -> None:
    """An empty movie folder lists every applicable missing component in order."""
    d = _movie_dir(tmp_path)
    result = media_completeness(d, "movie")
    assert result.complete is False
    assert result.missing == ("nfo", "poster", "landscape", "renamed_video", "trailer")


def test_media_completeness_tvshow_omits_renamed_video(tmp_path: Path) -> None:
    """A TV show's missing list never contains ``renamed_video`` (not applicable)."""
    d = tmp_path / "Breaking Bad (2008)"
    d.mkdir()
    _write(d / "tvshow.nfo", _VALID_NFO)
    (d / "poster.jpg").write_bytes(b"x")
    (d / "landscape.jpg").write_bytes(b"x")
    result = media_completeness(d, "tvshow")
    # Only the trailer is missing here.
    assert result.missing == ("trailer",)
    assert result.has_renamed_video is None


def test_media_completeness_uses_canonical_movie_nfo_name(tmp_path: Path) -> None:
    """The movie NFO is resolved as ``{Title}.nfo`` (year stripped), matching strict sites."""
    d = _movie_dir(tmp_path, "Amelie (2001)")
    _write(d / "Amelie.nfo", _VALID_NFO)
    result = media_completeness(d, "movie")
    assert result.nfo.status == "valid"


# ---------------------------------------------------------------------------
# layering invariant
# ---------------------------------------------------------------------------


def test_import_does_not_pull_upper_layers() -> None:
    """Importing core.completeness drags no indexer / web / acquire module in.

    Guards the ``core/`` layering contract at runtime: the module (and its
    transitive imports) must stay within stdlib + core + verified leaves. Run in
    a fresh interpreter so an unrelated earlier import in this test session
    cannot mask a real leak.
    """
    probe = (
        "import importlib, sys; importlib.import_module('personalscraper.core.completeness'); "
        "bad=[m for m in sys.modules if m.startswith(("
        "'personalscraper.indexer','personalscraper.web','personalscraper.acquire'))]; "
        "print('LEAK:'+','.join(bad)) if bad else print('CLEAN')"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "CLEAN", out.stdout.strip()
