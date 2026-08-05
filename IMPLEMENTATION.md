# Implementation Progress — recherche-juste

> For Claude: read this file at session start. Current feature tracker.

**Feature**: La recherche des Acquisitions trouve ce qu'on lui demande
**Type**: fix
**Version bump**: 0.84.0 → 0.85.0 (minor — nouveau moteur de ranking + pagination API + champs provider)
**Branch**: `fix/recherche-juste`
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: `docs/features/recherche-juste/DESIGN.md`
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

_(filled by /implement:plan)_

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.
