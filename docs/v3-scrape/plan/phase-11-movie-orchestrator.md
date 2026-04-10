# Phase 11 — Orchestrateur films

## Objectif

Assembler matching + NFO + artwork pour traiter un film complet.

## Sous-phases

### 3.11.1 — scrape_movie()

- [ ] Implémenter `Scraper.scrape_movie(movie_dir)` → ScrapeResult
- [ ] Flow :
  1. Extraire titre + année du nom de dossier
  2. Skip si .nfo existe déjà
  3. `match_movie()` → MatchResult
  4. Si pas de match → retourner ScrapeResult(action="skipped_low_confidence")
  5. Si le nom canonique TMDB diffère du nom de dossier actuel → renommer le dossier
  6. `tmdb_client.get_movie(id)` → données complètes
  7. `extract_stream_info(video_file)` → streamdetails
  8. `generate_movie_nfo()` → écrire le .nfo
  9. `download_movie_artwork()` → poster + landscape
  10. Retourner ScrapeResult(action="scraped")
- [ ] Gestion d'erreurs à chaque étape (ne pas crasher, log + continuer)

**Commit** : `v3.11.1: Implement movie scraping orchestrator`

### 3.11.2 — process_movies()

- [ ] Implémenter `Scraper.process_movies(movies_dir)` → list[ScrapeResult]
- [ ] Scanner tous les sous-dossiers de 001-MOVIES/
- [ ] Appeler scrape_movie() pour chacun
- [ ] Logger chaque opération
- [ ] Retourner la liste agrégée
- [ ] Tests avec structure réaliste

**Commit** : `v3.11.2: Implement batch movie processing`
