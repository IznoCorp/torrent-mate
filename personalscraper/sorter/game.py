"""Game (disc-image) release detection for the sorter.

A game release is a disc image (``.iso`` and friends) that carries a *game*
signal — a known repack/scene group in **release-group position** (the scene
convention ``Title.Tokens-GROUP``) or a console platform token — and that is NOT
a media rip.

This module is **precision-first**: its only consumer hides matched items from
the web médiathèque (``read_model.scan_staging_media``), so a false positive
would make a real media item silently vanish from triage. Two design choices
protect that invariant:

- **Group tokens are matched only in the trailing release-group position** (after
  the last ``-``), never anywhere in the name. A film whose *title* contains a
  word that is also a scene-group name (``The Matrix Reloaded``, ``The Switch``,
  ``A Prophet``, ``Plaza Suite``) is therefore NOT matched — a title word never
  sits in the group position. A genuine repack (``…-Mephisto``, ``…-RUNE``) does.
- **A bare version token is not a signal.** Fan-edit disc rips are versioned
  (``…Final.Cut.v2.0``) and would otherwise be hidden; real repacks carry a group
  or platform token, which is what we require.

Every media signal (a video child, TV season/episode markers, or a video-release
token such as ``1080p``/``BluRay``/``x264`` — which a movie or TV disc image
always carries) additionally **vetoes** the game verdict. The predicate is pure
(directory name + child extensions only, no I/O beyond one ``iterdir``), so it is
golden-testable.
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
DISC_IMAGE_EXTENSIONS: frozenset[str] = frozenset({"iso", "bin", "mds", "mdf", "nrg", "cue", "img"})

#: Known PC-game repack / scene groups (lowercased). Matched ONLY in the trailing
#: release-group position (see ``_trailing_group_token``), so entries that are
#: also ordinary words / film titles (``reloaded``, ``plaza``, ``prophet``…) are
#: safe: a title word is never the trailing ``-GROUP``, only an actual group is.
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
        "steampunks",
        "kaos",
    }
)

#: Console/platform tokens. Matched anywhere (they sit mid-name, e.g.
#: ``Game.PS4.FRENCH``). ``pc`` and ``switch`` are intentionally omitted — too
#: weak (``switch`` is the film "The Switch", ``pc`` matches non-game text);
#: Nintendo Switch is covered by the game-specific ``nsw`` tag.
_PLATFORM_RE: re.Pattern[str] = re.compile(r"(?i)\b(?:ps[345]|psvita|nsw|xbox(?:360|one)?|wiiu?)\b")


def _extension_of(path: Path) -> str:
    """Return *path*'s lowercase extension without the dot (``""`` if none)."""
    return path.suffix.lstrip(".").lower()


def _trailing_group_token(name: str) -> str | None:
    """Return the lowercased trailing release-group token of *name*, or ``None``.

    Scene/repack releases end with ``-GROUP`` (the group is always last). This
    returns the alphanumeric run immediately after the LAST ``-`` — e.g.
    ``"Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto"`` → ``"mephisto"`` (the
    ``Spider-Man`` hyphen is not the last one). A name with no hyphen has no
    group position and yields ``None``.

    Args:
        name: A release folder name or disc-image filename stem.

    Returns:
        The lowercased group token, or ``None`` when there is no trailing group.
    """
    if "-" not in name:
        return None
    tail = name.rsplit("-", 1)[1]
    match = re.match(r"[0-9a-zA-Z]+", tail)
    return match.group(0).lower() if match else None


def _has_game_signal(folder_name: str, disc_stems: list[str]) -> bool:
    """Whether a game signal is present: a trailing repack group or a platform tag.

    Args:
        folder_name: The release directory name.
        disc_stems: The disc-image filenames (extension stripped).

    Returns:
        True if any of ``folder_name``/``disc_stems`` ends with a known game
        group (release-group position), or a console-platform token appears.
    """
    for name in (folder_name, *disc_stems):
        token = _trailing_group_token(name)
        if token is not None and token in GAME_RELEASE_GROUPS:
            return True
    haystack = " ".join([folder_name, *disc_stems])
    return bool(_PLATFORM_RE.search(haystack))


def is_game_release(media_dir: Path) -> bool:
    """Whether *media_dir* is a game release (disc image + game signal, not media).

    Precision-first — a media rip is never a game. The verdict is True only when
    ALL hold:

    1. a direct child is a disc image (``DISC_IMAGE_EXTENSIONS``);
    2. NO direct child is a video file (a video child means a media rip);
    3. neither the folder name nor the disc-image filename(s) carry TV
       season/episode markers or a video-release token (``1080p``/``BluRay``/
       codec/source) — a movie or TV disc image always carries one;
    4. the folder name or a disc-image filename carries a game signal — a known
       repack group in trailing release-group position, or a console platform
       token.

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

    # Signal text = the release folder name plus every disc-image filename stem, so
    # a group living on the .iso (not the folder) is still seen.
    disc_stems = [Path(c.name).stem for c in files if _extension_of(c) in DISC_IMAGE_EXTENSIONS]
    haystack = " ".join([media_dir.name, *disc_stems])

    # A console token like ``PS4`` embeds ``S4``, which the season-pack TV-marker
    # regex (``s\d``) would read as "Season 4" and wrongly veto the game. Platform
    # tokens are a GAME signal, never a media one, so strip them before the media
    # vetoes (the game-signal check below still runs on the untouched names).
    veto_text = _PLATFORM_RE.sub(" ", haystack)
    if _has_tvshow_markers(veto_text):
        return False  # (3a) TV markers → media
    if _looks_like_video_release(veto_text):
        return False  # (3b) resolution/source/codec token → movie/TV disc image

    return _has_game_signal(media_dir.name, disc_stems)  # (4) a game signal is required
