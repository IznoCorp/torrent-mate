# Phase 2 — Scrape resilience

## Objectif

Rendre le scrape resilient aux crashes : detecter les NFO corrompus/incomplets, re-scraper automatiquement, recuperer les artworks manquants, et fast-skip quand tout est complet.

## Sous-phases

### 10.2.1 — NFO corrupt detection + re-scrape

- [ ] Remplacer `nfo_path.exists()` par `_is_nfo_complete(nfo_path)` dans `scrape_movie()`
- [ ] Remplacer `nfo_path.exists()` par `_is_nfo_complete(nfo_path)` dans `scrape_tvshow()`
- [ ] Si NFO existe mais invalide → supprimer le fichier NFO avant re-scrape
- [ ] Log WARNING "Corrupt NFO detected, re-scraping: {path}"
- [ ] Le re-scrape suit le meme flux que le scrape initial (match → details → NFO → artwork)
- [ ] Tests filesystem : creer un NFO XML invalide (tronque) → scrape le detecte et re-scrape
- [ ] Tests filesystem : creer un NFO sans `<uniqueid>` → scrape le detecte et re-scrape
- [ ] Tests filesystem : NFO valide → scrape skip normalement

**Commit** : `v10.2.1: Detect corrupt NFO and re-scrape automatically`

### 10.2.2 — Artwork partial recovery

- [ ] Ajouter `_check_artwork_complete(media_dir, media_type, title) -> list[str]` dans `scraper.py`
- [ ] Pour les films : verifier `Title-poster.jpg` et `Title-landscape.jpg`
- [ ] Pour les series : verifier `poster.jpg` et `fanart.jpg`
- [ ] Dans `scrape_movie()` et `scrape_tvshow()` : apres le check NFO valide (skip path)
- [ ] Si NFO valide mais artwork manquant → re-download uniquement les artwork manquants
- [ ] Ne PAS re-scrape le NFO — utiliser les IDs du NFO existant pour fetcher les images
- [ ] Status "artwork_recovered" dans ScrapeResult (compte comme success)
- [ ] Tests filesystem : NFO valide + poster present + landscape absent → re-download landscape
- [ ] Tests filesystem : NFO valide + tout artwork present → skip complet

**Commit** : `v10.2.2: Recover missing artwork without re-scraping NFO`

### 10.2.3 — Scrape fast-skip

- [ ] Ajouter `_has_unscraped_items(settings) -> bool` dans `scraper/run.py`
- [ ] Scan rapide : pour chaque dossier dans 001-MOVIES/ et 002-TVSHOWS/, check `_is_nfo_complete()`
- [ ] Retourne True des le premier dossier sans NFO valide
- [ ] Dans `run_scrape()` : si `_has_unscraped_items()` retourne False → retour immediat avec StepReport(skip)
- [ ] Le fast-skip comptabilise les items skipper dans skip_count
- [ ] Tests : fast-skip quand tous les dossiers ont un NFO valide
- [ ] Tests : pas de fast-skip quand un dossier n'a pas de NFO

**Commit** : `v10.2.3: Add scrape fast-skip when all NFOs are valid`
