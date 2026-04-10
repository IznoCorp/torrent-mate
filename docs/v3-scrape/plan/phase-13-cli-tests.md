# Phase 13 — CLI scrape + tests end-to-end

## Objectif

Connecter les orchestrateurs au CLI et valider l'ensemble.

## Sous-phases

### 3.13.1 — Commande CLI scrape

- [ ] Implémenter `personalscraper scrape` dans `cli.py` (remplacer le stub)
- [ ] Options : --dry-run, --interactive, --verbose, --movies-only, --tvshows-only
- [ ] Initialiser les clients API (TMDB + TVDB) depuis Settings
- [ ] Appeler process_movies() et process_tvshows()
- [ ] Alimenter StepReport avec les ScrapeResult
- [ ] Afficher résumé en fin de commande (X scrapés, Y skippés, Z erreurs)
- [ ] Logger toutes les opérations

**Commit** : `v3.13.1: Wire scrape command into CLI`

### 3.13.2 — Tests end-to-end dry-run

- [ ] Test `personalscraper scrape --dry-run` via CliRunner
- [ ] Vérifier que les API sont appelées mais rien n'est écrit
- [ ] Vérifier le résumé de sortie
- [ ] Tests avec mock API (pas d'appel réseau dans les tests unitaires)

**Commit** : `v3.13.2: Add dry-run end-to-end scrape tests`

### 3.13.3 — Tests end-to-end avec données réelles

- [ ] Test sur un film réel de 001-MOVIES/ (dry-run)
- [ ] Test sur une série réelle de 002-TVSHOWS/ (dry-run)
- [ ] Vérifier la qualité des matchs (confiance)
- [ ] Vérifier que les NFO seraient générés correctement
- [ ] Documenter les résultats dans le rapport de phase

**Commit** : `v3.13.3: Validate scraper against real media library`

### 3.13.4 — Test mode interactif

- [ ] Test `personalscraper scrape --interactive` avec mock Click.prompt
- [ ] Vérifier que les résultats sont présentés correctement
- [ ] Vérifier que le choix utilisateur est respecté
- [ ] Vérifier "Aucun résultat" → skip propre

**Commit** : `v3.13.4: Add interactive mode tests`
