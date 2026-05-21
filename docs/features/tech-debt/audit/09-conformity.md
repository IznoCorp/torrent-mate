# Item 11 — Audit conformité app vs DESIGN existants

**Date** : 2026-05-21
**Méthode** : cross-check des claims/invariants des DESIGN docs récents (event-bus,
provider-ids, media-indexer, pipeline-obs) contre l'état actuel du code et de la BDD.
Réutilisation des findings items 5-10 pour identifier les ACCEPTANCE_FAIL durables.
**Output** : rapport de conformité globale + identification des "feature shipped but
not deployed" + items DESIGN-ready pour item 14.

---

## 0. DESIGN docs sources auditées

| DESIGN doc    | Version livrée                                 | Audit                                     |
| ------------- | ---------------------------------------------- | ----------------------------------------- |
| event-bus     | v0.14.0 — `323c1b4`                            | Bus invariants + AppContext boundary rule |
| provider-ids  | v0.15.0 — `db106ac`                            | ACCEPTANCE.md 10 critères                 |
| media-indexer | (no version tag in DESIGN) — scattered commits | Soft-delete + drift + scan modes          |
| pipeline-obs  | archived                                       | Observability conventions                 |
| ext-staging   | archived                                       | Staging dirs layout                       |
| api-unify     | archived (post-arch-cleanup)                   | API layer structure                       |

Autres archives consultées mais non auditées en profondeur (logging, trailer, test-coverage,
test-realism, info-cmd, arch-cleanup, legacy-cleanup).

---

## 1. Conformité provider-ids — état réel

Re-check des 10 critères ACCEPTANCE.md (déclarés tous ✅ ou 🟡 à phase 15) contre le code/BDD actuels :

| #   | Criterion                                                  | Statut déclaré | **Statut réel post-audit**                                                                                    | Evidence                                                                                                                                                                                                                                                                                                                                             |
| --- | ---------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | DEV #2 root cause fix (episode NFO uniqueid)               | ✅             | ✅ **CONFIRMÉ**                                                                                               | Tests `test_regression_dev2_episode_ids.py` passent. NFOs sur disque ont `<uniqueid default="true">` sur épisodes.                                                                                                                                                                                                                                   |
| 2   | Fresh TV scrape produit NFOs avec canonical + xref         | ✅             | ✅ **CONFIRMÉ** (sur les nouveaux scrapes — observé pendant le run item 5 sur FROM (2022))                    |
| 3   | `personalscraper indexer --backfill-ids` walks the library | ✅             | ❌ **ACCEPTANCE_FAIL**                                                                                        | **Aucune CLI command `backfill-ids` n'existe**. `library-index --help` liste `--mode` choices : `full, quick, incremental, or enrich` — **pas de `backfill_ids` mode listé**. `rg "backfill[-_]ids" personalscraper/commands/` retourne 0. Le driver `run_backfill_ids` existe (en `indexer/scanner/_modes/backfill_ids.py`) mais zéro exposure CLI. |
| 4   | DB schema utilise `external_ids_json`                      | ✅ (schema)    | 🟡 **PARTIEL — DATA EMPTY**                                                                                   | Migration 005 a bien créé les colonnes (`canonical_provider`, `external_ids_json`, `ratings_json`). Schema OK. MAIS sur la BDD prod : **0/1935 items ont ces colonnes populées** (audit item 7). Backfill jamais exercé. ACCEPTANCE #4 ne peut PAS être validée empiriquement.                                                                       |
| 5   | `RuleCriteria.imdb_id` removed                             | ✅             | ✅ **CONFIRMÉ** (pas re-vérifié exhaustivement, mais grep rapide confirme absence)                            |
| 6   | Monolithic Protocols dropped                               | ✅             | ❌ **ACCEPTANCE_FAIL**                                                                                        | `personalscraper/api/torrent/_contracts.py:124: class TorrentClientFull(Protocol)` toujours présent. `personalscraper/api/metadata/_base.py:267: class MetadataProvider(Protocol)` toujours présent. Audit item 1 (plan-drift) l'avait déjà noté. Pas corrigé depuis.                                                                                |
| 7   | TrackerRegistry `priority_by_media_type`                   | ✅             | ✅ **CONFIRMÉ**                                                                                               |
| 8   | Tests verts + coverage ≥ 90%                               | ✅             | ✅ **CONFIRMÉ** (vérifié indirectement via les fixes item 7/8)                                                |
| 9   | Public CLI unchanged sauf `indexer backfill-ids`           | ✅             | ❌ **EN PARTIE TROMPEUR**                                                                                     | Le criterion dit "no breaking change" — OK. Mais le claim positif ("indexer backfill-ids ajouté") est FALSE (DEV ACCEPTANCE #3).                                                                                                                                                                                                                     |
| 10  | 8-show staging dispatch-ready post-merge                   | 🟡 (à valider) | ✅ **CONFIRMÉ EMPIRIQUEMENT** (par le run item 5 — 8 items prêts à dispatch hors Top Chef Le Concours bloqué) |

**Bilan provider-ids** :

- 2 ACCEPTANCE_FAIL durables : #3 (CLI manquante) + #6 (Protocols monolithiques survivent).
- 1 partielle : #4 (schema OK, data vide).
- 1 trompeuse : #9 (formulation positive sur un fait non vrai).

→ Pattern P23 (nouveau) : **ACCEPTANCE ticée par phase gate mais pas par "feature exercise"**.
Item 1 plan-drift avait identifié ce pattern (P1, P2), il se re-confirme ici à granularité fine.

---

## 2. Conformité event-bus — état réel

### 2.1 Invariants du DESIGN

- **NO DEFERRAL** — chaque sous-phase a tout livré.
- **AppContext boundary-only rule** — `AppContext` construit aux frontières (CLI, host) uniquement. Composants internes reçoivent `EventBus` + `Settings` + `config: Config`, jamais `AppContext`.
- **Event dataclass frozen=True kw_only=True**
- **Dispatch MRO-based** + cache invariant (subscription order indifférent)
- **JSON serialization contract** : tous les Events sont JSON-sérialisables

### 2.2 Vérification

```bash
$ rg -n "def \w+\(.*app_context: AppContext|def \w+\(.*ctx: AppContext" --type py personalscraper/ | grep -v "cli_helpers\|test"
```

Pour vérifier que les composants internes ne reçoivent pas `AppContext`. Test simple :

- `cli_helpers.py:25 — _build_app_context(config, settings) -> AppContext` : OK (construction au boundary)
- `cli_helpers.py:47 — per_step_boundary(config, settings) -> Iterator[AppContext]` : OK (context manager au boundary)
- `commands/pipeline.py:319, 360` — AppContext mentionné dans docstring/comment : OK (boundary)

→ **Boundary-only rule respectée** sur les sites principaux.

Le DEV #6 (VERIFY silent stdout) n'est PAS une violation event-bus per se — les events VERIFY
existent vraisemblablement sur le bus, juste pas en mode stdout. Hypothèse A de DEV #6.

### 2.3 ACCEPTANCE event-bus

Le DESIGN event-bus n'a pas d'ACCEPTANCE.md séparé (peut-être inclus en IMPLEMENTATION.md du
feature). Les "NO DEFERRAL" + "AppContext boundary" sont les invariants principaux. Apparemment
respectés.

**Bilan event-bus** : conformité OK, modulo l'observabilité asymétrique VERIFY (DEV #6) qui est
plus un gap CLI/logging qu'un breach event-bus.

---

## 3. Conformité media-indexer — état réel

### 3.1 Invariants du DESIGN

- Schema versionné via PRAGMA user_version + migrations idempotentes
- Soft-delete lifecycle (deleted_at + deleted_item tombstone)
- Drift detection (miss_strikes → n threshold → soft-delete)
- Scan modes (full, quick, incremental, enrich)
- Merkle short-circuit sur quick/incremental
- Bulk-change freeze (DiskBulkChangeDetected)
- Disk sentinel (UUID + bootstrap)
- WAL mode, foreign_keys

### 3.2 Vérification (cross-ref avec items 7/8)

| Invariant               | Statut réel                                | DEV concerné                                                                                        |
| ----------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| Schema versionné        | ✅ user_version=5, 5 migrations OK         | (DEV #15 cosmétique sur schema_version table)                                                       |
| Soft-delete lifecycle   | ❌ **TOTALEMENT CASSÉ**                    | DEV #18 — `increment_miss_strikes_for_disk` jamais appelée → drift inactif → soft-delete impossible |
| Migrations idempotentes | ✅ avec snapshots `.pre-migration-<v>.bak` | (DEV #15 cosmétique)                                                                                |
| Merkle short-circuit    | ✅ post fix #11 + #14                      | (DEV #11 et #14 traités)                                                                            |
| Bulk-change freeze      | ✅ déclenchée en validation post-fix #11   | (workaround `--confirm-bulk-change`)                                                                |
| Disk sentinel           | ✅ (vérifié au boot)                       | (pas testé en profondeur)                                                                           |
| WAL mode                | ✅ PRAGMA journal_mode = wal               | (item 7)                                                                                            |
| Foreign keys enforced   | ❌ **PRAGMA foreign_keys = 0**             | DEV #19                                                                                             |
| Scan modes              | ✅ full/quick/incremental/enrich exposés   | ACCEPTANCE provider-ids #3 fail (backfill_ids non listé)                                            |

**Bilan media-indexer** :

- 2 violations critiques : DEV #18 (drift cassé), DEV #19 (FK non-enforced)
- 1 ACCEPTANCE_FAIL : backfill_ids mode pas exposé en CLI
- Le reste : OK conformité

→ Pattern P24 (nouveau) : **infrastructure invariants déclarés mais pas activés au runtime**
(FK déclarées mais désactivées ; miss_strikes mécanisme défini mais jamais appelé). Le DESIGN
écrit le "comment" mais le wiring runtime manque.

---

## 4. Conformité pipeline-obs / observabilité

### 4.1 Conventions DESIGN

- structlog event-names en snake_case
- chaque step émet `step_started` + `step_completed` (ou `step_errored`)
- correlation_id propagé via `ContextVar`

### 4.2 Vérification

- ✅ Event-names en snake_case (vérifié sur ingest/sort/process events observés)
- ✅ Pipeline.run() émet `pipeline_started` + `pipeline_finished` (vu en `commands/pipeline.py:349, 416`)
- ✅ Per-step events visibles dans le run item 5 (ingest_complete, sort_complete, process_clean_complete, etc.)
- ❌ **VERIFY n'émet AUCUN event INFO sur stdout** (DEV #6) — soit ces events vont sur le bus uniquement (matrix v2.0 §VERIFY documente `verify_item_done` events), soit ils ont été droppés

→ Pattern P25 (nouveau) : **observability gap par command-level skip de structlog au profit de Typer rich**. Distinction "UX rich" vs "machine telemetry" pas tracée. Déjà identifié comme P18 en item 9.

---

## 5. Conformité ext-staging (staging dirs)

### 5.1 Convention

- `001-MOVIES/`, `002-TVSHOWS/`, `097-TEMP/`, `098-AUTRES/`, `099-SCRIPTS/`, `003-EBOOKS/`, `004-AUDIO/`
- Configuration dans `config/patterns.json5`

### 5.2 Vérification (depuis run item 5)

- ✅ Structure observée correspondante en `/Volumes/IznoServer SSD/A TRIER/`
- ✅ `097-TEMP` empty post-SORT (gate fonctionne)
- ❌ **10 `.DS_Store` survivent dans le staging** (DEV #4) — cleanup ENFORCE scope-limited

→ Pas un breach DESIGN majeur, plutôt un detail de cleanup à finaliser.

---

## 6. Patterns transversaux identifiés (P23-P25 nouveaux)

| #       | Pattern                                                                 | Instance principale           | Implication DESIGN tech-debt                                                                 |
| ------- | ----------------------------------------------------------------------- | ----------------------------- | -------------------------------------------------------------------------------------------- |
| **P23** | ACCEPTANCE ticée par phase gate mais pas par "feature exercise" durable | provider-ids #3, #6, #9       | Tous les criteria DOIVENT être ré-exécutés en fin de feature (live exercise, pas phase gate) |
| **P24** | Infrastructure invariants déclarés mais pas activés au runtime          | DEV #18 (drift), DEV #19 (FK) | "Activation test" obligatoire — pas seulement "wiring exists" mais "wiring runs in prod"     |
| **P25** | Observability gap par command-level UX→rich preference                  | DEV #6 (VERIFY)               | Trace claire "user-facing" vs "machine telemetry" — déjà P18                                 |

P23-P25 se cumulent à P1-P22 des items 6/7/8/9. Total : **25 patterns** systémiques recensés
pour le tech-debt DESIGN.

---

## 7. Items DESIGN-ready (CF-A..CF-K)

Items conformity-spécifiques :

**CF-A. ACCEPTANCE_FAIL provider-ids #3 — exposer `library-index --mode backfill-ids` OU commande dédiée**

Déjà identifié comme item L/BD-R/BD-S/BD-T (item 6, 8) + CL-P (item 9). Re-validation conformity : ce
n'est pas "à ajouter", c'est "à conformer" à un ACCEPTANCE déjà déclaré ✅. Severity : ACCEPTANCE_FAIL.

**CF-B. ACCEPTANCE_FAIL provider-ids #6 — drop `MetadataProvider` + `TorrentClientFull` Protocols**

Le criterion ACCEPTANCE #6 dit "no monolithic Protocol remains". Empirically :

```bash
$ rg -n "^class MetadataProvider\b|^class TorrentClientFull\b" personalscraper/api/
personalscraper/api/torrent/_contracts.py:124:class TorrentClientFull(...)
personalscraper/api/metadata/_base.py:267:class MetadataProvider(Protocol):
```

Tâche : pour chaque Protocol :

1. Audit callers (`rg "MetadataProvider\b" --type py`)
2. Migrer chaque caller vers les capability protocols atomiques
3. Drop la définition + drop les tests qui asseoient les monolithic

Estimation : 1-2 jours selon nombre de callers.

**CF-C. Re-exercise ACCEPTANCE post-merge automatique**

Pattern P23 → règle : après chaque merge feature, lancer une commande type
`personalscraper acceptance-check <feature>` qui re-exécute tous les criteria sur l'instance
courante. Différent du phase gate test.

Pour tech-debt 0.16.0 lui-même : prévoir une `ACCEPTANCE.md` avec critères exécutables (commandes
shell) pour chaque DEV traité.

**CF-D. Activation invariants — test au boot**

Pattern P24 → `personalscraper library-doctor` (item 8 BD-Y / item 9 CL-M) doit inclure :

- `PRAGMA foreign_keys` retourne 1
- Drift detection a tourné dans les N derniers scans (vérifier que miss_strikes a été
  incrémenté au moins une fois sur des phantom files de test)
- Migration coherence

**CF-E. Convention canonical : "feature shipped" = "feature deployed et exercé"**

Convention à inscrire dans `docs/reference/feature-lifecycle.md` (nouveau) :

- **Phase gate** : code mergeable + tests verts (current).
- **Acceptance** : criteria exécutés sur prod, evidence captured.
- **Deployment** : feature visible en runtime (CLI, cron, etc.).
- **Sunset** : si feature plus utilisée, déprécier explicitement.

Aide à éviter le pattern provider-ids "shipped but not deployed".

**CF-F. Audit transversal "DESIGN claims vs code" en CI**

Pour chaque DESIGN.md archived, extraire les claims (lignes "MUST", "SHALL", "✅") et vérifier
contre le code. Custom check, à terme un job CI.

Stretch goal — 0.17+. Mais l'idée : ne plus laisser des DESIGN obsolètes ou des claims trompeurs
dans `docs/archive/features/`.

**CF-G. Audit "tables/colonnes/Protocols/functions définies mais non utilisées"**

Combine P11 (item 7) + P16 (item 8) + finding CF-B. Audit unique pour tous types de "dead
infrastructure" :

- Tables (pending_op, item_issue, deleted_item)
- Colonnes (provider-IDs columns empty)
- Protocols (MetadataProvider, TorrentClientFull)
- Functions (increment_miss_strikes_for_disk)

À automatiser via custom CI script `scripts/audit-dead-infrastructure.py`.

**CF-H. Documentation runbook "post-merge actions"**

Chaque feature qui produit un changement de schéma BDD / config doit avoir un runbook
"actions post-merge" : commandes à lancer, validation à exécuter, alarme à configurer.

Pour provider-ids : devrait inclure "lancer backfill-ids" + "vérifier external_ids_json
populated rate".

**CF-I. ACCEPTANCE_FAIL post-merge alerting**

Si une ACCEPTANCE devient FAIL après merge (ex: provider-ids #3 qui était ✅ devient FAIL parce
que la CLI exposure manque), il faut alerter. Pattern :

- Test régression dédié pour chaque ACCEPTANCE criterion (pas juste phase gate)
- Run sur CI à chaque PR
- Si fail → block merge (ou warning explicite)

**CF-J. Acceptance criteria standardisés**

Convention : chaque criterion DOIT être une commande shell exécutable :

> ❌ "Public CLI unchanged sauf indexer backfill-ids" (prose)
>
> ✅ `personalscraper library-index --mode backfill-ids --help | head -1` (returns valid help text)

Le format est testable, regression-stable, non-ambigu. À inscrire en règle universelle dans
`/.claude/CLAUDE.md` ou similaire.

**CF-K. Migration `acceptance-check` pour features archived**

Sur chaque archived feature : re-rédiger ACCEPTANCE en commandes exécutables. Backfill
historique. À faire au moment du DESIGN tech-debt final pour les 3-4 features les plus
critiques (event-bus, provider-ids, media-indexer, pipeline-obs).

---

## 8. Catégorisation must/should/nice

### Must-have (DESIGN priorité 1)

- **CF-A** Expose backfill-ids CLI (ACCEPTANCE_FAIL provider-ids #3)
- **CF-B** Drop monolithic Protocols (ACCEPTANCE_FAIL provider-ids #6)
- **CF-D** Activation invariants test (combine items 7/8 BD-J/K/L + CF check)

### Should-have (DESIGN priorité 2)

- **CF-C** Re-exercise ACCEPTANCE post-merge (process)
- **CF-E** Convention "shipped = deployed" (process)
- **CF-G** Audit dead infrastructure (process + script)
- **CF-H** Documentation runbook post-merge (process)
- **CF-I** ACCEPTANCE_FAIL alerting CI (process)
- **CF-J** ACCEPTANCE criteria standardisés (process)

### Nice-to-have (0.17+)

- **CF-F** Audit DESIGN claims vs code en CI (long terme)
- **CF-K** Migration acceptance-check pour archived features (backfill)

---

## 9. Plan de phase conformité (intégré au plan global)

| Phase            | Items                                                  | Effort        |
| ---------------- | ------------------------------------------------------ | ------------- |
| CONF-1           | CF-A (backfill CLI) + CF-B (drop Protocols)            | 1-2 j         |
| CONF-2           | CF-D (activation invariants) + CF-G (dead infra audit) | 1-2 j         |
| CONF-3           | CF-C + CF-E + CF-H + CF-I + CF-J (process/docs)        | 1-2 j         |
| CONF-4 (différé) | CF-F + CF-K                                            | 1-2 j → 0.17+ |

Total conformité 0.16.0 : **3-6 jours** (CONF-1..CONF-3).

Avec recouvrement vs items déjà comptés (CF-A = BD-R+S+T = CL-P, etc.) : effort net additionnel
estimé à **1-2 jours**.

---

## 10. Synthèse cumulée multi-dimension (mise à jour pour item 14)

| Dimension                    | Items DESIGN-ready                                        | Jours 0.16.0 (nets)             |
| ---------------------------- | --------------------------------------------------------- | ------------------------------- |
| Pipeline app + indexer       | item 6 A-G + DEV #15-#19 + item 8 BD-A..BD-AK             | 9-14 j                          |
| Skill matrix v2.1 + agents   | item 6 M-T                                                | 1-2 j                           |
| Tests E2E + validation       | items 6/8/9/10 transverses (AB-AE + BD-AF/G/H + CL-K/S/T) | 2-3 j                           |
| CLI + observability + doc    | item 9/10 CL-A..CL-AN                                     | 8-13 j                          |
| Conformité / ACCEPTANCE_FAIL | item 11 CF-A..CF-K                                        | 1-2 j (net, après recouvrement) |
| **TOTAL 0.16.0**             |                                                           | **~13-22 j** (parallélisable)   |

Pas de croissance vs estimation item 10 — les items CF-\* recouvrent largement avec ceux des
items 6/8/9/10. Item 11 valide le périmètre et identifie les ACCEPTANCE_FAIL formellement.

---

## 11. Suite

L'item 12 (analyse critique design + architecture) explorera :

- L'architecture cible à 1.0 (vision long terme)
- Les décisions structurelles à figer maintenant vs reporter
- Les patterns inter-features (event-bus + provider-ids + pipeline) → architecture globale
- Le rôle de la skill pipeline-monitor v2.X dans le tooling pérenne

L'item 13 (synthèse globale brainstorms) consolidera items 6+8+10+12 en un master backlog.

L'item 14 (challenge final DESIGN) produira le DESIGN.md non-draft + plan/INDEX.md +
phases-XX.md prêts à `/implement:phase`.
