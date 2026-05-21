# Implementation Progress — tech-debt

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Tech-Debt (Global Cross-Feature Fixes) (type: bugfix)
**Version bump**: 0.15.0 → 0.15.1
**Branch**: fix/tech-debt
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/tech-debt/DESIGN.draft.md _(brouillon — version finale après audit pré-design)_
**Master plan**: docs/features/tech-debt/plan.draft/INDEX.md _(brouillon — version finale après audit pré-design)_

## Statut actuel

**🔍 Phase audit pré-design en cours.** Le DESIGN + plan actuels sont des brouillons rapides à raffiner ou réécrire selon les résultats de l'audit ci-dessous. Les phases d'implémentation ne démarrent qu'après l'item 14 (challenge final du design + plan).

## Audit pré-design (14 items)

Méthode : un par un, validation utilisateur entre chaque, communication en français, rien hors scope.

| #   | Item                                                   | Type           | Output attendu                        | Status                                                       |
| --- | ------------------------------------------------------ | -------------- | ------------------------------------- | ------------------------------------------------------------ |
| 1   | Étude des dérives des plans (cross-feature)            | Analyse        | Rapport patterns + causes racines     | [x] (audit/01-plan-drift.md)                                 |
| 2   | Étude du pipeline et de son fonctionnement             | Analyse        | Carto pipeline + invariants           | [x] (audit/02-pipeline-cartography.md)                       |
| 3   | Brainstorm MAJ skill pipeline-monitor                  | Brainstorm     | Liste changements à apporter          | [x] (audit/03-skill-update-brainstorm.md + Q1-Q10 décidées)  |
| 4   | MAJ skill pipeline-monitor                             | Implémentation | Skill mise à jour committée           | 🔄 paused — baseline `.claude/53d299d`, suite session future |
| 5   | Run pipeline-monitor (avec skill mise à jour)          | Analyse        | DEVIATION LIST + Conformity Check     | [ ]                                                          |
| 6   | Brainstorm améliorations suite au pipeline-monitor     | Brainstorm     | Liste items pour le design            | [ ]                                                          |
| 7   | Check BDD (intégrité, conformité, cohérence, améliors) | Analyse        | Rapport BDD                           | [ ]                                                          |
| 8   | Brainstorm améliorations BDD                           | Brainstorm     | Liste items pour le design            | [ ]                                                          |
| 9   | Analyse commandes CLI (bugs, design, améliorations)    | Analyse        | Rapport CLI                           | [ ]                                                          |
| 10  | Brainstorm améliorations CLI                           | Brainstorm     | Liste items pour le design            | [ ]                                                          |
| 11  | Analyse app + conformité design                        | Analyse        | Rapport conformité globale            | [ ]                                                          |
| 12  | Analyse critique design + architecture                 | Analyse        | Rapport critique structurel           | [ ]                                                          |
| 13  | Brainstorm améliorations globales                      | Brainstorm     | Synthèse de tous les brainstorms      | [ ]                                                          |
| 14  | Challenge final du design + plan tech-debt             | Validation     | DESIGN.md + plan/ propres (non-draft) | [ ]                                                          |

## Phases d'implémentation

_(à définir en item 14 — la table actuelle dans `plan.draft/INDEX.md` sera réévaluée à la lumière de l'audit)_

## État de l'item 4 (paused — reprise en session future)

**Architecture confirmée** : la skill `pipeline-monitor` vit dans `.claude/` qui est son propre repo git (gitignored dans personalscraper). Travail en 2 repos parallèles.

**État `.claude/` (repo skill)** :

- Branch : `personal-scraper`
- Baseline committé : `53d299d chore(pipeline-monitor): baseline WIP from 2026-05-18 session`
- Stash original `pipeline-monitor WIP before personal-scraper switch` : appliqué + droppé
- Rebase main : pas fait (à faire en début de session future)

**Sous-phases prévues (de la session future)** :

- **4.1** — Matrix v2.0 rewrite (`.claude/skills/pipeline-monitor/references/design-conformity-matrix.md`) : 9 StepReports + ENFORCE + TRAILERS + connexes + pré-recovery + 19 invariants + 5 catégories
- **4.2** — Pipeline.py SIGINT support (côté `personalscraper`, ce repo, branch `fix/tech-debt`) : `_shutdown_requested` flag inter-step
- **4.3** — Nouveaux agents : `pipeline-event-monitor`, `pipeline-invariant-checker`, `pipeline-bdd-validator`, `pipeline-matrix-stale-detector`
- **4.4** — Skill SKILL.md rewrite : wrapping process Python, assertion `MATRIX_VERSION`, lazy auto-scan, 5 catégories, `--remediate` flag, SIGINT handler, GATE 0+6 enrichis, simulation mode (BJ), weird outputs log (BK), library-reconcile cross-correlation (BL), compare précédent run (BM)
- **4.5** — Tests + smoke + documentation skill ↔ matrix

**Méthode** : validation entre chaque sous-phase (cf. décision utilisateur).

## Review cycles

_(rempli par implement:pr-review — max 3 cycles)_

## Next action

Démarrer **item 1 — étude des dérives des plans (cross-feature)**.
