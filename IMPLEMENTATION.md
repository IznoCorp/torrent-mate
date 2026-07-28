# Implementation Progress — torznab

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Retrait Torr9, base Generic Torznab, tracker Tr4ker
**Type**: feat
**Version bump**: 0.56.1 → 0.57.0 (minor)
**Branch**: feat/torznab
**Ticket**: #321 — claimed (session locale, heartbeat actif)
**PR merge**: auto (assomption — même mode que acq-states ; l'opérateur peut basculer manual)
**PR**: _(created after last phase)_
**Design**: docs/features/torznab/DESIGN.md
**Master plan**: _(to be defined after /implement:plan)_

## Contexte

Torr9.net a fermé — ordre opérateur 2026-07-28 : « Tu peux retirer Torr9 on va le
remplacer par Tr4ker ». Coupure immédiate déjà en place (commit `fix(torznab):
disable the closed torr9 tracker`). c411.py est déjà un client Torznab — il devient
la base d'un générique dont Tr4ker est la seconde config. Objectif durable : ajouter
un tracker Torznab = config + doc, zéro code.

Auth Tr4ker : `TR4KER_API_KEY` (recherche `/api/torznab`) + `TR4KER_PASSKEY`
optionnelle (RSS). Le brut `docs/tr4ker.md` contient la passkey réelle en clair —
le distillé n'en reprend aucune trace, le brut est supprimé en fin de feature.

## Phases

_(filled by /implement:plan)_

## Review cycles

_(filled by implement:pr-review)_

## Next action

Run `/implement:plan`.
