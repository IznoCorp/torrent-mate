# Tech-Debt Plan — INDEX

**Codename** : tech-debt
**SemVer** : MINOR (0.15.1 → 0.16.0)
**DESIGN** : `../DESIGN.md`
**Audit base** : `../audit/` (items 1-13)
**Master backlog** : `../audit/11-global-synthesis.md`

## Phases

| #   | Phase                                        | File                      | Effort | Status |
| --- | -------------------------------------------- | ------------------------- | ------ | ------ |
| 1   | Foundations BDD/indexer + PRAGMA             | phase-01-foundations.md   | 2-3 j  | [ ]    |
| 2   | CLI gaps + auto-trigger                      | phase-02-cli-gaps.md      | 2 j    | [ ]    |
| 3   | Observability (broadened DEV #6 → 7 cmds)    | phase-03-observability.md | 2 j    | [ ]    |
| 4   | Path detection + paranoia branch + cleanup   | phase-04-path-cleanup.md  | 2-3 j  | [ ]    |
| 5   | Conformity (drop Protocols + tests refactor) | phase-05-conformity.md    | 2-3 j  | [ ]    |
| 6   | Format + heavy doc work                      | phase-06-format-docs.md   | 3-4 j  | [ ]    |
| 7   | Matrix v2.1 + agents matrix-aware            | phase-07-matrix-v21.md    | 1-2 j  | [ ]    |
| 8   | Polish + Plan A reset + size hard-block      | phase-08-polish.md        | 3-4 j  | [ ]    |
| 9   | **Archive DESIGN.md updates (NEW)**          | phase-09-archive-docs.md  | 1-2 j  | [ ]    |

**Total post-REDO** : **17-25 jours séquentiel, 14-20 jours parallélisable**. Vs original
13-19 j = **+3-6 jours** suite à l'audit-quality REDO item 11 (`6eb5f31`, 26 nouveaux DEVs).

## Already shipped (pre-plan, on operator priority demand)

Commits sur `fix/tech-debt` depuis item 4 closure (`882bc6f`) :

| SHA       | DEV | Description                                                                          |
| --------- | --- | ------------------------------------------------------------------------------------ |
| `268cbee` | #9  | repair_root_duplicate inversion fix (data-loss)                                      |
| `29c4953` | #11 | compute_merkle_root sort-key determinism                                             |
| `fc39f77` | #13 | \_recreate_indexes IF NOT EXISTS (C5 race workers)                                   |
| `3993487` | #14 | \_build_disk_fingerprints + \_sample_fresh_fingerprints oshash IS NOT NULL alignment |

Plus 8 commits docs (`b52b592`, `69f60d7`, `29f87e5`, `67d73c0`, `bc3a4a6`, `53e5e6d`,
`3d8ef87`, `03b35e4`, `9d1a4b8`, `db8c705`) couvrant items 5-13 audit + brainstorms.

## Dependencies graph

```
Phase 1 (foundations) ──┬─→ Phase 2 (CLI gaps)
                        ├─→ Phase 3 (observability)
                        └─→ Phase 4 (path cleanup) ──→ Phase 5 (conformity)
                                                          │
Phase 6 (format+docs) ───────────────────────────────────┴─→ Phase 7 (matrix v2.1)
                                                                            │
                                                                            └─→ Phase 8 (polish)
```

Phases 2/3 peuvent partiellement paralléliser avec Phase 1 (différentes dimensions).
Phase 6 peut tourner en parallèle de Phase 4/5.

## ACCEPTANCE

Voir `../DESIGN.md` §6 pour les 15 criteria exécutables. À développer en `ACCEPTANCE.md`
séparé pendant Phase 8 (consolidation finale).

## Implementation conventions

- Chaque sous-phase = 1 commit avec scope `(tech-debt)`.
- Commits suivent Conventional Commits : `fix(tech-debt): ...`, `feat(tech-debt): ...`,
  `test(tech-debt): ...`, `docs(tech-debt): ...`.
- Phase gate = `chore(tech-debt): phase N gate — <description>` après que toutes les
  sous-phases sont vertes.
- `make check` (lint + test + module-size + typed-api) doit passer à chaque phase gate.
