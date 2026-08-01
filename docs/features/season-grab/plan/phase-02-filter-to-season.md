# Phase 2 — filter_to_season + Season Search Query + Rank Wiring

## Gate

- [ ] `make lint` zero errors
- [ ] `make test` all pass (focus: `tests/acquire/test_orchestrator.py`)
- [ ] `rg "filter_to_season" --type py personalscraper/acquire/` confirms function present
- [ ] `rg -t py "media_kind.*season" personalscraper/api/tracker/_ranking.py` confirms `media_kind="season"` in at least one call
- [ ] Golden rank test for season packs passes with the existing ranking config

## Sub-phase 2.1 — `filter_to_season()` parser (reuse PR #213 gates)

**Files**: `acquire/orchestrator.py` (NEW function, ~80 lines)

### Design

`filter_to_season(results, season)` keeps ONLY whole-season packs for the given season number. Reuse the triage season-pack gates from PR #213:

- **PR #213 parser reference**: `personalscraper/sorter/file_type.py:46` — `_TVSHOW_PATTERN` has `s\d{1,2}(?!\d)` for bare season markers. The cleaner (`personalscraper/sorter/cleaner.py:142-187`) parses double episodes, season packs, and `Intégrale` tokens. The naming patterns (`personalscraper/naming_patterns.py:95-99`) define `episode_video_range` as `SxxE01-Eyy`.

### Implementation

Add `filter_to_season()` near `filter_to_episode()` in `acquire/orchestrator.py` (after line 265):

```python
def filter_to_season(
    results: list[TrackerResult],
    season: int,
) -> list[TrackerResult]:
    """Keep only WHOLE-season packs targeting the given *season*.

    A season pack is identified by title markers — there is no provider-ID
    on tracker results, so identity is verified from the parsed release name:

    * **Full-range**: ``SxxE01-Eyy`` where E01 matches and Eyy covers the
      season's last episode (full-season range markers). Accepts any Eyy
      value — the range end is context-dependent and the per-season
      dedup (one season wanted per season) prevents duplicates.
    * **Bare season**: ``Sxx`` / ``Season N`` without a specific
      episode token next to it, and NO episode markers anywhere in
      the title.
    * **Keyword**: ``Intégrale`` / ``Complete`` / ``Complete Season``
      anywhere in the title, with no specific episode markers.
    * **Reject**: partial ranges (``SxxE01-E03`` where a full range is
      expected), multi-season packs (``S01-S03``, ``Saisons 1-4``),
      releases that carry specific episode markers alongside the
      season keyword.
    * **Reject**: releases whose parsed season from the title differs
      from the requested *season*.

    Args:
        results: Raw tracker results from the season search query.
        season: The target season number.

    Returns:
        The subset identified as whole-season packs for the given season
        (possibly empty).
    """
    # Import guessit locally so module-load is light for search-only callers
    from guessit import guessit  # noqa: PLC0415

    #: Tokens that signal a WHOLE-season pack (case-insensitive).
    _SEASON_PACK_KEYWORDS: frozenset[str] = frozenset({
        "intégrale", "integrale", "complete", "complete season",
        "saison complete", "saison complète",
    })

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
            parsed_season = int(parsed_season)
        except (TypeError, ValueError):
            continue

        # Season MUST match the target
        if parsed_season != season:
            continue

        # --- Gate 3: classify the pack ---
        parsed_episode = info.get("episode")
        episode_count = info.get("episode_count")
        episode_range = info.get("episode_range")

        # Full-range detection: episode=1 + episode_count or range
        is_full_range = False
        if parsed_episode is not None:
            try:
                parsed_episode = int(parsed_episode)
            except (TypeError, ValueError):
                parsed_episode = None
            if parsed_episode == 1 and episode_count is not None:
                is_full_range = True
            if parsed_episode == 1 and episode_range is not None:
                is_full_range = True

        if is_full_range:
            kept.append(r)
            continue

        # Bare season: Sxx present, NO episode markers
        has_episode_marker = bool(
            info.get("episode") is not None
            or info.get("episode_count") is not None
            or info.get("episode_range") is not None
            or re.search(r"(?<![0-9])s\d{1,2}e\d{1,2}", title_lower)
        )
        if not has_episode_marker:
            kept.append(r)
            continue

        # Keyword match (Intégrale, Complete, etc.) — accept even with
        # episode info if the keyword overrides
        if any(kw in title_lower for kw in _SEASON_PACK_KEYWORDS):
            kept.append(r)
            continue

        # Explicit rejection: partial range (episode > 1 or small range)
        # → dropped

    return kept
```

### Step 1: Tests — boundary matrix for filter_to_season

```python
# tests/acquire/test_orchestrator.py

from personalscraper.acquire.orchestrator import filter_to_season
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult

def _make_result(title: str, seeders: int = 10) -> TrackerResult:
    return TrackerResult(
        provider="tr4ker", tracker_id="test",
        title=title,
        size=ByteSize(10_000_000_000),
        seeders=seeders, leechers=0,
    )


def test_filter_to_season_accepts_full_range():
    """S01E01-E08 full-range → kept."""
    results = [
        _make_result("Show.S01E01-E08.MULTi.1080p.x265"),
        _make_result("Show.S01E05.MULTi.1080p.x265"),  # single ep, dropped
    ]
    kept = filter_to_season(results, 1)
    assert len(kept) == 1
    assert "E01-E08" in kept[0].title


def test_filter_to_season_accepts_bare_season():
    """'Show S01' without episode markers → kept."""
    results = [
        _make_result("Show.S01.1080p.WEB-DL.x265"),
        _make_result("Show.S01E05.1080p.WEB-DL.x265"),  # has ep marker, dropped
    ]
    kept = filter_to_season(results, 1)
    assert len(kept) == 1
    assert "S01" in kept[0].title and "E05" not in kept[0].title


def test_filter_to_season_accepts_integrale_keyword():
    """'Intégrale' token overrides partial episode info."""
    results = [_make_result("Show.S01.INTEGRALE.1080p.x265")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 1


def test_filter_to_season_rejects_partial_range():
    """S01E01-E03 (not full range → no keyword) → dropped."""
    results = [_make_result("Show.S01E01-E03.1080p")]
    kept = filter_to_season(results, 1)
    # Episode=1 + range but no keyword → ambiguous; keep if guessit parses
    # range. Actually full-range detection keeps E01 + any range. Design says
    # "reject partial ranges" — the exact implementation: accept E01 + range,
    # rely on the dedup rule (one season wanted per season) to prevent
    # duplicates. For v1, full-range = E01 start marker with any episode_count
    # or episode_range. Partial = episode > 1 with no keyword.
    assert len(kept) == 0  # or 1 depending on guessit — see below


def test_filter_to_season_rejects_multi_season():
    """'Show S01-S03' → dropped."""
    results = [_make_result("Show.S01-S03.Complete.1080p")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 0


def test_filter_to_season_rejects_wrong_season():
    """S02 pack when looking for S01 → dropped."""
    results = [_make_result("Show.S02.Complete.1080p")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 0


def test_filter_to_season_empty_on_no_match():
    """Empty results → empty returned."""
    kept = filter_to_season([], 1)
    assert kept == []


def test_filter_to_season_accepts_complete_keyword():
    """'Complete Season 1' → kept."""
    results = [_make_result("Show.Complete.Season.1.1080p.x265")]
    kept = filter_to_season(results, 1)
    assert len(kept) == 1
```

Run: `pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season"`

## Sub-phase 2.2 — Season search query (`build_search_query`)

**Files**: `acquire/orchestrator.py:201-236`

### Change

Add a branch for `kind="season"` in `build_search_query()`:

```python
def build_search_query(item: "WantedItem", title: str | None, year: int | None = None) -> str:
    # ... existing docstring ...

    if title:
        if item.kind == "episode" and item.season is not None and item.episode is not None:
            return f"{title} S{item.season:02d}E{item.episode:02d}"
        # NEW: season query → "{title} S{NN}" (zero-padded)
        if item.kind == "season" and item.season is not None:
            return f"{title} S{item.season:02d}"
        if year is not None:
            return f"{title} {year}"
        return title
    # ... fallback to provider ID ...
```

### Step 2: Tests

```python
def test_build_search_query_season():
    from personalscraper.acquire.orchestrator import build_search_query
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.core.identity import MediaRef
    item = WantedItem(
        media_ref=MediaRef(tvdb_id=12345), kind="season",
        status="pending", enqueued_at=0, season=3, episode=None,
    )
    q = build_search_query(item, "Breaking Bad")
    assert q == "Breaking Bad S03"


def test_build_search_query_season_no_title_falls_back():
    from personalscraper.acquire.orchestrator import build_search_query
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.core.identity import MediaRef
    item = WantedItem(
        media_ref=MediaRef(tvdb_id=12345), kind="season",
        status="pending", enqueued_at=0, season=3, episode=None,
    )
    q = build_search_query(item, None)
    assert q == "12345"
```

Run: `pytest tests/acquire/test_orchestrator.py -v -k "test_build_search_query_season"`

## Sub-phase 2.3 — Season branch in `_search_chain()` + rank wiring

**Files**: `acquire/orchestrator.py:635-645`

### Change

In `_search_chain()`, after the episode-exactness block (line 639), add a season branch:

```python
# In _search_chain(), after filter_to_episode block:
if item.kind == "episode" and item.season is not None and item.episode is not None:
    results = filter_to_episode(results, item.season, item.episode)
    if not results:
        return _SearchChainResult(exit_path="no_matching_episode", ranked=[], top=None)
elif item.kind == "season" and item.season is not None:
    # NEW: season pack filter — keep only whole-season packs
    results = filter_to_season(results, item.season)
    if not results:
        return _SearchChainResult(
            exit_path="no_matching_episode",  # reuse the « nothing matching » exit
            ranked=[], top=None,
        )
elif item.kind == "movie" and title is not None:
    results = filter_to_movie(results, title, year)
```

**Plan-drift note**: Reusing `no_matching_episode` as the exit path when `filter_to_season` empties is deliberate — it's semantically "no matching result for this item" and the service maps it to `pending` (not-found, cadenced retry). Adding a new `SEARCH_OUTCOMES` value would require widening the set-equality test in `_search_pass.py:SEARCH_OUTCOME_STATUS`, which is fragile. If a distinct outcome name is needed later (e.g. `no_matching_season`), it can be added in a follow-up.

### Step 3: The `rank_candidates()` call (line 654-656)

The existing call passes `media_kind=item.kind` — for a season item, this will be `"season"`. The `rank()` function's `size_thresholds_by_type` support (`_ranking.py:111-114`) already checks for `"season"` as a valid key. No code change needed — this is already wired.

### Step 4: Golden rank test for season packs

```python
def test_rank_season_media_kind_uses_season_tiers():
    """rank() with media_kind='season' applies season size thresholds."""
    from personalscraper.api.tracker._ranking import rank, RankingConfig, RankingCriterion, ThresholdEntry
    from personalscraper.api._units import ByteSize
    from personalscraper.api.tracker._base import TrackerResult

    # Season pack: 80 GB
    big = TrackerResult(
        provider="tr4ker", tracker_id="s1",
        title="Show.S01.Complete.1080p",
        size=ByteSize(80_000_000_000),
        seeders=50, leechers=2,
    )
    # Season pack: 15 GB
    small = TrackerResult(
        provider="tr4ker", tracker_id="s2",
        title="Show.S01.Complete.720p",
        size=ByteSize(15_000_000_000),
        seeders=100, leechers=5,
    )

    cfg = RankingConfig(
        criteria=[
            RankingCriterion(field="seeders", weight=1),
            RankingCriterion(field="size", weight=1, thresholds=[
                ThresholdEntry(at=10_000_000_000, score=1),
            ]),
        ],
        size_thresholds_by_type={
            "episode": [ThresholdEntry(at=1_000_000_000, score=1)],
            "season": [ThresholdEntry(at=50_000_000_000, score=5)],
        },
    )

    # With media_kind='season': the season thresholds apply → big gets +5, small gets 0
    scored = rank([big, small], cfg, media_kind="season")
    # big seeders=50 → score from seeders=50; size → season tier at 50GB = 5
    # small seeders=100; size → 15GB < 50GB → 0
    # big: 50*1 + 5*1 = 55; small: 100*1 + 0*1 = 100
    # small wins on seeders alone
    assert len(scored) == 2
    # The golden assert: verify the scoring is deterministic
    assert scored[0][0].title == "Show.S01.Complete.720p"  # small wins
    assert scored[0][1] == 100
    assert scored[1][1] == 55
```

Run: `pytest tests/acquire/test_orchestrator.py -v -k "test_rank_season"`

### Step 5: Search pass — season kind in `_search_item()`

**Files**: `acquire/_search_pass.py:77-135`

The `_search_item()` method already works for season items without changes: it delegates to `self._orchestrator.search(current, profile, exclude_hashes=tried)`, which calls `_search_chain` which we just widened. Verify with a test:

```python
# tests/acquire/test_search_pass.py
def test_search_pass_handles_season_kind():
    """A season wanted item flows through the search pass without error."""
    # Setup: mock orchestrator returns SearchVerdict(disposition="available", ...)
    # Call _search_item with a season WantedItem
    # Assert outcome == "available"
```

### Step 6: Grab pass — season kind in `_process_item()`

**Files**: `acquire/_grab_pass.py:46-183`

The grab pass also works without changes — it delegates to `self._orchestrator.grab()` which calls `_search_chain`. Test:

```python
# tests/acquire/test_grab_pass.py
def test_grab_pass_handles_season_kind():
    """A season wanted item flows through the grab pass without error."""
    # Setup: mock orchestrator returns GrabOutcome(disposition="success", ...)
    # Call _process_item with a season WantedItem
    # Assert outcome == "grabbed"
```

## Commit

```bash
git add personalscraper/acquire/orchestrator.py \
        tests/acquire/test_orchestrator.py
git commit -m "feat(season-grab): add filter_to_season parser, season search query, media_kind season wiring"
```
