# Phase 1 — Naming patterns (fichier de config)

## Objectif

Implémenter le système de patterns de nommage configurable, compatible MediaElch.

## Sous-phases

### 3.1.1 — NamingPatterns dataclass

- [ ] Créer `personalscraper/naming_patterns.py` (niveau package, partagé)
- [ ] Implémenter `NamingPatterns` dataclass avec tous les patterns MediaElch
- [ ] Patterns films : movie_dir, movie_video, movie_nfo, movie_poster, movie_fanart, movie_banner, movie_clearlogo, movie_clearart, movie_discart, movie_landscape
- [ ] Patterns séries show-level : tvshow_nfo, tvshow_poster, tvshow_fanart, tvshow_banner, tvshow_clearlogo, tvshow_clearart, tvshow_characterart, tvshow_landscape
- [ ] Patterns season-level : season_dir, season_poster, season_fanart, season_banner, season_landscape
- [ ] Patterns épisodes : episode_video, episode_nfo, episode_thumb

**Commit** : `v3.1.1: Implement NamingPatterns dataclass with MediaElch defaults`

### 3.1.2 — Templating

- [ ] Implémenter `format(pattern_name, **kwargs)` : remplace {Title}, {Year}, {Season:02d}, etc.
- [ ] Gérer `<baseFileName>` : résoudre à partir du nom du fichier vidéo
- [ ] Tests unitaires : chaque pattern produit le nom attendu

> Note : Pas de `load()` depuis fichier config. Les patterns sont des standards Kodi/MediaElch
> qui ne changent pas. La dataclass avec valeurs par défaut suffit (YAGNI).

**Commit** : `v3.1.2: Add pattern templating`

### 3.1.3 — Tests de conformité MediaElch

- [ ] Comparer les patterns générés avec les fichiers réels dans 001-MOVIES/ et 002-TVSHOWS/
- [ ] Vérifier que les noms produits correspondent à ce que MediaElch produit
- [ ] Tests paramétrés avec des cas variés (films avec sous-titres, séries multi-saisons)

**Commit** : `v3.1.3: Add MediaElch conformity tests for naming patterns`
