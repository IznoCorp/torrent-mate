# Implementation Plan — acq-states

**Feature**: Acquisitions — états véridiques (disponibilité tracker) + séparation search/grab

- amorce du suivi + poster serveur
  **Ticket**: #319
  **Binding design**: `docs/features/acq-states/DESIGN.md`
  **Binding constitution**: `docs/reference/product-intent.md` §5, §6, NE-DOIT-PAS-1/5/7/8
  **Branch**: `feat/acq-states`
  **Merge mode**: auto

## Phase table

| #   | Phase                                    | File                                                           | Status |
| --- | ---------------------------------------- | -------------------------------------------------------------- | ------ |
| 1   | Socle de persistance (migration + store) | [phase-01-persistence.md](phase-01-persistence.md)             | [ ]    |
| 2   | Séparation search / grab dans le moteur  | [phase-02-search-grab-split.md](phase-02-search-grab-split.md) | [ ]    |
| 3   | Commande `search` + ordonnancement       | [phase-03-search-command.md](phase-03-search-command.md)       | [ ]    |
| 4   | Dérivation serveur des 5 états           | [phase-04-state-derivation.md](phase-04-state-derivation.md)   | [ ]    |
| 5   | Fin des sources divergentes              | [phase-05-single-source.md](phase-05-single-source.md)         | [ ]    |
| 6   | Amorce à la création du suivi            | [phase-06-follow-priming.md](phase-06-follow-priming.md)       | [ ]    |
| 7   | Enrichissement serveur des métadonnées   | [phase-07-server-metadata.md](phase-07-server-metadata.md)     | [ ]    |
| 8   | UI — 5 états + Récupérer maintenant      | [phase-08-ui-states.md](phase-08-ui-states.md)                 | [ ]    |
| 9   | Garde-fous et acceptation                | [phase-09-guardrails-acc.md](phase-09-guardrails-acc.md)       | [ ]    |

## Sequencing rationale

**Phase 1 d'abord** — rien ne peut exister sans le statut `available` ni les colonnes de
verdict. Cette phase porte le **risque technique principal** : SQLite ne sait pas modifier une
contrainte `CHECK` par `ALTER TABLE`, il faut la reconstruction de table en 12 étapes. Isolée
en phase 1 pour être traitée à froid, avec sa propre gate.

**Phase 2 ensuite** — la séparation du moteur est le cœur de la feature. Elle s'appuie sur le
statut `available` de la phase 1 et rend l'état « À récupérer » réellement observable au lieu
de durer quelques secondes. C'est aussi ici que le verdict est persisté à tous les chemins de
sortie de `search`.

**Phase 3** — la passe `search` n'a de sens qu'exposée : commande CLI et entrée cron entre
`detect` (03:00) et `grab` (03:20). Sans elle, la séparation de la phase 2 ne s'exécuterait
jamais en production.

**Phase 4** — la dérivation des 5 états lit les faits des phases 1-2. Invariant central :
**panne ≠ absence** (DESIGN §3.3). Un seul point de dérivation côté serveur.

**Phase 5** — une fois la dérivation unique en place, on supprime le repli `poll_aired`
divergent. Cet ordre est impératif : supprimer le repli avant la dérivation laisserait le
panneau de détail muet.

**Phase 6** — l'amorce enchaîne `detect` → `search` → `grab` sur le seul suivi créé, et rend
l'état vrai immédiatement au lieu d'attendre 03:00. Elle vient après la phase 3 parce qu'elle
appelle la commande `search` que celle-ci crée.

**Phase 7** — l'enrichissement du poster est indépendant du modèle d'états ; ordonné ici pour
ne pas mêler deux natures de changement dans une même revue.

**Phase 8** — l'UI arrive en dernier parmi les phases fonctionnelles : elle consomme un contrat
serveur stable et n'y ajoute aucune dérivation.

**Phase 9** — garde-fous exécutables et vérification des 12 critères d'acceptation sur données
réelles.

## Invariants transverses (toutes phases)

1. **`search` ne télécharge rien.** Une passe `search` qui ajoute un torrent est un échec de
   phase, pas un détail.
2. **`grab` ne parcourt que les `available`.** C'est ce qui borne le surcoût tracker de la
   re-recherche et rend le choix opérateur compatible avec NE-DOIT-PAS-8.
3. **Panne ≠ absence.** `trackers_unavailable`, `circuit_open`, `no_seeders` ⇒ « Non vérifié »,
   jamais « En attente ».
4. **Aucun appel tracker déclenché par un rendu.** La disponibilité se lit d'un état persisté.
5. **Une seule dérivation.** L'UI mappe un état serveur vers un libellé et un ton ; elle n'en
   dérive aucun.
6. **Un test de régression par cause racine.** RC1, RC2, RC3 ont chacun un test qui échoue sur
   le code actuel et passe après correction.
7. **Autorité de déclenchement unique.** Amorce et « Récupérer maintenant » passent par le
   runner et le lock existants — jamais un second mécanisme.
8. **Contrat typé.** Toute évolution de route ⇒ `make openapi` + commit de `openapi.json` et
   `schema.d.ts`.
