# Item 13 — Synthèse globale brainstorms 6+8+10+11+12

**Date** : 2026-05-21
**Méthode** : consolidation des 5 brainstorms (items 6, 8, 10, 11, 12) en master backlog
ordonné par dépendances + priorité. Identification des items en recouvrement, déduplication,
et préparation du séquencement de phases pour l'item 14.
**Output** : master backlog DESIGN-ready + cross-table patterns/leviers consolidé +
ordonnancement définitif des phases tech-debt 0.16.0.

---

## 0. Recap multi-dimension

| Item      | Output                      | Items codifiés                                       | DEVs/Patterns ajoutés                          |
| --------- | --------------------------- | ---------------------------------------------------- | ---------------------------------------------- |
| Item 6    | brainstorm pipeline-monitor | A-AG (33)                                            | 10 patterns P1-P10 ; DEV #1-#12 contextualisés |
| Item 7    | audit BDD                   | (rapport, pas items)                                 | DEV #15-#19 + P11-P14                          |
| Item 8    | brainstorm BDD              | BD-A..BD-AK (37)                                     | 3 patterns P15-P17                             |
| Item 9    | audit CLI                   | (rapport)                                            | DEV #20-#23 + P18-P22                          |
| Item 10   | brainstorm CLI              | CL-A..CL-AN (35)                                     | (consolidation + exploratoires)                |
| Item 11   | conformité                  | CF-A..CF-K (11)                                      | 3 patterns P23-P25                             |
| Item 12   | architecture critique       | AR-A..AR-G (7)                                       | 4 patterns P26-P29                             |
| **Total** |                             | **130 items uniques codifiés** (avant dédoublonnage) | **29 patterns P1-P29 + 23 DEVs #1-#23**        |

---

## 1. Master backlog — déduplication

Beaucoup d'items se recouvrent entre les brainstorms. Identification des "items équivalents" :

| Item canonical                                | Aliases multiples                                                                                                  | Domaine             |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------- |
| **MUST-1 Drift mechanism fix**                | item 6 (implicite DEV #18) ; item 8 BD-A + BD-B ; item 11 (CF-D folds)                                             | indexer             |
| **MUST-2 FK enforcement**                     | item 6 (implicite DEV #19) ; item 8 BD-J + BD-K ; item 11 (CF-D folds)                                             | BDD                 |
| **MUST-3 library-scan CLI**                   | item 6 G (Top Chef France investig — résolu par scan) ; item 8 BD-G ; item 9 CL-L ; item 11 CF-A (provider-ids #3) | CLI                 |
| **MUST-4 Path missing detector**              | item 8 BD-C + BD-D                                                                                                 | indexer             |
| **MUST-5 repair_root_duplicate**              | (déjà traité DEV #9 fix)                                                                                           | scraper             |
| **MUST-6 merkle determinism**                 | (déjà traité DEV #11 fix)                                                                                          | indexer             |
| **MUST-7 idx_stream_kind_codec race**         | (déjà traité DEV #13 fix)                                                                                          | indexer             |
| **MUST-8 fingerprint queries alignment**      | (déjà traité DEV #14 fix)                                                                                          | indexer             |
| **MUST-9 dry-run gap (4 commandes)**          | item 9 CL-A (DEV #21)                                                                                              | CLI                 |
| **MUST-10 VERIFY structured events**          | item 6 Q (matrix v2.1 §VERIFY) ; item 9 CL-G (DEV #6)                                                              | CLI + observability |
| **MUST-11 run --help introspection**          | item 6 Y ; item 9 CL-I (DEV #7)                                                                                    | CLI doc             |
| **MUST-12 Matrix CLI references test**        | item 9 CL-T (catch DEV #10, #20)                                                                                   | tests               |
| **MUST-13 CI coverage CLI**                   | item 9 CL-K                                                                                                        | tests               |
| **MUST-14 Drop monolithic Protocols**         | item 11 CF-B (provider-ids #6)                                                                                     | api refactor        |
| **MUST-15 Matrix v2.1 + agents matrix-aware** | item 6 M, N, O, P, Q, R, S, T                                                                                      | skill               |
| **MUST-16 Test E2E scan→reconcile clean**     | item 8 BD-AG + BD-AF (fixture)                                                                                     | tests               |
| **MUST-17 Test miss-strike lifecycle**        | item 8 BD-B                                                                                                        | tests               |
| **MUST-18 Cleanup 8 shows orphans**           | item 8 BD-F                                                                                                        | one-shot            |
| **MUST-19 Backfill-ids first run**            | item 8 BD-T + item 6 L                                                                                             | one-shot            |

Total **MUST-1..MUST-19** (19 items must-have, 4 déjà traités).

Reste 15 items must-have à livrer pour 0.16.0.

### Should-have consolidé

| Item                                             | Aliases                                 | Domaine             |
| ------------------------------------------------ | --------------------------------------- | ------------------- | ---------------------------- | --- |
| **SH-1 Document lifecycle media_file**           | item 8 BD-E                             | doc                 |
| **SH-2 Documentation runbook backfill-ids**      | item 8 BD-R ; item 11 CF-H              | doc + ops           |
| **SH-3 Cron backfill-ids**                       | item 8 BD-S                             | ops                 |
| **SH-4 Hard-delete protections**                 | item 8 BD-M                             | code audit          |
| **SH-5 Audit FK orphans manuel**                 | item 8 BD-AE                            | one-shot validation |
| **SH-6 Audit pending_op + item_issue**           | item 8 BD-U + BD-V                      | code audit (P16)    |
| **SH-7 index_outbox GC**                         | item 8 BD-W ; item 10 CL-N (library-gc) | ops + CLI           |
| **SH-8 library-doctor command**                  | item 8 BD-Y ; item 9 CL-M               | CLI                 |
| **SH-9 PRAGMA integrity_check au boot**          | item 8 BD-L                             | code                |
| **SH-10 cli.invoke telemetry decorator**         | item 9 CL-F (DEV #23)                   | observability       |
| **SH-11 Console+log parity test**                | item 9 CL-H (DEV #6 generalised)        | tests               |
| **SH-12 Doc reference exhaustive `commands.md`** | item 9 CL-J                             | doc                 |
| \*\*SH-13 --format json                          | plain                                   | rich global\*\*     | item 9 CL-D + CL-E (DEV #22) | CLI |
| **SH-14 qbit-restart command**                   | item 9 CL-B (DEV #20)                   | CLI                 |
| **SH-15 library-reconcile flags clarif**         | item 9 CL-C (DEV #10)                   | CLI doc             |
| **SH-16 ACCEPTANCE re-exercise process**         | item 11 CF-C, CF-E, CF-I, CF-J          | process             |
| **SH-17 Audit dead infrastructure**              | item 11 CF-G ; item 7 P11               | code audit          |
| **SH-18 State ownership doc**                    | item 12 AR-A                            | doc                 |
| **SH-19 Module relationships doc**               | item 12 AR-B                            | doc                 |
| **SH-20 Anti-décisions doc**                     | item 12 AR-E                            | doc                 |
| **SH-21 Expose clean+cleanup CLI**               | item 12 AR-C                            | CLI                 |
| **SH-22 Trailers verify rename alias**           | item 12 AR-D                            | CLI                 |
| **SH-23 Schema_version row 3 cleanup**           | item 8 BD-N (DEV #15)                   | one-shot            |
| **SH-24 Pipeline matrix events update v2.1**     | item 6 M + autres                       | skill               |
| **SH-25 Pin commands tests**                     | item 9 CL-S                             | tests               |
| **SH-26 Audit modules sans CLI**                 | item 8 BD-H                             | code audit (P12)    |

Total **SH-1..SH-26** (26 items should-have).

### Nice-to-have consolidé (priorité 3 — 0.17+)

Recensement bref :

- item 6 nice : F, G, K, V, W, X, AA (7)
- item 8 nice : BD-O, BD-P, BD-Q, BD-AB, BD-AC, BD-AD, BD-X, BD-Z, BD-AA, BD-AI, BD-AJ, BD-AK (12)
- item 10 nice : CL-Q, CL-R, CL-U..CL-AN (14 explicites)
- item 11 nice : CF-F, CF-K (2)
- item 12 nice : AR-F, AR-G + namespace refactor + enforce decomp (4 majeurs)

Total **nice-to-have ~39 items** différés à 0.17+. NON listés ici en détail — re-cumulables
depuis les brainstorms individuels.

---

## 2. Cross-table master patterns / leviers

Consolidation P1-P29 :

### Patterns "code defect" (P1-P10 du run + P15)

| Pattern                                              | Domaine    | Levier MUST/SH                                         |
| ---------------------------------------------------- | ---------- | ------------------------------------------------------ |
| P1 Set sémantique partagé sans fn unique             | code       | MUST-8 fingerprint + audit transversal SH-17           |
| P2 Chaîne de découverte cachée                       | code+tests | MUST-16 + MUST-17 + règle SH-16 "validation à l'usage" |
| P3 DDL non-idempotent + concurrence                  | code       | MUST-7 (treated) + lint custom (nice)                  |
| P4 Sémantique inversée non pinned                    | tests      | MUST-5 (treated) + audit destructive ops (nice)        |
| P5 Hash sans tag de version                          | schema     | SH (nice) — `*_algo_version`                           |
| P6 Coverage gap matrix vs code-emit                  | skill      | MUST-15 matrix v2.1                                    |
| P7 Observabilité asymétrique (VERIFY)                | code       | MUST-10 + SH-11                                        |
| P8 Doc rot CLI vs impl                               | doc        | MUST-11 + SH-12                                        |
| P9 Agents non matrix-aware                           | skill      | MUST-15                                                |
| P10 Agent discovery non hot-reloadable               | tooling    | doc only — "rerun after agent change"                  |
| P15 Schema declare contrainte, runtime n'enforce pas | code       | MUST-2 + SH-9                                          |

### Patterns "infra dead" (P11-P14 + P16-P17 + P24)

| Pattern                                                 | Domaine     | Levier                                      |
| ------------------------------------------------------- | ----------- | ------------------------------------------- |
| P11 Code mort chemins critiques                         | code        | MUST-1 + SH-17                              |
| P12 CLI surface incomplète                              | code        | MUST-3 + MUST-13 + SH-26 + SH-8             |
| P13 Hard-delete sans cleanup downstream                 | code+ops    | MUST-4 + SH-4                               |
| P14 Migration buggy → résidu permanent                  | infra       | SH-23 + lint custom migration (nice)        |
| P16 Tables/colonnes vides jamais peuplées               | code+schema | SH-6 + audit                                |
| P17 Outbox/queue sans GC                                | code        | SH-7                                        |
| P24 Infrastructure invariants déclarés mais pas activés | code        | MUST-1, MUST-2 + SH-9 + library-doctor SH-8 |

### Patterns "process/ACCEPTANCE" (P18-P23 + P25)

| Pattern                                                   | Domaine | Levier                       |
| --------------------------------------------------------- | ------- | ---------------------------- |
| P18 UX rich vs telemetry structurée non-tracée            | code    | MUST-10 + SH-10 + SH-11      |
| P19 Inconsistance conventions par groupe                  | naming  | SH-22 + nice (rename, group) |
| P20 Matrix/SKILL references non-existent CLI              | tests   | MUST-12                      |
| P21 Mutate commands sans dry-run                          | code    | MUST-9                       |
| P22 Output format hardcoded inconsistent                  | code+UX | SH-13                        |
| P23 ACCEPTANCE ticée par phase gate mais pas par exercise | process | SH-16                        |
| P25 Observability gap par UX preference                   | code    | déjà couvert P18 + MUST-10   |

### Patterns "architecture" (P26-P29)

| Pattern                                         | Domaine      | Levier                               |
| ----------------------------------------------- | ------------ | ------------------------------------ |
| P26 Single-responsibility per CLI command       | architecture | nice (decomp enforce, rename ambigu) |
| P27 FS = vérité, BDD = projection               | architecture | SH-18 doc                            |
| P28 Composition over inheritance pour Protocols | architecture | MUST-14                              |
| P29 CLI = stable public API                     | architecture | SH-12 + nice (CL-AG convention)      |

→ **Tous les 29 patterns ont un ou plusieurs items must/should associés**. Le DESIGN tech-debt
peut référencer chaque pattern → ses leviers, en garantissant la couverture complète.

---

## 3. Ordonnancement des phases (séquencement définitif)

Plan ordonné par dépendances + capacité de parallélisation.

### Phase 1 — Foundations BDD/indexer (jours 1-3)

Objectif : restaurer le drift mechanism, activer les invariants, stabiliser les fondations BDD.

- **MUST-1** Drift fix (`increment_miss_strikes_for_disk` wired)
- **MUST-2** PRAGMA foreign_keys = ON
- **MUST-17** Test miss-strike lifecycle (valide MUST-1)
- **MUST-16** Test scan→reconcile=clean fixture (valide MUST-1 + MUST-2)
- **SH-23** schema_version row 3 cleanup (one-shot)
- **SH-9** PRAGMA integrity_check au boot

### Phase 2 — CLI gaps (jours 3-5)

Objectif : combler les commandes manquantes, fix les bugs CLI critiques.

- **MUST-3** library-scan CLI (résout DEV #16 + provider-ids #3)
- **MUST-9** --dry-run gaps (4 commandes mutateurs)
- **MUST-11** run --help introspection (DEV #7)
- **MUST-12** Test "matrix references valid CLI" (DEV #10 + #20)
- **MUST-13** CI coverage CLI
- **MUST-19** Backfill-ids first run (one-shot, dépend MUST-3)

### Phase 3 — Observability + telemetry (jours 5-7)

Objectif : combler le gap "user-facing vs machine-telemetry".

- **MUST-10** VERIFY structured events
- **SH-10** cli.invoke decorator (DEV #23)
- **SH-11** Console+log parity test (P18 enforcement)

### Phase 4 — Path detection + cleanup (jours 7-9)

Objectif : nettoyer les phantoms, valider les invariants en production.

- **MUST-4** Path missing detector
- **MUST-18** Cleanup 8 shows orphans (dépend MUST-3 + MUST-4)
- **SH-5** Audit FK orphans manuel
- **SH-4** Hard-delete protections audit
- **SH-15** library-reconcile flags clarif

### Phase 5 — Conformity / monolithic protocols drop (jours 9-11)

Objectif : honorer les ACCEPTANCE_FAIL provider-ids restantes.

- **MUST-14** Drop `MetadataProvider` + `TorrentClientFull` (provider-ids #6)
- **SH-7** index_outbox GC + library-gc CLI
- **SH-8** library-doctor command (consolide MUST-2 check + drift + outbox lag + provider-IDs %)

### Phase 6 — Format + doc unification (jours 11-13)

Objectif : standardiser output + docs reference exhaustives.

- **SH-13** --format json|plain|rich global
- **SH-12** Doc reference exhaustive commands.md
- **SH-1** Document lifecycle media_file
- **SH-2** Documentation runbook backfill-ids
- **SH-18** State ownership doc
- **SH-19** Module relationships doc
- **SH-20** Anti-décisions doc

### Phase 7 — Skill matrix v2.1 (jours 13-15)

Objectif : sync matrix avec les events réels du pipeline + agents matrix-aware.

- **MUST-15** Matrix v2.1 + agents matrix-aware prompts
- **SH-24** Pipeline matrix events update (les ~12 coverage gaps)

### Phase 8 — Polish + nice (jours 15-17+)

Objectif : completer les should-have restants.

- **SH-3** Cron backfill-ids
- **SH-6** Audit pending_op + item_issue
- **SH-14** qbit-restart (ou suppression mention matrix)
- **SH-17** Audit dead infrastructure
- **SH-21** Expose clean+cleanup CLI
- **SH-22** Trailers verify rename alias
- **SH-25** Pin commands tests
- **SH-26** Audit modules sans CLI
- **SH-16** ACCEPTANCE re-exercise process docs

### Hors-scope 0.16.0 (différés 0.17+)

Tous les nice-to-have des 5 brainstorms (~39 items).

---

## 4. Estimation finale 0.16.0

| Phase                            | Effort | Cumul |
| -------------------------------- | ------ | ----- |
| 1 — Foundations BDD/indexer      | 2-3 j  | 2-3   |
| 2 — CLI gaps                     | 2 j    | 4-5   |
| 3 — Observability                | 2 j    | 6-7   |
| 4 — Path detection + cleanup     | 2 j    | 8-9   |
| 5 — Conformity + monolithic drop | 2 j    | 10-11 |
| 6 — Format + doc                 | 2-3 j  | 12-14 |
| 7 — Matrix v2.1 + agents         | 1-2 j  | 13-16 |
| 8 — Polish + nice                | 2-3 j  | 15-19 |

Total : **15-19 jours** (séquentiel), **13-17 jours** (parallélisable optimal — 2 phases peuvent
tourner en parallèle si dimensions disjointes : ex P3 observability + P4 path detection).

Cohérent avec l'estimation cumulative items 6-12 (~13-22 j). Plus précis et actionnable.

---

## 5. Branch + versionning

- **Branch** : `fix/tech-debt` (existante)
- **Type** : bugfix au sens commit conventions, MAIS scope >> bugfix simple
- **Version bump** : **0.15.1 → 0.16.0 (MINOR)**, pas 0.15.2

Justification du minor bump :

- Nouveaux invariants enforced (FK, drift)
- Nouvelles commandes CLI exposées (library-scan, library-doctor, library-gc, qbit-restart,
  clean, cleanup, trailers audit, library-backfill-ids)
- Nouveau format flag global (`--format`)
- Nouvelles règles process (validation à l'usage, ACCEPTANCE re-exercise, dead infra audit)
- Matrix v2.1 (skill version bump)

Pas de breaking change utilisateur : tous les renames sont via alias deprecation.

→ Décision DESIGN : **VERSION bump 0.15.1 → 0.16.0** au create-branch tech-debt.

Note : la branche actuelle s'appelle `fix/tech-debt` (créé en bugfix). Pour conformer au mapping
type → branch prefix de `/implement:create-branch`, la branche devrait être `feat/tech-debt`.
Décision : **garder `fix/tech-debt` pour ce cycle** (renommer = git history complexity), figer
la convention "scope = type le plus large rencontré" pour les futures features.

---

## 6. Risk analysis

| Risk                                              | Impact | Mitigation                                                                              |
| ------------------------------------------------- | ------ | --------------------------------------------------------------------------------------- |
| Migration 005 → 006 introduit incompat            | low    | Backup automatique `.pre-migration-6.bak` (déjà en place) + tests E2E                   |
| FK ON révèle des orphans cachés                   | medium | Phase 1 run `PRAGMA foreign_key_check` AVANT activation ; si non-vide, cleanup d'abord  |
| Drop monolithic Protocols casse callers cachés    | medium | Audit `rg` exhaustif PRÉ-drop ; migration progressive (deprecation warning 1 release ?) |
| Backfill-ids first run prend > budget             | low    | `--budget-seconds` flag existant, run en plusieurs sessions                             |
| Phase 7 matrix v2.1 bumpe skill v2.1              | low    | Backward-compat assertion (skill v2.0 refuse de tourner sur matrix v2.1 — DESIGN)       |
| Cleanup 8 shows orphans soft-delete trop agressif | medium | Run `--dry-run` d'abord, validation user step-by-step (déjà la doctrine)                |

---

## 7. Output

Master backlog item 13 :

- **15 items MUST** restants pour 0.16.0 (4 already done via fix commits)
- **26 items SHOULD** pour 0.16.0
- **~39 items NICE** différés à 0.17+
- **29 patterns P1-P29** tous mappés à des leviers
- **8 phases ordonnées** avec dépendances explicites
- **13-19 jours estimés** (15-19 séquentiel, 13-17 parallélisable)
- **Version bump 0.16.0 MINOR** (non-breaking)

Cet item 13 = **base directe pour item 14**. Item 14 prend ce master backlog, le valide une
dernière fois, rédige le DESIGN.md final non-draft + plan/INDEX.md + phases-01..phases-08.md.

---

## 8. POST-REDO ADDENDUM (2026-05-21)

Suite à l'audit-quality REDO d'item 11 (commit `6eb5f31`), **26 nouveaux DEVs #24-#49** sont
intégrés au master backlog. Cette section consolide leur traitement dans le DESIGN tech-debt.

### 8.1 Master backlog enrichi

| Bloc         | Avant            | Après REDO                                  |
| ------------ | ---------------- | ------------------------------------------- |
| MUST         | 15 (11 restants) | 17 (13 restants) — ajout #27, #31 critiques |
| SHOULD       | 26               | 44 — ajout 18                               |
| NICE / 0.17+ | ~39              | ~45 — ajout 6                               |
| Patterns     | P1-P29           | P1-P34 (+5)                                 |

### 8.2 Nouveaux DEVs cartographiés par phase (post-REDO)

| Phase                   | DEVs originaux               | DEVs ajoutés post-REDO                                                                                                                                                                                                                                                                                                                                    |
| ----------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 Foundations           | DEV #18 #19 + MUST-1/2/16/17 | **DEV #33 + #34** (DEV #19 extended PRAGMA bypass multi-sites) ; **DEV #37** (BEGIN IMMEDIATE audit)                                                                                                                                                                                                                                                      |
| 2 CLI gaps              | MUST-3/9/11/12/13/19         | **DEV #28** (auto-trigger backfill post-scrape)                                                                                                                                                                                                                                                                                                           |
| 3 Observability         | MUST-10 + SH-10/11           | **DEV #40** (DEV #6 broadened — 7 per-step subcommands silent)                                                                                                                                                                                                                                                                                            |
| 4 Path cleanup          | MUST-4/18                    | **DEV #31** (paranoia branch dead — outbox drainer never writes scan_event) — **CRITIQUE NEW**                                                                                                                                                                                                                                                            |
| 5 Conformity            | MUST-14 (drop monolithic)    | **DEV #29** (MetadataProvider Protocol still tested), **DEV #38** (TorrentClientFull 2nd vector)                                                                                                                                                                                                                                                          |
| 6 Format + docs         | SH-1/2/12/13/18/19/20        | **DEV #24** (event-bus catalog 13→17), **#26** ($\_\_all\_\_$ omits Backfill), **#32** (media-indexer DESIGN.md stale post-mig 005), **#35** (scan_modes mismatch), **#36** (media_stream undocumented), **#41** (test-coverage branch drift), **#45** (logging.md broken paths), **#47** (details_payload type drift)                                    |
| 7 Matrix v2.1           | MUST-15 + SH-24              | (no change)                                                                                                                                                                                                                                                                                                                                               |
| 8 Polish                | SH-3/6/14/17/21/22/25/26/16  | **DEV #25** (event-bus module budgets), **#27** (Plan A reset+rescrape never executed — execute in Phase 8), **#30** (ratings Pydantic boundary), **#44** (ext-staging docstring leak), **#46** (0.10.0 module-size promise — promote check-module-size to hard block), **#48** (legacy VX leaks), **#49** (test_cli @patch trim + success criteria gate) |
| **9 Archive doc** (NEW) | —                            | **DEV #39** (pipeline-obs superseded banner), **#42** (trailer placement DESIGN stale), **#43** (trailer blocking semantics inverted), banner + old→new mapping pour 7 features (event-bus, provider-ids, media-indexer, pipeline-obs, trailer, logging, legacy-cleanup)                                                                                  |

### 8.3 Phase efforts revised

| Phase     | Original | Post-REDO                                                                              |
| --------- | -------- | -------------------------------------------------------------------------------------- |
| 1         | 2-3 j    | 2-3 j (DEV #33+34 fold in DEV #19 work)                                                |
| 2         | 2 j      | 2 j (DEV #28 within budget)                                                            |
| 3         | 2 j      | 2 j (DEV #40 fold in DEV #6)                                                           |
| 4         | 2 j      | **2-3 j** (DEV #31 paranoia branch = new safety net wire + E2E test)                   |
| 5         | 2 j      | **2-3 j** (DEV #29+38 monolithic Protocol drop is heavier than estimated)              |
| 6         | 2-3 j    | **3-4 j** (heavy doc rot work : 7 features + 5 reference docs to update)               |
| 7         | 1-2 j    | 1-2 j                                                                                  |
| 8         | 2-3 j    | **3-4 j** (DEV #27 Plan A reset is significant ; DEV #46 promote module-size to block) |
| **9 NEW** | —        | **1-2 j** (archive DESIGN.md banner + mapping for 7 features)                          |

**Nouveau total** : **17-25 jours** (séquentiel), **14-20 jours** (parallélisable). Vs
13-19 j original = **+3-6 jours**.

### 8.4 5 nouveaux patterns P30-P34

Cf `audit/09-conformity.md` §2. Tous mappés à des leviers existants ou nouveaux :

- **P30 DOC_ROT** → Phase 6+9 (sync archive DESIGN + reference docs)
- **P31 PROMISE_STALL** → DEV #46 (promote check-module-size to hard block)
- **P32 GATE_DRIFT** → SH-16 + CF-J extended (re-measure success criteria at gate)
- **P33 PRAGMA_BYPASS** → Phase 1 DEV #34 (extract `_apply_pragmas()` + lint rule)
- **P34 SAFETY_NET_DEAD** → Phase 4 DEV #31 + règle "chaque safety net a un E2E"

### 8.5 Decision summary

- **Tous les items 6/8/10/12 conservés tels quels** (validés par REDO)
- **Item 13 ENRICHED** par cet addendum
- **DESIGN.md** must add §12-§16 (cf 09-conformity.md §4.1)
- **plan/** adds Phase 9, expands Phase 6 + 8 efforts
- **Estimate 0.16.0** : 13-19 j → **17-25 j** (séquentiel), 14-20 j parallélisable

Cet addendum ferme l'audit pré-design tech-debt. Item 14 doit être révisé pour ces points.
