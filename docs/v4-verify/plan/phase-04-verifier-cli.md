# Phase 4 — Orchestrateur verify + CLI

## Objectif

Assembler checker + fixer + genre_mapper dans l'orchestrateur, connecter au CLI.

## Sous-phases

### 4.4.1 — Orchestrateur Verifier

- [ ] Créer `personalscraper/verify/verifier.py`
- [ ] Implémenter `VerifyResult` dataclass
- [ ] Implémenter `Verifier.__init__(settings, patterns, dry_run, fix)`
- [ ] Implémenter `verify_movie(movie_dir)` :
  1. `checker.check_movie()` → première passe
  2. Si fix=True et erreurs fixables → `fixer.fix_movie()`
  3. `checker.check_movie()` → deuxième passe
  4. Construire VerifyResult (status, errors, warnings, fixes_applied, category)
- [ ] Implémenter `verify_tvshow(show_dir)` — même logique
- [ ] Implémenter `verify_all_movies(movies_dir)` — itère, ne crash pas sur erreur individuelle
- [ ] Implémenter `verify_all_tvshows(tvshows_dir)` — idem
- [ ] Implémenter `get_dispatchable(results)` — filtre status != "blocked"
- [ ] Tests unitaires

**Commit** : `v4.4.1: Implement Verifier orchestrator`

### 4.4.2 — Commande CLI verify

- [ ] Ajouter `personalscraper verify` dans `cli.py`
- [ ] Options : `--dry-run`, `--fix` (défaut True), `--verbose`, `--movies-only`, `--tvshows-only`
- [ ] Initialiser Verifier depuis Settings
- [ ] Appeler `verify_all_movies()` + `verify_all_tvshows()`
- [ ] Afficher résumé : X valid, Y fixed, Z blocked, N warnings
- [ ] En mode verbose : détail par dossier (checks passés, corrections, erreurs)
- [ ] Alimenter StepReport avec les VerifyResult
- [ ] Tests CLI via CliRunner

**Commit** : `v4.4.2: Wire verify command into CLI`

### 4.4.3 — Tests end-to-end verify

- [ ] Test avec structure réaliste (tmp_path) :
  - 2 films OK, 1 film avec dossier mal nommé (fixable), 1 film sans NFO (blocked)
  - 2 séries OK, 1 série sans catégorie (blocked)
- [ ] Vérifier que `get_dispatchable()` retourne uniquement les dossiers valid/fixed
- [ ] Vérifier le résumé CLI
- [ ] Test dry-run : rien ne change, rapport correct
- [ ] Test que les VerifyResult sont sérialisables (pour V6 notifications)

**Commit** : `v4.4.3: Add end-to-end verify tests`
