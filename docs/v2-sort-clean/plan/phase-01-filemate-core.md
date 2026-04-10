# Phase 1 — Intégration FileMate core

## Objectif

Intégrer les modules réutilisables de FileMate dans personalscraper/sorter/.

## Sous-phases

### 2.1.1 — FileType enum et détection

- [ ] Créer `personalscraper/sorter/file_type.py`
- [ ] Porter `FileType` enum depuis FileMate (MOVIE, TVSHOW, EBOOK, AUDIO, APP, OTHER)
- [ ] Porter `FileTypeExtensions` (mapping extension → type)
- [ ] Porter `detect_file_type(path)` et `detect_dir_type(path)` depuis FileMate
- [ ] Détection TV basée sur les extensions uniquement dans cette phase
  - La détection améliorée via guessit (patterns `1x04`, `ep.1`) est implémentée en phase 2 (cleaner.py)
- [ ] Tests unitaires

**Commit** : `v2.1.1: Port file type detection from FileMate`

### 2.1.2 — Fuzzy directory matcher (rapidfuzz)

- [ ] Créer `personalscraper/sorter/matcher.py`
- [ ] Implémenter `media_processor(s)` : lowercase + NFD decomposition + strip ponctuation
  - ⚠️ `rapidfuzz.utils.default_process` ne supprime PAS les accents — custom obligatoire
  - Ref : docs/rapidfuzz-reference.md — section "media_processor custom"
- [ ] Implémenter `find_matching_directory(name, candidates, respect_year, threshold=85.0)`
  - Utiliser `rapidfuzz.process.extractOne(name, candidate_names, scorer=fuzz.WRatio, processor=media_processor)`
  - Si `respect_year=True` : extraire année des deux noms, rejeter si années différentes
  - Retourner `None` si score < threshold
- [ ] ⚠️ NE PAS porter le matcher bidirectionnel custom de FileMate — remplacé par rapidfuzz
  - Avantage : cohérence avec V3 (`confidence.py`) et V5 (`media_index.py`) qui utilisent aussi rapidfuzz
- [ ] Tests unitaires : doublons ("The Matrix" vs "The Matrix Remastered"), accents ("Amélie" vs "Amelie"),
      noms avec année, seuil de score

**Commit** : `v2.1.2: Implement rapidfuzz-based directory matcher`
