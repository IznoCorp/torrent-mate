# Phase 2 — Scrape resilience

## Objectif

Rendre le scrape resilient aux crashes : detecter les NFO corrompus/incomplets, re-scraper automatiquement, recuperer les artworks manquants, et fast-skip quand tout est complet.

## Sous-phases

### 10.2.1 — NFO corrupt detection + re-scrape

- [x] Remplacer `nfo_path.exists()` par `_is_nfo_complete(nfo_path)` dans `scrape_movie()`
- [x] Remplacer `nfo_path.exists()` par `_is_nfo_complete(nfo_path)` dans `scrape_tvshow()`
- [x] Si NFO existe mais invalide → supprimer le fichier NFO avant re-scrape
- [x] Log WARNING "Corrupt NFO detected, re-scraping: {path}"
- [x] Le re-scrape suit le meme flux que le scrape initial
- [x] Tests existants mis a jour pour ecrire des NFO valides (avec uniqueid)
- [x] Tests filesystem pour corrupt NFO → Phase 4 (10.4.1)

**Commit** : `v10.2.1: Detect corrupt NFO and re-scrape automatically`

### 10.2.2 — Artwork partial recovery

- [x] `_check_missing_movie_artwork` + `_recover_movie_artwork` dans `scraper.py`
- [x] `_recover_tvshow_artwork` pour les series
- [x] Recovery utilise TMDB ID du NFO existant pour fetcher les images
- [x] Status "artwork_recovered" dans ScrapeResult
- [x] Si recovery echoue → action reste "skipped_already_done" (pas bloquant)
- [x] Tests filesystem → Phase 4 (10.4.1)

**Commit** : `v10.2.2: Recover missing artwork without re-scraping NFO`

### 10.2.3 — Scrape fast-skip

- [x] Ajouter `_has_unscraped_items(settings) -> bool` dans `scraper/run.py`
- [x] Scan rapide : retourne True des le premier dossier sans NFO valide
- [x] Dans `run_scrape()` : fast-skip si `_has_unscraped_items()` retourne False
- [x] Tests existants mis a jour pour patcher `_has_unscraped_items`

**Commit** : `v10.2.3: Add scrape fast-skip when all NFOs are valid`
