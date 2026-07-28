# Implementation Plan — plex-refresh

**Ticket**: #328 · **Design**: `docs/features/plex-refresh/DESIGN.md` · **Branch**: `feat/plex-refresh` · **Merge**: auto

## Phase table

| #   | Phase                                 | File                                     | Status |
| --- | ------------------------------------- | ---------------------------------------- | ------ |
| 1   | Client + subscriber + câblage + tests | [phase-01-engine.md](phase-01-engine.md) | [ ]    |
| 2   | Docs + env + ACC + preuve réelle      | [phase-02-acc.md](phase-02-acc.md)       | [ ]    |

## Invariants

Fail-soft absolu (un dispatch ne peut JAMAIS échouer à cause de Plex) ; token jamais loggé ;
event_bus requis partout ; un refresh par dossier dispatché.
