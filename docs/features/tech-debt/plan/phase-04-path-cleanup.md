# Phase 4 — Path detection + cleanup phantoms

**Effort** : 2 jours
**Theme** : nettoyer les phantoms BDD, valider les invariants drift en production.

## Gate

- Phase 1 commited (drift mechanism active)
- Phase 2 commited (`library-scan` exists pour re-créer media_item manquants)

## Sub-phases

### 4.1 Path missing detector (MUST-4 / BD-C)

**Site** : `personalscraper/indexer/reconcile.py` — ajouter détecteur `detect_path_missing`.

**Implementation** :

```python
def detect_path_missing(conn: sqlite3.Connection) -> list[int]:
    """Return path.id values whose `disk.mount_path + rel_path` no longer exists on FS."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT p.id, p.disk_id, p.rel_path, d.mount_path
          FROM path p JOIN disk d ON d.id = p.disk_id
         WHERE d.is_mounted = 1
        """
    ).fetchall()
    missing: list[int] = []
    for r in rows:
        abs_path = Path(r["mount_path"]) / r["rel_path"]
        if not abs_path.exists():
            missing.append(int(r["id"]))
    return missing
```

Ajouter au `ReconcileReport` + au scope `--scope path_missing`.

**Commit** : `feat(tech-debt): add path_missing detector to library-reconcile (MUST-4)`

### 4.2 `--scope path_missing --enqueue-repairs` → soft-delete (BD-D)

**Site** : `personalscraper/indexer/reconcile.py` + `library-repair`.

**Implementation** : quand un path est missing, enqueue `repair_queue(scope='path', scope_id=path.id,
action='soft_delete_subtree')`. `library-repair` consomme et soft-delete via `file_repo.soft_delete`
tous les media_file dans ce path.

**Commit** : `feat(tech-debt): path_missing → repair_queue soft_delete_subtree (BD-D)`

### 4.3 Cleanup 8 phantom shows (MUST-18 / BD-F) — one-shot script

**Site** : `scripts/cleanup-2026-05-21-orphan-shows.py` (à archiver après usage)

**Actions** :

1. **5 phantom paths** (Bloqués, Avez-vous, Corneil et Bernie, Star Trek Enterprise, Star Trek
   Voyager) : invoke library-reconcile + library-repair via 4.2 pour soft-delete.
2. **2 FS-exists** (Monk, Squid Game) : lancer `personalscraper library-scan --disk 1` pour
   re-créer leurs `media_item` + linker leurs files via `library-index --mode incremental`.

**Validation** : `library-reconcile` retourne `path_missing=0`, `files_without_release ≈ 6655`
(les sidecars légitimes restants).

**Commit** : `chore(tech-debt): cleanup 8 phantom shows script + run report`

### 4.4 Audit FK orphans manuel (SH-5 / BD-AE)

**Script** : `scripts/audit-fk-orphans.py` — un SELECT par FK contrainte du schema. Log
chaque orphan trouvé. Aurait dû être 0 grâce à CASCADE applicatif, mais à vérifier post Phase 1
FK ON.

**Commit** : `test(tech-debt): audit FK orphans (SH-5)`

### 4.5 Hard-delete protections audit (SH-4 / BD-M)

```bash
rg -n "DELETE FROM media_item|DELETE FROM media_release|DELETE FROM season|DELETE FROM episode" --type py personalscraper/
```

Pour chaque site trouvé : remplacer par soft-delete (set `deleted_at`) si possible. Sinon
documenter pourquoi hard-delete est nécessaire.

**Commit** : `refactor(tech-debt): replace hard-deletes with soft-deletes where applicable (SH-4)`

### 4.6 library-reconcile flags clarif (SH-15 / DEV #10 / CL-C)

**Site** : `personalscraper/indexer/commands/reconcile.py` + `library-reconcile --help`.

**Actions** :

- Add explicit `--read-only` (default) and `--enqueue-repairs` (opt-in) flags. `--dry-run`
  alias for `--read-only`.
- Update help text to mention "read-only by default".

**Commit** : `feat(tech-debt): library-reconcile --read-only / --dry-run flag aliases (DEV #10)`

## Phase 4 Gate

- [ ] 4.1 `library-reconcile --scope path_missing` returns IDs
- [ ] 4.2 `library-repair` drains path_missing → soft-deletes
- [ ] 4.3 8 phantom shows resolved (5 soft-deleted + 2 re-indexed)
- [ ] 4.4 FK orphans audit script run, zero orphans
- [ ] 4.5 Hard-deletes audited + migrated
- [ ] 4.6 library-reconcile --dry-run alias works
- [ ] `make check` vert
- [ ] `library-reconcile` returns `total_findings <= 6655` (sidecars only)

**Phase gate commit** : `chore(tech-debt): phase 4 gate — path detection + cleanup`
