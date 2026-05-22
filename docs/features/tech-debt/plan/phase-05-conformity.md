# Phase 5 — Conformity (Protocol drop + tests refactor + ratings Pydantic) + GC + library-doctor

**Effort** : 2-3 jours (revised — DEV #29, #38, #30 added)
**Theme** : honorer les ACCEPTANCE_FAIL provider-ids restantes + outillage opérationnel +
fix tests qui asseoient les Protocols à dropper.

## Coverage matrix

| Item                                  | Sub-phase | Source pattern |
| ------------------------------------- | --------- | -------------- |
| MUST-14 / CF-B / ACCEPTANCE #6        | 5.1       | P28            |
| SH-7 / BD-W / CL-N                    | 5.2       | P17            |
| SH-8 / BD-Y / CL-M                    | 5.3       | P12, P24       |
| SH-16 / CF-C/E/I/J                    | 5.4       | P23, P32       |
| SH-2 / BD-R / CF-H                    | 5.5       | P30            |
| **DEV #29 tests Protocol refactor**   | 5.6 NEW   | P28            |
| **DEV #38 TorrentClientFull 2nd vec** | 5.7 NEW   | P28            |
| **DEV #30 ratings Pydantic boundary** | 5.8 NEW   | (scope-creep)  |

DESIGN sections impacted : §10 CLI (library-doctor, library-gc), §11 architecture (Protocol
discipline), §12 doc, §14 success criteria, §13 promise lifecycle.

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

### 5.6 Refactor tests qui asseoient le monolithic Protocol (DEV #29)

**Site** : `tests/unit/test_api_metadata_base.py:182-230`

**Bug** : `MetadataProvider(Protocol)` (api/metadata/\_base.py:267) ne peut pas être simplement
`git rm` parce que `tests/unit/test_api_metadata_base.py` fait des assertions `isinstance`
pinning le contrat. Drop la définition casse ces tests.

**Fix** : migrer les tests vers atomic protocol assertions :

```python
# Old (to drop)
def test_metadata_provider_protocol_contract():
    assert isinstance(client, MetadataProvider)

# New (per capability)
def test_metadata_client_supports_movie_details():
    assert isinstance(client, MovieDetailsProvider)
def test_metadata_client_supports_tv_details():
    assert isinstance(client, TvDetailsProvider)
# ... etc per capability used by each client
```

À faire AVANT 5.1 commit (sinon 5.1 casse).

**Commit** : `test(tech-debt): refactor MetadataProvider Protocol tests to atomic capabilities (DEV #29)`

### 5.7 TorrentClientFull migration (DEV #38)

**Site** : `personalscraper/api/torrent/_contracts.py:124 — class TorrentClientFull(Protocol)`

- `personalscraper/api/torrent/_factory.py:72` (factory cast)

**Bug** : `TorrentClientFull` est un composite Protocol qui re-crée la monolithic shape
sous un autre nom. provider-ids ACCEPTANCE #6 partiel viol via ce 2ᵉ vector.

**Fix** :

1. Identifier les callers via `rg "TorrentClientFull" --type py`
2. Pour chaque caller, identifier les capacités réellement utilisées
3. Remplacer `TorrentClientFull` par `Union[TorrentBasic, TorrentFilesByHash, …]` ou `Protocol`
   intersection composite explicite avec les capacités utilisées par CE caller
4. Drop `class TorrentClientFull` une fois tous les callers migrés
5. `_factory.py:72` retourne désormais le type le plus précis (e.g.
   `QBitClient | TransmissionClient` direct si applicable)

**Commit** : `refactor(tech-debt): drop TorrentClientFull composite, narrow factory returns (DEV #38)`

### 5.8 Ratings flow Pydantic boundary (DEV #30)

**Sites** :

- `personalscraper/scraper/tv_service.py:90-163`
- `personalscraper/scraper/movie_service.py`
- `personalscraper/scraper/_xref.py`
- `personalscraper/scraper/nfo_generator.py:200-208`

**Bug** : provider-ids feature a créé `ExternalIds` + `ProviderIds` Pydantic models (phase 7.4)
mais le scraper passe toujours `imdb_id`/`tmdb_id` flat positional. Scope-creep.

**Fix** : remplacer les paramètres flat par Pydantic models au scraper boundary :

```python
# Old
def _generate_nfo(title, imdb_id: str, tmdb_id: str, ratings: list[dict]): ...

# New
from personalscraper.scraper.models import ExternalIds, Ratings
def _generate_nfo(title, ids: ExternalIds, ratings: Ratings): ...
```

Migration progressive : pour chaque site, accept both old + new signatures via overload pendant
1 cycle, puis drop old en 0.17.

**Commit** : `refactor(tech-debt): use ExternalIds + Ratings Pydantic at scraper boundary (DEV #30)`

## Phase 5 Gate

- [ ] 5.1 `MetadataProvider` + `TorrentClientFull` supprimés, callers migrés (MUST-14, CF-B, DEV #38)
- [ ] 5.2 `library-gc --help` exit 0, GC fonctionne (SH-7)
- [ ] 5.3 `library-doctor` exit 0 sur DB saine (SH-8)
- [ ] 5.4 + 5.5 docs commitées (SH-2, SH-16)
- [ ] 5.6 tests Protocol refactorisés en atomic (DEV #29) — précondition de 5.1
- [ ] 5.7 callers TorrentClientFull migrés (DEV #38)
- [ ] 5.8 scraper boundary utilise Pydantic models (DEV #30)
- [ ] `make check` vert
- [ ] `rg "^class MetadataProvider\b|^class TorrentClientFull\b" personalscraper/` retourne 0
- [ ] provider-ids ACCEPTANCE #6 re-graded ✅

**Phase gate commit** : `chore(tech-debt): phase 5 gate — conformity (Protocols drop + tests refactor + ratings Pydantic) + GC + doctor`
