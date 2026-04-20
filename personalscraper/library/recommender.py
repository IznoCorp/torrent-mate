"""Library recommender — generate re-download recommendations.

Crosses library analysis with user preferences to produce a prioritized
list of items that should be re-downloaded in a better format.
Output format is the contract for future auto-download integration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from personalscraper.library.models import (
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    CurrentState,
    LibraryAnalysisItem,
    LibraryRecommendationResult,
    Recommendation,
    TargetState,
)
from personalscraper.library.preferences import LibraryPreferences

logger = logging.getLogger(__name__)


def _max_priority(*priorities: str) -> str:
    """Return the highest priority from a list."""
    order = {PRIORITY_HIGH: 3, PRIORITY_MEDIUM: 2, PRIORITY_LOW: 1}
    return max(priorities, key=lambda p: order.get(p, 0))


def _evaluate_movie(
    item: LibraryAnalysisItem,
    prefs: LibraryPreferences,
    ids: tuple[str | None, str | None] = (None, None),
) -> Recommendation | None:
    """Evaluate a single movie against preferences.

    Args:
        item: Analyzed movie item.
        prefs: User preferences.
        ids: Tuple of (tmdb_id, imdb_id) from scan data.

    Returns:
        Recommendation or None if item is conforming.
    """
    if not item.files:
        return None

    f = item.files[0]  # Movies have one video file
    reasons: list[str] = []
    priority = PRIORITY_LOW
    target_codec: str | None = None
    target_resolution: str | None = None
    target_max_size: float | None = None
    matched_rule: int | None = None

    vp = prefs.video

    # Check encoding rules first (override defaults)
    item_tmdb, item_imdb = ids
    for i, rule in enumerate(prefs.encoding_rules):
        c = rule.criteria
        match = False
        if c.imdb_id and item_imdb == c.imdb_id:
            match = True
        elif c.tmdb_id and item_tmdb == c.tmdb_id:
            match = True
        elif c.title and c.title.lower() in item.title.lower():
            match = True
        elif c.genre:
            pass  # Genre matching deferred — requires NFO genre data

        if match:
            if rule.resolution and f.video.resolution != rule.resolution:
                target_resolution = rule.resolution
                reasons.append(f"Override rule: want {rule.resolution}, have {f.video.resolution}")
                priority = PRIORITY_HIGH
                matched_rule = i
            if rule.codec and f.video.codec != rule.codec:
                target_codec = rule.codec
                reasons.append(f"Override rule: want {rule.codec}, have {f.video.codec}")
                priority = PRIORITY_HIGH
                matched_rule = i
            if rule.max_size_gb and f.size_gb > rule.max_size_gb:
                target_max_size = rule.max_size_gb
                reasons.append(f"Override rule: {f.size_gb:.1f} GB > {rule.max_size_gb:.1f} GB max")
                priority = PRIORITY_HIGH
                matched_rule = i
            break  # First matching rule wins

    # Codec check (if no rule override)
    if target_codec is None:
        if f.video.codec in vp.rejected_codecs:
            target_codec = vp.preferred_codec
            reasons.append(f"Rejected codec {f.video.codec}")
            priority = _max_priority(priority, PRIORITY_HIGH)
        elif f.video.codec != vp.preferred_codec and f.video.codec not in vp.fallback_codecs:
            target_codec = vp.preferred_codec
            reasons.append(f"Non-preferred codec {f.video.codec} → {vp.preferred_codec}")
            priority = _max_priority(priority, PRIORITY_MEDIUM)

    # Size check (if no rule override)
    if target_max_size is None and f.size_gb > vp.max_size_movie_gb:
        target_max_size = vp.max_size_movie_gb
        if f.size_gb > vp.max_size_movie_gb * 2:
            reasons.append(f"Very oversized: {f.size_gb:.1f} GB > 2x{vp.max_size_movie_gb:.1f} GB")
            priority = _max_priority(priority, PRIORITY_HIGH)
        else:
            reasons.append(f"Oversized: {f.size_gb:.1f} GB > {vp.max_size_movie_gb:.1f} GB")
            priority = _max_priority(priority, PRIORITY_MEDIUM)

    # Audio check
    profile_priority = prefs.audio.profile_priority
    if profile_priority and f.audio_profile in profile_priority:
        rank = profile_priority.index(f.audio_profile)
        if rank > 0:  # Not the best profile
            reasons.append(f"Audio {f.audio_profile} (preferred: {profile_priority[0]})")
            priority = _max_priority(priority, PRIORITY_MEDIUM)

    # Subtitle check
    if prefs.subtitles.required_languages:
        missing = set(prefs.subtitles.required_languages) - set(f.subtitle_languages)
        if missing:
            reasons.append(f"Missing required subtitles: {', '.join(sorted(missing))}")
            priority = _max_priority(priority, PRIORITY_LOW)

    if not reasons:
        return None

    # Build target
    try:
        target = TargetState(
            codec=target_codec,
            resolution=target_resolution,
            max_size_gb=target_max_size,
        )
    except ValueError:
        # All None — audio/subtitle only issues, set codec as target
        target = TargetState(codec=vp.preferred_codec, resolution=None, max_size_gb=None)

    savings = None
    if target_max_size:
        savings = round(f.size_gb - target_max_size, 1)
    elif target_codec and f.video.codec != target_codec:
        # Rough estimate: HEVC is ~50% smaller than H.264
        savings = round(f.size_gb * 0.4, 1)

    return Recommendation(
        path=item.path,
        title=item.title,
        media_type=item.media_type,
        disk=item.disk,
        category=item.category,
        tmdb_id=None,
        imdb_id=None,
        current=CurrentState(
            codec=f.video.codec,
            resolution=f.video.resolution,
            size_gb=f.size_gb,
            audio_profile=f.audio_profile,
            subtitle_languages=f.subtitle_languages,
        ),
        target=target,
        reasons=reasons,
        priority=priority,
        estimated_savings_gb=savings,
        matched_rule_index=matched_rule,
    )


def _evaluate_tvshow(
    item: LibraryAnalysisItem,
    prefs: LibraryPreferences,
) -> Recommendation | None:
    """Evaluate a TV show against preferences.

    Checks each episode file individually and detects disparate series.

    Args:
        item: Analyzed TV show item.
        prefs: User preferences.

    Returns:
        Recommendation or None if show is conforming.
    """
    if not item.files:
        return None

    reasons: list[str] = []
    priority = PRIORITY_LOW
    vp = prefs.video

    # Detect disparate codecs
    codecs = {f.video.codec for f in item.files}
    if len(codecs) > 1:
        reasons.append(f"Disparate codecs in series: {', '.join(sorted(codecs))}")
        priority = _max_priority(priority, PRIORITY_MEDIUM)

    # Check individual episodes
    non_preferred = [
        f for f in item.files if f.video.codec != vp.preferred_codec and f.video.codec not in vp.fallback_codecs
    ]
    rejected = [f for f in item.files if f.video.codec in vp.rejected_codecs]
    oversized = [f for f in item.files if f.size_gb > vp.max_size_episode_gb]

    if rejected:
        reasons.append(f"{len(rejected)} episodes with rejected codec")
        priority = _max_priority(priority, PRIORITY_HIGH)
    elif non_preferred:
        reasons.append(f"{len(non_preferred)}/{len(item.files)} episodes with non-preferred codec")
        priority = _max_priority(priority, PRIORITY_MEDIUM)

    if oversized:
        reasons.append(f"{len(oversized)} oversized episodes (>{vp.max_size_episode_gb:.1f} GB)")
        priority = _max_priority(priority, PRIORITY_MEDIUM)

    if not reasons:
        return None

    # Use first file as representative
    f = item.files[0]
    total_size = sum(fi.size_gb for fi in item.files)
    estimated_target_size = len(item.files) * vp.max_size_episode_gb
    savings = round(total_size - estimated_target_size, 1) if total_size > estimated_target_size else None

    try:
        target = TargetState(codec=vp.preferred_codec, resolution=None, max_size_gb=vp.max_size_episode_gb)
    except ValueError:
        target = TargetState(codec=vp.preferred_codec, resolution=None, max_size_gb=None)

    return Recommendation(
        path=item.path,
        title=item.title,
        media_type=item.media_type,
        disk=item.disk,
        category=item.category,
        tmdb_id=None,
        imdb_id=None,
        current=CurrentState(
            codec=f.video.codec,
            resolution=f.video.resolution,
            size_gb=total_size,
            audio_profile=f.audio_profile,
            subtitle_languages=f.subtitle_languages,
        ),
        target=target,
        reasons=reasons,
        priority=priority,
        estimated_savings_gb=savings,
        matched_rule_index=None,
    )


def generate_recommendations(
    items: list[LibraryAnalysisItem],
    prefs: LibraryPreferences,
    id_lookup: dict[str, tuple[str | None, str | None]] | None = None,
) -> LibraryRecommendationResult:
    """Generate re-download recommendations from analysis + preferences.

    Args:
        items: Analyzed library items.
        prefs: User preferences.
        id_lookup: Optional dict of path -> (tmdb_id, imdb_id) from scan data.

    Returns:
        LibraryRecommendationResult with prioritized recommendations.
    """
    lookup = id_lookup or {}
    recommendations: list[Recommendation] = []

    for item in items:
        ids = lookup.get(item.path, (None, None))
        if item.media_type == "movie":
            rec = _evaluate_movie(item, prefs, ids=ids)
        else:
            rec = _evaluate_tvshow(item, prefs)
        if rec:
            rec.tmdb_id = ids[0]
            rec.imdb_id = ids[1]
            recommendations.append(rec)

    total_savings = sum(r.estimated_savings_gb or 0 for r in recommendations)

    return LibraryRecommendationResult(
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
        total_recommendations=len(recommendations),
        estimated_total_savings_gb=round(total_savings, 1),
        items=recommendations,
    )
