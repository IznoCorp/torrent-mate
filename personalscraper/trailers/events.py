"""Trailer event catalog.

Hosts :class:`TrailerDownloaded`, emitted by
:mod:`personalscraper.trailers.orchestrator` after every successful
``YtdlpDownloader.download`` call. Failures (bot-detected, HTTP, yt-dlp
errors) do NOT emit — the catalog records completions only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from personalscraper.core.event_bus import Event


@dataclass(frozen=True, kw_only=True)
class TrailerDownloaded(Event):
    """Emitted after a successful trailer download.

    Attributes:
        media_path: Source media path (the movie folder or show
            sub-directory) the trailer was fetched for.
        trailer_path: Filesystem path where the trailer landed on disk.
        source_url: Resolved YouTube video URL the trailer was fetched
            from (the same string passed to ``YtdlpDownloader.download``).
    """

    media_path: Path
    trailer_path: Path
    source_url: str


__all__ = ["TrailerDownloaded"]
