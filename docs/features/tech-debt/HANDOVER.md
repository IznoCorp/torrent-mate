# Tech-Debt 0.16.0 — Session Handover

> **Pour la prochaine session Claude** : lis ce fichier EN ENTIER avant toute action. Il
> contient tout le contexte de la feature `tech-debt`, l'historique de l'audit pré-design,
> les 54 DEVs identifiés, les 34 patterns systémiques, l'état du plan, et les actions
> suivantes. Date de cet handover : **2026-05-22**.
>
> **⚠ Statut TRANSIENT** : ce document est temporaire. Il sera **supprimé en Phase 10.4**
> (closure post-implementation) car son contexte sera obsolète. Ne PAS y ajouter du contenu
> pérenne — utiliser `audit/`, `DESIGN.md`, `ACCEPTANCE.md`, ou `plan/` pour la doc durable.

## TL;DR (90 secondes)

- **Feature** : `tech-debt` = cleanup global cross-feature de personalscraper après merge
  de `feat/provider-ids` (v0.15.0).
- **Branch** : `fix/tech-debt` (existante, 21 commits depuis `882bc6f` item 4 closure).
- **Version bump** : 0.15.1 → **0.16.0 MINOR** (nouveaux invariants + nouvelles CLI, pas de
  breaking change).
- **Audit pré-design 14 items COMPLET** (items 1-14, certains REDO à profondeur audit-quality
  suite à challenge utilisateur).
- **DESIGN.md + plan/INDEX.md + 9 phase files + ACCEPTANCE.md (49 criteria exécutables)**
  livrés et committed.
- **4 fixes déjà shippés sur priorité absolue user** : DEV #9 (data-loss `repair_root_duplicate`),
  #11 (merkle non-déterministe), #13 (C5 race index recreate), #14 (oshash query divergence).
- **54/54 DEVs cartographiés**, **34/34 patterns leverage-mapped**, **8/8 sections DESIGN
  §9-§16 implémentées par ≥1 phase**.
- **Estimé** : 19-27 jours séquentiel, 15-22 jours parallélisable.
- **Prochaine action** : `/implement:phase` pour démarrer Phase 1 (Foundations BDD/indexer).

---

## 1. Contexte projet

### personalscraper

`personalscraper` est un **pipeline de triage média** :

1. **INGEST** : récupère les torrents complets depuis qBittorrent → staging area
2. **SORT** : classe par type (movie/show/ebook/audio) → sub-directories
3. **PROCESS** (composite clean+scrape+cleanup) : NFO + artwork via TMDB/TVDB, dedup
4. **ENFORCE** : sanitization, structure, coherence
5. **VERIFY** : qualification pre-dispatch
6. **TRAILERS** (optionnel) : acquisition trailers via yt-dlp
7. **DISPATCH** : déplacement vers les disques de stockage (Disk1-4 macFUSE NTFS)

CLI : `personalscraper <command>`. 30+ commandes top-level (pipeline + library-\* + trailers + config).

BDD locale : `~/.data/library.db` (SQLite WAL, ~44 MB, 1937 media_item, 149k media_file).

### feat/tech-debt origin

Après merge de `feat/provider-ids` (v0.15.0, SHA `db106ac`) :

1. Un **run pipeline-monitor** révèle des bugs critiques cross-feature
2. L'utilisateur demande un cleanup global = `feat/tech-debt`
3. Décision : méthodologie d'audit pré-design en 14 items, validation utilisateur entre chaque

### Branches actuelles

- **personalscraper repo** : `fix/tech-debt` (21 commits depuis `882bc6f` item 4 closure)
- **`.claude/` repo** : `personal-scraper` branch (5 commits item 4 sub-phases — matrix v2.0 +
  agents + skill v2.0)

---

## 2. Méthodologie d'audit pré-design (instructions utilisateur originales)

L'utilisateur a défini un audit en **14 items**, avec **validation utilisateur entre chaque
item**, communication en français, rien hors scope. La table-source dans IMPLEMENTATION.md :

| #   | Item                                                   | Type           | Output attendu                    |
| --- | ------------------------------------------------------ | -------------- | --------------------------------- |
| 1   | Étude des dérives des plans (cross-feature)            | Analyse        | Rapport patterns + causes racines |
| 2   | Étude du pipeline et de son fonctionnement             | Analyse        | Carto pipeline + invariants       |
| 3   | Brainstorm MAJ skill pipeline-monitor                  | Brainstorm     | Liste changements à apporter      |
| 4   | MAJ skill pipeline-monitor                             | Implémentation | Skill mise à jour committée       |
| 5   | Run pipeline-monitor (avec skill mise à jour)          | Analyse        | DEVIATION LIST + Conformity Check |
| 6   | Brainstorm améliorations suite au pipeline-monitor     | Brainstorm     | Liste items pour le design        |
| 7   | Check BDD (intégrité, conformité, cohérence, améliors) | Analyse        | Rapport BDD                       |
| 8   | Brainstorm améliorations BDD                           | Brainstorm     | Liste items pour le design        |
| 9   | Analyse commandes CLI (bugs, design, améliorations)    | Analyse        | Rapport CLI                       |
| 10  | Brainstorm améliorations CLI                           | Brainstorm     | Liste items pour le design        |
| 11  | Analyse app + conformité design                        | Analyse        | Rapport conformité globale        |
| 12  | Analyse critique design + architecture                 | Analyse        | Rapport critique structurel       |
| 13  | Brainstorm améliorations globales                      | Brainstorm     | Synthèse de tous les brainstorms  |
| 14  | Challenge final du design + plan tech-debt             | Validation     | DESIGN.md + plan/ propres         |

**Tous les 14 items ont été complétés**, certains REDO à profondeur audit-quality après
challenge utilisateur (notamment item 11). Les rapports sont dans `audit/01.md` à `audit/11.md`.

---

## 3. Historique de session (chronologique)

### Items 1-4 (sessions précédentes, déjà commit avant le 21-05)

- **Item 1** (`audit/01-plan-drift.md`) — Identification 8 patterns P1-P8 historiques de
  dérive (provider-ids ACCEPTANCE drift, etc.)
- **Item 2** (`audit/02-pipeline-cartography.md`) — Carto pipeline 9 StepReports + invariants
- **Item 3** (`audit/03-skill-update-brainstorm.md`) — Brainstorm matrix v2.0 + 10 questions Q1-Q10
- **Item 4** — Implémentation skill pipeline-monitor v2.0 en 5 sous-phases sur 2 repos
  (`.claude/personal-scraper` + `personalscraper/fix/tech-debt`). Closure commit `882bc6f`.

### Items 5-14 (session du 21-05-2026, ~16 heures)

#### Item 5 — Run pipeline-monitor v2.0 réel (10:00-17:30)

- Run réel `/pipeline-monitor --no-remediate` sur la pipeline live
- 12 DEVs identifiés (DEV #1-#12), dont DEV #9 CRITIQUE découverte par user en regardant le
  dry-run de PROCESS
- HARD gate DISPATCH a correctement bloqué (rule 11 zero-tolerance)
- Output : `docs/pipeline-runs/2026-05-21-17h16-pipeline-run.md`

#### Fixes opérateur priorité absolue (17:30-21:00)

User a demandé "fix DEV #9 + investigation DEV #11" :

- **`268cbee` fix(tech-debt) DEV #9** — `repair_root_duplicate` inversion fix (data-loss)
- **`29c4953` fix(tech-debt) DEV #11** — `compute_merkle_root` sort key tuple complet
- **`fc39f77` fix(tech-debt) DEV #13** — `_recreate_indexes` IF NOT EXISTS (C5 race workers)
- **`3993487` fix(tech-debt) DEV #14** — `_build_disk_fingerprints` + `_sample_fresh_fingerprints`
  oshash filter alignment

DEV #11 a révélé DEV #13 (race en run library-index), qui a révélé DEV #14 (filter
divergence). Chaîne de découverte (pattern P2).

Validation finale : `library-reconcile` → `merkle_drift=0` ✓.

#### Items 6-13 (brainstorms + audits, 21:00-23:00)

Production des audits dans `audit/04-pipeline-monitor-brainstorm.md`, `05-bdd-audit.md`,
`06-bdd-brainstorm.md`, `07-cli-audit.md`, `08-cli-brainstorm.md`, `09-conformity.md`,
`10-architecture-critique.md`, `11-global-synthesis.md`.

#### Item 14 — Final DESIGN + plan (commit `9649784`)

Production de :

- `DESIGN.md` (non-draft, 9 sections §0-§9)
- `plan/INDEX.md` + 8 phase files (`phase-01..phase-08.md`)
- Drafts (`DESIGN.draft.md` + `plan.draft/`) supprimés via `git rm`
- IMPLEMENTATION.md mis à jour avec 8 phases + bump 0.15.1→0.16.0

#### REDO item 11 à profondeur audit-quality (commit `6eb5f31`, ~23:00)

User a challengé : "item 11 fait complètement ?" Réponse honnête : non, seul 3 de 13 features
auditées en spot-check. User demande REDO audit-quality.

- Dispatch de **12 agents general-purpose en parallèle** (1 par feature archived)
- **235 claims/invariants/criteria** extraits et vérifiés un-par-un contre le codebase
- **26 nouveaux DEVs #24-#49** identifiés (17 NET-NEW, 9 EXTEND existants)
- **5 nouveaux patterns P30-P34** identifiés
- **Provider-ids ACCEPTANCE re-graded** : 4 sur 10 ✅ sont en réalité ❌🟡

#### Cascade REDO findings (commit `edf6d8a`, ~23:30)

- DESIGN.md gagne **§12-§16** (5 nouvelles sections — Documentation conformity, Promise
  lifecycle, Success criteria enforcement, PRAGMA discipline, Safety net E2E)
- plan/INDEX.md devient 10 phases (Phase 9 NEW = CLI Test Coverage added 2026-05-23 ;
  Phase 10 = Archive DESIGN.md updates — ex-Phase 9 renumérotée)
- `phase-10-archive-docs.md` créé (ex `phase-09-archive-docs.md` avant renum)
- `phase-09-cli-coverage.md` créé (Phase 9 NEW)
- Total estimate révisé : 13-19 j → 17-25 j

#### Full BDD reindex attempt (commit `5cb62db`, 22:00-23:30 même soirée)

User demande "indexation complète BDD avec enrich et tout". Tentative aboutit à découverte
de 5 NOUVEAUX bugs critiques :

- Step 1 (`scan_library()`) → **DEV #50** (duplicate disk rows uuid="disk_1" vs vrai
  VolumeUUID) + **DEV #53** (1863 duplicate media_item rows lookup-key mismatch)
- Cleanup manuel restauré 1937 items (1935 baseline + 2 légitimes : Monk + Squid Game)
- Step 3 (`library-index --mode enrich`) → **DEV #51** (enrich ne calcule pas oshash) + à
  l'analyse **DEV #52** (full walker pas de retry oshash sur rows existantes)
- Step 4 (`run_backfill_ids()`) → **DEV #54** (skip si canonical_provider IS NULL → chicken-
  and-egg : backfill USE canonical, jamais SET)
- Step 5 (`library-reconcile`) → état BDD propre : merkle=0, dispatch=0, releases=0

Conclusion : "tout migré + indexé" **pas possible** sans Plan A reset+rescrape (DEV #27)
ou init-canonical mode (DEV #54 fix).

#### Review pass + coverage fix (commit `cc0bb39`, 2026-05-22 dawn)

User demande : "passe review tous les items + cohérence plans/design + couvre bien
l'objectif de corriger TOUS les problèmes".

Grep automatique révèle :

- 22/54 DEVs sans citation explicite dans plan/
- 29/34 patterns sans levier explicite
- Bonus DEVs #50-#54 pas dans plan
- ACCEPTANCE.md inexistant (planifié 8.9)

Fix :

- Ajout 15 sub-phases (4 en Phase 1, 1 en Phase 4, 3 en Phase 5, 1 en Phase 6, 6 en Phase 8)
- Coverage matrix en début de chaque phase file
- DEV+Pattern+Section cross-tables dans plan/INDEX.md
- `ACCEPTANCE.md` créé avec **49 criteria exécutables**
- Estimate révisé : 17-25 j → **19-27 j séquentiel, 15-22 j parallélisable**
- Coverage finale : **54/54 DEVs ✓, 34/34 patterns ✓, 8/8 sections ✓**

---

## 4. Catalogue des findings (54 DEVs + 34 patterns)

### Les 54 DEVs

| DEV     | Sévérité | Domaine        | Description courte                                 | Status                                                                      |
| ------- | -------- | -------------- | -------------------------------------------------- | --------------------------------------------------------------------------- |
| #1      | critique | skill          | 4 agents matrix v2.0 non-discoverable              | OUVERT — Phase 7.4                                                          |
| #2      | mineur   | skill          | orphan-hunter false positive 097-TEMP              | OUVERT — Phase 7.3                                                          |
| #3      | mineur   | skill          | state-validator false claim .DS_Store              | OUVERT — Phase 7.3                                                          |
| #4      | mineur   | app            | ENFORCE scope-limited .DS_Store                    | OUVERT — Phase 6.6 (doc)                                                    |
| #5      | mineur   | app            | Counter asymmetry PROCESS:scrape                   | OUVERT — Phase 6.6 (doc)                                                    |
| #6      | majeur?  | app            | VERIFY silent stdout (events absents)              | OUVERT — Phase 3.1                                                          |
| #7      | mineur   | CLI            | `run --help` omet ENFORCE+TRAILERS                 | OUVERT — Phase 2.3                                                          |
| #8      | mineur   | skill          | Coverage gaps matrix v2.0 (~12 events)             | OUVERT — Phase 7.1                                                          |
| **#9**  | CRITIQUE | app            | `repair_root_duplicate` inversion data-loss        | **SHIPPED `268cbee`**                                                       |
| #10     | mineur   | skill          | `library-reconcile --dry-run` flag inexistant      | OUVERT — Phase 7.1 + 4.6                                                    |
| **#11** | majeur   | app            | `compute_merkle_root` sort instability             | **SHIPPED `29c4953`**                                                       |
| #12     | mineur   | BDD            | 7191 files_without_release (déco)                  | OUVERT — Phase 4.3                                                          |
| **#13** | CRITIQUE | app            | `_recreate_indexes` C5 race workers                | **SHIPPED `fc39f77`**                                                       |
| **#14** | majeur   | app            | `_build_disk_fingerprints` filter divergence       | **SHIPPED `3993487`**                                                       |
| #15     | mineur   | BDD            | `schema_version` row 3 manquante                   | OUVERT — Phase 1.5                                                          |
| #16     | CRITIQUE | CLI            | `library.scanner.scan_library()` non exposé CLI    | OUVERT — Phase 2.1                                                          |
| #17     | majeur   | BDD            | 5 phantom shows (FS supprimé)                      | OUVERT — Phase 4.3                                                          |
| #18     | CRITIQUE | BDD            | `increment_miss_strikes_for_disk` jamais appelée   | OUVERT — Phase 1.1                                                          |
| #19     | mineur   | BDD            | `PRAGMA foreign_keys = 0` runtime                  | OUVERT — Phase 1.2                                                          |
| #20     | mineur   | CLI            | `qbit-restart` référencée mais inexistante         | **RÉSOLU Phase 8.3 (Option B — matrix doc-only, cross-repo patch pending)** |
| #21     | mineur   | CLI            | `--dry-run` gaps sur 4 mutators                    | OUVERT — Phase 2.2                                                          |
| #22     | mineur   | CLI            | Output format incohérent                           | OUVERT — Phase 6.1                                                          |
| #23     | mineur   | CLI            | Aucune `cli.invoke.*` telemetry                    | OUVERT — Phase 3.2                                                          |
| #24     | majeur   | event-bus      | Catalog 13→17 events drift                         | OUVERT — Phase 8.13 + 10.1.a                                                |
| #25     | mineur   | event-bus      | Module budget violations                           | OUVERT — Phase 8.13                                                         |
| #26     | mineur   | event-bus      | `__all__` omits Backfill\*                         | OUVERT — Phase 10.1.a                                                       |
| #27     | CRITIQUE | provider-ids   | Plan A reset+rescrape jamais exécuté               | OUVERT — Phase 8.10                                                         |
| #28     | majeur   | provider-ids   | Auto-trigger backfill post-scrape jamais wired     | OUVERT — Phase 2.6 + 10.1.b                                                 |
| #29     | majeur   | api            | `MetadataProvider` Protocol toujours testé         | OUVERT — Phase 5.6                                                          |
| #30     | mineur   | scraper        | Ratings flow Pydantic boundary scope-creep         | OUVERT — Phase 5.8                                                          |
| #31     | CRITIQUE | indexer        | §17.1 paranoia branch dead                         | OUVERT — Phase 4.7                                                          |
| #32     | majeur   | media-indexer  | Archive DESIGN stale post-mig 005                  | OUVERT — Phase 10.1.c                                                       |
| #33     | majeur   | BDD            | PRAGMA busy_timeout bypass multi-site              | OUVERT — Phase 1.10                                                         |
| #34     | majeur   | BDD            | PRAGMA discipline globale bypass                   | OUVERT — Phase 1.10                                                         |
| #35     | mineur   | media-indexer  | scan_modes doc gap (4 vs 6)                        | OUVERT — Phase 10.1.c                                                       |
| #36     | mineur   | media-indexer  | `media_stream` extension undocumented              | OUVERT — Phase 10.1.c                                                       |
| #37     | mineur   | BDD            | `BEGIN IMMEDIATE` audit                            | OUVERT — Phase 1.10                                                         |
| #38     | majeur   | api            | `TorrentClientFull` re-creates monolithic          | OUVERT — Phase 5.7                                                          |
| #39     | majeur   | pipeline-obs   | DESIGN superseded by event-bus                     | OUVERT — Phase 10.1.d                                                       |
| #40     | majeur   | CLI            | DEV #6 broader — 7 per-step cmds silent            | OUVERT — Phase 3.1                                                          |
| #41     | mineur   | test-coverage  | Branch coverage drift 91→85.95%                    | OUVERT — Phase 8.14                                                         |
| #42     | mineur   | trailer        | DESIGN §4 placement stale (TV → Trailers/)         | OUVERT — Phase 10.1.e                                                       |
| #43     | mineur   | trailer        | DESIGN §14 blocking semantics inverted             | OUVERT — Phase 10.1.e                                                       |
| #44     | mineur   | ext-staging    | Docstring leak `_exclusions.py:383`                | OUVERT — Phase 10.2.a                                                       |
| #45     | mineur   | logging        | `docs/reference/logging.md` paths stale            | OUVERT — Phase 10.1.f + 10.3                                                |
| #46     | majeur   | arch-cleanup   | 0.10.0 module-size hard-block stalled 5 vers       | OUVERT — Phase 8.11                                                         |
| #47     | mineur   | arch-cleanup   | `details_payload` type drift                       | OUVERT — Phase 10.3                                                         |
| #48     | mineur   | legacy-cleanup | 43 VX leaks `docs/*.md` top-level                  | OUVERT — Phase 10.1.g + 10.2.b                                              |
| #49     | majeur   | test-realism   | `test_cli.py` @patch=52 (target ≤25)               | OUVERT — Phase 8.15                                                         |
| #50     | CRITIQUE | bonus          | `_ensure_disk_row` UUID mismatch (duplicate disks) | OUVERT — Phase 1.7                                                          |
| #51     | majeur   | bonus          | Enrich ne calcule pas oshash                       | OUVERT — Phase 1.8                                                          |
| #52     | majeur   | bonus          | Full walker pas de retry oshash                    | OUVERT — Phase 1.8                                                          |
| #53     | CRITIQUE | bonus          | `_upsert_media_item` duplicate creation            | OUVERT — Phase 8.12                                                         |
| #54     | CRITIQUE | bonus          | `run_backfill_ids` chicken-and-egg canonical       | OUVERT — Phase 1.9                                                          |

**4 SHIPPED, 50 OUVERTS** distribués sur 9 phases.

### Les 34 patterns systémiques (résumé)

- **P1-P10** : code defects (set sémantique, chaîne découverte, DDL, sémantique inversée,
  hash version, matrix coverage, observabilité, doc rot CLI, agents matrix-aware, discovery)
- **P11-P17** : infra dead (code mort, CLI surface, hard-delete, migration, schema/runtime,
  tables vides, outbox GC)
- **P18-P22** : process/UX (UX rich vs telemetry, naming conventions, matrix CLI refs, mutate
  sans dry-run, output format)
- **P23-P25** : ACCEPTANCE / activation / observability — ACCEPTANCE non re-exercised, infra
  non-activée, observability gap
- **P26-P29** : architecture — SRP CLI, FS=truth, composition Protocols, CLI=stable API
- **P30-P34** (post-REDO) : doc stale archives, promesses stallées, success criteria non
  re-mesurées, PRAGMA bypass, safety net dead

Voir `plan/INDEX.md` § "Patterns P1-P34 → leverage phases" pour le mapping complet.

---

## 5. État actuel (post commit `cc0bb39`)

### Branch fix/tech-debt — 22 commits depuis item 4 closure

```
cc0bb39 docs(tech-debt): plan completeness — 54/54 DEVs + 34/34 patterns + ACCEPTANCE.md
5cb62db docs(tech-debt): full BDD reindex attempt + 5 bonus DEVs #50-#54
edf6d8a docs(tech-debt): cascade item 11 REDO findings into synthesis + DESIGN + plan
6eb5f31 docs(tech-debt): item 11 REDO audit-quality — 13 features audited, 26 new DEVs
9649784 docs(tech-debt): item 14 final DESIGN + plan — non-draft, 8 phases ready
db8c705 docs(tech-debt): item 13 global synthesis — master backlog 80 items + 8-phase plan
9d1a4b8 docs(tech-debt): item 12 architecture critique — 7 structural critiques + 4 patterns
03b35e4 docs(tech-debt): item 11 conformity audit — 2 ACCEPTANCE_FAIL + 3 patterns
3d8ef87 docs(tech-debt): item 10 CLI brainstorm — 14 exploratory items + 7-phase plan
53e5e6d docs(tech-debt): item 9 CLI audit — 31 entry points + 4 new DEVs + 3 patterns
bc3a4a6 docs(tech-debt): item 8 brainstorm BDD — 37 items BD-* + 3 new patterns
67d73c0 docs(tech-debt): item 7 BDD audit — 5 new DEVs + drift mechanism broken
29f87e5 docs(tech-debt): item 6 brainstorm — 10 patterns + 33 items DESIGN-ready
69f60d7 docs(tech-debt): record DEV #13 + #14 discovery + final merkle_drift=0
3993487 fix(tech-debt): align _build_disk_fingerprints + _sample_fresh_fingerprints (DEV #14)
fc39f77 fix(tech-debt): make _recreate_indexes idempotent (DEV #13)
b52b592 docs(tech-debt): item 5 closure — pipeline-monitor v2.0 real-run + 12 DEV
29c4953 fix(tech-debt): make compute_merkle_root deterministic (DEV #11)
268cbee fix(tech-debt): invert repair_root_duplicate to keep fresh root copy (DEV #9)
```

(+ 3 commits anciens : `882bc6f` item 4 closure ; `f0208e4` SIGINT pipeline.py ; pre-item-4
historique)

### État BDD live (`.data/library.db`)

| Dimension                                 | Valeur                                                 |
| ----------------------------------------- | ------------------------------------------------------ |
| Path                                      | `/Users/izno/dev/PersonnalScaper/.data/library.db`     |
| Taille                                    | ~44 MB                                                 |
| user_version                              | 5                                                      |
| schema_version table                      | {1, 2, 4, 5} — row 3 manquante (DEV #15)               |
| `PRAGMA foreign_keys`                     | **0** (DEV #19)                                        |
| `PRAGMA journal_mode`                     | wal ✓                                                  |
| media_item                                | **1937** (1935 baseline + 2 legit : Monk + Squid Game) |
| media_release                             | 27,470                                                 |
| media_file actifs                         | 149,087                                                |
| media_file `oshash IS NULL`               | **118,414** (DEV #51/#52)                              |
| media_item `canonical_provider IS NULL`   | **1937 / 1937** (chain DEV #54 → #27)                  |
| media_item `external_ids_json = '{}'`     | **1937 / 1937** (chain DEV #54 → #27)                  |
| `library-reconcile` merkle_drift          | **0** ✓ (post fix #11+#14)                             |
| `library-reconcile` path_missing          | 0                                                      |
| `library-reconcile` files_without_release | 5,376 (legit sidecars + 5 phantoms DEV #17)            |

**Backups disponibles** :

- `.data/library.db.bak.pre-disk-dedup-2026-05-21` (after scan_library duplicate disks)
- `.data/library.db.bak.pre-duplicate-cleanup-2026-05-21` (after disk dedup, before media_item
  dedup)

### Working tree

```bash
$ git status --short
?? docs/archive/features/provider-ids/plan/DEVIATIONS.md  # gitignored, ignore
```

**Clean** — tout committed.

---

## 6. Plan d'exécution — 10 phases (estimé 21-30 jours séquentiel)

| #   | Phase                                                   | File                        | Effort | Status |
| --- | ------------------------------------------------------- | --------------------------- | ------ | ------ |
| 1   | Foundations BDD/indexer + PRAGMA + bonus DEVs           | `phase-01-foundations.md`   | 3-4 j  | [ ]    |
| 2   | CLI gaps + backfill-ids first run                       | `phase-02-cli-gaps.md`      | 2 j    | [ ]    |
| 3   | Observability (broadened DEV #6 → 7 cmds)               | `phase-03-observability.md` | 2 j    | [ ]    |
| 4   | Path detection + paranoia branch (DEV #31)              | `phase-04-path-cleanup.md`  | 2-3 j  | [ ]    |
| 5   | Conformity (drop Protocols + tests refactor + Pydantic) | `phase-05-conformity.md`    | 2-3 j  | [ ]    |
| 6   | Format + heavy doc work                                 | `phase-06-format-docs.md`   | 3-4 j  | [ ]    |
| 7   | Matrix v2.1 + agents matrix-aware                       | `phase-07-matrix-v21.md`    | 1-2 j  | [ ]    |
| 8   | Polish + Plan A reset + size hard-block + bonus         | `phase-08-polish.md`        | 3-4 j  | [ ]    |
| 9   | CLI Test Coverage (NEW 2026-05-23 — absorbe 8.7 SH-25)  | `phase-09-cli-coverage.md`  | 2-3 j  | [ ]    |
| 10  | Archive DESIGN.md updates (7 features) (ex-Phase 9)     | `phase-10-archive-docs.md`  | 1-2 j  | [ ]    |

Chaque phase file commence par une **coverage matrix** (Item → sub-phase → pattern) et finit
par une **gate checklist**. Voir le file individuel pour le détail.

### Dépendances inter-phases (graphe)

```
Phase 1 ─┬─→ Phase 2 (library-scan)
         ├─→ Phase 3 (parallèle possible)
         └─→ Phase 4 ──→ Phase 5
                              │
Phase 6 ──────────────────────┴─→ Phase 7 ──→ Phase 8 ──→ Phase 9 (CLI test coverage) ──→ Phase 10 (archive docs) ──→ PR
```

Phase 1 est le critical path (fondations + bonus DEVs + PRAGMA). Phases 2/3 peuvent
paralléliser avec Phase 4. Phase 8 dépend de tout (Plan A reset = closure).

---

## 7. Ce qui est fait (DONE) vs ce qui reste (TODO)

### DONE — Audit pré-design (14 items)

- ✅ Items 1-14 complétés
- ✅ Item 11 REDO à profondeur audit-quality (13 features × 235 claims)
- ✅ Cascade findings vers DESIGN + plan
- ✅ Coverage fix : 54/54 DEVs + 34/34 patterns + 8/8 sections mappés
- ✅ ACCEPTANCE.md créé (49 criteria exécutables)

### DONE — Fixes critiques (4 commits)

- ✅ DEV #9 — `repair_root_duplicate` data-loss → `268cbee`
- ✅ DEV #11 — `compute_merkle_root` non-déterministe → `29c4953`
- ✅ DEV #13 — `_recreate_indexes` C5 race → `fc39f77`
- ✅ DEV #14 — fingerprint query divergence → `3993487`

### DONE — Investigations

- ✅ Run pipeline-monitor v2.0 réel (12 DEVs surfaced)
- ✅ Audit BDD live (5 DEVs surfaced : #15-#19)
- ✅ Audit CLI (4 DEVs surfaced : #20-#23)
- ✅ Audit conformity (26 DEVs surfaced : #24-#49)
- ✅ Full BDD reindex attempt (5 bonus DEVs surfaced : #50-#54)

### TODO — 9 phases d'implémentation

50 DEVs ouverts à traiter sur 9 phases. Voir `plan/INDEX.md` § "DEV coverage matrix" pour
le mapping exhaustif.

### TODO — Plan A reset+rescrape (Phase 8.10)

C'est la sub-phase qui DÉBLOQUE provider-ids ACCEPTANCE #3 + #4 + #10 :

1. Backup library.db
2. `personalscraper library init-canonical` (créé en Phase 1.9 via DEV #54 fix)
3. `personalscraper library-index --mode backfill-ids --no-budget` (1-2 h API calls)
4. Vérification : `canonical_provider populated > 90%`

### TODO — ACCEPTANCE.md final marking (Phase 8.9 closure)

Marquer ✅/❌/🟡 à côté de chaque ACC-N à la fin de chaque phase.

---

## 8. Prochaines actions (ordre)

### Action immédiate après lecture de ce HANDOVER

```bash
# 1. Vérifier le state baseline
cd /Users/izno/dev/PersonnalScaper
git log --oneline -1     # Doit être cc0bb39
git status --short       # Doit être vide (sauf DEVIATIONS.md gitignored)
personalscraper library-reconcile | jq .merkle_drift  # Doit être []

# 2. Lire les docs principaux dans l'ordre
cat docs/features/tech-debt/HANDOVER.md         # CE FICHIER
cat IMPLEMENTATION.md                           # Phase tracker
cat docs/features/tech-debt/DESIGN.md           # 9 sections + ACCEPTANCE sketch
cat docs/features/tech-debt/plan/INDEX.md       # 9 phases + DEV/pattern cross-tables
cat docs/features/tech-debt/ACCEPTANCE.md       # 49 criteria exécutables
cat docs/features/tech-debt/plan/phase-01-foundations.md  # première phase à attaquer
```

### Démarrer Phase 1 — Foundations BDD/indexer (3-4 j)

```
/implement:phase
```

Ce skill va :

1. Lire IMPLEMENTATION.md → identifier la prochaine phase (1)
2. Lire phase-01-foundations.md → décomposer en sub-phases
3. Dispatcher un agent par sub-phase (Sonnet)
4. Phase gate au fin avec commit `chore(tech-debt): phase 1 gate — ...`

**Convention rappel** : validation utilisateur entre chaque sous-phase (cohérent avec la
méthodologie audit). Commits suivent Conventional Commits avec scope `(tech-debt)`.

### Alternative : continue inline si user préfère contrôle fin

```
On démarre Phase 1 sub-phase 1.1 (drift mechanism wire)
```

L'utilisateur valide manuellement entre chaque sub-phase. Same pattern qu'utilisé pendant
les audits.

### Si Plan A reset doit être anticipé

Le user peut vouloir faire Plan A AVANT Phase 1 (pour avoir des données provider-ids
populées plus tôt). C'est possible — Phase 1.9 (init-canonical) + Phase 8.10 (backfill) sont
techniquement indépendants des autres fixes. Discuter avec user.

---

## 9. Préférences utilisateur (memories durables à respecter)

Issues de `~/.claude/projects/-Users-izno-dev-PersonnalScaper/memory/MEMORY.md` :

- **Communication en français** (l'utilisateur écrit en français, donc Claude répond en
  français pour les conversations ; code/comments en anglais).
- **Pipeline always --dry-run first** (`feedback_pipeline_dry_run_first`) — pour chaque étape
  pipeline, dry-run avant real, show output, demande validation, puis real.
- **NO DEFERRAL absolu sur tech-debt** (`feedback_event_bus_no_deferral` étendu) — aucun
  step/test/scope item ne peut être différé. C'est pourquoi 54/54 DEVs sont dans 0.16.0,
  pas reporté à 0.17+.
- **Test de régression par bug** (`feedback_regression_test_per_bug`) — chaque bug détecté
  doit avoir un test qui le reproduit, avant ou avec le fix.
- **Multi-provider IDs séparation stricte** (`feedback_multi_provider_ids_separation`) —
  TVDB primaire, TMDB info+fallback, IMDB info uniquement. Pas de cross-contamination.
- **Pas de retro-compat avant v1.x** (`feedback_no_backcompat_before_v1`) — pas de scripts
  de migration ; modifs config/BDD/NFO ⇒ on fait évoluer en même temps qu'on code, sur
  l'unique instance.
- **`/implement:prepare-feature` artifacts never committed** — plans + DESIGN + ROADMAP
  entries restent uncommitted ; vérifier reflog avant reset/rebase.
- **Validation utilisateur entre chaque sub-phase** — méthodologie d'audit qui s'étend à
  l'implémentation. NE PAS enchaîner sans confirmation.

### Préférences additionnelles observées en session

- User a un fort sens de la rigueur — accepte les "non" honnêtes mieux que les "oui" approximatifs.
- User préfère qu'on lui présente plusieurs options avec leurs trade-offs plutôt qu'une
  décision unilatérale.
- User valorise la traçabilité (commits explicites + cross-tables).

---

## 10. Files of interest (navigation rapide)

### Tech-debt feature

```
docs/features/tech-debt/
├── HANDOVER.md                  ← CE FICHIER (à lire en premier)
├── DESIGN.md                    ← 9 sections design tech-debt
├── ACCEPTANCE.md                ← 49 criteria exécutables
├── audit/
│   ├── 01-plan-drift.md         ← P1-P8 historiques
│   ├── 02-pipeline-cartography.md
│   ├── 03-skill-update-brainstorm.md
│   ├── 04-pipeline-monitor-brainstorm.md
│   ├── 05-bdd-audit.md          ← DEV #15-#19
│   ├── 06-bdd-brainstorm.md
│   ├── 07-cli-audit.md          ← DEV #20-#23
│   ├── 08-cli-brainstorm.md
│   ├── 09-conformity.md         ← REDO audit-quality, DEV #24-#49 + bonus #50-#54
│   ├── 10-architecture-critique.md
│   └── 11-global-synthesis.md   ← Master backlog item 13
└── plan/
    ├── INDEX.md                 ← Cross-tables DEV/Pattern/Section
    ├── phase-01-foundations.md  ← drift+FK+PRAGMA+#50-#54
    ├── phase-02-cli-gaps.md
    ├── phase-03-observability.md
    ├── phase-04-path-cleanup.md ← paranoia branch DEV #31
    ├── phase-05-conformity.md   ← drop Protocols + tests refactor
    ├── phase-06-format-docs.md
    ├── phase-07-matrix-v21.md
    ├── phase-08-polish.md       ← Plan A reset + size hard-block
    └── phase-10-archive-docs.md ← 7 archived DESIGN updates
```

### Reference docs (sources actuelles)

```
docs/reference/
├── architecture.md              ← state ownership (à compléter Phase 6.3)
├── commands.md                  ← exhaustive CLI (à compléter Phase 6.2)
├── event-bus.md                 ← catalog 17 events (sync Phase 8.13 + 10.1.a)
├── external-ids-flow.md         ← provider-ids flow
├── indexer.md                   ← lifecycle media_file (à compléter Phase 6.4)
├── indexer-json-shapes.md
├── logging.md                   ← stale paths (fix Phase 10.1.f + 10.3)
├── naming.md
├── pipeline-internals.md
├── scraping.md
├── storage.md
├── testing.md
├── trailers.md
└── ... (provider API docs : tmdb, tvdb, omdb, trakt, lacale, c411, qbit, transmission, telegram, healthchecks)
```

### Archived features (à banner Phase 10.1)

```
docs/archive/features/
├── api-unify/         (audit done)
├── arch-cleanup/      (DEV #46+#47)
├── event-bus/         (DEV #24+#25+#26 → Phase 10.1.a)
├── ext-staging/       (DEV #44 → Phase 10.2.a)
├── info-cmd/          (no DESIGN, trivial)
├── legacy-cleanup/    (DEV #48 → Phase 10.1.g + 10.2.b)
├── logging/           (DEV #45 → Phase 10.1.f + 10.3)
├── media-indexer/     (DEV #31+#32+#33+#34+#35+#36+#37 → Phase 10.1.c)
├── pipeline-obs/      (DEV #39+#40 → Phase 10.1.d)
├── provider-ids/      (DEV #27+#28+#29+#30 → Phase 10.1.b)
├── test-coverage/     (DEV #41)
├── test-realism/      (DEV #49)
└── trailer/           (DEV #42+#43 → Phase 10.1.e)
```

### Skill pipeline-monitor (sur repo `.claude/`)

```
.claude/
├── skills/pipeline-monitor/
│   ├── SKILL.md (v2.0 → bump v2.1 en Phase 7.2)
│   ├── CHANGELOG.md
│   ├── host.py
│   └── references/design-conformity-matrix.md (v2.0 → bump v2.1 en Phase 7.1)
└── agents/
    ├── pipeline-orphan-hunter.md
    ├── pipeline-state-validator.md   ← FS-truth rule à ajouter Phase 7.3 DEV #3
    ├── pipeline-output-analyzer.md
    ├── pipeline-ingest-checker.md
    ├── pipeline-sort-checker.md
    ├── pipeline-scrape-checker.md
    ├── pipeline-dispatch-checker.md
    ├── pipeline-event-monitor.md
    ├── pipeline-invariant-checker.md
    ├── pipeline-bdd-validator.md
    └── pipeline-matrix-stale-detector.md
```

### Personalscraper code (cibles fixes Phase 1+)

```
personalscraper/
├── indexer/
│   ├── db.py                                ← Phase 1.10 : extract _apply_pragmas
│   ├── drift.py                             ← Phase 1.1 : wire increment_miss_strikes (DEV #18)
│   ├── reconcile.py                         ← Phase 4.1 : path_missing detector (MUST-4)
│   ├── scanner/
│   │   ├── _walker.py                       ← Phase 1.8 : retry oshash (DEV #52)
│   │   ├── _db_writes.py                    ← Phase 1.8 : oshash compute retry
│   │   └── _modes/
│   │       ├── enrich.py                    ← Phase 1.8 : add Step 4 oshash retry (DEV #51)
│   │       └── backfill_ids.py              ← Phase 1.9 : init_canonical_from_nfo (DEV #54)
│   ├── repos/disk_repo.py                   ← Phase 1.7 : real UUID lookup (DEV #50)
│   ├── outbox/
│   │   ├── _apply.py                        ← Phase 4.7 : insert scan_event outbox.* (DEV #31)
│   │   └── _drain.py
│   └── commands/scan.py                     ← Phase 1.1 : call increment_miss_strikes
├── library/
│   ├── scanner.py                           ← Phase 8.12 : _upsert_media_item dedup (DEV #53)
│   │                                          + Phase 1.7 : _ensure_disk_row UUID (DEV #50)
│   └── rescraper.py
├── api/
│   ├── metadata/_base.py                    ← Phase 5.1 : drop MetadataProvider Protocol (DEV #29)
│   └── torrent/_contracts.py                ← Phase 5.7 : drop TorrentClientFull (DEV #38)
├── commands/
│   ├── pipeline.py                          ← Phase 2.3 : run --help introspection (DEV #7)
│   │                                          + Phase 3.1 : VERIFY events (DEV #6+#40)
│   ├── library/
│   │   ├── scan.py                          ← Phase 2.1 : library-scan CLI (DEV #16) NEW
│   │   ├── doctor.py                        ← Phase 5.3 : library-doctor (SH-8) NEW
│   │   ├── gc.py                            ← Phase 5.2 : library-gc (SH-7) NEW
│   │   └── maintenance.py                   ← Phase 2.2 : --dry-run (DEV #21)
│   └── init_config.py                       ← Phase 2.2 : --dry-run (DEV #21)
├── trailers/cli.py                          ← Phase 8.6 : trailers audit alias (DEV AR-D)
└── scraper/
    ├── existing_validator.py                ← DEV #9 fix shipped commit 268cbee
    ├── tv_service.py                        ← Phase 5.8 : ExternalIds Pydantic (DEV #30)
    ├── movie_service.py                     ← idem
    └── nfo_generator.py                     ← idem
```

### Tests (additions Phase 1-8)

```
tests/
├── indexer/
│   ├── test_drift.py                        ← Phase 1.3 : test miss-strike lifecycle (MUST-17)
│   ├── test_index_ddl.py                    ← shipped commit fc39f77
│   ├── test_merkle.py                       ← shipped commit 29c4953
│   ├── test_scanner.py                      ← shipped commit 3993487
│   ├── test_index_db_pragmas.py             ← Phase 1.2 + 1.10 NEW (PRAGMA discipline)
│   ├── test_outbox_paranoia.py              ← Phase 4.7 NEW (DEV #31)
│   ├── test_ensure_disk_row.py              ← Phase 1.7 NEW (DEV #50)
│   ├── test_enrich_oshash_retry.py          ← Phase 1.8 NEW (DEV #51)
│   ├── test_walker_oshash_retry.py          ← Phase 1.8 NEW (DEV #52)
│   ├── test_init_canonical.py               ← Phase 1.9 NEW (DEV #54)
│   └── test_upsert_media_item_dedup.py      ← Phase 8.12 NEW (DEV #53)
├── integration/
│   ├── test_scan_reconcile_clean.py         ← Phase 1.4 NEW (MUST-16)
│   └── fixtures/seeded_library_fs.py        ← Phase 1.4 NEW (BD-AF)
├── scraper/
│   ├── test_existing_validator_extra.py     ← shipped commit 268cbee
│   └── test_regression_dev2_episode_ids.py
└── ...
```

---

## 11. Commands utiles pour la prochaine session

```bash
# État baseline
cd /Users/izno/dev/PersonnalScaper
git log --oneline 882bc6f..HEAD | nl   # 22 commits listés
git status --short                     # vide (sauf DEVIATIONS.md gitignored)

# Vérification BDD post-fixes
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item;"  # 1937
sqlite3 .data/library.db "PRAGMA foreign_keys;"              # 0 (DEV #19 — Phase 1.2 fix)
personalscraper library-reconcile | jq .merkle_drift         # []
personalscraper library-reconcile | jq .files_without_release  # 5376

# Validation coverage (refait à tout moment)
for n in $(seq 1 54); do
  m=$(grep -lE "DEV #?${n}\b|#${n}\b" docs/features/tech-debt/plan/*.md docs/features/tech-debt/plan/INDEX.md 2>/dev/null | wc -l | tr -d ' ')
  [ "$m" -eq 0 ] && echo "DEV #$n NOT COVERED"
done
# Doit être silent (54/54 covered)

# Démarrage Phase 1
/implement:phase
# OU manuellement :
# Lire docs/features/tech-debt/plan/phase-01-foundations.md
# Lire docs/features/tech-debt/ACCEPTANCE.md (criteria 01-10 = Phase 1)
# Démarrer sub-phase 1.1 (drift mechanism wire)
```

---

## 12. Anti-décisions (à NE PAS faire)

- ❌ **Ne pas mettre à jour `~/.gitconfig`** (CLAUDE.md global rule)
- ❌ **Ne pas commit sans demande explicite** (sauf si rule différente détectée)
- ❌ **Ne pas push sans demande explicite**
- ❌ **Ne pas force-push, ne pas amend des commits publiés**
- ❌ **Ne pas créer de nouveaux fichiers .md** sans demande (le system prompt insiste)
- ❌ **Ne pas exécuter `personalscraper` en background** (hook `block_background_pipeline.py`)
- ❌ **Ne pas utiliser `rg` sans `--type py`** (CLAUDE.md Search Safety — fixture 14GB peut
  crash machine)
- ❌ **Ne pas utiliser `curl/wget` sans `--connect-timeout 10 --max-time 30`** (hook
  `block_curl_without_timeout`)
- ❌ **Ne pas différer 0.17+** sans explicit user approval (NO DEFERRAL durable)
- ❌ **Ne pas modifier le plan sans cascade vers DESIGN + IMPLEMENTATION** (cohérence cross-doc)

---

## 13. Closure de session 2026-05-21/22

Le travail livré est conséquent :

- **~16 heures de session active** (15h00-07h00 environ avec pauses)
- **22 commits** sur fix/tech-debt
- **15 fichiers d'audit + plan + design + acceptance** créés ou mis à jour
- **54 DEVs identifiés**, 4 shippés, 50 planifiés
- **34 patterns systémiques** mappés à des leverage phases
- **2 challenges utilisateurs honorés** : REDO item 11 audit-quality + coverage fix
- **1 BDD reindex live attempt** révélant 5 bonus DEVs critiques

L'audit est **complet et solide**. Le plan est **exhaustif et traçable**. Le DESIGN est
**cohérent et challenged**. ACCEPTANCE est **exécutable**.

Reste : **implémenter** les 9 phases sur 19-27 jours. Premier pas = Phase 1.

Bon courage à la prochaine session 🚀

---

_HANDOVER rédigé 2026-05-22 par Claude (session précédente). Si questions sur des points
ambigus de cet handover, consulter d'abord les rapports audit dans `audit/`, puis demander
à l'opérateur._
