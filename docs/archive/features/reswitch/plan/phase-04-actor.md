# Phase 04 — Acteur de rebascule `reswitch_stalled`

## Gate

- `python -m pytest tests/acquire/test_reswitch.py -q` vert.
- `make lint` vert.

## Sous-phases

### 4.1 — Passe `reswitch_stalled`

Nouveau `acquire/_reswitch.py` : `reswitch_stalled(store, client, config, now, *, event_bus)`.

Pour chaque item `grabbed` avec `grabbed_hash` :

- Lire l'état via `client.get_by_hashes([hash])` ; calculer `grabbed_age_s` depuis `enqueued_at`/
  le timestamp de grab disponible.
- `classify_stall(...)` :
  - `STALLED_DEAD` : 1) `append_tried_hash(id, hash)`, 2) `client.delete(hash)` (retirer le torrent
    mort ; fail-soft si absent), 3) requeue de rebascule (clear `grabbed_hash`, statut → `pending`,
    `tried_hashes` conservé), 4) émettre `GrabReswitched(media_ref, old_hash, reason)`
    (event_bus **requis**, jamais optionnel — cf. contrat de signature event_bus).
  - sinon : ne rien faire (healthy/recoverable laissés tranquilles).
- Idempotence + fail-soft : un hash déjà tenté n'est pas re-traité en boucle.

Test rouge-avant `tests/acquire/test_reswitch.py` : stalled_dead ⇒ requeue + hash mémorisé + delete
appelé + `GrabReswitched` émis ; healthy ⇒ aucun effet ; client indisponible ⇒ no-op fail-soft.

### 4.2 — Câblage cadence + garde-fou honnête

- Invoquer `reswitch_stalled` dans la cadence acquisition (là où `reconcile` tourne — même passe
  regulière), après `reconcile` (absence) et avant/around le grab pass.
- Garde-fou §méthode : quand la passe grab suivante ne trouve **plus aucune** release non exclue,
  l'item passe `en_attente` avec `last_search_outcome` explicite (« toutes les sources tentées ont
  échoué ») — jamais un item bloqué qui prétend « en cours ».
- Test d'intégration : deux releases ; la 1re grabée stalle (dead) ⇒ rebascule ⇒ la 2e est grabée ;
  si la 2e stalle aussi ⇒ `en_attente` honnête (raison), plus de re-grab de la 1re (exclue).
