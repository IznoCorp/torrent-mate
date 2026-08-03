# Phase 3 — Auto Detection R1 + Absorption R5

## Gate

- [ ] `make lint` zero errors
- [ ] `make test` all pass (focus: `tests/acquire/test_detect.py`)
- [ ] `rg "detect.*season" --type py personalscraper/acquire/detect.py` confirms season detection path
- [ ] Boundary matrix tests: aired-exactly-7-days, exactly-half-owned both pass
- [ ] `personalscraper follow detect --dry-run` on real store reports season candidates

## Sub-phase 3.1 — Season detection pass in `DetectService`

**Files**: `acquire/detect.py` (add `_detect_seasons()` method, ~100 lines)

### Design (DESIGN §3.2)

After the per-episode pass, group aired episodes by season. For each season where:

- (a) ALL episodes have aired (`air_date <= today` — already filtered by `ep.air_date > today: continue` at line 225)
- (b) `last_air_date <= today - 7d` (the season's LAST episode aired ≥ 1 week ago)
- (c) `owned_count <= total/2` (ownership predicate per episode, RP6)
- (d) No live season wanted exists (dedup, one per follow+season)
- (e) Season is not fully owned

Then: enqueue the season wanted + absorb (R5) the season's live episode wanteds.

### Implementation

Add to `DetectService` after `_detect_episode` (after line 409):

```python
def _detect_seasons(
    self,
    aired: "list[AiredEpisode]",
    by_ref: "dict[MediaRef, FollowedSeries]",
    actions: list[DetectAction],
    counts: "_MutableCounts",
    *,
    dry_run: bool,
    now: int,
    today: "date",
) -> None:
    """Post-pass: group aired episodes by season and enqueue season wanteds (R1).

    Runs AFTER the per-episode pass so episode wanteds exist when absorption
    runs. One season wanted per follow+season — same dedup rule as movies.

    Args:
        aired: Every aired episode (air_date <= today, per filter at line 225).
        by_ref: Followed-series lookup by MediaRef.
        actions: Output list (mutated).
        counts: Running counters (mutated).
        dry_run: When True, no writes or events happen.
        now: Unix epoch seconds (stamps enqueued_at).
        today: The reference date (for the 7-day gate).
    """
    from datetime import timedelta

    # Group aired episodes by (followed_id, season)
    season_eps: dict[tuple[int, int], list[AiredEpisode]] = {}
    for ep in aired:
        fs = by_ref.get(ep.media_ref)
        if fs is None or fs.id is None:
            continue
        key = (fs.id, ep.season)
        season_eps.setdefault(key, []).append(ep)

    cutoff = today - timedelta(days=7)

    for (followed_id, season_num), eps in season_eps.items():
        total = len(eps)

        # (b) Last aired date must be >= 7 days ago
        last_air = max(ep.air_date for ep in eps)
        if last_air > cutoff:
            continue

        # (c) Count owned episodes
        owned = 0
        for ep in eps:
            try:
                if self._ownership.owns(ep.media_ref, kind="episode",
                                         season=ep.season, episode=ep.episode):
                    owned += 1
            except Exception:  # fail-soft
                pass

        # (e) Not fully owned
        if owned == total:
            continue

        # (c) Owned <= total/2
        if owned > total / 2:
            continue

        # (d) Dedup: one live season wanted per follow+season
        existing = self._store.wanted.find(
            followed_id=followed_id, kind="season",
            season=season_num, episode=None,
        )
        if existing is not None:
            continue

        # --- Enqueue the season wanted ---
        fs = next((s for s in by_ref.values() if s.id == followed_id), None)
        if fs is None:
            continue

        actions.append(DetectAction(
            "season", fs.title, season_num, None,
            str(last_air), None,
            DetectOutcome.ENQUEUED,
        ))
        counts.enqueued += 1

        if dry_run:
            continue

        season_wid = self._store.wanted.add(
            WantedItem(
                media_ref=fs.media_ref,
                kind="season",
                status="pending",
                enqueued_at=now,
                followed_id=followed_id,
                season=season_num,
                episode=None,
            )
        )
        self._event_bus.emit(
            WantedEnqueued(media_ref=fs.media_ref, kind="season",
                           season=season_num, episode=None)
        )
        log.info(
            "acquire.detect.season_enqueued",
            series=fs.title, season=season_num,
            aired=total, owned=owned,
            last_air=str(last_air),
        )

        # --- R5: Absorb live episode wanteds for this season ---
        absorbed_ids: list[int] = []
        for ep in eps:
            ep_wanted = self._store.wanted.find(
                followed_id=followed_id, kind="episode",
                season=ep.season, episode=ep.episode,
            )
            if ep_wanted is not None and ep_wanted.id is not None:
                if ep_wanted.status in ("pending", "searching", "available"):
                    if ep_wanted.id is not None:
                        absorbed_ids.append(ep_wanted.id)

        if absorbed_ids:
            self._store.wanted.absorb_episodes(season_wid, tuple(absorbed_ids))
            self._event_bus.emit(
                SeasonAbsorbedEpisodes(
                    season_wanted_id=season_wid,
                    media_ref=fs.media_ref,
                    season=season_num,
                    absorbed_ids=tuple(absorbed_ids),
                )
            )
            log.info(
                "acquire.detect.season_absorbed",
                season_wanted_id=season_wid,
                absorbed_count=len(absorbed_ids),
            )
```

### Step 1: Wire the call into `run()`

In `DetectService.run()` (line 226-228), after the episode loop, add:

```python
# After `for ep in known:` loop...
# --- P3: season detection (R1) ---
self._detect_seasons(
    [ep for ep in known if ep.air_date <= today],
    by_ref, actions, counts,
    dry_run=dry_run, now=now, today=today,
)
```

### Step 2: Also import new events

In `detect.py:33`, add to imports:

```python
from personalscraper.acquire.events import (
    FilmAcquired, WantedEnqueued,
    SeasonAbsorbedEpisodes,  # NEW
)
```

### Step 2: Tests — boundary matrix

```python
# tests/acquire/test_detect.py

from datetime import date, timedelta
from unittest.mock import MagicMock

def test_season_detect_enqueues_when_conditions_met():
    """R1: last ep aired >= 7d, owned <= half → season wanted enqueued."""
    # Setup
    store = MagicMock()
    store.wanted.find.return_value = None  # no existing season wanted
    ownership = MagicMock()
    # 6 eps aired, 2 owned → exactly half → SHOULD enqueue
    ownership.owns.side_effect = lambda *a, **kw: (
        True if int(kw.get("episode", 0)) <= 2 else False
    )
    # ... build DetectService, call run
    # Asserts: store.wanted.add called with kind="season"
    # Asserts: WantedEnqueued emitted with kind="season"


def test_season_detect_skips_when_last_ep_recent():
    """R1(b): last ep aired < 7d ago → no season wanted."""
    # today - 3d for last ep → cutoff is today-7d → 3d < 7d → skip
    # Assert: no season wanted enqueued


def test_season_detect_skips_when_more_than_half_owned():
    """R1(c): owned > total/2 → skip."""
    # 6 eps, 4 owned → 4 > 3 → skip
    # Assert: no season wanted enqueued


def test_season_detect_skips_when_fully_owned():
    """R1(e): owned == total → skip."""
    # 6 eps, 6 owned → skip
    # Assert: no season wanted enqueued


def test_season_detect_skips_when_duplicate():
    """R1(d): live season wanted already exists → skip."""
    # store.wanted.find returns existing season row
    # Assert: no new wanted added


def test_season_detect_absorbs_episode_wanteds():
    """R5: enqueued season absorbs live episode wanteds."""
    # store.wanted.find for episodes returns live rows
    # After enqueue, store.wanted.absorb_episodes is called
    # And SeasonAbsorbedEpisodes event is emitted


def test_season_detect_boundary_exactly_7_days():
    """R1 boundary: last ep aired exactly 7 days ago → enqueue."""
    # today = date(2026, 8, 1), last_air = date(2026, 7, 25)
    # cutoff = today - 7d = July 25
    # last_air <= cutoff → True (equal → enqueue)
    # Assert: enqueued


def test_season_detect_boundary_exactly_half_owned():
    """R1 boundary: exactly half owned → enqueue."""
    # 6 eps, 3 owned → 3 <= 3 → True
    # Assert: enqueued
```

Run: `pytest tests/acquire/test_detect.py -v -k "test_season_detect"`

## Commit

```bash
git add personalscraper/acquire/detect.py tests/acquire/test_detect.py
git commit -m "feat(season-grab): auto season detection R1 — group aired episodes, enqueue season wanted when last aired >= 1w and owned <= half, absorb live episode wanteds R5"
```
