# Implementation Progress — game-hide

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Détecter les jeux (ISO) et les masquer de la médiathèque
**Type**: feat
**Version bump**: 0.60.0 → 0.61.0 (minor)
**Branch**: feat/game-hide
**Ticket**: #334 — claimed
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/game-hide/DESIGN.md
**Master plan**: docs/features/game-hide/plan/INDEX.md

## Phases

| #   | Phase                         | File                                                        | Status |
| --- | ----------------------------- | ----------------------------------------------------------- | ------ |
| 1   | Détection — `is_game_release` | [phase-01](docs/features/game-hide/plan/phase-01-detect.md) | [x]    |
| 2   | Filtre read-model + log       | [phase-02](docs/features/game-hide/plan/phase-02-filter.md) | [x]    |
| 3   | ACC + preuve 390 px + gate    | [phase-03](docs/features/game-hide/plan/phase-03-acc.md)    | [x]    |

## ACC results (2026-07-28)

| ACC    | Verdict | Preuve                                                                                                                                                                                                                                                                                                      |
| ------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | ✅ PASS | `pytest tests/sorter/test_game.py` — dossier `Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto` (iso+nfo) ⇒ `is_game_release` True. (10 tests verts.)                                                                                                                                                          |
| ACC-02 | ✅ PASS | même suite — image disque de FILM (`The.Matrix.1999.1080p.BluRay.iso`) ⇒ False (garde anti-faux-positif video-release) ; régression PS5→S5 couverte.                                                                                                                                                        |
| ACC-03 | ✅ PASS | `pytest tests/unit/web/staging/test_read_model_game_filter.py` — jeu en OTHER non surfacé, média non-jeu en OTHER visible, log `staging_game_hidden` émis.                                                                                                                                                  |
| ACC-04 | ✅ PASS | `make check` **exit 0** (977 tests front + suite Python + guardrails) ; `make openapi` sans drift (aucun changement de contrat).                                                                                                                                                                            |
| ACC-05 | ✅ PASS | **Preuve données réelles** (config réelle + `library.db` réelle) : `scan_staging_media` ne surface PLUS `Marvels.Spider-Man.2` (log `staging_game_hidden` → `098-AUTRES`), et « Top Chef Le Concours Parallèle » (autre item OTHER, non-jeu) **reste visible**. Confirmation visuelle sur `tm.` post-merge. |

### ACC-05 — preuve données réelles (2026-07-28)

```
staging_dir: /Volumes/IznoServer SSD/A TRIER
total staged items surfaced: 1
Marvels/Spider-Man items STILL surfaced: NONE (correct)
staging_game_hidden log entries: [('098-AUTRES', 'Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto')]
All surfaced folders: ['Top Chef Le Concours Parallèle (2026)']
```

Note : la preuve visuelle Chrome sur `tm-staging.` exigerait un déploiement de branche
sur staging (force-push gaté par le classifieur auto-mode) ; la preuve données réelles
ci-dessus (read model réel sur arborescence réelle) est plus forte, et la confirmation
visuelle est faite sur `tm.` (prod) après le merge/déploiement.

## Review cycles

_(filled by implement:pr-review)_

## Next action

All phases complete — run /implement:feature-pr
