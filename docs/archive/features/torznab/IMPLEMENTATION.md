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
**Master plan**: `docs/features/torznab/plan/INDEX.md`

## Contexte

Torr9.net a fermé — ordre opérateur 2026-07-28 : « Tu peux retirer Torr9 on va le
remplacer par Tr4ker ». Coupure immédiate déjà en place (commit `fix(torznab):
disable the closed torr9 tracker`). c411.py est déjà un client Torznab — il devient
la base d'un générique dont Tr4ker est la seconde config. Objectif durable : ajouter
un tracker Torznab = config + doc, zéro code.

Auth Tr4ker : `TR4KER_PASSKEY` unique (convention opérateur 2026-07-28), valeur envoyée
en `apikey=` sur `/api/torznab` ; servira aussi au RSS. Le brut `docs/tr4ker.md` contient la passkey réelle en clair —
le distillé n'en reprend aucune trace, le brut est supprimé en fin de feature.

## Phases

| #   | Phase                                   | File                                                               | Status |
| --- | --------------------------------------- | ------------------------------------------------------------------ | ------ |
| 1   | Generic Torznab extrait de C411 (pinné) | [phase-01](docs/features/torznab/plan/phase-01-generic-torznab.md) | [x]    |
| 2   | Client Tr4ker + activation + config     | [phase-02](docs/features/torznab/plan/phase-02-tr4ker.md)          | [x]    |
| 3   | Retrait torr9 (code, tests, activation) | [phase-03](docs/features/torznab/plan/phase-03-remove-torr9.md)    | [x]    |
| 4   | Docs + .env.example                     | [phase-04](docs/features/torznab/plan/phase-04-docs-env.md)        | [x]    |
| 5   | Vérification réelle + ACC + gate finale | [phase-05](docs/features/torznab/plan/phase-05-verify-acc.md)      | [x]    |

## ACC — vérification exécutée (2026-07-28)

| ID     | Verdict | Preuve                                                                                                                                                                                                                                                                                                 |
| ------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ACC-01 | ✅      | tests c411 inchangés verts (pin phase 1, diff vide) ; dé-pin documenté d'UN champ (tmdb_id, 3b)                                                                                                                                                                                                        |
| ACC-02 | ✅      | grep torr9 : 0 dans personalscraper/ ; 3 hits assumés dans test_removed_tracker_history.py (protège les lignes réelles de la base)                                                                                                                                                                     |
| ACC-03 | ⏸ défér | Sonde réelle 12:13 : /api/torznab ET /api ET /api/torznab/all → 401 HTML identique ⇒ chemin OK, **passkey refusée comme apikey** (l'avertissement du doc amont). Remède demandé à l'opérateur : clé API du profil dans TR4KER_PASSKEY. Re-sonde avant merge ; sinon enabled:false + protocole différé. |
| ACC-04 | ✅      | grep passkey réelle sur docs/ + .env.example : 0                                                                                                                                                                                                                                                       |
| ACC-05 | ✅      | delta noms de clés .env → .env.example : vide ; TORR9_* deprecated                                                                                                                                                                                                                                     |
| ACC-06 | ✅      | brut supprimé (backup scratchpad session) ; tr4ker-api.md présent + indexé CLAUDE.md                                                                                                                                                                                                                   |
| ACC-07 | ✅      | make check : 9293 passed, 0 ERROR, ruff/mypy clean                                                                                                                                                                                                                                                     |

## Review cycles

_(filled by implement:pr-review)_

## Next action

feature-pr : push + PR + CI, re-sonde ACC-03 avant merge.
