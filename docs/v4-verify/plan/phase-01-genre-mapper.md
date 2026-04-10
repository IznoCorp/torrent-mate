# Phase 1 — Genre mapper (catégorisation)

## Objectif

Implémenter le mapping genres API → catégories de destination disques. Module partagé avec V5 (dispatch).

## Sous-phases

### 4.1.1 — GenreMapper avec genres TMDB films + KNOWN_CATEGORIES

- [ ] Créer `personalscraper/genre_mapper.py` (racine du package, partagé V4+V5)
- [ ] Définir `KNOWN_CATEGORIES: frozenset[str]` avec toutes les catégories valides
  - V5 importera ce frozenset pour valider les catégories reçues
- [ ] Implémenter `GenreMapper` class avec constantes genre IDs TMDB films
  - Ref : docs/TMDB-API.md#genres-films (19 genres, IDs stables)
- [ ] Implémenter `categorize_movie(genres, genre_ids)` → str
  - Animation (ID 16) → "films animations"
  - Documentaire (ID 99) → "films documentaires"
  - Défaut → "films"
  - ⚠️ "spectacles" et "theatres" ne sont PAS détectables via genres TMDB/TVDB
    → seul le fichier `.category` (voir 4.1.3) permet cette catégorisation
- [ ] Gérer le cas genre_ids=None → fallback sur les noms de genres (strings)
  - Normaliser les noms : lowercase, sans accents, pour gérer "Documentaire"/"Documentary"
- [ ] Tests paramétrés : chaque catégorie couverte, y compris noms de genres en français
  - ⚠️ TMDB avec fr-FR retourne des genres FR ("Animation", "Documentaire", "Science-Fiction")
  - Tester le fallback string avec : "Documentaire", "Documentary", "Animation", "Comédie", "Aventure"

**Commit** : `v4.1.1: Implement GenreMapper for TMDB movie categorization`

### 4.1.2 — Catégorisation séries (TMDB + TVDB)

- [ ] Implémenter `categorize_tvshow(genres, genre_ids, origin_country, source)` → str
- [ ] Logique TMDB TV :
  - Animation (ID 16) + origin_country contient "JP" → "series animes"
  - Animation (ID 16) sans JP → "series animations"
  - Documentaire (ID 99) → "series documentaires"
  - Reality (10764) / Talk (10767) / News (10763) → "emissions"
  - Défaut → "series"
- [ ] Logique TVDB :
  - ⚠️ IDs genres TVDB différents : Animation=17, Anime=27, Documentary=3, Reality=8, Talk Show=10, News=11
  - Anime (ID 27) → "series animes" (TVDB a un genre Anime dédié, pas besoin de origin_country)
  - Animation (ID 17) → "series animations"
  - Documentary (ID 3) → "series documentaires"
  - Reality/Talk/News → "emissions"
- [ ] Tests paramétrés avec source="tmdb" et source="tvdb"

**Commit** : `v4.1.2: Add TV show categorization with TMDB and TVDB genre support`

### 4.1.3 — Catégorisation depuis NFO + fichier .category

- [ ] Implémenter `categorize_from_nfo(nfo_path, media_type)` → str | None
  - **Priorité 1** : fichier `.category` dans le dossier parent du NFO
    - Si `.category` existe et contenu (stripped) ∈ `KNOWN_CATEGORIES` → retourner directement
    - Ceci résout le problème spectacles/théâtres (aucun genre API ne correspond)
    - Le fichier `.category` peut être placé manuellement ou par un futur enrichissement de V3
  - **Priorité 2** : parsing NFO XML
    - Extraire les tags `<genre>` → genre names
    - Extraire `<country>` ou `<originaltitle>` pour indice anime
    - Extraire `<uniqueid type="...">` pour déterminer la source (tmdb/tvdb)
    - Appeler `categorize_movie()` ou `categorize_tvshow()` selon media_type
  - Retourner None si genres absents et pas de `.category`
- [ ] Tests avec des NFO réels de 001-MOVIES/ et 002-TVSHOWS/
- [ ] Tests avec fichier `.category` contenant "spectacles", "theatres", valeur invalide, fichier absent

**Commit** : `v4.1.3: Implement NFO-based categorization with .category override`
