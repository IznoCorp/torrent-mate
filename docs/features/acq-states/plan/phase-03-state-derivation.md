# Phase 03 — Dérivation serveur des 5 états

**Goal**: un point de dérivation unique, côté serveur, produisant les 5 états à partir de faits
(catalogue diffusé × possession × file `wanted` × verdict de recherche). C'est le cœur de la
feature et le remplacement direct du code qui affirmait « À jour » sur zéro connaissance.

**Constitution servie**: §5 (états visibles), NE-DOIT-PAS-1 (mentir).

**Design**: `DESIGN.md` §3.1, §3.2, §3.3.

## Surface

| Fichier                                     | Action                                                 |
| ------------------------------------------- | ------------------------------------------------------ |
| `personalscraper/web/acquisition/states.py` | **NEW** — la dérivation, source unique                 |
| `personalscraper/web/models/acquisition.py` | `FollowStatus` étendu ; `status` délègue à `states.py` |
| `personalscraper/web/acquisition/truth.py`  | `FollowTruth` porte les compteurs par état             |
| `tests/unit/web/acquisition/test_states.py` | **NEW** — table de vérité exhaustive                   |
| `tests/unit/web/acquisition/test_truth.py`  | mise à jour                                            |

## Le contrat d'états

```python
EpisodeState = Literal[
    "en_mediatheque",   # À jour
    "en_attente",       # recherche CONCLUE, rien de prenable
    "a_recuperer",      # candidat prenable connu, pas encore pris
    "en_acquisition",   # pris (grabbed) ou pipeline en cours
    "non_verifie",      # aucune recherche conclue — on ne sait pas
]
```

`FollowStatus` (état de carte) reprend les mêmes valeurs, plus `disabled` (suivi en pause) et
`verification_en_cours` (run d'amorce en vol, phase 5).

## La règle de dérivation, par épisode diffusé

Ordre d'évaluation **impératif** — le premier qui matche gagne :

```python
def derive_episode_state(*, owned, wanted_status, last_search_outcome, last_search_found):
    """Derive one aired episode's state from persisted facts only.

    Order matters. Ownership wins over everything: an episode sitting in the
    library is « À jour » even if a stale grabbed row still points at it (the
    phantom-grabbed case that used to pin a series at « en cours » while all
    its files were green).

    A search that did NOT conclude — provider outage, open circuit, dead swarm
    — must never read as « En attente ». Absence of knowledge is « Non vérifié »,
    never an assertion about the trackers. This is the invariant the founding
    incident violated, one level up.
    """
    if owned:
        return "en_mediatheque"
    if wanted_status == "grabbed":
        return "en_acquisition"
    if last_search_outcome is None:
        return "non_verifie"
    if last_search_outcome in INCONCLUSIVE_OUTCOMES:   # panne ≠ absence
        return "non_verifie"
    if (last_search_found or 0) > 0:
        return "a_recuperer"
    return "en_attente"


#: Outcomes that mean « the search did not conclude » — the engine could not
#: form an opinion about tracker availability. Reporting any of these as
#: « En attente » would claim knowledge we do not have.
INCONCLUSIVE_OUTCOMES = frozenset({
    "trackers_unavailable",
    "circuit_open",
    "search_api_error",
    "no_seeders",
})
```

## L'état de carte, à partir des épisodes

Agrégation, du plus urgent au plus serein — la carte doit montrer **ce qui demande une action** :

1. un épisode `a_recuperer` ⇒ **À récupérer**
2. sinon un `en_acquisition` ⇒ **En cours d'acquisition**
3. sinon un `en_attente` ⇒ **En attente**
4. sinon un `non_verifie` ⇒ **Non vérifié**
5. sinon (tous `en_mediatheque`) ⇒ **À jour**

**Catalogue vide ⇒ « Non vérifié »**, jamais « À jour ». C'est la correction directe de
`models/acquisition.py:99-104`. Une série sans catalogue n'est pas à jour : on ne sait rien
d'elle.

## Sous-phases

### 3.1 — Test-first : la table de vérité

**Commit**: `test(acq-states): truth table for the five acquisition states`

Le test qui reproduit l'incident fondateur, écrit en premier et **échouant sur le code actuel** :

```python
def test_empty_catalog_is_never_up_to_date() -> None:
    """A follow with no aired catalog must read « Non vérifié », never « À jour ».

    Reproduces the founding incident: Furious (TVDB 468000) was added at 09:18,
    the detect cron had last run at 03:00, so the catalog was empty and the card
    fell through to the raw wanted counters — zero rows — and declared « À jour »
    while three aired episodes were missing from the library.
    """
```

Plus la table exhaustive : chaque combinaison (possession × statut wanted × outcome × found)
produit l'état attendu, avec une ligne dédiée par outcome non concluant.

### 3.2 — La dérivation

**Commit**: `feat(acq-states): derive the five acquisition states server-side`

`states.py` créé, `models/acquisition.py:99-104` remplacé par une délégation. **Supprimer** le
repli sur les compteurs bruts : il n'a plus de raison d'être et il est la cause de RC2.

## Gate

1. `make lint` + `make test`.
2. Le test `test_empty_catalog_is_never_up_to_date` échouait avant 3.2, passe après.
3. `rg -n "up_to_date" --type py personalscraper/web/models/acquisition.py` — plus aucun retour
   `up_to_date` sur un chemin d'ignorance.
4. Table de vérité complète : chaque outcome de la phase 2 a sa ligne de test.
5. Aucun appel réseau dans `states.py` — vérifié par lecture et par absence d'import provider.
6. `make openapi` si le contrat change ⇒ commit de `openapi.json` + `schema.d.ts`.
