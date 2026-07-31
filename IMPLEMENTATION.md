# Implementation Progress — plex-env

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Scan Plex après dispatch — .env canonique (crons deploy) + règles constitution v3
**Type**: fix
**Version bump**: 0.65.1 → 0.65.2 (patch)
**Branch**: fix/plex-env
**Ticket**: #346 — claimed
**PR merge**: auto

## Root cause (#26 / #22 / #25 Plex)

Les crons pipeline/dispatch tournent le checkout **deploy** (`~/deploy/torrentmate`), dont le
`.env` n'a **pas** `PLEX_TOKEN` (le `.env` dev l'a). `Settings` chargeait le `.env` de la racine du
checkout courant → token vide → `build_plex_subscriber` renvoie `None`
(`plex_refresh_disabled reason=no_token`) → **aucun scan Plex après dispatch** → média acquis +
dispatché + indexé mais **invisible dans Plex** (Supergirl, Rooster…).

## Fix

- **`personalscraper/config.py`** : `Settings` charge désormais un **overlay** de `.env` —
  `_resolve_env_files()` : le `.env` **canonique** (à côté du `config/` que le clone pointe déjà via
  `PERSONALSCRAPER_CONFIG`, ou `PERSONALSCRAPER_ENV_FILE` explicite) est chargé **sous** le `.env`
  local. Le local **gagne** sur toute clé qu'il définit (deploy/staging gardent leurs secrets), le
  canonique **comble** seulement les clés manquantes (le trou `PLEX_TOKEN`). Rétro-compat totale : sans
  `PERSONALSCRAPER_CONFIG`, ou quand canonique == local (checkout dev), un seul `.env` (comportement
  historique). Zéro changement PM2 (réutilise `PERSONALSCRAPER_CONFIG` déjà positionné sur les crons).
- **Constitution v3** (`docs/reference/product-intent.md`) : §4 « la chaîne va jusqu'à la visibilité
  Plex » (acquisition→pipeline→dispatch→scan Plex ; acquis mais invisible = dénaturation §4) + §5
  « identité conservée » (récup via acquisition garde l'ID du suivi pour le scraping).

## #25 (Rooster / IDs) — état

IDs vérifiés **propres** (library.db item unique tvdb 457770 = suivi). « Garder l'ID au scraping »
déjà en place (#16 scrape-follow-id). Le bug Plex de Rooster = ce root cause (token absent).

## Gate

- `make check` vert + `make openapi` sans dérive (pas de modèle web).
- Post-merge : vérifier `plex_refresh` plus jamais `disabled` sur un run cron ; re-déclencher un scan
  pour les médias déjà invisibles (Supergirl / Rooster).

## Next action

feature-pr (push + PR + CI), review adversariale, merge squash, déploiement prod, vérif Plex, clôture #346.
