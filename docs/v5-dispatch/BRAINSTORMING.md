# V4 — DISPATCH : Brainstorming

> Déplacement intelligent des médias vers Disk1-4 (merge séries, replace films, free space)

## Contexte

Après V3 (scrape), les médias dans `001-MOVIES/` et `002-TVSHOWS/` ont leurs .nfo, artwork,
et les épisodes sont renommés dans des dossiers `Saison XX/`. V4 doit les envoyer sur le bon
disque de stockage.

## Décisions prises

### Règles de dispatch

| Type                | Si existe déjà sur un disque      | Si nouveau                         |
| ------------------- | --------------------------------- | ---------------------------------- |
| Films (tous types)  | **Remplacer** le dossier existant | Disque avec le plus d'espace libre |
| Séries (tous types) | **Merger** les nouveaux épisodes  | Disque avec le plus d'espace libre |

### Disques et catégories

| Disque | Catégories                                                                                                                                    |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Disk1  | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk2  | series, series animes                                                                                                                         |
| Disk3  | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk4  | films, films animations, series, series animations, series documentaires, emissions                                                           |

### Index des médias — réécriture Python

- **Réécrire from scratch** en Python (pas de wrapper autour des scripts bash BashMate)
- Les scripts bash (`index-medias.sh`, `find-media.sh`) sont trop limités :
  - Fichier plat sans structure (pas de type, pas de disque)
  - Pas de mise à jour incrémentale
  - Pas de fuzzy matching
  - Pas de tracking des suppressions

### Format d'index

- **JSON** pour la simplicité (pas SQLite — le volume est faible, ~quelques milliers d'entrées)
- Structure : `{nom_normalisé: {disk, category, path, type, last_updated}}`
- Mise à jour incrémentale (scan only what changed since last run)
- Matching intelligent : normalisation unicode, fuzzy si nécessaire

### Mapping catégorie → dossier disque

Le type de média (film, série, etc.) détermine dans quel sous-dossier du disque il va.
Ce mapping doit être **configurable** (fichier de config ou .env).

```
001-MOVIES    → films/
002-TVSHOWS   → series/
004-AUDIO     → livres audios/
```

Note : certains sous-types (films animations, series animes, etc.) nécessitent
une détection plus fine (genre TMDB/TVDB ? tag dans le nom ? mapping manuel ?).

## Décisions complémentaires

### Sous-types (films animations, series animes, etc.)

- Détection par le **genre TMDB/TVDB** récupéré en V3
- Genre "Animation" → films animations / series animations
- Genre "Animation" + origine Japon → series animes
- Le genre est stocké dans le .nfo, donc lisible par V4
- Mapping genre → sous-type configurable

### Seuil d'espace disque

- **100 Go minimum** sur un disque pour accepter un dispatch
- Toujours choisir le disque avec le **plus d'espace disponible** parmi ceux compatibles
- `df` ou `shutil.disk_usage()` pour vérifier

### Aucun disque compatible

- **Skip** le média + **Warning** dans les logs + **Notification** Telegram
- Le média reste dans A TRIER/ jusqu'à ce qu'un disque soit libéré

## Contraintes techniques

1. **Chemins avec espaces** — tous les disques ont des chemins avec espaces
2. **Merge séries** — copier uniquement les fichiers qui n'existent pas déjà (ou écraser si même nom)
3. **Replace films** — supprimer l'ancien dossier, copier le nouveau
4. **Vérification post-move** — s'assurer que les fichiers sont bien arrivés (taille identique)
5. **Dry-run** — obligatoire
6. **Logging** — chaque move/merge doit être loggé pour V5
