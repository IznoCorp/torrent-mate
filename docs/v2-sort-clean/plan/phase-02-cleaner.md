# Phase 2 — NameCleaner via guessit

## Objectif

Implémenter le cleaner de noms de fichiers media en utilisant `guessit` comme moteur de parsing.

> Voir `docs/guessit-evaluation.md` pour l'évaluation complète de la librairie.
> guessit remplace le système regex custom initialement prévu. Il gère nativement :
> 140+ streaming services, titres avec chiffres/années, conventions françaises (VFF, VOSTFR, etc.)

## Sous-phases

### 2.2.1 — NameCleaner wrapper guessit

> Ref : [docs/guessit-evaluation.md](../../guessit-evaluation.md) — section "Impact sur le plan V2"

- [x] Créer `personalscraper/sorter/cleaner.py`
- [x] Implémenter `NameCleaner` comme thin wrapper autour de `guessit.guessit()`
- [x] Implémenter `clean(name)` : retourne titre + season/episode via guessit
- [x] Implémenter `extract_year(name)` : via `guessit(name).get("year")`
- [x] Implémenter `extract_season_episode(name)` : via guessit (S01E04, 1x04, Saison X, doubles)
  - Gérer les doubles épisodes : `guessit(name).get("episode")` peut retourner `[1, 2]` (list)
  - Gérer les packs saison : `guessit(name).get("season")` peut retourner `[1, 2, ..., 8]` (list)
- [x] Implémenter `clean_for_folder(name)` : retourne "Title (Year)" ou "Title"
- [x] Implémenter `get_media_type(name)` : retourne `guessit(name).get("type")` ("movie"/"episode")
  - Utilisé par `file_type.py` pour renforcer la détection movie vs tvshow
  - Ajouté à l'interface `NameCleaner` (voir V2 DESIGN.md)
- [x] Cacher le résultat guessit via `@lru_cache(maxsize=512)` sur `_guess_cached()`

**Commit** : `v2.2.1: Implement NameCleaner via guessit` ✅

### 2.2.2 — Tests exhaustifs du cleaner

- [x] Tests avec les noms réels du dossier `torrents/complete/` (5 noms)
- [x] Tests cas edge : titres avec chiffres (`24`, `300`)
- [x] Tests cas edge : titres contenant des années (`Blade Runner 2049`)
- [x] Tests français : VFF, VOSTFR, TRUEFRENCH, MULTi
- [x] Tests : pas d'année, pas de season/episode, noms très courts
- [x] Tests : double épisodes (S02E01E02), packs saison (S01-S08)
- [x] Vérifier que title + year sont correctement extraits (36 tests total)

**Commit** : `v2.2.2: Add exhaustive cleaner tests with real torrent names` ✅
