"""Plex match-hint files (``.plexmatch``) — the TV-series side.

The Plex Media Server 1.25.9+ "match hinting" feature reads a line-delimited
``.plexmatch`` file from a series directory and uses its directives to match
the series exactly instead of guessing from the folder name
(support.plex.tv/articles/plexmatch/). The scraper writes one next to the
``tvshow.nfo`` so Plex can never mis-match a scraped show — the wrong-match
class the 2026-08-24 « Gentlemen » incident belongs to.

Movies deliberately get NO ``.plexmatch``: the feature is documented for TV
series only. The movie equivalent is the ``{tmdb-<id>}`` folder-name hint
(see ``NamingPatterns.movie_folder_name``).

Import direction: scraper leaf — no api/, no indexer.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("scraper.plexmatch")

#: Fixed file name Plex looks for (exact, dot included — "plexmatch.txt" or
#: ".plexmatch.txt" are silently ignored by the server).
PLEXMATCH_FILENAME = ".plexmatch"


def _content(title: str, tvdb_id: int) -> str:
    """Render the match-hint directives.

    Format per the Plex documentation: one ``hint: value`` per line, hint
    names case-insensitive, ``#`` opens a comment. ``tvdbid`` overrides every
    other hint, so the ``title`` line is the readable fallback for a server
    whose agent would otherwise match on the directory name alone.

    Args:
        title: The scraped series title.
        tvdb_id: The canonical TVDB id.

    Returns:
        The file content, trailing newline included.
    """
    return f"title: {title}\ntvdbid: {tvdb_id}\n"


def write_plexmatch(
    show_dir: Path,
    *,
    title: str,
    tvdb_id: int,
    dry_run: bool,
) -> bool:
    """Write the ``.plexmatch`` file into a scraped show directory.

    Args:
        show_dir: The show's directory (post-rename).
        title: The scraped series title.
        tvdb_id: The canonical TVDB id.
        dry_run: When True, log the intent and touch nothing.

    Returns:
        True when the file was written (or would be, in dry-run mode).
    """
    path = show_dir / PLEXMATCH_FILENAME
    body = _content(title, tvdb_id)
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
    log.info("plexmatch_written", path=str(path), tvdb_id=tvdb_id)
    return True


__all__ = ["PLEXMATCH_FILENAME", "write_plexmatch"]
