# Implementation Progress — tech-debt

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Tech-Debt (Global Cross-Feature Fixes) (type: minor)
**Version bump**: 0.15.1 → 0.16.0 (decision item 13 §5)
**Branch**: fix/tech-debt (conservée — voir item 13 §5)
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/tech-debt/DESIGN.md
**Master plan**: docs/features/tech-debt/plan/INDEX.md

## Statut actuel

**✅ Audit pré-design 14 items COMPLET.** DESIGN.md + plan/ produits. 8 phases ordonnées
(13-19 jours estimés). Démarrage `/implement:phase` quand prêt.

4 fix commits déjà shipped sur priorité absolue user (DEV #9, #11, #13, #14). 6 phases doc
audit committed (items 5-13).

## Audit pré-design (14 items)

Méthode : un par un, validation utilisateur entre chaque, communication en français, rien hors scope.

| #   | Item                                                   | Type           | Output attendu                        | Status                                                                                                                                                                                                                                                                                                        |
| --- | ------------------------------------------------------ | -------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Étude des dérives des plans (cross-feature)            | Analyse        | Rapport patterns + causes racines     | [x] (audit/01-plan-drift.md)                                                                                                                                                                                                                                                                                  |
| 2   | Étude du pipeline et de son fonctionnement             | Analyse        | Carto pipeline + invariants           | [x] (audit/02-pipeline-cartography.md)                                                                                                                                                                                                                                                                        |
| 3   | Brainstorm MAJ skill pipeline-monitor                  | Brainstorm     | Liste changements à apporter          | [x] (audit/03-skill-update-brainstorm.md + Q1-Q10 décidées)                                                                                                                                                                                                                                                   |
| 4   | MAJ skill pipeline-monitor                             | Implémentation | Skill mise à jour committée           | [x] (matrix v2.0 + SIGINT + 4 agents + SKILL.md + host.py)                                                                                                                                                                                                                                                    |
| 5   | Run pipeline-monitor (avec skill mise à jour)          | Analyse        | DEVIATION LIST + Conformity Check     | [x] (docs/pipeline-runs/2026-05-21-17h16-pipeline-run.md — 12 DEV ; DEV #9 critique data-loss + DEV #11 majeur merkle non-déterministe traités hors-scope sur priorité absolue user)                                                                                                                          |
| 6   | Brainstorm améliorations suite au pipeline-monitor     | Brainstorm     | Liste items pour le design            | [x] (audit/04-pipeline-monitor-brainstorm.md — 10 patterns P1-P10 + 33 items A-AG triés must/should/nice)                                                                                                                                                                                                     |
| 7   | Check BDD (intégrité, conformité, cohérence, améliors) | Analyse        | Rapport BDD                           | [x] (audit/05-bdd-audit.md — DEV #15-#19 nouveaux ; cause racine décomposée pour DEV #12 ; 4 nouveaux patterns P11-P14)                                                                                                                                                                                       |
| 8   | Brainstorm améliorations BDD                           | Brainstorm     | Liste items pour le design            | [x] (audit/06-bdd-brainstorm.md — 37 items BD-A..BD-AK + 3 nouveaux patterns P15-P17 + plan 5 phases BDD 9-14j)                                                                                                                                                                                               |
| 9   | Analyse commandes CLI (bugs, design, améliorations)    | Analyse        | Rapport CLI                           | [x] (audit/07-cli-audit.md — 31 entry points inventoriés ; 4 DEV #20-#23 ; 3 patterns P20-P22 ; 20 items CL-A..CL-T)                                                                                                                                                                                          |
| 10  | Brainstorm améliorations CLI                           | Brainstorm     | Liste items pour le design            | [x] (audit/08-cli-brainstorm.md — 14 items exploratoires CL-U..CL-AN ajoutés ; plan 7 phases CLI ; tableau global multi-dim 13-22j)                                                                                                                                                                           |
| 11  | Analyse app + conformité design                        | Analyse        | Rapport conformité globale            | [x] **REDO audit-quality** (audit/09-conformity.md — 13 features audités exhaustivement ; 235 claims vérifiées ; 26 DEVs #24-#49 + 5 BONUS DEVs #50-#54 trouvés en reindex BDD attempt 2026-05-21 ; 5 patterns P30-P34 ; provider-ids ACCEPTANCE re-grade 4/10 ✅→❌🟡 ; +2-3 j → +3-4 j sur estimate 0.16.0) |
| 12  | Analyse critique design + architecture                 | Analyse        | Rapport critique structurel           | [x] (audit/10-architecture-critique.md — 7 critiques structurelles A-G ; 4 patterns P26-P29 ; 7 items AR-A..AR-G ; net 1-2 j 0.16.0)                                                                                                                                                                          |
| 13  | Brainstorm améliorations globales                      | Brainstorm     | Synthèse de tous les brainstorms      | [x] (audit/11-global-synthesis.md — 15 MUST + 26 SHOULD + ~39 NICE déférés ; 29 patterns P1-P29 tous mappés ; plan 8 phases ; 13-19 j estimés)                                                                                                                                                                |
| 14  | Challenge final du design + plan tech-debt             | Validation     | DESIGN.md + plan/ propres (non-draft) | [x] (DESIGN.md + plan/INDEX.md + 8 phase files ; drafts supprimés ; 15 ACCEPTANCE criteria executables ; bump 0.16.0 MINOR decided)                                                                                                                                                                           |

## Phases d'implémentation

Voir `docs/features/tech-debt/plan/INDEX.md` pour le détail. **9 phases** (post-REDO item 11)
ordonnées par dépendances :

| #   | Phase                                        | File                      | Effort | Status |
| --- | -------------------------------------------- | ------------------------- | ------ | ------ |
| 1   | Foundations BDD/indexer + PRAGMA discipline  | phase-01-foundations.md   | 2-3 j  | [ ]    |
| 2   | CLI gaps + backfill auto-trigger             | phase-02-cli-gaps.md      | 2 j    | [ ]    |
| 3   | Observability (broadened)                    | phase-03-observability.md | 2 j    | [ ]    |
| 4   | Path + paranoia branch + cleanup             | phase-04-path-cleanup.md  | 2-3 j  | [ ]    |
| 5   | Conformity (drop Protocols + tests refactor) | phase-05-conformity.md    | 2-3 j  | [ ]    |
| 6   | Format + heavy doc work                      | phase-06-format-docs.md   | 3-4 j  | [ ]    |
| 7   | Matrix v2.1 + agents matrix-aware            | phase-07-matrix-v21.md    | 1-2 j  | [ ]    |
| 8   | Polish + Plan A reset + size hard-block      | phase-08-polish.md        | 3-4 j  | [ ]    |
| 9   | **Archive DESIGN.md updates (NEW)**          | phase-09-archive-docs.md  | 1-2 j  | [ ]    |

**Total post-REDO** : **17-25 jours séquentiel, 14-20 jours parallélisable**. Vs original
13-19 j = +3-6 j suite à l'audit-quality REDO item 11 (`6eb5f31`, 26 nouveaux DEVs).

## Already shipped (priority absolue user, hors-plan)

| SHA       | DEV | Description                                                       |
| --------- | --- | ----------------------------------------------------------------- |
| `268cbee` | #9  | repair_root_duplicate inversion fix (data-loss)                   |
| `29c4953` | #11 | compute_merkle_root sort-key determinism                          |
| `fc39f77` | #13 | \_recreate_indexes IF NOT EXISTS (C5 race workers)                |
| `3993487` | #14 | \_build_disk_fingerprints + \_sample_fresh_fingerprints alignment |

## Item 4 — clos (2026-05-21)

Réalisé en 5 sous-phases, 2 repos en parallèle. Branches : `.claude/personal-scraper`
(skill + agents + matrix) et `personalscraper/fix/tech-debt` (pipeline.py).

| Sous-phase | Repo                            | SHA       | Livrable                                                                                                                                                                                                                                                      |
| ---------- | ------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.1        | `.claude/personal-scraper`      | `110f3ae` | Matrix v2.0 : 9 StepReports, 5 catégories (ACCEPTANCE_FAIL), 19 invariants AD–AV, pré-recovery, connexes                                                                                                                                                      |
| 4.2        | `personalscraper/fix/tech-debt` | `f0208e4` | SIGINT inter-step : `Pipeline.request_shutdown()`, `_PipelineInterrupted`, handler installé en `run()`, restauré en finally. 11 tests de régression.                                                                                                          |
| 4.3        | `.claude/personal-scraper`      | `77b7946` | 4 agents : `pipeline-event-monitor`, `pipeline-invariant-checker`, `pipeline-bdd-validator`, `pipeline-matrix-stale-detector`                                                                                                                                 |
| 4.4        | `.claude/personal-scraper`      | `df19183` | SKILL.md v2.0 : `MATRIX_VERSION` assertion, 9 StepReports, 5 catégories, `--remediate` flag (read-only par défaut), wrapping process (Q5), simulation mode (BJ), weird outputs log (BK), library-reconcile cross-correlation (BL), compare précédent run (BM) |
| 4.5        | `.claude/personal-scraper`      | `d0a666b` | `host.py` (wrapping Python + JSONL dump), `CHANGELOG.md`, sync matrix↔skill, doc dans `.claude/CLAUDE.md`. Audits config-health-checker + skill-dependency-checker : HEALTHY.                                                                                 |

Méthode : validation utilisateur entre chaque sous-phase respectée.

## Review cycles

_(rempli par implement:pr-review — max 3 cycles)_

## Next action

Audit pré-design terminé. **Démarrer `/implement:phase`** pour commencer Phase 1 (Foundations
BDD/indexer).

Lectures préalables avant Phase 1 :

- `docs/features/tech-debt/DESIGN.md` (sections §9 BDD, §10 CLI, §11 architecture)
- `docs/features/tech-debt/plan/INDEX.md` (graphe de dépendances)
- `docs/features/tech-debt/plan/phase-01-foundations.md`
- `docs/features/tech-debt/audit/11-global-synthesis.md` (master backlog)

Méthode : continuer la validation par phase utilisateur (cohérent avec la méthodologie
audit). Chaque phase = N sous-phases + phase gate commit + `make check` vert.
