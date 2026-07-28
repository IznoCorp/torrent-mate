# Implementation Progress — episode-states

> For Claude: read this file at session start.

**Feature**: Statut « Annoncé » (épisodes futurs) + légende couleurs + date au clic
**Type**: feat · **Version bump**: 0.59.1 → 0.60.0 (minor) · **Branch**: feat/episode-states
**Ticket**: #332 — claimed · **PR merge**: auto
**Design**: docs/features/episode-states/DESIGN.md · **Master plan**: docs/features/episode-states/plan/INDEX.md

## Contexte

Tâches opérateur #9 (légende couleurs des puces) + #10 (statut « Annoncé » = épisodes futurs
connus, avec date de diffusion, affichée au clic) — groupées (même zone, la légende doit
inclure Annoncé). Décisions opérateur : tous les futurs connus (pas la saison courante seule) ;
1 couleur/statut ; date au clic sur chaque puce. Invariant : le cache stocke les futurs mais
la file wanted ne prend que les diffusés (un futur n'est pas cherchable).

## Phases

| #   | Phase                                   | File                                                              | Status |
| --- | --------------------------------------- | ----------------------------------------------------------------- | ------ |
| 1   | Backend — cache élargi + état `annonce` | [phase-01](docs/features/episode-states/plan/phase-01-backend.md) | [x]    |
| 2   | UI — statut, légende, date au clic      | [phase-02](docs/features/episode-states/plan/phase-02-ui.md)      | [x]    |
| 3   | ACC + preuve 390 px + gate              | [phase-03](docs/features/episode-states/plan/phase-03-acc.md)     | [x]    |

## ACC results (2026-07-28)

| ACC    | Verdict | Preuve                                                                                                                                                                                                       |
| ------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ACC-01 | ✅ PASS | `pytest tests/acquire/test_airing.py tests/acquire/test_detect_service.py` — futur → cache, jamais `wanted`.                                                                                                  |
| ACC-02 | ✅ PASS | `pytest tests/unit/web/acquisition/test_annonce_state.py` — `derive_episode_state(air_date>today)` ⇒ `annonce` (rouge-avant vérifié).                                                                          |
| ACC-03 | ✅ PASS | `pytest tests/unit/web/acquisition/test_truth.py test_completeness.py` — futur n'entre pas dans le tally ; carte reste « À jour ».                                                                             |
| ACC-04 | ✅ PASS | spy dans `test_detect_service.py` — `poll_known` appelé **une** fois par série. (78 tests backend verts au total.)                                                                                            |
| ACC-05 | ✅ PASS | Preuve Chrome 390 px sur staging (Furious S01, E1-3 diffusés + E4-8 annoncés 03→31/08) : légende 6 tons distincts dérivée de meta.ts, `annonce` violet, `scrollWidth-innerWidth==0`, popover date non clippé. |
| ACC-06 | ✅ PASS | `make openapi` sans drift (`annonce` + `announced` dans schema.d.ts) ; `make check` vert ; front lint+typecheck+vitest (157) verts.                                                                           |

### ACC-05 — preuve 390 px (staging, 2026-07-28)

Série suivie **Furious** (TVDB), saison 1 : E1-E3 diffusés (≤ aujourd'hui), E4-E8
annoncés (`air_date` 2026-08-03 → 2026-08-31) après `detect --series` sur le binaire
staging. API `completeness` : `{"season":1,"announced":5,"total":3,"owned":3}`.

Harnais iframe 390 px (viewport Chrome épinglé 1440) :

- `overflowX == 0` (aucun scroll horizontal).
- Légende présente, **6 libellés** : « En médiathèque / À récupérer / En cours /
  En attente / Non vérifié / **Annoncé** », 6 couleurs distinctes (violet `--upcoming`
  pour Annoncé, pointillé `muted` pour Non vérifié) — lisibles en clair et sombre.
- `aria-label` corrects : E1-3 « En médiathèque », E4-8 « Annoncé ».
- Popover date (portalisé, non clippé) : clic E1 ⇒ « Diffusé le 27 juillet 2026 » ;
  clic E4 ⇒ « Sortie prévue le 3 août 2026 » (français long, jamais le jeton ISO).

## Next action

All phases complete — run /implement:feature-pr
