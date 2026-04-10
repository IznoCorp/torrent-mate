# Phase 5 — Confidence scoring + matching films

## Objectif

Implémenter le système de confiance et le matching films via TMDB.

## Sous-phases

### 3.5.1 — Algorithme de score de confiance (rapidfuzz)

> Ref : [docs/rapidfuzz-reference.md](../../rapidfuzz-reference.md)

- [ ] Créer `personalscraper/scraper/confidence.py`
- [ ] Implémenter `media_processor(s)` : `default_process` + NFD decomposition pour strip les accents FR
  - ⚠️ `default_process` de rapidfuzz NE supprime PAS les accents — processor custom obligatoire
- [ ] Implémenter `MatchResult` dataclass (api_id, api_title, api_year, confidence, source)
- [ ] Implémenter `score_match(local_title, local_year, api_title, api_year)` → float
  - Utiliser `fuzz.WRatio(local_title, api_title, processor=media_processor)` (score 0-100 → 0.0-1.0)
  - ⚠️ `WRatio` sans processor retourne des scores faux (pas de lowercase, pas de strip ponctuation)
  - Ajustement année : +0.1 si match exact, -0.15 si année différente de >1 an
- [ ] Seuils : HIGH_CONFIDENCE = 0.8, LOW_CONFIDENCE = 0.5
- [ ] Tests paramétrés : match exact, partiel, mauvais, sans année, titres FR avec accents

**Commit** : `v3.5.1: Implement confidence scoring with rapidfuzz WRatio`

### 3.5.2 — Matching films (TMDB)

- [ ] Implémenter `match_movie(tmdb_client, title, year)` → MatchResult | None
- [ ] Rechercher sur TMDB → scorer chaque résultat → garder le meilleur
- [ ] ⚠️ Le param `year` de TMDB n'est PAS un filtre strict — il booste la pertinence mais retourne d'autres années. Le scoring DOIT comparer `release_date` côté client pour valider l'année.
- [ ] Si meilleur score >= 0.8 → retourner le MatchResult (auto-accept)
- [ ] Si meilleur score < 0.5 → retourner None (pas de match)
- [ ] Si entre 0.5 et 0.8 → retourner le MatchResult (confidence dans le champ float,
      c'est l'appelant scrape_movie/scrape_tvshow qui décide : skip en auto, prompt en interactif)
- [ ] Tests avec des films réels de 001-MOVIES/

**Commit** : `v3.5.2: Implement movie matching via TMDB`

### 3.5.3 — Mode interactif

- [ ] Implémenter `prompt_user_choice(results: list[MatchResult])` → MatchResult | None
- [ ] Utiliser Click.prompt pour afficher les résultats numérotés
- [ ] Option "Aucun de ces résultats" → retourner None
- [ ] Appelé quand --interactive et que la confiance est < 0.8
- [ ] Tests avec mock Click.prompt

**Commit** : `v3.5.3: Implement interactive matching mode`
