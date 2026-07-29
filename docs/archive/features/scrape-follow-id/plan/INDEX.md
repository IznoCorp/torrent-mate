# Implementation Plan — scrape-follow-id

**Ticket**: #338 · **Design**: `docs/features/scrape-follow-id/DESIGN.md` · **Branch**: `feat/scrape-follow-id` · **Merge**: auto

## Phase table

| #   | Phase                             | File                                         | Status |
| --- | --------------------------------- | -------------------------------------------- | ------ |
| 1   | Résolveur `resolve_followed_tvdb` | [phase-01-resolver.md](phase-01-resolver.md) | [ ]    |
| 2   | Injection orchestrateur + wiring  | [phase-02-inject.md](phase-02-inject.md)     | [ ]    |
| 3   | ACC + gate                        | [phase-03-acc.md](phase-03-acc.md)           | [ ]    |

## Invariants

TVDB reste primaire · le résolveur ne force QUE si un seul tvdb du suivi recouvre le dossier ET la
garde titre passe (anti-collision) · fail-soft (exception → None → match libre) · rétro-compat
(sans résolveur, comportement inchangé) · films hors périmètre.
