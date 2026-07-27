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
**Master plan**: _(to be defined after /implement:plan)_

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

_(filled by /implement:plan)_

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:plan` to generate the phase plan from the design doc.
