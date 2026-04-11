# Phase 12 — Orchestrateur séries

## Objectif

Assembler matching + NFO + artwork + saisons + renommage pour traiter une série complète.

## Sous-phases

### 3.12.1 — scrape_tvshow()

- [ ] Implémenter `Scraper.scrape_tvshow(show_dir)` → ScrapeResult
- [ ] Flow :
  1. Extraire titre + année du nom de dossier
  2. Skip si tvshow.nfo existe déjà
  3. `match_tvshow()` → MatchResult (TVDB → fallback TMDB)
  4. Si pas de match → retourner ScrapeResult(action="skipped_low_confidence")
  5. Si nom dossier ≠ `{Title} ({Year})` canonique → renommer le dossier, update show_dir
  6. Récupérer les données série complètes
  7. `generate_tvshow_nfo()` → écrire tvshow.nfo
  8. `download_tvshow_artwork()` → poster + landscape + season posters
  9. Pour chaque saison détectée localement :
     a. `get_episode_titles(match, season)` → titres épisodes
     b. `create_season_dirs()` → dossier Saison XX/
     c. `rename_episodes()` → renommage fichiers
     d. Pour chaque épisode renommé :
     - `extract_stream_info(video)` → streamdetails
     - `generate_episode_nfo()` → écrire .nfo épisode
  10. Retourner ScrapeResult(action="scraped", episodes_renamed=N)
- [ ] Gestion d'erreurs par épisode (ne pas abandonner la série si 1 épisode échoue)

**Commit** : `v3.12.1: Implement TV show scraping orchestrator`

### 3.12.2 — process_tvshows()

- [ ] Implémenter `Scraper.process_tvshows(tvshows_dir)` → list[ScrapeResult]
- [ ] Scanner tous les sous-dossiers de 002-TVSHOWS/
- [ ] Appeler scrape_tvshow() pour chacun
- [ ] Logger chaque opération
- [ ] Retourner la liste agrégée
- [ ] Tests avec structure réaliste

**Commit** : `v3.12.2: Implement batch TV show processing`

### 3.12.3 — Gestion multi-saisons

- [ ] Tester avec une série qui a plusieurs saisons localement
- [ ] Vérifier que chaque saison a ses épisodes renommés
- [ ] Vérifier season posters pour chaque saison
- [ ] Vérifier qu'une saison absente de l'API ne crashe pas

**Commit** : `v3.12.3: Add multi-season handling tests`
