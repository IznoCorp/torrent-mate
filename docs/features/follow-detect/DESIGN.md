# DESIGN — Follow D2: calendar-first detection → wanted enqueue + cadence backoff

| Field                        | Value                                                                                                                                                                                                                                                                                  |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Codename (proposed)**      | `follow-detect`                                                                                                                                                                                                                                                                        |
| **Roadmap item**             | Follow D2 (P2, vague 4) — "détection calendrier-d'abord (RP9) + file `wanted` + cadence backoff + ownership (RP6)"                                                                                                                                                                     |
| **Type**                     | minor                                                                                                                                                                                                                                                                                  |
| **Version bump**             | 0.31.0 → 0.32.0                                                                                                                                                                                                                                                                        |
| **Date**                     | 2026-06-15                                                                                                                                                                                                                                                                             |
| **Depends on (all shipped)** | `acquire.airing.poll_aired` (RP9), `store.follow.list_active()` (Follow D1), `core.ownership.OwnershipChecker.owns()` via `ctx.acquire.ownership` (RP6), `store.wanted.*` + `WantedItem` (RP3/RP3a), `WantedEnqueued`/`WantedAbandoned` events + `AcquisitionTelegramSubscriber` (RP4) |
| **Unblocks**                 | Follow D3 (the grab is already live via the shipped grab core `AcquisitionService.run()`); Watcher (vague 4)                                                                                                                                                                           |

> Follow D2 is the **first production consumer** of the calendar half (RP9) and the ownership predicate
> (RP6), both shipped wired-but-not-consumed. D2 turns the **aired set** into `wanted` entries (skipping owned
> ones, deduping against the existing queue), and makes the **search loop cadence-aware** so a `wanted` entry
> is re-searched on a backoff schedule (Hot/Warm/Cold) until grabbed or abandoned at cutoff. The tracker grab
> itself is D3 — already shipped (`GrabOrchestrator`/`AcquisitionService`); D2 only **produces** the queue and
> **gates** how often the existing loop acts on each entry.

---

## 1. Responsibility boundary (the load-bearing rule)

D2 owns exactly five things and nothing else:

1. **Detection** — enumerate aired episodes for the active followed set (via RP9's `poll_aired`).
2. **Enqueue** — convert each non-owned, non-duplicate `AiredEpisode` into a `WantedItem(kind='episode', status='pending')` and persist it (`store.wanted.add`).
3. **Cadence policy** — define the Hot/Warm/Cold/cutoff backoff model + its config (global default + per-series `cadence_json` override).
4. **Cadence-aware re-search gating** — make the existing `AcquisitionService.run()` loop consult the cadence predicate instead of the flat `_STALE_THRESHOLD_S` constant; abandon at cutoff.
5. **Events** — emit `WantedEnqueued` (on enqueue) and `WantedAbandoned(reason='cutoff_reached')` (at cutoff).

D2 does **NOT**:

- Change the air-date poll mechanics (RP9 / `acquire/airing.py`) — it is consumed read-only.
- Perform the tracker grab/rank/dedup-cross-tracker (Follow D3 — the grab core `GrabOrchestrator` + `AcquisitionService` are already shipped and **consume** the queue; D2 never writes the grab path).
- Follow **movies** — `FollowedSeries` is a TV series; D2 enqueues `kind='episode'` only. Movie-follow is a separate, out-of-scope trigger.
- Add a torrent client / fetch boundary (RP1a/RP7 — grab-side D3 concerns).

This boundary is encoded in tests (§11): the detect path makes **zero** grab calls, and `poll_aired` keeps its existing negative-boundary tests (it still never reads `cadence_json` nor calls `store.wanted.*` nor `ownership.owns`).

---

## 2. Two-stage architecture

Follow D2 is two cooperating stages that share the `wanted` table as the seam:

### Stage A — DETECT (new `follow detect` CLI command)

```
store.follow.list_active()                  # FollowedSeries[] (Follow D1, shipped)
  → poll_aired(series, registry, today)     # list[AiredEpisode] (RP9, shipped)
    → for each AiredEpisode:
        owned   = ctx.acquire.ownership.owns(ep.media_ref, kind='episode', season=ep.season, episode=ep.episode)
        if owned: record "skipped-owned"; continue
        dup     = store.wanted.find(followed_id, 'episode', ep.season, ep.episode) is not None
        if dup:   record "skipped-dup"; continue
        store.wanted.add(WantedItem(media_ref=ep.media_ref, kind='episode', status='pending',
                                    enqueued_at=now, followed_id=fs.id, season=ep.season,
                                    episode=ep.episode, criteria_json=<series source criteria or None>))
        bus.emit(WantedEnqueued(media_ref=ep.media_ref, kind='episode', season=ep.season, episode=ep.episode))
        record "enqueued"
```

`--dry-run` runs everything **except** `add()` + `emit()` (preview only). The command renders a Rich table of
`[Series, Season, Episode, AirDate, Title, Action]`.

### Stage B — CADENCE-AWARE SEARCH (existing `AcquisitionService.run()`, made cadence-aware)

The loop (`service.py:151-231`) currently selects items via `list_pending()` + `list_stale_searching(older_than=_STALE_THRESHOLD_S)` (flat 1h, `service.py:74`). D2 replaces the "is this item due to (re)search now?" decision with the **cadence predicate** and adds a **cutoff → abandon** transition. The actual grab (`orchestrator.grab`) is unchanged.

---

## 3. Cadence model — new `acquire/cadence.py` (pure, no business logic)

A narrow module: a value object + two pure functions. Time arithmetic and tier selection only. **Layering invariant**: imports `core`/stdlib only — never `scraper`, `indexer`, `store`, or the event bus.

```python
@dataclass(frozen=True)
class CadenceTier:
    max_age_s: int            # upper age bound for this tier (exclusive of the next)
    interval_s: int           # min gap between two searches while in this tier

@dataclass(frozen=True)
class Cadence:
    tiers: tuple[CadenceTier, ...]   # ordered by max_age_s ascending (Hot, Warm, Cold)
    cutoff_s: int                     # age at/after which the item is abandoned

def is_due_by_cadence(cadence: Cadence, *, now: int, enqueued_at: int, last_search_at: int | None) -> bool:
    """True iff the item should be (re)searched at `now`. False when not-yet-due OR past cutoff."""

def is_past_cutoff(cadence: Cadence, *, now: int, enqueued_at: int) -> bool:
    """True iff (now - enqueued_at) >= cutoff_s — the item must be abandoned, not searched."""
```

Semantics (ROADMAP frozen decision, 2026-06-01):

- **age** = `now − enqueued_at` (seconds). `enqueued_at` is the detection time; it stands in for "time since the episode entered the wanted queue".
- Tier by age: 🔥 **Hot** `0 ≤ age < 72h` → `interval = 2h` · 🌤 **Warm** `72h ≤ age < 14d` → `interval = 1d` · ❄️ **Cold** `14d ≤ age < 30d` → `interval = 7d`.
- ⛔ **cutoff** `age ≥ 30d` → `is_past_cutoff = True`, `is_due_by_cadence = False`.
- **due** = `not is_past_cutoff AND (last_search_at is None OR (now − last_search_at) ≥ interval(tier(age)))`.
  A never-searched item (`last_search_at is None`) is **due immediately** within the cadence window (the
  first search is prompt — trackers lag airing, and the existing `run()` loop already searches `pending`
  items without an interval gate). The interval gate applies only to **re**-searches.

`attempts` is **not** part of the cadence predicate (the existing attempts-cap abandon at `service.py:357`,
`MAX_ATTEMPTS=5`, is orthogonal and retained). Cadence governs _when_ to search; attempts-cap governs _how
many times_ a search may fail before terminal abandon.

---

## 4. Cadence config + per-series override

### Global default — `conf/models/acquire.py`

`AcquireConfig` (`conf/models/acquire.py:19`, currently only `db_path`) gains a `cadence` field:

```python
class CadenceTierConfig(BaseModel):
    max_age_hours: int
    interval_minutes: int

class CadenceConfig(BaseModel):
    tiers: list[CadenceTierConfig] = Field(default_factory=_default_tiers)  # Hot/Warm/Cold
    cutoff_days: int = 30
    # validator: tiers strictly increasing by max_age_hours, all > 0; cutoff_days*24 >= last tier max_age_hours
    # (the last tier's max_age IS the cutoff boundary in the canonical policy: Cold 720h == cutoff 30d)

class AcquireConfig(BaseModel):
    db_path: ...
    cadence: CadenceConfig = Field(default_factory=CadenceConfig)
```

Surfaced in `config/acquire.json5` + `config.example/acquire.json5` (loaded by `conf/loader.py:120` →
merged `conf/overlay.py:31` → validated `conf/loader.py:200`). The defaults reproduce the frozen decision, so
an absent `cadence` block loads to the canonical Hot/Warm/Cold/30d policy. **Pre-1.0**: schema evolves in
place; no migration. The composition root (`cli_helpers/__init__.py:26`) does **not** read `cadence` at boot —
it is threaded through `Config` and read only by the `follow detect` command + the cadence-aware loop.

### Per-series override — `FollowedSeries.cadence_json`

The column exists and is inert (`migrations/001_init.sql:14`, `domain.py:45`). D2 adds codecs in
`desired.py` mirroring the `quality_profile_json` pattern (`desired.py:128-214`):

```python
def cadence_to_json(cadence: Cadence) -> str: ...
def cadence_from_json(blob: str | None) -> Cadence | None: ...   # None blob → None (use global default)
def cadence_from_config(cfg: CadenceConfig) -> Cadence: ...       # unit bridge: hours/min/days → seconds VO
def effective_cadence(series_override: Cadence | None, global_default: Cadence) -> Cadence:  # series → global
```

These bridges live in `desired.py` (alongside the `quality_profile_json` codecs) so `acquire/cadence.py` stays
pure (it never imports `conf`). `cadence_from_config` converts the Pydantic `CadenceConfig`
(`max_age_hours`/`interval_minutes`/`cutoff_days`) into the seconds-based `Cadence` VO. **Precedence is
whole-object** (the per-series `cadence_json` encodes a complete `Cadence`): `effective_cadence` returns the
series override when present (non-`None`), otherwise the global default verbatim — no field-by-field merge,
since the payload is a tier tuple.

---

## 5. Store + domain additions

### Dedup guard — `WantedSubStore.find`

The wanted table has **no** UNIQUE constraint on `(followed_id, kind, season, episode)`
(`migrations/001_init.sql:18-35`) — only `grabbed_hash` guards double-grab. D2 adds a **soft** dedup guard:

```python
# _ports.py (WantedSubStore protocol, :72-102) + store.py (_WantedSubStore, :434-611)
def find(self, *, followed_id: int | None, kind: WantedKind,
         season: int | None, episode: int | None) -> WantedItem | None: ...
```

The `WHERE` clause must handle NULL `season`/`episode` correctly (episode-kind has both non-NULL; the method
is used by D2 only for episodes). D2 calls `find()` before `add()`; a hit → skip (record "skipped-dup"). A soft
guard (not a UNIQUE constraint) is chosen so D2 can _distinguish and report_ the dedup, and to avoid the
NULL-in-UNIQUE subtlety for the future movie case. The absence of a hard constraint is a **documented caveat**;
detection is single-writer (one `follow detect` at a time, serialized by the store's `BEGIN IMMEDIATE`).

### No new wanted columns

Cadence needs only `enqueued_at` + `last_search_at` + `attempts`, all present (`domain.py:73-109`,
`last_search_at:86`, `attempts:107`, `followed_id:102`). The `claim_for_search` path
(`store.py:533-562`) already increments `attempts` and stamps `last_search_at` atomically under
`BEGIN IMMEDIATE` with a `status='pending'` guard — unchanged.

---

## 6. DETECT → WantedItem mapping

`AiredEpisode(media_ref, season, episode, air_date, title)` (`domain.py:50-70`) →

```python
WantedItem(
    media_ref   = ep.media_ref,        # the series ref (tvdb primary), carried through from poll_aired
    kind        = 'episode',
    status      = 'pending',
    enqueued_at = now,                 # detection time (injected, no hidden clock — see §10)
    followed_id = fs.id,               # FK back to the FollowedSeries (cadence resolution in Stage B)
    season      = ep.season,
    episode     = ep.episode,
    criteria_json = <source_criteria_to_json(fs source criteria) or None>,
    # last_search_at, attempts, grabbed_hash default to NULL/0
)
```

`followed_id` is the load-bearing link: Stage B hydrates the `FollowedSeries` from `followed_id` to resolve the
per-series cadence override. `criteria_json` carries any per-series source preferences for D3's later grab (the
grab core reads `effective_quality(series, item)` — `desired.py`).

---

## 7. Cadence-aware `run()` seam (exact placement)

`_process_item` (`service.py:233-298`) current order: (1) re-promote stale `searching`→`pending`
(`:257-261`), (2) `claim_for_search` (`:263`), (3) fetch, (4) hash-guard, (5) resolve profile, (6) grab,
(7) disposition (`:288-298`).

D2 inserts two checks **before the atomic claim** (so a not-yet-due item never wastes a claim or increments
`attempts`):

```
(1) re-promote stale → pending
(2) CUTOFF CHECK:  if is_past_cutoff(cadence, now, enqueued_at):
                       set_status('abandoned'); bus.emit(WantedAbandoned(media_ref, reason='cutoff_reached'))
                       return outcome=abandoned
(3) CADENCE CHECK: if not is_due_by_cadence(cadence, now, enqueued_at, last_search_at):
                       return outcome=skipped            # stays 'pending', re-listed next run, no claim
(4) claim_for_search → fetch → hash-guard → resolve → grab → disposition (unchanged)
```

- `cadence` is `effective_cadence(cadence_from_json(fs.cadence_json), cadence_from_config(config.acquire.cadence))`
  where `fs` is the `FollowedSeries` for `item.followed_id` (hydrated once per run via a
  `followed_id → FollowedSeries` map built from `store.follow`; the global default `Cadence` is also built once
  per run — items with `followed_id is None` fall back to it).
- The flat `_STALE_THRESHOLD_S` (`:74`) and `list_stale_searching(older_than=...)` still select stale
  `searching` rows for **re-promotion**; the cadence predicate then decides whether the re-promoted (or already
  pending) row is actually due. Effectively `_STALE_THRESHOLD_S` becomes a stale-recovery window, not the search
  cadence.
- **`RunSummary` semantics** (`service.py:78-95`): not-due → `skipped`; cutoff → `abandoned`. Preserves the
  existing meaning (`skipped` = "row did not enter the grab pipeline").
- **Emit-after-persist**: the cutoff `WantedAbandoned` is emitted _after_ the `abandoned` write, symmetrical to
  the attempts-cap abandon (`service.py:355-357`) and `GrabSucceeded` (`:333-341`).

---

## 8. Events + Telegram (already wired — emit-only)

- `WantedEnqueued(media_ref, kind, season, episode)` (`events.py:54-69`) — emitted in Stage A after `add()`.
- `WantedAbandoned(media_ref, reason)` (`events.py:73-84`) — emitted in Stage B at cutoff with
  `reason='cutoff_reached'` (joins the existing terminal/attempts-cap emitters at `orchestrator.py:347` /
  `service.py:357`).
- Publish via `bus.emit(EventInstance)` (`core/event_bus.py:412-462`, typed frozen-dataclass contract).
- `AcquisitionTelegramSubscriber` **already** handles both (`subscribers/acquire.py:40-210`,
  `_on_wanted_enqueued:159-169`, `_on_wanted_abandoned`). The acquire events module is in the eager-import hub
  (`events/__init__.py:20-33`, `_acquire_events`) — registration guaranteed. **Zero** subscriber/registration/
  hub changes; D2 only emits.

The detect command needs the event bus on the `AppContext`/`AcquireContext`. Stage A emits only when **not**
`--dry-run`.

---

## 9. CLI — `personalscraper follow detect`

`@follow_app.command("detect")` in `commands/follow.py` (the Typer sub-group, `follow.py:42`, registered via
`add_typer` at `:215` — **no** new registration). Pattern mirrors `follow add`/`follow list`:

- `@handle_cli_errors` decorator; `log = get_logger("cli.follow")` (already module-level, `follow.py:39`).
- `per_step_boundary(config, settings, build_torrent_client=False)` (`cli_helpers/__init__.py:216-253`) yields
  the `AppContext` (provider_registry + acquire + store); read-only, never touches the torrent daemon; the
  boundary calls `acquire.close()` on exit (do not close manually).
- Flags: `--dry-run` (preview, no `add`/`emit`), `--series <name|id>` (optional filter of the active set).
- Output: Rich table `[Series, Season, Episode, AirDate, Title, Action]`, `Action ∈ {enqueued, skipped-owned,
skipped-dup, dry-run}`; summary line `N enqueued, M skipped-owned, K skipped-dup`. Empty active set →
  friendly "No active followed series" message.
- `poll_aired` is fail-soft (logs warnings, returns partial results, never raises `ApiError`/`CircuitOpenError`
  to the command); ownership `owns()` is fail-soft (returns `False` on any error → treated as not-owned).

---

## 10. Layering, determinism, fail-soft invariants

- **Layering**: `acquire/cadence.py` imports `core`/stdlib only. The CLI command lives at the boundary
  (`commands/`), composes the context, and never imports `indexer`/`pipeline`. `acquire/` reaches ownership only
  via `core.ownership` (the concrete `IndexerOwnershipChecker` is injected at the composition root,
  `cli_helpers/__init__.py:174-213`, `acquire/_factory.py:145-156`). RP-layer guard (if active) must still pass.
- **Determinism**: `today`/`now` are injected (mirrors RP9's `poll_aired(*, today)`) — the detect command
  passes `date.today()`; the cadence predicate takes `now: int` (unix seconds). No hidden clocks in the pure
  cadence module or the enqueue logic (testability).
- **Fail-soft**: a single series failing to poll (RP9 fail-soft) does not abort detection; ownership errors →
  not-owned (may over-enqueue, acceptable — D3 grab is idempotent on `grabbed_hash`); Telegram outage →
  subscriber swallows (existing behavior).
- **Composition-root safety**: `cadence` config is read lazily by the command/loop, **not** built at
  `_build_app_context` — no shared-lifetime lock, no cross-command serialization regression.

---

## 11. Verification (ACCEPTANCE — every criterion an executable command, SH-16)

1. **Cadence predicate** — Hot/Warm/Cold tier selection + interval gating + cutoff, all boundaries (age=0,
   72h±1, 14d±1, 30d±1; `last_search_at` None vs recent vs stale). Pure unit tests, injected `now`.
2. **`effective_cadence`** — series override wins field-by-field; `None` → global default verbatim.
3. **Config** — `CadenceConfig` default reproduces the frozen Hot/Warm/Cold/30d policy; validator rejects
   non-monotonic / non-positive tiers; absent `cadence` block loads the default.
4. **`store.wanted.find`** — returns the row for a known `(followed_id, 'episode', season, episode)`, `None`
   otherwise; round-trips through `add`.
5. **DETECT golden** — given a followed set + stubbed `poll_aired` + stubbed ownership, asserts **which**
   episodes are enqueued vs skipped-owned vs skipped-dup, that `WantedEnqueued` is emitted once per enqueue with
   the right fields, and the `WantedItem` carries `followed_id`/`kind='episode'`/`status='pending'`.
6. **DETECT `--dry-run`** — zero `store.wanted.add` calls, zero events emitted, table still rendered.
7. **Cadence-aware `run()`** — a not-due item is `skipped` (no `claim_for_search`, `attempts` unchanged);
   a due item proceeds to claim; a past-cutoff item is set `abandoned` and emits
   `WantedAbandoned(reason='cutoff_reached')` **before** any grab, with no claim.
8. **Boundary preserved** — DETECT makes zero grab calls; `poll_aired`'s negative-boundary tests still pass
   (no `cadence_json` read, no `store.wanted.*`, no `ownership.owns`).
9. **Layering guard** — `acquire/cadence.py` imports no `indexer`/`store`/`scraper`/event-bus.
10. **`make check`** green; `python -c "import personalscraper"` smoke.

---

## 12. Decisions

- **A** — Two-stage: a dedicated DETECT command produces the queue; the **existing** `AcquisitionService.run()`
  loop is made cadence-aware (no new loop). The grab stays D3 (already shipped).
- **B** — Dedicated `follow detect` CLI subcommand (not folded into `grab`/`run`); standalone, later driven by
  the Watcher.
- **C** — Soft dedup via `store.wanted.find()` before `add()` (no UNIQUE constraint) — reportable, NULL-safe for
  the future movie case; single-writer detection makes the soft guard sufficient.
- **D** — Cadence logic in a new pure `acquire/cadence.py` (VO + two functions), config in `conf/models/acquire.py`,
  codecs in `desired.py` — layering-clean, testable in isolation.
- **E** — Poll **all** active series each run (no `last_poll_at` column) — the followed set is bounded, RP9 is
  rate-limited + circuit-protected, and the cadence/ownership/dedup throttle downstream (airing DESIGN §10).
- **F** — Episode-only (`kind='episode'`); movie-follow is out of scope (separate trigger).

---

## 13. Phase decomposition (for `implement:plan`)

1. **Cadence module + config + codec** — `acquire/cadence.py` (`Cadence`/`CadenceTier`, `is_due_by_cadence`,
   `is_past_cutoff`; pure, `core`/stdlib only), `CadenceConfig` in `conf/models/acquire.py` + `acquire.json5`
   (both example + real), `cadence_to_json`/`cadence_from_json`/`cadence_from_config`/`effective_cadence` in
   `desired.py`. Tests: criteria 1-3.
2. **Wanted dedup** — `WantedSubStore.find()` + `_ports.py` protocol + impl in `store.py`. Tests: criterion 4.
3. **DETECT + `follow detect` CLI** — detect logic (`list_active` → `poll_aired` → ownership filter → dedup →
   `add` → emit `WantedEnqueued`), `@follow_app.command("detect")` with `--dry-run`/`--series`, Rich output.
   Tests: criteria 5-6, 8 (boundary), 9 (layering).
4. **Cadence-aware `run()` loop** — insert cutoff + cadence checks before `claim_for_search` in `_process_item`,
   `WantedAbandoned(reason='cutoff_reached')` emit, `RunSummary` semantics, retire flat-threshold-as-cadence.
   Tests: criterion 7.
5. **Docs + ACCEPTANCE + gate** — surgical `docs/reference/architecture.md` edit (`acquire/cadence.py` + the
   Follow D2 boundary note), `ACCEPTANCE.md` (criteria 1-10 as executable commands), `make check` +
   design-gaps local run.
