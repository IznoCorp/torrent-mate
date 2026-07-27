# Phase 06 — Amorce à la création du suivi

**Goal**: un suivi fraîchement créé est **amorcé tout de suite** (catalogue + file `wanted` +
première recherche) au lieu d'attendre le cron de 03:00. L'ajout répond 201 immédiatement et
l'amorce s'exécute visiblement.

**Constitution servie**: §6 (s'exécute ou s'enfile **visiblement**), NE-DOIT-PAS-2 (file ou
attente invisible), NE-DOIT-PAS-5 (échec silencieux), NE-DOIT-PAS-7 (pas de second mécanisme).

**Design**: `DESIGN.md` §2 RC1 + §4 D2.

## Le défaut corrigé

`POST /api/acquisition/followed` insère la ligne et s'arrête. Le 2026-07-27, Furious ajouté à
09:18 restait sans catalogue ni file jusqu'au cron du lendemain ; le « Rechercher » de
l'opérateur à 09:19 a donc lancé un `grab` qui n'avait **rien à faire** et a rendu rc=0 —
un succès silencieux sur une action qui n'a rien accompli.

## Surface

| Fichier                                               | Action                                                    |
| ----------------------------------------------------- | --------------------------------------------------------- |
| `personalscraper/web/routes/acquisition.py`           | `create_follow` enfile le run d'amorce après le 201       |
| `personalscraper/web/maintenance/registry.py`         | action « amorce d'un suivi » dans le catalogue de runners |
| `personalscraper/web/models/acquisition.py`           | `FollowStatus` gagne `verification_en_cours`              |
| `tests/unit/web/routes/test_create_follow_priming.py` | **NEW** — reproduit RC1                                   |

## Décisions d'implémentation

**Autorité de déclenchement unique.** L'amorce passe par le **runner et le lock existants**
(ceux qui exécutent déjà `detect` et `grab` depuis l'interface) — jamais un nouveau mécanisme
parallèle. Concrètement : réutiliser le chemin qui a produit
`grab_runner_starting / grab_runner_completed` dans les logs prod, pas en écrire un second.

**Périmètre du run d'amorce** : les **trois passes enchaînées** sur le seul suivi créé —
`detect --series {id}` → `search --followed-id {id}` → `grab --followed-id {id}`. Ne jamais
déclencher une passe globale : ajouter une série ne doit pas relancer l'acquisition de toute la
médiathèque.

L'enchaînement traverse volontairement les trois états en quelques secondes (Non vérifié → À
récupérer → En cours d'acquisition). Ce n'est pas contradictoire avec la séparation de la
phase 2 : à l'ajout, l'opérateur veut le rattrapage immédiat ; en régime permanent, ce sont les
passes planifiées qui espacent les transitions et rendent « À récupérer » observable.

**Visibilité.** Tant que le run est en vol, la carte affiche **« Vérification en cours »**
(`verification_en_cours`), pas un état deviné, et surtout pas « À jour ». Le run est
consultable comme les autres (même historique, même détail).

**Échec bruyant.** Si l'amorce échoue (providers injoignables, trackers en panne), la carte le
dit et reste en « Non vérifié » — jamais un état optimiste. NE-DOIT-PAS-5.

**Idempotence.** Réactiver un suivi inactif ré-amorce ; deux amorces concurrentes sur le même
suivi ne produisent qu'un run (le refus d'idempotence est le seul refus permis par §6).

## Sous-phases

### 6.1 — Test-first : reproduire RC1

**Commit**: `test(acq-states): a fresh follow is primed, never silently idle`

```python
def test_create_follow_enqueues_a_priming_run() -> None:
    """Creating a follow must prime it — catalog, queue, first search.

    Reproduces the founding incident: Furious was added at 09:18:50 while the
    detect cron had last run at 03:00:02. With no priming, the operator's
    « Rechercher » at 09:19:09 ran a grab over an empty wanted queue and
    returned rc=0 — a success report for an action that did nothing.
    """


def test_priming_failure_leaves_non_verifie_not_up_to_date() -> None:
    """A failed priming run must never leave the card looking healthy."""
```

### 6.2 — L'amorce

**Commit**: `feat(acq-states): prime a new follow through the existing run authority`

### 6.3 — L'état « Vérification en cours »

**Commit**: `feat(acq-states): surface the priming run on the follow card`

## Gate

1. `make lint` + `make test`.
2. Les deux tests de 6.1 échouaient avant, passent après.
3. `rg -n "pipeline.lock|runner" --type py personalscraper/web/routes/acquisition.py` — l'amorce
   emprunte l'autorité existante ; aucun `subprocess` ni thread ad hoc introduit.
4. Un ajout réel via l'interface (staging interdit en écriture ⇒ prod, ou test d'intégration)
   produit un run visible et un catalogue peuplé en moins d'une minute.
5. L'amorce ne déclenche **pas** de passe globale : vérifié en comptant les `wanted` créées.
6. `make openapi` ⇒ commit de `openapi.json` + `schema.d.ts`.
