# V3 — SCRAPE : Brainstorming

> Scraping automatique des métadonnées (TMDB/TVDB), génération NFO, téléchargement artwork

## Contexte

Actuellement fait manuellement via MediaElch (GUI). L'objectif est de remplacer cette étape
par des appels API directs à TMDB pour générer automatiquement les fichiers NFO et artwork.

## Ressources existantes

- **Clé API TMDB** : disponible dans `/opt/YoutubeTrailerScraper/.env`
- **YoutubeTrailerScraper** : patterns réutilisables (multi-langue, rate limiting, cache, title normalization)
- **Scripts legacy** : `TVDBNameToNum.py`, `EpisodesTVDBNamer.py` (TVDB v3, chemins Windows)

## NFO Format attendu (Kodi/Plex)

### Films

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>...</title>
  <originaltitle>...</originaltitle>
  <year>...</year>
  <plot>...</plot>
  <genre>...</genre>
  <director>...</director>
  <actor><name>...</name><role>...</role><thumb>...</thumb></actor>
  ...
</movie>
```

### Séries

- `tvshow.nfo` au niveau show
- `S01E01.nfo` au niveau épisode

## Artwork à télécharger

| Type          | Film                  | Série                 |
| ------------- | --------------------- | --------------------- |
| poster        | `Title-poster.jpg`    | `poster.jpg`          |
| fanart        | `Title-fanart.jpg`    | `fanart.jpg`          |
| banner        | `Title-banner.jpg`    | `banner.jpg`          |
| clearlogo     | `Title-clearlogo.png` | `clearlogo.png`       |
| clearart      | `Title-clearart.png`  | —                     |
| discart       | `Title-discart.png`   | —                     |
| landscape     | `Title-landscape.jpg` | `landscape.jpg`       |
| season poster | —                     | `season01-poster.jpg` |
| episode thumb | —                     | `S01E01-thumb.jpg`    |

## Questions ouvertes

- [ ] TMDB seul ou TMDB + Fanart.tv pour l'artwork ?
- [ ] Gestion des mauvais matchs (mode interactif ? seuil de confiance ?)
- [ ] Télécharger les photos acteurs (.actors/) ?
- [ ] Quelle langue prioritaire pour les métadonnées ? (fr-FR puis fallback en-US ?)

## Notes de brainstorming

_À compléter lors de la session de brainstorming dédiée_
