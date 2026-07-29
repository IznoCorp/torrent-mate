# Phase 03 — Mémoire des hashes tentés + exclusion au ranking

## Gate

- `python -m pytest tests/acquire/ tests/tracker/ -q` vert.
- `make lint` vert. Migration appliquée (colonne présente sur une DB neuve).

## Sous-phases

### 3.1 — Colonne `tried_hashes_json` sur `wanted` + store

- Migration idempotente (ajouter la colonne `tried_hashes_json TEXT` — défaut `'[]'`/`NULL`) selon
  le mécanisme de migration acquire/indexer en place (fail-soft, staging skip).
- `acquire/domain.py` : exposer `tried_hashes: tuple[str, ...]` sur le modèle `WantedItem`
  (décodé du JSON). NFC/casse : les hashes sont hex lowercase, pas de normalisation Unicode requise.
- Store (`acquire/_wanted_store.py`) : `append_tried_hash(id, info_hash)` (idempotent : pas de
  doublon) + `list_tried_hashes(id) -> tuple[str, ...]`.
- Le requeue (`requeue_missing` et le requeue de rebascule) **conserve** `tried_hashes` (ne le vide
  jamais lors d'un clear de `grabbed_hash`). Un requeue « propre » (nouvelle recherche voulue par
  l'opérateur) peut le vider — décision explicite, testée.
- Test round-trip : append × N (dont doublon) → list dédupliqué et ordonné.

### 3.2 — Paramètre `exclude_hashes` sur `rank` / `rank_candidates`

- `api/tracker/_ranking.py:rank` : signature `rank(results, ranking, *, exclude_hashes:
frozenset[str] = frozenset())` — écarte tout `r.info_hash in exclude_hashes` avant le tri
  (comparaison lowercase). Défaut vide = comportement inchangé.
- `acquire/orchestrator.py:rank_candidates` : propager `exclude_hashes` jusqu'à `rank`.
- Chemin grab (`GrabOrchestrator` / `_grab_pass`) : passer `list_tried_hashes(item.id)` en
  exclusion lors de la recherche/ranking d'un item.
- Tests : un hash exclu n'apparaît jamais dans le résultat ; rétro-compat (défaut vide) ; le grab
  d'un item ayant des `tried_hashes` choisit une AUTRE release.
