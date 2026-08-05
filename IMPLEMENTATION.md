# Implementation Progress — file-absorbee

> For Claude: read this file at session start. Current feature tracker.

**Feature**: La file d'acquisition suit le pointeur d'absorption
**Type**: fix
**Version bump**: 0.86.0 → 0.86.1 (bugfix)
**Branch**: `fix/file-absorbee`
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: `docs/features/file-absorbee/DESIGN.md`
**Ticket**: #411

## Contexte

La file d'acquisition affiche « En cours d'acquisition » sur 31 lignes (sur 94) dont
l'acquisition est terminée : elle **rapporte le pointeur d'absorption au lieu de le suivre**,
la prohibition littérale de la §13. Le seam de vérité (`substitute_absorbed_facts`) existe
depuis #398 mais la file n'y a jamais été convertie.

## Invariants non négociables (DESIGN §2, arbitrés par l'opérateur)

- La résolution passe par le **seam partagé** `substitute_absorbed_facts` — jamais une
  seconde implémentation de la règle (ni en SQL, ni en Python, ni en TypeScript).
- Pointeur pendant (`absorbed_by` NULL / saison absente) → la ligne **garde** `absorbed`.
- Le filtre statut est résolu **en JavaScript**, sur la valeur déjà résolue par le backend.
- Aucun verdict « conforme » sans `scripts/check-acquisition-coherence.py` à 0 anomalie sur
  les **données réelles**, après correctif, et sans preuve écran à 390 px.

**Master plan**: `docs/features/file-absorbee/plan/INDEX.md`

## Phases

| #  | Phase                                                  | Plan                                             | Status |
| -- | ------------------------------------------------------ | ------------------------------------------------ | ------ |
| 01 | Backend — la route suit le pointeur                    | `plan/phase-01-backend-resolution.md`            | [x]    |
| 02 | Frontend — filtre JS résolu + vocabulaire corrigé      | `plan/phase-02-frontend-filtre.md`               | [x]    |
| 03 | Garde — `QUEUE_ABSORBED_DANGLING`                      | `plan/phase-03-garde.md`                         | [x]    |
| 04 | Gates, PR, CI, merge, preuve sur données réelles       | `plan/phase-04-gates-preuve.md`                  | [ ]    |

## Preuves déjà exécutées (datées)

- **2026-08-05 20:36** — résolution confrontée à une **copie des données réelles** (94 lignes) :
  les **31** lignes `absorbed` servies `done`, dont #5/#6/#7/#8 (les 4 du rapport) ; aucune ligne
  non-absorbée altérée ; aucune ligne sans statut servi.
- **2026-08-05 20:36** — mutation-check : la route remise à `status=row["status"]` fait **rougir
  5 tests** ; les 3 survivants sont ceux qui doivent survivre (pointeur pendant, lignes ordinaires).
- **2026-08-05 20:47** — `scripts/check-acquisition-coherence.py` (garde étendue) : **0 anomalie**
  sur les données réelles.
- **2026-08-05 20:55** — `make check` **vert** après rebase sur `origin/main` (`e1bd6956`) :
  10380 passed / 3 skipped / 2 xfailed, front 1275 passed, OpenAPI sans dérive, bump 0.85.1 → 0.85.2.

Reste dû par la phase 04 (§13 : rien de tout cela ne se remplace par une relecture) : preuve
écran à 390 px, filtre « Terminé » sur l'UI déployée, et re-passage de la garde **après**
déploiement.

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Phase 04 — pousser, PR, CI, merge, puis vérification sur l'interface déployée.
