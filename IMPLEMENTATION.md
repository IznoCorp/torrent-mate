# Implementation Progress — recherche-juste

> For Claude: read this file at session start. Current feature tracker.

**Feature**: La recherche des Acquisitions trouve ce qu'on lui demande
**Type**: fix
**Version bump**: 0.84.0 → 0.85.0 (minor — nouveau moteur de ranking + pagination API + champs provider)
**Branch**: `fix/recherche-juste`
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: `docs/features/recherche-juste/DESIGN.md`
**Master plan**: `docs/features/recherche-juste/plan/INDEX.md`
**Diagnostic source**: `docs/analysis/2026-08-05-acquisition-search-relevance-diagnosis.md`
**Ticket**: KanbanMate #409

## Contexte d'exécution

Worktree isolé `.claude/worktrees/acq-search-relevance`, branché sur `origin/main` (`207abc25`).
**Jamais de `pip install -e .`** ici : le package est résolu par cwd, l'install editable globale
et les crons prod restent intacts. Baseline à la création : 10429 passed, 7 skipped, 0 failed.

## Invariants non négociables (DESIGN §2, gelés)

- Le chemin de scrape ne bouge pas : `_match_score.py`, `_match_movie.py`, `_match_tv.py`,
  `scraper/movie_service.py` **strictement inchangés** (ACC-01 le prouve).
- TVDB reste canonique pour les séries **dans le scrape** ; l'union TVDB ∪ TMDB ne concerne
  que les surfaces de recherche interactive.
- L'id de suivi d'une série reste l'**id TVDB**, même quand la ligne vient de TMDB (§5).
- La page ne scrolle jamais latéralement (§12) : le carrousel scrolle dans **son** conteneur.
- Rien en silence (§8) : `total` reflète le nombre réel de candidats, jamais la taille de page.
- Les pondérations du score sont **calibrées par le jeu golden**, jamais figées à la main.

## Phases

| #   | Phase                                                   | Fichier plan                          | Cause visée | Status |
| --- | ------------------------------------------------------- | ------------------------------------- | ----------- | ------ |
| 1   | Porter le signal de popularité sur `SearchResult`       | `phase-01-popularity-signal.md`       | RC4 (prérequis) | [x] |
| 2   | Le moteur de ranking + le jeu golden (test-first)       | `phase-02-search-ranking-engine.md`   | RC1, RC2, RC4   | [x] |
| 3   | Recherche TV — union TVDB ∪ TMDB par `remote_ids`       | `phase-03-tv-union.md`                | RC5             | [x] |
| 4   | Pagination API + branchement des deux surfaces          | `phase-04-api-pagination-surfaces.md` | RC3, RC6        | [x] |
| 5   | UI carrousel mobile-first + preuve 390 px               | `phase-05-ui-carousel-mobile.md`      | §12             | [x] |
| 6   | Portes, PR, CI, merge, déploiement, vérification réelle | `phase-06-gates-pr-deploy.md`         | —               | [ ] |
| 7   | Filtre par nom sur les suivis (demande opérateur)       | `phase-07-followed-name-filter.md`    | §12, §8         | [x] |

L'ordre porte du sens : le signal de popularité doit exister avant le moteur qui le consomme ;
le moteur doit être prouvé isolément avant d'être branché sur deux surfaces ; l'UI vient après
une API qui pagine réellement.

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Phase 6 (`phase-06-gates-pr-deploy.md`) — portes, PR, CI, merge, déploiement, vérification réelle.

ACC-05 (preuve 390 px) et ACC-03/ACC-04 (données live) sont exécutés APRÈS déploiement — déclarés
différés, non cochés d'avance.

Relevé de calibrage : `docs/features/recherche-juste/CALIBRATION.md` (pondérations du DESIGN
conservées ; observation sur la redondance du terme « titre exact » à porter au corps de PR).
