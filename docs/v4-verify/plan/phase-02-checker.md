# Phase 2 — Media checker (vérifications)

## Objectif

Implémenter la vérification complète d'un dossier média contre les standards attendus.

## Sous-phases

### 4.2.1 — Checks films de base

- [ ] Créer `personalscraper/verify/checker.py`
- [ ] Implémenter `Severity` enum (ERROR, WARNING) et `CheckResult` dataclass
- [ ] Implémenter `MediaChecker.__init__(patterns: NamingPatterns, genre_mapper: GenreMapper)`
- [ ] Implémenter `check_movie(movie_dir)` avec les checks :
  - `video_present` : au moins 1 fichier vidéo reconnu (extensions de CLAUDE.md) → ERROR
  - `dir_naming` : format `Title (Year)/` — regex `^.+ \(\d{4}\)$` → ERROR (fixable=True)
  - `nfo_present` : fichier `.nfo` correspondant au pattern NamingPatterns → ERROR
  - `nfo_valid` : XML parseable + tags `<title>`, `<year>` présents → ERROR
- [ ] Tests unitaires avec dossiers tmp_path

**Commit** : `v4.2.1: Implement base movie checks (video, naming, NFO)`

### 4.2.2 — Checks films avancés (IDs, artwork, streamdetails, catégorie)

- [ ] Checks supplémentaires :
  - `nfo_ids` : `<uniqueid type="tmdb">` ET `<uniqueid type="imdb">` présents → ERROR
  - `artwork_poster` : fichier poster selon NamingPatterns → WARNING
  - `artwork_landscape` : fichier landscape selon NamingPatterns → WARNING
  - `streamdetails` : `<fileinfo><streamdetails>` dans le NFO → WARNING
  - `category` : `genre_mapper.categorize_from_nfo()` retourne un résultat non-None → ERROR
- [ ] Tests avec NFO réels (extraits de 001-MOVIES/)

**Commit** : `v4.2.2: Add advanced movie checks (IDs, artwork, category)`

### 4.2.3 — Checks séries

- [ ] Implémenter `check_tvshow(show_dir)` avec les checks :
  - `video_present` → ERROR
  - `dir_naming` : format `Show Name (Year)/` → ERROR (fixable=True)
  - `nfo_present` : `tvshow.nfo` → ERROR
  - `nfo_valid` : XML + tags `<title>`, `<year>` → ERROR
  - `nfo_ids` : `<uniqueid type="tvdb">` minimum → ERROR
  - `artwork_poster` : `poster.jpg` → WARNING
  - `artwork_landscape` : `landscape.jpg` → WARNING
  - `season_structure` : au moins un `Saison XX/` avec des épisodes `S01E01 - Titre.ext` → ERROR
  - `season_posters` : `seasonNN-poster.jpg` par saison → WARNING
  - `episode_nfo` : `.nfo` par épisode dans chaque saison → WARNING
  - `streamdetails` : dans les NFO épisode → WARNING
  - `category` : catégorie identifiable → ERROR
- [ ] Tests avec structure de série réaliste

**Commit** : `v4.2.3: Implement TV show checks`

### 4.2.4 — Helper : parsing NFO

- [ ] Implémenter `_parse_nfo(nfo_path)` → ET.Element | None (XML invalide → None)
- [ ] Implémenter `_extract_genres(root)` → list[str] (tags `<genre>`)
- [ ] Implémenter `_extract_country(root)` → str | None (tag `<country>`)
- [ ] Implémenter `_extract_ids(root)` → dict[str, str] (type → id, ex: {"tmdb": "550", "imdb": "tt0137523"})
- [ ] Tests de parsing avec des NFO valides et invalides

**Commit** : `v4.2.4: Implement NFO parsing helpers`
