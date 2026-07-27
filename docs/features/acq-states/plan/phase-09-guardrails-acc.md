# Phase 09 — Garde-fous et acceptation

**Goal**: rendre la conformité **exécutable** et vérifier les 8 critères d'acceptation sur
données réelles. Aucun verdict « conforme » sans run daté à l'appui.

**Constitution servie**: §méthode (preuve ou non-conforme), NE-DOIT-PAS-1.

**Design**: `DESIGN.md` §6.

## Surface

| Fichier                                             | Action                                        |
| --------------------------------------------------- | --------------------------------------------- |
| `scripts/check-acquisition-coherence.py`            | étendu aux 5 états et au verdict de recherche |
| `tests/integration/test_no_tracker_call_on_read.py` | **NEW** — NE-DOIT-PAS-8 exécutable            |
| `docs/reference/web-ui.md`                          | vocabulaire des 5 états                       |
| `docs/reference/maintenance.md`                     | action d'amorce au catalogue                  |
| `CHANGELOG.md`                                      | entrée 0.55.0                                 |

## Sous-phases

### 9.1 — Garde-fou : aucun appel tracker au rendu

**Commit**: `test(acq-states): reading a card must never hit a tracker`

```python
def test_reading_follows_never_calls_a_tracker() -> None:
    """Rendering acquisition surfaces must not touch trackers or providers.

    NE-DOIT-PAS-8: getting banned from a tracker deprives the operator of the
    tool. Availability is read from persisted state; a read path that searches
    live would turn every page refresh into tracker traffic.
    """
```

Compte les appels sortants pendant `GET /followed` et `GET /followed/{id}/completeness` :
doit être **zéro**.

### 9.2 — Extension du garde-fou de cohérence

**Commit**: `feat(acq-states): extend the acquisition-coherence guard to the five states`

Le script `check-acquisition-coherence.py` gagne les vérifications :

- aucun suivi actif en `up_to_date` sans catalogue diffusé (le défaut fondateur) ;
- aucun épisode en `en_attente` dont le dernier outcome est non concluant (panne ≠ absence) ;
- aucun `wanted` ouvert avec `last_search_at` renseigné mais `last_search_outcome` nul
  (chemin de sortie oublié en phase 2) ;
- aucun `wanted` en `available` dont le dernier verdict n'est pas `available` (statut et verdict
  désynchronisés) ;
- aucun `wanted` en `available` depuis plus de 24 h (le grab ne le consomme pas — passe morte
  ou cron absent) ;
- aucun suivi actif sans poster alors que le provider en expose un.

### 9.3 — Documentation

**Commit**: `docs(acq-states): document the five acquisition states`

### 9.4 — Vérification des critères d'acceptation

**Commit**: `chore(acq-states): phase 8 gate — ACC verified on real data`

Les **12** critères `ACC-NN` du DESIGN §6 sont ré-exercés, commande **exécutée** et sortie
collée dans `IMPLEMENTATION.md`. Un critère non exercé est un critère non tenu.

Cas de vérification privilégié : **Furious (followed_id 10)**, le média de l'incident — plus
une série non possédée pour exercer « En attente » et « À récupérer », et une panne tracker
simulée pour exercer « Non vérifié ».

**Vérification bout-en-bout de la séparation** (ACC-09 à ACC-12) : sur un épisode réellement
disponible, exécuter `search` seul, constater l'état « À récupérer » **et zéro torrent ajouté**,
puis exécuter `grab` et constater le passage en « En cours d'acquisition ». C'est la preuve
directe que la demande opérateur est satisfaite.

## Gate

1. `make check` — lint + test + module-size + typed-api.
2. `python scripts/check-acquisition-coherence.py` — **zéro anomalie**.
3. `python scripts/audit_design_coverage.py --strict` et `update_feature_map.py --check`
   (gates CI-only, à lancer localement).
4. Les 8 critères ACC exercés, sorties collées dans `IMPLEMENTATION.md`.
5. `python -c "import personalscraper"` — smoke test.
6. Bump de version présent (0.55.0) et cohérent avec `/api/version` après déploiement.
