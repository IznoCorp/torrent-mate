# Phase 6 — ACCEPTANCE.md + Full Gate

## Gate

- [ ] `make check` zero errors (lint + test + module-size + typed-api)
- [ ] `python -c "import personalscraper"` smoke test
- [ ] `rg "from personalscraper.acquire.events import SeasonAbsorbedEpisodes" --type py tests/` confirms new events importable in tests
- [ ] All ACC-NN criteria pass (executed, output documented in ACCEPTANCE.md)
- [ ] Golden rank test pinned with deterministic output
- [ ] Residual import grep: no stale references to old module paths

## Sub-phase 6.1 — ACCEPTANCE.md

**Files**: `docs/features/season-grab/ACCEPTANCE.md` (NEW)

### Content

````markdown
# Season Grab — Acceptance Criteria

> **Feature**: season-grab (#378)
> **Version**: 0.75.0
> **Date**: 2026-08-01
>
> Every criterion is an executable shell command with documented expected output.
> Prose-only criteria are invalid per SH-16 / tech-debt 0.16.0.

## ACC-01 — R1 Boundary: aired-exactly-7-days

**What**: Season detection enqueues when last episode aired exactly 7 days ago.

```bash
pytest tests/acquire/test_detect.py -v -k "test_season_detect_boundary_exactly_7_days"
```
````

**Expected**: 1 passed. The test sets today=Aug 1, last_air=Jul 25 (7-day boundary)
and asserts the season wanted is enqueued.

## ACC-02 — R1 Boundary: exactly-half-owned

**What**: Season detection enqueues when exactly half the season is owned.

```bash
pytest tests/acquire/test_detect.py -v -k "test_season_detect_boundary_exactly_half_owned"
```

**Expected**: 1 passed. 6 eps, 3 owned → owned <= total/2 (3 <= 3) → enqueued.

## ACC-03 — R2 Conversion: 0-exact + pack present

**What**: Episode search with 0 episode-exact results but a season pack
present triggers season conversion.

```bash
pytest tests/acquire/test_search_pass.py -v -k "test_conversion_enqueues_season_when_pack_present"
```

**Expected**: 1 passed. Season wanted enqueued, triggering episode absorbed.

## ACC-04 — R2 Conversion: siblings absorbed

**What**: The conversion absorbs the triggering episode AND its live siblings.

```bash
pytest tests/acquire/test_search_pass.py -v -k "test_conversion_absorbs_siblings"
```

**Expected**: 1 passed. store.wanted.absorb_episodes called with all live episode IDs.

## ACC-05 — filter_to_season: accepts full-range

**What**: `S01E01-E08` full-range marker is accepted.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_accepts_full_range"
```

**Expected**: 1 passed. The full-range result survives.

## ACC-06 — filter_to_season: accepts bare-Sxx

**What**: `Show S01` without episode markers is accepted.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_accepts_bare_season"
```

**Expected**: 1 passed. The bare-season result survives.

## ACC-07 — filter_to_season: accepts Intégrale

**What**: `Intégrale` keyword in title is accepted.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_accepts_integrale_keyword"
```

**Expected**: 1 passed. The Intégrale release survives.

## ACC-08 — filter_to_season: rejects partial

**What**: Partial range (non-full, no keyword) is rejected.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_rejects_partial_range"
```

**Expected**: 1 passed. The partial-range result is dropped.

## ACC-09 — filter_to_season: rejects multi-season

**What**: Multi-season packs are rejected.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_rejects_multi_season"
```

**Expected**: 1 passed. `S01-S03` is dropped.

## ACC-10 — filter_to_season: rejects wrong season

**What**: Pack for the wrong season is rejected.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_rejects_wrong_season"
```

**Expected**: 1 passed. S02 pack when targeting S01 is dropped.

## ACC-11 — Rank golden: media_kind="season"

**What**: `rank()` with `media_kind="season"` applies per-type season size thresholds.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_rank_season_media_kind_uses_season_tiers"
```

**Expected**: 1 passed. Small season pack with more seeders beats big pack that
doesn't meet the season tier threshold. The golden assert verifies exact scores.

## ACC-12 — API: 403 on staging

**What**: `POST /api/acquisition/follows/{id}/seasons/{season}/grab` returns 403
on staging role.

```bash
pytest tests/web/routes/test_acquisition.py -v -k "test_season_grab_403_on_staging"
```

**Expected**: 1 passed. HTTP 403 Forbidden.

## ACC-13 — API: absorbs siblings

**What**: The grab endpoint absorbs episode wanteds when creating a season wanted.

```bash
pytest tests/web/routes/test_acquisition.py -v -k "test_season_grab_creates_season_wanted"
```

**Expected**: 1 passed. Response includes `absorbed_count > 0`.

## ACC-14 — API: idempotent on duplicate

**What**: Second grab on same season returns existing row (no 500).

```bash
pytest tests/web/routes/test_acquisition.py -v -k "test_season_grab_returns_existing_on_duplicate"
```

**Expected**: 1 passed. Same `season_wanted_id` returned.

## ACC-15 — R6 Fallback: re-enqueues exactly missing

**What**: Cutoff fallback re-enqueues every aired episode for the season.

```bash
pytest tests/acquire/test_pass_gates.py -v -k "test_season_cutoff_falls_back_to_episodes"
```

**Expected**: 1 passed. store.wanted.add called once per aired episode.

## ACC-16 — Live dry-run (post-merge, manual)

**What**: `personalscraper follow detect --dry-run` on the real store reports
season candidates without writes.

```bash
personalscraper follow detect --dry-run 2>&1 | head -20
```

**Expected**: Table output includes rows with kind "season" in the table
— no writes to acquire.db (verify: unchanged mtime).

````

### Step 1: Create ACCEPTANCE.md

Write the content above to `docs/features/season-grab/ACCEPTANCE.md`.

## Sub-phase 6.2 — Full Gate

### Step 1: Run `make check`

```bash
make check
````

**Expected**: All targets pass:

- ruff: 0 errors
- mypy: 0 errors
- pytest: NNNN passed, 0 failed, 0 error
- module-size: no module over 1000 lines
- typed-api: no regressions

### Step 2: Run `personalscraper follow detect --dry-run`

```bash
personalscraper follow detect --dry-run 2>&1 | head -30
```

**Expected**: Table output includes "season" kind rows when a followed show
has a season meeting the R1 criteria. No acquire.db writes (check `stat acquire.db` mtime unchanged).

### Step 3: Import smoke test

```bash
python -c "
from personalscraper.acquire.events import SeasonAbsorbedEpisodes, SeasonFellBackToEpisodes
from personalscraper.acquire.domain import WantedItem
from personalscraper.core.identity import MediaRef
import time
now = int(time.time())
w = WantedItem(media_ref=MediaRef(tvdb_id=12345), kind='season', status='pending', enqueued_at=now, season=3, episode=None)
print(f'OK: season wanted kind={w.kind}, status={w.status}')
"
```

**Expected**: `OK: season wanted kind=season, status=pending`

### Step 4: Residual import grep

```bash
rg "old\.module\.path" --type py personalscraper/ tests/  # replace with any deleted modules
```

**Expected**: Zero matches. If any module was deleted in this feature, verify no stale imports remain.

### Step 5: Event coverage check

```bash
rg "SeasonAbsorbedEpisodes\|SeasonFellBackToEpisodes" --type py personalscraper/acquire/events.py
```

**Expected**: Both events present in `__all__`.

```bash
rg "SeasonAbsorbedEpisodes" --type py personalscraper/acquire/ -l
```

**Expected**: Events imported at emission sites (detect.py, _search_pass.py).

## Commit

```bash
git add docs/features/season-grab/ACCEPTANCE.md
git commit -m "docs(season-grab): ACCEPTANCE.md with 16 executable criteria, full gate"
```
