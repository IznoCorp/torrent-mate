# Phase 5 — Artwork downloader + episode renaming

## Objectif

Télécharger l'artwork et renommer/réorganiser les épisodes dans les dossiers saison.

## Sous-phases

### 3.5.1 — Artwork downloader

- [ ] Créer `personalscraper/scraper/artwork.py`
- [ ] Implémenter `ArtworkDownloader.download_image(url, dest)` → bool
- [ ] Implémenter `download_movie_artwork(data, dir, patterns)` → poster + landscape
- [ ] Implémenter `download_tvshow_artwork(data, dir, patterns)` → poster + landscape + season posters
- [ ] Skip si artwork déjà existant
- [ ] Timeout et retry sur les téléchargements
- [ ] Tests (mock HTTP ou images de test)

**Commit** : `v3.5.1: Implement artwork downloader (poster, landscape, season)`

### 3.5.2 — Création Saison XX/ et renommage épisodes

- [ ] Dans `scraper.py` : logique de création des dossiers `Saison XX/`
- [ ] Matcher chaque fichier vidéo à un épisode API via season+episode number
- [ ] Renommer : `S01E01 - Titre Episode.mkv` (via NamingPatterns)
- [ ] Déplacer dans le bon dossier `Saison XX/`
- [ ] Gérer les sous-titres associés (même base name → même renommage)
- [ ] Support dry-run
- [ ] Tests

**Commit** : `v3.5.2: Implement season folder creation and episode renaming`
