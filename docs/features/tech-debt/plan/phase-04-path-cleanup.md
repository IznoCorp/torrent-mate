# Phase 4 — Path detection + cleanup phantoms + paranoia branch

**Effort** : 2-3 jours (revised — DEV #31 added)
**Theme** : nettoyer les phantoms BDD, valider les invariants drift en production, wire
la §17.1 paranoia branch (DEV #31).

## Coverage matrix

| Item                             | Sub-phase | Source pattern      |
| -------------------------------- | --------- | ------------------- |
| MUST-4 / BD-C                    | 4.1       | P13                 |
| BD-D                             | 4.2       | P13                 |
| MUST-18 / BD-F / DEV #17 + #12   | 4.3       | P13                 |
| SH-5 / BD-AE                     | 4.4       | P15 audit           |
| SH-4 / BD-M                      | 4.5       | P13                 |
| SH-15 / DEV #10 / CL-C           | 4.6       | P20                 |
| **DEV #31 paranoia branch wire** | 4.7 NEW   | P34 SAFETY_NET_DEAD |

DESIGN sections impacted : §9 BDD lifecycle invariants, §16 Safety net E2E (DEV #31 is
the second-most critical safety-net-dead instance after DEV #18).

## Gate

- **READ FIRST** : `docs/features/tech-debt/AGENT_BRIEFING.md`
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

**Site** : `personalscraper/commands/library/audit.py` (où vit la commande `@app.command("library-reconcile")`, ligne 18) + `library-reconcile --help`. Path corrigé R4 — l'audit disait `indexer/commands/reconcile.py` qui n'existe pas.

**Actions** :

- Add explicit `--read-only` (default) and `--enqueue-repairs` (opt-in) flags. `--dry-run`
  alias for `--read-only`.
- Update help text to mention "read-only by default".

**Commit** : `feat(tech-debt): library-reconcile --read-only / --dry-run flag aliases (DEV #10)`

### 4.7 Wire §17.1 paranoia branch (DEV #31)

**Site** :

- `personalscraper/indexer/outbox/_apply.py` — must call `log_repo.insert_scan_event` on
  successful drain
- `personalscraper/indexer/scanner/_modes/quick.py` — already queries `scan_event WHERE event
LIKE 'outbox.%'` (the safety net)

**Bug** (DEV #31) : `_modes/quick.py` queries for `scan_event` rows tagged `outbox.move` /
`outbox.nfo_write` etc. as a paranoia branch (catch "pipeline crashed between FS mutation
and outbox insert"). But `outbox/_drain.py` + `_apply.py` only emit structlog events,
never insert `scan_event` rows. Live DB confirms : 0 outbox-prefixed scan_event rows after
33 scan runs. Safety net is dead.

**Fix** : on each successful drain step in `_apply.py`, insert a matching scan_event row in
the same transaction as `processed_at=now` :

```python
# After successful drain side-effect (FS mutation done + DB row updated)
log_repo.insert_scan_event(
    conn,
    event="outbox.move",  # or 'outbox.nfo_write', 'outbox.artwork', etc.
    payload_json=json.dumps({"disk_id": disk_id, "rel_path": rel_path, "filename": filename}),
    ...
)
```

**Test E2E (CRITICAL)** : `test_paranoia_branch_catches_crash_between_fs_and_db` —

1. Mock `_apply.py` to crash AFTER FS mutation, BEFORE outbox row update + scan_event insert
2. Run quick scan, assert paranoia branch re-walks the affected path
3. Without DEV #31 fix : test fails (paranoia branch sees 0 outbox events → no re-walk).

**Pattern P34 SAFETY_NET_DEAD enforcement** : add to test policy "tout safety net DOIT avoir
un test E2E qui force le scénario qu'il adresse + assert que le filet a déclenché".

**Commit** : `fix(tech-debt): wire outbox.* scan_event rows so paranoia branch fires (DEV #31)`

## Phase 4 Gate

- [ ] 4.1 `library-reconcile --scope path_missing` returns IDs (MUST-4)
- [ ] 4.2 `library-repair` drains path_missing → soft-deletes (BD-D)
- [ ] 4.3 8 phantom shows resolved (5 soft-deleted + 2 re-indexed) (MUST-18, DEV #17, DEV #12)
- [ ] 4.4 FK orphans audit script run, zero orphans (SH-5)
- [ ] 4.5 Hard-deletes audited + migrated (SH-4)
- [ ] 4.6 library-reconcile --dry-run alias works (DEV #10)
- [ ] 4.7 paranoia branch E2E test PASS (DEV #31)
- [ ] `make check` vert
- [ ] `library-reconcile` returns `total_findings <= 6655` (sidecars only)
- [ ] Live DB has outbox-prefixed scan_event rows after first dispatch post-fix

**Phase gate commit** : `chore(tech-debt): phase 4 gate — path detection + cleanup + paranoia branch wire (DEV #31)`
