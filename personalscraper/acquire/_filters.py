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
from typing import TYPE_CHECKING, Any

from personalscraper.acquire.desired import QualityProfile, Resolution
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.identity import MediaRef

log = get_logger("acquire.filters")

# Anchored audio language regex: \b prevents MULTILINGUAL from matching MULTI
# and ConVOSTed from matching VOSTFR.  re.IGNORECASE handles mixed-case titles.
_AUDIO_LANG_RE = re.compile(
    r"\b(VFF|VFQ|VFI|VF2|VOF|TRUEFRENCH|MULTI|VOSTFR|VOST|VO)\b",
    re.IGNORECASE,
)

# Stereoscopic-3D release markers. A 2D library never wants a Side-By-Side /
# Over-Under encode (two half-width or half-height images), so these are dropped
# by default (QualityProfile.exclude_3d). Anchored with \b to avoid matching
# inside unrelated tokens; bare "SBS" is intentionally NOT matched (it collides
# with the SBS broadcaster tag) — the real 3D releases always carry the
# Full-/Half-/H- prefix or an explicit "3D" token.
_STEREO_3D_RE = re.compile(
    r"\b(3D|(?:Full|Half|H)[.\-]?SBS|Over[.\-_]Under)\b",
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


#: Newznab category classes (``id // 1000``) that are positively NOT video.
#: 1=Console, 3=Audio, 4=PC, 7=Books. Every ``wanted.kind`` is video
#: (``movie``/``episode``/``season``), so a result in one of these classes can
#: never satisfy a wanted item — whichever tracker published it.
#:
#: Deliberately a REJECT list, not an accept list: the video classes (2=Movies,
#: 5=TV) are not the only ones a video release may legitimately carry (6=XXX,
#: 8=Other/Misc), and an accept list would silently drop them. Only what we
#: positively know is non-video gets dropped.
_NON_VIDEO_CATEGORY_CLASSES = frozenset({1, 3, 4, 7})


def _passes_video_category(result: TrackerResult) -> bool:
    """Return True unless the result's Newznab category is positively non-video.

    The tracker's category is authoritative metadata — unlike a title heuristic,
    it cannot be fooled by an artist prefix or a "Motion Picture" token. It is
    the field that would have caught the Spider-Man soundtrack: the album was
    tagged Audio (c411 ``3010``, tr4ker ``3000``) while the title guard scored
    96/100 against the wanted film and the resolution filter failed open.

    Provider-agnostic: the rule keys on the Newznab class shared by every
    Torznab indexer, never on which tracker sent the result.

    FAIL-OPEN on anything unparseable — an absent category or a slug-based
    dialect (``"films"``) leaves the result in play. A tracker that publishes no
    category must never have its whole result set silently wiped.

    Args:
        result: Candidate torrent result.

    Returns:
        ``True`` when the result should survive the category filter.
    """
    raw = result.category
    if raw is None:
        return True
    text = raw.strip()
    if not text.isdigit():
        return True
    return int(text) // 1000 not in _NON_VIDEO_CATEGORY_CLASSES


def _passes_not_3d(result: TrackerResult, profile: QualityProfile) -> bool:
    """Return True unless *result* is a stereoscopic-3D encode the profile drops.

    Args:
        result: Candidate torrent result.
        profile: Active quality profile.

    Returns:
        ``True`` when the result should survive (not 3D, or 3D allowed by the
        profile); ``False`` for a 3D Side-By-Side / Over-Under release when
        ``profile.exclude_3d`` is set.
    """
    if not profile.exclude_3d:
        # Opt-out: a 3D-capable rig wants these.
        return True
    return _STEREO_3D_RE.search(result.title) is None


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
    media_ref: MediaRef | None = None,
) -> list[TrackerResult]:
    """Apply eliminatory hard-filters; return surviving results.

    Filters applied in order:
    0. TMDB identity — drops a result whose ``tmdb_id`` contradicts the
       wanted item's ``tmdb_id`` (prevents grabbing the wrong version/remake,
       e.g. a 1984 vs 2021 same-title film). Engages ONLY when both the result
       and ``media_ref`` carry a ``tmdb_id``; otherwise it is a no-op (can't
       disambiguate). Cheapest and most decisive, so it runs first.
    0b. Video category — drops a result whose Newznab category is positively
       non-video (Audio / Console / PC / Books). Unconditional: every
       ``wanted.kind`` is video, so no wanted item can ever be satisfied by an
       album or a game. Fail-open on an absent or non-numeric category.
    1. Resolution floor (fail-open on unrecognised tokens).
    2. Stereoscopic-3D exclusion (Side-By-Side / Over-Under) — on by default,
       a 2D library never wants a 3D encode.
    3. Audio language (parsed from title with anchored regex).

    A result must pass **all** filters to survive.  An empty survivor list
    signals ``all_filtered`` → ``WantedAbandoned`` in the orchestrator.

    Args:
        results: Candidate results from the search stage.
        profile: Effective quality profile for this grab attempt.
        media_ref: The wanted item's provider IDs, used by the TMDB identity
            filter. Optional: when ``None`` (e.g. the manual CLI grab has no
            wanted item) or when either ``media_ref.tmdb_id`` or the result's
            ``tmdb_id`` is ``None``, the identity filter is a no-op.

    Returns:
        Filtered list (may be empty).
    """
    survivors = []
    for r in results:
        if (
            media_ref is not None
            and media_ref.tmdb_id is not None
            and r.tmdb_id is not None
            and r.tmdb_id != media_ref.tmdb_id
        ):
            log.debug(
                "acquire.filter.tmdb_mismatch",
                title=r.title,
                result_tmdb=r.tmdb_id,
                wanted_tmdb=media_ref.tmdb_id,
            )
            continue
        if not _passes_video_category(r):
            log.debug(
                "acquire.filter.non_video_category_dropped",
                title=r.title,
                category=r.category,
                provider=r.provider,
            )
            continue
        if not _passes_resolution(r, profile):
            log.debug(
                "acquire.filter.resolution_dropped",
                title=r.title,
                resolution=r.resolution,
                min_resolution=profile.min_resolution,
            )
            continue
        if not _passes_not_3d(r, profile):
            log.debug("acquire.filter.stereo_3d_dropped", title=r.title)
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


def filter_to_episode(
    results: "list[TrackerResult]",
    season: int,
    episode: int,
) -> "list[TrackerResult]":
    """Keep only results whose title carries the exact ``SxxEyy`` token.

    A title-based query (``"{title} SxxEyy"``) returns fuzzy matches — other
    episodes of the season, season packs — because trackers match loosely. Left
    unfiltered they rank by seeders, so the wrong episode can win (observed:
    ``S09E05`` wanted → an ``S09E01`` release ranked top). This keeps only
    releases naming the requested episode, tolerating zero-padding (``S9E5`` /
    ``S09E05``) and multi-episode spans (``S09E05-E06`` / ``S09E05E06`` still
    match E05). Season packs (no ``E`` token) are intentionally dropped — an
    exact-episode want should not pull a whole season.

    Args:
        results: The raw tracker results for the query.
        season: Wanted season number.
        episode: Wanted episode number.

    Returns:
        The subset whose title names the exact episode (possibly empty).
    """
    # (?<![0-9]) / (?![0-9]) bound the numbers so E5 does not match E51 and
    # S9 does not match S19; 0* absorbs the zero-padding difference.
    pattern = re.compile(rf"(?<![0-9])s0*{season}e0*{episode}(?![0-9])", re.IGNORECASE)
    return [r for r in results if pattern.search(r.title)]


def _episode_numbers(episode_raw: object) -> list[int]:
    """Normalize guessit's ``episode`` field (int or list) to a sorted int list.

    Args:
        episode_raw: The raw ``episode`` value from a guessit parse — an int,
            a list of ints, or ``None``.

    Returns:
        The episode numbers sorted ascending; empty when absent or when any
        value cannot be coerced to an int (fail-soft — an unparseable marker
        must never read as coverage).
    """
    if episode_raw is None:
        return []
    values: list[Any] = episode_raw if isinstance(episode_raw, list) else [episode_raw]
    numbers: list[int] = []
    for value in values:
        try:
            numbers.append(int(value))
        except (TypeError, ValueError):
            return []
    return sorted(numbers)


def filter_to_season(
    results: list[TrackerResult],
    season: int,
    *,
    expected_count: int | None = None,
) -> list[TrackerResult]:
    """Keep only WHOLE-season packs targeting the given *season*.

    A season pack is identified by title markers — there is no provider-ID
    on tracker results, so identity is verified from the parsed release name:

    * **Bare season**: ``Sxx`` / ``Season N`` / ``Intégrale`` / ``Complete``
      forms with NO episode markers anywhere in the title — the title claims
      the whole season and nothing contradicts it. Kept.
    * **Verified full coverage**: a release carrying episode markers is kept
      ONLY when its coverage is proven against *expected_count* (the number
      of aired episodes in the target season): the episode list must start
      at E01 and reach at least ``expected_count`` (``SxxE01-Eyy`` with
      ``yy >= expected_count``), or be a lone E01 whose guessit
      ``episode_count`` reaches it.
    * **Reject**: partial ranges (``S02E01-E05`` of a 12-episode season),
      single episodes even when a season keyword is present
      (``S02E05.COMPLETE`` — the keyword never overrides an explicit episode
      marker), ANY marker-carrying release when *expected_count* is unknown
      (a pack whose coverage cannot be verified is not « the season »),
      multi-season packs (``S01-S03``, ``Saisons 1-4``), and releases whose
      parsed season differs from the requested *season*.

    Args:
        results: Raw tracker results from the season search query.
        season: The target season number.
        expected_count: Number of aired episodes in the target season, when
            known (from the aired catalog cache). ``None`` = unknown →
            episode-marker releases are rejected conservatively.

    Returns:
        The subset identified as whole-season packs for the given season
        (possibly empty).
    """
    from guessit import guessit  # noqa: PLC0415

    kept: list[TrackerResult] = []
    for r in results:
        title = r.title
        title_lower = title.lower()

        # --- Gate 1: reject multi-season packs ---
        if re.search(r"\bS\d{1,2}[-–]\d{1,2}\b", title, re.IGNORECASE):
            continue
        if re.search(r"(?i)saisons?\s*\d{1,2}\s*[-–àa]\s*\d{1,2}", title):
            continue

        # --- Gate 2: parse the title via guessit ---
        try:
            info = guessit(title)
        except Exception:
            continue  # unparseable → skip (fail-soft)

        parsed_season = info.get("season")
        if parsed_season is None:
            continue  # no season signal at all
        try:
            # guessit can return a list for multi-season packs (e.g. S01-S03);
            # int() on a list raises TypeError → dropped (also caught by Gate 1).
            parsed_season = int(parsed_season)
        except (TypeError, ValueError):
            continue

        # Season MUST match the target
        if parsed_season != season:
            continue

        # --- Gate 3: classify the pack ---
        episode_raw = info.get("episode")
        episode_count = info.get("episode_count")
        episode_range = info.get("episode_range")

        has_episode_marker = bool(
            episode_raw is not None
            or episode_count is not None
            or episode_range is not None
            or re.search(r"(?<![0-9])s\d{1,2}e\d{1,2}", title_lower)
        )

        # Bare season (keyword or not): no episode markers → the title claims
        # the whole season and nothing contradicts it.
        if not has_episode_marker:
            kept.append(r)
            continue

        # Episode markers present: only PROVEN full coverage may pass (review
        # F4 — R3 replace-all would install a 5-of-12 pack as « the season »
        # and the missing episodes would never be acquired). Coverage cannot
        # be proven without the aired-episode count.
        if expected_count is None:
            continue

        eps = _episode_numbers(episode_raw)
        if not eps or eps[0] != 1:
            continue  # no E01 start → partial pack whatever its length

        if eps[-1] >= expected_count:
            kept.append(r)
            continue

        # A lone E01 with an explicit episode_count (« E01 of 12 ») is
        # coverage evidence too.
        if len(eps) == 1 and episode_count is not None:
            try:
                if int(episode_count) >= expected_count:
                    kept.append(r)
                    continue
            except (TypeError, ValueError):
                pass

        # Partial coverage (E01-E05 of 12, keyword + lone episode) → dropped.

    return kept


__all__ = ["apply_hard_filters", "filter_to_episode", "filter_to_season"]
