# Implementation Progress — spine-truth

> For Claude: read this file at session start. Current feature tracker.

**Feature**: La spine de provenance ne perd plus aucun parcours (§13)
**Type**: fix
**Version bump**: 0.79.2 → 0.80.0 (minor — migration + nouvelle règle de garde + backfill)
**Branch**: `fix/spine-truth`
**Design**: `docs/features/spine-truth/DESIGN.md`
**Diagnostic source**: `docs/analysis/2026-08-05-provenance-spine-hole-handoff.md`

## Contexte d'exécution

Worktree isolé `.claude/worktrees/acq-escalade`, branché sur `origin/main` (`821009d7`).
**Jamais de `pip install -e .`** ici : le package est résolu par cwd, l'install editable globale
et les crons prod restent intacts.

## Invariants non négociables (DESIGN §7, gelés)

- La spine reste **advisory** : aucune écriture de provenance ne fait échouer une étape.
  Ce qui change est la **visibilité** de l'échec, jamais sa gravité.
- Le chemin redevient une **entrée de recherche** ; l'écriture est keyée sur `info_hash`.
- Le backfill **n'invente rien** : `ingest_path` / `current_path` / `scraped_at` restent NULL.
- Une règle de garde = **un** mode de défaillance (pas de doublon avec `GRABBED_HASH_MISSING`).
- Aucun verdict « conforme » sans `scripts/check-acquisition-coherence.py` à exit 0 sur les
  données réelles, **après** déploiement.

## Phases

| #   | Phase                                                          | Défaut visé | Status |
| --- | -------------------------------------------------------------- | ----------- | ------ |
| 1   | Migration 015 — `CHECK kind` accepte `'season'` + garde G1      | Cause A     | [ ]    |
| 2   | `move_path` de sous-arbre + dispatch corrélé par `info_hash`    | Cause B     | [ ]    |
| 3   | Le rejet d'écriture n'est plus muet + gardes G2/G3              | le trou     | [ ]    |
| 4   | §12 — les 3 `<Link>` en `block h-full` + test                   | Cause C     | [ ]    |
| 5   | Backfill §13 — reconstruire les lignes perdues                  | l'état      | [ ]    |
| 6   | Gates, PR, CI, merge, déploiement, vérification réelle + 390px  | —           | [ ]    |

L'ordre porte du sens : la migration doit précéder tout test qui écrit un `kind='season'` ;
la corrélation doit précéder les gardes qui l'auditent ; le backfill vient en dernier parce
qu'il s'appuie sur la table migrée.

## ACCEPTANCE

_(rempli en phase 6 — déroulé daté sur données réelles, §méthode règle 2)_

## Next action

Phase 1 — écrire le test de la migration avant la migration.
