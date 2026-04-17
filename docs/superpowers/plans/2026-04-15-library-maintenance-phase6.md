# Phase 6: Recommender — library-recommend command

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `personalscraper library-recommend` — cross analysis with preferences to produce a prioritized re-download list. Supports `--sort` and `--export csv`.

**Architecture:** `recommender.py` loads `library_analysis.json` and `library_preferences.json`, evaluates each item against preferences and encoding rules, assigns priority, estimates savings. Output `library_recommendations.json` is the contract for future auto-download integration.

**Tech Stack:** Python, Typer, pydantic, csv, pytest

---

## Task 1: Implement recommendation engine

**Files:**

- Create: `personalscraper/library/recommender.py`
- Create: `tests/library/test_recommender.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/library/test_recommender.py
"""Tests for personalscraper.library.recommender — re-download recommendations."""

import pytest

from personalscraper.library.models import (
    AudioTrack,
    LibraryAnalysisItem,
    MediaFileAnalysis,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    SubtitleTrack,
    VideoInfo,
)
from personalscraper.library.preferences import (
    EncodingRule,
    LibraryPreferences,
    RuleCriteria,
    VideoPreferences,
)
from personalscraper.library.recommender import generate_recommendations


def _make_movie(
    codec: str = "hevc", height: int = 1080, size_gb: float = 2.0,
    audio_lang: str = "fra", audio_profile: str = "vf",
    sub_languages: list[str] | None = None,
    title: str = "Movie", tmdb_id: str | None = "1", imdb_id: str | None = None,
) -> LibraryAnalysisItem:
    """Helper to build a movie analysis item."""
    return LibraryAnalysisItem(
        path=f"/Volumes/Disk1/medias/films/{title} (2024)",
        disk="Disk1", category="films", media_type="movie",
        title=title, year=2024,
        files=[MediaFileAnalysis(
            path=f"/Volumes/Disk1/medias/films/{title} (2024)/{title}.mkv",
            size_gb=size_gb, duration_seconds=7200,
            video=VideoInfo(codec=codec, width=int(height * 16 / 9),
                            height=height, bitrate_kbps=5000,
                            hdr=False, hdr_type=None),
            audio_tracks=[AudioTrack(codec="eac3", language=audio_lang,
                                     channels=6, is_atmos=False, is_default=True)],
            subtitle_tracks=[SubtitleTrack(language=l, format="srt",
                                           forced=False, is_default=False)
                             for l in (sub_languages or [])],
            audio_profile=audio_profile,
            subtitle_languages=sorted(sub_languages or []),
            analyzed_at="2026-04-15T12:00:00",
        )],
    )


class TestRecommendCodec:
    """Tests for codec-based recommendations."""

    def test_preferred_codec_no_recommendation(self) -> None:
        """Movie with preferred codec should not be recommended."""
        items = [_make_movie(codec="hevc")]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0

    def test_rejected_codec_high_priority(self) -> None:
        """Movie with rejected codec should be high priority."""
        items = [_make_movie(codec="mpeg2")]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_HIGH
        assert "rejected codec" in result.items[0].reasons[0].lower()

    def test_non_preferred_codec_medium_priority(self) -> None:
        """Movie with non-preferred, non-rejected codec should be medium."""
        items = [_make_movie(codec="h264")]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_MEDIUM

    def test_fallback_codec_no_recommendation(self) -> None:
        """Movie with fallback codec (av1) should not be recommended."""
        items = [_make_movie(codec="av1")]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0


class TestRecommendSize:
    """Tests for size-based recommendations."""

    def test_oversized_movie_medium(self) -> None:
        """Movie exceeding max_size should be medium priority."""
        items = [_make_movie(codec="hevc", size_gb=6.0)]
        prefs = LibraryPreferences(video=VideoPreferences(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].priority == PRIORITY_MEDIUM

    def test_very_oversized_movie_high(self) -> None:
        """Movie exceeding 2x max should be high priority."""
        items = [_make_movie(codec="hevc", size_gb=9.0)]
        prefs = LibraryPreferences(video=VideoPreferences(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.items[0].priority == PRIORITY_HIGH

    def test_savings_estimated(self) -> None:
        """Estimated savings should be current_size - max_size."""
        items = [_make_movie(codec="hevc", size_gb=6.0)]
        prefs = LibraryPreferences(video=VideoPreferences(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)
        assert result.items[0].estimated_savings_gb == pytest.approx(2.0, abs=0.1)


class TestRecommendAudio:
    """Tests for audio-based recommendations."""

    def test_vo_when_multi_preferred(self) -> None:
        """VO movie when multi preferred should be recommended."""
        items = [_make_movie(audio_lang="eng", audio_profile="vo")]
        prefs = LibraryPreferences()  # default: multi > vf > vostfr > vo
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert "audio" in result.items[0].reasons[0].lower()

    def test_multi_audio_no_recommendation(self) -> None:
        """MULTI movie should not be recommended for audio."""
        items = [_make_movie(audio_profile="multi")]
        prefs = LibraryPreferences()
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 0


class TestRecommendSubtitles:
    """Tests for subtitle-based recommendations."""

    def test_missing_required_subtitle_low(self) -> None:
        """Movie without required French subtitles should be low priority."""
        items = [_make_movie(sub_languages=["eng"])]
        prefs = LibraryPreferences()  # default: required=["fra"]
        result = generate_recommendations(items, prefs)
        assert any(r.priority == PRIORITY_LOW for r in result.items)


class TestEncodingRules:
    """Tests for override rule matching."""

    def test_rule_by_imdb_id(self) -> None:
        """Rule matching IMDB ID should override target."""
        items = [_make_movie(codec="hevc", imdb_id="tt4154796")]
        prefs = LibraryPreferences(encoding_rules=[
            EncodingRule(
                criteria=RuleCriteria(imdb_id="tt4154796"),
                resolution="2160p",
            ),
        ])
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].target.resolution == "2160p"
        assert result.items[0].priority == PRIORITY_HIGH
        assert result.items[0].matched_rule_index == 0

    def test_rule_by_title_substring(self) -> None:
        """Rule matching title substring should apply."""
        items = [_make_movie(codec="hevc", title="Animation Movie", size_gb=3.0)]
        prefs = LibraryPreferences(encoding_rules=[
            EncodingRule(
                criteria=RuleCriteria(title="Animation"),
                max_size_gb=2.0,
            ),
        ])
        result = generate_recommendations(items, prefs)
        assert result.total_recommendations == 1
        assert result.items[0].matched_rule_index == 0

    def test_genre_matching_deferred(self) -> None:
        """Genre-based rules are deferred (V14 scope: title + ID only).

        Genre matching requires cross-referencing NFO data, which is
        not yet implemented. Rules with only genre criteria will not match.
        """
        items = [_make_movie(codec="h264")]
        prefs = LibraryPreferences(encoding_rules=[
            EncodingRule(
                criteria=RuleCriteria(genre="Animation"),
                codec="hevc",
            ),
        ])
        result = generate_recommendations(items, prefs)
        # Genre rule does NOT match — still picks up h264→hevc from default prefs
        assert result.total_recommendations == 1
        assert result.items[0].matched_rule_index is None  # default, not rule


class TestDisparateSeries:
    """Tests for mixed-codec series detection."""

    def test_mixed_codec_series(self) -> None:
        """Series with mixed h264/hevc episodes should be flagged."""
        item = LibraryAnalysisItem(
            path="/tmp/Show (2024)", disk="Disk1", category="series",
            media_type="tvshow", title="Show", year=2024,
            files=[
                MediaFileAnalysis(
                    path="/tmp/Show (2024)/Saison 01/S01E01.mkv",
                    size_gb=1.0, duration_seconds=3600,
                    video=VideoInfo(codec="h264", width=1920, height=1080,
                                    bitrate_kbps=5000, hdr=False, hdr_type=None),
                    audio_tracks=[], subtitle_tracks=[],
                    audio_profile="vf", subtitle_languages=[],
                    analyzed_at="2026-04-15T12:00:00",
                ),
                MediaFileAnalysis(
                    path="/tmp/Show (2024)/Saison 01/S01E02.mkv",
                    size_gb=0.5, duration_seconds=3600,
                    video=VideoInfo(codec="hevc", width=1920, height=1080,
                                    bitrate_kbps=3000, hdr=False, hdr_type=None),
                    audio_tracks=[], subtitle_tracks=[],
                    audio_profile="vf", subtitle_languages=[],
                    analyzed_at="2026-04-15T12:00:00",
                ),
            ],
        )
        prefs = LibraryPreferences()
        result = generate_recommendations([item], prefs)
        assert result.total_recommendations == 1
        assert "disparate" in result.items[0].reasons[0].lower() or "mixed" in result.items[0].reasons[0].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_recommender.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement recommender.py**

```python
# personalscraper/library/recommender.py
"""Library recommender — generate re-download recommendations.

Crosses library analysis with user preferences to produce a prioritized
list of items that should be re-downloaded in a better format.
Output format is the contract for future auto-download integration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from personalscraper.library.models import (
    CurrentState,
    LibraryAnalysisItem,
    LibraryRecommendationResult,
    MediaFileAnalysis,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
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
    # IDs come from scan data via id_lookup parameter
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
            reasons.append(f"Very oversized: {f.size_gb:.1f} GB > 2×{vp.max_size_movie_gb:.1f} GB")
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
        path=item.path, title=item.title, media_type=item.media_type,
        disk=item.disk, category=item.category,
        tmdb_id=None, imdb_id=None,  # Enriched by generate_recommendations from scan data
        current=CurrentState(
            codec=f.video.codec, resolution=f.video.resolution,
            size_gb=f.size_gb, audio_profile=f.audio_profile,
            subtitle_languages=f.subtitle_languages,
        ),
        target=target, reasons=reasons, priority=priority,
        estimated_savings_gb=savings, matched_rule_index=matched_rule,
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
    non_preferred = [f for f in item.files if f.video.codec != vp.preferred_codec
                     and f.video.codec not in vp.fallback_codecs]
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
        path=item.path, title=item.title, media_type=item.media_type,
        disk=item.disk, category=item.category,
        tmdb_id=None, imdb_id=None,  # Enriched by generate_recommendations from scan data
        current=CurrentState(
            codec=f.video.codec, resolution=f.video.resolution,
            size_gb=total_size, audio_profile=f.audio_profile,
            subtitle_languages=f.subtitle_languages,
        ),
        target=target, reasons=reasons, priority=priority,
        estimated_savings_gb=savings, matched_rule_index=None,
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
        id_lookup: Optional dict of path → (tmdb_id, imdb_id) from scan data.
            Used to enrich recommendations with IDs for future auto-download.

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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_recommender.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add personalscraper/library/recommender.py tests/library/test_recommender.py
git commit -m "v14.6.1: Implement recommendation engine with priority, savings, encoding rules"
```

---

## Task 2: Add library-recommend CLI command with CSV export

**Files:**

- Modify: `personalscraper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestLibraryRecommend:
    def test_help(self, runner) -> None:
        result = runner.invoke(app, ["library-recommend", "--help"])
        assert result.exit_code == 0
        assert "--sort" in result.output
        assert "--export" in result.output
        assert "--disk" in result.output
        assert "--category" in result.output
```

- [ ] **Step 2: Add `_reconstruct_analysis_items` helper to analyzer.py**

Add to `personalscraper/library/analyzer.py` — this MUST exist before the CLI command imports it:

```python
def _reconstruct_analysis_items(data: dict) -> list[LibraryAnalysisItem]:
    """Reconstruct LibraryAnalysisItem list from JSON data."""
    items = []
    for item_data in data.get("items", []):
        files = []
        for f_data in item_data.get("files", []):
            vid = f_data.get("video", {})
            files.append(MediaFileAnalysis(
                path=f_data.get("path", ""),
                size_gb=f_data.get("size_gb", 0),
                duration_seconds=f_data.get("duration_seconds"),
                video=VideoInfo(
                    codec=vid.get("codec", ""), width=vid.get("width", 0),
                    height=vid.get("height", 0),
                    bitrate_kbps=vid.get("bitrate_kbps"),
                    hdr=vid.get("hdr", False), hdr_type=vid.get("hdr_type"),
                ),
                audio_tracks=[
                    AudioTrack(
                        codec=a.get("codec", ""), language=a.get("language", "und"),
                        channels=a.get("channels", 2), is_atmos=a.get("is_atmos", False),
                        is_default=a.get("is_default", False),
                    ) for a in f_data.get("audio_tracks", [])
                ],
                subtitle_tracks=[
                    SubtitleTrack(
                        language=s.get("language", "und"), format=s.get("format", "unknown"),
                        forced=s.get("forced", False), is_default=s.get("is_default", False),
                    ) for s in f_data.get("subtitle_tracks", [])
                ],
                audio_profile=f_data.get("audio_profile", "vo"),
                subtitle_languages=f_data.get("subtitle_languages", []),
                analyzed_at=f_data.get("analyzed_at", ""),
            ))
        items.append(LibraryAnalysisItem(
            path=item_data.get("path", ""),
            disk=item_data.get("disk", ""),
            category=item_data.get("category", ""),
            media_type=item_data.get("media_type", "movie"),
            title=item_data.get("title", ""),
            year=item_data.get("year"),
            files=files,
        ))
    return items
```

- [ ] **Step 3: Add library-recommend command to cli.py**

```python
@app.command()
@handle_cli_errors
def library_recommend(
    sort: str = typer.Option("priority", "--sort", help="Sort by: priority, size, codec"),
    export: str = typer.Option(None, "--export", help="Export format: csv"),
) -> None:
    """Generate re-download recommendations from library analysis.

    Requires library-analyze to have been run first.
    Reads library_analysis.json and library_preferences.json.

    Examples:
        personalscraper library-recommend
        personalscraper library-recommend --sort size
        personalscraper library-recommend --export csv
    """
    import csv
    import io
    import json

    from personalscraper.library.models import read_json, write_json
    from personalscraper.library.preferences import LibraryPreferences
    from personalscraper.library.recommender import generate_recommendations
    from personalscraper.library.models import LibraryAnalysisItem

    console = state["console"]
    settings = get_settings()

    # Load analysis
    analysis_path = settings.data_dir / "library_analysis.json"
    if not analysis_path.exists():
        console.print("[red]No analysis found. Run library-analyze first.[/red]")
        raise typer.Exit(1)

    analysis_data = read_json(analysis_path)

    # Load preferences
    prefs_path = settings.data_dir / settings.library_preferences_file
    if prefs_path.exists():
        prefs = LibraryPreferences.model_validate_json(prefs_path.read_text())
    else:
        prefs = LibraryPreferences()
        console.print("[yellow]No preferences file found, using defaults.[/yellow]")

    # Reconstruct analysis items (simplified — from JSON dicts)
    from personalscraper.library.analyzer import _reconstruct_analysis_items
    items = _reconstruct_analysis_items(analysis_data)

    result = generate_recommendations(items, prefs)

    # Sort
    sort_keys = {
        "priority": lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.priority, 3),
        "size": lambda r: -(r.estimated_savings_gb or 0),
        "codec": lambda r: r.current.codec,
    }
    if sort in sort_keys:
        result.items.sort(key=sort_keys[sort])

    # Write JSON
    output_path = settings.data_dir / "library_recommendations.json"
    write_json(result, output_path)

    # CSV export
    if export == "csv":
        csv_path = settings.data_dir / "library_recommendations.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "type", "disk", "codec", "resolution",
                             "size_gb", "audio", "priority", "savings_gb", "reasons"])
            for r in result.items:
                writer.writerow([
                    r.title, r.media_type, r.disk,
                    r.current.codec, r.current.resolution,
                    f"{r.current.size_gb:.1f}", r.current.audio_profile,
                    r.priority, f"{r.estimated_savings_gb or 0:.1f}",
                    "; ".join(r.reasons),
                ])
        console.print(f"[green]CSV exported:[/green] {csv_path}")

    console.print(
        f"[green]Recommendations:[/green] {result.total_recommendations} items, "
        f"~{result.estimated_total_savings_gb:.1f} GB potential savings → {output_path}"
    )
```

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_cli.py::TestLibraryRecommend tests/library/test_recommender.py -v`
Expected: ALL PASS

```bash
git add personalscraper/library/recommender.py personalscraper/library/analyzer.py personalscraper/cli.py tests/
git commit -m "v14.6.2: Add library-recommend CLI with CSV export and sort options"
```

---

## Acceptance Criteria — Phase 6

- [ ] Rejected codecs → high priority, non-preferred → medium, fallback → no recommendation
- [ ] Size 2× max → high, >max → medium, savings estimated
- [ ] Encoding rules match by imdb_id, tmdb_id, title substring
- [ ] Disparate series (mixed codecs) detected and flagged
- [ ] Audio profile ranking works (multi best, vo worst)
- [ ] `--sort size|codec|priority` and `--export csv` functional
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`
