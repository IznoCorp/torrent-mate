"""Hard-filter stage for the grab orchestrator (RP5b).

Eliminatory filters applied BEFORE dedup so a merge never drops the only
profile-passing variant.  Two filters are active at RP5b:

1. **Resolution floor** — drops results below ``profile.min_resolution``.
   None-resolution = FAIL-OPEN (passes) by default: unparseable resolution
   tokens (REMUX, COMPLETE.BLURAY, WEB-DL pack) are often the best source
   and are soft-scored by ``rank()`` later.

2. **Audio language filter** — parses language markers from ``result.title``
   (NOT ``result.audio`` which is codec-only — see TrackerResult.audio
   docstring). Uses anchored regex to prevent false-matches like
   ``MULTILINGUAL`` matching ``MULTI`` or ``ConVOSTed`` matching ``VOSTFR``.

Import direction: ``acquire/desired.py`` + ``api/tracker/_base.py`` + stdlib.
Never imports sorter, cleaner, or indexer.
"""

from __future__ import annotations

import re

from personalscraper.acquire.desired import QualityProfile, Resolution
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.logger import get_logger

log = get_logger("acquire.filters")

# Anchored audio language regex: \b prevents MULTILINGUAL from matching MULTI
# and ConVOSTed from matching VOSTFR.  re.IGNORECASE handles mixed-case titles.
_AUDIO_LANG_RE = re.compile(
    r"\b(VFF|VFQ|VFI|VF2|VOF|TRUEFRENCH|MULTI|VOSTFR|VOST|VO)\b",
    re.IGNORECASE,
)

# Normalise matched raw markers to the three canonical tier names used
# in QualityProfile.required_audio.
_AUDIO_NORM: dict[str, str] = {
    "vff": "VF",
    "vfq": "VF",
    "vfi": "VF",
    "vf2": "VF",
    "vof": "VF",
    "truefrench": "VF",
    "multi": "VF",  # MULTI always includes a French track
    "vostfr": "VOSTFR",
    "vost": "VOSTFR",
    "vo": "VO",
}


def _parse_resolution(token: str | None) -> Resolution | None:
    """Map a raw resolution token to a :class:`Resolution` tier.

    Args:
        token: Raw ``TrackerResult.resolution`` string (e.g. ``"1080p"``,
            ``"4k"``, ``"uhd"``), or ``None``.

    Returns:
        Matching :class:`Resolution` tier, or ``None`` if the input was
        ``None`` (field absent from the tracker title).
        Unrecognised tokens return ``Resolution.UNKNOWN`` via
        :meth:`Resolution.from_token`.
    """
    if token is None:
        return None
    return Resolution.from_token(token)


def _parse_audio_languages(title: str) -> frozenset[str]:
    """Extract canonical language tier markers from a torrent title.

    Parses ``result.title`` (NOT ``result.audio`` — codec-only field) with
    the anchored ``_AUDIO_LANG_RE`` to avoid false-matches.

    Args:
        title: Raw torrent title from :class:`TrackerResult`.

    Returns:
        Set of canonical tier strings (``{"VF"}``, ``{"VOSTFR"}``,
        ``{"VF", "VO"}``, …), or empty set if no marker found.
    """
    found: set[str] = set()
    for m in _AUDIO_LANG_RE.finditer(title):
        canonical = _AUDIO_NORM.get(m.group(0).lower())
        if canonical:
            found.add(canonical)
    return frozenset(found)


def _passes_resolution(result: TrackerResult, profile: QualityProfile) -> bool:
    """Return True if *result* meets the profile's resolution floor.

    Args:
        result: Candidate torrent result.
        profile: Active quality profile.

    Returns:
        ``True`` when the result should survive the resolution filter.
    """
    if profile.min_resolution is None:
        # Permissive default: no floor configured — filter is a no-op.
        return True
    parsed = _parse_resolution(result.resolution)
    if parsed is None or parsed is Resolution.UNKNOWN:
        # Field absent (None) or unrecognised token (UNKNOWN): FAIL-OPEN by
        # default; FAIL-CLOSED only when the profile requires a known resolution.
        return not profile.require_known_resolution
    return parsed >= profile.min_resolution


def _passes_audio(result: TrackerResult, profile: QualityProfile) -> bool:
    """Return True if *result* contains at least one required audio language.

    Args:
        result: Candidate torrent result.
        profile: Active quality profile.

    Returns:
        ``True`` when the result should survive the audio filter.
    """
    if not profile.required_audio:
        # Permissive default: no audio requirement — filter is a no-op.
        return True
    found = _parse_audio_languages(result.title)
    return bool(found & profile.required_audio)


def apply_hard_filters(
    results: list[TrackerResult],
    profile: QualityProfile,
) -> list[TrackerResult]:
    """Apply eliminatory hard-filters; return surviving results.

    Filters applied in order:
    1. Resolution floor (fail-open on unrecognised tokens).
    2. Audio language (parsed from title with anchored regex).

    A result must pass **both** filters to survive.  An empty survivor list
    signals ``all_filtered`` → ``WantedAbandoned`` in the orchestrator.

    Args:
        results: Candidate results from the search stage.
        profile: Effective quality profile for this grab attempt.

    Returns:
        Filtered list (may be empty).
    """
    survivors = []
    for r in results:
        if not _passes_resolution(r, profile):
            log.debug(
                "acquire.filter.resolution_dropped",
                title=r.title,
                resolution=r.resolution,
                min_resolution=profile.min_resolution,
            )
            continue
        if not _passes_audio(r, profile):
            log.debug(
                "acquire.filter.audio_dropped",
                title=r.title,
                required=sorted(profile.required_audio),
            )
            continue
        survivors.append(r)
    return survivors


__all__ = ["apply_hard_filters"]
