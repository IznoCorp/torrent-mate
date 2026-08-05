# Plan — file-absorbee

Feature : **La file d'acquisition suit le pointeur d'absorption** (#411)
Design : `docs/features/file-absorbee/DESIGN.md`
Bump : 0.84.0 → 0.84.1 (`fix/file-absorbee`)

## Ordre et raison de l'ordre

| #  | Phase                                                    | Fichier                              | Défaut visé |
| -- | -------------------------------------------------------- | ------------------------------------ | ----------- |
| 01 | Backend — la route suit le pointeur                      | `phase-01-backend-resolution.md`     | La cause    |
| 02 | Frontend — filtre JS résolu + vocabulaire corrigé        | `phase-02-frontend-filtre.md`        | La cohérence filtre ↔ pastille |
| 03 | Garde — `QUEUE_ABSORBED_DANGLING`                        | `phase-03-garde.md`                  | Le trou de la garde |
| 04 | Gates, PR, CI, merge, vérification sur données réelles   | `phase-04-gates-preuve.md`           | La preuve  |

L'ordre porte du sens :

- **01 avant 02** : le frontend filtre sur la valeur *résolue par le backend*. Filtrer en JS
  avant que la route ne résolve produirait un filtre qui trie des mensonges.
- **03 après 01** : la règle de garde s'écrit contre le comportement corrigé — un pointeur
  pendant n'est une anomalie que parce que la route, elle, sait suivre les pointeurs sains.
- **04 en dernier** : la §13 exige (1) le code corrigé, (2) l'état vérifié, (3) le contrôle
  exécutable à zéro anomalie. La preuve n'a de valeur qu'après déploiement.

## Invariants applicables à toutes les phases

- **Une seule dérivation.** `substitute_absorbed_facts` est la règle. Aucune phase ne la
  réimplémente — ni en SQL, ni en Python, ni en TypeScript.
- **Test-first sur le défaut.** La phase 01 écrit le test des 4 lignes American Dad et le
  voit **rouge** avant tout correctif.
- **Pas de verdict sans exécution.** Aucune phase ne se déclare finie sur une relecture.
