# DESIGN — mobile-shell : garde structurelle anti-scroll-horizontal

**Codename**: `mobile-shell` · **Ticket**: #330 · **Type**: `fix` · **Bump**: 0.59.0 → 0.59.1
**Constitution**: DOIT-1 (utilisable), la régression mobile est une dénaturation récurrente.

## Bug prouvé (Chrome, harnais iframe 390 px réel, 2026-07-28)

Le viewport Chrome est épinglé à 1440 px (`resize_window` ne déclenche pas le CSS mobile) ;
mesure via iframe 390 px same-origin :

| Route              | overflow-X page | élément le + à droite                                                           | bottom-bar                        |
| ------------------ | --------------- | ------------------------------------------------------------------------------- | --------------------------------- |
| **`/` (Contrôle)** | **13 px**       | 403 (span `ml-2 text-xs`, w=335, texte non tronqué dans un flex sans `min-w-0`) | fixe mais scrollable AVEC la page |
| /pipeline          | 0               | 444 (clippé par un ancêtre)                                                     | fixe                              |
| /medias            | 0               | 390                                                                             | fixe                              |
| /acquisition       | 0               | 430 (clippé — bouton « Chercher », tâche #3)                                    | fixe                              |
| /systeme           | 0               | 434 (clippé)                                                                    | fixe                              |
| /config            | 0               | 390                                                                             | fixe                              |

Symptôme opérateur confirmé sur `/` : la page scrolle de 13 px → la bottom-bar `position:fixed`
devient scrollable car le viewport de layout mesure 403 px. Les autres routes ont des enfants
qui débordent (jusqu'à 444 px), masqués par un `overflow-hidden` ancêtre — **bombes latentes**.

## Cause structurelle

`AppShell.tsx:144` — le root `<div className="flex min-h-screen …">` n'a **aucun** clamp
horizontal. `AppShell.tsx:152` — le `<main className="… max-w-7xl mx-auto w-full">` n'a ni
`min-w-0` ni `overflow-x-clip`. N'importe quel enfant qui déborde élargit donc le viewport de
layout et rend toute la page (bottom-bar comprise) scrollable horizontalement. Corriger le span
coupable page par page serait le jeu de la taupe que l'opérateur dénonce.

## D1 — Le shell clampe, une fois pour toutes

`AppShell.tsx` :

- root `<div>` : `overflow-x-clip` (aucun scroll horizontal de page possible, jamais).
- wrapper de contenu + `<main>` : `min-w-0` (le flex-child ne se laisse plus pousser par un
  enfant large) + `overflow-x-clip` sur `<main>` (un contenu large est coupé, pas propagé).
- `BottomTabBar` : garantie `position:fixed` (déjà le cas) — une fois le root clampé, elle est
  stable ; vérifier qu'aucun de ses enfants ne la rend scrollable (`min-w-0`/`overflow` interne).

Choix `clip` plutôt que `hidden` : `clip` n'introduit pas de conteneur de défilement (pas de
capture de scroll accidentel), c'est le comportement voulu pour un shell.

## D2 — Les coupables ponctuels, corrigés comme conséquences

Le span `/` (texte sans `truncate`/`min-w-0` dans un flex) et le bouton « Chercher »
d'Acquisition (#3) sont réparés à leur source (`min-w-0` sur le flex-child, `truncate`/
`break-words`/`flex-wrap` selon le cas) — mais ce sont des finitions ; **D1 est le filet qui
empêche la classe entière de revenir**.

## D3 — Garde-fou exécutable (CŒUR de la demande)

Un test qui **casse la CI** si une route régresse. Deux options selon ce que le harnais de test
permet :

- **jsdom/vitest** : monter `AppShell` + chaque route à `width=390`, assert
  `documentElement.scrollWidth <= innerWidth` (jsdom ne layoute pas vraiment — si insuffisant,
  se rabattre sur un test de contrat de classe : le root porte `overflow-x-clip`, `<main>`
  porte `min-w-0`).
- **Playwright** (`.mcp.json` a Playwright) : viewport réel 390 px, les 6 routes, assert
  `scrollWidth - innerWidth === 0` ET bottom-bar `getBoundingClientRect().bottom ≈ viewport`
  ET non-scrollable — la garde vraie. Préférer celle-ci si le harnais e2e existe déjà.

Le test décide : implémenter la plus forte que l'infra permet, documenter le choix.

## ACC

| ID     | Critère                                                                                                              |
| ------ | -------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | Root porte `overflow-x-clip`, `<main>` porte `min-w-0` (+ clip) — test de contrat.                                   |
| ACC-02 | Garde-fou : les 6 routes à 390 px ⇒ `scrollWidth-innerWidth==0` (le test échoue sur le code AVANT D1 — rouge-avant). |
| ACC-03 | Bottom-bar fixe et non-scrollable à 390 px sur les 6 routes.                                                         |
| ACC-04 | Bouton « Chercher » (#3) aligné à 390 px.                                                                            |
| ACC-05 | Preuve réelle Chrome 390 px sur les 6 routes (audit re-exécuté ⇒ 0 partout). npm lint+typecheck+vitest verts.        |

## Hors périmètre

Refonte visuelle mobile ; la sidebar desktop (≥ md) inchangée.
