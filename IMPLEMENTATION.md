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

### Cycle 1 — adversarial `code-reviewer` (PR #337, 2026-07-29)

**Verdict : chemin create airtight sur tous les invariants durs ; 1 HIGH trouvé** (bon catch).

- **HIGH — suivi silencieusement inerte à la réactivation/reprise.** `tvdb_unresolved` n'était
  posé qu'à la création ; réactiver (POST re-match) ou reprendre (toggle PATCH `active=true`) une
  série sans TVDB la remettait active **sans** résolution **ni** drapeau → l'opérateur croit que
  ça marche alors que `poll_known` la saute. **Corrigé** (commit `7758ab56`) : `tvdb_unresolved`
  est désormais **dérivé de l'état** (`show ∧ active ∧ pas de tvdb_id`) dans les DEUX builders —
  create, réactivation, toggle ET liste sont honnêtes ; badge persistant « Sans ID TVDB » côté
  front. Tests ajoutés (dérivation + badge + toast).

**Items ouverts (présentés, décision opérateur — non tranchés unilatéralement) :**

- **(LOW-MED, perf)** L'ajout-par-ID d'une série construit le registry **deux fois** (une fois pour
  la résolution TVDB, une fois pour l'enrichissement métadonnées). Coût réel ≈ un build de registry
  en plus (~80 ms) ; le pire-cas ~50 s n'arrive que si **deux** hôtes providers pendent (même risque
  que le chemin métadonnées existant). Fusionner les deux dans un seul `scoped_provider_clients`
  l'éliminerait. Non fait (borné, action peu fréquente) — à arbitrer.
- **(ENHANCEMENT)** La réactivation ne **re-résout** pas le TVDB (elle le signale seulement via le
  drapeau dérivé). Une panne provider transitoire à la création reste inerte jusqu'à un ré-ajout
  explicite. Auto-recovery possible (re-résoudre + mettre à jour le media_ref stocké au moment de
  la réactivation) — à arbitrer.

## Next action

All phases complete — run /implement:feature-pr
