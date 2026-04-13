# Phase 1 — Helpers validation + Ingest/Sort/Clean idempotence

## Objectif

Creer les helpers de validation NFO et fast-skip, puis rendre Ingest, Sort et Clean parfaitement idempotents avec detection des etats corrompus.

## Sous-phases

### 10.1.1 — \_is_nfo_complete + fast-skip helpers

- [ ] Ajouter `_is_nfo_complete(nfo_path) -> bool` dans `scraper/scraper.py`
- [ ] Valide : XML parsable ET `<uniqueid>` present avec texte non-vide
- [ ] Retourne False pour : fichier absent, XML invalide, pas de uniqueid
- [ ] Ajouter `_has_unsorted_items(settings) -> bool` dans `sorter/run.py`
- [ ] Verifie si 097-TEMP contient des items non-hidden
- [ ] Ajouter `_has_polluted_folders(category_dir) -> bool` dans `process/reclean.py`
- [ ] Scan rapide : retourne True des le premier dossier pollue trouve
- [ ] Tests : \_is_nfo_complete avec NFO valide, tronque, sans uniqueid, absent
- [ ] Tests : \_has_unsorted_items avec dir vide, avec fichiers, avec hidden seulement
- [ ] Tests : \_has_polluted_folders avec dossiers propres, avec dossier pollue

**Commit** : `v10.1.1: Add NFO validation and fast-skip helper functions`

### 10.1.2 — Ingest idempotence + fast-skip

- [ ] Ajouter fast-skip en debut de `run_ingest()` : si aucun torrent completed non-ingere → retour immediat
- [ ] Le fast-skip retourne un StepReport avec skip_count = nombre de torrents deja ingeres
- [ ] Verifier que le nettoyage orphelins `.ingest_tmp_*` fonctionne toujours
- [ ] Tests : fast-skip quand tous les torrents sont deja ingeres
- [ ] Tests : pas de fast-skip quand un nouveau torrent est present

**Commit** : `v10.1.2: Add ingest fast-skip when no new torrents`

### 10.1.3 — Sort idempotence + fast-skip

- [ ] Ajouter fast-skip en debut de `run_sort()` : si `_has_unsorted_items()` retourne False → retour immediat
- [ ] Dans `Sorter.sort_item()` : avant de deplacer, verifier si un dossier avec le meme titre existe deja dans la categorie destination
- [ ] Utiliser `fuzzy_match_score` pour la detection (meme guards que dedup)
- [ ] Si match → status "skipped" avec message "already sorted as {existing_name}"
- [ ] Tests : sort fast-skip avec 097-TEMP vide
- [ ] Tests : sort skip item deja present dans 001-MOVIES
- [ ] Tests : sort ne skip pas si titre different

**Commit** : `v10.1.3: Add sort idempotence — skip already-sorted items`

### 10.1.4 — Clean idempotence + fast-skip

- [ ] Ajouter fast-skip en debut de `run_clean()` : si `_has_polluted_folders()` retourne False pour les deux categories → retour immediat
- [ ] Dans `reclean_folders()` : si dossier source n'existe plus (crash mid-rename) mais target existe → skip sans erreur
- [ ] Tests : clean fast-skip quand tous les dossiers sont propres
- [ ] Tests : clean skip dossier source disparu quand target existe

**Commit** : `v10.1.4: Add clean idempotence — fast-skip and crash recovery`
