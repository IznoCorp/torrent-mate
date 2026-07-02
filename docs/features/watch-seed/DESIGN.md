# Design — watch-seed (Watcher Service + native cross-seeding)

**Status**: brainstormed 2026-07-02 — combined feature approved by operator
**Codename**: `watch-seed`
**Type**: minor (0.38.0 → 0.39.0) · commit type `feat` · branch `feat/watch-seed`
**Supersedes**: `docs/superpowers/roadmap/cross-seed/specs/DESIGN.md` (prepared 2026-06-19,
uncommitted) — its D1–D11 decisions are carried over verbatim below; the roadmap copy is
deleted when this design lands on the feature branch.
**Roadmap**: folds **Watcher Service** (Vague 4) + **RP10** (Vague 3/4) + **Cross-Seed X1/X2**
(Vague 5) into one feature, per operator decision 2026-07-02 (X1's per-completion trigger
depends on the Watcher; shipping them together closes the loop in one PR).

## Problem / Goal

Two gaps, one seam:

1. **No trigger.** The pipeline has no working scheduled trigger today. The intended
   launchd agent (`com.personalscraper.pipeline`, daily 03:00) is **not installed** on the
   host, and its template is **broken** (`python -m personalscraper run` — no `__main__.py`
   exists; verified live 2026-07-02). Three installed indexer LaunchAgents point at the
   stale misspelled repo path `/Users/izno/dev/PersonnalScaper` and have been silently
   failing (exit 1) for months. The pipeline only runs when invoked manually.
2. **No cross-seeding.** A completed torrent seeds on exactly one tracker. The same bytes
   in qBittorrent's `complete/` could seed the identical release on every other managed
   tracker at zero download cost. Nothing does this.

**Goal**: a **Watcher daemon** (PM2-managed `personalscraper watch`) becomes the single
trigger authority — it polls qBittorrent, reacts to completions by (a) invoking the
**cross-seed per-completion path** and (b) firing a debounced pipeline run, with a 24 h
safety-net sweep — and the **native cross-seed engine** (RP10a structural matcher + RP10b
inject + `CrossSeedService`) multiplies ratio on managed trackers. launchd is fully
decommissioned; all personalscraper daemons/scheduled jobs migrate to PM2.

This is **native** cross-seeding (the project replaces the Prowlarr/Jackett/autobrr stack
per the ROADMAP vision), **not** an integration of the external `cross-seed` tool.

## Frozen decisions

### Cross-seed half (D1–D11, brainstorm 2026-06-19 — carried over unchanged)

| #   | Decision          | Choice                                                                                                                                                                                                                    |
| --- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Build vs buy      | **Native** — reuse existing Python bricks; no Prowlarr/Jackett/autobrr (the project replaces them).                                                                                                                       |
| D2  | Seed source       | **qBittorrent's `complete/` copy ONLY.** Staging is a disposable copy, never the seed source. Single filesystem → no multi-disk/linking problem.                                                                          |
| D3  | Trigger           | Per-completion path via the **Watcher** — which ships **in this same feature** (was: deferred to Vague 4) — **+** a throttled CLI for the back-catalog sweep. No new daemon beyond the Watcher itself.                    |
| D4  | Matching          | **Structural full-match (strict)**: name prefilter → fetch candidate `.torrent` → parse its file-list → compare file-tree + sizes + `piece_length` → inject only on match → qBittorrent recheck is the **final arbiter**. |
| D5  | Target trackers   | **Managed trackers only** (registry-gated), origin tracker excluded.                                                                                                                                                      |
| D6  | Scope v1          | **All** completed torrents, **per-completion + initial throttled back-catalog sweep**.                                                                                                                                    |
| D7  | Search signal     | **Release name** (strongest signal for an _identical_ release); media-id secondary.                                                                                                                                       |
| D8  | Architecture      | **Shared RP (RP10 = structural match + inject engine)** + a **thin `CrossSeedService`** in `acquire/` on top.                                                                                                             |
| D9  | Tracker gate      | **Per-tracker opt-in** (`cross_seed: false` by default).                                                                                                                                                                  |
| D10 | Obligation timing | Write the seed obligation **after recheck confirms** (no phantom HnR obligations).                                                                                                                                        |
| D11 | Linking           | **None in v1.** Renamed-but-byte-identical releases (need hardlink/symlink) are **deferred** post-v1.                                                                                                                     |

### Watcher half (W1–W8, brainstorm 2026-07-02)

| #   | Decision          | Choice                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| W1  | Watch mechanism   | **Poll** `TorrentLister.get_completed()` every `poll_interval_s` (default 60 s). No qBittorrent `sync/maindata` delta API in v1 (entirely net-new, nothing to reuse). Poll failures use the existing `TORRENT_LISTING_ERRORS` except-tuple: log + skip cycle, never crash.                                                                                                                                                               |
| W2  | Process model     | **PM2** — operator directive: _all_ personalscraper daemons/scheduled jobs migrate to PM2. Repo ships `ecosystem.config.js`. launchd is fully decommissioned (templates, scripts, installed agents, docs).                                                                                                                                                                                                                               |
| W3  | Trigger semantics | **Event-driven + 24 h safety net**: completions trigger runs; if no successful run for `safety_net_hours` (default 24), fire a sweep run. Keeps the existing Healthchecks.io 1-day-period check valid unchanged.                                                                                                                                                                                                                         |
| W4  | Debounce + manual | Quiet-window debounce, **default 900 s (15 min)**, configurable. Manual bypass: `personalscraper watch-now` writes a sentinel file in `data_dir`; the daemon consumes it next cycle → immediate run (future Web UI uses the same channel). Manual `personalscraper run` keeps working (same lock; Watcher sees it held and requeues).                                                                                                    |
| W5  | Execution model   | **Subprocess CLI** — the daemon is a pure scheduler: it spawns `personalscraper run --no-console` and `personalscraper cross-seed --hash <H>` as subprocesses. Reuses lock/healthcheck/Telegram/exit-code semantics 1:1; pipeline crash isolated from the daemon; fresh memory per run.                                                                                                                                                  |
| W6  | Lock discipline   | `pipeline.lock` is acquired **by the spawned run only** (CLI already does), never for the daemon's lifetime. Lock held (a manual run in progress) → the daemon requeues the trigger and retries after the debounce interval.                                                                                                                                                                                                             |
| W7  | Work predicate    | "Pipeline-worthy work exists" = ∃ completed torrent with hash ∉ `ingested_torrents.json` ∧ `SEED_PURE` ∉ tags. **No new dedup state** — `IngestTracker` is already the authority. Anti-storm: if the predicate stays true after a run (item repeatedly failing ingest), exponential backoff up to the safety-net interval.                                                                                                               |
| W8  | launchd cleanup   | **Full decommission in this feature**: delete `com.personalscraper.pipeline.plist.template`, `scripts/install-launchd.sh`, `scripts/uninstall-launchd.sh`, `launchd-plists/`, `docs/reference/launchd/`; operator runbook removes the 3 stale indexer agents (index-quick/rotate redundant since index-sync #211; index-enrich becomes a PM2 `cron_restart` entry); update INSTALLATION.md / MANUAL.md / commands.md / CONFIGURATION.md. |

## Architecture

Three tiers: the shared RP10 engine, the `CrossSeedService`, and the Watcher.

### RP10 — shared "structural match + inject" engine (net-new primitives)

Reusable beyond cross-seed (e.g. future E2 re-scrape).

- **RP10a — `.torrent` introspection + structural matcher.** Extend the bencode parser in
  `api/torrent/_base.py` (existing `_bencode_info_hash`, `_bencode_str`, `_bencode_end`,
  depth cap 100) with a **file-list extractor**: parse `info.name`, `info.piece length`,
  and `info.files[]` (multi-file) / `info.length` (single-file) into a typed
  `TorrentLayout` (`name`, `piece_length`, `files: [(rel_path, size)]`, `total_size`).
  Add a **pure** `structural_match(local: TorrentLayout, candidate: TorrentLayout) ->
MatchVerdict` (full-match strict: identical `piece_length` ∧ identical file-list —
  relative paths + sizes + order — ∧ identical root name `info.name`: without linking,
  the injected torrent is pointed at the source's `save_path` and must find every file at
  the exact path it declares, so a renamed root cannot match in v1 — D11). Detect and
  reject BitTorrent v2/hybrid (`info.meta version == 2`) in v1.
- **RP10b — `inject` capability on the torrent-write protocol.** Extend
  `api/torrent/qbittorrent.py` (today `add()` omits `savepath` per its D10, no
  `skip_checking`, no recheck) with an **inject path**: a new method
  `inject(source, *, save_path, recheck=True, paused=True) -> str` that POSTs the
  candidate `.torrent` bytes with `savepath=<source torrent's save_path>`,
  `skip_checking=false`, added paused, then drives a **recheck** and exposes the result
  state. Add `list_files(info_hash) -> list[(rel_path, size)]` and
  `properties(info_hash)` (wrap `torrents_files` / `torrents_properties`) to read a local
  torrent's layout + `piece_length`. Extend the `TorrentItem` mapper with `save_path` and
  `completion_on` (currently dropped by `_torrent_item`). Gate via a new
  `@runtime_checkable` protocol `TorrentInjector` in `api/torrent/_contracts.py`,
  `isinstance`-checked by callers exactly like `TorrentLimiter` / `TorrentTagger` →
  Transmission opts out cleanly.

### cross-seed — `CrossSeedService` (in `acquire/`)

Thin orchestration consuming RP10 + existing ports. Injected at the single composition
root (`_build_app_context` → `build_acquire_context`) via **one handle** (RP5c
discipline), depends **downward** on `api/` ports + `acquire.db` (RP-layer guard), never
imports the triage packages.

- **X1** — `CrossSeedService` core + per-completion entry (`check(info_hash)`) +
  per-tracker gate (RP2 extension).
- **X2** — back-catalog sweep + throttle (quota/day, inter-search delay, exclude-recent),
  persisted in `acquire.db`.

Reused as-is: `TrackerRegistry.search_candidates` (`api/tracker/_registry.py`),
`resolve_source` / `fetch_torrent_source` (RP1a, `api/tracker/_fetch.py`),
`core/tags.SEED_PURE` (O1), `SeedObligation` + `SeedSubStore.add` (RP3,
`acquire/domain.py` + `acquire/store.py` — the only obligation write API),
`TrackerEconomyConfig` (RP2, `conf/models/api_config.py`).

CLI: `personalscraper cross-seed --sweep` (throttled back-catalog) and
`personalscraper cross-seed --hash <H>` (single-torrent check — the form the Watcher
spawns per completion, and the operator's manual entry point).

### Watcher — `WatcherService` (in `acquire/`) + `watch` command loop

- **`acquire/watcher.py` — `WatcherService`**: a **pure** decision engine (injected clock,
  no I/O, no sleep — house style per `acquire/cadence.py` and `indexer/_throttle.py`).
  Holds the poll/debounce/safety-net/backoff state machine. Inputs per cycle: the
  completed-torrent snapshot, the ingested-hash set, sentinel-poke flag, now(). Output: a
  decision (`idle` | `start_debounce` | `fire_run(reason)` | `fire_cross_seed(hashes)` |
  `requeue`). Unit-testable exhaustively without a daemon.
- **`commands/watch.py` — the loop** (commands layer — `acquire/` may not import
  `commands/`/`pipeline`, so inversion lives here): builds a **listing-only** qBittorrent
  client, reads `IngestTracker`'s hash set, consults `WatcherService`, executes decisions
  by spawning subprocesses (W5), consumes/clears the sentinel file, handles SIGTERM
  gracefully (finish current cycle, never kill a spawned run), re-login policy honoring
  the existing 1 h auth-lockout file. New module must be added to the
  `test_app_context_boundary.py` allowlist if it touches `AppContext`, and uses
  `personalscraper.logger.get_logger` (check_logging lint).
- **`commands/watch.py` also registers `watch-now`**: writes the sentinel file
  `data_dir/watch.trigger` and exits. No IPC, no daemon dependency — if the daemon is
  down, the sentinel is consumed at next boot.
- **`run --no-console` flag** (small extension to `commands/pipeline.py`): Rich console
  off, **Telegram on** — the daemon-spawned-run mode. Today's `--headless` disables both;
  it remains unchanged.

### Watcher flow

```
every poll_interval_s (default 60):
  1. sentinel present?                        → consume → fire run NOW (reason=manual)
  2. get_completed()  [TORRENT_LISTING_ERRORS → log, skip cycle]
  3. NEW completions (completion_on / first-seen) not SEED_PURE
       → spawn `cross-seed --hash H` per hash   (exempt from debounce; idempotent via
                                                 exclude-recent + Conflict409)
  4. work predicate (W7) true?
       → not in debounce: start debounce window (debounce_s, default 900)
       → debounce expired: spawn `run --no-console` (reason=completion)
  5. no successful run for safety_net_hours (default 24)?
       → spawn `run --no-console` (reason=safety_net)
  6. spawn attempted but pipeline.lock held (exit "Another instance is running")
       → requeue, retry next debounce interval (W6)
  7. run finished OK → record last_successful_run_at; predicate still true?
       → exponential backoff before next auto-run (W7 anti-storm)
```

### Cross-seed engine flow (per source torrent — carried over)

```
1. Read the source's LOCAL layout            → RP10b list_files + properties
                                               (rel paths, sizes, piece_length, save_path)
   skip if tagged SEED_PURE (it IS a cross-seed) or BitTorrent v2/hybrid
2. Build query from the release NAME          → D7
3. search_candidates(name, media_type)        → existing registry; managed trackers;
                                                EXCLUDE the origin tracker; gate cross_seed=true
4. For each candidate:
     resolve_source(candidate) → fetch .torrent  → RP1a (auth handled, 10 MiB cap)
     RP10a parse → candidate TorrentLayout
     RP10a structural_match(source, candidate)   → full-match strict (D4)
5. On match → injection step
6. Persist (source_hash, tracker, date) in acquire.db → exclude-recent
```

## Injection, recheck, tagging, obligations (carried over)

**Injection (RP10b)**: `inject(candidate_source, save_path=<source.save_path>,
recheck=True, paused=True)` → POST candidate `.torrent` bytes to qBittorrent, `savepath`
on the existing `complete/` data, `skip_checking=false`, added paused, then **recheck**.
qBittorrent re-hashes the pieces against the existing data and seeds only what verifies —
**no re-download**, and a false match simply fails verification. Idempotent: an
already-present hash returns via the existing `Conflict409` handling.

**Obligation written AFTER recheck confirms (D10)**:

```
inject (paused) → recheck → poll torrent state
  if verified (100% — strict full-match)  → resume + add_tags(SEED_PURE) + write SeedObligation
  else (false match slipped through)       → remove the injection + log, NO obligation
```

The `SeedObligation` carries `info_hash=injected`, `source_tracker=target`,
`min_seed_time`/`min_ratio` from that tracker's `TrackerEconomyConfig` (RP2),
`dispatched_path=<complete/ content path>`. Enforcement remains **O2's** policy (future);
recording obligations now is forward-compatible — the store already supports N
obligations per path (`find_active_under`).

**Tagging (O1)**: `add_tags(info_hash, [SEED_PURE])` → ingest skips unconditionally
(`ingest/ingest.py`), the Watcher's work predicate skips too (W7). The real content
already passed triage via the original torrent; the cross-seed copy is pure seed.

## Config

New blocks in **both** `config/` and `config.example/` overlays (anti-drift rule):

- **`watch`** block: `enabled: false` (kill-switch), `poll_interval_s: 60`,
  `debounce_s: 900`, `safety_net_hours: 24`.
- **`cross_seed`** block: `enabled: false` (global kill-switch),
  `max_searches_per_day` (~250), `min_delay_between_searches_s` (~30),
  `exclude_recent_search_days` (~3).
- **`TrackerProviderConfig.cross_seed: bool = False`** (RP2 family) — per-tracker opt-in
  in `config/tracker.json5` + `config.example/tracker.json5`.

## State

- Watcher: one tiny KV entry in `acquire.db` (`last_successful_run_at`) via the store's
  lazy-open + BEGIN IMMEDIATE discipline (never a lifetime lock — composition-root rule).
  Debounce deadline and backoff live in memory: a PM2 restart re-derives them (work
  predicate re-evaluates; safety-net timer restarts from persisted state).
- Cross-seed: search history (`source_hash`, `tracker`, `searched_at`) + daily quota
  counter in `acquire.db` (X2 sub-store).

## Events (RP4 pattern)

New frozen kw_only dataclasses over `core.event_bus.Event` in `acquire/events.py`:
`WatcherRunTriggered(reason: completion|safety_net|manual)`,
`CrossSeedInjected(info_hash, source_tracker)`, `CrossSeedRejected(info_hash, tracker,
reason)`. All events are emitted in-process by the **spawned CLI commands** (which own
their AppContext/bus and Telegram subscribers) — the daemon itself stays event-silent
(its EventBus would be invisible cross-process anyway) and reports via structlog to PM2
logs. Since the daemon knows the trigger reason but the spawned `run` owns the bus, `run`
gains a hidden `--trigger-reason` option (default absent = manual CLI invocation): when
set, the run command emits `WatcherRunTriggered` on its bus before `PipelineStarted`, so
Telegram/future Web UI can attribute the run. Reuses `SeedObligationRecorded` (already in
catalog).

## PM2 + launchd cutover (W2/W8)

- Repo ships **`ecosystem.config.js`**: app `personalscraper-watch` (script:
  `personalscraper`, args `watch`, `interpreter: 'none'`, autorestart on) + scheduled
  entries with `autorestart: false` + `cron_restart`: weekly `library-index --mode enrich
--budget 1800`, weekly `backfill-ids` (replaces the never-installed launchd plist).
- **Deleted from repo**: `com.personalscraper.pipeline.plist.template`,
  `scripts/install-launchd.sh`, `scripts/uninstall-launchd.sh`, `launchd-plists/`,
  `docs/reference/launchd/`.
- **Operator cutover runbook** (shipped in `docs/reference/runbook-post-merge.md`):
  `launchctl bootout` + rm of the 3 stale `personalscraper-index-*` plists (quick/rotate
  redundant since index-sync #211; enrich now PM2-scheduled),
  `pm2 start ecosystem.config.js && pm2 save`.
- **Docs updated**: INSTALLATION.md (§launchd → §PM2), MANUAL.md, README.md,
  `docs/reference/commands.md` (scheduling section), CONFIGURATION.md (healthcheck note:
  1-day period stays valid thanks to the W3 safety net).

## Non-goals

- No Prowlarr/Jackett/autobrr (D1). No external `cross-seed` tool.
- No cross-seeding from staging or the dispatched media library — `complete/` only (D2).
- No **linking** (hardlink/symlink/reflink) → no renamed-release matching in v1 (D11).
- No fuzzy/partial matching — strict full-match only (D4).
- No new tracker auth primitive (reuse RP7). No ratio/economy _engine_ work (Ratio C1).
- No change to `_ranking.py`, `TrackerResult` ranking, `resolve_source` logic, or the
  triage packages' internals. cross-seed and the Watcher plug in.
- No qBittorrent `sync/maindata` delta API (W1) — poll is enough at this scale.
- No O2 obligation _enforcement_ (recording only; enforcement ships with O2).
- No Web UI — but `watch-now`'s sentinel channel is designed as its future entry point.
- No `asyncio` — synchronous loop with injected clock/sleep (house style).

## Risks

- **Vacuous algo tests** (project memory: parser/API code passes `make check` while
  hiding real bugs — bencode/qBit edge cases). **Mitigation**: golden fixtures from
  **real** `.torrent` files + adversarial pr-review + re-reproduce the parse before
  merge. No synthetic-only fixtures. #1 risk for RP10a.
- **Tracker policy** — not all private trackers permit automated cross-seeding.
  **Mitigation**: per-tracker **opt-in** (D9); each confirmed cross-seed writes an
  obligation honored by future O2.
- **Snatch-storm on the back-catalog sweep** — **Mitigation**: throttle (quota/day +
  delay + exclude-recent), persisted; per-completion is targeted (one search).
- **Recheck false positive/negative** — handled by D10 (remove, no obligation). Renamed
  root → not matched in v1 (D11), not a false seed.
- **BitTorrent v2/hybrid** — different piece structure → detect `meta version`, skip in
  v1 (documented limitation).
- **qBit auth lockout vs daemon** — a reconnect loop that rebuilds the client per cycle
  could trip the 1 h lockout (designed against cron retry storms). **Mitigation**: build
  the listing client once, catch `TORRENT_LISTING_ERRORS` per poll, re-login only on
  auth failure, honor the lockout file (skip cycles while locked out).
- **Lock starvation / run storms** — W6 requeue + W7 exponential backoff; the daemon
  never holds `pipeline.lock` itself, so manual CLI and future Web UI always contend
  fairly.
- **Daemon longevity** — subprocess model (W5) keeps the daemon tiny and each run's
  memory fresh; PM2 restarts on crash; SIGTERM handling never orphans a spawned run
  (spawned run owns the lock and its own healthcheck pings).
- **PM2 + pyenv interpreter** — `interpreter: 'none'` + absolute script path resolution
  needed so PM2 finds the pyenv-shim `personalscraper` entry point; document in
  ecosystem file comments.
- **Concurrency** — Watcher fires several completions in parallel → `acquire.db`
  BEGIN IMMEDIATE serializes obligation writes + the quota counter; `add`/`inject`
  idempotent (Conflict409); one `cross-seed --hash` subprocess at a time (daemon
  serializes its spawns).
- **Overlay drift** — add config to **both** `config/` and `config.example/`.

## Testing strategy

- **RP10a (parser + matcher)** — golden fixtures of real `.torrent` files (single-file,
  multi-file, nested dirs, varied `piece_length`); assert file-list/sizes/`piece_length`
  exactly. Adversarial: malformed bencode, deep nesting (existing 100-level guard),
  missing keys, **v2/hybrid**. `structural_match`: positives + negatives
  (`piece_length` ≠, extra file, renamed root → no-match); deterministic/symmetric.
- **RP10b (inject)** — integration vs a mocked qBit client: `savepath` =
  source.save_path, `skip_checking=false`, recheck called, paused→resume, Conflict409
  idempotent; `isinstance(TorrentInjector)` gating → Transmission skips.
- **WatcherService** — pure unit tests of every state transition with injected clock:
  debounce open/extend/expire, safety-net firing, sentinel bypass, lock-held requeue,
  anti-storm backoff, SEED_PURE exclusion from the predicate. Zero real sleeps.
- **watch loop (integration)** — fake qBit client + stub subprocess runner: completions
  → cross-seed spawns + debounced run spawn; poll error → cycle skipped; SIGTERM →
  graceful; sentinel file consumed exactly once.
- **X1/X2** — fakes for registry/transports/torrent-client: happy path (1 match →
  inject + tag + obligation **after recheck OK**), no-match, candidate fetch 401 (RP7)
  fail-soft, origin tracker excluded, recheck-fails → remove without obligation,
  idempotent re-run; sweep: quota exhausted stops, delay respected, exclude-recent
  persisted cross-run.
- **E2E roundtrip** — fixture `complete/` + fake trackers → sweep → assert injections
  tagged `SEED_PURE` + obligations written + **ingest skips them** + Watcher predicate
  ignores them.
- **Regression test per bug** (project rule).

## ACCEPTANCE criteria (executable; SH-16)

ACC-1 — RP10a parses a real `.torrent` file-list + piece_length:

```bash
python -m pytest tests/unit/test_torrent_layout.py -q
# Expected: N passed, 0 failed (file-list/sizes/piece_length asserted on real fixtures)
```

ACC-2 — `structural_match` rejects a piece_length mismatch and a renamed root:

```bash
python -m pytest tests/unit/test_structural_match.py -q
# Expected: N passed, 0 failed (negatives asserted: piece_length≠, extra file, renamed root)
```

ACC-3 — `TorrentInjector` protocol exists and qBit composes it; Transmission does not:

```bash
python -c "from personalscraper.api.torrent._contracts import TorrentInjector; from personalscraper.api.torrent.qbittorrent import QBitClient; print(hasattr(QBitClient,'inject') and hasattr(QBitClient,'list_files'))"
# Expected: True
```

ACC-4 — per-tracker `cross_seed` gate exists and defaults off (both overlays):

```bash
python -c "from personalscraper.conf.models.api_config import TrackerProviderConfig; print(TrackerProviderConfig().cross_seed)"
# Expected: False
grep -c 'cross_seed' config/tracker.json5 config.example/tracker.json5
# Expected: each file ≥ 1
```

ACC-5 — the CLI sweep + single-hash commands are registered:

```bash
personalscraper cross-seed --help >/dev/null 2>&1 && echo OK
# Expected: OK (with --sweep and --hash options documented)
```

ACC-6 — a confirmed cross-seed is tagged SEED_PURE and writes an obligation:

```bash
python -m pytest tests/integration/acquire/test_cross_seed_service.py -q
# Expected: N passed, 0 failed (inject→recheck OK→tag SEED_PURE + SeedObligation; recheck-fails→no obligation)
```

ACC-7 — ingest skips a SEED_PURE cross-seed injection (roundtrip):

```bash
python -m pytest tests/e2e -q -k cross_seed -m e2e
# Expected: N passed, 0 failed (injected cross-seed is skipped by ingest)
```

ACC-8 — the Watcher CLI commands are registered:

```bash
personalscraper watch --help >/dev/null 2>&1 && personalscraper watch-now --help >/dev/null 2>&1 && echo OK
# Expected: OK
```

ACC-9 — `watch-now` writes the sentinel the daemon consumes:

```bash
python -m pytest tests/integration/acquire/test_watcher_loop.py -q -k sentinel
# Expected: N passed, 0 failed (sentinel written by watch-now, consumed exactly once by the loop)
```

ACC-10 — WatcherService state machine fully covered (debounce, safety-net, backoff):

```bash
python -m pytest tests/unit/test_watcher_service.py -q
# Expected: N passed, 0 failed
```

ACC-11 — `run --no-console` exists (Rich off, Telegram on):

```bash
personalscraper run --help 2>&1 | grep -c 'no-console'
# Expected: ≥ 1
```

ACC-12 — launchd machinery is gone and PM2 ecosystem ships:

```bash
ls com.personalscraper.pipeline.plist.template scripts/install-launchd.sh scripts/uninstall-launchd.sh launchd-plists 2>&1 | grep -c 'No such file'
# Expected: 4
test -f ecosystem.config.js && echo OK
# Expected: OK
```

ACC-13 — full suite green:

```bash
make test 2>&1 | tail -1
# Expected: "NNNN passed" with 0 failed / 0 errors
```
