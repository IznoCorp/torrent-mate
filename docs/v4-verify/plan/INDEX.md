# V4 — VERIFY : Plan d'implémentation

> Quality gate : vérification, correction et qualification des médias scrapés

## Phases

| #   | Phase                          | Fichier                                              | Status |
| --- | ------------------------------ | ---------------------------------------------------- | ------ |
| 1   | Genre mapper (catégorisation)  | [phase-01-genre-mapper.md](phase-01-genre-mapper.md) | [ ]    |
| ·   | _Contrôle de cohérence P1→P2_  |                                                      | [ ]    |
| 2   | Media checker (vérifications)  | [phase-02-checker.md](phase-02-checker.md)           | [ ]    |
| ·   | _Contrôle de cohérence P2→P3_  |                                                      | [ ]    |
| 3   | Media fixer (corrections auto) | [phase-03-fixer.md](phase-03-fixer.md)               | [ ]    |
| ·   | _Contrôle de cohérence P3→P4_  |                                                      | [ ]    |
| 4   | Orchestrateur verify + CLI     | [phase-04-verifier-cli.md](phase-04-verifier-cli.md) | [ ]    |
| ·   | _Contrôle de cohérence V4→V5_  |                                                      | [ ]    |

## Dépendances entre phases

```
Phase 1 (genre mapper) ──┐
                          ├──▶ Phase 4 (orchestrateur + CLI)
Phase 2 (checker) ───────┤
                          │
Phase 3 (fixer) ─────────┘

Phase 2 dépend de Phase 1 (checker utilise genre_mapper pour le critère catégorie)
Phase 3 dépend de Phase 2 (fixer reçoit les CheckResult pour savoir quoi corriger)
Phase 4 assemble tout
```

Phases 1-3 : modules indépendants (mais 2 dépend de 1, 3 dépend de 2).
Phase 4 : orchestrateur + intégration CLI.

## Contrôles de cohérence

### Après Phase 1 (Genre mapper)

- [ ] `categorize_movie()` retourne la bonne catégorie pour chaque combinaison de genres
- [ ] `categorize_tvshow()` distingue anime (JP + Animation) des autres animations
- [ ] Gère les genres TMDB films, TMDB TV, ET TVDB (3 systèmes d'IDs)
- [ ] Genre inconnu → retourne None (pas de crash)
- [ ] Tests paramétrés couvrent toutes les catégories de destination

### Après Phase 2 (Media checker)

- [ ] `check_movie()` retourne la bonne sévérité pour chaque critère
- [ ] `check_tvshow()` vérifie la structure Saison XX/ + épisodes
- [ ] NFO parsé correctement, tags obligatoires identifiés
- [ ] Artwork vérifié avec les bons noms (NamingPatterns)
- [ ] Critère catégorie utilise genre_mapper correctement

### Après Phase 3 (Media fixer)

- [ ] Renommage dossier depuis NFO fonctionne
- [ ] Renommage artwork fonctionne
- [ ] Dry-run ne modifie rien
- [ ] Fix d'un dossier suivi de re-check → plus d'erreurs fixables

### Après Phase 4 (Orchestrateur → V5)

- [ ] `verify_movie()` enchaîne check → fix → re-check → categorize
- [ ] `verify_all_movies()` traite tous les dossiers, n'arrête pas sur erreur
- [ ] `get_dispatchable()` filtre correctement (valid + fixed, pas blocked)
- [ ] CLI `personalscraper verify` fonctionne standalone
- [ ] CLI `personalscraper verify --dry-run` n'écrit rien
- [ ] CLI `personalscraper verify --fix` corrige puis valide
- [ ] Rapport final : X valid, Y fixed, Z blocked
- [ ] Les `VerifyResult` sont compatibles avec V5 (dispatch) et V6 (notifications)
