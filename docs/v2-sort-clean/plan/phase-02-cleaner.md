# Phase 2 — NameCleaner via guessit

## Objectif

Implémenter le cleaner de noms de fichiers media en utilisant `guessit` comme moteur de parsing.

> Voir `docs/guessit-evaluation.md` pour l'évaluation complète de la librairie.
> guessit remplace le système regex custom initialement prévu. Il gère nativement :
> 140+ streaming services, titres avec chiffres/années, conventions françaises (VFF, VOSTFR, etc.)

## Sous-phases

### 2.2.1 — NameCleaner wrapper guessit

> Ref : [docs/guessit-evaluation.md](../../guessit-evaluation.md) — section "Impact sur le plan V2"

- [ ] Créer `personalscraper/sorter/cleaner.py`
- [ ] Implémenter `NameCleaner` comme thin wrapper autour de `guessit.guessit()`
- [ ] Implémenter `clean(name)` : retourne titre + season/episode via guessit
- [ ] Implémenter `extract_year(name)` : via `guessit(name).get("year")`
- [ ] Implémenter `extract_season_episode(name)` : via guessit (S01E04, 1x04, Saison X, doubles)
  - Gérer les doubles épisodes : `guessit(name).get("episode")` peut retourner `[1, 2]` (list)
  - Gérer les packs saison : `guessit(name).get("season")` peut retourner `[1, 2, ..., 8]` (list)
- [ ] Implémenter `clean_for_folder(name)` : retourne "Title (Year)" ou "Title"
- [ ] Implémenter `get_media_type(name)` : retourne `guessit(name).get("type")` ("movie"/"episode")
  - Utilisé par `file_type.py` pour renforcer la détection movie vs tvshow
  - Ajouté à l'interface `NameCleaner` (voir V2 DESIGN.md)
- [ ] Cacher le résultat guessit dans la classe (un seul appel `guess()` par nom, pas un par méthode)

**Commit** : `v2.2.1: Implement NameCleaner via guessit`

### 2.2.2 — Tests exhaustifs du cleaner

- [ ] Tests avec les noms réels du dossier `torrents/complete/`
- [ ] Tests cas edge : titres avec chiffres (`2001`, `24`, `300`, `Se7en`)
- [ ] Tests cas edge : titres contenant des années (`Blade Runner 2049`)
- [ ] Tests français : VFF, VOSTFR, TRUEFRENCH, MULTi, Saison
- [ ] Tests : pas d'année, pas de season/episode, noms très courts
- [ ] Tests : double épisodes (S02E01E02), packs saison (S01-S08)
- [ ] Vérifier que title + year sont correctement extraits pour le scraping

**Commit** : `v2.2.2: Add exhaustive cleaner tests with real torrent names`
