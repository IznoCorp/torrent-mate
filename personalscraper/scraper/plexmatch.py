"""Plex match-hint files (``.plexmatch``) — both media families.

The Plex Media Server "match hinting" feature reads a line-delimited
``.plexmatch`` file from a media directory and uses its directives to match
the item exactly instead of guessing from the folder name. The scraper writes
one — next to the NFO, at scrape time — for BOTH families, per the operator's
directive: a show gets its canonical TVDB id, a movie its TMDB id. This is the
wrong-match class the 2026-08-24 « Gentlemen » incident belongs to.

The file is NAME-NEUTRAL by design: folder and file names are the settled
Kodi-canonical contract and are NEVER modified to carry a match hint — the
hint lives entirely in this sidecar file.

Import direction: scraper leaf — no api/, no indexer.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("scraper.plexmatch")

#: Fixed file name Plex looks for (exact, dot included — "plexmatch.txt" or
#: ".plexmatch.txt" are silently ignored by the server).
PLEXMATCH_FILENAME = ".plexmatch"


def _content(title: str, tvdb_id: int | None, tmdb_id: int | None) -> str:
    """Render the match-hint directives.

    Format per the Plex documentation: one ``hint: value`` per line, hint
    names case-insensitive, ``#`` opens a comment. The provider-ID hint
    overrides every other hint, so the ``title`` line is the readable
    fallback for a server whose agent would otherwise match on the directory
    name alone.

    Args:
        title: The scraped title.
        tvdb_id: The canonical TVDB id (series), or ``None``.
        tmdb_id: The canonical TMDB id (movie), or ``None``.

    Returns:
        The file content, trailing newline included.
    """
    lines = [f"title: {title}"]
    if tvdb_id is not None:
        lines.append(f"tvdbid: {tvdb_id}")
    if tmdb_id is not None:
        lines.append(f"tmdbid: {tmdb_id}")
    return "\n".join(lines) + "\n"


def write_plexmatch(
    media_dir: Path,
    *,
    title: str,
    tvdb_id: int | None = None,
    tmdb_id: int | None = None,
    dry_run: bool,
) -> bool:
    """Write the ``.plexmatch`` file into a scraped media directory.

    Args:
        media_dir: The media directory (movie or show, post-rename).
        title: The scraped title.
        tvdb_id: The canonical TVDB id for a series (``None`` for a movie).
        tmdb_id: The canonical TMDB id for a movie (``None`` for a series).
        dry_run: When True, log the intent and touch nothing.

    Returns:
        True when the file was written (or would be, in dry-run mode).

    Raises:
        ValueError: When neither (or both) of *tvdb_id* and *tmdb_id* is given.
    """
    if (tvdb_id is None) == (tmdb_id is None):
        raise ValueError("write_plexmatch needs exactly one of tvdb_id / tmdb_id")
    path = media_dir / PLEXMATCH_FILENAME
    body = _content(title, tvdb_id, tmdb_id)
    if dry_run:
        log.info("plexmatch_would_write", path=str(path))
        return True
    try:
        path.write_text(body, encoding="utf-8")
    except OSError as exc:
        # Fail-soft: the hint is a Plex nicety — the Kodi NFO remains the
        # canonical metadata and a failed hint write must not fail the scrape.
        log.warning("plexmatch_write_failed", path=str(path), error=str(exc))
        return False
    log.info("plexmatch_written", path=str(path), tvdb_id=tvdb_id, tmdb_id=tmdb_id)
    return True


__all__ = ["PLEXMATCH_FILENAME", "write_plexmatch"]
