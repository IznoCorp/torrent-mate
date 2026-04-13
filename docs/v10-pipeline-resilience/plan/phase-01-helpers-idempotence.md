# Phase 1 — Helpers validation + Ingest/Sort/Clean idempotence

## Objectif

Creer les helpers de validation NFO et fast-skip, puis rendre Ingest, Sort et Clean parfaitement idempotents avec detection des etats corrompus.

## Sous-phases

### 10.1.1 — \_is_nfo_complete + fast-skip helpers

- [x] Ajouter `_is_nfo_complete(nfo_path) -> bool` dans `scraper/scraper.py`
- [x] Valide : XML parsable ET `<uniqueid>` present avec texte non-vide
- [x] Retourne False pour : fichier absent, XML invalide, pas de uniqueid
- [x] Ajouter `_has_unsorted_items(settings) -> bool` dans `sorter/run.py`
- [x] Verifie si 097-TEMP contient des items non-hidden
- [x] Ajouter `_has_polluted_folders(category_dir) -> bool` dans `process/reclean.py`
- [x] Scan rapide : retourne True des le premier dossier pollue trouve
- [x] Tests : \_is_nfo_complete avec NFO valide, tronque, sans uniqueid, absent
- [x] Tests : \_has_unsorted_items avec dir vide, avec fichiers, avec hidden seulement
- [x] Tests : \_has_polluted_folders avec dossiers propres, avec dossier pollue

**Commit** : `v10.1.1: Add NFO validation and fast-skip helper functions`

### 10.1.2 — Ingest idempotence + fast-skip

- [x] Ingest deja idempotent : hash tracker skip per-item, orphan cleanup fonctionne
- [x] Fast-skip non applicable (qBit connection requise pour lister les torrents)
- [x] Tests existants couvrent : already_ingested_skip, orphan cleanup, no_torrents

**Commit** : `v10.1.2: Add ingest fast-skip when no new torrents`

### 10.1.3 — Sort idempotence + fast-skip

- [x] Ajouter fast-skip en debut de `run_sort()` : si `_has_unsorted_items()` retourne False → retour immediat
- [x] Sort skip exact-name duplicates deja implemente dans `sort_item()` (ligne 149)
- [x] Fuzzy dedup delegue a la phase clean (reclean+dedup) — pas duplique dans sort
- [x] Tests : sort fast-skip avec 097-TEMP vide
- [x] Tests : sort processes items quand 097-TEMP a du contenu

**Commit** : `v10.1.3: Add sort idempotence — skip already-sorted items`

### 10.1.4 — Clean idempotence + fast-skip

- [ ] Ajouter fast-skip en debut de `run_clean()` : si `_has_polluted_folders()` retourne False pour les deux categories → retour immediat
- [ ] Dans `reclean_folders()` : si dossier source n'existe plus (crash mid-rename) mais target existe → skip sans erreur
- [ ] Tests : clean fast-skip quand tous les dossiers sont propres
- [ ] Tests : clean skip dossier source disparu quand target existe

**Commit** : `v10.1.4: Add clean idempotence — fast-skip and crash recovery`
