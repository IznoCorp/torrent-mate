"""Game (disc-image) release detection for the sorter.

A game release is a disc image (``.iso`` and friends) that carries a *game*
signal — a known repack/scene group, a ``vX.Y.Z`` version token, or a console
platform token — and that is NOT a media rip.

This module is **precision-first**: its only consumer hides matched items from
the web médiathèque (``read_model.scan_staging_media``), so a false positive
would make a real media item silently vanish from triage. Every media signal
(a video child, TV season/episode markers, or a video-release token such as
``1080p``/``BluRay``/``x264`` — which a movie or TV disc image always carries)
**vetoes** the game verdict. The predicate is pure (directory name + child
extensions only, no I/O beyond one ``iterdir``), so it is golden-testable.
"""

import re
from pathlib import Path

from personalscraper.core.media_types import VIDEO_EXTENSIONS
from personalscraper.sorter.file_type import (
    _has_tvshow_markers,
    _looks_like_video_release,
)

#: Optical-disc-image extensions (a game's primary payload). A movie/TV rip can
#: also be an ``.iso`` — those are separated out by the media vetoes below, never
#: by this set alone.
DISC_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {"iso", "bin", "mds", "mdf", "nrg", "cue", "img"}
)

#: Known PC-game repack / scene groups (lowercased). Presence of any as a
#: name token is a sufficient game signal. Kept deliberately conservative —
#: only groups that release games, never movie/TV groups.
GAME_RELEASE_GROUPS: frozenset[str] = frozenset(
    {
        "mephisto",
        "fitgirl",
        "dodi",
        "rune",
        "codex",
        "plaza",
        "skidrow",
        "tenoke",
        "razor",
        "razor1911",
        "empress",
        "elamigos",
        "gog",
        "flt",
        "hoodlum",
        "reloaded",
        "prophet",
        "goldberg",
        "chronos",
        "i_know",
        "steampunks",
        "kaos",
    }
)

#: A ``vX.Y`` / ``vX.Y.Z`` version token (e.g. ``v1.526.0``) — games are
#: versioned this way, media releases are not.
_GAME_VERSION_RE: re.Pattern[str] = re.compile(r"(?i)\bv\d+\.\d+(?:\.\d+)*\b")

#: Console/platform tokens. ``pc`` is intentionally omitted — too weak a token
#: (risk of matching non-game text); PC games are still caught by their repack
#: group or version, which they virtually always carry.
_PLATFORM_RE: re.Pattern[str] = re.compile(
    r"(?i)\b(?:ps[345]|psvita|nsw|switch|xbox(?:360|one)?|wii[uu]?)\b"
)

#: Split a release name into lowercase alphanumeric tokens for group matching.
_TOKEN_RE: re.Pattern[str] = re.compile(r"[^0-9a-zA-Z]+")


def _extension_of(path: Path) -> str:
    """Return *path*'s lowercase extension without the dot (``""`` if none)."""
    return path.suffix.lstrip(".").lower()


def _has_game_signal(text: str) -> bool:
    """Whether *text* carries a game signal (repack group, version, or platform).

    Args:
        text: The concatenated release name + disc-image filename(s).

    Returns:
        True if any known game group token, a ``vX.Y[.Z]`` version token, or a
        console-platform token is present.
    """
    tokens = {t for t in _TOKEN_RE.split(text.lower()) if t}
    if tokens & GAME_RELEASE_GROUPS:
        return True
    if _GAME_VERSION_RE.search(text):
        return True
    return bool(_PLATFORM_RE.search(text))


def is_game_release(media_dir: Path) -> bool:
    """Whether *media_dir* is a game release (disc image + game signal, not media).

    Precision-first — a media rip is never a game. The verdict is True only when
    ALL hold:

    1. a direct child is a disc image (``DISC_IMAGE_EXTENSIONS``);
    2. NO direct child is a video file (a video child means a media rip);
    3. neither the folder name nor the disc-image filename(s) carry TV
       season/episode markers or a video-release token (``1080p``/``BluRay``/
       codec/source) — a movie or TV disc image always carries one;
    4. the folder name or disc-image filename(s) carry a game signal
       (repack group, ``vX.Y[.Z]`` version, or console platform).

    Args:
        media_dir: The staged release directory to classify.

    Returns:
        True if *media_dir* is a game release, else False. Fail-soft: an
        unreadable/absent directory yields False (never raises).
    """
    try:
        files = [c for c in media_dir.iterdir() if c.is_file()]
    except OSError:
        # Unreadable/absent directory: cannot prove it is a game → not hidden.
        return False

    extensions = {_extension_of(c) for c in files}
    if not (extensions & DISC_IMAGE_EXTENSIONS):
        return False  # (1) no disc image → not a game
    if extensions & VIDEO_EXTENSIONS:
        return False  # (2) a video child means a media rip, not a game

    # Signal text = the release folder name plus every disc-image filename, so a
    # signal living on the .iso (not the folder) is still seen.
    disc_names = [
        c.name for c in files if _extension_of(c) in DISC_IMAGE_EXTENSIONS
    ]
    haystack = " ".join([media_dir.name, *disc_names])

    # A console token like ``PS4`` embeds ``S4``, which the season-pack TV-marker
    # regex (``s\d``) would read as "Season 4" and wrongly veto the game. Platform
    # tokens are a GAME signal, never a media one, so strip them before the media
    # vetoes (the game-signal check below still runs on the untouched haystack).
    veto_text = _PLATFORM_RE.sub(" ", haystack)
    if _has_tvshow_markers(veto_text):
        return False  # (3a) TV markers → media
    if _looks_like_video_release(veto_text):
        return False  # (3b) resolution/source/codec token → movie/TV disc image

    return _has_game_signal(haystack)  # (4) a game signal is required
