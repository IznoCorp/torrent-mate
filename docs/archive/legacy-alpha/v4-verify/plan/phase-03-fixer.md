# Phase 3 — Media fixer (corrections automatiques)

## Objectif

Implémenter les corrections automatiques pour les problèmes identifiés par le checker.

## Sous-phases

### 4.3.1 — Fixer films

- [ ] Créer `personalscraper/verify/fixer.py`
- [ ] Implémenter `FixAction` dataclass et `MediaFixer.__init__(patterns, dry_run)`
- [ ] Implémenter `fix_movie(movie_dir, checks)` → list[FixAction]
  - `dir_naming` failed + NFO existe → extraire titre/année du NFO → `Path.rename()`
  - `artwork_poster` failed + un fichier `poster.jpg` ou `*.poster.*` trouvé → renommer selon NamingPatterns
  - `artwork_landscape` failed + un fichier `landscape.jpg` ou `*.landscape.*` trouvé → renommer
- [ ] Support dry_run : construire les FixAction mais ne pas exécuter les rename
- [ ] Gestion erreur I/O : try/except sur chaque rename, log + skip si échec
- [ ] Tests avec tmp_path

**Commit** : `v4.3.1: Implement movie fixer (dir rename, artwork rename)`

### 4.3.2 — Fixer séries

- [ ] Implémenter `fix_tvshow(show_dir, checks)` → list[FixAction]
  - `dir_naming` failed → même logique que films (depuis tvshow.nfo)
  - `season_structure` : épisodes hors dossier saison → déplacer dans le bon `Saison XX/`
  - `artwork` mal nommé → renommer
- [ ] Support dry_run
- [ ] Tests

**Commit** : `v4.3.2: Implement tvshow fixer (dir rename, episode relocation)`

### 4.3.3 — Tests intégration fix → re-check

- [ ] Test complet : créer un dossier film "cassé" → fix → re-check → tous les checks fixables passent
- [ ] Test complet : dossier série "cassé" → fix → re-check
- [ ] Test dry_run : vérifier que rien n'est modifié, mais FixActions sont quand même retournées
- [ ] Test cas non fixable : NFO absent → fix ne fait rien → re-check toujours en erreur

**Commit** : `v4.3.3: Add integration tests for fix-then-recheck cycle`
