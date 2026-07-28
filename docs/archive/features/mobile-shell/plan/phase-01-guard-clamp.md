# Phase 01 — Garde-fou d'abord (rouge-avant) + clamp du shell

**Goal**: écrire la garde AVANT le fix (elle est rouge sur le shell actuel), puis clamper le
shell pour la rendre verte.

## Contrainte d'infra (vérifiée)

Le harnais frontend = **vitest + jsdom** (pas de Playwright installé). jsdom **ne layoute pas**
— `scrollWidth`/`innerWidth` y sont vacueux. La garde CI est donc un **contrat de classe** :
elle vérifie que le shell porte les protections structurelles, ce qui attrape la régression
« quelqu'un retire `overflow-x-clip` du shell ». La preuve de layout réel (scrollWidth==innerWidth
à 390 px) est faite hors-CI en Chrome (ACC-05, par l'orchestrateur).

## Surface

| Fichier                                            | Action                                                                                                                                                                                         |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/components/layout/AppShell.test.tsx` | **garde rouge-avant** : le root rendu porte `overflow-x-clip` ; le `<main>` porte `min-w-0` ET `overflow-x-clip` ; la `BottomTabBar` est `fixed`. Ces assertions ÉCHOUENT sur le shell actuel. |
| `frontend/src/components/layout/AppShell.tsx`      | root `<div>` (l.144) + `overflow-x-clip` ; wrapper contenu (l.146, a déjà `min-w-0`) OK ; `<main>` (l.152) + `min-w-0 overflow-x-clip`                                                         |
| `frontend/src/components/layout/BottomTabBar.tsx`  | vérifier `fixed` + qu'aucun enfant ne la rende scrollable (`min-w-0` sur le flex interne si besoin) ; test de contrat                                                                          |

## Sous-phases

### 1.1 — `test(mobile-shell): shell must clamp horizontal overflow (failing-first)`

### 1.2 — `fix(mobile-shell): the shell clamps horizontal overflow structurally`

## Gate

`cd frontend && npm run lint && npm run typecheck && npm run test` — vert ; la garde de 1.1
échouait avant 1.2, passe après (vérifié) ; aucune régression des tests existants
AppShell/BottomTabBar/Sidebar (contrat sidebar desktop ≥ md intact).
