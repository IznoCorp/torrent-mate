# Phase 16 — Tracker Family Base + Ranking Engine

**Type**: infra
**Goal**: Ship `api/tracker/_base.py`, `_ranking.py`, `_registry.py`. No tracker provider yet.

## Gate (prereq)

Phase 15 complete. `ByteSize` is stable from Phase 1. Ranking Pydantic models already exist in `api/tracker/_ranking.py` from Phase 2 because config validation needs them early.

## Sub-phases

### 16.1 — `api/tracker/__init__.py` + `_base.py`

`_base.py`:

- `TrackerResult` dataclass (per DESIGN §6.1) — `size: ByteSize` (typed, not int).
- `TrackerClient` Protocol — `search(query, media_type, year)`, `get_categories()`.

**Commit**: `feat(api-unify): add tracker family base — Protocol + TrackerResult`

### 16.2 — `api/tracker/_ranking.py`

Extend the existing `api/tracker/_ranking.py` created in Phase 2 with runtime ranking behavior:

- `rank(results, ranking) -> list[tuple[TrackerResult, int]]`.

Keep `ThresholdEntry`, `RankingCriterion`, `RankingBonuses`, and `TorrentRanking` / `RankingConfig` as the same objects consumed by `personalscraper/conf/models/api_config.py`. Do not duplicate ranking Pydantic models in config modules.

**Commit**: `feat(api-unify): add tracker ranking engine + ThresholdEntry`

### 16.3 — `api/tracker/_registry.py`

```python
class TrackerRegistry:
    def __init__(self, trackers: dict[str, TrackerClient],
                 priority: list[str], ranking: TorrentRanking) -> None:
        self._trackers = trackers
        self._priority = priority
        self._ranking = ranking

    def search_all(self, query, media_type="movie", year=None) -> list[tuple[TrackerResult, int]]:
        results: list[TrackerResult] = []
        for name in self._priority:
            client = self._trackers.get(name)
            if client is None:
                continue
            try:
                results.extend(client.search(query, media_type, year))
            except Exception:
                log.warning("tracker_search_failed", tracker=name, exc_info=True)
        return rank(results, self._ranking)
```

**Commit**: `feat(api-unify): add TrackerRegistry`

### 16.4 — Ranking engine tests

`tests/unit/test_ranking.py` — comprehensive coverage of `rank()`:

- Categorical scoring: `resolution: {"2160p": 20}` matches and adds `weight × 20` points.
- Threshold scoring: `seeders` thresholds at 0/5/20/100 → highest applicable applied.
- `ByteSize` thresholds: `size: 5_000_000_000` matches `at: "1GB"` (5GB > 1GB), threshold "5GB" rung → score 10.
- `min_seeders` filter drops sub-threshold results.
- `freeleech` and `silverleech` bonuses additive.
- Sort order: highest score first, stable for ties.

`tests/unit/test_threshold_entry.py`:

- `ThresholdEntry(at="1GB", score=10).at == 1_000_000_000`.
- `ThresholdEntry(at="500MiB", score=5).at == 524_288_000`.
- `ThresholdEntry(at=100, score=2).at == 100`.
- Invalid literal raises `ValueError`.

**Commit**: `test(api-unify): add ranking engine tests`

### 16.5 — Phase 16 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.tracker._base import TrackerClient, TrackerResult"
python -c "from personalscraper.api.tracker._ranking import rank, ThresholdEntry, RankingCriterion, TorrentRanking"
python -c "from personalscraper.api.tracker._registry import TrackerRegistry"
```

**Commit**: `chore(api-unify): phase 16 gate — tracker base + ranking done`
