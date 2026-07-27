"""Pin the ``movie_video_renamed`` catalog check (VERIFY-MAINTENANCE-04).

The movie-video-rename gate used to live OUTSIDE the check catalog as the
``verify.completeness.video_rename_gap`` bolt-on. P5.6 moved it into the registry
as a DISPATCH-stage, movie-only ERROR check consuming the single on-disk
read-model (``core.completeness.media_completeness``). These tests prove:

1. the check FAILS for a not-yet-renamed movie video and PASSES for the canonical
   ``{Title}`` stem (the exact verdict the old bolt-on produced),
2. it is wired into ``MediaChecker.check_movie`` (the real dispatch gate), and
3. a not-yet-renamed movie video still BLOCKS ``verify`` / ``dispatch_completeness``
   exactly as before — a previously-valid movie flips to ``blocked``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import personalscraper.verify.checks  # noqa: F401 — trigger plugin registration
from personalscraper.conf.models.config import Config
from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.checker import MediaChecker
from personalscraper.verify.checks.base import CheckContext, CheckStage
from personalscraper.verify.checks.catalog import run_check
from personalscraper.verify.completeness import dispatch_completeness
from personalscraper.verify.verifier import Verifier
from tests.fixtures.settings_stub import make_typed_settings_stub
from tests.verify.golden import _corpus


def _movie_dir(root: Path, video_name: str) -> Path:
    """Create ``root/Cube (1997)/`` holding a single video named *video_name*.

    Args:
        root: Parent directory (a pytest ``tmp_path``).
        video_name: The video file name to write inside the movie folder.

    Returns:
        The created movie directory.
    """
    d = root / "Cube (1997)"
    d.mkdir(parents=True)
    (d / video_name).write_bytes(b"video-bytes")
    return d


def _movie_ctx(media_dir: Path) -> CheckContext:
    """Build a DISPATCH ``CheckContext`` for a movie dir (Config is a stub)."""
    return CheckContext(
        media_dir=media_dir,
        media_type="movie",
        stage=CheckStage.DISPATCH,
        config=MagicMock(),
        patterns=PATTERNS,
    )


def test_check_fails_for_unrenamed_video(tmp_path: Path) -> None:
    """A raw-release video stem fails ``movie_video_renamed`` (ERROR)."""
    d = _movie_dir(tmp_path, "Cube.1997.1080p.BluRay.x264-GROUP.mkv")
    results = run_check(CheckStage.DISPATCH, "movie_video_renamed", _movie_ctx(d))

    assert len(results) == 1
    assert results[0].passed is False
    assert results[0].severity.value == "error"
    assert "Cube" in results[0].message


def test_check_passes_for_canonical_video(tmp_path: Path) -> None:
    """The canonical ``{Title}.mkv`` stem passes ``movie_video_renamed``."""
    d = _movie_dir(tmp_path, "Cube.mkv")
    results = run_check(CheckStage.DISPATCH, "movie_video_renamed", _movie_ctx(d))

    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].message == ""


def test_check_movie_includes_movie_video_renamed(test_config: Config, tmp_path: Path) -> None:
    """``MediaChecker.check_movie`` emits the ``movie_video_renamed`` result (registry wiring)."""
    d = _movie_dir(tmp_path, "Cube.1997.1080p.BluRay.mkv")
    results = MediaChecker(PATTERNS, test_config).check_movie(d)

    renamed = [r for r in results if r.name == "movie_video_renamed"]
    assert len(renamed) == 1, "movie_video_renamed must run exactly once in check_movie"
    assert renamed[0].passed is False


def test_verify_movie_blocks_unrenamed_movie(test_config: Config, tmp_path: Path) -> None:
    """A previously-valid movie flips valid → blocked once its video is un-renamed."""
    items = _corpus.build_item_corpus(tmp_path / "corpus")
    movie = items["movie_valid"]
    verifier = Verifier(make_typed_settings_stub(), PATTERNS, test_config, dry_run=True, fix=False)

    # Baseline: the canonical corpus movie is dispatchable.
    assert verifier.verify_movie(movie).status in ("valid", "fixed")

    # Un-rename the video to a raw release name → the gate must block on it.
    (movie / "Movie Valid.mkv").rename(movie / "Movie.Valid.2024.1080p.BluRay.mkv")
    result = verifier.verify_movie(movie)
    assert result.status == "blocked"
    assert any("not renamed to canonical" in e for e in result.errors)


def test_dispatch_completeness_blocks_unrenamed_movie(test_config: Config, tmp_path: Path) -> None:
    """``dispatch_completeness`` still returns ``blocked`` for a not-yet-renamed movie."""
    items = _corpus.build_item_corpus(tmp_path / "corpus")
    movie = items["movie_valid"]
    (movie / "Movie Valid.mkv").rename(movie / "Movie.Valid.2024.1080p.mkv")

    verifier = Verifier(make_typed_settings_stub(), PATTERNS, test_config, dry_run=True, fix=False)
    status, errors = dispatch_completeness(verifier, movie, "movie")

    assert status == "blocked"
    assert any("not renamed to canonical" in e for e in errors)
