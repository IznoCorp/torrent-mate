# [O4] Seed Safety — download events + bandwidth caps (ticket #177)

**Date**: 2026-08-03 · **Codename**: `seed-caps` · **Type**: feat · **Bump**: minor (0.75.2 → 0.76.0)

## 1. Problem

Ticket #177 (roadmap O4): « Events de download (via RP4) + caps de bande passante par
torrent ET globaux. » Re-scope verified against the tree on 2026-08-03:

- **Per-torrent caps — plumbing shipped, never exercised.** `TorrentLimits`
  (`api/torrent/_base.py:150`) carries `up_bytes_per_s`/`down_bytes_per_s`;
  `TorrentClient.add()` accepts `limits=` (`_contracts.py:149`) and the qBittorrent
  mapper folds them atomically into `torrents_add` (`_limit_kwargs`,
  `qbittorrent.py:845`); `TorrentLimiter.apply_limits` exists for post-add changes.
  **Zero callers build a `TorrentLimits` anywhere.**
- **Global caps absent.** No `transfer_set_*` call exists; qBittorrent's global
  transfer limits are never managed.
- **Download events absent.** `acquire/events.py` has 19 events (Grab*, SeedObligation*,
  CrossSeed*, Season*…) but nothing between `GrabSucceeded` and library ownership.
  Download progress exists only as a polled field in the web read-model
  (`web/acquisition/downloads.py`) — invisible to Telegram and the event feed.

Dependency #154 (RP4 event catalogue) is CLOSED. Scope boundary: `ratio` /
`seed_time_minutes` share-limits stay UNTOUCHED (None) — they belong to #173 (C1 ratio
loop) / #174 (O3 disk arbiter). O4 is bandwidth + events only.

## 2. Decisions (defaults per operator arbitrage sources)

| #   | Decision                                                                                                                                               | Rationale                                                                                         |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| D1  | Config lives at `acquire.bandwidth` (new `BandwidthConfig` on `AcquireConfig`)                                                                         | Caps are acquisition/seed-safety operational policy; Réglages S4 write-path can expose it later   |
| D2  | `None` = touch nothing (per-field). We never reset a limit the operator set by hand in qBittorrent                                                     | Least-surprise; mirrors `apply_limits` no-op contract                                             |
| D3  | Per-torrent caps applied AT ADD TIME via the existing `add(limits=)` parameter — atomic, no second API call                                            | Plumbing already ships it; no new failure window                                                  |
| D4  | Clients without `TorrentLimiter` (Transmission): gate `isinstance` in the orchestrator, log `grab.limits.unsupported` once, add WITHOUT limits         | D8 contract raises otherwise; a cap must never block a grab                                       |
| D5  | Global caps re-asserted at the START of every acquire run (idempotent, self-healing), fail-soft on `ApiError` (log warning, run continues)             | An operator change in the qBit UI self-heals on next pass; a dead client must not block searches  |
| D6  | Download events emitted from `reconcile_wanted` — the pass that already walks hash-carrying wanted rows against the client                             | Single truthful observation point; no new poller                                                  |
| D7  | Exactly-once via a new `download_marks` table (migration 014), pruned when the wanted row leaves the open set                                          | Events must not re-fire across runs; marks are advisory state, no FK (provenance-spine precedent) |
| D8  | `DownloadProgressed` fires on 25/50/75 % threshold crossings only; Telegram subscribes to `DownloadCompleted` only; the web event feed shows all three | Anti-spam; §8 « rien en silence » satisfied by the feed, not by Telegram noise                    |
| D9  | `reconcile_wanted` gains a REQUIRED `event_bus` parameter and its `client_hashes` parameter becomes `client_items: dict[str, TorrentItem]              | None`                                                                                             | Project contract: event_bus required at every emission site, all callers updated; `commands/grab.py:164` already fetches full items and throws them away |
| D10 | Humanized byte sizes accepted in config (`"5MB"`), reusing the ByteSize coercion pattern of `conf/models/_ranking.py`                                  | Consistency with size tiers UX                                                                    |

## 3. Components

### 3.1 Config — `BandwidthConfig` (new, `conf/models/acquire.py`)

```python
class BandwidthConfig(_StrictModel):
    per_torrent_down: int | None = None   # bytes/s; humanized str coerced; None = no cap
    per_torrent_up: int | None = None
    global_down: int | None = None        # None = leave qBittorrent setting alone
    global_up: int | None = None
```

- Field validator coerces `"5MB"`-style strings via pydantic ByteSize (same as `_ranking.py`).
- Values are bytes/s. Validation: `> 0` when set (0 is NOT the "unlimited" sentinel in
  our config — unlimited is expressed by omitting the key; the qBittorrent wire value 0
  is produced only by the mapper, never written by the operator).
- `AcquireConfig.bandwidth: BandwidthConfig = Field(default_factory=BandwidthConfig)`.
- `config.example/acquire.json5` gains the commented block (config-drift rule).

### 3.2 Per-torrent caps (orchestrator)

- `GrabOrchestrator.__init__` gains `bandwidth: BandwidthConfig` (required — wired from
  `_factory.py:169` and `commands/search.py:203`).
- In the add path (`orchestrator.py:~890`): when `per_torrent_down` or `per_torrent_up`
  is set AND `isinstance(self._torrent_client, TorrentLimiter)` → build
  `TorrentLimits(up_bytes_per_s=…, down_bytes_per_s=…)` (ratio/seed_time stay None) and
  pass `limits=` to `add()`. Unsupported client + configured caps → structlog warning
  `acquire.grab.limits_unsupported` (once per run via a flag), add without limits.
- No behavior change when both fields are None (default).

### 3.3 Global caps (new capability protocol)

- `_contracts.py`: new runtime-checkable protocol `GlobalRateLimiter` with
  `apply_global_limits(up_bytes_per_s: int | None, down_bytes_per_s: int | None) -> None`
  (None field = no API call, same contract as `apply_limits`).
- `qbittorrent.py`: implement via `transfer_set_upload_limit` / `transfer_set_download_limit`
  (qbittorrentapi). Transmission: deliberately NOT implemented (module docstring updated).
- Call site: acquire run entry (`service.py`, before the search pass), guarded by
  `isinstance` + at-least-one-field-set; `ApiError` → `acquire.global_limits.failed`
  warning, run continues (D5).

### 3.4 Download events (RP4 catalogue additions, `acquire/events.py`)

```python
class DownloadStarted(Event):    # first observation in client, progress < 1.0
    info_hash: str; title: str; provider: str; kind: str

class DownloadProgressed(Event): # 25/50/75 threshold crossing (highest crossed)
    info_hash: str; title: str; progress: float; threshold_pct: int

class DownloadCompleted(Event):  # first observation with progress >= 1.0
    info_hash: str; title: str; provider: str; kind: str
```

- Frozen kw_only dataclasses over `core.event_bus.Event`, docstrings per RP4 house style.
- `title`/`provider`/`kind` come from the wanted row (already loaded by reconcile).
- A torrent observed already-complete on its first sighting emits `DownloadCompleted`
  only (no synthetic Started/Progressed backfill — events are observations, not history).

### 3.5 Exactly-once marks (migration 014, `_wanted_store.py` or sibling store)

```sql
CREATE TABLE download_marks (
  info_hash TEXT PRIMARY KEY,
  started_emitted INTEGER NOT NULL DEFAULT 0,
  last_threshold INTEGER NOT NULL DEFAULT 0,   -- 0|25|50|75
  completed_emitted INTEGER NOT NULL DEFAULT 0,
  updated_at REAL NOT NULL
);
```

- Read-modify-write inside reconcile's existing transaction discipline; emit AFTER
  persist (emit-after-persist precedent, DESIGN season-grab §15).
- Prune: reconcile deletes marks whose info_hash no longer belongs to any OPEN wanted
  row (same sweep that closes rows). Terminal rows keep no marks.
- Migration runner tolerance already handles cross-version shared DB (user_version 14).

### 3.6 Reconcile signature change

```python
def reconcile_wanted(
    store, ownership,
    client_items: dict[str, TorrentItem] | None,   # was: client_hashes: set[str] | None
    *, event_bus: EventBus,                         # NEW, required
) -> ReconcileSummary:
```

- Internally derives `client_hashes = set(client_items)` — every existing presence
  check is unchanged.
- New emission block per hash-carrying OPEN row present in `client_items`: compare
  `TorrentItem.progress` against `download_marks`, emit transitions, persist marks.
- Callers updated: `commands/grab.py` (passes the dict it already fetches at line 164),
  `commands/search.py` (passes `None` → ownership-only half, zero events — unchanged
  semantics), plus any test fixture.

### 3.7 Subscribers + web feed labels

- `subscribers/acquire.py`: subscribe `DownloadCompleted` (13th) —
  « ✅ Téléchargement terminé : {title} ». Started/Progressed NOT wired to Telegram (D8).
- Frontend `eventTypeLabel` map: French labels for the three new types
  (« Téléchargement démarré », « Téléchargement en cours (N %) », « Téléchargement terminé »)
  - summary rendering; vitest coverage for the labels (X7 rule: no raw enum ever rendered).
- No new route, no OpenAPI change expected (event feed is schema-generic). If any
  Pydantic route model changes after all, `make openapi` + commit (CI drift guard).

## 4. Error handling

| Failure                                                      | Behavior                                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `add()` with limits fails                                    | Same taxonomy as today (§6.2 catch order) — limits add no new failure class (atomic kwargs)                                                                                                                                                                                                                                                  |
| Client lacks `TorrentLimiter` and caps configured            | Warning once per run, grab proceeds uncapped (D4)                                                                                                                                                                                                                                                                                            |
| `apply_global_limits` ApiError                               | Warning `acquire.global_limits.failed`, run continues (D5)                                                                                                                                                                                                                                                                                   |
| Marks write fails                                            | Reconcile row processing continues; event skipped this pass (next pass retries — at-least-once bounded by marks persist-before-emit ordering: persist first, so a crash between persist and emit LOSES that emit rather than duplicating it — chosen deliberately: feed events are advisory, duplicates are worse than one missed threshold) |
| Shared DB opened by prod (user_version 14 unknown to 0.75.x) | `_migrate.py` no-ops when user_version ≥ highest known (verified behavior)                                                                                                                                                                                                                                                                   |

## 5. Testing

- Unit: BandwidthConfig coercion/validation (humanized strings, zero rejection);
  orchestrator limits gating (capable client / incapable client / no config);
  global-limits call + fail-soft; marks store CRUD + prune.
- Behavior: reconcile emission matrix — fresh hash mid-download → Started (+thresholds
  crossed so far? NO — only the highest crossed threshold at first sighting, per D8
  «crossings», assert exactly one Progressed max per pass); progress regression (qBit
  recheck) does NOT re-emit lower thresholds; already-complete first sighting → Completed
  only; second pass same state → zero emits (exactly-once); row closes → marks pruned.
- Events: one regression test per event class asserting emit-after-persist ordering.
- Subscribers: DownloadCompleted Telegram message golden; Started/Progressed absent.
- Frontend: eventTypeLabel unit tests for the three labels.
- Migration: 014 upgrade + no-op-on-newer tests (existing harness patterns).
- E2E manual (ACCEPTANCE): grab with caps configured → qBittorrent shows per-torrent
  limits; global limits visible in qBit UI; event feed shows the download lifecycle.

## 6. Suggested phases

1. Config (`BandwidthConfig` + example) + migration 014 + marks store.
2. Per-torrent caps (orchestrator + wiring) + global caps (protocol + qBit impl + service call site).
3. Events catalogue + reconcile signature change + emission logic + callers.
4. Subscribers + frontend labels + ACCEPTANCE + full gate.

## 7. Out of scope (explicit)

- Ratio/seed-time share limits (→ #173/#174).
- Any web write-path UI for bandwidth config (S4 editor covers `acquire.*` generically
  if/when exposed; not this ticket).
- Transmission implementations of either capability.
- Scheduling/throttling windows (time-of-day caps) — YAGNI until an operator ask.
