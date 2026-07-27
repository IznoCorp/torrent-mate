# Implementation Progress — acq-states

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Acquisitions — états véridiques (disponibilité tracker) + amorce du suivi + poster serveur
**Type**: feat
**Version bump**: 0.54.1 → 0.55.0 (minor)
**Branch**: feat/acq-states
**Ticket**: #319 — claimed (session locale, heartbeat actif)
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/acq-states/DESIGN.md
**Master plan**: `docs/features/acq-states/plan/INDEX.md`

## Contexte

Incident fondateur : la série _Furious_ (TVDB 468000), ajoutée le 2026-07-27, affichait
« À jour » avec 3 épisodes diffusés absents de la médiathèque, et sans poster.

Trois causes racines établies avec preuves (détail dans le DESIGN) :

- **RC1** — `POST /followed` n'amorce ni catalogue ni file `wanted` ; seul le cron `detect`
  de 03:00 le fait → le « Rechercher » manuel est un succès silencieux.
- **RC2** — la carte et le panneau de détail lisent **deux sources divergentes** : cache vide
  → « À jour » côté carte, repli `poll_aired` live → 3 épisodes `manquant` côté détail.
- **RC3** — aucun enrichissement serveur du poster ; il ne vient que du candidat de recherche
  envoyé par le client, donc jamais par le formulaire d'ajout par ID.

L'incident lui-même a été résolu manuellement le 2026-07-27 (`detect` + `grab` + pipeline 264) :
les 3 épisodes sont en médiathèque. Cette feature corrige les causes, pas le symptôme.

## Décisions opérateur (2026-07-27)

| Sujet             | Décision                                                                               |
| ----------------- | -------------------------------------------------------------------------------------- |
| Modèle d'états    | 5 états — À jour / En attente / À récupérer / En cours d'acquisition / **Non vérifié** |
| « Disponible »    | = **candidat réellement prenable** (survit aux filtres éliminatoires)                  |
| Persistance       | colonnes sur `wanted` (`last_search_outcome`, `last_search_found`)                     |
| Amorce            | 201 immédiat + run d'amorce **visible** via l'autorité de déclenchement existante      |
| Fichier `VERSION` | **supprimé** — mort et désynchronisé (0.48.0 vs 0.54.1 réel)                           |
| Merge             | auto                                                                                   |

## Phases

| #   | Phase                                    | File                                                                                               | Status |
| --- | ---------------------------------------- | -------------------------------------------------------------------------------------------------- | ------ |
| 1   | Socle de persistance (migration + store) | [phase-01-persistence.md](docs/features/acq-states/plan/phase-01-persistence.md)                   | [ ]    |
| 2   | Le moteur enregistre son verdict         | [phase-02-orchestrator-verdict.md](docs/features/acq-states/plan/phase-02-orchestrator-verdict.md) | [ ]    |
| 3   | Dérivation serveur des 5 états           | [phase-03-state-derivation.md](docs/features/acq-states/plan/phase-03-state-derivation.md)         | [ ]    |
| 4   | Fin des sources divergentes              | [phase-04-single-source.md](docs/features/acq-states/plan/phase-04-single-source.md)               | [ ]    |
| 5   | Amorce à la création du suivi            | [phase-05-follow-priming.md](docs/features/acq-states/plan/phase-05-follow-priming.md)             | [ ]    |
| 6   | Enrichissement serveur des métadonnées   | [phase-06-server-metadata.md](docs/features/acq-states/plan/phase-06-server-metadata.md)           | [ ]    |
| 7   | UI — les 5 états en français             | [phase-07-ui-states.md](docs/features/acq-states/plan/phase-07-ui-states.md)                       | [ ]    |
| 8   | Garde-fous et acceptation                | [phase-08-guardrails-acc.md](docs/features/acq-states/plan/phase-08-guardrails-acc.md)             | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start phase 1.
