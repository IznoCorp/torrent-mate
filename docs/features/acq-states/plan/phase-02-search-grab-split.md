# Phase 02 — Séparation search / grab dans le moteur

**Goal**: scinder l'opération atomique actuelle en deux. `search` interroge les trackers et
statue sur la disponibilité **sans rien télécharger** ; `grab` ne consomme que les items connus
disponibles. C'est le cœur de la feature : sans cette séparation, « À récupérer » ne dure que
quelques millisecondes à l'intérieur d'un appel de fonction.

**Constitution servie**: §5 (le watcher vérifie la disponibilité **puis** récupère),
NE-DOIT-PAS-5 (échec silencieux), NE-DOIT-PAS-8 (pas de rafale tracker).

**Design**: `DESIGN.md` §3.3 + §3.4.

## Ce qui existe aujourd'hui

`orchestrator.py` fait, en une passe : claim → search → `filter_to_episode` →
`apply_hard_filters` → `dedup` → `rank` → pick top → `add` au client torrent → `mark_grabbed`.
`service.run()` itère `list_pending()` + `list_stale_searching()`.

Les issues sont **déjà nommées** (lignes ~295-345) — elles ne sont simplement jamais persistées.

## La découpe

| Nouvelle opération | Fait                                                   | Ne fait pas              |
| ------------------ | ------------------------------------------------------ | ------------------------ |
| `search_one`       | search → filtre → rank → **statue** + persiste verdict | n'ajoute aucun torrent   |
| `grab_one`         | re-search → filtre → rank → pick top → **add**         | ne statue pas la cadence |

**`search_one` ne télécharge rien.** C'est l'invariant n°1 de la feature. Un `search` qui
ajoute un torrent est un échec de phase.

**`grab_one` refait sa propre recherche** (arbitrage opérateur, DESIGN §3.4) au lieu de
réutiliser un candidat mémorisé. Il ne parcourt que `list_available()` — un petit sous-ensemble
— ce qui borne le surcoût tracker.

**Retour arrière honnête** : si la re-recherche de `grab_one` ne trouve plus rien (torrent
retiré entre les deux passes), l'item **repasse** en `pending` avec le nouveau verdict
enregistré. Jamais un ajout à l'aveugle, jamais un état figé sur « À récupérer ».

## Chemins de sortie de `search_one` (exhaustif)

| Chemin                    | `outcome` persisté     | `found`       | Statut résultant |
| ------------------------- | ---------------------- | ------------- | ---------------- |
| `CircuitOpenError`        | `circuit_open`         | `NULL`        | `pending`        |
| `ApiError`                | `search_api_error`     | `NULL`        | `pending`        |
| `outcome.all_errored`     | `trackers_unavailable` | `NULL`        | `pending`        |
| aucun résultat            | `no_candidates`        | `0`           | `pending`        |
| `filter_to_episode` vide  | `no_matching_episode`  | `0`           | `pending`        |
| `apply_hard_filters` vide | `all_filtered`         | `0`           | `pending`        |
| `rank` vide (min_seeders) | `no_seeders`           | `NULL`        | `pending`        |
| candidats prenables       | `available`            | `len(ranked)` | **`available`**  |

**Piège à éviter** : ne PAS écrire `found = 0` sur les chemins de panne par commodité. `0`
signifie « j'ai cherché, il n'y a rien » ; sur une panne c'est faux, et ce faux remonterait
jusqu'à l'écran en « En attente » mensonger — le défaut fondateur, déplacé d'un cran.

## Cadence

La cadence (2 h à chaud / 1 j / 7 j / coupure 30 j) s'applique à **`search`** : c'est elle qui
espace les re-vérifications d'un épisode indisponible. Un item `available` est pris par la
passe `grab` suivante **sans attendre sa cadence** — il est déjà connu disponible.

## Sous-phases

### 2.1 — Test-first : `search` ne télécharge rien

**Commit**: `test(acq-states): a search pass must never add a torrent`

```python
def test_search_pass_adds_no_torrent() -> None:
    """The search pass states availability; it never downloads.

    Separating search from grab is the whole point: while they were one atomic
    operation, « À récupérer » existed for milliseconds inside a single function
    call and the operator could never see what was available but not yet taken.
    """
```

### 2.2 — Test-first : les chemins de sortie de `search`

**Commit**: `test(acq-states): cover every search exit path's persisted verdict`

Un test par ligne du tableau ci-dessus, plus un **test de couverture exhaustive** qui échoue si
un nouveau chemin de sortie apparaît sans persistance — sinon la prochaine évolution rouvrira
silencieusement la faille.

### 2.3 — `search_one`

**Commit**: `feat(acq-states): split the search operation out of the grab orchestrator`

### 2.4 — Test-first : `grab` borné aux disponibles + retour arrière

**Commit**: `test(acq-states): grab walks only available items and reverts on disappearance`

```python
def test_grab_only_walks_available_items() -> None:
    """Grab must not re-search the whole pending backlog.

    Bounding grab to list_available() is what makes the operator's « always
    re-search » choice cheap: a handful of known-available items, never the
    full queue (NE-DOIT-PAS-8).
    """


def test_grab_reverts_to_pending_when_the_torrent_vanished() -> None:
    """A candidate that disappeared between the two passes must not be faked."""
```

### 2.5 — `grab_one`

**Commit**: `feat(acq-states): grab consumes only known-available items`

## Gate

1. `make lint` + `make test`.
2. Les tests de 2.1, 2.2 et 2.4 échouaient avant leur sous-phase, passent après (vérifié
   réellement, pas supposé).
3. Le test de couverture exhaustive des chemins de sortie passe.
4. Aucun chemin de panne ne persiste `found = 0`.
5. `rg -n "torrent_client|\.add\(" --type py` sur le chemin `search_one` — **aucun** ajout de
   torrent atteignable depuis la passe search.
6. Vérification sur données réelles : une passe `search` sur un suivi produit des items
   `available` et **zéro** nouveau torrent dans qBittorrent.
