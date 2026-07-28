# Phase 01 — M9 : hash d'intention pré-add (D2)

**Goal**: fermer la fenêtre add()→mark_grabbed — plus jamais de torrent orphelin dans
qBittorrent sans obligation de seed. Les docstrings « PR #320 review, M9 — OPEN » tombent.

## Surface

| Fichier                                                                                                      | Action                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/acquire/service.py` (`_process_item`/`_persist_success` — retrouver par `rg -n "M9" -t py`) | persister le hash choisi AVANT `add()` (ligne encore `searching`) ; confirmation par `mark_grabbed` après                                                                                         |
| `personalscraper/acquire/_wanted_store.py`                                                                   | méthode d'écriture du hash d'intention (UPDATE grabbed_hash WHERE id AND status='searching') + nettoyage (hash→NULL)                                                                              |
| `personalscraper/acquire/reconcile.py` + la reprise stale                                                    | une ligne `searching`+hash : le torrent est dans le client ⇒ confirmer grabbed + obligation ; absent ⇒ NULL le hash, re-cherchable                                                                |
| `personalscraper/acquire/domain.py`                                                                          | docstring grabbed_hash réécrite (la garantie devient vraie)                                                                                                                                       |
| tests                                                                                                        | rouge-avant : crash simulé entre add et mark_grabbed ⇒ le run suivant confirme + enregistre l'obligation, zéro orphelin ; §11d exactly-once re-testé ; reprise « torrent absent » nettoie le hash |

## Règles

- L'ordre verdict-avant-statut de #320 est conservé.
- `reclaim_stale_searching` (grabbed_hash IS NULL) reste correct : une ligne hash+searching
  n'est PAS reclaimable — c'est la reprise réconciliatrice qui la traite. Vérifier que les
  deux passes la routent bien vers la réconciliation et pas vers un skip perpétuel.

## Gate

pytest tests/acquire/ -q vert ; mypy 0 ; rouge-avant vérifié ; `rg -n "M9" -t py personalscraper/` ⇒ 0.
