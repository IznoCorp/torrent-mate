# Phase 3 — Confidence scoring + matching

## Objectif

Implémenter le système de confiance pour matcher les médias locaux aux résultats API.

## Sous-phases

### 3.3.1 — Score de confiance

- [ ] Créer `personalscraper/scraper/confidence.py`
- [ ] Implémenter `score_match(local_title, local_year, api_title, api_year)` → float 0.0-1.0
- [ ] Normalisation : lowercase, strip accents, strip articles (le/la/the/a)
- [ ] Scoring : exact title = 0.6, year match = +0.3, partial title = proportionnel
- [ ] Implémenter `MatchResult` dataclass
- [ ] Tests unitaires avec cas variés (exact, partiel, mauvais)

**Commit** : `v3.3.1: Implement confidence scoring for API matching`

### 3.3.2 — Logique de matching (movie + tvshow)

- [ ] Dans `scraper.py` (ou module dédié) : `_match_movie(title, year)` et `_match_tvshow(title, year)`
- [ ] Movie : TMDB search → score → auto si >= 0.8 ou interactive si flag
- [ ] TVShow : TVDB search → score → si fail → TMDB fallback → score
- [ ] Mode interactif : `_prompt_user(results)` avec Click.prompt
- [ ] Mode auto sans confiance : skip + rapport
- [ ] Tests

**Commit** : `v3.3.2: Implement movie and tvshow matching with confidence`
