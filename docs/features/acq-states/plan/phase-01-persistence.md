# Phase 01 — Socle de persistance (migration + store)

**Goal**: rendre stockable le **résultat** de la dernière recherche tracker sur chaque ligne
`wanted`. Aucun comportement visible ne change : c'est le socle des phases 2 et 3.

**Constitution servie**: §5 (états visibles), NE-DOIT-PAS-8 (la disponibilité se lit, elle ne se
redemande pas au tracker).

**Design**: `DESIGN.md` §4 D1.

## Surface

| Fichier                                                            | Action                                                     |
| ------------------------------------------------------------------ | ---------------------------------------------------------- |
| `personalscraper/acquire/migrations/008_wanted_search_outcome.sql` | **NEW** — deux colonnes sur `wanted`                       |
| `personalscraper/acquire/domain.py`                                | `WantedItem` porte les deux nouveaux champs                |
| `personalscraper/acquire/_wanted_store.py`                         | SELECT/INSERT étendus + `record_search_outcome()`          |
| `personalscraper/acquire/_store_rows.py`                           | mapping ligne → `WantedItem`                               |
| `tests/acquire/test_migrations.py`                                 | migration 008 appliquée, colonnes présentes, idempotence   |
| `tests/acquire/test_store.py`                                      | aller-retour des nouveaux champs + `record_search_outcome` |

## Sous-phases

### 1.1 — Migration 008

**Commit**: `feat(acq-states): add last_search_outcome + last_search_found to wanted`

```sql
-- 008_wanted_search_outcome.sql
-- Persist the VERDICT of the last tracker search per wanted item.
--
-- The engine already computes this verdict at every exit path of the grab
-- orchestrator (no_candidates / no_matching_episode / all_filtered /
-- trackers_unavailable / …) but discards it, so the UI could never tell
-- "searched, nothing takeable" from "never searched" — the ambiguity that let a
-- freshly-followed series read « À jour » with three aired episodes missing.
--
-- NULL on both columns = never searched → « Non vérifié ». This is the honest
-- default for every pre-existing row: we genuinely do not know.
ALTER TABLE wanted ADD COLUMN last_search_outcome TEXT;
ALTER TABLE wanted ADD COLUMN last_search_found   INTEGER;
```

`last_search_outcome` stocke l'issue **nommée**, pas un booléen : c'est ce qui permet de
distinguer une panne d'une absence (DESIGN §3.3) et de diagnostiquer sans relire les logs.
`last_search_found` compte les candidats **prenables** (survivants des filtres éliminatoires),
pas les résultats bruts.

**Rétro-compat** : conformément à la règle « pas de rétro-compat avant v1.x », aucun script de
migration de données. Les lignes existantes restent à `NULL` = « Non vérifié », ce qui est la
vérité.

### 1.2 — Domaine + store

**Commit**: `feat(acq-states): expose search outcome through the wanted store`

- `WantedItem` gagne `last_search_outcome: str | None` et `last_search_found: int | None`.
- Tous les SELECT de `_wanted_store.py` (`get`, `_list_wanted_by_status`, `mark_done_by_hash`)
  ajoutent les deux colonnes — **vérifier chaque requête**, une seule oubliée renvoie des
  `WantedItem` incohérents selon le chemin de lecture.
- Nouvelle méthode :

```python
def record_search_outcome(self, wanted_id: int, outcome: str, found: int) -> None:
    """Persist the verdict of the search that just ran for this item.

    Called once per search attempt by the grab orchestrator, at every exit
    path — including the failure paths. A path that forgets to call this
    leaves the item reading « Non vérifié » forever, which is a lie by
    omission of exactly the kind this feature exists to remove.

    Args:
        wanted_id: The wanted row that was searched.
        outcome: The orchestrator's named outcome (``no_candidates``,
            ``all_filtered``, ``trackers_unavailable``, ``grabbed``, …).
        found: Number of TAKEABLE candidates — survivors of the exact-episode
            filter, the hard profile filters and the min-seeders floor. Not
            the raw tracker hit count.
    """
```

## Gate

1. `make lint` — zéro erreur.
2. `make test` — zéro échec, zéro ERROR de collecte.
3. La migration 008 s'applique sur une `acquire.db` vierge **et** sur une base déjà migrée
   (idempotence), vérifié par test.
4. `rg -n "SELECT.*FROM wanted" --type py personalscraper/acquire/` — chaque requête listant des
   colonnes explicites inclut les deux nouvelles.
5. Aucun changement de comportement observable : les états affichés sont identiques à avant.
