"""Shared release-title quality-token parser for the tracker family.

Every tracker receives quality markers (resolution, codec, source, audio,
container format) encoded in the release **title** rather than as structured
JSON/XML fields — so each must regex-extract them from the title. This module
owns the single regex table and the parse function so every tracker extracts
the *same* tokens.

Before this module existed, one tracker client owned ``_TITLE_PATTERNS`` +
``_parse_title``, ``c411.py`` reached across the family boundary to call
that sibling's private method, and a third client parsed nothing at all —
silently dropping the quality signal the ranker relies on
(TORRENT-TRACKERS-03). Every client now calls :func:`parse_title_quality`.
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
    # Language / audio-track marker — a SEPARATE axis from the audio CODEC above.
    # « MULTi » (several audio tracks) and the French VF variants (VFF/VFQ/…) live
    # here so a ranking criterion can score « prefer Multi » — the operator's
    # request the ``audio`` codec field could never serve (a torrent never carries
    # a VFF token in its codec). Normalized to an UPPERCASE canonical token (see
    # below) so config ``values`` lookups are case-stable.
    "language": re.compile(
        r"\b(multi|vff|vfq|vfi|vof|truefrench|french|vostfr|subfrench|vo)\b",
        re.IGNORECASE,
    ),
    "format": re.compile(r"\.(mkv|mp4|avi|m4v|wmv|mov)$", re.IGNORECASE),
}

#: Language token priority (best → weakest). A release title can carry SEVERAL
#: language tokens — most decisively when a title WORD collides with a marker
#: (``The French Dispatch MULTi`` → both ``FRENCH`` and ``MULTI``). Selecting by
#: this priority (rather than the leftmost regex match) makes ``MULTI`` — the
#: multi-track release the operator prefers — win over a mere ``FRENCH`` title
#: word, so the language score reflects the release, not the film's name.
_LANGUAGE_PRIORITY: tuple[str, ...] = (
    "MULTI",
    "VFF",
    "VFQ",
    "VFI",
    "VOF",
    "TRUEFRENCH",
    "FRENCH",
    "VOSTFR",
    "SUBFRENCH",
    "VO",
)


def parse_title_quality(title: str) -> dict[str, str | None]:
    """Extract quality fields from a release title.

    Args:
        title: Raw release/torrent title.

    Returns:
        Dict with keys ``resolution``, ``codec``, ``source``, ``audio``,
        ``language``, ``format``. Each value is the matched token or ``None`` when
        no pattern matches. ``language`` is normalized to an UPPERCASE canonical
        token (``MULTI`` / ``VFF`` / ``VOSTFR`` / …) so ranking ``values`` lookups
        are case-stable regardless of the release's casing (``MULTi`` / ``MULTI``);
        the other fields keep the matched token as it appears. Freeleech /
        silverleech flags are NOT included — each client reads its own structured
        signal for them.
    """
    out: dict[str, str | None] = {}
    for field, pattern in _TITLE_PATTERNS.items():
        if field == "language":
            # ALL matches, not the leftmost: a title word (``French``…) can
            # precede the real marker (``MULTi``). Normalize to UPPERCASE (the
            # one case-stable axis) and pick the highest-priority token present.
            found = {tok.upper() for tok in pattern.findall(title)}
            out[field] = next((tok for tok in _LANGUAGE_PRIORITY if tok in found), None)
            continue
        match = pattern.search(title)
        out[field] = match.group(1) if match else None
    return out
