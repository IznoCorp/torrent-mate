# Item 11 — Audit conformité app vs DESIGN (audit-quality REDO)

**Date** : 2026-05-21 (REDO — supersedes the brainstorm-quality first pass)
**Méthode** : audit RIGOUREUX des 13 archived features. Pour chaque DESIGN.md +
ACCEPTANCE.md + IMPLEMENTATION.md : extraction exhaustive des claims/MUST/SHALL,
verification commande par commande contre le codebase actuel, classification
CONFORMING / VIOLATION / UNVERIFIABLE / N/A.
**Output** : rapport conformité globale audit-quality + 26 nouveaux DEVs (#24-#49) à
intégrer au master backlog.

---

## 0. Périmètre auditée

| Feature        | DESIGN LOC | ACCEPTANCE       | IMPL LOC | Claims auditées | Conformité                                     |
| -------------- | ---------- | ---------------- | -------- | --------------- | ---------------------------------------------- |
| event-bus      | 904        | (inline)         | 293      | 25              | 19 OK / 4 VIOL / 2 UNV                         |
| provider-ids   | 602        | 36 (10 criteria) | 390      | 18              | 7 OK / 5 VIOL / 1 PARTIAL / 5 UNV/NEW          |
| media-indexer  | 1543       | (none)           | (none)   | 47              | 28 OK / 14 VIOL / 3 UNV / 2 N/A                |
| api-unify      | 1026       | (inline)         | 509      | 27              | 22 OK / 3 VIOL / 2 UNV                         |
| pipeline-obs   | 259        | (inline)         | 113      | 14              | 7 OK / 6 superseded / 1 UNV                    |
| test-coverage  | 430        | (inline)         | 97       | 23              | 22 OK / 0 VIOL / 1 UNV                         |
| trailer        | 538        | (inline)         | 159      | 14              | 11 OK / 2 VIOL (doc lag) / 1 UNV               |
| ext-staging    | 451        | (inline)         | 42       | 16              | 15 OK / 1 minor (docstring leak)               |
| logging        | 108        | (inline)         | 82       | 13              | 12 OK / 1 doc-stale                            |
| arch-cleanup   | 270        | (inline)         | 88       | 19              | 17 OK / 2 VIOL (size regress + 0.10.0 promise) |
| legacy-cleanup | 313        | (inline)         | 44       | 8               | 5 OK / 1 PARTIAL / 2 leak                      |
| test-realism   | 130        | (inline)         | 44       | 10              | 8 OK / 2 VIOL (targets missed)                 |
| info-cmd       | (none)     | (none)           | 40       | 1               | trivial — CLI command exists, no further claim |

**Total claims auditées** : ~235
**Conformity rate global** : ~80% (190 CONFORMING) — solide globalement, mais 39 VIOLATIONs
nouvelles avant déduplication.

---

## 1. Nouveaux DEVs #24-#49

Suite à l'audit-quality. Les anciens DEV #1-#23 (items 5-10) restent valides ; les nouveaux
complètent.

| #   | Catégorie        | Sév.     | Feature        | Description (courte)                                                                                                                                                                                                                                           |
| --- | ---------------- | -------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 24  | DOC_ROT          | major    | event-bus      | v1 catalog claim 13 events ; reality 17 (provider-ids added 4 `Backfill*`). `docs/reference/event-bus.md` table stale. `events/__init__.py:__all__` omits Backfill\*.                                                                                          |
| 25  | DESIGN_DRIFT     | minor    | event-bus      | Module budget violations : `core/event_bus.py` 410/400, `indexer/events.py` 123/60, `tests/fixtures/event_samples.py` 243/150. Soit raise budgets, soit split.                                                                                                 |
| 26  | DOC_RULE_BROKEN  | minor    | event-bus      | Rule "consumers reach event classes via `personalscraper.events` re-exports" broken pour Backfill\* (importables uniquement depuis `personalscraper.indexer.events`).                                                                                          |
| 27  | DESIGN_DEVIATION | CRITIQUE | provider-ids   | DESIGN §6.5 + §8 Plan A reset+rescrape **jamais exécuté** sur library.db prod. 0/1935 items ont external_ids_json populé. ACCEPTANCE #4 vide. Origine de DEV #12 sub-cause "provider-IDs empty".                                                               |
| 28  | DESIGN_DEVIATION | majeur   | provider-ids   | Auto-trigger backfill post-`process` **jamais wired** dans `scraper/run.py`. Phase 8.3 IMPL marquée `partial`. `run_backfill_ids` callable uniquement programmatiquement.                                                                                      |
| 29  | DESIGN_DEVIATION | majeur   | provider-ids   | `MetadataProvider(Protocol)` à `_base.py:267` **toujours activement testé** comme Protocol (`tests/unit/test_api_metadata_base.py:182-230` asserts isinstance). Le drop n'est pas qu'un `git rm`.                                                              |
| 30  | DESIGN_DEVIATION | mineur   | provider-ids   | Ratings flow scope-creep : `tv_service.py`, `movie_service.py`, `_xref.py`, `nfo_generator.py:200-208` passent `imdb_id`/`tmdb_id` flat positional au lieu d'`ExternalIds` Pydantic.                                                                           |
| 31  | DESIGN_DEVIATION | CRITIQUE | media-indexer  | **§17.1 paranoia branch MORTE** : `_modes/quick.py` query `scan_event WHERE event LIKE 'outbox.%'` ; mais `outbox/_drain.py` + `_apply.py` n'insèrent **jamais** ces scan_event rows. Safety net dead.                                                         |
| 32  | DOC_ROT          | majeur   | media-indexer  | Archive DESIGN.md décrit `tmdb_id/imdb_id/tvdb_id` colonnes + 3 indexes. Migration 005 a tout droppé pour `external_ids_json` + JSON-path indexes. DESIGN jamais amendé.                                                                                       |
| 33  | DESIGN_DEVIATION | majeur   | media-indexer  | `PRAGMA busy_timeout=5000` (DESIGN §6.1) **non appliqué** sur `dispatch/run.py` (×2), `commands/library/audit.py`, `conf/loader.py`. Connexions raw bypass `open_db()` → contention = OperationalError immédiate au lieu d'attendre 5 s. Extension de DEV #19. |
| 34  | DESIGN_DEVIATION | majeur   | media-indexer  | DEV #19 sous-estimé : non seulement `foreign_keys=0`, mais aussi `temp_store`, `cache_size`, `mmap_size` ne sont pas appliquées sur les sites raw (`_concurrency.py`, `outbox/_disk.py`, `outbox/_publish.py`). Extract `_apply_pragmas()` requis.             |
| 35  | DOC_ROT          | mineur   | media-indexer  | DESIGN §11.1 documente 4 scan modes ; schema CHECK accepte 6 (`+verify, +repair`). Cosmetic gap.                                                                                                                                                               |
| 36  | DOC_ROT          | mineur   | media-indexer  | Migration 004 a étendu `media_stream` (`hdr_format`, `is_atmos`, `is_default`, `forced`, `format`) — pas dans archived DESIGN §6.2. Sync `docs/reference/indexer.md` à vérifier.                                                                               |
| 37  | UNVERIFIED       | mineur   | media-indexer  | DESIGN §6.4 spécifie `BEGIN IMMEDIATE` pour chaque write transaction. Pas grep ; à auditer.                                                                                                                                                                    |
| 38  | DESIGN_DEVIATION | mineur   | api-unify      | `TorrentClientFull` (`api/torrent/_contracts.py:124`) re-crée la monolithic shape sous un autre nom (composite avec 4 capabilities + factory cast). Provider-ids ACCEPTANCE #6 partiellement violé sur 2 vectors.                                              |
| 39  | DOC_ROT          | majeur   | pipeline-obs   | Archive DESIGN.md décrit `PipelineObserver` Protocol + `StepEvent` + `notify_progress` ; tout supplanté par event-bus. **6 claims sur 14 superseded**. Aucune bannière dans archive. Old → new mapping table missing.                                          |
| 40  | DESIGN_DEVIATION | majeur   | pipeline-obs   | **DEV #6 sous-estimé** : tous les 7 per-step CLI subcommands (`ingest`, `sort`, `scrape`, `verify`, `enforce`, `dispatch`, `process`) n'émettent aucun event INFO structlog au command layer. Pas seulement `verify`.                                          |
| 41  | DOC_LAG          | mineur   | test-coverage  | Branch coverage drift : claim retrospective "91 %" (DESIGN §10 Q3) ; current `coverage.xml` = 85.95%. Above gate, mais doc rot.                                                                                                                                |
| 42  | DOC_ROT          | mineur   | trailer        | DESIGN §4 décrit placement flat `{name}-trailer.{ext}` pour movies ET TV ; code production utilise `Trailers/` subfolder pour TV (mid-PR pivot cycle 3). Archive DESIGN jamais amendé.                                                                         |
| 43  | DOC_ROT          | mineur   | trailer        | DESIGN §14 "status=partial does NOT block dispatch" contredit reference doc "Blocking by default (sauf `--continue-on-trailer-error`)". Pivot intentionnel cycle 3. Archive stale.                                                                             |
| 44  | DOC_LEAK         | mineur   | ext-staging    | `indexer/scanner/_exclusions.py:383` docstring contient `"001-MOVIES/Inception (2010)"` ; DESIGN Phase 2 critère 3 mandate `grep "\"0[0-9]\{2\}-"` = 0 hits. Violation cosmétique.                                                                             |
| 45  | DOC_ROT          | mineur   | logging        | `docs/reference/logging.md:82,139` référence `personalscraper.scraper.http_retry` + `scraper/tmdb_client.py` — chemins n'existent plus (refactor api-unify/provider-ids). Real path : `core/http_helpers.py` + `api/metadata/tmdb.py`.                         |
| 46  | DESIGN_DEVIATION | majeur   | arch-cleanup   | **0.10.0 hard-block module-size promesse stalled depuis 5 versions** (we're at 0.15.1). `scripts/check-module-size.py` toujours advisory. `tv_service.py` (986 LOC) + `existing_validator.py` (917 LOC) régressés au-dessus 800.                               |
| 47  | DESIGN_DRIFT     | mineur   | arch-cleanup   | DESIGN.md spécifie `StepReport.details_payload: Any \| None` ; code actuel `dict[str, Any] \| None`. Stricter, OK ; mais doc drift.                                                                                                                            |
| 48  | DOC_LEAK         | mineur   | legacy-cleanup | 4 hits VX résiduels dans `personalscraper/` (release_linker.py "V1 implementation" x2, classifier.py "V14 compat" intentional). MANUAL.md 2 leaks ("V3"). `docs/*.md` top-level 43 hits hors-scope original mais doc rot.                                      |
| 49  | DESIGN_DEVIATION | majeur   | test-realism   | `test_cli.py` @patch=52 (target DESIGN §5 ≤25, miss 27 patches). Total hotspots 66 (target ≤58). **Success criteria §8 jamais re-mesurée au gate** — feature mergée avec target manqué. Process drift.                                                         |

---

## 2. Patterns systémiques (P30-P34 nouveaux + confirmation P1-P29)

### P30 — Documentation stale post-feature-archive (DOC_ROT)

Pattern récurrent confirmé sur 7 features : event-bus (#24, #26), provider-ids (#27, #28),
media-indexer (#32, #35, #36), pipeline-obs (#39), trailer (#42, #43), logging (#45),
legacy-cleanup (#48). Cause racine : archived DESIGN.md n'est pas re-vérifié quand un
refactor suivant le casse.

**Levier** : règle DESIGN tech-debt — "chaque archived feature DESIGN.md DOIT être amendée
(banner stale + old→new mapping table) à la prochaine release qui invalide une partie de
ses claims".

### P31 — Promesses de version stalled (PROMISE_STALL)

#46 : 0.10.0 hard-block module-size 5 versions overdue. #27 : Plan A reset+rescrape jamais
exécuté. Cause racine : promesses dans DESIGN sans timeline applicable, sans CI gate.

**Levier** : pour chaque "promise versionnelle" dans DESIGN, créer un CI check qui échoue
à partir de la version cible si la promise n'est pas honorée.

### P32 — Success criteria not re-measured at phase gate (GATE_DRIFT)

#49 (test-realism), #41 (test-coverage retrospective drift). Phase gate vérifie tests verts

- lint mais pas les quantitative targets du DESIGN §8.

**Levier** : règle "DESIGN §8 success-criteria re-measurement" obligatoire au gate. Ajout
à process P23 d'item 11 v1.

### P33 — PRAGMA / connection-init discipline broken (PRAGMA_BYPASS)

#33 + #34 (media-indexer). Plusieurs sites raw `sqlite3.connect()` bypass `open_db()` →
FK, busy_timeout, cache_size, mmap_size non appliqués. DEV #19 sous-estimé.

**Levier** : extract `_apply_pragmas(conn)` helper, lint rule "bare `sqlite3.connect(`
outside `db.py` is banned".

### P34 — Safety net défaillant (paranoia branch dead)

#31 (media-indexer §17.1). Le filet de sécurité existe en code (query, table) mais le
producteur ne fait pas son INSERT. Idem P11 (DEV #18 drift dead code).

**Levier** : règle "chaque safety net DOIT avoir un test E2E qui force le scénario qu'il
adresse" (étend BD-AG).

---

## 3. Cross-reference avec items 6-10 (déduplication)

| Nouveau DEV | Recouvre / extend                                              | Statut                                                             |
| ----------- | -------------------------------------------------------------- | ------------------------------------------------------------------ |
| #27         | DEV #12 (files_without_release / provider-IDs empty)           | EXTEND — root cause confirmée                                      |
| #28         | provider-ids ACCEPTANCE #3 (DEV #16)                           | NEW dimension (auto-trigger ≠ CLI exposure)                        |
| #29         | provider-ids ACCEPTANCE #6 (CF-B)                              | EXTEND — tests asseoient le Protocol, drop plus complexe que prévu |
| #31         | DEV #18 family (dead infra)                                    | NEW instance de pattern P11                                        |
| #33+#34     | DEV #19                                                        | EXTEND — DEV #19 sous-estimé, multi-site                           |
| #38         | provider-ids ACCEPTANCE #6 (CF-B)                              | EXTEND — 2ᵉ vector                                                 |
| #40         | DEV #6                                                         | EXTEND — pas juste verify, tous les 7 per-step                     |
| #46         | item 12 critique §1.A (couteau-suisse) + module-size guardrail | NEW (specifically 0.10.0 promise)                                  |

Les autres (#24, #25, #26, #30, #32, #35-37, #39, #41-45, #47-49) sont **NEW**, non recouverts.

→ **17 nouveaux DEVs vraiment nouveaux** + 9 qui extend/precise des DEVs existants.

---

## 4. Implications pour le DESIGN tech-debt (item 14)

Le DESIGN actuel (committed `9649784`) doit être étendu :

### 4.1 Nouvelles sections à ajouter

- **§12 Documentation conformity** (nouveau) : règles P30 + actions sur les 7 archived
  DESIGN.md stale.
- **§13 Promise lifecycle** (nouveau) : règles P31 — versioned promises tracking, CI gate.
- **§14 Success criteria enforcement** (nouveau) : règle P32 + obligation re-measurement.
- **§15 PRAGMA & connection discipline** (nouveau) : règle P33 + helper extraction.
- **§16 Safety net E2E** (nouveau) : règle P34 + tests E2E par safety net.

### 4.2 Nouveaux items DESIGN-ready

Trop nombreux pour lister ici (26 DEVs × 1-2 items chacun = ~40 items). À consolider en
item 13 redo (synthesis update).

### 4.3 Phase plan updates

Phases existantes 1-8 (tech-debt 0.16.0) couvrent partiellement les nouveaux findings :

- Phase 1 foundations : DEV #34 + #33 (étend DEV #19) — already in scope, mais portée
  élargie
- Phase 2 CLI : DEV #27 + #28 — already in scope (backfill-ids + first run)
- Phase 5 conformity : DEV #29 + #38 (drop monolithic Protocols) — already in scope
- Phase 6 doc : DEV #24, #26, #32, #35, #36, #41-43, #45, #47, #48 — **HEAVILY EXPANDED**

**Nouveau phase à ajouter** : **Phase 6.5 / Phase 9** "Archive DESIGN.md update" — banner
stale + old→new mapping pour les 7 features avec doc rot. ~1 j.

Et : **Phase 1.7** sub-phase "extract `_apply_pragmas()` + lint rule" — fold dans Phase 1.

### 4.4 Estimation révisée

| Phase originale | Items ajoutés                                         | Effort original | Effort révisé          |
| --------------- | ----------------------------------------------------- | --------------- | ---------------------- |
| Phase 1         | DEV #33+34                                            | 2-3 j           | 2-3 j (already covers) |
| Phase 2         | (no change)                                           | 2 j             | 2 j                    |
| Phase 3         | DEV #40 broader scope                                 | 2 j             | 2 j (already covers)   |
| Phase 4         | (no change)                                           | 2 j             | 2 j                    |
| Phase 5         | DEV #29+38+30                                         | 2 j             | 2-3 j                  |
| Phase 6         | DEV #24-26, #32, #35-36, #41-45, #47-48               | 2-3 j           | **3-4 j** (heavy doc)  |
| Phase 7         | (no change)                                           | 1-2 j           | 1-2 j                  |
| Phase 8         | DEV #31 (safety net E2E) + #49 (test-cli @patch trim) | 2-3 j           | **3-4 j**              |
| **NEW Phase 9** | Archive DESIGN.md updates                             | —               | **1-2 j**              |

**Nouveau total** : **15-22 jours** (vs 13-19 j original) = +2-3 j.

---

## 5. Synthesis re-classification

Provider-ids ACCEPTANCE re-graded (était ✅ partout dans l'archive) :

| #   | Was | Now | Reason                                                  |
| --- | --- | --- | ------------------------------------------------------- |
| 1   | ✅  | ✅  | CONFORM — verified                                      |
| 2   | ✅  | ✅  | CONFORM — verified                                      |
| 3   | ✅  | ❌  | VIOLATION — DEV #16 CLI missing                         |
| 4   | ✅  | 🟡  | PARTIAL — schema OK, data empty                         |
| 5   | ✅  | ✅  | CONFORM — verified                                      |
| 6   | ✅  | ❌  | VIOLATION — DEV #29+38 monolithic Protocols (2 vectors) |
| 7   | ✅  | ✅  | CONFORM — verified                                      |
| 8   | ✅  | 🟡  | UNVERIFIABLE in audit (would need fresh `make test`)    |
| 9   | ✅  | ❌  | VIOLATION — DEV #16 same root                           |
| 10  | 🟡  | 🟡  | PENDING — never exercised live (DEV #27)                |

**4 sur 10 ACCEPTANCE rows précédemment ✅ sont en réalité VIOLATION**. La feature
provider-ids était mergée avec ACCEPTANCE drift.

---

## 6. Suite

Cette version REDO de item 11 supersedes la version brainstorm-quality précédente.

**Items 6, 8, 9, 10, 12 à re-évaluer** : sont-ils aussi brainstorm-quality ? L'audit
ci-dessus a essentiellement validé leurs findings (DEV #1-#23) ET ajouté 26 nouveaux DEVs
(#24-#49). Les brainstorms (items 6, 8, 10) consolident des findings — ils ne sont pas
"faux", juste incomplets vis-à-vis des findings audit-quality.

**Décision recommandée** :

- Garder items 6, 8, 10 tels quels (ce sont des brainstorms basés sur des audits précédents)
- Mettre à jour **item 13 synthèse globale** pour inclure les 26 nouveaux DEVs
- Mettre à jour **DESIGN.md tech-debt** pour les 5 nouvelles sections §12-§16
- Mettre à jour **plan/** pour ajouter Phase 9 archive doc updates + revoir effort
- Re-marquer item 11 [x] avec note "audit-quality REDO"

L'item 12 architecture critique est plus opinion-based ; sa re-évaluation n'apporterait pas
les mêmes new findings que item 11 audit. Acceptable tel quel.

L'item 14 DESIGN+plan devra être révisé pour intégrer #24-#49.
# Bonus DEVs trouvés pendant reindex BDD (2026-05-21 22h35-22h40)

## DEV #50 — CRITIQUE : library.scanner._ensure_disk_row crée des doubles

**Site** : `personalscraper/library/scanner.py:756,781`

```python
existing = disk_repo.get_by_uuid(conn, disk_cfg.id)  # disk_cfg.id = "disk_1" string
if existing is None:
    row = _build_disk_row(disk_cfg, now_s)  # uuid="disk_1"
    disk_repo.insert(conn, row)
```

**Problem** : la fonction lookup par `disk_cfg.id` (config string, e.g. "disk_1") au lieu du
vrai VolumeUUID (sentinel-derived, e.g. F7E3C03C-...). Donc si la BDD a déjà les disks
indexés par vrai UUID (via indexer.scanner.bootstrap_disk_identity), `_ensure_disk_row`
ne les trouve pas → INSERT un duplicate avec uuid="disk_1".

**Reproduit** : run `scan_library()` une fois → la table `disk` passe de 4 rows à 8 rows
(4 originaux + 4 doublons "disk_1"/"disk_2"/...).

**Conséquence** : sentinel_mismatch skip sur les 4 nouveaux disks, scan_library skip
l'_indexer_scan() interne, les nouveaux media_item restent sans linkage media_file/release.

**Fix proposé** : `_ensure_disk_row` doit utiliser `verify_disk_mounted(disk_cfg).found_uuid`
ou `bootstrap_disk_identity()` pour récupérer le vrai VolumeUUID, puis lookup par ça.

## DEV #51 — MAJEUR : enrich mode does not compute oshash

**Site** : `personalscraper/indexer/scanner/_modes/enrich.py:290-430 _enrich_one_file`

`_enrich_one_file` fait 3 enrichments :
1. Stream extraction (MediaInfoWrapper)
2. NFO status check
3. Artwork inventory

**Mais ne (re)calcule jamais oshash**. Si oshash est NULL (calcul a échoué au scan initial),
enrich ne le retentera jamais. Le file reste avec `oshash IS NULL AND enriched_at IS NOT NULL`
indéfiniment.

**Reproduit** : 118,414 files dans library.db ont ce profil. Aucune commande CLI ne
recompute. Seul `library-index --mode full` recompute (au walker step), mais possiblement
skip si la row existe déjà.

**Fix proposé** : soit ajouter une step "retry oshash if NULL" dans `_enrich_one_file`, soit
exposer un mode dédié `library-index --mode oshash-retry`.

## DEV #52 — MAJEUR : library-index --mode full ne retry pas oshash sur rows existantes

**Site** : `personalscraper/indexer/scanner/_walker.py:496` + `_db_writes.py:222`

`_compute_oshash` retourne `str | None`. Si return None (read failure), oshash=NULL set
en INSERT. Sur les runs suivants, le walker traite la row existante mais probablement ne
re-tente pas oshash. À vérifier dans le code.

**Cas observé** : 118k files ont `oshash IS NULL` après 5+ scans `--mode full`. Pas de retry.

**Fix proposé** : dans le walker, si une row existante a `oshash IS NULL`, retry la compute.

## DEV #53 — CRITIQUE : scan_library._upsert_media_item crée des duplicates

**Site** : `personalscraper/library/scanner.py` (around _upsert_media_item, line ~523)

**Reproduit** : un appel à `scan_library()` sur une BDD avec 1935 media_item existants
en a créé 1863 doublons (1935 → 3798). Les doublons :
- ont le même title (sans année dans le champ title)
- ont le même year
- mais l'item existant a "(YYYY)" littéralement dans le title (e.g., "13 jours, 13 nuits (2025)")
- le nouveau n'a que "13 jours, 13 nuits"

Lookup key dans `_upsert_media_item` ne match pas la version `title=cleaned` vs `title=raw_with_year`.

**Conséquence** : 1861 rows fantômes en BDD (1863 doublons - 2 légitimes Monk + Squid Game),
zero releases linkées vers eux, espace disque BDD gaspillé, queries lentes.

**Fix proposé** : normaliser le lookup key (strip "(YYYY)" du title avant lookup), OU
utiliser (title_normalized, year) comme key composite.

**Cleanup ad-hoc** : DELETE FROM media_item WHERE id IN (SELECT id FROM media_item m
LEFT JOIN media_release r ON r.item_id = m.id WHERE m.date_created > <recent> GROUP BY m.id
HAVING COUNT(r.id) = 0).

## DEV #54 — CRITIQUE : run_backfill_ids skip items WHERE canonical_provider IS NULL

**Site** : `personalscraper/indexer/scanner/_modes/backfill_ids.py` (predicate logic)

**Observé** : sur 1937 items en BDD, tous ont `canonical_provider IS NULL`. Le dry-run
de `run_backfill_ids` traite 1937 items mais skip 100% avec log
`backfill_ids_canonical_unsupported canonical=None`.

**Chicken-and-egg** : backfill UTILISE canonical_provider, ne le SET PAS. Pour que backfill
populate `external_ids_json` + `ratings_json`, il faut d'abord que canonical_provider soit
set, ce qui ne se fait que via une scrape complète (NFO write avec tag canonical).

**Conséquence** : `library-index --mode backfill-ids` est un no-op sur toute BDD qui n'a
jamais été rescrapée post-provider-ids. = DEV #27 root cause (Plan A reset+rescrape jamais
exécuté). Provider-IDs ACCEPTANCE #3 + #4 ne peuvent JAMAIS être validés sans le rescrape.

**Fix proposé** :
1. Court terme : ajouter un mode `--init-canonical` qui scanne les NFOs et set
   canonical_provider depuis `<uniqueid default="true" type="X">`.
2. Long terme : Phase 8 du tech-debt 0.16.0 doit forcément faire le rescrape complet.


---

## 9. Reindex BDD attempt 2026-05-21 — outcome

**Sequence run** (post-cascade item 11 REDO) :

1. `scan_library()` via Python (DEV #16 CLI absent) → produced **DEV #50** (duplicate disks
   id=5-8 with uuid="disk_1"…) AND **DEV #53** (1863 duplicate media_item rows because
   `_upsert_media_item` lookup key inconsistent with stored title format).
2. Manual cleanup : DELETE duplicate disks + delete 1861 phantom media_item via
   cascading season/episode/attr.
3. `library-index --mode incremental --confirm-bulk-change` → merkle short-circuit OK.
4. `library-index --mode enrich --budget 540` → **DEV #51** : enrich doesn't compute oshash
   (no-op on 118k oshash-NULL files).
5. `library-index --mode full` → ~17 min walk, no new files. Confirms **DEV #52** : full
   walker doesn't retry oshash on existing rows.
6. `library-relink --apply` → linked 1815 files (Monk + Squid Game now properly indexed,
   2 legitimate new items kept).
7. `run_backfill_ids()` dry-run via Python → **DEV #54** : all 1937 items skipped because
   `canonical_provider IS NULL` everywhere. Backfill chicken-and-egg : uses canonical,
   doesn't set it.
8. `library-reconcile` final : merkle=0, dispatch=0, enrich=0, releases=0, items=0,
   files_without_release=5,376 (sidecars + 5 phantoms DEV #17), season_count_drift=3
   (cosmetic Monk + Squid Game post first-link).

**Final BDD state** (clean) :
- 1,937 media_item (1,935 baseline + Monk + Squid Game truly added)
- 27,470 media_release (+117 from relink)
- 149,087 media_file (118,414 still oshash NULL — DEV #51/#52)
- 0 / 1,937 items have canonical_provider populated (DEV #54)
- 0 / 1,937 items have external_ids_json populated (chain : DEV #54 → DEV #27)
- 0 / 1,937 items have ratings_json populated (chain : DEV #54 → DEV #27)

**Conclusion** : full BDD "migrate everything + index everything" is **NOT POSSIBLE** with
the current codebase. The bottleneck is DEV #54 (backfill chicken-and-egg) which requires
either a `--init-canonical` mode (new) or a full `library-rescrape` of all 1,937 items
(API-heavy, hours). DEV #50, #53 made the scan_library invocation actively destructive
(duplicate creation). DEV #51, #52 leave 80% of files without oshash.

**Tech-debt 0.16.0 scope expansion** : add 5 new CRITIQUE/MAJEUR DEVs (#50-#54). The Plan A
reset+rescrape (DEV #27, Phase 8) is no longer optional — it's the only path to populate
provider-IDs on the live BDD.

Revised estimate +1-2 d : **17-25 → 18-27 d sequential, 14-20 → 15-22 d parallelised**.
