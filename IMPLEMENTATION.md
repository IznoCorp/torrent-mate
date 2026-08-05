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
| 1   | Migration 015 — `CHECK kind` accepte `'season'` + garde G1      | Cause A     | [x]    |
| 2   | `move_path` de sous-arbre + dispatch corrélé par `info_hash`    | Cause B     | [x]    |
| 3   | Le rejet d'écriture n'est plus muet + gardes G2/G3              | le trou     | [x]    |
| 4   | §12 — les 3 `<Link>` en `block h-full` + test                   | Cause C     | [x]    |
| 5   | Backfill §13 — reconstruire les lignes perdues                  | l'état      | [x]    |
| 6   | Gates, PR, CI, merge, déploiement, vérification réelle + 390px  | —           | [ ]    |

L'ordre porte du sens : la migration doit précéder tout test qui écrit un `kind='season'` ;
la corrélation doit précéder les gardes qui l'auditent ; le backfill vient en dernier parce
qu'il s'appuie sur la table migrée.

## Mutation-check des gardes (exécuté 2026-08-05)

Chaque garde a été confrontée à l'implémentation fautive qu'elle prétend attraper — une
garde qui passe sur le code cassé ne garde rien.

| Mutation appliquée | Garde | Résultat |
| --- | --- | --- |
| `CHECK` remis à `('movie','episode')` | G1 égalité `kind` | **1 failed** ✅ |
| contenance remise à l'égalité de chemin | corrélation dispatch | **8 failed** ✅ |
| `log.error` remis à `log.warning` | rejet non muet | **1 failed** ✅ |
| branche `SPINE_ROW_MISSING` neutralisée | G2 | **2 failed** ✅ |
| branche `SPINE_DISPATCH_MISSING` neutralisée | G3 | **1 failed** ✅ |
| `h-full` retiré d'une seule tuile | §12 hauteurs égales | **1 failed** ✅ |
| backfill écrivant un `current_path` inventé | §13 « ne rien inventer » | **1 failed** ✅ |
| backfill déclarant `dispatched` sans preuve | §13 statut prouvé | **2 failed** ✅ |
| `--apply` ignoré (dry-run qui écrit) | dry-run par défaut | **1 failed** ✅ |

## ACCEPTANCE

_(rempli en phase 6 — déroulé daté sur données réelles après déploiement, §méthode règle 2)_

Répétition à blanc du backfill sur les bases RÉELLES (2026-08-05, lecture seule) :
**57 parcours** reconstruits — 55 `dispatched` avec leur chemin de médiathèque réel,
2 arrêtés à `grabbed` (les deux packs American Dad encore en vol : `wanted.status='grabbed'`,
donc aucun atterrissage à prouver).

## Next action

Phase 6 — PR, CI verte, merge, déploiement, puis migration + backfill `--apply` sur les
bases réelles, `check-acquisition-coherence.py` à exit 0, et la Vue d'ensemble à 390px.
