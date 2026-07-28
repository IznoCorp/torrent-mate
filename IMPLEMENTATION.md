# Implementation Progress — follow-by-id

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Suivre par ID IMDB et TMDB (résolution TVDB pour les séries)
**Type**: feat
**Version bump**: 0.61.0 → 0.62.0 (minor)
**Branch**: feat/follow-by-id
**Ticket**: #336 — claimed
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/follow-by-id/DESIGN.md
**Master plan**: docs/features/follow-by-id/plan/INDEX.md

## Phases

| #   | Phase                            | File                                                             | Status |
| --- | -------------------------------- | ---------------------------------------------------------------- | ------ |
| 1   | Backend — résolution TVDB séries | [phase-01](docs/features/follow-by-id/plan/phase-01-backend.md)  | [x]    |
| 2   | Frontend — sélecteur de provider | [phase-02](docs/features/follow-by-id/plan/phase-02-frontend.md) | [x]    |
| 3   | ACC + preuve 390 px + gate       | [phase-03](docs/features/follow-by-id/plan/phase-03-acc.md)      | [x]    |

## ACC results (2026-07-29)

| ACC    | Verdict | Preuve                                                                                                                                                                                          |
| ------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | ✅ PASS | `pytest tests/unit/test_tmdb_client.py::TestFindByImdb ::TestGetTvdbId` — `find_by_imdb` + `get_tvdb_id` (transport mock).                                                                      |
| ACC-02 | ✅ PASS | `pytest tests/unit/web/acquisition/test_follow_resolve_tvdb.py` — résolution tmdb→tvdb et imdb→find→tvdb. **+ Preuve données réelles live TMDB** (voir ci-dessous).                             |
| ACC-03 | ✅ PASS | `pytest tests/e2e/test_acquisition.py::TestFollowByIdTvdbResolution::test_series_unresolved_is_flagged_not_silent` — non résolu ⇒ suivi créé + `tvdb_unresolved=true`.                          |
| ACC-04 | ✅ PASS | même suite — film par tmdb ⇒ aucune résolution (scope non entré), `tvdb_unresolved=false`.                                                                                                      |
| ACC-05 | ✅ PASS | `vitest` — `buildIdFollowBody` (mapping + validation IMDB) + tests sélecteur FollowedPanel (TMDB→tmdb_id, IMDB→imdb_id, IMDB mal formé désactive). Preuve visuelle Chrome sur `tm.` post-merge. |
| ACC-06 | ✅ PASS | `make check` **exit 0** (9514 back + 989 front) ; `make openapi` régénéré (`tvdb_unresolved`).                                                                                                  |

### ACC-02 — preuve données réelles (live TMDB, 2026-07-29)

Bug attrapé par cette preuve (que les mocks masquaient) : le parser TMDB ne garde que les
external ids **string**, or `tvdb_id` est un **entier** → jamais dans `MediaDetails.external_ids`.
Corrigé par `get_tvdb_id` (lecture brute de `/tv/{id}/external_ids`). Vérifié en live :

```
resolve via TMDB id 1399    -> TVDB 121361
resolve via IMDB tt0944947  -> TVDB 121361   (Game of Thrones — TVDB attendu 121361)
PASS
```

## Review cycles

_(filled by implement:pr-review)_

## Next action

All phases complete — run /implement:feature-pr
