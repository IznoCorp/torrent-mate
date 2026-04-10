# Phase 1 — Intégration FileMate core

## Objectif

Intégrer les modules réutilisables de FileMate dans personalscraper/sorter/.

## Sous-phases

### 2.1.1 — FileType enum et détection

- [ ] Créer `personalscraper/sorter/file_type.py`
- [ ] Porter `FileType` enum depuis FileMate (MOVIE, TVSHOW, EBOOK, AUDIO, APP, OTHER)
- [ ] Porter `FileTypeExtensions` (mapping extension → type)
- [ ] Porter `detect_file_type(path)` et `detect_dir_type(path)` depuis FileMate
- [ ] Adapter la détection TV : ajouter patterns `1x04`, `ep.1`
- [ ] Tests unitaires

**Commit** : `v2.1.1: Port file type detection from FileMate`

### 2.1.2 — Fuzzy directory matcher

- [ ] Créer `personalscraper/sorter/matcher.py`
- [ ] Porter `find_matching_directory()` et `tokenize()` depuis FileMate
- [ ] Conserver la logique bidirectionnelle + single-token guard + year respect
- [ ] Tests unitaires (reprendre les tests existants de FileMate)

**Commit** : `v2.1.2: Port fuzzy directory matcher from FileMate`
