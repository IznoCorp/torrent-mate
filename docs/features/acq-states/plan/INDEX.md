# Implementation Plan — acq-states

**Feature**: Acquisitions — états véridiques (disponibilité tracker) + amorce du suivi + poster serveur
**Ticket**: #319
**Binding design**: `docs/features/acq-states/DESIGN.md`
**Binding constitution**: `docs/reference/product-intent.md` §5, §6, NE-DOIT-PAS-1/5/7/8
**Branch**: `feat/acq-states`
**Merge mode**: auto

## Phase table

| #   | Phase                                    | File                                                                 | Status |
| --- | ---------------------------------------- | -------------------------------------------------------------------- | ------ |
| 1   | Socle de persistance (migration + store) | [phase-01-persistence.md](phase-01-persistence.md)                   | [ ]    |
| 2   | Le moteur enregistre son verdict         | [phase-02-orchestrator-verdict.md](phase-02-orchestrator-verdict.md) | [ ]    |
| 3   | Dérivation serveur des 5 états           | [phase-03-state-derivation.md](phase-03-state-derivation.md)         | [ ]    |
| 4   | Fin des sources divergentes              | [phase-04-single-source.md](phase-04-single-source.md)               | [ ]    |
| 5   | Amorce à la création du suivi            | [phase-05-follow-priming.md](phase-05-follow-priming.md)             | [ ]    |
| 6   | Enrichissement serveur des métadonnées   | [phase-06-server-metadata.md](phase-06-server-metadata.md)           | [ ]    |
| 7   | UI — les 5 états en français             | [phase-07-ui-states.md](phase-07-ui-states.md)                       | [ ]    |
| 8   | Garde-fous et acceptation                | [phase-08-guardrails-acc.md](phase-08-guardrails-acc.md)             | [ ]    |

## Sequencing rationale

**Phase 1 d'abord** — rien ne peut dériver un état « En attente » vs « À récupérer » tant que le
résultat de recherche n'est pas stockable. La migration `008` et les accesseurs du store sont le
socle dont dépendent les phases 2 et 3. Aucun comportement visible ne change.

**Phase 2 ensuite** — le moteur calcule déjà son verdict à chaque sortie
(`no_candidates`, `all_filtered`, `trackers_unavailable`, …) mais le jette. Cette phase le
persiste, à **tous** les chemins de sortie sans exception : un chemin oublié produirait un
« Non vérifié » perpétuel, c'est-à-dire un nouveau mensonge par omission. Toujours aucun
changement visible.

**Phase 3** — la dérivation des 5 états devient possible : elle lit les faits des phases 1-2.
C'est ici que se joue l'invariant **panne ≠ absence** (DESIGN §3.3). Un seul point de dérivation,
côté serveur, consommé par toutes les surfaces.

**Phase 4** — une fois la dérivation unique en place, on supprime le repli `poll_aired` divergent
de `compute_completeness`. Cet ordre est impératif : supprimer le repli avant d'avoir la
dérivation laisserait le panneau de détail sans catalogue et donc muet.

**Phase 5** — l'amorce à la création rend la dérivation vraie **tout de suite** au lieu d'attendre
le cron de 03:00. Elle vient après la phase 4 parce qu'elle s'appuie sur l'état « Vérification en
cours » que la dérivation unifiée sait désormais exprimer.

**Phase 6** — l'enrichissement serveur du poster est indépendant du modèle d'états ; il est
ordonné ici pour ne pas mélanger deux natures de changement dans une même phase de revue.

**Phase 7** — l'UI arrive en dernier parmi les phases fonctionnelles : elle consomme un contrat
serveur désormais stable, sans jamais re-dériver d'état en JSX.

**Phase 8** — garde-fous exécutables et vérification des 8 critères d'acceptation sur données
réelles.

## Invariants transverses (toutes phases)

1. **Aucun appel tracker déclenché par un rendu.** La disponibilité se lit d'un état persisté
   (NE-DOIT-PAS-8). Tout `search_all` sur un chemin de lecture web est un échec de phase.
2. **Panne ≠ absence.** `trackers_unavailable`, `circuit_open`, `no_seeders` ⇒ « Non vérifié »,
   jamais « En attente » (DESIGN §3.3).
3. **Une seule dérivation.** L'UI ne re-dérive aucun état ; elle mappe un état serveur vers un
   libellé et un ton.
4. **Un test de régression par cause racine.** RC1, RC2, RC3 ont chacun un test qui échoue sur le
   code actuel et passe après correction.
5. **Autorité de déclenchement unique.** L'amorce passe par le runner et le lock existants —
   jamais un second mécanisme (NE-DOIT-PAS-7).
6. **Contrat typé.** Toute évolution de route ⇒ `make openapi` + commit de `openapi.json` et
   `schema.d.ts` régénérés.
