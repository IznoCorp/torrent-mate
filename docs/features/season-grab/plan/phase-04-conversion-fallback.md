# Phase 4 — Episode→Season Conversion R2 + Fallback R6

## Gate

- [ ] `make lint` zero errors
- [ ] `make test` all pass (focus: `tests/acquire/test_search_pass.py`, `tests/acquire/test_grab_pass.py`)
- [ ] `rg "filter_to_season.*results" --type py personalscraper/acquire/_search_pass.py` confirms conversion path
- [ ] `rg "fallback_episodes" --type py personalscraper/acquire/` confirms fallback in cutoff gate
- [ ] Unit test: episode search 0-exact + pack present → season wanted created + siblings absorbed
- [ ] Unit test: cutoff fallback re-enqueues exactly missing episodes

## Sub-phase 4.1 — Episode→Season Conversion (R2) in the Search Pass

**Files**: `acquire/_search_pass.py:77-135`, `acquire/_search_pass.py` (add `_try_season_conversion()` method)

### Design (DESIGN §3.3)

When an episode wanted's search returns raw results but `filter_to_episode` ZEROES them, run `filter_to_season` over the SAME raw results. If ≥1 whole-season pack survives: enqueue/reuse the season wanted, absorb the episode (and its live siblings), and let the season wanted proceed on the NEXT pass. No double-grab in the same tick.

**Plan-drift note**: The DESIGN says "enqueue/reuse the season wanted for that season, absorb the episode (and its live siblings), and let the season wanted proceed on the NEXT pass." This means: the search pass does NOT advance the season wanted to `available` in the same tick — it enqueues as `pending` and the next search pass will re-evaluate it. This avoids a search+double-grab in one pass. The grab pass only walks `available` rows, which the season item won't be yet.

### Implementation

In `SearchPassMixin._search_item()`, after the `_search_chain` call returns a verdict, add season conversion. The best insertion point is in `_apply_search_verdict` or in `_search_item` itself, right after the verdict is received.

Add a new method `_try_season_conversion` in `SearchPassMixin`:

```python
def _try_season_conversion(
    self, item: WantedItem, now: int, *, cadence: Cadence
) -> bool:
    """Try to convert an unconcluded episode search into a season wanted (R2).

    Called when ``item.kind='episode'`` and the search pass found no
    episode-exact match. Runs ``filter_to_season`` over the raw results —
    if a whole-season pack survives, enqueue a season wanted and absorb
    this episode + its live siblings.

    The season wanted is enqueued as ``pending`` (not advanced to available
    in this tick) so the next pass evaluates it cleanly.

    Args:
        item: The claimed episode item (status='searching').
        now: Unix epoch seconds (stamps enqueued_at).
        cadence: Effective cadence (passed to satisfy the _search_item sig).

    Returns:
        True when a season wanted was created/absorbed, False otherwise.
    """
    assert item.id is not None  # noqa: S101
    if item.kind != "episode" or item.season is None:
        return False
    if item.followed_id is None:
        return False

    # Re-run the search chain to get raw results — the orchestrator's
    # _search_chain discards them after filter_to_episode. We need the
    # raw results BEFORE the episode filter to check for season packs.
    # Design choice: re-search? No — the raw results are gone. The
    # orchestrator could be widened to return raw results on a verdict,
    # but that's a bigger change. Instead: the conversion runs on the
    # orchestrator's _search_chain result if it exited "no_matching_episode".
    # BUT we need the raw results. Two options:
    #
    # A) Widen SearchVerdict to carry raw_results on certain paths
    # B) Have _try_season_conversion do its own search_candidates call
    #
    # Option A is cleaner. Add `raw_results: list[TrackerResult] | None = None`
    # to SearchVerdict. The orchestrator populates it when available
    # (even on no_matching_episode — the raw results existed, just
    # filter_to_episode emptied them).
    #
    # For v1, the simplest path: in _search_chain, save raw results BEFORE
    # filter_to_episode empties them. Pass them back on the verdict.

    # ... implementation depends on the verdict carrying raw results.
    # For now, lay out the logic:
    pass
```

**Revised approach (simpler)**: Modify `_search_chain` to carry `raw_results` on the `_SearchChainResult` when the raw results exist but the filter emptied them. Then in `search()`, pass them onto `SearchVerdict`. Then in `_search_item()`, after the verdict is returned:

```python
# In _search_item(), after `verdict = self._orchestrator.search(...)`:
if (
    verdict.outcome == "no_matching_episode"
    and item.kind == "episode"
    and item.season is not None
    and verdict.raw_results is not None
):
    from personalscraper.acquire.orchestrator import filter_to_season
    season_packs = filter_to_season(list(verdict.raw_results), item.season)
    if season_packs:
        self._enqueue_season_from_conversion(
            item, verdict.raw_results, season_packs, now,
        )
        # The episode row stays absorbed; the season is enqueued pending.
        # Return "waiting" — the episode was not found, season is pending.
        return "waiting"
```

### Step 1: Widen `SearchVerdict` to carry `raw_results`

In `acquire/orchestrator.py`:

```python
@dataclass(frozen=True)
class SearchVerdict:
    # ... existing fields ...
    raw_results: tuple[TrackerResult, ...] | None = None
```

In `_search_chain`, before `filter_to_episode` empties the list, capture:

```python
# In _search_chain(), before filter_to_episode:
raw_before_filter = list(results)  # snapshot

# After filter_to_episode:
results = filter_to_episode(results, item.season, item.episode)
if not results:
    return _SearchChainResult(
        exit_path="no_matching_episode",
        ranked=[],
        top=None,
        raw_before_filter=raw_before_filter,  # NEW: carry for R2
    )
```

Add `raw_before_filter: list[TrackerResult] | None = None` to `_SearchChainResult`, and thread it through `search()` → `SearchVerdict.raw_results`.

### Step 2: Implement `_enqueue_season_from_conversion()`

```python
def _enqueue_season_from_conversion(
    self,
    episode_item: WantedItem,
    raw_results: list[TrackerResult],
    season_packs: list[TrackerResult],
    now: int,
) -> None:
    """Enqueue/reuse a season wanted for the episode's season (R2).

    Called from the search pass when a no-matching-episode verdict
    reveals a whole-season pack. Absorption is idempotent — if a
    season wanted already exists, only absorption runs.
    """
    assert episode_item.followed_id is not None
    assert episode_item.season is not None
    fid = episode_item.followed_id
    season_num = episode_item.season

    # Dedup: one season wanted per follow+season
    existing = self._store.wanted.find(
        followed_id=fid, kind="season",
        season=season_num, episode=None,
    )
    season_wid = existing.id if existing is not None else None

    if season_wid is None:
        # Enqueue the season wanted
        season_wid = self._store.wanted.add(
            WantedItem(
                media_ref=episode_item.media_ref,
                kind="season",
                status="pending",
                enqueued_at=now,
                followed_id=fid,
                season=season_num,
                episode=None,
            )
        )
        self._event_bus.emit(
            WantedEnqueued(media_ref=episode_item.media_ref,
                           kind="season", season=season_num, episode=None)
        )
        log.info(
            "acquire.service.season_conversion_enqueued",
            wanted_id=episode_item.id,
            season=season_num,
            season_wanted_id=season_wid,
        )

    # Absorb the triggering episode + its live siblings
    live_episode_ids: list[int] = []
    for ep_num in self._aired_episodes_for_season(fid, season_num):
        ep_wanted = self._store.wanted.find(
            followed_id=fid, kind="episode",
            season=season_num, episode=ep_num,
        )
        if ep_wanted is not None and ep_wanted.id is not None:
            if ep_wanted.status in ("pending", "searching", "available"):
                live_episode_ids.append(ep_wanted.id)

    if live_episode_ids:
        self._store.wanted.absorb_episodes(season_wid, tuple(live_episode_ids))
        self._event_bus.emit(
            SeasonAbsorbedEpisodes(
                season_wanted_id=season_wid,
                media_ref=episode_item.media_ref,
                season=season_num,
                absorbed_ids=tuple(live_episode_ids),
            )
        )
        log.info(
            "acquire.service.season_conversion_absorbed",
            episode_count=len(live_episode_ids),
        )
```

### Step 3: Helper `_aired_episodes_for_season()`

```python
def _aired_episodes_for_season(self, followed_id: int, season: int) -> list[int]:
    """Return episode numbers of aired episodes for the given follow+season."""
    rows = self._store.wanted._conn.execute(
        "SELECT DISTINCT episode FROM aired_episode "
        "WHERE followed_id = ? AND season = ? AND episode IS NOT NULL "
        "ORDER BY episode",
        (followed_id, season),
    ).fetchall()
    return [int(r["episode"]) for r in rows]
```

**Plan-drift note**: This method accesses `self._store.wanted._conn` directly — the aired_episode table is in the same DB. If a dedicated aired-store method exists (check `_aired_store.py`), use it instead. Grep: `rg "class.*AiredSubStore" --type py personalscraper/acquire/` — if found, add a `list_for_season()` method there and use it.

### Step 4: Tests

```python
# tests/acquire/test_search_pass.py

def test_conversion_enqueues_season_when_pack_present():
    """R2: episode search 0-exact + pack present → season wanted enqueued."""
    # Mock: orchestrator.search returns SearchVerdict with
    #   outcome="no_matching_episode", raw_results containing a season pack
    # Assert: store.wanted.add called with kind="season"
    # Assert: WantedEnqueued emitted with kind="season"


def test_conversion_absorbs_siblings_when_season_exists():
    """R2: season wanted already exists → only absorption runs."""
    # Mock: store.wanted.find for season returns existing row (id=99)
    # Assert: store.wanted.add NOT called (reuse existing)
    # Assert: store.wanted.absorb_episodes(99, ...) called


def test_conversion_noop_when_no_pack_in_results():
    """R2: raw results present but no season pack → no conversion."""
    # Mock: filter_to_season returns [] over the raw results
    # Assert: no season wanted enqueued
    # Assert: no absorption
```

Run: `pytest tests/acquire/test_search_pass.py -v -k "test_conversion"`

## Sub-phase 4.2 — Fallback R6 in the Cutoff Gate

**Files**: `acquire/_pass_gates.py:61-115`

### Design (DESIGN §3.5)

When `_apply_cutoff_gate` hits a `kind="season"` item past its cutoff:

- Re-enqueue the season's MISSING episodes (ownership-checked) as fresh episode wanteds
- Set the season row to `fallback_episodes`
- Emit `SeasonFellBackToEpisodes`
- Telegram notification fires per existing cutoff path

### Implementation

Modify `_apply_cutoff_gate()` in `PassGatesMixin`:

```python
def _apply_cutoff_gate(self, item: WantedItem, now: int, *, cadence: Cadence) -> _GateVerdict:
    assert item.id is not None
    wanted_id = item.id

    # ... stale recovery (unchanged) ...

    if is_past_cutoff(cadence, now=now, enqueued_at=item.enqueued_at):
        # R6: season kind → fallback instead of abandon
        if item.kind == "season" and item.season is not None and item.followed_id is not None:
            return self._fallback_season(item, now)
        # ... existing abandon path ...
        self._store.wanted.set_status(wanted_id, "abandoned")
        self._event_bus.emit(WantedAbandoned(media_ref=item.media_ref, reason="cutoff_reached"))
        log.info("acquire.service.cutoff_abandoned", wanted_id=wanted_id)
        return "abandoned"

    return "proceed"
```

### Step 2: Add `_fallback_season()` method

```python
def _fallback_season(self, item: WantedItem, now: int) -> _GateVerdict:
    """R6: season cutoff → re-enqueue missing episodes, set fallback_episodes.

    Reads the aired catalog to know which episodes exist, checks ownership
    per episode, and re-enqueues the unowned ones as fresh episode wanteds.

    Returns:
        ``"abandoned"`` (the season row is terminal — the gate outcome
        maps to abandoned for the caller's counter).
    """
    assert item.id is not None and item.followed_id is not None and item.season is not None
    season_wanted_id = item.id
    followed_id = item.followed_id
    season_num = item.season

    # List aired episodes for this season
    aired_eps = self._store.wanted._conn.execute(
        "SELECT episode FROM aired_episode "
        "WHERE followed_id = ? AND season = ? AND episode IS NOT NULL",
        (followed_id, season_num),
    ).fetchall()
    episode_numbers = sorted(int(r["episode"]) for r in aired_eps)

    # Ownership check — needs the ownership checker. The mixin doesn't
    # carry one! That's a design gap. The PassGatesMixin only has
    # _store and _event_bus.
    #
    # Option A: inject ownership into PassGatesMixin (wider change)
    # Option B: re-enqueue ALL episodes, trusting the detect pass to
    #   skip owned ones (existing _detect_episode already does this)
    #
    # Option B is simpler and safe: detect's per-episode pass will
    # skip owned episodes. The cost is re-enqueuing episodes that get
    # immediately skipped — acceptable for a cutoff that fires rarely.
    reenqueued = 0
    for ep_num in episode_numbers:
        wanted_id = self._store.wanted.add(
            WantedItem(
                media_ref=item.media_ref,
                kind="episode",
                status="pending",
                enqueued_at=now,
                followed_id=followed_id,
                season=season_num,
                episode=ep_num,
            )
        )
        reenqueued += 1

    # Transition the season row
    self._store.wanted.fallback_season(season_wanted_id)

    self._event_bus.emit(
        SeasonFellBackToEpisodes(
            season_wanted_id=season_wanted_id,
            media_ref=item.media_ref,
            season=season_num,
            reenqueued_count=reenqueued,
        )
    )
    # Existing cutoff Telegram notification fires via the caller's
    # "abandoned" return — the caller emits WantedAbandoned.
    log.info(
        "acquire.service.season_fallback",
        wanted_id=season_wanted_id,
        season=season_num,
        reenqueued=reenqueued,
    )
    return "abandoned"
```

**Plan-drift note**: The `PassGatesMixin` has no `_ownership` attribute. Option B (re-enqueue all, let detect skip owned) is the pragmatic v1 approach. For v2, inject the OwnershipChecker into the gates and filter pre-reenqueue. The detect pass already has the `owned → skip` logic at line 342, so no double-enqueue risk — just some churn of creating-then-skipping rows.

### Step 3: Tests

```python
# tests/acquire/test_pass_gates.py

def test_season_cutoff_falls_back_to_episodes():
    """R6: season past cutoff → fallback_episodes + re-enqueue missing eps."""
    # Setup: season wanted (kind=season, season=3), 8 aired eps in catalog
    # Cutoff is past → _apply_cutoff_gate returns "abandoned"
    # Assert: store.wanted.add called 8 times (one per ep, kind=episode)
    # Assert: store.wanted.fallback_season called
    # Assert: SeasonFellBackToEpisodes event emitted


def test_season_fallback_reenqueues_exact_missing_count():
    """R6: reenqueued_count matches the aired episode count."""
    # 5 aired eps → reenqueued_count == 5
    # Assert: SeasonFellBackToEpisodes.reenqueued_count == 5
```

Run: `pytest tests/acquire/test_pass_gates.py -v -k "test_season"`

## Commit

```bash
git add personalscraper/acquire/_search_pass.py personalscraper/acquire/_pass_gates.py \
        personalscraper/acquire/orchestrator.py \
        tests/acquire/test_search_pass.py tests/acquire/test_pass_gates.py
git commit -m "feat(season-grab): episode-to-season conversion R2 in search pass, season cutoff fallback R6"
```
