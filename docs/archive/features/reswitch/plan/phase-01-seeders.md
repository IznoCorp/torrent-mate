# Phase 01 — Seeders renforcés dans le score

## Gate

- `python -m pytest tests/tracker/test_ranking_seeders.py -q` vert.
- `make lint` vert (ruff + mypy).

## Sous-phases

### 1.1 — Test rouge-avant `tests/tracker/test_ranking_seeders.py`

Construire des `TrackerResult` identiques sauf `seeders`, ranker via `rank(results, ranking)`
avec la config réelle chargée, et asserter :

- À qualité égale (mêmes resolution/codec/format/audio/source), la release **100 seeds** sort
  strictement avant la **2 seeds**.
- Un écart de seeders (2 → 100) suffit à dépasser un écart de codec (x264 vs x265) mais **pas** un
  saut de résolution (720p vs 1080p) — la politique 1080p reste prioritaire.
- Une release 0-seed est écartée par `min_seeders`.

### 1.2 — Ajuster `config/ranking.json5` + `config.example/ranking.json5`

Critère `seeders` : `weight: 2`, seuils `0→0, 1→3, 5→8, 20→14, 50→18, 100→22`. `min_seeders: 1`
conservé. Contrainte : max seeders = 2×22 = 44 < résolution 4×20 = 80. Les deux fichiers
(runtime + example) restent alignés (`config/` est force-add, CI-safe : la CI ne charge pas la
vraie config). Aucun changement de code Python (moteur générique déjà pilotable par config).
