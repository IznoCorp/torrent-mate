# Phase 5 — Conformity + monolithic Protocols drop + GC + library-doctor

**Effort** : 2 jours
**Theme** : honorer les ACCEPTANCE_FAIL provider-ids restantes + outillage opérationnel.

## Gate

- Phase 1 + Phase 2 commited (foundations + library-scan exists)
- ACCEPTANCE provider-ids #3 partial done par Phase 2.6 backfill-ids first run

## Sub-phases

### 5.1 Drop monolithic Protocols (MUST-14 / CF-B / ACCEPTANCE_FAIL provider-ids #6)

**Sites cibles** :

- `personalscraper/api/torrent/_contracts.py:124 — class TorrentClientFull(Protocol)`
- `personalscraper/api/metadata/_base.py:267 — class MetadataProvider(Protocol)`

**Steps** :

1. **Audit callers** :

   ```bash
   rg -n "MetadataProvider\b" --type py personalscraper/ tests/
   rg -n "TorrentClientFull\b" --type py personalscraper/ tests/
   ```

2. **Migrer chaque caller** vers les capability protocols atomiques :
   - `MetadataDetails` (get_movie/get_tv)
   - `MetadataSearch` (search_movie/search_tv)
   - `MetadataArtwork` (get_images)
   - `TorrentBasic` (list/get/add/delete)
   - `TorrentFilesByHash` (get_files_by_hash)
   - autres capabilities atomiques selon provider-ids DESIGN

3. **Drop la définition** : supprimer les classes + drop les tests qui asseoient les
   monolithic Protocols.

**Commits** : un par caller migré + `refactor(tech-debt): drop MetadataProvider Protocol (CF-B)`

- idem TorrentClientFull.

### 5.2 `library-gc` CLI command (SH-7 / BD-W / CL-N)

**Site** : `personalscraper/commands/library/gc.py` (nouveau)

**Implementation** :

```python
@app.command("library-gc")
@cli_telemetry
@handle_cli_errors
def library_gc(
    ctx: typer.Context,
    older_than_days: int = typer.Option(30, "--older-than-days"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Garbage-collect old index_outbox rows (status=done, processed_at < cutoff)."""
    # SELECT count → log → DELETE if not dry_run
```

**Commit** : `feat(tech-debt): library-gc CLI for index_outbox cleanup (SH-7)`

### 5.3 `library-doctor` CLI command (SH-8 / BD-Y / CL-M)

**Site** : `personalscraper/commands/library/doctor.py` (nouveau)

**Health checks** :

- `PRAGMA integrity_check` returns `ok`
- `PRAGMA foreign_keys` returns 1
- `PRAGMA foreign_key_check` returns zero rows
- schema_version table coherent with user_version
- scan_run lifecycle : no stuck `running` > 1h
- repair_queue : pending < threshold
- index_outbox : oldest pending < threshold (lag)
- merkle_drift = 0 (live recompute vs stored)
- canonical_provider populated > 50% of items (post Phase 2.6)
- 0 phantom paths (post Phase 4)

Sortie tabulaire + exit code 0 si tous OK, non-0 sinon. JSON output via `--format json` (lié
Phase 6.1).

**Commit** : `feat(tech-debt): library-doctor health check CLI (SH-8)`

### 5.4 ACCEPTANCE re-exercise process docs (SH-16 / CF-C, CF-E, CF-I, CF-J)

**Site** : `docs/reference/feature-lifecycle.md` (nouveau)

**Contenu** :

- Phase gate ≠ deployment
- Convention "ACCEPTANCE criteria DOIVENT être des commandes shell exécutables"
- Post-merge ACCEPTANCE re-exercise obligatoire
- ACCEPTANCE_FAIL alerting CI (futur — 0.17+)

* update `.claude/CLAUDE.md` ou `docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md`
  avec la règle.

**Commit** : `docs(tech-debt): feature-lifecycle conventions + ACCEPTANCE format rule (SH-16)`

### 5.5 Documentation runbook post-merge (SH-2 + CF-H)

**Site** : `docs/reference/runbook-post-merge.md` (nouveau)

**Contenu** :

- Pour chaque feature touchant schéma BDD / config / CLI : actions post-merge
- Validation à exécuter (par exemple "lancer backfill-ids puis library-doctor")
- Alarmes / monitoring à configurer

Cas concret tech-debt : commands à lancer post-0.16.0 merge.

**Commit** : `docs(tech-debt): runbook post-merge for schema/config/CLI changes (SH-2)`

## Phase 5 Gate

- [ ] 5.1 `MetadataProvider` + `TorrentClientFull` supprimés, callers migrés, tests verts
- [ ] 5.2 `library-gc --help` exit 0, GC fonctionne
- [ ] 5.3 `library-doctor` exit 0 sur DB saine, exit non-0 sur DB cassée (testé via fixture)
- [ ] 5.4 + 5.5 docs commitées
- [ ] `make check` vert
- [ ] `rg "^class MetadataProvider\b|^class TorrentClientFull\b" personalscraper/` retourne 0

**Phase gate commit** : `chore(tech-debt): phase 5 gate — conformity + monolithic Protocols drop`
