# Plan — reswitch

Master plan for the `reswitch` feature. Design: `docs/features/reswitch/DESIGN.md`.

| #   | Phase                                          | File                  | Status |
| --- | ---------------------------------------------- | --------------------- | ------ |
| 1   | Seeders renforcés (config + test)              | phase-01-seeders.md   | [ ]    |
| 2   | Observabilité swarm (`swarm_seeds` + classify) | phase-02-swarm.md     | [ ]    |
| 3   | Mémoire hashes tentés + exclusion ranking      | phase-03-exclusion.md | [ ]    |
| 4   | Acteur de rebascule (`reswitch_stalled`)       | phase-04-actor.md     | [ ]    |
| 5   | Surfaçage UI + events + ACC + déploiement      | phase-05-acc.md       | [ ]    |

Discipline: test rouge-avant par bug/comportement ; chaque phase vérifiée vs DESIGN ;
aucun step différé (event-bus NO DEFERRAL) ; `make check` au gate de la dernière phase.
