# Phase 1 — Genre mapper (catégorisation)

## Objectif

Implémenter le mapping genres API → catégories de destination disques. Module partagé avec V5 (dispatch).

## Sous-phases

### 4.1.1 — GenreMapper avec genres TMDB films

- [ ] Créer `personalscraper/verify/genre_mapper.py`
- [ ] Implémenter `GenreMapper` class avec constantes genre IDs TMDB films
  - Ref : docs/TMDB-API.md#genres-films (19 genres, IDs stables)
- [ ] Implémenter `categorize_movie(genres, genre_ids)` → str
  - Animation (ID 16) → "films animations"
  - Documentaire (ID 99) → "films documentaires"
  - Défaut → "films"
  - Spectacle/théâtre : basé sur genre names (pas d'ID TMDB dédié) → "spectacles" / "theatres"
- [ ] Gérer le cas genre_ids=None → fallback sur les noms de genres (strings)
- [ ] Tests paramétrés : chaque catégorie couverte

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

### 4.1.3 — Catégorisation depuis NFO (parsing genres)

- [ ] Implémenter `categorize_from_nfo(nfo_path, media_type)` → str | None
  - Parser le NFO XML → extraire les tags `<genre>`
  - Extraire `<country>` ou `<originaltitle>` pour indice anime
  - Extraire `<uniqueid type="...">` pour déterminer la source (tmdb/tvdb)
  - Appeler `categorize_movie()` ou `categorize_tvshow()` selon media_type
- [ ] Retourner None si genres absents ou catégorie non identifiable
- [ ] Tests avec des NFO réels de 001-MOVIES/ et 002-TVSHOWS/

**Commit** : `v4.1.3: Implement NFO-based categorization`
