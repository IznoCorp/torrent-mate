# ROADMAP — TorrentMate

> **Status (2026-08-16)** — Waves 1-4 **delivered** (acquisition foundation RP1-RP10, Follow D1-D3, Watcher, Cross-Seed X1, O1, Torr9, E2, ArchiCleanup, TrackersSpike). Since the previous stamp (2026-07-04, 0.77.0): **Web UI S1–S7 all shipped** (tm-shell #158 through acq-watch #186, plus later UX overhaul waves), **Seed Safety O4 shipped** (seed-caps #382), **Verify V1+V2 shipped** (check-plugins #33). Still open: Ratio C1-C3, Seed Safety O2-O3, Verify V3, Cross-Seed X2, digitalcore, Follow D4, E1, RP8/RP-layer, wave-7 stretch (Active Health, Hot-Swap, LLM). Tracked 1:1 on the KanbanMate board (GitHub Project #4). Partial: O2 (RP3 plumbing done, seedtime policy pending). Code version at resync: 0.97.11. LaCale: **removed entirely** (rm-lacale #156, 0.77.0 — the "deprecation" scope was changed to complete removal by the operator).

> **Current mission (2026-08-16)** — the active work is the shell-mobile v1 redesign, tracked in `IMPLEMENTATION.md` at the repo root (which this roadmap predates). The vo-title fix (#435/#436) shipped.

> Future ideas. Each item goes through its own brainstorming before implementation.
> **Priority**: **P1** (high — unblocks, do early) → **P3** (stretch).
> **Wave**: dependency-correct build order (see "Construction plan").
> **Shipped work is not tracked here** — see `CHANGELOG.md` and `docs/archive/features/`.
> Restructured on **2026-06-01** (trackers/ratio/follow brainstorm + refacto-prep,
> multi-agent analysis). `lib-fold` already shipped → removed.

> ⚠️ **Code references are dated HINTS (mostly 2026-06-01; statuses resynced 2026-08-16), not
> contracts.** Paths, method/class names, described capabilities, "shipped" mentions: the code
> evolves. Re-verify the actual state **when picking up a wave** and update the entry concerned.
> This roadmap describes the **intent** (what / why), not the design.

---

## 🎯 Vision — the closed loop

Self-hosted system running as a **closed loop**:

```
ACQUIRE ──▶ TRIAGE ──▶ STORE & INDEX ──▶ SEED / RATIO ──▶ SUPERVISE
(series follow    (existing rename/    (disks +          (healthy ratio on  (Web UI +
 + auto-download   clean/scrape/        indexer DB)       private trackers)  Telegram)
 private trackers) dispatch pipeline)                                        │
        ▲──────────────────────────────────────────────────────────────────┘
```

The new features (acquisition, ratio, seed-safety) all rest on **a shared foundation**: a
**download core** (RP5) on top of a torrent client able to **add** and **tag** (RP1), a
**per-tracker config** (RP2), an **acquisition persistence** (RP3) and an **event catalog**
(RP4). We lay these foundations before anything else.

---

## 🏛 Target architecture (intent)

> What the roadmap **converges** toward. Intent level — **not a design**. Each item serves this
> target rather than piling up. (From the multi-agent architecture review, 2026-06-02.)

- **A top-level `acquire/` lobe** — peer package of `ingest`/`sort`/`dispatch`/`indexer`,
  home of the orchestrator, the acquisition service, Follow, Ratio, Seed-Safety and the Watcher.
  It depends **downward** on the `api/` ports (tracker, torrent, transport) + its own
  `acquire.db` store, and **never imports** the triage packages.
- **A single triage ↔ acquisition seam** — all contact reduces to the **seed-pure /
  useful-content tag** (`tags` field, RP1): acquisition writes it, triage reads it and skips, the
  Watcher (which replaces the 3-hour cron) consumes the same contract. No other coupling.
- **Partitioned state, single authorities** — `library.db` remains the **single-writer** authority
  of the _owned_ (read SELECT-only across the boundary via the ownership predicate, RP6);
  `acquire.db` owns the _desired / obligation_ under its own single-writer discipline. **One
  single** free-space authority, read by dispatch (de-facto owner), maintenance and the O3 arbiter.
- **Single composition root** — one single application-context construction site, extended with **one**
  acquisition handle (+ the tracker registry), never N fields (otherwise the frozen context drifts
  into a service locator).
- **Direct control, observe-only EventBus** — acquisition orchestrates itself through direct
  top-down calls; the EventBus carries **one** event catalog that SUPERVISE (Telegram + Web UI
  read-models) consumes; Web UI write actions go through the **same trigger authority**
  (pipeline lock) as the Watcher.
- **Guaranteed import direction** — the layering guardrail is extended to enforce that `acquire/`
  depends downward, never the reverse (RP-layer).

---

## 🧊 Frozen decisions (brainstorm 2026-06-01)

| #           | Decision                                    | Choice                                                                                                                                                                                                                                                          |
| ----------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Q1**      | "New episode" detection (series follow)     | **Calendar-trigger**: we poll air dates (TVDB/TMDB) → once the air date has passed, the episode enters a `wanted` queue → **repeated** search on the trackers until it is found (trackers lag behind the broadcast).                                             |
| **cadence** | Search frequency for `wanted` items         | **Tiered backoff, configurable** (global default + per-series override): 🔥 Hot 0–72 h → ~every 2 h; 🌤 Warm 3–14 d → 1×/day; ❄️ Cold 14–30 d → 1×/week; ⛔ 30-day cutoff → stop + Telegram notification.                                                          |
| **Q2**      | Per-tracker ratio measurement               | **Cascade**: tracker API endpoint first **→ fallback to local qBittorrent aggregation** (sum up/down per host) if the tracker does not expose its ratio. Registry-style capability detection.                                                                    |
| **Q3**      | Tracker sequencing + freeleech radar        | **API study spike → torr9 → digitalcore**. Freeleech radar **R1 conditional**: only if a tracker exposes a window-enumeration API; otherwise R1 reduces to harvest-by-search (already shipped).                                                                  |
| **Q4**      | `.torrent` download boundary                | **PersonalScraper fetch + POST**: we download the `.torrent` (auth handled) then POST the file to qBittorrent; **magnet exception** for links without auth. The 401 stays observable/routable (vs qBit, which cannot re-authenticate an expired token).          |

---

## 🗺️ Construction plan — 7 waves

Dependency-correct execution index. `RPx` = refacto-prep (see dedicated section); the codes
`Sx/Dx/Ox/Vx/Cx/R1` = sub-features (see catalogue). Rich detail in the **Catalogue** below.

### Wave 1 — Leaves + foundation kickoff

- **RP1** `[DONE — feat/torrent-write]` — torrent write protocol (add/category/limit) + tags on the torrent item + Transmission fail-fast. **Pin Q4 here.**
- **RP1a** `[DONE — feat/torrent-fetch]` — fetch boundary (PersonalScraper fetch+POST, magnet exception).
- **RP2** `[DONE — feat/tracker-economy]` — per-tracker economy config (ratio policy + announce secret); **strikes the "no new config schema" non-goal**.
- **Name-keyed matching E1** `[P2]` — catch-up by name when the episode number is absent (mode 1) + non-blocking flag when name/number frankly diverge, the number remaining the key (mode 2). Lightweight, inside triage.
- **architecture.md Multi-Filesystem cleanup** `[DONE — feat/arch-cleanup]` — dead pointer (shipped).

### Wave 2 — Persistence / events + composition root + `acquire/` package + supervision shell

- **RP3** `[DONE — feat/acquire-store]` — `acquire.db` store (separate from `library.db`): followed series + `wanted` + obligations + ratio state; partitioned single-writer; _fail-open_ deletion authority (who decides vs who executes).
- **RP3a** `[DONE — feat/acquire-store]` — shared **"desired item"** domain model (Follow/Ratio/Renewal/E2), the orchestrator's input contract. Lives in `acquire/`.
- **RP4** `[DONE — feat/acquire-events]` — acquisition event catalog + Telegram subscriber (silent); **register the producing module in the eager-import hub**.
- **RP5a** `[DONE — feat/tracker-wiring]` — wire the tracker registry into the composition root + **config-driven factory + boot validation** at parity with metadata.
- **LaCale Deprecation** `[DONE — refactor/rm-lacale (#156), 0.77.0]` — scope changed by the operator: deprecation → **complete removal** (la-cale.space is dead). Executable zero-remanence proofs (lacale + torr9): `docs/archive/features/rm-lacale/ACCEPTANCE.md`.
- **RP5c** `[DONE — feat/acquire-lobe]` — top-level **`acquire/`** package (home of orchestrator/Follow/Ratio/Seed-Safety/Watcher) + **one single handle** at the composition root.
- **RP-layer** `[P2, parallel]` — extend the layering guardrail for the import direction of `acquire/`.
- **Web UI S1** `[DONE — feat/tm-shell (#158)]` — shell + auth + WebSocket + headless container.
- **Verify V1** `[DONE — feat/check-plugins (#33)]` — check registry + 2 protocols (pre-dispatch check on a path + library-row check).
- **Additional Trackers — spike** `[DONE — docs/reference/*-api.md]` — API study (Q3), depends on RP2 only.

### Wave 3 — The "grab" core + the guardrail

- **RP5b** `[DONE — feat/grab-core]` — shared grab core (orchestrator + acquisition service) on top of RP5a. **Gate of the epic.** Contains the **pre-ranking cross-tracker dedup** stage.
- **Seed Safety O1** `[DONE — feat/seed-pure]` — "seed-pure" tag + skip through `ingest`/`sort`/`process`; **defines the skip contract the Watcher (wave 4) will consume**.
- **Seed Safety O2** `[P2, re-scoped]` — seed obligation policy: relocate-not-delete on unmet seed obligation (requires the O3 disk-budget arbiter, Wave 5). The first plumbing (persisted obligation table + permit consulted by deleters) was absorbed into RP3 (`acquire-store`).
- **RP6** `[DONE — feat/ownership]` — "I already own it" predicate in the indexer's query layer.
- **RP7** `[DONE — feat/tracker-auth]` — tracker auth lifecycle + grab freshness (auth-failure event).
- **RP9** `[DONE — feat/airing]` — capability to poll air dates over a _set_ (after Q1).
- **RP10** `[DONE — feat/watch-seed (#212)]` — shared **structural-match + inject** engine (RP10a `.torrent` parser/comparator · RP10b `inject` capability + `TorrentInjector` protocol). Lays the ground for **Cross-Seed (X1/X2, wave 5)**; reusable by E2.
- **Additional Trackers — torr9** `[DONE — feat/torr9 (#209)]` — first tracker, after RP7 (auth).
  - **Status** `[DONE — feat/torr9 merged #209, 0.37.0]`: design+plan on the branch (docs/archive/features/torr9/), API captured live (JSON+JWT search, RSS freeleech radar) — doc docs/reference/torr9-api.md, fixtures docs/reference/_samples/torr9/.

- **Freeleech R1** `[P3, conditional]` — window discovery (only if an enumeration API exists; otherwise harvest-by-search).

### Wave 4 — Headline acquisition + supervision trigger

- **Follow D1** `[DONE — feat/follow-list]` — store + CRUD of the followed list (`personalscraper follow add/list/remove`).
- **Follow D2** `[DONE — feat/airing + feat/ownership]` — calendar-first detection (RP9) + `wanted` queue + backoff cadence + ownership (RP6) (`personalscraper follow detect`).
- **Follow D3** `[DONE — feat/grab-title-resolution (#214)]` — grab via the shared core (RP5b). The remaining blocker was the **wanted→title resolution**: `build_search_query` builds `"{title} SxxEyy"` (store-backed resolver injected) instead of the numeric ID, + `filter_to_episode` (exact-episode before ranking). Cross-tracker dedup + resolve_source + fetch already provided by RP5b. Validated for real (grab downloads the right episodes of followed series) + scheduled under PM2 (`follow-detect` + `grab`).
- **Watcher Service** `[DONE — feat/watch-seed (#212)]` — replaces the cron; decommissions launchd + PM2 `personalscraper-watch`; consumes O1's seed-pure skip contract; single trigger authority (pipeline lock).

### Wave 5 — Ratio policy + the rest of the orchestration

- **Ratio C1** `[P3]` — per-tracker measurement (Q2: API→qBit fallback, reads RP2's per-tracker ceiling) + grab loop toward the target.
- **Seed Safety O3** `[P2]` — global disk-budget arbiter (**precedence: real media wins**). **One single** free-space authority read by dispatch (de-facto owner) / maintenance / O3 — not three computations. Precedes C2.
- **Ratio C2** `[P3]` — rotation/LRU (respects O2, bounded by O3).
- **Ratio C3** `[P3]` — hybrid "useful content" mode (tagged via O1).
- **Seed Safety O4** `[DONE — feat/seed-caps (#382)]` — events + bandwidth caps (per torrent **and** global).
- **Verify V2** `[DONE — feat/check-plugins (#33)]` — granular CLI (`verify --check nfo_validity`).
- **Name-keyed correction E2** `[DONE — feat/rescrape-target]` — name-keyed re-scrape from the original download (re-downloaded if gone) when bad numbering is observed in Plex. Depends on the grab core (RP5b) + trackers.
- **Additional Trackers — digitalcore** `[P2]` — second tracker (after torr9).
- **Cross-Seed X1** `[DONE — feat/watch-seed (#212)]` — `CrossSeedService` (`acquire/` lobe): per-completion via the **Watcher** + per-tracker `cross_seed` gate (RP2) + strict structural match (RP10a) + inject onto existing data + recheck (RP10b) + `SEED_PURE` tag (O1) + `SeedObligation` after recheck (RP3, O2 policy). On top of **RP10**. Validated for real (inject on Murder.Mindfully.S01, recheck 100%, c411 obligation).
- **Cross-Seed X2** `[P2]` — back-catalog sweep + throttle (quota/day, delay, recent-exclusion, persisted in `acquire.db`).

### Wave 6 — Supervision surfaces over the now-living acquisition

- **Web UI S2** `[DONE — feat/pipe-control (#227)]` — pipeline control + logs + history.
- **Web UI S3** `[DONE — feat/maint-dash (#228)]` — maintenance dashboard.
- **Web UI S4** `[DONE — feat/config-editor (#230)]` — config editor. (Historical note: "safe reload" depended on a reload that only existed for the providers config (RP8, wave 7) — either bound S4 to that perimeter, or anticipate a wider reload seam.)
- **Web UI S5** `[DONE — feat/scrape-arbiter (#184)]` — interactive scraping. (Historical note: required a **pause/resume-on-human-decision** seam the batch pipeline did not have — anticipated as a structural prerequisite.)
- **Web UI S6** `[DONE — feat/reg-health (#185)]` — registry + health (**merges Registry Consumer**); includes **S6.0 — freeze the registry status as additive-only BEFORE exposing the panel**.
- **Web UI S7** `[DONE — feat/acq-watch (#186)]` — acquisition/watcher pages (on the RP4 events).
- **Verify V3** `[P2]` — Web UI panel per check (on V1).

### Wave 7 — Registry deferrals + debt + stretch

- **RP8** `[P3, prerequisite]` — single live re-prioritization primitive (drain + atomic swap).
- **Active Health Scoring — network core** `[P3]` — on top of RP8.
- **Active Health Scoring — ratio slice** `[P3]` — reads the Ratio state (after C1).
- **Hot-Swap Provider Config** `[P3]` — on top of RP8.
- **Tech-Debt Round 2** `[P3]`.
  - **Full TV-scrape unification (option B)** — extract a shared "scrape a TV show" core (match + provider resolution + title resolution) that `tv_service`, the maintenance rescraper AND `existing_validator` instantiate. The source-aware fetch _slice_ (`fetch_show_data` in `_tvdb_convert.py`) was already unified in **torrent-write phase 17** (fix of the TVDB-only 404 bug: the rescraper fed a TVDB id to `tmdb.get_tv` → 404 → abort). Remains to de-duplicate `_lookup_series` (match + title-resolve), still copied across the three. Big multi-file refactor touching the pipeline's scrape path (~6000 tests) → **dedicated feature, not a fix**. The remaining duplication is the root cause of this bug class.
- **Follow D4** `[P2→P3]` — per-criterion override rules + per-series quality profiles + cron.
- **Library renewal** `[P3]` — auto-download trigger sourced from the recommendations.
- **LLM Pipeline Assistant** `[P3]`.

---

## 🧱 Refacto-prep (ground preparation)

> New **ground-preparation** features, motivated by gaps **observed** in the code (dated hints,
> to re-verify). We lay them before the acquisition features so we do not build on sand.

| Code         | Prio | Type         | What (intent)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Prepares                                                 |
| ------------ | ---- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| **RP1**      | P1   | prerequisite | `[DONE — feat/torrent-write]` The torrent client can drive an existing torrent (pause/resume/delete, seed state) but **cannot ADD one**. The item model already carries a category but **no tags**. Add a **write protocol** (add + categorization + limits) + a tags field; the Transmission client must **refuse to start if it cannot add** (fail-fast). Pin Q4.                                                                                                                                                                                                                                     | Orchestration, Follow, Ratio, Watcher, Trackers          |
| **RP1a**     | P1   | prerequisite | `[DONE — feat/torrent-fetch]` Some trackers require auth to fetch the `.torrent` → if qBittorrent fetches it itself it can hit a 401. PersonalScraper fetches the `.torrent` (auth handled) then POSTs the file; **magnet exception** (link without auth).                                                                                                                                                                                                                                                                                                                                              | Follow, Ratio, Orchestration                             |
| **RP2**      | P1   | parallel     | `[DONE — feat/tracker-economy]` The per-tracker config today only carries **activation**. Add the **per-tracker economy** (ratio policy + announce secret/passkey) **before torr9/digitalcore**. The Additional Trackers non-goal "no new config schema" is **struck**.                                                                                                                                                                                                                                                                                                                                 | Ratio, Trackers, Follow, Orchestration                   |
| **RP3**      | P1   | parallel     | `[DONE — feat/acquire-store (0.26.0)]` Delivered: `core/sqlite/` extraction, `MediaRef`, `AcquireConfig`, 4-table `acquire.db`, `ConcreteAcquireStore` (lazy/lock-free), `DeletePermit`/`SeedObligationRecorder`, `DeleteAuthority` (resolver + `record_dispatch`), per-site wiring (dispatch 3-state + `disk_cleaner` hard-skip). Absorbs the first O2 plumbing (persisted obligation table + permit consulted by deleters). See the O2 re-scope below.                                                                                                                                                 | Follow, Orchestration, Ratio                             |
| **RP3a**     | P2   | prerequisite | `[DONE — feat/acquire-store]` Name **once** the shared **"desired item" domain model** (episode/movie/release + quality profile + source criteria; followed series; `wanted` entry; seed obligation), reused by Follow, Ratio, Renewal and E2, and consumed as the **orchestrator's input contract** (RP5b). Prevents each feature from reinventing "the thing I want" (same trap as the scattered events). Lives in `acquire/`. Shared vocabulary, no schema.                                                                                                                                            | Follow, Ratio, Renewal, E2                               |
| **RP4**      | P1   | parallel     | `[DONE — feat/acquire-events]` No acquisition event exists today. Define them **once** (single catalog) + one Telegram subscriber, silent until waves 4–5. ⚠️ The producing module must be **registered in the events eager-import hub** (+ catalog counter), otherwise the envelope round-trip silently drops cross-process / Web UI events (breaks S7 + Telegram).                                                                                                                                                                                                                                     | Orchestration, Freeleech, Watcher, Follow, Ratio, Web UI |
| **RP5a**     | P1   | prerequisite | `[DONE — feat/tracker-wiring]` The tracker registry exists but **is not wired into the runtime application context**. Wire it; **absorbs the need for an injection container** (the context carries the registry). ⚠️ Wiring also requires **config-driven construction + boot validation at parity** with the metadata registry (today the constructor takes a pre-built dict; neither factory nor validation on the tracker side) — to avoid a second divergent path. Prerequisite of RP5b.                                                                                                             | RP5b, Follow, Ratio, Watcher                             |
| **RP5b**     | P1   | prerequisite | `[DONE — feat/grab-core]` No **shared grab core**. Create a **download orchestrator + acquisition service** on top of RP5a, **inside the `acquire/` package** (RP5c). **Gate of the epic** — Ratio C1 and Follow D3 share this core. Contains the **pre-ranking cross-tracker dedup** stage (that is the orchestrator's job; D3 merely refers to it).                                                                                                                                                                                                                                                    | Orchestration, Follow, Ratio, Watcher                    |
| **RP5c**     | P1   | prerequisite | `[DONE — feat/acquire-lobe]` **Give the acquisition lobe a home + an injection seam**: a top-level **`acquire/` package** (peer of ingest/sort/dispatch/indexer) hosting the orchestrator, acquisition service, Follow, Ratio, Seed-Safety, Watcher; depends on the `api/` ports + `acquire.db`, **never** on triage. Injected at the single composition root via **one single handle** (not N fields → the frozen AppContext does not drift into a service locator). Extends RP5a beyond the registry alone. Intent, not a class layout.                                                                 | Orchestration, Follow, Ratio, Seed-Safety, Watcher       |
| **RP6**      | P2   | parallel     | `[DONE — feat/ownership]` "I already own it" predicate undefined. Add it in the **indexer's query layer** (NOT in the movies service, already too big — see Tech-Debt Round 2).                                                                                                                                                                                                                                                                                                                                                                                                                        | Follow, Ratio                                            |
| **RP7**      | P2   | parallel     | `[DONE — feat/tracker-auth]` Short-lived auth tokens; the circuit breaker does not react to 4xx. **Re-resolve the URL right before adding** the torrent, and emit a **tracker auth-failure event**. With RP1a the 401 is observable.                                                                                                                                                                                                                                                                                                                                                                   | Follow, Ratio, Trackers, Active Health                   |
| **RP8**      | P3   | prerequisite | Hot-Swap **and** Active Health both want to **mutate the chain order live**: one single **safe primitive** (drain + atomic swap).                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Active Health, Hot-Swap                                  |
| **RP9**      | P2   | prerequisite | `[DONE — feat/airing]` Today the episode fetch happens **series by series**; polling air dates over a **SET** of series is a new capability to add. Resolve Q1 first.                                                                                                                                                                                                                                                                                                                                                                                                                                  | Follow                                                   |
| **RP-layer** | P2   | parallel     | When `acquire/` lands, **extend the layering guardrail** to enforce its import direction: `acquire/` → down (`api`/`core`/`conf` + `acquire.db`), **never** the reverse; the pipeline composes it, it does not import the pipeline. (Incidentally, the current enumeration omits `insights`/`maintenance`/`enforce`/`process`.) State the invariant, not the test.                                                                                                                                                                                                                                       | acquire/ (the whole lobe)                                |
| **RP10**     | P2   | prerequisite | `[DONE — feat/watch-seed (#212)]` No capability for **injection onto existing data** nor for **introspecting a .torrent's tree**. Add a shared **structural-match + inject engine**: (a) RP10a — extract the file list + `piece_length` from a .torrent (extends the `_bencode_info_hash` bencode parser) + a pure structural comparator; (b) RP10b — an `inject` capability (savepath→existing data + recheck + `list_files`) on the torrent write protocol, guarded by a `TorrentInjector` protocol (Transmission opt-out). **Net-new** cross-seed bricks, reusable (E2).                               | Cross-Seed (X1/X2), E2                                   |

---

## 📦 Feature catalogue (detail)

### — Acquisition —

#### TVShow Follow & Auto-Download System (D1–D4)

> Reworked 2026-06-01: the **series follow** is the headline feature; the former
> "Auto-Download System" (subscription + multi-tracker search) **merges into it** as
> facets. Split into 4 sub-features (+ the library renewal pulled out as a standalone item).

Automatic download of new episodes / seasons of the series on a **followed list**,
searching **all active trackers**, picking the **best torrent** (hard filters + score).

- **D1 — List + CRUD**: store of followed series, **manual list** (add/remove),
  independent of the library — you can follow a series you do not own yet.
- **D2 — Detection**: **calendar-first** (Q1) — we poll the air dates → `wanted` queue →
  repeated tracker search following the **backoff cadence** (Hot/Warm/Cold/cutoff, configurable
  globally + per series). Ownership via RP6 (do not search for what we already own).
- **D3 — Grab (shared core)**: via the grab core (RP5b).
  - **Hard filters (eliminatory)**: required audio track (VF/VOSTFR), minimum quality (≥1080p)…
  - **Weighted score** on the survivors: seeders, freeleech/tracker economy, source, codec, size.
  - **Cross-tracker dedup BEFORE ranking** (carried by the orchestrator, RP5b): the scoring handles
    one result at a time → we group by `info_hash`, pick the best provenance, and pass
    **one** representative to the ranking stage.
  - URL re-resolution (RP7) + fetch (RP1a) + "useful content" tag (O1) for normal ingestion.
- **D4 — Overrides & profiles**: per-criterion rules (studio, director, franchise, title, IMDB
  ID) + **per-series quality profiles** (VOSTFR anime vs VF series) + cron. (The library
  renewal was pulled out as a standalone item — see below.)

**Depends on**: RP1, RP1a, RP2, RP3, RP5a/RP5b, RP6, RP7, RP9; active trackers; the ranking stage (shipped).

#### Ratio Management Module (C1–C3)

> Downloads the torrents most **conducive to sharing** to raise the ratio,
> **tracker by tracker**. Distinct from Follow (here we download **to seed**) but the modes coexist.
> Stays **P3**: it is **policy** on top of the P2 foundation.

- **C1 — Measurement + loop**: per-tracker ratio in **cascade** (Q2: API endpoint → fallback to
  local qBit aggregation). Grab loop while `ratio < target` **and** `disk < ceiling`
  (per-tracker config via RP2).
- **C2 — Rotation/LRU**: never delete before the **minimum seedtime** (O2 policy), then
  **LRU rotation by profitability** when the quota is full, bounded by the disk arbiter (O3).
- **C3 — Useful-content hybrid**: if a torrent with a good swarm matches wanted content
  (wishlist/library, via RP6), we **keep** it (tagged "useful content" via O1) instead of discarding it.

"Conducive to sharing" criteria: freeleech (priority, see R1), seeders/leechers ratio, size,
freshness, swarm velocity.

**Depends on**: RP1, RP1a, RP2, RP3, RP5a/RP5b, RP6; Seed Safety O1/O2/O3; Freeleech R1 (bonus); the ranking stage.

#### Cross-Seed Module (X1-X2)

> Seeds the **identical release** already owned (qBit's `complete/` copy) on the **other
> managed trackers**, at zero download cost. Distinct from Ratio (which downloads **new** material
> to seed); same SEED lobe. **Native** build (replaces Prowlarr/Jackett/autobrr — closed-loop vision).
> Design prepared: `docs/superpowers/roadmap/cross-seed/specs/DESIGN.md` (decisions D1–D11 frozen 2026-06-19).

- **X1 — Service + per-completion**: `CrossSeedService` (`acquire/` lobe) triggered by the **Watcher**
  on each completion; search **by name** on the managed trackers (origin excluded, opt-in `cross_seed`
  gate), **strict structural match** (tree + sizes + `piece_length`, RP10a), **inject** onto the
  existing data + recheck (RP10b), then `SEED_PURE` tag (O1) + `SeedObligation` **after recheck
  confirmation** (RP3, O2 policy). **No linking in v1** (renamed release = deferred).
- **X2 — Back-catalog sweep + throttle**: retroactive sweep of all of `complete/`, throttled
  (quota/day + delay + exclusion of recently-searched, persisted in `acquire.db`) to respect
  private-tracker etiquette.

**Net-new**: RP10 (match+inject engine) + the thin orchestration. **Everything else = dependencies** on
already-planned bricks.
**Depends on**: **Watcher** (W4, trigger) · **O1** (W3, shipped) · **O2** (W3→5, enforcement) · **RP2** (W1,
`cross_seed` gate) · **RP3** (✅, obligations) · **RP5b** (search/resolve/registry) · **RP7** (W3, auth fetch)
· **RP10** (new). → **Wave 5**, sibling of Ratio C1-C3.
**Non-goals**: Prowlarr/Jackett/autobrr; cross-seed from staging/library; fuzzy/partial matching; linking (v1).

#### Download Orchestration & Seed Safety (O1–O4)

> **Shared layer** (P2) between the downloading modules and the torrent client / triage.
> Without it, seed-pure would pollute the library and seed obligations would be violated.

- **O1 — "Seed-pure" tag + skip**: marking carried by the item model (category + tags, via
  RP1); **skip at every pipeline stage** (`ingest`/`sort`/`process`). **Defines the skip
  contract the Watcher will consume** (wave 4). "Useful content" grabs are on the contrary
  tagged for normal ingestion. **Anti-library-pollution guardrail.**
- **O2 — Seed obligation / anti-HnR** (re-scoped 2026-06-10): the first plumbing (persisted
  obligation table + delete permit consulted by deleters) was absorbed into RP3
  (`acquire-store` 0.26.0). O2 now carries only the **policy refinement** —
  relocate-not-delete on an unmet seed obligation (depends on the O3 disk-budget
  arbiter, Wave 5). No module deletes/stops a torrent before the tracker's minimum
  seedtime (avoids HnR penalties).
- **O3 — Global disk-budget arbiter**: enforces the quotas (including C1's per-tracker
  ceiling); **precedence: real-media dispatch always wins**, the arbiter only reserves the
  unclaimed space; **one single free-space authority** that dispatch (**de-facto owner
  today**), maintenance and the arbiter read — the arbiter does not duplicate the computation nor
  reaches into dispatch's disk internals. Connected to the maintenance subsystem.
- **O4 — Events + caps** `[DONE — feat/seed-caps (#382)]`: download events (via RP4) + **bandwidth caps per torrent
  AND global**.

**Depends on**: RP1, RP3, RP4; torrent client (qBittorrent); Telegram notifier; maintenance subsystem (shipped).
**Frames/blocks**: Watcher, Ratio, TVShow Follow.

#### Additional Trackers (spike → torr9 → digitalcore)

> Raised P3 → P2 on 2026-06-01 (LaCale falls → need for active sources). Sequencing Q3.

Implement two new tracker providers following the existing tracker-client protocol,
on the unified HTTP transport infrastructure. **API study spike first** (Torznab/RSS/REST, real
samples, one reference doc per tracker), **then torr9, then digitalcore**.

- Two providers plug-compatible with the tracker registry + the ranking engine.
- Capture the per-tracker economy (freeleech, bonus, minimum seedtime, passkey) → **via the RP2 schema**.
- Activation via the existing provider-activation mechanism.
- Detect whether the tracker exposes a **freeleech window-enumeration API** → gates R1 (Q3).

**Non-goals**: new ranking criteria (the engine already supports them).
**Depends on**: RP2 (config schema), RP7 (auth). ⚠️ The former "no new config schema" non-goal is **struck** (RP2).
**Order**: spike in wave 2 (depends on RP2); torr9 in wave 3 (after RP7); digitalcore in wave 5.

#### Freeleech Radar (R1) — conditional

> **Transverse** module shared by Ratio and Follow. **The per-result plumbing is already
> shipped** (freeleech marker + ranking bonus). The only net-new = the **proactive window
> discovery**.

- **R1**: freeleech-window event + window discovery — **only if ≥1 tracker exposes
  an enumeration API** (otherwise R1 reduces to the already-shipped harvest-by-search). Ratio makes
  it its #1 priority (ratio gain at zero cost); Follow uses it as a scoring criterion.

**Depends on**: Additional Trackers (Q3 spike), Event Bus (shipped).

#### Watcher Service

Replaces the cron trigger with a real-time service.

- Watches the qBittorrent state or the `complete/` directory; triggers `personalscraper run`.
- **Ignores torrents tagged "seed-pure"** (consumes the contract defined by O1).
- **Decommission the 3-hour cron at cutover** (otherwise double ingestion) — canonical mention of the cron cadence.
- **Single trigger authority**: Watcher, ex-cron and Web UI actions (S2 start/kill) go through the **same pipeline lock** — no parallel writer.

**Depends on**: Event Bus (shipped), Pipeline Observer Protocol (shipped), Seed Safety O1.

### — Supervise —

#### Web Management UI (S1–S7)

Web interface to drive/supervise the whole project. Split into 7 sub-features.

- **S1** `[DONE — feat/tm-shell (#158)]` — shell + auth + WebSocket + headless container (**to build first**).
- **S2** `[DONE — feat/pipe-control (#227)]` — pipeline control: start/pause/resume/kill (`ingest`/`sort`/`process`/`dispatch`), live logs, status, history.
- **S3** `[DONE — feat/maint-dash (#228)]` — maintenance dashboard: disk/free space per disk, orphans (temporary prefix), locks, index health, run history.
- **S4** `[DONE — feat/config-editor (#230)]` — visual config editor with schema validation + safe reload. (Historical note: the "safe reload" depended on a reload mechanism that at the time only existed for the providers config (RP8, wave 7): either S4 bounds its reload to that perimeter, or a wider reload seam is anticipated.)
- **S5** `[DONE — feat/scrape-arbiter (#184)]` — interactive scraping: manual decision points (ambiguous TMDB/TVDB matches, multi-result picks, fuzzy arbitration, title/year/season override). (Historical note: required a **pause/resume-on-human-decision** seam the batch pipeline did not have — anticipated as a structural prerequisite.)
- **S6** `[DONE — feat/reg-health (#185)]` — registry + health (**merges the former "Web UI Registry Consumer"**): WebSocket on
  the registry events (fallback / exhaustion / locked capability / fan-out / boot), read REST for
  the registry state and operations, circuit + chain + latency panel.
  - **S6.0** — freeze the registry status as **additive-only BEFORE** exposing the panel (Active
    Health in wave 7 extends it): explicit carrier of this prerequisite.
- **S7** `[DONE — feat/acq-watch (#186)]` — acquisition/watcher pages (status, history, followed-list CRUD, override rules) on the RP4 events.

**Architecture (to settle at design time)**: FastAPI/Flask+HTMX vs SPA+REST/WebSocket; local-only vs basic auth;
reverse-proxy friendly (sub-path behind `iznogoudatall.xyz`). **Out of scope v1**: multi-user, remote agent control, mobile UX.
**Depends on**: Pipeline Observer (shipped), Event Bus (shipped), RP4 (for S7), registry status/operations (shipped, for S6).

### — Quality / platform —

#### Verify Checker Plugin System (V1–V3)

The verify checker is today a **monolithic module**: adding a check means editing
the file. Move it to a **plugin architecture** → testable, extensible checks, discoverable
by the Web UI. Landing zone of the former library validator.

- **V1** `[DONE — feat/check-plugins (#33)]` — check registry + **two protocols**: **pre-dispatch** check (operates on a path)
  and **library-row** check (ex-validator), under one registry. Each existing group
  (e.g.: NFO, artwork, naming, stream, genre, size, video duplicates) becomes a plugin.
- **V2** `[DONE — feat/check-plugins (#33)]` — granular CLI: `personalscraper verify --check nfo_validity`.
- **V3** — Web UI panel per check (list, individual run, results).

**Non-goals**: changing check logic beyond the extraction.

#### Active Health Scoring (Registry) — on top of RP8

Move from the passive circuit breaker to **active health scoring**: background per-provider
monitoring task (periodic check), **sliding average** over N checks, de-prioritization in the chain
below a threshold (retried at the next window); the registry status includes the score. Chain-order
mutation **via the RP8 primitive**.

- **Ratio slice (brainstorm 2026-06-01)**: for tracker providers, factor in the ratio state
  (close to the limit → de-prioritize) **on top of** network health. Fed by Ratio C1 →
  **this slice waits for C1 (wave 5)**.

**Non-goals**: active load-balancing, per-region routing. **Risk**: the health-check budget must be bounded.
**Depends on**: Provider Registry (shipped), **RP8**, RP7; ratio slice ⇐ Ratio C1.

#### Hot-Swap Provider Configuration — on top of RP8

Reload the provider config on SIGHUP / file change **without restarting**.

- File-watcher on the provider config file → validation → if PASS, **atomic swap via RP8**,
  5 s drain, hot-swap event.

**Non-goals**: hot-swap of IMPLEMENTATIONS (config only), distributed config.
**Depends on**: Provider Registry (shipped), config validation (shipped), **RP8**.

#### Episode resolution by name (E1 + E2)

> Reframed 2026-06-02: the former "Reverse Episode Lookup" becomes a feature **integrated into the
> pipeline** (no longer an isolated tool). The **episode name** serves as the key when the number is
> absent or wrong — but **the number remains the default key** and the (noisy: other language,
> misspelled, absent) name **never** overrides it automatically.

Today a TV file without SxxExx is **silently skipped** (it stays loose at the series
root). This feature catches it, and also attacks the cause of mis-numbered series
(scraping sources in disagreement, noticed after the fact in Plex). The episode title is matched
against the episode list **already fetched** from the provider at the decision point (hence lightweight).

**E1 — Name-keyed matching (integrated into triage, lightweight)** — modes 1 & 2:

- **Mode 1 — fallback (number absent)**: match the episode by name against the list already in
  memory (instead of the current skip). Fuzzy + confidence threshold: automatic if clear-cut, otherwise
  we do not invent (skip / flag). The name is the key because it is the only available signal.
- **Mode 2 — corroboration (number + name present)**: **non-blocking, the number remains the key**. If
  the name match is **clear-cut** and **strongly contradicts** the number, we **flag** (warning /
  Verify check / review marker) without ever overriding the number. Goal: spot a probable
  bad numbering early. A weak / foreign / misspelled name is **ignored** (no penalty).

**E2 — Correction via name-keyed re-scrape (manual, heavy)** — mode 3:

- When bad numbering is **observed in Plex**, trigger (per series) a
  **name-keyed re-scrape from the original download**. If the torrent is no longer there, it is
  **re-downloaded** (via the grab core + trackers). The corrected version replaces the bad one
  (TV move rules: merge/replace).
- Reuses the E1 engine. **Depends on the acquisition stack** → lands late (wave 5).
- ⚠️ **Open question (design)**: re-downloading only recovers the names if a
  **title-named** release exists (many only carry SxxExx). To dig at E2 design time.

**E2 trigger**: manual per-series command (the human observes it in Plex). A CLI along the lines of
`resolve-episodes` therefore survives, but wired to the **same engine** (E1) — it is no longer
"outside the pipeline", it shares the integrated logic.

**Depends on**

- **E1**: episode matching + confidence model (shipped) — the episode list is already in
  memory at the decision point; no dependency on the acquisition foundation.
- **E2**: E1 + grab core (RP5b) + active trackers + re-download (RP1/RP1a).

#### Tech-Debt Round 2 (`tech-debt-2`)

> Status (hint 2026-05-28): no acute god-module crisis.

- Extract the **movies service** (the biggest module, close to the hard ceiling) along the dedup/rename/orphan-unlink seam.
- Decide the guardrail policy for `__init__.py` files: the size check excludes them all, which hides a few large package-inits (e.g. metadata registry, indexer scanner).
- Wide sweep: dead code, `TODO`/`FIXME`/`HACK`, `type: ignore`/`pragma: no cover`, broad `except`, magic values, expired skips/`xfail`.

**Non-goals**: behavior changes (structural moves only).

#### architecture.md Multi-Filesystem cleanup `[doc]`

"Multi-Filesystem" section still marked _planned_ even though **already shipped** — the only
remaining dead pointer. Doc cleanup.

#### LLM Pipeline Assistant (idea, kept for last)

Connect an LLM (local/remote) as an arbitration assistant for the human-decision points
(ambiguous matches, error post-mortems, inconsistencies). RAG over the library + user
corrections — never fine-tuning, never autonomous, always under validation. Deliberately simple.

Vision/open questions: `docs/superpowers/roadmap/llm-assistant/brainstorming.md`.
**Brainstorming started** (2026-05-11/12): principles laid out, use cases framed, presumed stack
(MCP + sqlite-vec + Ollama + Open WebUI), 3 open questions. Resume via `/brainstorming`.

#### Library renewal (acquisition trigger)

> Pulled out of Follow D4 on 2026-06-01: it is not an override rule but a **distinct
> acquisition trigger**, sourced from the library recommendations.

Plug the library's **recommendation list** into auto-download to renew /
complete the collection (replace versions, fill gaps). Reuses the grab core (RP5b)
and the ownership predicate (RP6).

**Depends on**: RP5b (grab core), RP6 (ownership), library recommendations (shipped). Reads **P3**.

### — Deprecations —

#### LaCale Deprecation

`[DONE — refactor/rm-lacale (#156), 0.77.0]` — **Scope changed by the operator: deprecation → COMPLETE REMOVAL** (la-cale.space is dead; the live config carried `enabled: false` with a CircuitOpenError incident). Client, factory entry, `ProviderName.LACALE` member, activation entries, ranking samples, SecretsTab, `config.example` block, `docs/reference/lacale-api.md` + fixtures: all removed. Historical database rows (`source_tracker="lacale"`) remain readable as-is — regression: `tests/acquire/test_removed_tracker_history.py` (parameterized torr9 + lacale). Executable zero-remanence proofs (D8 torr9 + D10 lacale): `docs/archive/features/rm-lacale/ACCEPTANCE.md`. The former deprecation plan (`deprecated` flag, skipped tests, code kept) is obsolete — see the 2026-06-02 reclassification journal below for the history.

---

## 🔀 Merge & reclassification journal (2026-06-01)

From the multi-agent brainstorm (code-anchored analysis, adversarial critique applied):

**Merges**

- **Web UI Registry Consumer** → **Web UI S6** page (zero independent backend; status/operations shipped in 0.16.0).
- **Dependency Injection Container** → **RP5a** (the application context must carry the tracker registry — that is the RP5a seam).
- **Freeleech Radar per-result plumbing** → already shipped; only net-new survivor = **R1** (window discovery).
- **Scattered acquisition events** → **RP4** (one single catalog).
- **Active Health mutation + Hot-Swap swap** → **single RP8 primitive** (both mutate the chain order live).
- **Library validator** → 2nd protocol in **Verify V1**.

**Splits** (features too big → spec-sized)

- Web Management UI → **S1–S7** · TVShow Follow → **D1–D4** · Seed Safety → **O1–O4** · Verify → **V1–V3** · Ratio → **C1–C3** · Freeleech → **R1**.
- (Coherence pass) **RP5 → RP5a + RP5b** (registry/DI wiring vs grab core) · **Library renewal** pulled out of D4 as a standalone item.

**Coherence additions** (otherwise the loop does not turn)

- Cross-tracker **pre-ranking** dedup (in RP5b/D3) · real-disk > seed-pure precedence (O3) ·
  3-hour cron decommission at Watcher cutover · registry status versioning before S6 (S6.0).

**Reclassifications**

- `lib-fold` (shipped in 0.19.0) **removed**. · LaCale → P1. · torr9+digitalcore P3 → P2. · DI Container → absorbed into RP5a.

**Deferred (not retained this round)**: comfort — list bootstrap from the indexer, dedicated Web UI ratio pages.

**Coherence pass (2026-06-01)**: roadmap made less code-dependent (references = dated hints,
not contracts); split/order re-verified; 1 hard ordering fix (torr9 W2→W3, depended on
RP7); no over-zeal (over-splits refused).

**Reframe Reverse Episode Lookup → Episode resolution by name (2026-06-02)**: from an isolated
manual tool to a feature **integrated into the pipeline**. Split into **E1** (name-keyed matching,
fallback + non-blocking corroboration modes, wave 1 — the number remains the default key) and **E2**
(correction via name-keyed re-scrape from the original download / re-download, wave 5, depends on the
grab core + trackers). Frozen principle: the (noisy) name never supplants the number
automatically; it serves as a fallback (number absent) or as a soft signal (number present).

**Architecture pass (2026-06-02)**: code-anchored multi-agent architecture review. Verdict — the roadmap
**thinks architecture** (shared RPs laid before the features, merges that reduce the surface, order =
layering, reasoned state ownership), not piling-up. Major gap fixed: **the altitude of the acquisition
lobe**. Additions: **🏛 Target architecture** section + **RP5c** (`acquire/` package + single
injection seam), **RP3a** (shared "desired item" domain model), **RP-layer** (import-direction
guardrail); clarifications on **RP3** (ownership/partition of `acquire.db`, deletion
decide-vs-execute), **RP5a** (config factory + boot validation), **RP4** (eager-import event
registration), **O3** (single free-space authority, dispatch de-facto owner); dependency notes for
**S4/S5** (reload + pause/resume seams) and the **Watcher** (single trigger authority).

**LaCale Deprecation reclassification W1→W2 (2026-06-02)**: code-footprint survey (brainstorm
`/implement:feature`, multi-agent survey). The deprecation as specified ("removal from the active
registry" + "boot warning") presupposes a **wired tracker registry**, which **does not exist
yet** — that is precisely **RP5a**'s job (`TrackerRegistry` never instantiated, `resolve_active`
never called for trackers, no `tracker_registry` in the AppContext; the only live lever
today = the `config/tracker.json5 lacale.enabled` flag, currently `true`). LaCale Deprecation
**therefore depends on RP5a** and moves down to Wave 2. Decisions settled for when it is done: drop
`lacale` from `priority` (prod **+** example), **full doc sweep** (+ fix of the stale
`_contracts.py` docstring that wrongly claims `FreeleechAware`), `lacale.py` stays **importable** (c411
`_parse_title` coupling, to coordinate with tech-debt-2). Apparent quick-win → in reality **gated by RP5a**.

---

## 📜 Journal — original request (verbatim, 2026-06-01)

The operator's original request, verbatim (French):

> - LaCale n'est plus, déprécié, garder le code.
> - 2 nouveaux trackers : https://torr9.net/ et https://digitalcore.club/
> - Module de gestion du ratio (téléchargement automatique des torrents les plus propices au
>   partage afin d'augmenter le ratio). Gestion tracker par tracker.
> - Module de suivi tvshows (téléchargement automatique des nouveaux épisodes / nouvelles saisons
>   d'une série, parmi une liste de séries suivies) ; recherche sur tous les trackers et choix du
>   meilleur torrent selon plusieurs critères (ratio, qualité, piste audio…).
>
> Puis : « on pense aussi architecture en ajoutant des features de refacto si nécessaire pour
> préparer le terrain »

→ RP1–RP9. The refined detail lives in the Catalogue + the Construction plan above.
