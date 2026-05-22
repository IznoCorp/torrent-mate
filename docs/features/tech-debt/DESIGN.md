# Design — Tech-Debt (Global Cross-Feature Fixes)

**Codename** : `tech-debt`
**SemVer** : MINOR (0.15.1 → 0.16.0) — voir item 13 §5 pour justification
**Branch** : `fix/tech-debt` (existante depuis 0.15.0 → 0.15.1 ; rename non-effectué)
**Date** : 2026-05-21 (final)
**Status** : Final non-draft — pending `/implement:phase` execution

## 0. Origin

Cette feature est un **cleanup cross-feature** déclenché après merge de `feat/provider-ids`
(`db106ac`). L'audit pré-design (items 1-13, voir `audit/`) a réalisé un run réel de la skill
pipeline-monitor v2.0 (item 5) + 6 brainstorms + 1 audit BDD + 1 audit CLI + 1 conformity check

- 1 critique architecturale + 1 synthèse globale.

Documents sources :

- `audit/01-plan-drift.md` — patterns de dérive cross-feature (P1-P8 historiques)
- `audit/02-pipeline-cartography.md` — carto du pipeline (9 StepReports)
- `audit/03-skill-update-brainstorm.md` + items A-BO → matrix v2.0 skill
- `audit/04-pipeline-monitor-brainstorm.md` — 33 items + P1-P10
- `audit/05-bdd-audit.md` — 5 DEVs nouveaux #15-#19 + P11-P14
- `audit/06-bdd-brainstorm.md` — 37 items BD-\* + P15-P17
- `audit/07-cli-audit.md` — 4 DEVs #20-#23 + P18-P22
- `audit/08-cli-brainstorm.md` — 35 items CL-\*
- `audit/09-conformity.md` — 2 ACCEPTANCE_FAIL provider-ids + P23-P25
- `audit/10-architecture-critique.md` — 7 critiques + P26-P29
- `audit/11-global-synthesis.md` — master backlog 80 items + 8-phase plan

## 1. Problem Statement

Trois patterns systémiques (parmi 29 P1-P29 codifiés) sont la racine :

### Pattern A — Infrastructure invariants déclarés mais pas activés (P24)

Le code définit des mécanismes qui ne tournent jamais en prod :

- **Drift detection cassée (DEV #18)** : `increment_miss_strikes_for_disk` définie dans
  `indexer/drift.py:417` mais **zéro caller**. Conséquence : `miss_strikes` stuck à 0, soft-
  delete impossible, ~297 phantom files BDD vivants indéfiniment.
- **FK non-enforced (DEV #19)** : `PRAGMA foreign_keys = 0` au runtime. Schema déclare
  CASCADE/SET NULL/RESTRICT, runtime ne vérifie pas.
- **`library.scanner.scan_library()` non exposé CLI (DEV #16)** : seule fn créatrice de
  `media_item`, sans CLI command. Aucun nouveau media_item créé depuis 03/05/2026.

### Pattern B — ACCEPTANCE ticée par phase gate mais pas par feature exercise (P23)

Provider-ids v0.15.0 ACCEPTANCE.md déclare ✅ sur 10/10. Audit conformité :

- **#3 ACCEPTANCE_FAIL** : `personalscraper indexer --backfill-ids` n'existe pas (driver oui,
  CLI non). Conséquence : 0/1935 items ont external_ids_json populé.
- **#6 ACCEPTANCE_FAIL** : `MetadataProvider` + `TorrentClientFull` Protocols survivent.
- **#9 misleading** : claim positif sur fait faux.

### Pattern C — Code defects découverts par chaîne de validation (P2)

DEV #11 (merkle non-déterministe) a masqué DEV #13 (C5 race index recreate), qui a masqué
DEV #14 (oshash filter divergence). Chaque fix a permis le suivant de devenir observable.
Validation à l'usage manquante = chaîne invisible.

Plus 17 autres patterns systémiques (P1-P29) avec leurs leviers individuels.

## 2. Scope

### In scope (15 MUST + 26 SHOULD)

15 items must-have (4 déjà shipped via `268cbee`, `29c4953`, `fc39f77`, `3993487` — 11 restants)
et 26 items should-have, distribués en 8 phases (item 13 §3).

Couvre :

- BDD invariants (drift + FK)
- CLI gaps + format unification + telemetry
- Path-missing detector + cleanup phantom paths
- Monolithic Protocols drop (ACCEPTANCE_FAIL provider-ids)
- Matrix v2.1 + agents matrix-aware
- Documentation reference (state ownership, module relationships, anti-décisions, lifecycle)
- Tests E2E (scan→reconcile=clean, miss-strike lifecycle, matrix-CLI refs)

### Out of scope (différé 0.17+)

39 items nice-to-have :

- Refactor namespaces (library/indexer/scraper polysémie)
- Décomposition `enforce` (3 sous-responsabilités → 3 commandes)
- Unification library scanner + indexer scanner
- REPL + interactive dispatch + pipe stdio + JSON-API mode + `suggest`/`diagnose`
- Schema_version table dépréciation
- Hash version-tag stockage
- I18n help text français
- Audit DESIGN claims vs code en CI
- Acceptance-check backfill features archived

## 3. Goals

1. **Restaurer le drift mechanism** — soft-delete fonctionnel, phantoms purgés naturellement.
2. **Activer FK enforcement runtime** — schema guarantee = runtime guarantee.
3. **Combler les gaps CLI** — `library-scan`, `library-doctor`, `library-gc`, backfill-ids,
   `qbit-restart`, --dry-run sur mutateurs manquants, format unification.
4. **Honorer les ACCEPTANCE_FAIL provider-ids** — drop monolithic Protocols, expose backfill-ids,
   first-run backfill.
5. **Sync matrix v2.1 avec la réalité** — 12 events nouveaux documentés + agents matrix-aware
   par défaut + auto-detect missing agents.
6. **Test infrastructure E2E** — scan→reconcile=clean ; matrix-CLI refs ; miss-strike lifecycle.
7. **Doc reference cohérente** — state ownership, module relationships, anti-décisions,
   lifecycle media_file.

## 4. Non-Goals

Verrouillés explicitement pour 0.16.0 :

- **Pas de refactor architecture** (namespace, enforce decomp, scanner unification) — 0.17+.
- **Pas de breaking change CLI** — tous les renames via deprecation alias.
- **Pas de JSON-API server mode** — 1.x roadmap.
- **Pas de microservices / multi-tenant / auth** — anti-décisions 1.0 (cf §11).
- **Pas de plugin loader dynamique** — extensions via subclassing/import only.

## 5. Architecture (sections §9-§11 nouvelles, §1-§8 hérités du draft)

### §9 BDD lifecycle invariants

Invariants à enforce + tester pour la couche BDD :

1. **Drift detection vivante** — `media_file.miss_strikes` s'incrémente sur chaque scan où la
   row n'est pas visitée. `apply_soft_deletes` consomme les strikes au-dessus du threshold.
2. **FK enforcement runtime** — `PRAGMA foreign_keys = ON` au boot de chaque connection ;
   `PRAGMA foreign_key_check;` retourne 0 rows.
3. **Soft-delete propre** — tout file disparu du FS aboutit à `deleted_at NOT NULL` +
   `deleted_item` tombstone dans un nombre borné de scans (N = config.indexer.scan.n_strikes_for_softdelete).
4. **Path coherence** — `path` rows + `Path(rel_path).exists()` aligned ; détecteur
   `path_missing` ajouté à `library-reconcile`.
5. **Schema_version cohérent** — `INSERT OR IGNORE INTO schema_version VALUES (3);` patch
   one-shot. Long terme : déprécier (0.17+) ou journal explicite.
6. **No phantom rows** — aucune row `deleted_at IS NULL` ne référence un FS path supprimé > N
   scans.

### §10 CLI surface completeness

Règles :

1. **CLI completeness** : chaque module métier critique expose ≥1 commande CLI documentée.
2. **Dry-run par défaut sur tout ce qui mute** — règle universelle ; `library-repair`,
   `library-relink`, `library-clean`, `init-config` ajoutent `--dry-run`.
3. **Telemetry structlog obligatoire** — chaque commande émet ≥1 `cli.invoke.<cmd>` au start +
   ≥1 event "domain progress" par étape clé. VERIFY corrigé pour émettre `verify_item_done` en INFO.
4. **Output format unifié** — `--format json|plain|rich` global ; default rich pour humain.
5. **Documentation référence par commande** — `docs/reference/commands.md` exhaustif.
6. **Matrix references CI-validated** — test "matrix mentionne uniquement des CLI existantes".

### §11 Architecture / state ownership

1. **FS = vérité, BDD = projection** (P27). State ownership matrix dans
   `docs/reference/architecture.md` :
   - FS owns media files + NFOs + sidecars
   - BDD owns dispatch_path, fingerprints, drift state, item attributes
   - Pipeline owns lock files
   - EventBus owns transient observability
2. **CLI = stable public API** (P29). Add command = non-breaking. Change flag = breaking.
   Rename = alias deprecation 1 release.
3. **Composition over inheritance for Protocols** (P28). Capabilities atomiques ;
   `MetadataProvider` + `TorrentClientFull` droppés.
4. **Anti-décisions 1.0** documentées dans `docs/reference/architecture.md` § "Out of scope
   for 1.0".

### §12 Documentation conformity (P30 — post-REDO)

Pattern observé sur 7 archived features (event-bus #24, provider-ids #27, media-indexer #32,
pipeline-obs #39, trailer #42+#43, logging #45, legacy-cleanup #48) : DESIGN.md archivé non
ré-vérifié après refactor suivant qui le casse.

Règles :

1. **Chaque archived feature DESIGN.md DOIT être amendée** au prochain refactor qui invalide
   une partie de ses claims : banner "STATUS : superseded by feat/X, see docs/reference/Y"
   - table old→new mapping pour les symboles renommés / supprimés.
2. **Reference docs `docs/reference/*.md` sont source-of-truth pour le code actuel**.
   Archive = snapshot historique, jamais authoritative pour l'état présent.
3. **Phase 9 "Archive doc updates"** matérialise cette règle en 0.16.0 pour les 7 features
   identifiées.

### §13 Promise lifecycle (P31 — post-REDO)

Pattern observé : promesses versionnelles dans DESIGN sans CI gate (DEV #46 — 0.10.0
module-size hard-block stalled depuis 5 versions ; DEV #27 — provider-ids Plan A
reset+rescrape jamais exécuté).

Règles :

1. **Toute "promise versionnelle" dans un DESIGN DOIT avoir un CI check** qui échoue à
   partir de la version cible si la promise n'est pas honorée.
2. **Versioned promises tracker** dans `docs/reference/promises.md` (nouveau) — liste
   toutes les promesses + version cible + statut.
3. Application immédiate en 0.16.0 : promote `scripts/check-module-size.py` en hard-block
   (exit 1 sur WARN, pas seulement print).

### §14 Success criteria enforcement (P32 — post-REDO)

Pattern observé (DEV #41 test-coverage drift, DEV #49 test-realism target manqué) : les
quantitative targets DESIGN §8 ne sont pas re-mesurés au phase gate.

Règles :

1. **Au phase gate final d'une feature, re-mesurer EVERY quantitative target** du DESIGN §8
   (coverage %, @patch count, LOC, etc.). Si manqué : feature ne merge pas.
2. **Checklist `phase-gate-checklist.md`** (nouveau) — template avec re-measurement steps.
3. **Format ACCEPTANCE.md exécutable** déjà inscrit en §6 ; étendre pour TOUTE feature
   future.

### §15 PRAGMA & connection discipline (P33 — post-REDO)

Pattern observé (DEV #19 sous-estimé + #33 + #34) : multiples sites raw `sqlite3.connect()`
bypass `open_db()` → `foreign_keys`, `busy_timeout`, `cache_size`, `mmap_size`, `temp_store`
non appliqués.

Règles :

1. **`personalscraper/indexer/db.py` expose `_apply_pragmas(conn)`** helper consommé par
   `open_db()` et par TOUT site qui ouvre une connexion SQLite.
2. **Lint rule custom** : `rg "sqlite3\.connect\(" personalscraper/ --type py | grep -v "db.py"`
   doit retourner zero. Ajout `scripts/check-pragma-discipline.py` au `make check`.
3. Sites à migrer (Phase 1) : `dispatch/run.py` (×2), `commands/library/audit.py`,
   `conf/loader.py`, `_concurrency.py`, `outbox/_disk.py`, `outbox/_publish.py`.

### §16 Safety net E2E (P34 — post-REDO)

Pattern observé (DEV #18 drift dead, DEV #31 paranoia branch dead) : code safety-net présent
mais producteur jamais wire → filet inactif silencieusement.

Règles :

1. **Chaque safety net DOIT avoir un test E2E** qui force le scénario qu'il adresse + assert
   que le filet a déclenché. Sans ce test, le filet est considéré "non-shipped".
2. Application immédiate :
   - DEV #18 : test miss-strike lifecycle (Phase 1, BD-B / MUST-17)
   - DEV #31 : test paranoia branch — crash drainer entre FS mutation et BDD insert,
     vérifier que la quick scan suivante re-walk le path (Phase 4, NEW test)
3. **Audit `scripts/audit-safety-nets.py`** (nice-to-have 0.17+) — détecte les modules
   `drift.py` / `recovery.py` / `paranoia*.py` sans test E2E correspondant.

## 6. ACCEPTANCE (exécutables)

**Voir `ACCEPTANCE.md`** (créé 2026-05-22) — 49 criteria exécutables couvrant 54/54 DEVs,
34/34 patterns, 8/8 DESIGN sections, 9 phases. Chaque criterion est une commande shell avec
output attendu.

Sketch des 15 criteria clés (la version complète est en `ACCEPTANCE.md`) :

| #   | Criterion                 | Commande de validation                                                                                                                          |
| --- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| 1   | Drift mechanism active    | `personalscraper library-index --mode full` puis vérif `media_file.miss_strikes > 0` pour fichiers supprimés depuis le précédent scan           |
| 2   | FK enforced               | `sqlite3 library.db "PRAGMA foreign_keys;"` returns `1` ; `PRAGMA foreign_key_check;` zero rows                                                 |
| 3   | `library-scan` exists     | `personalscraper library-scan --help` exit 0                                                                                                    |
| 4   | `library-doctor` exists   | `personalscraper library-doctor --help` exit 0 ; `library-doctor` exit 0 on healthy DB                                                          |
| 5   | `library-gc` exists       | `personalscraper library-gc --dry-run --help` exit 0                                                                                            |
| 6   | backfill-ids CLI          | `personalscraper library-index --mode backfill-ids --help` lists `backfill-ids` mode                                                            |
| 7   | Drop monolithic Protocols | `rg -n "^class MetadataProvider\b                                                                                                               | ^class TorrentClientFull\b" personalscraper/` returns zero |
| 8   | Dry-run on mutators       | `personalscraper library-repair --dry-run --help` ; `library-relink --dry-run` ; `library-clean --dry-run` ; `init-config --dry-run` all exit 0 |
| 9   | VERIFY structured events  | `personalscraper verify -v 2>&1 \| grep verify_item_done` finds events                                                                          |
| 10  | run --help lists 9 steps  | `personalscraper run --help` mentions enforce + trailers (and others)                                                                           |
| 11  | --format unified          | `personalscraper --format json library-reconcile` outputs JSON ; `--format plain` outputs plain                                                 |
| 12  | Matrix v2.1 syncs         | `personalscraper library-reconcile --dry-run` (or matrix events catalog cmd) shows no events missing from matrix                                |
| 13  | Test E2E scan→reconcile   | `make test -k test_pipeline_e2e_reconcile_clean` passes                                                                                         |
| 14  | Cleanup 8 phantom shows   | `library-reconcile` reports `path_missing=0` after cleanup                                                                                      |
| 15  | Backfill-ids first run    | `SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL` → tends toward 0                                                             |

## 7. Phases

Voir `plan/INDEX.md` et `plan/phase-NN-*.md` pour le détail. **9 phases** (post-REDO item 11)
ordonnées par dépendances :

1. Foundations BDD/indexer (drift + FK + PRAGMA discipline + tests E2E + schema_version)
2. CLI gaps (library-scan, dry-run, run-help, matrix-CLI test, backfill-ids auto-trigger)
3. Observability (VERIFY events + 6 autres per-step + cli.invoke decorator + console+log parity)
4. Path detection + cleanup (path_missing + 8 shows + flags clarif + paranoia branch wire)
5. Conformity + monolithic Protocols drop (MetadataProvider tests refactor) + GC + library-doctor
6. Format + documentation reference (heavy archive doc rot work)
7. Matrix v2.1 + agents matrix-aware
8. Polish + Plan A reset+rescrape + module-size hard-block + ACCEPTANCE.md
9. **Archive DESIGN.md updates** (banner + old→new mapping pour 7 features stale)

Estimation : **17-25 jours séquentiel, 14-20 jours parallélisable** (revue post-REDO).

## 8. References

- `IMPLEMENTATION.md` — phase tracker
- `audit/01..11` — toute la démarche d'audit
- `docs/pipeline-runs/2026-05-21-17h16-pipeline-run.md` — run réel item 5
- `docs/reference/` — architecture, indexer, commands, etc.

## 9. Risques & Mitigations

Voir item 13 §6 :

1. FK ON révèle des orphans cachés → run `foreign_key_check` AVANT activation ; cleanup d'abord.
2. Drop monolithic Protocols casse callers cachés → `rg` exhaustif pré-drop.
3. Backfill-ids first run dépasse budget → `--budget-seconds` flag, run en plusieurs sessions.
4. Matrix v2.1 + skill v2.0 mismatch → assertion bloquante au boot skill (déjà DESIGN matrix).
5. Cleanup 8 phantom shows trop agressif → dry-run d'abord, validation step-by-step.
6. Migration 005 → 006 incompat → backup `.pre-migration-6.bak` (déjà en place).
