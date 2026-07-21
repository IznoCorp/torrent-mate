"""Shared release-title quality-token parser for the tracker family.

The lacale / c411 / torr9 trackers all receive quality markers (resolution,
codec, source, audio, container format) encoded in the release **title** rather
than as structured JSON/XML fields — so each must regex-extract them from the
title. This module owns the single regex table and the parse function so every
tracker extracts the *same* tokens.

Before this module existed, ``lacale.py`` owned ``_TITLE_PATTERNS`` +
``_parse_title`` and ``c411.py`` reached across the family boundary to call
``LaCaleClient._parse_title``, while ``torr9.py`` parsed nothing at all —
silently dropping the quality signal the ranker relies on
(TORRENT-TRACKERS-03). All three now call :func:`parse_title_quality`.
"""

from __future__ import annotations

import re

#: Field name → compiled pattern. The captured group 1 is the extracted token.
#: ``resolution``/``codec``/``source``/``audio`` are word-boundary matches that
#: fire anywhere in the title; ``format`` matches a trailing file-extension
#: (``$``-anchored) — most tracker titles carry no extension, so it stays
#: ``None`` for them (this is expected, not a miss).
_TITLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "resolution": re.compile(r"\b(2160p|1080p|720p|480p|4k|uhd)\b", re.IGNORECASE),
    "codec": re.compile(r"\b(x265|x264|h\.?265|h\.?264|hevc|av1|xvid|divx)\b", re.IGNORECASE),
    "source": re.compile(
        r"\b(uhd[. ]bluray|bluray|brrip|web[- ]?dl|webrip|hdtv|dvdrip)\b",
        re.IGNORECASE,
    ),
    "audio": re.compile(
        r"\b(truehd|atmos|dts[- ]?hd|dts|ddp?5\.1|aac|ac3|flac|mp3)\b",
        re.IGNORECASE,
    ),
    "format": re.compile(r"\.(mkv|mp4|avi|m4v|wmv|mov)$", re.IGNORECASE),
}


def parse_title_quality(title: str) -> dict[str, str | None]:
    """Extract quality fields from a release title.

    Args:
        title: Raw release/torrent title.

    Returns:
        Dict with keys ``resolution``, ``codec``, ``source``, ``audio``,
        ``format``. Each value is the matched token (as it appears in the
        title) or ``None`` when no pattern matches. Freeleech/silverleech flags
        are NOT included — they are not encoded uniformly across trackers and
        each client reads its own structured signal for them.
    """
    out: dict[str, str | None] = {}
    for field, pattern in _TITLE_PATTERNS.items():
        match = pattern.search(title)
        out[field] = match.group(1) if match else None
    return out
