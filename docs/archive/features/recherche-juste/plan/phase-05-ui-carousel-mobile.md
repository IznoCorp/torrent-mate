# Phase 5 — UI carrousel mobile-first + preuve 390 px

**Constitution servie** : §12 (mobile first), §8 (rien en silence), §5 (une recherche trouve).
**DESIGN** : §9.

## Gate

```bash
cd frontend && npm run lint && npx tsc -b --noEmit && npm run test -- --run
```

Puis la preuve visuelle, non négociable (ACC-05) : harnais iframe 390 px sur `/acquisitions`,
recherche `spiderman`, mesure de `document.body.scrollWidth` vs `clientWidth`.

Attendu : portes frontend vertes ; `scrollWidth === clientWidth` sur le **body**, et
`scrollWidth > clientWidth` sur le **conteneur du carrousel** — c'est la preuve que le
défilement est borné au conteneur et ne fuit pas dans la page.

## Le problème

`frontend/src/components/acquisition/MediaSearchAdd.tsx:336` affiche une grille figée
`grid-cols-2 sm:grid-cols-3 lg:grid-cols-5`, sans compteur ni navigation. Même avec l'API
paginée de la phase 4, l'opérateur ne verrait que la première page et ne saurait pas qu'il y a
une suite.

## La lecture du §12, à tenir

Le §12 dit « au doigt, **sans scroll horizontal** ». Cette règle vise le **débordement
accidentel** d'une surface hors du viewport — un titre qui pousse la page à 430 px de large.
Elle n'interdit pas une interaction latérale délibérée et bornée à son conteneur : c'est
précisément l'arbitrage rendu par l'opérateur en choisissant la rangée défilante.

Cette lecture n'est pas postulée : ACC-05 la **prouve** en mesurant que la page, elle, ne
déborde pas. Si la mesure échoue, c'est l'implémentation qui est fausse, pas le §.

## Sous-phases

### 5.1 — Le hook pagine

`frontend/src/hooks/useAcquisition.ts:99` (`useMediaSearch`) : passer à une requête paginée
(`useInfiniteQuery` de TanStack, ou une pagination explicite par `offset`). La clé de requête
doit inclure la pagination, sinon les pages se écrasent dans le cache.

### 5.2 — Le carrousel

Rangée `snap-x snap-mandatory` à défilement horizontal, scrollable au doigt. Le conteneur porte
`overflow-x: auto` ; la page ne bouge pas.

- **Flèches ← → à partir de `sm` uniquement.** Sur téléphone le pouce suffit, et une flèche y
  volerait de la largeur — « la largeur est la ressource rare » (§12).
- **Compteur de résultats** visible (« 81 résultats »). Sans lui, l'opérateur croit avoir tout
  vu : c'est exactement le silence que le §8 interdit.
- **Page suivante chargée à l'approche du bord**, sans bouton à viser.
- `MediaCard` (`frontend/src/components/ds/MediaCard`) réutilisé **tel quel** — la composition
  de carte est une règle gravée (§12), on n'y touche pas.

### 5.3 — États

Chargement (squelettes à la forme du carrousel, pas de la grille), erreur (`ErrorState` avec
retry, déjà présent), vide (`EmptyState`, déjà présent). Le chargement de la page suivante ne
doit pas faire disparaître les cartes déjà affichées — un carrousel qui se vide en cours de
défilement est pire que pas de pagination.

### 5.4 — Tests frontend

Test de composant : la rangée rend N cartes, le compteur affiche le `total` de l'API (et non le
nombre de cartes rendues), les flèches sont absentes du DOM sous `sm`, présentes au-delà.

### 5.5 — La preuve à 390 px

Harnais iframe (`docs/reference/web-ui.md`) : viewport Chrome épinglé, iframe same-origin à
390 px, audit de `scrollWidth` sur `/acquisitions` avec des résultats affichés. Une maquette
validée uniquement sur grand écran ne vaut rien (§12).

Vérifier sur **staging** (`tm-staging.iznogoudatall.xyz`) — jamais de serveur local sur 8710 /
8711, Caddy y route déjà. Attention au cache du service worker : comparer le hash du chunk servi
avec `/index.html` en `no-store` avant de conclure quoi que ce soit sur le front déployé.

## Fichiers

| Fichier | Nature |
| --- | --- |
| `frontend/src/components/acquisition/MediaSearchAdd.tsx` | grille → carrousel |
| `frontend/src/hooks/useAcquisition.ts` | recherche paginée |
| `frontend/src/api/acquisition.ts` | params `offset` / `limit` |
| tests de composant | rangée, compteur, flèches responsives |

## Ce que cette phase ne fait pas

Elle ne redessine pas la carte média ni le reste de l'écran Acquisitions. Le périmètre est la
surface de recherche.
