# Phase 1 — Foundations BDD/indexer

**Effort** : 2-3 jours
**Theme** : restaurer le drift mechanism, activer les invariants FK, fixture E2E.

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

- `personalscraper/indexer/db.py — open_db()` ou équivalent

**Implementation** :

Pré-check + activation. **CRITIQUE** : un `PRAGMA foreign_key_check;` doit retourner zero
AVANT d'activer FK ON, sinon les opérations qui passaient silencieusement vont échouer.

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

## Phase 1 Gate

- [ ] 1.1 commit + test
- [ ] 1.2 commit + test
- [ ] 1.3 commit + test miss-strike lifecycle PASS
- [ ] 1.4 commit + test scan→reconcile=clean PASS
- [ ] 1.5 commit + migration 006 applies cleanly
- [ ] 1.6 commit
- [ ] `make check` vert (lint + test + module-size)
- [ ] `personalscraper library-index --mode full` puis `library-reconcile` → `merkle_drift=[]`,
      `path_missing=0` (sur DB cleanée si nécessaire)

**Phase gate commit** : `chore(tech-debt): phase 1 gate — foundations BDD/indexer`
