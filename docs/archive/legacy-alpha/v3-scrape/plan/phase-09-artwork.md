# Phase 9 — Artwork downloader

## Objectif

Télécharger poster, landscape et season posters depuis TMDB/TVDB.

## Sous-phases

> Note : Ne télécharger que poster + landscape (films) et poster + landscape + season posters (séries).
> Les autres patterns (fanart, clearlogo, etc.) sont définis dans NamingPatterns pour compatibilité
> avec les fichiers ajoutés manuellement, mais ne sont PAS téléchargés automatiquement.
>
> **Mapping artwork TMDB vs TVDB** :
>
> - TMDB : `posters[]` → poster, `backdrops[]` → landscape (filtrer avec `include_image_language=fr,en,null`)
> - TVDB : type 2 = Poster série, type 3 = Background série (≈landscape, 1920×1080), type 7 = Poster saison
> - ⚠️ TVDB n'a pas de type "landscape" — le Background est l'équivalent le plus proche
> - Ref : [docs/TVDB-API.md — Types d'artwork](../../TVDB-API.md#types-dartwork)

### 3.9.1 — Downloader de base

- [ ] Créer `personalscraper/scraper/artwork.py`
- [ ] Implémenter `ArtworkDownloader.__init__()` avec session requests
- [ ] Implémenter `download_image(url, dest_path)` → bool
- [ ] Timeout 30s (images peuvent être lourdes)
- [ ] Retry 2x si échec
- [ ] Vérifier que le fichier téléchargé a une taille > 0
- [ ] Skip si fichier existe déjà à destination
- [ ] Support `dry_run` : si True, log le téléchargement prévu sans écrire de fichier

**Commit** : `v3.9.1: Implement base artwork image downloader`

### 3.9.2 — Artwork films

- [ ] Implémenter `download_movie_artwork(movie_data, movie_dir, patterns)` → list[Path]
- [ ] Sélectionner la meilleure image poster (langue fr > en > null)
- [ ] Sélectionner la meilleure image landscape/backdrop
- [ ] Utiliser NamingPatterns pour les noms de fichiers
- [ ] Retourner la liste des fichiers téléchargés
- [ ] Tests avec mock HTTP

**Commit** : `v3.9.2: Implement movie artwork download (poster + landscape)`

### 3.9.3 — Artwork séries + season posters

- [ ] Implémenter `download_tvshow_artwork(show_data, show_dir, patterns)` → list[Path]
- [ ] Show-level : poster.jpg + landscape.jpg
- [ ] Season-level : season{NN}-poster.jpg pour chaque saison détectée
- [ ] Utiliser NamingPatterns
- [ ] Tests

**Commit** : `v3.9.3: Implement tvshow artwork download with season posters`
