# Phase 6 — Scraper orchestrator + CLI + tests

## Objectif

Assembler tous les composants et connecter au CLI.

## Sous-phases

### 3.6.1 — Scraper orchestrator

- [ ] Créer `personalscraper/scraper/scraper.py`
- [ ] Implémenter `Scraper.__init__(settings, patterns, dry_run, interactive)`
- [ ] Implémenter `process_movies(movies_dir)` → list[ScrapeResult]
- [ ] Implémenter `process_tvshows(tvshows_dir)` → list[ScrapeResult]
- [ ] Implémenter `scrape_movie(dir)` : match → NFO → artwork
- [ ] Implémenter `scrape_tvshow(dir)` : match → tvshow.nfo → artwork → saisons → rename → episode NFO
- [ ] Skip les médias déjà scrapés (vérifier existence .nfo)
- [ ] Gestion d'erreurs item par item

**Commit** : `v3.6.1: Implement Scraper orchestrator`

### 3.6.2 — Commande CLI scrape

- [ ] Implémenter `personalscraper scrape` dans `cli.py`
- [ ] Options : --dry-run, --interactive, --verbose
- [ ] Alimenter StepReport avec les ScrapeResult
- [ ] Afficher résumé en fin de commande

**Commit** : `v3.6.2: Wire scrape command into CLI`

### 3.6.3 — Tests end-to-end

- [ ] Test dry-run sur les médias existants dans 001-MOVIES/ et 002-TVSHOWS/
- [ ] Vérifier les NFO générés (XML valide, tags présents)
- [ ] Vérifier les artwork téléchargés (fichiers existent, taille > 0)
- [ ] Vérifier le renommage épisodes
- [ ] Test mode interactif (mock Click.prompt)

**Commit** : `v3.6.3: Add end-to-end scrape tests`
