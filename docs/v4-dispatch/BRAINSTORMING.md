# V4 — DISPATCH : Brainstorming

> Déplacement intelligent des médias vers Disk1-4 (merge séries, replace films, free space)

## Contexte

Une fois les médias triés et scrapés, il faut les envoyer sur le bon disque de stockage.
Les règles diffèrent selon le type de média (replace pour films, merge pour séries).

## Règles de dispatch

| Type                | Si existe déjà                    | Si nouveau                         |
| ------------------- | --------------------------------- | ---------------------------------- |
| Films (tous types)  | **Remplacer** le dossier existant | Disque avec le plus d'espace libre |
| Séries (tous types) | **Merger** les nouveaux épisodes  | Disque avec le plus d'espace libre |

## Disques et catégories

| Disque | Catégories                                                                                                                                    |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Disk1  | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk2  | series, series animes                                                                                                                         |
| Disk3  | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk4  | films, films animations, series, series animations, series documentaires, emissions                                                           |

## Outils existants à évaluer

### BashMate/MediaMate (`~/BashMate/MediaMate/FindMedia/`)

- `index-medias.sh` : indexe tous les dossiers médias dans `~/.medias_cache`
- `find-media.sh` : recherche grep case-insensitive dans le cache

**Limites identifiées :**

- Pas de mise à jour incrémentale (rebuild complet à chaque fois)
- Matching par sous-chaîne simple (pas de fuzzy)
- Fichier plat sans structure (pas de type, pas de disque)
- Pas de tracking des suppressions (entrées orphelines)

### Recommandation préliminaire

Réécrire un index Python intégré au pipeline qui :

- Maintient un index structuré (JSON/SQLite) avec disque + catégorie + chemin
- Supporte la mise à jour incrémentale
- Offre un matching intelligent (fuzzy, normalisation accents)
- Est importable comme module

## Questions ouvertes

- [ ] Réécrire l'index from scratch ou wrapper autour des scripts bash existants ?
- [ ] Format d'index : JSON (simple) ou SQLite (performant sur gros volumes) ?
- [ ] Comment gérer le merge de séries ? (copier uniquement les fichiers manquants ? écraser si même nom ?)
- [ ] Vérification d'espace libre avant déplacement (seuil minimum ?)
- [ ] Que faire si aucun disque n'a assez d'espace ?

## Notes de brainstorming

_À compléter lors de la session de brainstorming dédiée_
