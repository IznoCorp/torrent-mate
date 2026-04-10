# Phase 2 — Nouveau cleaner regex

## Objectif

Remplacer le système clean_words.txt/clean_chars.txt par un cleaner regex robuste.

## Sous-phases

### 2.2.1 — NameCleaner avec patterns catégoriels

- [ ] Créer `personalscraper/sorter/cleaner.py`
- [ ] Implémenter les regex par catégorie (RESOLUTION, CODEC, AUDIO, SOURCE, VIDEO_PROPS, LANGUAGE, RELEASE_GROUP, MISC)
- [ ] Implémenter `clean(name)` : applique tous les patterns, collapse espaces
- [ ] Implémenter `extract_year(name)` : regex `(19|20)\d{2}`
- [ ] Implémenter `extract_season_episode(name)` : S01E04, 1x04, Saison X Episode Y
- [ ] Implémenter `clean_for_folder(name)` : retourne "Title (Year)" ou "Title"

**Commit** : `v2.2.1: Implement regex-based NameCleaner`

### 2.2.2 — Tests exhaustifs du cleaner

- [ ] Tests avec les noms réels du dossier `torrents/complete/`
- [ ] Tests sur les cas problématiques connus (Avatar..., noms avec chiffres)
- [ ] Tests edge cases : pas d'année, pas de season/episode, noms très courts
- [ ] Vérifier que title + year sont correctement extraits pour le scraping

**Commit** : `v2.2.2: Add exhaustive cleaner tests with real torrent names`
