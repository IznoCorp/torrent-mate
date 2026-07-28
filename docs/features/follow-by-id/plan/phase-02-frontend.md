# Phase 02 — Frontend : sélecteur de provider dans « Ajouter par ID »

**Goal**: le formulaire add-by-ID accepte TVDB / TMDB / IMDB ; envoie le bon champ ; IMDB validé
`tt\d+` ; le fail-soft `tvdb_unresolved` est signalé à l'opérateur.

## Surface

| Fichier                                                        | Action                                                                                                                                                                                                                                                                                                                   |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `frontend/src/components/acquisition/FollowedPanel.tsx`        | Renommer l'accordéon « Ajouter par ID ». Remplacer le champ « ID TVDB » par : un **sélecteur de provider** (segmented TVDB/TMDB/IMDB) + un champ ID (number pour TVDB/TMDB, text pour IMDB avec placeholder `tt0137523`). Le bouton Suivre reste. Le titre optionnel reste.                                              |
| `frontend/src/hooks/useAcquisition.ts` (ou `useFollowedPanel`) | State `provider: 'tvdb'\|'tmdb'\|'imdb'` + `idValue`. `handleAdd` construit le `CreateFollowRequest` avec le bon champ (`tvdb_id`/`tmdb_id` en int, `imdb_id` en string). Validation : IMDB doit matcher `^tt\d+$` (sinon bouton désactivé / message). Au succès, si `tvdb_unresolved` → toast **warning** non-bloquant. |
| tests                                                          | ACC-05 : sélectionner TMDB envoie `{tmdb_id}` ; IMDB envoie `{imdb_id: 'tt...'}` et rejette un IMDB mal formé ; TVDB inchangé ; un retour `tvdb_unresolved:true` déclenche un toast warning. Contrat de classe / a11y du sélecteur.                                                                                      |

## Règles

- IMDB est une **chaîne** (`tt\d+`), TVDB/TMDB des **entiers** — ne jamais envoyer un `imdb_id`
  numérique ni un `tvdb_id` string.
- Le toast `tvdb_unresolved` **prévient sans bloquer** (« Série ajoutée, mais l'ID TVDB n'a pas pu
  être résolu — la détection d'épisodes est indisponible tant qu'un ID TVDB n'est pas fourni »).
- Mobile 390 px : le sélecteur + champ + bouton ne débordent pas (réutiliser le pattern
  `flex-wrap`/`min-w-0` des autres formulaires acquisition).

## Gate

`cd frontend && npm run lint && npm run typecheck && npm run test` verts ; aucune régression des
tests FollowedPanel existants.
