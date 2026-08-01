# Season Grab — Acceptance Criteria

> **Feature**: season-grab (#378)
> **Version**: 0.75.0
> **Date**: 2026-08-01
> **DESIGN**: docs/features/season-grab/DESIGN.md
> **Plan**: docs/features/season-grab/plan/phase-06-acceptance.md
>
> Every criterion is an executable shell command with documented expected output.
> Prose-only criteria are invalid per SH-16 / tech-debt 0.16.0.
> Status is updated at each phase gate and at the final PR gate.

---

## ACC-01 — R1 Boundary: aired-exactly-7-days

**What**: Season detection enqueues when last episode aired exactly 7 days ago.
**Scope**: DESIGN §2 R1 (auto season wanted — last aired ≥ 1 week).

```bash
pytest tests/acquire/test_detect_service.py -v -k "test_season_detect_boundary_exactly_7_days"
# Expected: 1 passed. Last ep aired exactly 7 days ago → season action emitted.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-02 — R1 Boundary: exactly-half-owned

**What**: Season detection enqueues when exactly half the season is owned.
**Scope**: DESIGN §2 R1 (owned ≤ half).

```bash
pytest tests/acquire/test_detect_service.py -v -k "test_season_detect_boundary_exactly_half_owned"
# Expected: 1 passed. 6 episodes, 3 owned → owned ≤ total/2 → season enqueued.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-03 — R2 Conversion: 0-exact + pack present

**What**: Episode search with 0 episode-exact results but a season pack
present triggers season conversion.
**Scope**: DESIGN §3.3 (episode→season conversion).

```bash
pytest tests/acquire/test_search_pass.py -v -k "test_conversion_enqueues_season_when_pack_present"
# Expected: 1 passed. Season wanted enqueued, WantedEnqueued(season) emitted,
# SeasonAbsorbedEpisodes emitted.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-04 — R5 Absorption: store transitions status

**What**: absorb_episodes() sets status='absorbed' + absorbed_by on matching episode rows.
**Scope**: DESIGN §2 R5 (absorption — live episode wanteds get absorbed status).

```bash
pytest tests/acquire/test_store.py -v -k "test_absorb_episodes_transitions_status"
# Expected: 1 passed. 3 episode rows absorbed, each with status='absorbed'
# and absorbed_by pointing to the season wanted id.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-05 — filter_to_season: accepts full-range

**What**: `S01E01-E08` full-range marker is accepted.
**Scope**: DESIGN §3.4 (filter_to_season — whole-season pack detection).

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_accepts_full_range"
# Expected: 1 passed. The full-range result survives.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-06 — filter_to_season: accepts bare-Sxx

**What**: `Show S01` without episode markers is accepted.
**Scope**: DESIGN §3.4.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_accepts_bare_season"
# Expected: 1 passed. The bare-season result survives.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-07 — filter_to_season: accepts Intégrale

**What**: `Intégrale` keyword in title is accepted.
**Scope**: DESIGN §3.4.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_accepts_integrale_keyword"
# Expected: 1 passed. The Intégrale release survives.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-08 — filter_to_season: rejects partial

**What**: Partial range (non-full, no keyword) is rejected.
**Scope**: DESIGN §3.4 (reject partial ranges).

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_rejects_partial_range"
# Expected: 1 passed. S01E03-E06 is dropped.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-09 — filter_to_season: rejects multi-season

**What**: Multi-season packs are rejected.
**Scope**: DESIGN §3.4 (single-season only, reject multi-season).

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_rejects_multi_season"
# Expected: 1 passed. S01-S03 is dropped.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-10 — filter_to_season: rejects wrong season

**What**: Pack for the wrong season is rejected.
**Scope**: DESIGN §3.4.

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_filter_to_season_rejects_wrong_season"
# Expected: 1 passed. S02 pack when targeting S01 is dropped.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-11 — Rank golden: media_kind="season"

**What**: `rank()` with `media_kind="season"` applies per-type season size thresholds.
**Scope**: DESIGN §3.4 (ranking — #376 provision activates for "season").

```bash
pytest tests/acquire/test_orchestrator.py -v -k "test_rank_season_media_kind_uses_season_tiers"
# Expected: 1 passed. 80 GB pack scores 5 (≥50GB season tier), 15 GB pack scores 0.
# Golden assert: scored_season[0][1] == 5, scored_season[1][1] == 0.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-12 — API: 403 on staging

**What**: `POST /api/acquisition/follows/{id}/seasons/{season}/grab` returns 403
on staging role (require_not_staging dependency).
**Scope**: DESIGN §3.6 (web UI + API — staging-guarded).

```bash
pytest tests/unit/web/routes/test_season_grab.py -v -k "TestSeasonGrab and test_403_on_staging"
# Expected: 1 passed. HTTP 403 Forbidden, body contains "read-only".
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-13 — API: creates season wanted + absorbs episodes

**What**: The grab endpoint creates a season wanted and absorbs live episode wanteds.
**Scope**: DESIGN §2 R4/R5 (manual button + absorption).

```bash
pytest tests/unit/web/routes/test_season_grab.py -v -k "TestSeasonGrab and test_creates_season_wanted_and_absorbs_episodes"
# Expected: 1 passed. HTTP 201, response includes season=1, season_wanted_id>0, absorbed_count=3.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-14 — API: idempotent on duplicate

**What**: Second grab on same season returns existing row (no 500).
**Scope**: DESIGN §3.6 (idempotent — one live season wanted per follow+season).

```bash
pytest tests/unit/web/routes/test_season_grab.py -v -k "TestSeasonGrab and test_duplicate_returns_existing"
# Expected: 1 passed. Same season_wanted_id returned, absorbed_count unchanged.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-15 — R6 Fallback: season cutoff re-enqueues episodes

**What**: Cutoff fallback re-enqueues every aired episode for the season,
transitions season row to fallback_episodes, emits SeasonFellBackToEpisodes.
**Scope**: DESIGN §2 R6 / §3.5 (fallback — degrade to per-episode retry).

```bash
pytest tests/acquire/test_pass_gates.py -v -k "test_season_cutoff_falls_back_to_episodes"
# Expected: 1 passed. 8 re-enqueued episodes, season status=fallback_episodes,
# SeasonFellBackToEpisodes emitted with season_wanted_id, season=3, reenqueued_count=8.
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## ACC-16 — Live dry-run: follow detect reports season candidates

**What**: `personalscraper follow detect --dry-run` on the real store reports
season candidates without writes.
**Scope**: DESIGN §3.2 (detection — auto season wanted).

```bash
personalscraper follow detect --dry-run 2>&1 | head -20
# Expected: Table output includes rows with kind "season" when a followed show
# has a season meeting the R1 criteria (last aired ≥ 1 week, owned ≤ half).
# No acquire.db writes — verify with: stat acquire.db (mtime unchanged).
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## Event Catalog Check

**What**: New events are declared in `__all__` and importable.

```bash
python -c "
from personalscraper.acquire.events import SeasonAbsorbedEpisodes, SeasonFellBackToEpisodes
print('OK: both events importable')
"
# Expected: OK: both events importable (zero exit code).
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## WantedKind + WantedStatus Check

**What**: Domain model includes "season" kind and "absorbed"/"fallback_episodes" statuses.

```bash
pytest tests/acquire/test_domain.py -v -k "test_wanted_kind_includes_season or test_wanted_status_includes_absorbed_and_fallback"
# Expected: 2 passed. WantedKind set includes "season"; WantedStatus includes "absorbed" + "fallback_episodes".
```

**Status**: PASS (exercised 2026-08-01, post review-fix wave)

---

## Re-exercise Log

| Date       | Phase | ACC-01 | ACC-02 | ACC-03 | ACC-04 | ACC-05 | ACC-06 | ACC-07 | ACC-08 | ACC-09 | ACC-10 | ACC-11 | ACC-12 | ACC-13 | ACC-14 | ACC-15 | ACC-16 |
| ---------- | ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
| 2026-08-01 | 6+fix | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     |

Run notes (2026-08-01, after the 14-commit adversarial-review fix wave `3156b40f..cd34a2c2`):

- ACC-01..15 + Event Catalog + WantedKind/Status checks: every pytest selector ran individually — `1 passed` each (ACC-09 `2 passed`: selector matches an added regression sibling; ACC-DOM `2 passed` as documented).
- ACC-16 live: `personalscraper follow detect --dry-run` exit 0; `wanted` table row count/max-id 53→53 and db mtime unchanged (sqlite snapshot before/after) — NO writes. Zero season candidates reported: the live library holds no season currently meeting R1 (post-fix gate: all episodes aired + last ≥ 7d + owned ≤ half). This is the honest outcome — the pre-fix code minted a season from a single aired episode of a still-airing season (review finding 2), which no longer happens.
- Full gates same day: `make check` → 9919 passed backend, 1040 frontend, lint/mypy clean.
