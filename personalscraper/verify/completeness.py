"""Single executable definition of "scraped / dispatchable" for a staging item.

This is the ONE place that decides whether a staged media is complete enough to
dispatch, shared by:

* ``scripts/check-media-complete.py`` — the CLI guardrail (product-intent.md §méthode
  rule 6 + the executable garde-fou), and
* ``personalscraper.web.staging.read_model`` — so the web UI "Vérification" state
  reflects the **same** criteria the pipeline ``verify`` step uses to gate dispatch,
  never a looser one. The read-model used to call an item "verified" on a laxer
  signal (an NFO + a poster + *any* video), which let an item show "Vérification :
  Fait" while the pipeline ``verify`` still blocked its dispatch (unrenamed
  video/episodes). That divergence is exactly what §méthode rule 6 forbids.

Definition of complete (identical to what ``verify`` + ``get_dispatchable`` enforce):

1. The pipeline ``verify`` step (DISPATCH-stage checks, ``dry_run=True``, ``fix=False``)
   returns status ``valid``/``fixed`` — the real gate that authorizes dispatch. It
   checks the NFO, poster naming, TV episode renaming into ``Saison NN/`` + per-episode
   NFOs, etc. (ERROR-severity checks block; WARNING-severity ones — landscape,
   ``<streamdetails>`` — legitimately do not).
2. For a **movie**, the video file is renamed to the canonical ``Title.<ext>`` — a
   dimension ``verify`` does not enforce but the library convention requires
   (``Obsession.mkv``, never the raw release name).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.naming_patterns import PATTERNS
from personalscraper.scraper.classifier import _parse_folder_name

if TYPE_CHECKING:
    from personalscraper.verify.verifier import Verifier

#: Video extensions counted as the main media file (mirrors check-media-complete).
VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".ts", ".wmv"}


def main_video(folder: Path) -> Path | None:
    """Return the largest non-trailer video file directly in *folder*, or ``None``.

    Args:
        folder: A movie folder in staging.

    Returns:
        The largest top-level video file that is not a trailer / AppleDouble, or
        ``None`` when the folder holds no such video.
    """
    best: Path | None = None
    best_size = -1
    try:
        entries = list(folder.iterdir())
    except OSError:
        return None
    for f in entries:
        if not f.is_file() or f.suffix.lower() not in VIDEO_EXTS:
            continue
        if "trailer" in f.stem.lower() or f.name.startswith("._"):
            continue
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size > best_size:
            best, best_size = f, size
    return best


def video_rename_gap(folder: Path) -> str | None:
    """Return a message when a movie's video is NOT canonically renamed, else ``None``.

    Canonical = ``patterns.format('movie_video', Title=<parsed folder title>)`` — i.e.
    the folder title with the year stripped (``Obsession (2026)`` → ``Obsession.mkv``).
    A raw release name (with resolution/codec tokens) fails this.

    Args:
        folder: A movie folder in staging.

    Returns:
        A human-readable English gap description, or ``None`` when the video is
        correctly named.
    """
    video = main_video(folder)
    if video is None:
        return "no video file found"
    title, _year = _parse_folder_name(folder.name)
    expected = PATTERNS.format("movie_video", Title=title)
    if video.stem != expected:
        return f"video not renamed: '{video.name}' (expected '{expected}{video.suffix}')"
    return None


def dispatch_completeness(verifier: Verifier, media_dir: Path, media_kind: str) -> tuple[str, list[str]]:
    """Return ``(status, errors)`` — the single verdict on whether *media_dir* dispatches.

    Runs the real pipeline ``verify`` (via *verifier*, which the caller builds once with
    ``dry_run=True, fix=False`` so this is pure/read-only) and, for a movie, adds the
    canonical video-rename check. ``status`` is ``"valid"``/``"fixed"`` when the item is
    dispatchable and ``"blocked"`` when it is not; ``errors`` are the concrete verify
    messages (+ the movie video-rename gap) — empty iff dispatchable.

    Args:
        verifier: A :class:`~personalscraper.verify.verifier.Verifier` built with
            ``dry_run=True, fix=False`` (read-only). One instance is reused across items.
        media_dir: The staged media folder (``Title (Year)`` for movies, show root for TV).
        media_kind: ``"movie"`` or ``"tvshow"``.

    Returns:
        ``(status, errors)``. ``status='blocked'`` whenever *errors* is non-empty; else
        the verifier's own ``valid``/``fixed`` status.
    """
    if media_kind == "movie":
        result = verifier.verify_movie(media_dir)
    else:
        result = verifier.verify_tvshow(media_dir)

    errors: list[str] = list(result.errors or [])
    if result.status not in ("valid", "fixed") and not errors:
        # Blocked with no ERROR-severity message (defensive): surface the status.
        errors.append(f"verify status={result.status}")

    if media_kind == "movie":
        gap = video_rename_gap(media_dir)
        if gap is not None:
            errors.append(gap)

    if errors:
        return "blocked", errors
    return result.status, []
