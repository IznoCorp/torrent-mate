# Phase 2 — Process: reclean + dedup

## Objectif

Creer le module `process/` avec les fonctions de re-nettoyage des noms de dossiers et de fusion des doublons fuzzy. Corrige #25 (Avatar nom pollue).

## Sous-phases

### 9.2.1 — is_title_polluted detection

- [x] Creer `personalscraper/process/__init__.py`
- [x] Creer `personalscraper/process/reclean.py`
- [x] `is_title_polluted(title: str) -> bool` — utilise guessit pour detecter les tokens release
- [x] Detecte : `screen_size`, `video_codec`, `release_group`, `source`, `audio_codec`
- [x] Ne flag PAS les titres propres comme "Scream 7" ou "2001 A Space Odyssey"
- [x] Tests : "Avatar de feu et de cendres 7 1 neostark" → True
- [x] Tests : "Scream 7" → False, "The Matrix" → False
- [x] Tests : "Movie.Title.2024.1080p.BluRay.x264-GROUP" → True

**Commit** : `v9.2.1: Add is_title_polluted() release token detection`

### 9.2.2 — reclean_folders

- [x] `reclean_folders(category_dir, dry_run) -> StepReport`
- [x] Scan tous les dossiers de category_dir
- [x] Passe 1 (locale) : si `is_title_polluted(titre)` → re-clean via NameCleaner
- [x] Renomme le dossier en format propre `Title (Year)` apres re-clean
- [x] Si la cible existe deja → merge via `_merge_dirs`
- [x] StepReport comptabilise : success (re-cleaned), skip (already clean), error (failed)
- [x] Dry-run : log sans renommer
- [x] Tests : dossier pollue → renomme, dossier propre → skip, target exists → merge

**Commit** : `v9.2.2: Add reclean_folders() with two-pass detection`

### 9.2.3 — dedup_folders

- [x] Creer `personalscraper/process/dedup.py`
- [x] `dedup_folders(category_dir, dry_run) -> int` — retourne le nombre de merges
- [x] Compare chaque paire de dossiers via `fuzzy_match_score` (year guard actif)
- [x] Quand doublon detecte : merge le moins complet dans le plus complet
- [x] "Plus complet" = a un NFO, ou plus de fichiers, ou a un poster
- [x] Utilise `_merge_dirs` pour la fusion
- [x] Protections anti-faux-positif : threshold 90%+, year +-1, length ratio 0.67
- [x] Tests : "Shrinking" + "Shrinking (2023)" → merge
- [x] Tests : "The Matrix (1999)" + "The Matrix (2003)" → pas de merge (year guard)
- [x] Tests : dry-run → log sans merger

**Commit** : `v9.2.3: Add dedup_folders() fuzzy duplicate merger`
