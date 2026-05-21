# Item 8 — Brainstorm améliorations BDD

**Date** : 2026-05-21
**Méthode** : conversion des DEVs (#12, #15-#19) + patterns (P11-P14) identifiés en item 7 en
items DESIGN-ready, plus brainstorm exhaustif des axes BDD non explorés au run.
**Output** : liste BDD-spécifique d'items pour le DESIGN tech-debt (item 14), avec dépendances
inter-items et plan de phases.

---

## 0. Diagnostic actuel

### Forces de l'architecture BDD existante

- **Schema bien structuré** : 17 tables, normalisation correcte (`media_item` ↔ `season` ↔
  `episode` ↔ `media_release` ↔ `media_file`). `0 orphan` aux trois niveaux relationnels testés.
- **Flex-attr via `item_attribute`** : extensibilité sans migrations pour des attributs
  rarement queried (`dispatch_path`, `normalized_title`).
- **Versionning schema** : `PRAGMA user_version` + table `schema_version` + 5 migrations
  appliquées sans incident bloquant (DEV #15 cosmétique).
- **WAL mode** activé → concurrence lecture/écriture saine.
- **integrity_check = ok** → aucune corruption.
- **Soft-delete par design** : colonnes `deleted_at` partout, tombstone `deleted_item`.
- **Idempotence partielle** : `INSERT OR IGNORE` dans `apply_migrations`, `idx_repair_pending_dedup`
  pour `repair_queue`.
- **Detector framework** : `library-reconcile` propose 6 scopes (merkle, dispatch_path, enrich,
  release, season, item), extensible.
- **Repair queue + outbox** : pattern event-sourcing local, séparation enqueue/drain.

### Faiblesses / dette identifiée par cet audit

- **Drift detection cassée** : DEV #18 (code mort) rend le mécanisme miss-strikes totalement
  dysfonctionnel. Impact direct : ~297 phantom files indéfiniment vivants en BDD.
- **CLI surface incomplète** : DEV #16 — la fonction qui CRÉE les `media_item` n'a pas
  d'exposition CLI. Aucun nouveau media_item depuis 18 jours.
- **FK non-enforced** : DEV #19 — schema déclare contraintes mais runtime ne les vérifie pas.
  Empirique OK, garantie hollow.
- **Détecteur path-missing absent** : DEV #17 — pas de mécanisme pour réconcilier `path` rows
  vs FS à granularité fichier (seul item-level via `dispatch_path`).
- **Schema_version désynchronisé** : DEV #15 — résidu cosmétique mais signe d'une migration
  re-apply non gérée.
- **Provider-IDs columns vides** : 0/1935 — backfill jamais lancé sur cette BDD. Item L du
  brainstorm 6 + ACCEPTANCE #4 provider-ids non-testable.
- **Outbox accumulation** : 133 rows tous `done`, pas de GC documenté.
- **`pending_op` vide partout** : table inutile ou mécanisme dormant ? À clarifier.
- **`item_issue` vide partout** : table définie sans usage observable. À auditer.
- **Aucun test E2E "scan→reconcile=clean"** : aurait attrapé DEV #18 immédiatement.

---

## 1. Items BDD par dimension

Brainstorm exhaustif. Codifié `BD-A` à `BD-Z+`.

### 1.1 — Drift / lifecycle / soft-delete

**BD-A. DEV #18 fix — appeler `increment_miss_strikes_for_disk` dans scan flow**

Site exact : `personalscraper/indexer/commands/scan.py`, entre la fin du walk et le
`apply_soft_deletes` (lignes ~287). Pour chaque disk visité : `drift.increment_miss_strikes_for_disk(
conn, d.id, current_generation)`.

Conditions :

- Seulement en mode `full` (incremental n'visite pas toutes les paths).
- Pas en `dry_run`.
- Pas en `enrich` mode (qui ne walk pas).

**BD-B. Test E2E miss-strike lifecycle**

- Setup : créer un FS temp avec un .mkv, scanner (`full`), assert media_file row, scan_generation = N.
- Supprimer le fichier sur FS, scanner full N+1 → assert miss_strikes = 1.
- Scanner full N+2 → assert miss_strikes = 2.
- Scanner full N+3 → assert miss_strikes = 3 AND deleted_at NOT NULL (soft-deleted).

**BD-C. Nouveau détecteur `path_missing` dans `library-reconcile`**

Itère `path` table + `Path(disk.mount_path) / p.rel_path .exists()` pour chaque row. Files
sous une path manquante → ajoute à `ReconcileReport.path_missing`.

Plus rapide qu'un walk FS complet car index-only. Pendant 100 ms sur 6,926 path rows.

**BD-D. `--scope path_missing --enqueue-repairs` → soft-delete propre**

Quand `path_missing` détecte un drift, enqueue `repair_queue(scope='path', scope_id=path.id,
action='soft_delete_subtree')`. `library-repair` consomme et soft-delete via `file_repo`.

**BD-E. Documenter les états du lifecycle media_file**

State machine : `discovered (stage A, oshash=NULL)` → `enriched (oshash set)` → `linked
(release_id set)` → `verified (last_verified_at bumped)` → `missed (miss_strikes++)` → `tombstoned
(deleted_at set + deleted_item row)`. Diagramme dans `docs/reference/indexer.md`.

**BD-F. Cleanup ponctuel des 8 shows orphans (post-fix)**

Script one-shot `scripts/cleanup-2026-05-21-orphan-shows.py` (à archiver après usage) :

- Pour 5 phantom paths (DEV #17) : soft-delete tous les media_file de leurs sous-dirs + drop
  path rows.
- Pour 2 FS-exists Monk + Squid Game : relancer scrape ou library-scan dédiée (post DEV #16 fix).

À ne pas mettre dans la codebase production permanente.

### 1.2 — CLI surface completeness

**BD-G. DEV #16 fix — commande `personalscraper library-scan`**

Expose `library.scanner.scan_library()` via Typer. Args : `--disk <id>` (optionnel, all by
default), `--mode full` (futur : autres modes), `--dry-run`.

- Crée/upserte `media_item` + `season` + `episode` à partir des NFOs sur disque.
- Suivie d'un `_indexer_scan` interne (existing behavior dans `scan_library()`).
- À lancer post-dispatch ou en cron (alongside `library-index`).

**BD-H. Audit transversal "modules métier sans CLI command"**

Script de vérification `scripts/audit-cli-coverage.py` :

- Iterate `personalscraper/library/*.py`, `personalscraper/indexer/*.py`, `personalscraper/trailers/*.py`,
  `personalscraper/scraper/*.py`.
- Pour chaque module avec >100 LOC, vérifier qu'au moins une commande Typer l'invoke.
- Si non → warning + suggéré command stub.

Pattern P12 codifié.

**BD-I. Documenter chaque commande CLI dans `docs/reference/commands.md`**

Audit actuel : combien de commandes CLI ont une doc référence ? Le help text Typer est intrinsèque,
mais une doc structurée (cas d'usage, paramètres, side effects, ordre canonique post-dispatch)
manque pour la moitié.

### 1.3 — FK enforcement + integrity invariants

**BD-J. DEV #19 fix — `PRAGMA foreign_keys = ON` au boot**

Site : `personalscraper/indexer/db.py — open_db()`. Ajouter `conn.execute("PRAGMA foreign_keys = ON")`
après ouverture, avant toute query métier.

**BD-K. Test E2E invariant `foreign_key_check` vide**

Pytest fixture : ouvre la BDD test, lance `PRAGMA foreign_key_check;` → assert no rows. À mettre
dans `conftest.py` ou comme test final de session.

Pour la BDD prod : à ajouter aux invariants matrix v2.1 (nouvel item AX par exemple).

**BD-L. `PRAGMA integrity_check` au boot (warning si non-ok)**

Currently fait nulle part. À ajouter dans `open_db()` au moins en mode debug, ou via une
commande dédiée `personalscraper library-integrity-check`.

**BD-M. Hard-delete protections**

Le schema déclare `ON DELETE CASCADE` pour `media_release.item_id` etc. Mais `_upsert_media_item`
n'utilise jamais DELETE — uniquement INSERT/UPDATE. Vérifier : aucun code applicatif ne fait
de `DELETE FROM media_item`. Si trouvé, soft-delete préféré.

```bash
rg -n "DELETE FROM media_item|DELETE FROM media_release|DELETE FROM season|DELETE FROM episode" --type py personalscraper/
```

### 1.4 — Migrations / schema_version

**BD-N. DEV #15 cleanup — `INSERT OR IGNORE INTO schema_version VALUES (3);`**

One-shot fix sur la BDD prod. À documenter dans le runbook (pas dans une nouvelle migration —
elle n'aurait pas le bon comportement).

**BD-O. Déprécier la table `schema_version`**

`PRAGMA user_version` est la source de vérité. La table `schema_version` est redondante,
historiquement utile pour avoir un journal mais en pratique inutilisée pour de la logique.

Migration 006 : `DROP TABLE schema_version;` + suppression de tous les `INSERT INTO
schema_version` dans les migrations futures.

OU :

**BD-P. Convertir `schema_version` en journal explicite**

Si on garde la table, étendre son schema : `version INTEGER PK, applied_at INTEGER, applied_by
TEXT, success INTEGER, notes TEXT`. Un VRAI audit log. Mais coût > bénéfice probablement.

**BD-Q. Hook lint custom : every migration must bump user_version AND insert schema_version row**

Si on garde la table, un script qui vérifie chaque `*.sql` du dossier migrations contient
exactement 1 `PRAGMA user_version =` et 1 `INSERT INTO schema_version`.

### 1.5 — Provider-IDs columns

**BD-R. Documentation runbook backfill-ids**

`docs/reference/external-ids-flow.md` existe déjà (mentionné dans CLAUDE.md). Vérifier qu'il
documente :

- Quand lancer `library-index --mode backfill-ids` (post-merge provider-ids, puis cron mensuel ?)
- Comment vérifier le résultat (`canonical_provider`, `external_ids_json`, `ratings_json` populés)
- Backoff / API quota (TMDB / TVDB / OMDB rate limits)

**BD-S. Cron / launchd entry pour backfill-ids**

Si pas déjà fait, ajouter à `launchd-plists/` un job qui lance backfill-ids hebdomadaire (~ 30 min
pour 1935 items). Avec `--budget-seconds` pour borner.

**BD-T. Backfill-ids one-shot first run sur prod**

Script de validation : lance le backfill, attend, assert `SELECT COUNT(*) FROM media_item WHERE
canonical_provider IS NULL` → tend vers 0 (modulo les items sans TMDB/TVDB ID dans leur NFO).

### 1.6 — Outbox / pending_op / item_issue

**BD-U. Auditer `pending_op` (0 rows) — table morte ou mécanisme dormant ?**

```bash
rg -n "pending_op" --type py personalscraper/
```

Si aucun caller productif → DROP via migration 006. Si caller exists mais zéro insert → bug ou
condition jamais déclenchée.

**BD-V. Auditer `item_issue` (0 rows) — idem**

Même check que BD-U.

**BD-W. GC policy pour `index_outbox`**

133 rows `done`, oldest 2026-05-02. Si on garde tout indéfiniment, croissance illimitée. Policy :
purge rows `status='done' AND processed_at < now() - 30 days`. Mettre dans `library-repair` ou
nouveau `library-gc`.

**BD-X. Métrique `outbox_lag` exposée**

Pour observabilité : le delta `now() - MIN(enqueued_at) WHERE status = 'pending'` est l'âge du
plus vieux pending row. Exposer via `library-status`.

### 1.7 — Observability / metrics

**BD-Y. Commande `personalscraper library-doctor`**

Health check global : integrity_check, foreign_keys, schema_version cohérent, drift signals
(merkle, miss_strikes lifecycle), outbox lag, repair_queue backlog, provider-IDs coverage.
Sortie tabulaire + exit code != 0 si critique.

**BD-Z. Métriques BDD exposées**

`library-status` actuel affiche scan_run info. Étendre pour exposer :

- 7191 files_without_release (decomposed per cause : sidecar / phantom / missing-item / new-orphan)
- 0 dispatch_path_missing
- merkle_drift count
- repair_queue backlog by status
- outbox lag
- provider-IDs coverage %

**BD-AA. Diff inter-scan_run dans `library-status`**

Currently `library-status` affiche le dernier scan_run. Ajouter "diff vs avant-dernier" :
files_added, files_soft_deleted, scan_generation bump, etc.

### 1.8 — Schema evolution / dette structurelle

**BD-AB. Migration 006 — DEV #15 + BD-O cleanup**

Single migration combine :

1. `INSERT OR IGNORE INTO schema_version VALUES (3);`
2. (Optionnel) `DROP TABLE schema_version;` si on choisit BD-O dépréciation.
3. `PRAGMA user_version = 6;`
4. `INSERT INTO schema_version (6);` ou supprimé selon décision BD-O.

**BD-AC. Audit "tables vides depuis init"**

Sur les 17 tables : `deleted_item`, `item_issue`, `pending_op` sont à 0. Vérifier qu'elles
ont au moins UN site INSERT actif dans le code. Sinon DROP via migration.

**BD-AD. Audit "colonnes never populated"**

Pour chaque table, `SELECT COUNT(*) WHERE col IS NOT NULL` sur chaque colonne. Si une colonne
est partout NULL → soit drop, soit document que c'est par design (ex: `media_file.xxh3_full`
"rare manual repair only").

**BD-AE. Audit FK orphans manuel (en attendant DEV #19 fix)**

```sql
-- 0 orphan releases
SELECT COUNT(*) FROM media_release r WHERE r.item_id IS NOT NULL AND r.item_id NOT IN (SELECT id FROM media_item);
-- 0 orphan files (path FK)
SELECT COUNT(*) FROM media_file mf WHERE mf.path_id NOT IN (SELECT id FROM path);
-- 0 orphan streams
SELECT COUNT(*) FROM media_stream ms WHERE ms.file_id NOT IN (SELECT id FROM media_file);
-- 0 orphan repair_queue (file_id ?)
SELECT COUNT(*) FROM repair_queue rq WHERE rq.scope='file' AND rq.scope_id NOT IN (SELECT id FROM media_file);
```

Tout `0` confirmera empiriquement que CASCADE applicatif fonctionne. Sinon = orphan, log.

### 1.9 — Tests / régression

**BD-AF. Pytest fixture "fresh DB seeded with realistic dataset"**

Une fixture qui :

- Crée une BDD via migrations 001-005.
- Insert ~10 media_item, ~50 episodes, ~100 media_file (realistic distribution).
- Permet aux tests E2E (BD-B, BD-K, etc.) de tourner contre un dataset reproductible.

**BD-AG. Test "scan → reconcile = clean"**

E2E :

1. Fixture above + un FS temp aligné avec la BDD.
2. Run `library-index --mode full`.
3. Run `library-reconcile`.
4. Assert `total_findings == 0`.

Aurait attrapé DEV #11 + #14 + #18 en CI.

**BD-AH. Test "migration up-to-date sur fresh DB"**

Crée DB vide, lance `apply_migrations` → assert `user_version == LATEST` AND `schema_version
== set(range(1, LATEST+1))`. Aurait attrapé DEV #15 si la migration 003 buggy avait été
introduite avec le test.

### 1.10 — Sécurité / robustesse

**BD-AI. Backup automatique pre-migration (déjà existant)**

`apply_migrations` fait déjà un `.pre-migration-<ver>.bak`. Vérifier que :

- Les backups ne s'accumulent pas indéfiniment (purge des vieux après 30 jours ?)
- Une commande `personalscraper library-rollback <version>` existe ? (currently manual)

**BD-AJ. Lock around library.db en multi-process**

`filelock.FileLock` existe via `indexer_lock`. Auditer que toutes les CLI commands qui mutate
la BDD prennent le lock. `library-scan` (BD-G) devra le faire.

**BD-AK. WAL checkpoint policy**

WAL fichier peut grossir indéfiniment si jamais checkpointé. Vérifier le `wal_autocheckpoint`
(default 1000 pages). Audit script :

```python
conn.execute("PRAGMA wal_checkpoint(FULL)")
```

À lancer pendant les périodes calmes (post-scan ?).

---

## 2. Catégorisation must / should / nice

### Must-have (DESIGN tech-debt priorité 1)

- **BD-A** DEV #18 fix (drift mechanism)
- **BD-B** Test E2E miss-strike lifecycle
- **BD-G** DEV #16 fix (`library-scan` CLI)
- **BD-J** DEV #19 fix (PRAGMA foreign_keys ON)
- **BD-K** Test invariant `foreign_key_check` vide
- **BD-N** DEV #15 cleanup (INSERT row 3)
- **BD-C** Détecteur `path_missing`
- **BD-AG** Test "scan → reconcile = clean" en CI

### Should-have (priorité 2)

- **BD-D** `--scope path_missing --enqueue-repairs`
- **BD-E** Documenter lifecycle media_file
- **BD-F** Cleanup script 8 shows orphans
- **BD-H** Audit "modules sans CLI"
- **BD-I** Doc référence chaque CLI
- **BD-L** PRAGMA integrity_check au boot
- **BD-M** Hard-delete protections audit
- **BD-R** Documentation runbook backfill-ids
- **BD-S** Cron backfill-ids
- **BD-T** First-run backfill-ids sur prod
- **BD-U** Audit `pending_op`
- **BD-V** Audit `item_issue`
- **BD-W** GC policy `index_outbox`
- **BD-Y** Commande `library-doctor`
- **BD-AE** Audit FK orphans manuel
- **BD-AF** Fixture seeded
- **BD-AH** Test migration up-to-date

### Nice-to-have (priorité 3 — 0.17+)

- **BD-O** Déprécier `schema_version` table (ou)
- **BD-P** Étendre `schema_version` en audit log
- **BD-Q** Lint custom migrations
- **BD-AB** Migration 006 combinée
- **BD-AC** Audit tables vides
- **BD-AD** Audit colonnes never populated
- **BD-X** Métrique `outbox_lag`
- **BD-Z** `library-status` étendu
- **BD-AA** Diff inter-scan_run
- **BD-AI** Purge backups
- **BD-AJ** Lock audit
- **BD-AK** WAL checkpoint policy

---

## 3. Dépendances inter-items

Graphe d'ordonnancement :

```
BD-A (DEV #18 fix)
  ├── BD-B (test miss-strike) [validation BD-A]
  ├── BD-C (path_missing) [parallèle, scope différent]
  └── BD-F (cleanup orphans) [après BD-A pour soft-delete propre]

BD-G (library-scan CLI)
  ├── BD-R/S/T (backfill-ids) [parallèle, peut tourner avant ou après]
  └── BD-F (cleanup orphans) [après BD-G pour re-créer Monk + Squid Game]

BD-J (PRAGMA foreign_keys)
  └── BD-K (test FK check) [validation BD-J]

BD-N (DEV #15 cleanup) — standalone

BD-AG (test scan → reconcile clean)
  ├── BD-AF (fixture seeded) [prérequis]
  ├── BD-A done [needed for clean reconcile]
  ├── BD-J done [needed for FK check]
  └── BD-C done [needed for path_missing baseline]
```

---

## 4. Cross-patterns → leviers (extension du tableau item 7 §3)

| #       | Pattern                                          | DEV instance                              | Levier (BD-X)                         |
| ------- | ------------------------------------------------ | ----------------------------------------- | ------------------------------------- |
| **P11** | Code mort dans chemins critiques                 | DEV #18                                   | BD-A + BD-H (audit code mort général) |
| **P12** | CLI surface incomplète                           | DEV #16                                   | BD-G + BD-H + BD-I                    |
| **P13** | Hard-delete sans cleanup downstream              | DEV #17                                   | BD-C + BD-D + BD-M                    |
| **P14** | Migration buggy → résidu permanent               | DEV #15                                   | BD-N + BD-Q + BD-AH                   |
| **P15** | Schema declare contrainte, runtime n'enforce pas | DEV #19                                   | BD-J + BD-K + BD-L                    |
| **P16** | Tables/colonnes vides jamais peuplées            | pending_op, item_issue, provider-IDs cols | BD-U + BD-V + BD-AC + BD-AD           |
| **P17** | Outbox/queue sans GC                             | index_outbox 133 done                     | BD-W + BD-X                           |

P15, P16, P17 sont nouveaux (BDD-spécifiques, complètent P11-P14 d'item 7).

---

## 5. Implications pour le DESIGN tech-debt (item 14)

### Section "BDD lifecycle invariants" (§9 nouvelle dans DESIGN.md)

Récapitulatif des invariants BDD à enforcer/tester :

1. **Drift detection vivante** : `media_file.miss_strikes` s'incrémente à chaque scan où la row
   n'est pas visitée. Test : créer fichier, scanner, supprimer, scanner N fois, assert miss_strikes=N
   puis deleted_at NOT NULL.
2. **FK enforcement runtime** : `PRAGMA foreign_keys = ON` au boot, `foreign_key_check` vide.
3. **Soft-delete propre** : tout file disparu du FS doit aboutir à `deleted_at NOT NULL` +
   `deleted_item` row dans un nombre borné de scans.
4. **Path coherence** : `path` rows + `Path(rel_path).exists()` aligned. `path_missing` détecteur.
5. **Schema_version cohérent OU déprécié** : éviter la dérive cosmétique.
6. **No phantom rows** : aucune row `deleted_at IS NULL` ne référence un FS path supprimé > N jours.

### Section "CLI surface completeness" (§10 nouvelle)

Récapitulatif des règles CLI :

1. **Chaque module métier critique expose AU MOINS UNE commande CLI** documentée.
2. **`personalscraper library-scan` créé** (DEV #16 fix).
3. **`personalscraper library-doctor` créé** (BD-Y).
4. **Audit CLI coverage** dans CI : `scripts/audit-cli-coverage.py`.
5. **Doc référence par commande** dans `docs/reference/commands.md`.

### Plan de phases BDD (intégré au plan global tech-debt)

Estimation par phase :

| Phase        | Items                                     | Effort                           |
| ------------ | ----------------------------------------- | -------------------------------- |
| BDD-1        | BD-A + BD-B + BD-J + BD-K + BD-AF + BD-AG | 2-3 j (foundations + tests E2E)  |
| BDD-2        | BD-G + BD-R + BD-S + BD-T                 | 2-3 j (CLI + backfill prod)      |
| BDD-3        | BD-C + BD-D + BD-F + BD-L + BD-M + BD-AE  | 2-3 j (path detection + cleanup) |
| BDD-4        | BD-N + BD-U + BD-V + BD-W + BD-Y + BD-Z   | 2-3 j (cleanup + observability)  |
| BDD-5 (nice) | BD-H + BD-I + BD-AC + BD-AD + autres      | 1-2 j (audits + polish)          |

Total BDD seul : **9-14 jours** sur les 13-22 du DESIGN global.

---

## 6. Suite

L'item 9 (analyse CLI) reprendra :

- BD-H (audit CLI coverage) — l'instrumente
- BD-I (doc référence par commande) — l'instrumente
- DEV #7 (run --help doc rot)
- DEV #10 (library-reconcile --dry-run inexistant)

L'item 10 (brainstorm CLI) consolidera ces points + ses propres trouvailles en items CLI-
spécifiques, alignés sur le DESIGN.

L'item 11 (analyse app + conformité design) cross-vérifiera que tous les DEVs/items entrent
dans une cohérence design.

L'item 14 (challenge final DESIGN) consolidera tout en un DESIGN.md final + phases plan.

---

## 7. Synthèse rapide pour le DESIGN

- **17 DEVs au total** (du run pipeline-monitor item 5 + audit BDD item 7) → 6 traités (#9, #11,
  #13, #14 par les fixes existants), 11 restants à intégrer au DESIGN.
- **17 patterns P1-P17** identifiés. Tous doivent être adressés explicitement dans le DESIGN final.
- **3 sections DESIGN.md à créer** : §9 BDD lifecycle invariants, §10 CLI surface completeness,
  - les 8 sections déjà proposées en item 6 §6.
- **5 phases tech-debt BDD** : foundations + CLI + path detection + cleanup + polish.
- **Estimation totale** : 13-22 jours, bump **0.16.0** (minor — invariants nouveaux, pas de
  breaking change utilisateur).
