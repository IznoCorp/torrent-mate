# Phase 11 — New Trackers + Ranking

## Gate

**Prerequisites**: Phase 10 complete. `docs/reference/lacale-api.md` and `docs/reference/c411-api.md` exist. `api/transport/` exists.

## Goal

Implement `api/tracker/` package: LaCale + C411 clients, `TrackerRegistry`, ranking engine, typed `TrackerResult`.

## Sub-phases

### 11.1 — Create `api/tracker/` package + `_base.py`

**Files**:

- `personalscraper/api/tracker/__init__.py`
- `personalscraper/api/tracker/_base.py`

`_base.py` contains:

- `TrackerClient` Protocol (from DESIGN §6.1)
- `TrackerResult` dataclass with all fields (provider, tracker_id, title, size_bytes, seeders, leechers, category, download_url, info_hash, source_url, is_freeleech, is_silverleech, upload_date, format, codec, source, resolution, audio)
- `RankingCriterion` dataclass (field, weight, values, thresholds, prefer)
- `TorrentRanking` dataclass (criteria list, freeleech_bonus, silverleech_bonus, min_seeders)
- `rank()` function — iterates criteria, computes weighted score, adds bonuses, returns sorted list

```python
def rank(results: list[TrackerResult],
         ranking: TorrentRanking) -> list[tuple[TrackerResult, int]]:
    scored = []
    for r in results:
        if r.seeders < ranking.min_seeders:
            continue
        score = 0
        for c in ranking.criteria:
            val = getattr(r, c.field, None)
            if val is None:
                continue
            points = 0
            if c.values is not None:
                points = c.values.get(str(val), 0)
            elif c.thresholds is not None and isinstance(val, (int, float)):
                applicable = max((t for t in c.thresholds if val >= t), default=0)
                points = c.thresholds.get(applicable, 0)
            score += int(points * c.weight)
        if r.is_freeleech:
            score += ranking.freeleech_bonus
        if r.is_silverleech:
            score += ranking.silverleech_bonus
        scored.append((r, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
```

**Commit**: `feat(api-unify): add tracker base types and ranking engine`

### 11.2 — Create `api/tracker/lacale.py`

Implement `LaCaleClient` following `docs/reference/lacale-api.md`:

- Auth from `.env` (`LACALE_API_KEY`)
- `REQUIRED_CREDS = ["LACALE_API_KEY"]`
- `search(query, media_type, year)` → returns `list[TrackerResult]`
- `get_categories()` → returns `dict[str, str]`
- Parse torrent metadata (format, codec, resolution, source, audio) from title strings

**Commit**: `feat(api-unify): add LaCale tracker client`

### 11.3 — Create `api/tracker/c411.py`

Implement `C411Client` following `docs/reference/c411-api.md`:

- Auth from `.env` (`C411_API_KEY`)
- `REQUIRED_CREDS = ["C411_API_KEY"]`
- Same interface as LaCale

**Commit**: `feat(api-unify): add C411 tracker client`

### 11.4 — Create `api/tracker/_registry.py`

Implement `TrackerRegistry`:

```python
class TrackerRegistry:
    def __init__(self, trackers: dict[str, TrackerClient],
                 priority: list[str], ranking: TorrentRanking) -> None:
        self._trackers = trackers
        self._priority = priority
        self._ranking = ranking

    def search_all(self, query: str, media_type: str = "movie",
                   year: int | None = None) -> list[tuple[TrackerResult, int]]:
        results: list[TrackerResult] = []
        for name in self._priority:
            if name not in self._trackers:
                continue
            try:
                results.extend(self._trackers[name].search(query, media_type, year))
            except Exception:
                log.warning("tracker_search_failed", tracker=name, exc_info=True)
        return rank(results, self._ranking)
```

**Commit**: `feat(api-unify): add TrackerRegistry`

### 11.5 — Tests

Write unit tests for:

- `rank()` function — various ranking scenarios
- `TrackerRegistry.search_all()` — multi-tracker merge
- LaCaleClient and C411Client with mock HTTP responses

**Commit**: `test(api-unify): add tracker tests`

### 11.6 — Phase 11 gate

```bash
make check && python3 scripts/check-module-size.py
python -c "from personalscraper.api.tracker.lacale import LaCaleClient; from personalscraper.api.tracker._registry import TrackerRegistry"
```

**Commit**: `chore(api-unify): phase 11 gate — trackers + ranking done`
