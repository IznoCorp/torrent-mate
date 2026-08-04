# Implementation Progress — acq-escalade

> For Claude: read this file at session start. Current feature tracker.

**Feature**: L'acquisition escalade vers le pack saison quand la recherche épisode échoue
**Type**: fix
**Version bump**: 0.78.0 → 0.78.2 (bugfix)
**Branch**: fix/acq-escalade
**PR merge**: auto — standing operator contract: adversarial review(s) + tests before merge.
**PR**: _(created after last phase)_
**Design**: docs/features/acq-escalade/DESIGN.md
**Master plan**: docs/features/acq-escalade/plan/INDEX.md

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

| #   | Phase                                                    | File                                     | Défaut | Status |
| --- | -------------------------------------------------------- | ---------------------------------------- | ------ | ------ |
| 1   | Propager le bus du processus dans le scan post-dispatch   | phase-01-event-bus-propagation.md        | D4     | [ ]    |
| 2   | `trackers_degraded` — une panne n'est pas une absence     | phase-02-trackers-degraded.md            | D2     | [ ]    |
| 3   | Escalade épisode→saison sur l'évidence d'échec            | phase-03-starvation-escalation.md        | D1     | [ ]    |
| 4   | Extraction de la route season-grab (comportement constant)| phase-04-extract-season-grab-route.md    | —      | [ ]    |
| 5   | L'action opérateur déclenche la passe                     | phase-05-operator-trigger.md             | D3     | [ ]    |

L'ordre porte du sens : D4 masque l'effet observable de tout le reste ; D2 change la sémantique
d'`attempts` dont dépend D1 ; l'extraction dégage la marge que D3 exige sous le plafond de 1000.

## Point ouvert (décision opérateur en attente)

La phase 2 rembourse l'essai **uniquement** sur `trackers_degraded`. Les autres verdicts non
conclus (`trackers_unavailable`, `circuit_open`, `search_api_error`) continuent de consommer un
essai — comportement préexistant, non modifié faute d'arbitrage. Conséquence : après la phase 2,
`attempts` signifie « recherches conclues + recherches en panne totale ». Étendre le
remboursement à toute la famille panne rendrait le compteur exact, mais c'est un changement de
comportement supplémentaire qui n'a pas été validé.

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.
