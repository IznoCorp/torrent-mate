"""F5 regression — the verify gate and the rescraper agree on artwork presence.

DESIGN §9 (executable completeness) / conformity fix F5: ``verify``'s poster
gate and ``maintenance.rescraper`` disagreed about whether a poster was on disk.
``verify`` used exact-name detection (``{Title}-poster.jpg`` for movies, bare
``poster.jpg`` for TV shows) while the rescraper used the canonical union
(``core.artwork_naming`` — which also recognises the Kodi ``folder.jpg`` and the
MediaElch folder-prefixed spelling). A movie whose only poster was ``folder.jpg``
was therefore *blocked by verify* yet *seen as complete by the rescraper*: the
gate and the repair loop contradicted each other on the same directory.

These tests pin the agreement: for a directory whose poster is spelled in a
legitimate-but-non-strict form, ``verify.PosterPresent`` (the real check) and
``rescraper._detect_needs`` must return the SAME poster-presence verdict.

Before the P5.3 fix this file FAILS — ``verify`` reports the poster absent while
the rescraper reports it present. After the fix both consult
``core.artwork_naming.artwork_status`` and agree.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checker import MediaChecker


def _verify_says_poster_present(media_dir: Path, media_type: str, config: Config) -> bool:
    """Return the ``verify`` gate's poster-presence verdict via the real check.

    Runs only the ``poster_present`` DISPATCH check through :class:`MediaChecker`
    so the verdict is the exact one dispatch consumes (not a re-implementation).

    Args:
        media_dir: The media directory to inspect.
        media_type: ``"movie"`` or ``"tvshow"``.
        config: A synthetic :class:`Config` (the check does not read it, but
            :class:`MediaChecker` requires one).

    Returns:
        ``True`` iff ``verify`` considers the poster present.
    """
    checker = MediaChecker(NamingPatterns(), config)
    only = frozenset({"poster_present"})
    results = checker.check_movie(media_dir, only) if media_type == "movie" else checker.check_tvshow(media_dir, only)
    poster = next(r for r in results if r.name == "poster_present")
    return poster.passed


def _rescraper_says_poster_present(media_dir: Path, media_type: str) -> bool:
    """Return the rescraper's poster-presence verdict via ``_detect_needs``.

    Uses the ``--only artwork`` path so the returned tuple isolates the artwork
    signal; ``needs_artwork`` inverts to a poster-presence verdict.

    Args:
        media_dir: The media directory to inspect.
        media_type: ``"movie"`` or ``"tvshow"``.

    Returns:
        ``True`` iff the rescraper considers the poster present (``not
        needs_artwork``).
    """
    from personalscraper.maintenance.rescraper import _detect_needs

    _, needs_artwork, _ = _detect_needs(media_dir, media_type, "artwork")
    return not needs_artwork


def test_movie_folder_jpg_poster_verify_and_rescraper_agree(tmp_path: Path, test_config: Config) -> None:
    """A movie whose only poster is ``folder.jpg`` — both must see it present.

    Pre-fix this fails: ``verify`` looks for ``{Title}-poster.jpg`` (absent) and
    reports the poster missing, while the rescraper's canonical detection sees
    ``folder.jpg`` and reports it present — the F5 disagreement.
    """
    movie = tmp_path / "Le Robot sauvage (2024)"
    movie.mkdir()
    (movie / "Le Robot sauvage.mkv").write_bytes(b"\x00" * 1000)
    # Kodi ``folder.jpg`` — a legitimate poster spelling the strict verify check
    # did not recognise (``{Title}-poster.jpg`` is what it looked for).
    (movie / "folder.jpg").write_bytes(b"\xff")

    verify_present = _verify_says_poster_present(movie, "movie", test_config)
    rescraper_present = _rescraper_says_poster_present(movie, "movie")

    assert verify_present == rescraper_present, (
        f"verify and rescraper disagree on poster presence for a folder.jpg-postered movie: "
        f"verify_present={verify_present}, rescraper_present={rescraper_present}"
    )


def test_tvshow_mediaelch_poster_verify_and_rescraper_agree(tmp_path: Path, test_config: Config) -> None:
    """A TV show with a MediaElch folder-prefixed poster — both must see it present.

    Pre-fix this fails: ``verify`` looks for a bare ``poster.jpg`` (absent) while
    the rescraper's canonical detection sees ``{Folder}-poster.jpg`` and reports
    it present — the F5 disagreement.
    """
    show = tmp_path / "Robot Chicken (2005)"
    show.mkdir()
    season = show / "Saison 01"
    season.mkdir()
    (season / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * 1000)
    # MediaElch folder-name-prefixed poster — the union recognises it, the strict
    # ``poster.jpg`` tvshow check did not.
    (show / "Robot Chicken (2005)-poster.jpg").write_bytes(b"\xff")

    verify_present = _verify_says_poster_present(show, "tvshow", test_config)
    rescraper_present = _rescraper_says_poster_present(show, "tvshow")

    assert verify_present == rescraper_present, (
        f"verify and rescraper disagree on poster presence for a MediaElch-postered show: "
        f"verify_present={verify_present}, rescraper_present={rescraper_present}"
    )
