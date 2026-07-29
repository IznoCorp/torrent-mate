# Phase 02 — Comportement : reset après Suivre (#19) + sous-onglets séries/films (#20)

## Surface
- `MediaSearchAdd.tsx` : au succès d'un follow (`doFollow` onSuccess), `setQuery("")` + `setDraft("")`
  (recherche réinitialisée). Toast succès conservé.
- `FollowedPanel.tsx` : sélecteur segmenté « Séries | Films » au-dessus de la liste, filtrant
  `activeItems`/`inactiveItems` par `item.kind` (`show`/`movie`). Défaut « Séries ». Filtre client.
- tests : après follow, requête vidée ; un film n'apparaît pas sous « Séries », une série pas sous
  « Films ».

## Gate
`npm run lint && typecheck && test` verts.
