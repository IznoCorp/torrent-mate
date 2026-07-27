# Phase 02 — Le moteur enregistre son verdict

**Goal**: persister l'issue de chaque recherche à **tous** les chemins de sortie de
l'orchestrateur de grab. Le verdict existe déjà en mémoire ; il est aujourd'hui jeté.

**Constitution servie**: NE-DOIT-PAS-5 (échec silencieux), §5.

**Design**: `DESIGN.md` §3.3 + §4 D1.

## Surface

| Fichier                                      | Action                                                                          |
| -------------------------------------------- | ------------------------------------------------------------------------------- |
| `personalscraper/acquire/orchestrator.py`    | `record_search_outcome` à chaque retour de `_not_found` / `_retryable` / succès |
| `personalscraper/acquire/service.py`         | passage du store à l'orchestrateur si nécessaire                                |
| `tests/acquire/test_orchestrator_outcome.py` | **NEW** — un test par chemin de sortie                                          |

## Chemins de sortie à couvrir (exhaustif)

Relevés dans `orchestrator.py` autour des lignes 295-345. **Aucun ne doit être oublié** :

| Chemin                     | `outcome` persisté     | `found`       | Sens                            |
| -------------------------- | ---------------------- | ------------- | ------------------------------- |
| `CircuitOpenError`         | `circuit_open`         | `NULL`        | panne — on ne sait pas          |
| `ApiError`                 | `search_api_error`     | `NULL`        | panne — on ne sait pas          |
| `outcome.all_errored`      | `trackers_unavailable` | `NULL`        | panne — on ne sait pas          |
| `not outcome.results`      | `no_candidates`        | `0`           | conclusion : rien               |
| `filter_to_episode` vide   | `no_matching_episode`  | `0`           | conclusion : rien de prenable   |
| `apply_hard_filters` vide  | `all_filtered`         | `0`           | conclusion : rien de prenable   |
| `rank` vide (`no_seeders`) | `no_seeders`           | `NULL`        | swarm mort — pas une conclusion |
| `no_torrent_client`        | `no_torrent_client`    | `len(ranked)` | prenable connu, non pris        |
| échec d'ajout / resolve    | l'issue réelle         | `len(ranked)` | prenable connu, non pris        |
| succès                     | `grabbed`              | `len(ranked)` | pris                            |

**Règle de remplissage de `found`** : `NULL` quand la recherche **n'a pas conclu** (panne,
circuit ouvert, swarm mort) ; un entier quand elle a conclu. C'est cette distinction, et elle
seule, qui permettra à la phase 3 de ne jamais transformer une panne en « En attente ».

**Piège à éviter** : ne PAS écrire `found = 0` sur les chemins de panne par commodité. Un `0`
signifie « j'ai cherché, il n'y a rien » ; sur une panne c'est faux, et ce faux se propagerait
jusqu'à l'écran sous la forme d'un « En attente » mensonger — exactement le défaut corrigé ici.

## Sous-phases

### 2.1 — Test-first : un test par chemin de sortie

**Commit**: `test(acq-states): cover every grab exit path's persisted verdict`

Écrire d'abord les tests, avec l'orchestrateur inchangé : ils échouent tous. Chaque test force un
chemin de sortie (mocks tracker/registry) puis asserte le couple
(`last_search_outcome`, `last_search_found`) écrit en base.

Inclure un **test de couverture exhaustive** qui échoue si un nouveau chemin de sortie apparaît
sans persistance — sinon la prochaine évolution rouvrira silencieusement la faille :

```python
def test_every_exit_path_records_an_outcome() -> None:
    """No orchestrator exit path may return without persisting its verdict.

    A forgotten path leaves the item reading « Non vérifié » forever — a lie by
    omission of the exact kind this feature removes. This test walks the
    orchestrator's return statements via AST and asserts each is preceded by a
    recorded outcome, so a future exit path cannot silently reopen the gap.
    """
```

### 2.2 — Persistance à chaque chemin

**Commit**: `feat(acq-states): persist the search verdict at every grab exit path`

Les tests de 2.1 passent au vert.

## Gate

1. `make lint` + `make test` — zéro erreur, zéro échec.
2. Les tests de 2.1 échouaient avant 2.2 et passent après (vérifié, pas supposé).
3. Le test de couverture exhaustive des chemins de sortie passe.
4. Aucun chemin de panne ne persiste `found = 0`.
5. Un `grab` réel sur une série suivie écrit bien un `last_search_outcome` non nul en base —
   vérification sur données réelles, pas seulement en test.
