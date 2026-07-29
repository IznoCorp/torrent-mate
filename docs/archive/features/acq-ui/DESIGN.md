# DESIGN — acq-ui : polish de l'UI Acquisitions (4 demandes opérateur)

**Codename** : `acq-ui` · **Type** : `feat` · **Bump** : minor (0.63.0 → 0.64.0)
**Ticket** : #340 · **Merge** : auto

## Constitution produit (CONTRAIGNANT)

Sert `docs/reference/product-intent.md` **§3 (lisibilité / densité utile)** : l'écran d'acquisition
doit utiliser toute la largeur (surtout mobile), ne pas gaspiller d'espace en états vides
encombrants, et présenter les suivis de façon claire (séries vs films).

## Demandes (4)

1. **#12 — full-width.** Le contenu de chaque onglet est enfermé dans une grande `Card`
   (`AcquisitionPage.tsx` : `<Card><CardContent>`) : marge extérieure + padding intérieur ⇒ double
   perte de largeur, surtout à 390 px. **Retirer la box** : le contenu de l'onglet vit directement
   dans la `section`.
2. **#19 — reset après « Suivre ».** Dans `MediaSearchAdd`, au succès d'un follow, réinitialiser la
   recherche (vider requête + résultats) — prêt pour une nouvelle recherche.
3. **#20 — séries / films.** Dans la liste des suivis (`FollowedPanel`), séparer séries et films
   via des sous-onglets « Séries » / « Films » (filtre sur `item.kind`).
4. **#21 — fusion recherche + retrait empty-state.** Fusionner la recherche par titre
   (`MediaSearchAdd`) et l'ajout par ID (accordéon `FollowedPanel`) en UNE surface, et retirer la
   grosse zone vide « Recherchez un média / Tapez un titre… » qui occupe l'espace sans recherche.

## Approche

- **#12** : supprimer `<Card><CardContent>` autour du contenu d'onglet ; garder un espacement
  vertical (`flex flex-col gap-*`). Le `max-w-5xl mx-auto` de la `section` reste (lisibilité
  desktop) ; sur mobile la section prend déjà toute la largeur — sans la box, le contenu gagne le
  padding+bordure. Vérifier `scrollWidth-innerWidth==0` à 390 px.
- **#19** : `MediaSearchAdd.doFollow` onSuccess ⇒ `setQuery("")` + `setDraft("")` (l'empty-state /
  liste se vide). Le toast de succès reste.
- **#20** : `FollowedPanel` — un petit sélecteur segmenté « Séries | Films » au-dessus de la liste,
  filtrant `activeItems`/`inactiveItems` par `item.kind` (`show`/`movie`). Défaut « Séries ». Pas de
  changement d'API (le filtre est client).
- **#21** : la recherche par titre (`MediaSearchAdd`) devient la surface unique ; y intégrer
  l'entrée par ID (le sélecteur TVDB/TMDB/IMDB + champ id, déplacé depuis l'accordéon
  `FollowedPanel`) — un seul bloc « Ajouter un média » (titre OU id). Retirer l'`EmptyState`
  « Recherchez un média » quand `query === ""` (n'afficher les résultats que lorsqu'il y a une
  recherche). L'accordéon « Ajouter par ID » de `FollowedPanel` est retiré (déplacé dans la surface
  fusionnée) — le hook `useFollowedPanel` add-by-id est réutilisé, pas dupliqué.

## Non-buts

- Pas de changement de contrat web (tout est front). `make openapi` ne doit pas dériver.
- Pas de refonte des autres onglets (File/Obligations/Watcher) au-delà du retrait de la box #12.

## ACCEPTANCE (commandes exécutables)

- **ACC-01** — `#12` : `AcquisitionPage` ne contient plus `<Card>` autour du contenu d'onglet
  (test de structure) ; preuve Chrome 390 px `scrollWidth-innerWidth==0`, contenu pleine largeur.
- **ACC-02** — `#19` : après un follow réussi, `query`/`draft` sont vidés (test `MediaSearchAdd`).
- **ACC-03** — `#20` : sous-onglets « Séries »/« Films » filtrent la liste par kind (test
  `FollowedPanel` : un film n'apparaît pas sous « Séries » et inversement).
- **ACC-04** — `#21` : pas d'`EmptyState` « Recherchez un média » quand la requête est vide ;
  l'entrée par ID (sélecteur provider) est présente dans la surface fusionnée ; l'accordéon
  « Ajouter par ID » de `FollowedPanel` est retiré.
- **ACC-05** — `cd frontend && npm run lint && npm run typecheck && npm run test` verts ;
  `make openapi` sans dérive. Preuve Chrome 390 px (les 4 changements visibles).

## Phases (indicatif — `/implement:plan` fait foi)

1. **Structure** — #12 (retrait box) + #21 (fusion recherche + retrait empty-state) + tests.
2. **Comportement** — #19 (reset après Suivre) + #20 (sous-onglets séries/films) + tests.
3. **ACC + preuve 390 px + gate**.
