# Phase 01 — Structure : retrait box (#12) + fusion recherche + retrait empty-state (#21)

## Surface
- `frontend/src/pages/AcquisitionPage.tsx` : retirer `<Card><CardContent>` autour du contenu
  d'onglet ; le contenu vit dans la `section` (garder un espacement). Imports `Card` nettoyés.
- `frontend/src/components/acquisition/MediaSearchAdd.tsx` : surface de recherche unique
  « Ajouter un média » — titre + entrée par ID (sélecteur TVDB/TMDB/IMDB + champ id) ; retirer
  l'`EmptyState` « Recherchez un média » quand `query===""` (résultats seulement si recherche).
- `frontend/src/components/acquisition/FollowedPanel.tsx` : retirer l'accordéon « Ajouter par ID »
  (déplacé dans la surface fusionnée). Réutiliser le hook add-by-id, pas de duplication.
- tests : structure (pas de `<Card>` autour du contenu ; pas d'empty-state à vide ; sélecteur
  provider présent dans la surface fusionnée ; accordéon retiré de FollowedPanel).

## Gate
`npm run lint && typecheck && test` verts ; aucune régression AcquisitionPage/MediaSearchAdd/FollowedPanel.
