# Phase 01 — Socle de persistance (migration + store)

**Goal**: rendre stockables le **statut `available`** et le **verdict** de la dernière recherche
tracker sur chaque ligne `wanted`. Aucun comportement visible ne change : c'est le socle des
phases 2 et 4.

**Constitution servie**: §5 (états visibles), NE-DOIT-PAS-8 (la disponibilité se lit, elle ne se
redemande pas au tracker).

**Design**: `DESIGN.md` §4 D1.

## Risque principal de la feature

SQLite **ne sait pas** modifier une contrainte `CHECK` par `ALTER TABLE`. Ajouter `available`
au `CHECK (status IN (...))` impose la **reconstruction de table en 12 étapes** :
`PRAGMA foreign_keys=OFF` → table neuve → copie → `DROP` → `RENAME` → recréation des index →
`PRAGMA foreign_key_check` → `PRAGMA foreign_keys=ON`. L'index partiel `idx_wanted_pending` doit
être recréé à l'identique.

C'est isolé en phase 1 pour être traité à froid. Une reconstruction ratée sur `acquire.db`
perdrait la file d'acquisition : **sauvegarder la base avant d'exécuter la migration sur les
données réelles**.

## Surface

| Fichier                                                             | Action                                                                 |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `personalscraper/acquire/migrations/008_wanted_available_state.sql` | **NEW** — reconstruction + 2 colonnes                                  |
| `personalscraper/acquire/domain.py`                                 | `WantedStatus` + `WantedItem` étendus                                  |
| `personalscraper/acquire/_wanted_store.py`                          | SELECT/INSERT étendus + `record_search_outcome()` + `list_available()` |
| `personalscraper/acquire/_store_rows.py`                            | mapping ligne → `WantedItem`                                           |
| `tests/acquire/test_migrations.py`                                  | migration 008 : application, idempotence, préservation des données     |
| `tests/acquire/test_store.py`                                       | aller-retour des nouveaux champs + nouvelles méthodes                  |

## Sous-phases

### 1.1 — Migration 008

**Commit**: `feat(acq-states): add available status and search verdict to wanted`

```sql
-- 008_wanted_available_state.sql
--
-- Two changes, one rebuild:
--
-- 1. New status 'available' — the gap between « searched, takeable candidate
--    found » and « torrent added ». Without it the operator can never see
--    « À récupérer »: search and grab used to be one atomic operation, so the
--    state existed for milliseconds inside a single function call.
--
-- 2. Verdict columns — the engine already computes a named outcome at every
--    exit path (no_candidates / all_filtered / trackers_unavailable / …) but
--    discarded it, so the UI could not tell « searched, nothing takeable »
--    from « never searched ». That ambiguity let a freshly-followed series
--    read « À jour » with three aired episodes missing from the library.
--
-- SQLite cannot ALTER a CHECK constraint, hence the full table rebuild.
-- NULL verdict columns on existing rows = « never searched » — the honest
-- default: we genuinely do not know.
```

**Points de vigilance** :

- l'index partiel `idx_wanted_pending` doit être recréé **à l'identique** après le `RENAME` ;
- `PRAGMA foreign_key_check` doit être exécuté **avant** de réactiver les clés étrangères ;
- la copie doit préserver **toutes** les colonnes existantes, `grabbed_hash` compris — une
  colonne oubliée perd les hashes d'idempotence et rouvre la fenêtre de double-emit ;
- conformément à « pas de rétro-compat avant v1.x », aucune migration de données applicative :
  les lignes existantes gardent leur statut et reçoivent des verdicts `NULL`.

### 1.2 — Domaine + store

**Commit**: `feat(acq-states): expose available status and search verdict through the store`

- `WantedStatus` accueille `available`.
- `WantedItem` gagne `last_search_outcome: str | None` et `last_search_found: int | None`.
- Tous les SELECT de `_wanted_store.py` (`get`, `_list_wanted_by_status`, `mark_done_by_hash`)
  ajoutent les deux colonnes — **vérifier chaque requête** : une seule oubliée renvoie des
  `WantedItem` incohérents selon le chemin de lecture.
- Nouvelles méthodes :

```python
def record_search_outcome(self, wanted_id: int, outcome: str, found: int | None) -> None:
    """Persist the verdict of the search that just ran for this item.

    Called once per search attempt, at EVERY exit path — including failures.
    A path that forgets to call this leaves the item reading « Non vérifié »
    forever, a lie by omission of exactly the kind this feature removes.

    Args:
        wanted_id: The wanted row that was searched.
        outcome: The named outcome (``no_candidates``, ``all_filtered``,
            ``trackers_unavailable``, ``available``, ``grabbed``, …).
        found: Number of TAKEABLE candidates — survivors of the exact-episode
            filter, the hard profile filters and the min-seeders floor. ``None``
            when the search did NOT conclude (outage, open circuit, dead swarm):
            zero would mean « I looked, there is nothing », which is false.
    """


def list_available(self) -> list[WantedItem]:
    """Items a search found takeable but the grab pass has not taken yet.

    This is the ONLY queue the grab pass walks. Bounding grab to this subset
    is what keeps its re-search cheap: it re-queries a handful of known-available
    items, never the whole pending backlog (NE-DOIT-PAS-8).
    """
```

## Gate

1. `make lint` — zéro erreur.
2. `make test` — zéro échec, zéro ERROR de collecte.
3. La migration 008 s'applique sur une base vierge **et** sur une base déjà migrée
   (idempotence), vérifié par test.
4. **Test de préservation** : une base contenant des `wanted` de chaque statut, avec
   `grabbed_hash` renseigné, conserve toutes ses lignes et toutes ses valeurs après migration.
5. `PRAGMA foreign_key_check` retourne vide après migration.
6. L'index `idx_wanted_pending` existe encore et est toujours partiel — vérifié par
   `SELECT sql FROM sqlite_master WHERE name='idx_wanted_pending'`.
7. `rg -n "SELECT.*FROM wanted" --type py personalscraper/acquire/` — chaque requête à colonnes
   explicites inclut les deux nouvelles.
8. Aucun changement de comportement observable : les états affichés sont identiques à avant.
