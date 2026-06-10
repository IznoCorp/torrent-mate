# DESIGN — RP3: `acquire.db` store + single deletion authority

| Field                   | Value                                                                                                                                            |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Codename (proposed)** | `acquire-store`                                                                                                                                  |
| **Roadmap item**        | RP3 (P1, Vague 2) — partially absorbs O2's first wiring (see §11)                                                                                |
| **Type**                | minor                                                                                                                                            |
| **Version bump**        | 0.25.0 → 0.26.0                                                                                                                                  |
| **Date**                | 2026-06-10                                                                                                                                       |
| **Depends on**          | RP5c (`acquire/` lobe + `AcquireStore` seam), RP2 (`TrackerEconomyConfig`), RP1 (`TorrentItem.tags`, `is_seeding`, `get_completed`) — all merged |
| **Builds toward**       | RP5b (grab core), Follow D1–D3, Ratio C1–C3, Seed-Safety O1–O4                                                                                   |

> This design was hardened by a 6-lens adversarial review against the live codebase
> (2026-06-10). Every claim below that diverges from the ROADMAP's dated hints is
> code-verified; file:line evidence is cited inline where it overturns an assumption.

---

## 1. Problem & context

The acquisition lobe (`acquire/`, landed by RP5c) currently exposes a one-method
`AcquireStore` Protocol (`close()` only) and a `store: AcquireStore | None = None`
slot on `AcquireContext`, hard-wired to `None` in `build_acquire_context`. There is
**no acquisition persistence** anywhere in the project, and **no seed-aware guard** on
any deletion path: `maintenance/disk_cleaner` and `dispatch` (movie replace / TV merge)
delete media with zero knowledge of whether a torrent is still seeding from those bytes
(verified: `rg seed|info_hash|seedtime` over `dispatch/` + `maintenance/` returns zero
hits in any deletion path). Deleting a still-seeding payload before its tracker's minimum
seed time is a hit-and-run (HnR) penalty on the user's private trackers.

RP3 fills the store seam **and** establishes the project's first single deletion
authority, fail-open, so later acquisition features (Follow, Ratio, Seed-Safety, the
Watcher) have a persistence home and an HnR guard to build on.

## 2. Goals / Non-goals

**Goals**

1. A dedicated `acquire.db` SQLite store (separate file from `library.db`) with four
   tables — followed series, the `wanted` queue, seed obligations, ratio state — under a
   single-writer discipline, filling the `AcquireStore` slot.
2. Extract the proven SQLite machinery from `indexer/db.py` into a **neutral**
   `core/sqlite/` so both `indexer/` and `acquire/` consume one socle (no duplication of
   lock/PRAGMA/migration logic).
3. A single **deletion authority**: a fail-open `DeletePermit` port (neutral) wired into
   `disk_cleaner` and `dispatch`, backed by persisted seed obligations, that prevents
   HnR deletions where it can and degrades to ALLOW where it can't.
4. Config plumbing for the store (`acquire.json5` overlay + `AcquireConfig`), zero
   migration tooling (pre-v1, single instance evolves in place).

**Non-goals**

- ❌ Acquisition events / Telegram subscriber — owned by **RP4** (parallel P1). RP3 stays
  EventBus-silent.
- ❌ The "do I already own this" ownership predicate — owned by **RP6** (indexer query
  layer, SELECT-only across the boundary).
- ❌ Per-followed-series quality profile + source criteria — owned by **RP3a** (P2, the
  RP5b orchestrator-input contract). RP3 defines only the store-facing identity subset.
- ❌ The ratio-measurement loop (writer of `ratio_state`) — owned by **Ratio C1** (Vague 5).
  RP3 creates the table as a **dormant data-carrier**.
- ❌ Relocate-not-delete on an unmet seed obligation — owned by **O2/O3** (needs the
  global disk-budget arbiter, Vague 5). RP3 detects, records, and warns; it does not relocate.
- ❌ Any new trigger/pipeline lock — acquisition triggering routes through the existing
  `pipeline.lock` (single trigger authority).

## 3. Frozen decisions

| #     | Decision                                                                    | Resolution                                                                                                                                                                        |
| ----- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | How `acquire/` obtains the SQLite primitives (it may not import `indexer/`) | **Full extraction to `core/sqlite/`** — see §5. Adversarially constrained: core must be **event-free**, exception bases are minimal markers, `_fs_probe` moves too.               |
| **B** | RP3a domain vocabulary: fold in or defer                                    | **Fold the store-facing subset only** (FollowedSeries / WantedItem / SeedObligation / RatioState, keyed on a neutral `MediaRef`). Defer QualityProfile + source-criteria to RP3a. |
| **C** | Deletion authority: persistence-only vs full wiring                         | **Full wiring** — persistence + neutral port + consult sites in `disk_cleaner` and `dispatch` — but with **per-site, seedtime-aware policy** (§7), not blanket warn-and-proceed.  |
| **D** | `ratio_state` table now or later                                            | **Create now, dormant.** Writer arrives with Ratio C1 (Vague 5). Matches the established data-carrier pattern (RP2 economy config, RP4 events "muet jusqu'aux vagues 4–5").       |

## 4. Architecture & layering

New / changed modules (import direction is strictly downward; `acquire/` never imports a
triage package, the deleters never import `acquire/`):

```
core/                         (neutral leaf — importable by everyone, imports nothing upward)
  sqlite/
    _pragmas.py     apply_pragmas(conn)            — the canonical 8-PRAGMA set (SSOT)
    _open.py        open_db(path, *, ...)          — EVENT-FREE: corruption-quarantine, FK-orphan,
                                                      free-space guard (raises neutral SqliteDiskFullError),
                                                      macFUSE-NTFS rejection
    _lock.py        db_lock(path, *, timeout=0)    — FileLock + .lock.json sidecar + stale-PID recovery;
                                                      logs core.sqlite.lock.* events
    _migrate.py     apply_migrations(conn, dir_)   — moved as-is (already dir-parameterized)
    _fs_probe.py    probe_mount(path) -> MountInfo  — moved here (genuinely neutral)
    errors.py       Sqlite{Lock,Corrupt,InvalidPath,DiskFull,FKOrphans,Migration}Error  — minimal markers
  identity.py       MediaRef                        — neutral provider-id value object (tmdb/tvdb/imdb)
  delete_permit.py  DeletePermit, SeedObligationRecorder (Protocols) + AllowAllPermit (fail-open no-op)
indexer/
  db.py             THIN WRAPPER: re-exports every core symbol the 77 test files import;
                    keeps the event-emitting check_free_space (+ DiskFullWarning);
                    re-parents IndexerXxxError onto the core markers
acquire/
  _ports.py         AcquireStore Protocol EXTENDED with query/write methods
  domain.py         FollowedSeries, WantedItem, SeedObligation, RatioState (frozen VOs, keyed on MediaRef)
  config.py         (model lives in conf/ — see §8) read by the factory
  store.py          concrete AcquireStore over core/sqlite: sub-stores .follow/.wanted/.seed/.ratio
  migrations/001_init.sql
  delete_authority.py  implements DeletePermit + SeedObligationRecorder over the store + live torrent client
  _factory.py       builds the store + the delete-authority, sets them on AcquireContext
maintenance/disk_cleaner.py   gains `permit: DeletePermit = AllowAllPermit()` param (consult before delete)
dispatch/ (run.py, _movie.py, _tv.py)  gains injected DeletePermit + SeedObligationRecorder (core-typed)
```

**Layering facts verified against `tests/architecture/test_layering.py`:**
`_FORBIDDEN_PREFIXES` excludes `core` and `conf` → `core/` is a legal import target for
`maintenance/` and `dispatch/`. `core/delete_permit.py` + `core/identity.py` must import
only stdlib/typing (mirror `core/_contracts.py`) so `test_core_does_not_import_upward`
stays green. The deleters depend on the **core port types only**; the concrete
`acquire/` impls are injected by the composition root.

## 5. Pillar 1 — `core/sqlite/` extraction (the load-bearing refactor)

The SQLite machinery in `indexer/db.py` is **liftable but not a verbatim move**. Verified
constraints and the resulting plan:

1. **Core must be EVENT-FREE.** `open_db`/`check_free_space` emit `DiskFullWarning`, an
   indexer-domain event (`indexer/events.py`). A neutral core cannot import it.
   → `core.sqlite.open_db` takes **no `event_bus` param** and raises a neutral
   `SqliteDiskFullError` (no event). The event-emitting `check_free_space` + the
   `DiskFullWarning` emit **stay in the `indexer/db.py` wrapper**, which keeps its
   `event_bus: EventBus` (no-default) signature — this is required because
   `tests/architecture/test_event_bus_required_signatures.py` pins `indexer.db.open_db`
   and `indexer.db.check_free_space` and runs an AST sweep over the whole package
   forbidding `event_bus: EventBus | None`. Core having no `event_bus` param keeps both
   the pin and the sweep green.

2. **Exception bases are minimal markers.** Tests construct `IndexerXxxError` with keyword
   args (`IndexerLockError(pid=…)`, `IndexerMigrationError(version=…)`) and read rich
   attrs (`.pid`, `.quarantine_path`, `.free_bytes`, `.required_bytes`, `.mount_point`,
   `.orphan_count`, `.version`) across 9 files (65 references). → `core/sqlite/errors.py`
   defines **bare markers** `Sqlite{Lock,Corrupt,InvalidPath,DiskFull,FKOrphans,Migration}Error`
   (subclassing `RuntimeError`/`ValueError`/`OSError` as today). The full
   attribute-bearing `IndexerXxxError` **stay in `indexer/db.py`, re-parented** to subclass
   the core marker. All raising code raises the indexer subclass (never the bare base) so
   attributes are present. Regression test: `isinstance(IndexerCorruptError(...), SqliteCorruptError)`.

3. **`_fs_probe` moves to `core/sqlite/_fs_probe.py`** (it is genuinely neutral — stdlib +
   logger only). Six non-test importers (`conf/models/indexer.py`, `conf/models/disks.py`,
   `indexer/_fs_capability.py`, `indexer/scanner/__init__.py`, `indexer/scanner/_spotlight.py`,
   `indexer/db.py`) get a re-export shim at `personalscraper.indexer._fs_probe`.
   `conf/models/indexer.py` imports `probe_mount` from **core** (conf→core is clean; the
   current `# layering: allow` marker for conf→indexer is relaxed).

4. **`apply_migrations` is already `(conn, dir_)`-parameterized** — pure move. All 10 call
   sites pass their own migrations dir. `acquire/` calls it with its own dir.

5. **Event-string rename.** Only `indexer.lock.stale_recovered` is asserted in a test
   (`tests/indexer/test_db.py:186`). The moved `db_lock` logs `core.sqlite.lock.stale_recovered`;
   that one assertion is updated. `indexer.db.*` / `indexer.migration.*` event strings have
   **zero** test assertions → free to become `core.sqlite.*`.

6. **`open_db` imports no indexer schema/repos** (verified) — coupling is narrow (only
   `_fs_probe` + `DiskFullWarning`), both addressed above.

**Gate for this phase:** all `indexer/` tests green; residual-import grep
(`from personalscraper.indexer.db import …` across 77 files) still resolves via the
wrapper; `isinstance` regression test passes; `make check` green.

## 6. Pillar 2 — `acquire.db` store

### 6.1 Schema (one file, one writer-lock, logical partition)

Four tables, single `acquire.db` file, a single `acquire.db.lock`; "partitioned write
authority" = sub-store **method namespaces** (`store.follow.*`, `store.wanted.*`,
`store.seed.*`, `store.ratio.*`) over one lock (no 3-file/3-lock split — matches the
indexer precedent where one lock serializes one DB file). Conventions mirrored from
`001_init.sql`: `INTEGER PRIMARY KEY`, unix-epoch-second `INTEGER` timestamps, `CHECK IN`
enums, FKs with explicit `ON DELETE`, partial indexes `WHERE status='…'`, JSON-as-TEXT
`*_json` columns.

| Table             | Key columns                                                                                                                                                                                                                                                          | Writer authority | Status                                    |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ----------------------------------------- |
| `followed_series` | `media_ref_json` (MediaRef), `title`, `active`, `quality_profile_json` _(nullable; rich profile = RP3a)_, `cadence_json` _(nullable; RP9/D2)_, `added_at`                                                                                                            | follow           | active (Follow D1 consumes)               |
| `wanted`          | `followed_id` FK→followed_series, `media_ref_json`, `kind` CHECK(movie/episode), `season`, `episode`, `status` CHECK(pending/searching/grabbed/done/abandoned), `criteria_json`, `enqueued_at`, `last_search_at`, `attempts`; partial index `WHERE status='pending'` | follow           | active (Follow D2)                        |
| `seed_obligation` | `info_hash`, `source_tracker`, `dispatched_path` (nullable), `min_seed_time_s`, `min_ratio`, `added_at`, `satisfied_at` (nullable), `breached_at` (nullable), `released_at` (nullable)                                                                               | seed-safety      | **active — the deletion-authority table** |
| `ratio_state`     | `tracker_name` PK, `observed_ratio`, `accumulated_seed_time_s`, `hnr_count`, `updated_at`                                                                                                                                                                            | ratio            | **DORMANT** (writer = Ratio C1, Vague 5)  |

**Policy is never duplicated into the DB.** `min_seed_time`/`min_ratio`/`target_ratio`
are read from `TrackerEconomyConfig` (`conf/models/api_config.py`) at the point of use; a
seed obligation snapshots the numbers it was created with only as an audit convenience.
Passkeys are never persisted (env via `resolve_optional_secret`).

### 6.2 Domain value objects (`acquire/domain.py`) — store-facing subset only

Frozen dataclasses: `FollowedSeries`, `WantedItem`, `SeedObligation`, `RatioState`, all
keyed on the neutral **`core.identity.MediaRef`** (explicit `tmdb_id` / `tvdb_id` /
`imdb_id` slots; tvdb primary per the multi-provider separation rule). Humanized durations
reuse `conf.models._duration.parse_duration`. **`MediaRef` is deliberately NOT named
`ExternalIds`** — that name is taken by `indexer/external_ids.py` (column-bound,
series/episode hierarchical shape) and `scraper/models.py::ScraperExternalIds` (flat), and
`acquire/` may import neither (layering). `QualityProfile` + source-criteria are **deferred
to RP3a**; `quality_profile_json` is a nullable passthrough column until then.

### 6.3 Single-writer model (SQLite-native) + brief migration lock

> **CHANGE-LOG (sub-phase 3.4, supersedes the earlier "lifetime writer lock" wording):**
> The 3.3 store took the core `db_lock` (FileLock) with `timeout=0` and **held it for
> the store's lifetime**. Because `cli_helpers._build_app_context` is the **single
> composition root** for _every_ command (pipeline, `library/scan` cron, `library/report`,
> `library/query`, `library/audit`, `trailers/cli`), that made every command open
> `acquire.db` and hold the writer lock for its whole runtime — so two previously-concurrent
> commands (e.g. the library-index cron during `personalscraper run`) crashed the second
> with `AcquireLockError`. It also violated this section's own "strict leaf, never held
> across an FS/HTTP op" rule and would have blocked the Phase-4/5 fail-open delete-permit
> _reader_. The model below replaces the lifetime lock.

- **Cross-process single-writer is SQLite-native:** `acquire.db` is opened in **WAL** mode
  (canonical PRAGMA set) and every write goes through `BEGIN IMMEDIATE` (`store._write_tx`)
  with `busy_timeout=5000`. SQLite then serializes writers across processes for free — the
  **same model** used by the indexer outbox publisher and the Phase-5 lock-free seed-
  obligation writer. **No per-write `FileLock`.**
- **Reads are lock-free** (WAL). No lock anywhere on the read path — a **hard requirement**
  of the Phase-4/5 fail-open delete-permit reader, which must never take the writer lock.
- **The core `db_lock` (FileLock) is taken ONLY briefly around open + migrate** — a single
  `with db_lock(..., timeout=10s, error_factory=AcquireLockError):` block wrapping
  `open_db` + `apply_migrations`, then released immediately. `apply_migrations` is
  idempotent (a no-op once `user_version` is current), so the steady-state path holds this
  lock for microseconds. It is a **strict leaf**: never held across an FS operation, never
  across a qBit/Transmission HTTP call, **never `timeout=0`, never for the store's lifetime**.
- **The store opens lazily** (on first sub-store access). `build_acquire_store(config)`
  returns an **inert** handle — no `mkdir`, no connection, no lock, no migration. Commands
  that never touch acquire state open nothing and take no lock, so the **shared composition
  root does NOT serialize unrelated commands** (the library-index cron may run concurrently
  with the pipeline). Open/migration errors (`AcquireLockError` / `AcquireCorruptError` /
  `AcquireMigrationError`) therefore surface at **first access**, not at boot — intentional
  and consistent with §9 fail-open (the future delete-permit treats store-unavailable as
  ALLOW); the config-level WAL-safety validator still validates the **path** at boot.
- **Total lock order invariant** (enforced by discipline + doc):
  `pipeline.lock` (outer) > `indexer_lock` > `acquire.db.lock` (leaf — now only the **brief
  migration lock**). No `acquire.db` writer may acquire `pipeline.lock` or `indexer_lock`
  while holding the migration lock. This makes opposite-order pairs unreachable → provably
  deadlock-free. (`acquire.db` being a separate file also _reduces_ contention: it never
  contends with the indexer scan's `library.db` writer.)
- `store.close()` is **fail-soft** (closes the connection if one was opened, without
  raising) and **idempotent**; close-without-open is a pure no-op (there is no lifetime
  lock to release). It honors `AcquireContext.close()`'s documented no-suppress contract.

### 6.4 Factory wiring

`build_acquire_context` (the single construction site) gains a `build_acquire_store(config)`
delegate (parity with `build_tracker_registry`) and a `build_delete_authority(store,
torrent_client, config)` delegate; it sets `store=` and the delete-authority on
`AcquireContext` instead of `store=None`. **`build_acquire_store` is inert** (no I/O), so
the factory needs **no path guard** — a mock config whose `.acquire` is never dereferenced
into a sub-store leaks nothing. **No `AppContext` change, no `cli_helpers` change** beyond
what already exists — `per_step_boundary` teardown already calls `acquire.close()`, which
now transitively closes the store (a no-op when the store was never opened).

## 7. Pillar 3 — single deletion authority

### 7.1 Ports (neutral, `core/delete_permit.py`)

```python
class DeletePermit(Protocol):
    def may_delete(self, path: Path) -> PermitDecision: ...   # ALLOW | VETO(reason)

class SeedObligationRecorder(Protocol):
    def record_dispatch(self, *, staging_source: Path, dispatched_dest: Path) -> None: ...

class AllowAllPermit:   # fail-open no-op default for tests + store-absent
    def may_delete(self, path: Path) -> PermitDecision: return ALLOW
```

`acquire/delete_authority.py` implements both over the store + the borrowed
`torrent_client`. **Fail-open everywhere:** store absent / unreadable / lock-timeout /
no-obligation / any lookup error → **ALLOW**. VETO only on a positively-known unmet obligation.

### 7.2 Two resolvers that do NOT share a path-match assumption

The original "live `content_path` match resolves a deletion candidate" idea is **provably
false** and dropped: qBit/Transmission `content_path` stays under `torrent_complete_dir`
(no `set_location`/`rename` call exists anywhere; the link is severed at **ingest**, where
seeding torrents are _copied_ into staging). The two trees never overlap. Therefore:

- **Deletion-time resolver** (used by `disk_cleaner`, future ratio-rotation): joins **only**
  on the persisted `seed_obligation.dispatched_path` (exact path vs the deletion path and
  its descendants — not a loose dir-prefix, to avoid over-vetoing a genuine orphan when
  `torrent_complete_dir` happens to sit inside a storage disk). A **path-exists guard**
  makes a stale obligation (crash before move) inert.
- **Dispatch-time obligation writer** (`SeedObligationRecorder.record_dispatch`): correlates
  the staging source to a live **seeding** torrent by **basename + total size** against a
  single cached `get_completed()` call (NOT path-prefix). Scoped to `is_seeding()==True`
  torrents only (stopped/moved torrents have a dangling `content_path` and carry no live
  obligation → correctly skipped). **Writes the obligation BEFORE the FS move** (a lost
  obligation is a lost safety constraint, unlike the indexer's self-healing derived-cache
  outbox; write-before-move guarantees "lost obligation ⇒ move never happened"). The write
  is **lock-free + fail-soft**, mirroring `outbox/_publish.py`: a short raw `sqlite3`
  connection + `busy_timeout` + swallow-on-error (NOT `acquire.db.lock` with `timeout=0`,
  which would maximize obligation loss). Logs HIT/MISS with miss-reason
  (`no-live-torrent` | `not-seeding` | `name+size-ambiguous` | `merge-basename-divergence`)
  so real coverage is observable.

### 7.3 Per-site policy (seedtime-aware, corrects the O3 conflation)

`O3 "le vrai média gagne"` governs **disk-budget precedence**, not licence to delete a
live seed. Correct three-state policy:

| Site                                                 | Decision                                                                                                                                                                                                                                                             |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `maintenance/disk_cleaner`                           | VETO = **hard skip** (count as skipped-by-obligation, like the existing "disk full, cannot replace" skip). Residue cleanup (.actors / junk / empty / orphan-release) never targets a live payload, so this never stalls legitimate cleanup; it fails safe.           |
| `dispatch` replace/merge, **seedtime/min_ratio MET** | **ALLOW** (proceed; obligation satisfied → `satisfied_at` set).                                                                                                                                                                                                      |
| `dispatch` replace/merge, **NOT met**                | **Proceed** (new real media must land) **+ mark `seed_obligation.breached_at` + structlog `acquire.hnr_risk` warning** (recorded, never silent). **Relocate-not-delete is chartered to O2/O3** (needs the disk-budget arbiter, Vague 5). Fail-open if no obligation. |

Note: under **default config** (torrent_complete_dir distinct from the storage disks +
ingest copying seeding torrents) dispatch deletes only library **copies**, so the breach
branch is near-dead; it becomes load-bearing only in topology A (torrent_complete_dir on a
storage disk) or once Ratio C2/C3 seeds directly from the library — both arrive with O3, so
deferring relocate is dependency-correct.

### 7.4 Injection (composition root, no deleter imports `acquire/`)

- **Dispatch:** `DispatchStep` (already on the `AppContext` boundary) forwards
  `ctx.app.acquire.delete_authority` (a core-typed handle composing the permit + recorder)
  into `run_dispatch` → the single `Dispatcher()` (`dispatch/run.py`). `Dispatcher.__init__`
  / `run_dispatch` gain core-typed params defaulting to `AllowAllPermit()`.
- **Maintenance:** `disk_cleaner.clean_library(config, …)` gains `permit: DeletePermit =
AllowAllPermit()`. Maintenance has **no `AppContext`** on its path (legacy `AppCtx` only),
  so the `commands/library/maintenance.py` command builds the acquire authority at the
  command boundary and passes the core-typed permit in. `disk_cleaner.py` never imports
  `acquire/`.
- Passing a `DeletePermit`/recorder is **`AppContext`-boundary-compliant** ("the specific
  service", not the bundle); no new `APP_CONTEXT_ALLOWED_FUNCS` entry.

## 8. Config

- New `config.example/acquire.json5` owning the `acquire` top-level key:
  `acquire: { db_path: null }` (room for future `acquire.*` tunables). **Bundled in the same
  commit** (else `test_example_config.py`'s `load_config_dir` over the whole dir raises
  `ConfigLoadError`). Added to the `overlays` array in **both** `config.example/config.json5`
  and the live `config/config.json5`.
- `AcquireConfig(_StrictModel)`: `db_path: Path | None = Field(default=None,
validate_default=True)` + a WAL-safety field validator mirroring `IndexerConfig`
  (`probe_mount` from core, reject `ntfs_macfuse`/`unknown`). Registered on `Config` as
  `acquire: AcquireConfig = Field(default_factory=AcquireConfig)` — **co-required** because
  `_StrictModel` is `extra='forbid'`. `_resolve_derived_paths` extended:
  `if self.acquire.db_path is None: object.__setattr__(self.acquire, 'db_path',
self.paths.data_dir / 'acquire.db')`.
- `docs/reference/config-overlay-layout.md`: bump "15 → 16 overlays" (3 prose spots) + add
  the `acquire` row to the key-ownership table.
- **No migration tooling** (pre-v1; single instance evolves config + schema in place).

## 9. Error handling, events, lifecycle

- Exceptions: `core.sqlite.errors.Sqlite*Error` markers; `acquire/`-specific subclasses
  (`AcquireLockError`, `AcquireCorruptError`, `AcquireMigrationError`) with actionable
  messages, subclassing the core markers. CLI catches the tuple →
  `typer.echo(str(exc), err=True); return 1`.
- **Fail-open** on every deletion-authority path; **fail-soft** on every best-effort store
  write (swallow + `*_lost`/`*_skipped` log).
- **EventBus-silent:** RP4 owns the acquisition event catalog + eager-import registration.
  The store does not take or emit on an `EventBus` (avoids dropping un-registered events on
  round-trip). The only "signal" RP3 emits is **structlog** (`acquire.*` event names via
  `personalscraper.logger.get_logger`, never `structlog.get_logger` directly).

## 10. Phase decomposition (for `/implement:plan`)

1. **`core/sqlite` extraction** — move neutral mechanics + `_fs_probe`; event-free `open_db`;
   marker exceptions + re-parented `IndexerXxxError`; thin `indexer/db.py` wrapper +
   re-export shims; event-string rename + 1 test update; `isinstance` + residual-import
   gate. Indexer ~6000 tests green.
2. **`core/identity.MediaRef` + `AcquireConfig` + `acquire.json5`** — config plumbing,
   derived path, WAL-safety validator, overlay-layout doc bump, example-config test.
3. **`acquire/domain.py` + schema + store** — VOs, `001_init.sql` (4 tables), `AcquireStore`
   Protocol extension, concrete store (4 sub-stores; **lazy open, SQLite-native single-writer
   via `BEGIN IMMEDIATE`, lock-free reads, brief migration-only `db_lock`** — corrected in
   sub-phase 3.4, see §6.3 CHANGE-LOG), factory wiring (`store=` filled, lazily),
   migration-contract + concurrency-regression + laziness + close() tests.
4. **`core/delete_permit` + `acquire/delete_authority`** — Protocols + `AllowAllPermit`,
   deletion-time resolver (persisted `dispatched_path` + path-exists guard), fail-open;
   adversarial fail-open mutation tests.
5. **Dispatch-time writer + per-site wiring** — `record_dispatch` (basename+size,
   `is_seeding`, write-before-move, lock-free fail-soft, HIT/MISS log); inject permit/recorder
   into `dispatch/run.py` + `clean_library`; three-state dispatch policy + hard-skip
   maintenance; crash-window tests.
6. **Guardrails + docs + gate** — extend `test_layering.py` (maintenance/dispatch ⇏ acquire,
   non-vacuous control); lock-order doc; `architecture.md` + reference docs;
   `ACCEPTANCE.md`; ROADMAP RP3/O2 re-scope; `make check` gate.

## 11. ROADMAP re-scope (deviation, signed off)

RP3 as designed **absorbs O2's first deletion-authority wiring** (the persisted obligation
table + the permit consulted by the deleters), per the operator's "câblage complet"
decision. O2 is re-scoped to **policy refinement** on top of the now-wired authority
(notably relocate-not-delete, which depends on the O3 disk-budget arbiter). The ROADMAP
RP3 and O2 entries are updated in Phase 6 to record this split. SemVer stays **minor**.

## 12. Testing strategy

- **Per-bug regression discipline** + adversarial goldens on the lock/migration code
  (memory: dispatched DB code ships vacuous tests that hide real bugs).
- Migration-contract test (every version 1..N in `schema_version`; `user_version` == latest).
- **Concurrency regression (sub-phase 3.4):** two stores on the SAME `db_path` both open +
  read with NO `AcquireLockError` (the lifetime-lock regression is fixed); a write through
  one handle is visible to another (`BEGIN IMMEDIATE` durability across handles); the brief
  migration `db_lock` still maps a live holder → `AcquireLockError` + stale-PID recovery.
- **Laziness (sub-phase 3.4):** `build_acquire_store` creates no db file / connection / lock
  until the first sub-store access; building a context opens nothing at boot.
- **Fail-open mutation-proven:** inject a VETO → deleter skips; remove the obligation →
  deleter deletes. Store absent/unreadable → ALLOW.
- **Crash-window tests:** (1) move-then-kill-before-obligation → live path can't help
  (storage disk) but no over-delete because obligation absent ⇒ ALLOW is acceptable;
  (2) obligation-then-kill-before-move → stale obligation inert via path-exists guard,
  re-run completes; (3) concurrent acquire writer holding the lock while dispatch writes →
  lock-free path does not hang, proceeds.
- **Seedtime policy:** dispatch over a dest equal to a live torrent's content_path with
  seedtime NOT met → does NOT relocate (deferred) but marks `breached_at` + logs
  `acquire.hnr_risk`; seedtime MET → proceeds, sets `satisfied_at`.
- **Layering:** extended guard (maintenance/dispatch ⇏ acquire, non-vacuous positive
  control); `core/delete_permit` + `core/identity` import nothing upward; indexer ~6000 green
  post-extraction.

## 13. ACCEPTANCE preview (executable criteria — finalized in ACCEPTANCE.md)

Each criterion is an executable shell command with a documented expected output, e.g.:

- `python -c "import personalscraper"` → exit 0 (smoke).
- `personalscraper init-config && ls config/acquire.json5` → file present.
- A pytest selector proving fail-open: store-absent deletion proceeds.
- A pytest selector proving the migration contract on a fresh `acquire.db`.
- `make check` → green (lint + test + module-size + typed-api).

## 14. Open items explicitly deferred (not gaps)

- `QualityProfile` + source-criteria vocabulary → **RP3a**.
- `ratio_state` writer (measurement loop) → **Ratio C1**.
- Relocate-not-delete on unmet obligation → **O2/O3** (disk-budget arbiter).
- Acquisition events + Telegram → **RP4**.
- Ownership predicate (`wanted` ↔ owned dedup) → **RP6**.
- Watcher / cron decommission, trigger authority → **Watcher Service** (Vague 4).
