# Phase 10 — Dossiers saison + renommage épisodes

## Objectif

Créer les dossiers Saison XX/ et renommer les épisodes avec les titres de l'API.

## Sous-phases

### 3.10.1 — Création des dossiers saison

- [ ] Implémenter `create_season_dirs(show_dir, episodes, patterns)` → list[Path]
- [ ] Détecter quelles saisons sont présentes (depuis les fichiers vidéo)
- [ ] Créer `Saison 01/`, `Saison 02/`, etc. (via NamingPatterns.season_dir)
- [ ] Ne pas recréer si existe déjà
- [ ] Support dry-run
- [ ] Tests

**Commit** : `v3.10.1: Implement season directory creation`

### 3.10.2 — Matching fichiers → épisodes API

- [ ] Implémenter `match_episode_files(video_files, api_episodes)` → list[tuple]
- [ ] Extraire S/E du filename (réutiliser le cleaner de V2)
- [ ] Matcher avec le dict {episode_number: title} de l'API
- [ ] Retourner [(video_path, season, episode, api_title)]
- [ ] Gérer les épisodes non trouvés dans l'API (garder le nom original, log warning)
- [ ] Tests avec des fichiers réalistes

**Commit** : `v3.10.2: Implement episode file-to-API matching`

### 3.10.3 — Renommage épisodes + sous-titres

- [ ] Implémenter `rename_episodes(matched_episodes, show_dir, patterns, dry_run)`
- [ ] Renommer chaque vidéo : `S01E01 - Titre Episode.mkv` (via NamingPatterns)
- [ ] Déplacer dans le bon dossier `Saison XX/`
- [ ] Détecter les sous-titres associés (même base name .srt, .sub, .vtt)
- [ ] Renommer les sous-titres avec le même pattern
- [ ] Support dry-run (log sans rename/move)
- [ ] Tests

**Commit** : `v3.10.3: Implement episode and subtitle renaming`

### 3.10.4 — Tests end-to-end renommage

- [ ] Test complet avec structure réaliste (tmp_path) :
  - Dossier série avec fichiers S01E01...S01E08 nommés avec tags torrent
  - API mock retournant les titres d'épisodes
  - Vérifier : dossiers saison créés, fichiers renommés, sous-titres renommés
- [ ] Test dry-run : rien ne bouge
- [ ] Test épisode manquant dans l'API : nom original conservé

**Commit** : `v3.10.4: Add end-to-end episode renaming tests`
