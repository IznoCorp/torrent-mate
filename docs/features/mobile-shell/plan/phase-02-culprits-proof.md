# Phase 02 — Coupables ponctuels + preuve réelle 390 px

**Goal**: réparer à la source les deux débordements identifiés (finitions, le clamp les couvre
déjà visuellement) et documenter la preuve.

## Surface

| Fichier                                                                                             | Action                                                                                                                                                                            |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| la carte/ligne de `/` portant le `span.ml-2.text-xs.text-muted-foreground` (w=335, débordait à 403) | `min-w-0` sur le flex-child + `truncate` ou `break-words` selon l'intention (retrouver : rg -n "text-muted-foreground" -g '*.tsx' les composants de la page Contrôle / dashboard) |
| le bouton « Chercher » d'Acquisition (débordait à 430 — tâche #3)                                   | aligner : `min-w-0`/`shrink`/`flex-wrap` sur sa rangée de recherche (frontend/src/pages/AcquisitionPage.tsx ou le composant de recherche)                                         |
| tests                                                                                               | contrat de classe sur les deux corrections si un test de la page existe déjà ; sinon note                                                                                         |
| `CHANGELOG.md`                                                                                      | entrée 0.59.1                                                                                                                                                                     |

## Preuve (ACC-05, hors CI — par l'orchestrateur en Chrome)

Le harnais iframe 390 px re-exécuté sur les 6 routes ⇒ `scrollWidth-innerWidth==0` partout,
bottom-bar visible et non-scrollable, bouton Chercher aligné. Collée dans IMPLEMENTATION.md.

## Gate

`npm run lint && typecheck && test` verts ; CHANGELOG à jour ; les fixes ne cassent aucun test
de page existant.
