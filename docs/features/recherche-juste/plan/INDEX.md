# Plan — `recherche-juste`

Découpage d'exécution de `docs/features/recherche-juste/DESIGN.md`. Six phases, dans un ordre
qui porte du sens : le signal de popularité doit exister avant le moteur qui le consomme ; le
moteur doit être prouvé avant d'être branché sur deux surfaces ; l'UI vient après une API qui
pagine réellement.

## Phases

| #   | Phase                                                            | Fichier                                    | Status |
| --- | ---------------------------------------------------------------- | ------------------------------------------ | ------ |
| 1   | Porter le signal de popularité sur `SearchResult`                | `phase-01-popularity-signal.md`            | [ ]    |
| 2   | Le moteur de ranking + le jeu golden (test-first)                | `phase-02-search-ranking-engine.md`        | [ ]    |
| 3   | Recherche TV — union TVDB ∪ TMDB par `remote_ids`                | `phase-03-tv-union.md`                     | [ ]    |
| 4   | Pagination API + branchement des deux surfaces                   | `phase-04-api-pagination-surfaces.md`      | [ ]    |
| 5   | UI carrousel mobile-first + preuve 390 px                        | `phase-05-ui-carousel-mobile.md`           | [ ]    |
| 6   | Portes, PR, CI, merge, déploiement, vérification réelle          | `phase-06-gates-pr-deploy.md`              | [ ]    |

## Règle de travail (toutes phases)

- **Test-first.** Chaque défaut corrigé a d'abord un test qui le reproduit, rouge, avant le
  correctif. Un correctif sans test rouge préalable n'est pas recevable.
- **Le chemin de scrape ne bouge pas.** `_match_score.py`, `_match_movie.py`, `_match_tv.py`,
  `scraper/movie_service.py` restent inchangés — vérifié à chaque porte de phase par ACC-01.
- **Aucun report.** Aucun step, test ou sous-périmètre différé sans arbitrage explicite de
  l'opérateur. Une difficulté se signale, elle ne se contourne pas en silence.
- **Fixtures réelles.** Les jeux de test s'appuient sur des payloads provider capturés, jamais
  sur des formes inventées.
- **Pas de `pip install -e .`** dans ce worktree : le package est résolu par `cwd`.

## Portes communes à chaque phase

```bash
make lint        # ruff + mypy, 0 erreur
make test        # NNNN passed, 0 failed / 0 error
git diff --name-only origin/main...HEAD -- \
  personalscraper/scraper/_match_score.py \
  personalscraper/scraper/_match_movie.py \
  personalscraper/scraper/_match_tv.py \
  personalscraper/scraper/movie_service.py   # sortie VIDE (ACC-01)
```

Un `ERROR` (et pas seulement `FAILED`) dans `make test` signifie que la collecte a planté :
tous les tests suivants sont sautés. Corriger les imports avant toute autre chose.

## Traçabilité DESIGN → phases

| Cause racine | Traitée en |
| --- | --- |
| RC1 `_length_ratio_guard` met la cible à 0.000 | Phase 2 |
| RC2 `_superstring_penalty` rétrograde les extensions | Phase 2 |
| RC3 `limit=5` en dur, pas de pagination | Phase 4 |
| RC4 popularité et récence jetées | Phase 1 (portage) + Phase 2 (usage) |
| RC5 TMDB jamais consulté en TV | Phase 3 |
| RC6 le deck de résolution a le même défaut | Phase 4 |
| §12 mobile first | Phase 5 |
