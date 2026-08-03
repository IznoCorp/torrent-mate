# Phase 3 — Events catalogue + reconcile signature change + emission + callers

**Gate**: Phase 2 complete — caps wired and live. `BandwidthConfig` flows through `_factory.py` to orchestrator and service. No code outside acquire is yet aware of download events.

## Scope

Three new `Event` subclasses in `acquire/events.py`, `reconcile_wanted` signature change (`client_items: dict[str, TorrentItem] | None` replaces `client_hashes: set[str] | None`, REQUIRED `event_bus` parameter added), emission logic in the reconcile sweep using `DownloadMarksStore`, and ALL callers updated (`commands/grab.py`, `commands/search.py`, test fixtures).

---

## Sub-phase 3.1: Download event classes

**Commit**: `feat(seed-caps): add DownloadStarted, DownloadProgressed, DownloadCompleted events`

### Files
- **Modify**: `personalscraper/acquire/events.py` — add 3 event classes + `__all__` entries
- **Create**: `tests/acquire/test_download_events.py`

### Implementation

In `events.py`, add three frozen kw_only dataclasses after the last existing event (before `__all__`), following the house style:

**`DownloadStarted`** — fields: `info_hash: str`, `title: str`, `provider: str`, `kind: str`. Emitted when a hash-carrying OPEN row first appears in the client with progress < 1.0.

**`DownloadProgressed`** — fields: `info_hash: str`, `title: str`, `progress: float`, `threshold_pct: int`. Emitted on 25/50/75% threshold crossing (highest crossed per pass, D8). Progress regressions (qBit recheck) do NOT re-emit lower thresholds.

**`DownloadCompleted`** — fields: `info_hash: str`, `title: str`, `provider: str`, `kind: str`. Emitted on first observation with progress >= 1.0. If already-complete on first sighting, only this event fires (no synthetic Started/Progressed backfill).

Add all three to `__all__`.

### Tests

In `tests/acquire/test_download_events.py`, verify each class:
- Is a subclass of `Event`
- Constructs with required fields
- Has auto-derived `source` and `timestamp`
- Values round-trip correctly

### Gate
```bash
pytest tests/acquire/test_download_events.py -v   # all pass
```

---

## Sub-phase 3.2: Reconcile signature change + emission logic

**Commit**: `feat(seed-caps): add download event emission to reconcile_wanted`

### Files
- **Modify**: `personalscraper/acquire/reconcile.py` — signature change + emission block
- **Create**: `tests/acquire/test_reconcile_download_events.py`

### Implementation

**Signature change** (D9): Replace `client_hashes: set[str] | None` with `client_items: dict[str, TorrentItem] | None`, add REQUIRED `*, event_bus: EventBus` parameter.

At the top of the function body, derive the old set: `client_hashes = set(client_items.keys()) if client_items is not None else None`. All existing presence checks are unchanged.

**Emission block** — after the existing row-processing loop, add a new pass:

1. Fetch open hash-carrying rows from the store.
2. For each row present in `client_items`:
   - Read `DownloadMarksStore.get(info_hash)` to get current mark state.
   - Compare `TorrentItem.progress` against marks.
   - **Emit-after-persist**: persist marks FIRST, then emit events.
   - If `progress >= 1.0` and not yet completed: persist `completed=True, started=True`, emit `DownloadCompleted`.
   - Else: if not yet started, persist `started=True`, emit `DownloadStarted`. Then compute highest crossed threshold (25/50/75) above `last_threshold`, persist the threshold, emit ONE `DownloadProgressed` (D8: only highest crossed per pass).
3. After the loop, call `marks.prune_stale(active_hashes)` to clean up closed-row marks (D7).

### Tests

In `tests/acquire/test_reconcile_download_events.py`, behavior-driven tests:
- Fresh hash mid-download → `DownloadStarted` only (first pass, no threshold crossed yet)
- Already-complete first sighting → `DownloadCompleted` only (no synthetic backfill)
- Threshold crossing 25% (last=0, progress=0.30 → `DownloadProgressed(threshold_pct=25)`)
- Threshold crossing 50% skips 25% (last=25, progress=0.55 → `DownloadProgressed(threshold_pct=50)`)
- Progress regression (qBit recheck: 0.80→0.20, last=75 → no emit)
- Second pass same state → zero emits (exactly-once, D7)
- Row closes → marks pruned (D7)
- Emit-after-persist ordering verified via mock side_effect ordering

### Gate
```bash
pytest tests/acquire/test_reconcile_download_events.py tests/acquire/test_download_events.py -v   # all pass
```

---

## Sub-phase 3.3: Caller updates (grab.py + search.py + test fixtures)

**Commit**: `feat(seed-caps): update reconcile_wanted callers for new signature`

### Files
- **Modify**: `personalscraper/commands/grab.py:155-184` — pass `client_items` dict + `event_bus`
- **Modify**: `personalscraper/commands/search.py` — pass `None` + `event_bus`
- **Modify**: All test files calling `reconcile_wanted` — update to new signature

### Implementation

**grab.py**: The existing code at line 164 already fetches full `TorrentItem` objects via `torrent_client.get_by_hashes(in_flight)` then extracts only `.hash.lower()`. Change to build `client_items = {t.hash.lower(): t for t in items}` instead of `client_hashes = {t.hash.lower() for t in ...}`. Pass `client_items` (was `client_hashes`) and add `event_bus=event_bus`.

**search.py**: Pass `None` for `client_items` (ownership-only half, zero events — unchanged semantics) and add `event_bus=event_bus`.

**Test fixtures**: Grep `rg "reconcile_wanted\(" --type py tests/` and update every call to the new signature (`client_items=...` replacing `client_hashes=...`, add `event_bus=...`).

### Gate
```bash
# Verify zero old-signature callers remain
rg "reconcile_wanted\(" --type py personalscraper/ tests/ | grep -v "client_items" && echo "FAIL: stale caller" || echo "OK"
make lint
pytest tests/acquire/ tests/commands/ -v -k "reconcile or download"
python -c "import personalscraper"
```

---

## Phase 3 Gate (before proceeding to Phase 4)

```bash
rg "reconcile_wanted\(" --type py personalscraper/ tests/ | grep -v "client_items" && echo "STALE CALLER" || echo "OK"
make lint
pytest tests/acquire/ -v
python -c "import personalscraper"
```

**Produces for Phase 4**: Download events fire from `reconcile_wanted` with exactly-once semantics. `event_bus` plumbed through all reconcile callers. Three new event types in the catalogue.
