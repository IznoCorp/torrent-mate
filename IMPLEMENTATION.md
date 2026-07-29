# Implementation Progress — scrape-follow-id

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Au scrape d'une série suivie, réutiliser l'ID TVDB du suivi (anti-split)
**Type**: fix
**Version bump**: 0.62.0 → 0.63.0 (minor)
**Branch**: feat/scrape-follow-id
**Ticket**: #338 — claimed
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/scrape-follow-id/DESIGN.md
**Master plan**: docs/features/scrape-follow-id/plan/INDEX.md

## Phases

| #   | Phase                             | File                                                                 | Status |
| --- | --------------------------------- | -------------------------------------------------------------------- | ------ |
| 1   | Résolveur `resolve_followed_tvdb` | [phase-01](docs/features/scrape-follow-id/plan/phase-01-resolver.md) | [x]    |
| 2   | Injection orchestrateur + wiring  | [phase-02](docs/features/scrape-follow-id/plan/phase-02-inject.md)   | [x]    |
| 3   | ACC + gate                        | [phase-03](docs/features/scrape-follow-id/plan/phase-03-acc.md)      | [x]    |

## ACC results (2026-07-29)

| ACC    | Verdict | Preuve                                                                                                                                                                           |
| ------ | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | ✅ PASS | `pytest tests/scraper/test_resolve_followed_tvdb.py` — Rooster S01E06-E10 grabbed tvdb 457770 titre « Rooster » ⇒ renvoie 457770.                                                |
| ACC-02 | ✅ PASS | même suite — deux suivis partageant S01E06 ⇒ None ; titre dissemblable ⇒ None (garde anti-collision).                                                                            |
| ACC-03 | ✅ PASS | même suite — grabbed vide / pas d'épisode / grabbed sans tvdb ⇒ None (fail-soft, jamais d'exception).                                                                            |
| ACC-04 | ✅ PASS | `pytest tests/scraper/test_scrape_follow_injection.py` — résolveur→id ⇒ `scrape_tvshow_forced('tvdb', id)` ; None/absent/exception ⇒ `scrape_tvshow` (rétro-compat + fail-soft). |
| ACC-05 | ✅ PASS | `make check` **exit 0** (9531 back + 992 front) ; `make openapi` sans dérive (aucun changement de contrat web). 947 tests scraper existants verts (rétro-compat).                |

## Review cycles

_(filled by implement:pr-review)_

## Next action

All phases complete — run /implement:feature-pr
