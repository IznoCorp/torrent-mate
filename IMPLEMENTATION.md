# Implementation Progress — acq-escalade

> For Claude: read this file at session start. Current feature tracker.

**Feature**: L'acquisition escalade vers le pack saison quand la recherche épisode échoue
**Type**: fix
**Version bump**: 0.78.0 → 0.78.2 (bugfix)
**Branch**: fix/acq-escalade
**PR merge**: auto — standing operator contract: adversarial review(s) + tests before merge.
**PR**: _(created after last phase)_
**Design**: docs/features/acq-escalade/DESIGN.md
**Master plan**: _(to be defined after /implement:plan)_

## Contexte d'exécution

Travail mené dans le worktree `.claude/worktrees/acq-escalade` (isolement demandé par
l'opérateur : une feature concurrente `fix/media-sheet-data` est en vol dans un autre
worktree depuis 2026-08-04 14:10).

**0.78.1 est pris** par `fix/media-sheet-data` (non mergée) — d'où le saut à **0.78.2**.

Points de collision connus avec cette feature concurrente, à re-vérifier avant merge :

| Fichier | Pourquoi il collisionne |
| --- | --- |
| `personalscraper/__init__.py` | Ligne de version — résolu par le saut à 0.78.2 |
| `frontend/openapi.json`, `frontend/src/api/schema.d.ts` | Fichiers régénérés ; `make openapi` après merge tranche |
| `frontend/src/components/acquisition/FollowedPanel.tsx` | Touché par les deux si D3 change le code de réponse |

## Invariants non négociables (DESIGN, gelés)

- `event_bus` est un paramètre **REQUIS** sur tout site d'émission — jamais `| None`, jamais
  de défaut. Le défaut est précisément ce qui a produit D4.
- `SearchVerdict.found` n'est **jamais 0** sur un chemin non conclu (panne ≠ absence).
- Une action opérateur légitime ne répond **jamais 409** (§6) : elle s'exécute ou s'enfile
  visiblement ; seul refus permis = idempotence sur la même cible.
- La sonde saison est **bornée** : au plus une par `(followed_id, season)` et par passe.
- Les portes de DETECT restent **inchangées** — deux déclencheurs distincts coexistent.
- Aucun verdict de conformité sans `scripts/check-acquisition-coherence.py` à **exit 0**.
- Toute modification de route FastAPI ⇒ `make openapi` + fichiers régénérés commités.

## Phases

_(filled by /implement:plan)_

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.
