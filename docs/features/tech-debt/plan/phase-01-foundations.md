# Phase 1 — Foundations BDD/indexer + PRAGMA discipline

**Effort** : 3-4 jours (revised post coverage-fix)
**Theme** : restaurer le drift mechanism, activer les invariants FK, PRAGMA discipline
multi-site, oshash retry, init-canonical bridge, fixture E2E.

## Coverage matrix

| Item             | Sub-phase  | Source pattern    |
| ---------------- | ---------- | ----------------- |
| MUST-1 / DEV #18 | 1.1        | P11, P24          |
| MUST-2 / DEV #19 | 1.2        | P15, P24          |
| MUST-17 / BD-B   | 1.3        | P2 (test E2E)     |
| MUST-16 / BD-AG  | 1.4        | P2 (test E2E)     |
| SH-23 / DEV #15  | 1.5        | P14               |
| SH-9 / BD-L      | 1.6        | P15               |
| DEV #50          | 1.7 NEW    | (bonus)           |
| DEV #51 + #52    | 1.8 NEW    | (bonus)           |
| DEV #54          | 1.9 NEW    | (bonus)           |
| DEV #33 + #34    | 1.10 NEW   | P33 PRAGMA_BYPASS |
| DEV #37          | 1.10 audit | (covered)         |

DESIGN sections impacted : §9 BDD lifecycle invariants, §15 PRAGMA discipline.

## Gate (prérequis avant cette phase)

- Branch `fix/tech-debt` checkout
- DESIGN.md + plan/INDEX.md committed
- 4 fix commits déjà shipped (268cbee, 29c4953, fc39f77, 3993487)
- `make test` vert (vérifier avant de démarrer)

## Sub-phases

### 1.1 Restaurer le drift mechanism (MUST-1 / DEV #18)

**Sites** :

- `personalscraper/indexer/drift.py:417` — `increment_miss_strikes_for_disk` existe
- `personalscraper/indexer/commands/scan.py:~285` — entre walk fin et `apply_soft_deletes`

**Implementation** :

Ajouter dans `scan.py` après le walk, pour chaque disk visité :

```python
from personalscraper.indexer.drift import increment_miss_strikes_for_disk

# After walk loop, before apply_soft_deletes
if not dry_run and scan_mode in (ScanMode.full,):  # incremental visits selectively
    for d in filtered_disks:
        try:
            increment_miss_strikes_for_disk(conn, d.id, current_generation)
        except sqlite3.Error as exc:
            log.warning("indexer.cli.index.miss_strike_failed", disk_id=d.id, error=str(exc))
```

Conditions : full mode seulement (incremental visite sélectivement, ne bumpe pas la gen
universellement) ; pas en dry_run.

**Commit** : `fix(tech-debt): wire increment_miss_strikes_for_disk into scan flow (DEV #18)`

### 1.2 Activer FK enforcement runtime (MUST-2 / DEV #19)

**Sites** :

- `personalscraper/indexer/db.py — open_db()` (ligne ~313, **PRAGMA foreign_keys=ON déjà présent
  depuis commit `5a6397cd` 2026-04-30** — l'audit DEV #19 a légèrement sous-estimé l'état du
  code) — la fix réelle est d'ajouter un **pre-check** + **propager `_apply_pragmas()`** aux
  sites raw (voir 1.10 PRAGMA discipline + DEV #33/#34).

**Implementation** :

Pré-check + (re-)activation. **CRITIQUE** : un `PRAGMA foreign_key_check;` doit retourner zero
AVANT d'activer FK ON, sinon les opérations qui passaient silencieusement vont échouer. Le
code actuel active FK sans pre-check — c'est ce que cette sub-phase corrige.

```python
def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), ...)
    # Pre-check : si orphans, log + abort (sauf flag bypass pour dev)
    orphans = conn.execute("PRAGMA foreign_key_check;").fetchall()
    if orphans:
        log.error("indexer.db.foreign_key_orphans", count=len(orphans), sample=orphans[:5])
        # Phase 1 strict: raise. Phase 8: peut être softer avec flag.
        raise IndexerCorruptError(f"FK orphans detected: {len(orphans)}")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

**Commit** : `fix(tech-debt): enforce PRAGMA foreign_keys = ON at open_db (DEV #19)`

### 1.3 Test E2E miss-strike lifecycle (MUST-17 / BD-B)

**Site** : `tests/indexer/test_drift_e2e.py` (nouveau fichier)

**Scenario** :

```python
def test_miss_strike_lifecycle_on_deleted_file(tmp_path, fs):
    """Create FS file → scan → assert media_file. Delete FS file → scan N times →
    assert miss_strikes==N. On N+1 scan, assert deleted_at NOT NULL (soft-deleted).
    """
    # Setup : fixture seeded with config + DB
    # Run N successive scans with file present then absent
    # Assert miss_strikes progression + soft-delete
```

**Commit** : `test(tech-debt): pin miss-strike lifecycle E2E (MUST-17)`

### 1.4 Test E2E scan→reconcile=clean (MUST-16 / BD-AG + BD-AF)

**Site** : `tests/integration/test_scan_reconcile_clean.py` (nouveau)

**Fixture** (BD-AF) : `tests/integration/fixtures/seeded_library_fs.py` ; FS temp + DB
pré-seedée + 10 media_item + ~50 episodes + ~100 media_file.

**Scenario** :

1. Seed DB + FS aligned
2. Run `library-index --mode full`
3. Run `library-reconcile`
4. Assert `total_findings == 0`

**Commit** : `test(tech-debt): pin scan→reconcile=clean invariant (MUST-16)`

### 1.5 schema_version row 3 cleanup (SH-23 / DEV #15)

One-shot patch dans une migration `006_schema_version_row3_fixup.sql` :

```sql
INSERT OR IGNORE INTO schema_version (version) VALUES (3);
INSERT INTO schema_version (version) VALUES (6);
PRAGMA user_version = 6;
```

**Commit** : `fix(tech-debt): backfill missing schema_version row 3 (DEV #15)`

### 1.6 PRAGMA integrity_check au boot (SH-9 / BD-L)

Dans `open_db()` (après FK activation) :

```python
ic = conn.execute("PRAGMA integrity_check;").fetchone()[0]
if ic != "ok":
    log.error("indexer.db.integrity_check_failed", result=ic)
    raise IndexerCorruptError(f"integrity_check returned: {ic}")
```

**Commit** : `fix(tech-debt): PRAGMA integrity_check at open_db (SH-9)`

### 1.7 Fix library.scanner.\_ensure_disk_row UUID mismatch (DEV #50)

**Site** : `personalscraper/library/scanner.py:756,781 — _ensure_disk_row`

**Bug** : `_ensure_disk_row` looks up `disk` row by `disk_repo.get_by_uuid(conn, disk_cfg.id)`
where `disk_cfg.id` is the config string ("disk_1"), but rows inserted by
`indexer.scanner.bootstrap_disk_identity` carry the real VolumeUUID (e.g.
`F7E3C03C-...`). Result : `scan_library()` inserts 4 duplicate disk rows (uuid="disk_1" etc.)
and subsequent operations skip them with `sentinel_mismatch`.

**Reproduit empiriquement 2026-05-21 22h35** : `disk` table 4 → 8 rows after one
`scan_library()` call.

**Fix** :

```python
# Look up by VolumeUUID via the existing sentinel-verified helper, fall back
# to label match for legacy rows.
from personalscraper.indexer.merkle import verify_disk_mounted, DiskMountStatus

def _ensure_disk_row(conn, disk_cfg, now_s):
    # Try by label first (config-stable across remounts)
    existing = disk_repo.get_by_label(conn, disk_cfg.id)
    if existing is not None:
        return existing
    # Fall back to VolumeUUID lookup via mount probe
    real_uuid = _probe_volume_uuid(disk_cfg.path)  # uses bootstrap_disk_identity if needed
    existing = disk_repo.get_by_uuid(conn, real_uuid)
    if existing is not None:
        return existing
    # Truly new disk : insert with real UUID
    row = _build_disk_row_with_uuid(disk_cfg, real_uuid, now_s)
    disk_repo.insert(conn, row)
    return row
```

**Test** : add `test_ensure_disk_row_no_duplicate` — pre-populate disk row with real UUID,
call `_ensure_disk_row` with same config, assert no INSERT.

**Commit** : `fix(tech-debt): _ensure_disk_row uses real VolumeUUID, no duplicates (DEV #50)`

### 1.8 Retry oshash on Stage-A rows (DEV #51 + #52)

**Sites** :

- `personalscraper/indexer/scanner/_modes/enrich.py:290 _enrich_one_file` — add oshash retry step
- `personalscraper/indexer/scanner/_walker.py:496` — full walker should retry on existing
  rows with `oshash IS NULL`

**Strategy** :

1. **Enrich path (DEV #51)** : in `_enrich_one_file`, after the existing 3 steps (streams, NFO,
   artwork), add Step 4 :

   ```python
   # Step 4 (NEW): retry oshash if NULL
   current = conn.execute("SELECT oshash FROM media_file WHERE id = ?", (file_id,)).fetchone()
   if current and current[0] is None:
       from personalscraper.indexer.fingerprint import oshash as _compute
       try:
           new_oshash = _compute(file_path)
           if new_oshash:
               conn.execute("UPDATE media_file SET oshash = ? WHERE id = ?", (new_oshash, file_id))
               log.info("indexer.enrich.oshash_recomputed", file_id=file_id)
       except OSError as exc:
           log.warning("indexer.enrich.oshash_retry_failed", file_id=file_id, error=str(exc))
   ```

2. **Full walker path (DEV #52)** : in `_db_writes._compute_oshash`, when called on existing
   row with `oshash IS NULL`, attempt re-compute even on UPDATE (not just INSERT).

**Tests** :

- `test_enrich_recomputes_null_oshash` — seed row with oshash=NULL but enriched_at set, run
  enrich, assert oshash populated.
- `test_walker_retries_oshash_on_existing_null` — same for walker full mode.

**Commit** : `feat(tech-debt): retry oshash on null-oshash rows in enrich + full walker (DEV #51, #52)`

### 1.9 Init-canonical mode (DEV #54)

**Site** : `personalscraper/indexer/scanner/_modes/backfill_ids.py` (extend) +
`personalscraper/commands/library/scan.py` (Phase 2.1 will create) — add `--init-canonical`
flag OR new `library-init-canonical` CLI sub-command.

**Bug** : `run_backfill_ids` skips items where `canonical_provider IS NULL` with log
`backfill_ids_canonical_unsupported`. But on a BDD pre-provider-ids (or post-scan_library
without scrape), 100% of items have `canonical_provider IS NULL`. Chicken-and-egg.

**Fix** : add a "canonical-from-NFO" bootstrap step :

```python
def init_canonical_from_nfo(conn, config) -> int:
    """Walk all media_item, read their NFO from FS, extract <uniqueid default="true">
    type, set canonical_provider accordingly. Returns count populated."""
    count = 0
    for item in conn.execute("SELECT id, dispatch_path FROM media_item WHERE canonical_provider IS NULL"):
        nfo_path = _resolve_nfo_path(item.dispatch_path, item.kind)
        if not nfo_path.exists():
            continue
        canonical = _parse_canonical_from_nfo(nfo_path)  # 'tvdb' | 'tmdb' | None
        if canonical:
            conn.execute("UPDATE media_item SET canonical_provider = ? WHERE id = ?",
                         (canonical, item.id))
            count += 1
    return count
```

Then `run_backfill_ids` becomes useful : init-canonical first, then backfill fills the
rest from API.

**Test** : `test_init_canonical_from_nfo_populates_from_tvdb_default` — seed item with
NFO containing `<uniqueid default="true" type="tvdb">…</uniqueid>`, run init, assert
`canonical_provider='tvdb'`.

**Commit** : `feat(tech-debt): library init-canonical CLI to bootstrap from NFOs (DEV #54)`

**Post-commit action (Plan A launch — décision opérateur 2026-05-22, option b)** :

Immédiatement après le commit 1.9 et avant de démarrer 1.10, lancer Plan A en arrière-plan :

```bash
# 1. Bootstrap canonical from NFOs (rapide, ~minutes)
personalscraper library-init-canonical
# 2. Plan A : backfill cross-provider IDs + ratings via TMDB/TVDB
# Run en BACKGROUND avec log fichier — peut tourner pendant Phase 2 + Phase 3
nohup personalscraper library-index --mode backfill-ids --no-budget \
  > .data/plan-a-backfill.log 2>&1 &
echo $! > .data/plan-a-backfill.pid
```

Estimation : 1-2h API calls TMDB/TVDB. Aucune supervision continue requise — vérifier
périodiquement `tail -f .data/plan-a-backfill.log` ou attendre `library-doctor` à Phase 5.3.

**Vérification finale en Phase 8.10** : `SELECT COUNT(*) FROM media_item WHERE
external_ids_json != '{}'` doit dépasser 90% (closure ACCEPTANCE provider-ids #3/#4/#10).
Si Plan A a échoué (réseau, rate-limit, quota), Phase 8.10 le relance avec budget.

### 1.10 PRAGMA discipline multi-site (DEV #33 + #34 + audit #37)

**Sites** (raw `sqlite3.connect()` bypass `open_db`) :

- `personalscraper/dispatch/run.py` (×2)
- `personalscraper/commands/library/audit.py`
- `personalscraper/conf/loader.py`
- `personalscraper/indexer/_concurrency.py`
- `personalscraper/indexer/outbox/_disk.py`
- `personalscraper/indexer/outbox/_publish.py`

**Fix** :

1. Extract `_apply_pragmas(conn)` helper in `personalscraper/indexer/db.py` (canonical
   PRAGMA set : `journal_mode=WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`,
   `cache_size=-65536`, `mmap_size=268435456`, `wal_autocheckpoint=1000`,
   `busy_timeout=5000`, `foreign_keys=ON`).
2. Migrate every raw-connect site to call `_apply_pragmas(conn)` after `sqlite3.connect()`.
3. Add lint guard `scripts/check-pragma-discipline.py` :

   ```python
   # Fail if any sqlite3.connect( outside indexer/db.py without _apply_pragmas
   ```

   Wire into `make check`.

**Audit DEV #37 (BEGIN IMMEDIATE)** : run `rg "BEGIN IMMEDIATE\|conn.execute\(.BEGIN"
personalscraper/indexer/`. If absent in write paths, file a follow-up issue (low priority
0.17+, not bloquant pour 0.16.0).

**Commit** : `fix(tech-debt): _apply_pragmas helper + migrate raw connect sites + lint
guard (DEV #33, #34)`

## Phase 1 Gate

- [ ] 1.1 commit + test (DEV #18)
- [ ] 1.2 commit + test (DEV #19)
- [ ] 1.3 commit + test miss-strike lifecycle PASS (MUST-17)
- [ ] 1.4 commit + test scan→reconcile=clean PASS (MUST-16)
- [ ] 1.5 commit + migration 006 applies cleanly (DEV #15)
- [ ] 1.6 commit (SH-9)
- [ ] 1.7 commit + test (DEV #50)
- [ ] 1.8 commit + 2 tests (DEV #51, #52)
- [ ] 1.9 commit + test + new CLI command (DEV #54)
- [ ] 1.10 commit + lint guard pass (DEV #33, #34, #37 audit)
- [ ] `make check` vert (lint + test + module-size + pragma-discipline)
- [ ] `personalscraper library-index --mode full` puis `library-reconcile` →
      `merkle_drift=[]`, `path_missing=0`
- [ ] `personalscraper library init-canonical` (or equivalent) populates
      `canonical_provider` on ≥ 50% of items
- [ ] `rg "sqlite3\.connect\(" personalscraper/ --type py | grep -v "db.py"` returns zero

**Phase gate commit** : `chore(tech-debt): phase 1 gate — foundations BDD/indexer + PRAGMA discipline + 5 bonus DEVs`
