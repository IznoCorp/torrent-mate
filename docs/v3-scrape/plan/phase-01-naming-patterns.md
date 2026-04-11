# Phase 1 — Naming patterns (fichier de config)

## Objectif

Implémenter le système de patterns de nommage configurable, compatible MediaElch.

## Sous-phases

### 3.1.1 — NamingPatterns dataclass

- [x] Créer `personalscraper/naming_patterns.py` (niveau package, partagé)
- [x] Implémenter `NamingPatterns` frozen dataclass avec tous les patterns MediaElch
- [x] Patterns films : movie_dir, movie_video, movie_nfo, movie_poster, movie_fanart, movie_banner, movie_clearlogo, movie_clearart, movie_discart, movie_landscape
- [x] Patterns séries show-level : tvshow_nfo, tvshow_poster, tvshow_fanart, tvshow_banner, tvshow_clearlogo, tvshow_clearart, tvshow_characterart, tvshow_landscape
- [x] Patterns season-level : season_dir, season_poster, season_fanart, season_banner, season_landscape
- [x] Patterns épisodes : episode_video, episode_nfo, episode_thumb

**Commit** : `v3.1.1: Implement NamingPatterns dataclass with MediaElch defaults` ✅

### 3.1.2 — Templating + Tests de conformité MediaElch (merged with 3.1.3)

- [x] Implémenter `format(pattern_name, **kwargs)` et `format_base_filename()`
- [x] Tests unitaires : chaque pattern produit le nom attendu (32 tests)
- [x] Comparé avec fichiers réels : The Piano Lesson, Gérald le Conquérant, Shrinking S03, Fallout
- [x] Épisodes FR vérifiés : « I will be grape », Régime dépression

**Commit** : `v3.1.2: Add pattern templating with MediaElch conformity tests` ✅
