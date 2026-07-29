# Phase 02 — Injection orchestrateur + wiring composition

**Goal**: le scrape d'un dossier suivi appelle `scrape_tvshow_forced(tvdb, id_du_suivi)` au lieu
du match libre ; rétro-compat sans résolveur.

## Surface

| Fichier                                                                                                   | Action                                                                                                                                                                                                                                                                                                                                   |
| --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `personalscraper/scraper/orchestrator.py`                                                                 | `Scraper.__init__` gagne `follow_tvdb_resolver: Callable[[Path], int                                                                                                                                                                                                                                                                     | None] | None = None`(défaut None ⇒ inchangé). Dans la boucle de scrape, AVANT`self.scrape_tvshow(show_dir)`:`forced = resolver(show_dir) if resolver else None`; si`forced is not None`→`self.scrape_tvshow_forced(show_dir, "tvdb", forced)`, sinon `scrape_tvshow`. Fail-soft (exception résolveur → log + None). |
| composition pipeline (là où `Scraper` + `AcquireStore` sont construits — `process/run.py` ou le boundary) | Construire le résolveur : lit `store.wanted.list_grabbed()` + les titres des suivis, appelle `resolve_followed_tvdb`. Passe le callable à `Scraper(follow_tvdb_resolver=…)`. Ne pas coupler le scraper au store directement (le callable encapsule l'accès).                                                                             |
| `personalscraper/acquire/store.py`                                                                        | Si absent : un lecteur `list_grabbed()` (déjà utilisé par le reconcile) + un accès aux titres de suivis (`follow.list`/`get`). Réutiliser l'existant.                                                                                                                                                                                    |
| tests                                                                                                     | ACC-04 : Scraper avec un résolveur stub renvoyant un id ⇒ `scrape_tvshow_forced` appelé (spy) ; stub renvoyant None ⇒ `scrape_tvshow` appelé ; **sans** résolveur (None) ⇒ `scrape_tvshow` (rétro-compat). Wiring : le callable construit interroge le store et rend le bon id (test d'intégration léger avec un store en mémoire/temp). |

## Règles

- **Rétro-compatible** : `follow_tvdb_resolver=None` par défaut ⇒ comportement strictement inchangé
  (tous les tests scraper existants passent).
- Le scraper ne connaît PAS le store ni les wanted — il reçoit un `Callable[[Path], int | None]`.
- Fail-soft de bout en bout : un résolveur qui lève ⇒ match libre (jamais bloquer le scrape).

## Gate

`make check` vert ; aucune régression des tests scraper/process existants ; `mypy` sur l'orchestrateur.
