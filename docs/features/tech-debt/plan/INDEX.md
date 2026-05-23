# Tech-Debt Plan — INDEX

**Codename** : tech-debt
**SemVer** : MINOR (0.15.1 → 0.16.0)
**DESIGN** : `../DESIGN.md`
**Audit base** : `../audit/` (items 1-13)
**Master backlog** : `../audit/11-global-synthesis.md`

## Phases

| #    | Phase                                                                   | File                      | Effort  | Status |
| ---- | ----------------------------------------------------------------------- | ------------------------- | ------- | ------ |
| 0    | Pre-Foundations: skill safety net (DEV #1 promu)                        | phase-00-skill-safety.md  | 0.5 j   | [ ]    |
| 1    | Foundations BDD/indexer + PRAGMA + bonus DEVs                           | phase-01-foundations.md   | 3-4 j   | [ ]    |
| 2    | CLI gaps + backfill-ids first run                                       | phase-02-cli-gaps.md      | 2 j     | [ ]    |
| 3    | Observability (broadened DEV #6 → 7 cmds)                               | phase-03-observability.md | 2 j     | [ ]    |
| 4    | Path detection + paranoia branch (DEV #31)                              | phase-04-path-cleanup.md  | 2-3 j   | [ ]    |
| 5    | Conformity (drop Protocols + tests refactor + Pydantic)                 | phase-05-conformity.md    | 2-3 j   | [ ]    |
| 5.9  | NTFS cache pressure (audit/12 integration)                              | (no formal phase file)    | 1 j     | [x]    |
| 5.10 | Process Hardening (drift-detect + phase-gate + briefing v2 + drafts)    | (no formal phase file)    | 1 j     | [x]    |
| 5.11 | Corrections (IMPL+ACC+plan sync + ACC-NTFS + drift-detect refine)       | (no formal phase file)    | 0.5 j   | [x]    |
| 6    | Format + heavy doc work                                                 | phase-06-format-docs.md   | 3-4 j   | [x]    |
| 7    | Matrix v2.1 + agents matrix-aware                                       | phase-07-matrix-v21.md    | 1-2 j   | [x]    |
| 8    | Polish + Plan A reset + size hard-block + bonus                         | phase-08-polish.md        | 3-4 j   | [ ]    |
| 9    | CLI Test Coverage (NEW — absorbe 8.7 SH-25 ; 11 harnesses déjà shippés) | phase-09-cli-coverage.md  | 1.5-2 j | [ ]    |
| 10   | Archive DESIGN.md updates (7 features)                                  | phase-10-archive-docs.md  | 1-2 j   | [ ]    |

**Total post coverage-fix + Phase 9 CLI Coverage** : **20.5-29 jours séquentiel,
16.5-24 jours parallélisable**. Vs post-REDO 17-25 j = **+3.5-4 jours** (DEV #50-#54 +
14 DEVs non-cités précédemment + nouvelle Phase 9 CLI test coverage 1.5-2 j —
révisée 2026-05-23 après audit qui a révélé 11 harnesses library déjà shippés en
parallèle par l'agent d'implémentation, scope restant = 17 critiques + 6 non-critiques

- harmonisation des 11 existants).

## DEV coverage matrix (54/54 DEVs)

| DEV | Phase          | Description courte                                       |
| --- | -------------- | -------------------------------------------------------- |
| #1  | 0.1            | Skill auto-detect missing agents (promu pré-foundations) |
| #2  | 7.3            | Agents matrix-aware prompts                              |
| #3  | 7.3            | state-validator FS-truth rule                            |
| #4  | 6.6            | ENFORCE scope doc                                        |
| #5  | 6.6            | PROCESS counter asymmetry doc                            |
| #6  | 3.1            | VERIFY structured events                                 |
| #7  | 2.3            | run --help introspection                                 |
| #8  | 7.1            | Matrix v2.1 events catalog                               |
| #9  | -              | SHIPPED commit 268cbee                                   |
| #10 | 7.1, 4.6       | matrix flag fix + reconcile clarif                       |
| #11 | -              | SHIPPED commit 29c4953                                   |
| #12 | 4.3            | 8 phantom shows cleanup                                  |
| #13 | -              | SHIPPED commit fc39f77                                   |
| #14 | -              | SHIPPED commit 3993487                                   |
| #15 | 1.5            | schema_version row 3 cleanup                             |
| #16 | 2.1            | library-scan CLI                                         |
| #17 | 4.3            | 5 phantom paths cleanup                                  |
| #18 | 1.1            | drift mechanism wire                                     |
| #19 | 1.2            | PRAGMA foreign_keys ON                                   |
| #20 | 2.4, 8.3       | qbit-restart cmd + matrix-CLI test                       |
| #21 | 2.2            | --dry-run on 4 mutators                                  |
| #22 | 6.1            | --format unified                                         |
| #23 | 3.2            | cli_telemetry decorator                                  |
| #24 | 8.13, 10.1.a   | event-bus catalog 13→17                                  |
| #25 | 8.13           | event-bus module budgets                                 |
| #26 | 10.1.a         | events/**init**.py **all**                               |
| #27 | 8.10           | Plan A reset+rescrape                                    |
| #28 | 2.6, 10.1.b    | backfill auto-trigger doc + first run                    |
| #29 | 5.1            | Tests Protocol refactor                                  |
| #30 | 5.3            | Ratings Pydantic boundary                                |
| #31 | 4.7            | Paranoia branch wire                                     |
| #32 | 10.1.c         | media-indexer archive banner                             |
| #33 | 1.10           | PRAGMA bypass multi-site                                 |
| #34 | 1.10           | PRAGMA discipline complete                               |
| #35 | 10.1.c         | scan_modes doc gap                                       |
| #36 | 10.1.c         | media_stream extension doc                               |
| #37 | 1.10           | BEGIN IMMEDIATE audit                                    |
| #38 | 5.2            | TorrentClientFull 2nd vector                             |
| #39 | 10.1.d         | pipeline-obs superseded banner                           |
| #40 | 3.1            | DEV #6 broader (7 per-step cmds)                         |
| #41 | 8.14           | test-coverage branch re-measure                          |
| #42 | 10.1.e         | trailer §4 placement                                     |
| #43 | 10.1.e         | trailer §14 blocking                                     |
| #44 | 10.2.a         | \_exclusions.py docstring                                |
| #45 | 10.1.f, 10.3   | logging.md broken paths                                  |
| #46 | 8.11           | check-module-size hard-block                             |
| #47 | 10.3           | details_payload type drift                               |
| #48 | 10.1.g, 10.2.b | VX leaks                                                 |
| #49 | 8.15           | test_cli @patch trim                                     |
| #50 | 1.7            | \_ensure_disk_row UUID mismatch                          |
| #51 | 1.8            | Enrich oshash retry                                      |
| #52 | 1.8            | Walker oshash retry                                      |
| #53 | 8.12           | \_upsert_media_item dedup + UNIQUE                       |
| #54 | 1.9            | init-canonical mode                                      |

→ **54/54 DEVs couverts par 0.16.0**, 0 différé à 0.17+ (directive opérateur 2026-05-22).

## Patterns P1-P34 → leverage phases

| Pattern | Phase(s)             | Lever                                                               |
| ------- | -------------------- | ------------------------------------------------------------------- |
| P1      | 1.10 + 5.1           | DEV #14 shipped + DEV #33+#34                                       |
| P2      | 1.3 + 1.4            | E2E tests MUST-16+17                                                |
| P3      | shipped + 1.10 audit | DEV #13 shipped + audit autres DDL via PRAGMA lint                  |
| P4      | shipped + 5.1        | DEV #9 shipped + tests refactor DEV #29                             |
| P5      | 1.8                  | hash version-tag effectivement adressé via oshash retry DEV #51/#52 |
| P6      | 7.1                  | Coverage gap matrix                                                 |
| P7+P25  | 3.1                  | Observability gap                                                   |
| P8      | 2.3, 6.2             | Doc rot CLI                                                         |
| P9      | 7.3                  | Agents matrix-aware                                                 |
| P10     | 0.1                  | Agent discovery (promu pré-foundations)                             |
| P11+P34 | 1.1, 4.7, 8.4        | Dead code + dead safety net                                         |
| P12     | 2.1, 5.5, 5.6, 8.8   | CLI surface                                                         |
| P13     | 4.1-4.5              | Hard-delete cleanup                                                 |
| P14     | 1.5                  | Migration residue                                                   |
| P15     | 1.2, 1.6             | Schema vs runtime                                                   |
| P16     | 8.2                  | Empty tables                                                        |
| P17     | 5.5                  | Outbox GC                                                           |
| P18     | 3.1, 3.2, 3.3        | UX rich vs telemetry                                                |
| P19     | 8.6                  | Naming convention                                                   |
| P20     | 2.4, 7.1             | Matrix CLI refs                                                     |
| P21     | 2.2                  | Mutate w/o --dry-run                                                |
| P22     | 6.1                  | Output format                                                       |
| P23     | 5.7, 8.10            | ACCEPTANCE phase gate vs exercise                                   |
| P24     | 1.1, 1.2, 1.6        | Infra invariants not activated                                      |
| P26     | 8.5                  | SRP CLI cmd                                                         |
| P27     | 6.3                  | FS = truth, BDD = projection                                        |
| P28     | 5.1, 5.2, 5.4        | Composition Protocols (refactor tests → migrate callers → drop)     |
| P29     | 6.2                  | CLI = stable API                                                    |
| P30     | 10.1, 10.2, 10.3     | Documentation stale post-archive                                    |
| P31     | 8.11                 | Promesses stallées                                                  |
| P32     | 5.7, 8.9, 8.14, 8.15 | Success criteria                                                    |
| P33     | 1.10                 | PRAGMA discipline                                                   |

→ **34/34 patterns mapped to ≥1 leverage phase**.

## DESIGN sections §9-§16 → phases

| Section                                  | Implementing phase(s)         |
| ---------------------------------------- | ----------------------------- |
| §9 BDD lifecycle invariants              | 1.1, 1.2, 1.6, 4.1, 4.7, 8.10 |
| §10 CLI surface completeness             | 2.1-2.5, 5.6, 6.1, 6.2        |
| §11 Architecture / state ownership       | 5.4, 5.2, 6.3                 |
| §12 Documentation conformity (P30)       | 6.2-6.5, 10.1-10.3            |
| §13 Promise lifecycle (P31)              | 8.11                          |
| §14 Success criteria enforcement (P32)   | 5.7, 8.9, 8.14, 8.15          |
| §15 PRAGMA & connection discipline (P33) | 1.10                          |
| §16 Safety net E2E (P34)                 | 1.1, 1.3, 4.7                 |

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
Phase 0 (skill safety net) ──→ Phase 1 (foundations) ──┬─→ Phase 2 (CLI gaps)
                                                       ├─→ Phase 3 (observability)
                                                       └─→ Phase 4 (path cleanup) ──→ Phase 5 (conformity)
                                                                                          │
Phase 6 (format+docs) ───────────────────────────────────────────────────────────────────┴─→ Phase 7 (matrix v2.1)
                                                                                                            │
                                                                                                            └─→ Phase 8 (polish) ──→ Phase 9 (CLI test coverage) ──→ Phase 10 (archive docs)
```

Phase 0 est sur le repo `.claude/` (branche `personal-scraper`), distinct de Phases 1-8 sur
`personalscraper/fix/tech-debt`. Phase 0 doit être committé AVANT de lancer Phase 1, pour
que les Phases 1-8 bénéficient d'un monitoring `pipeline-monitor` v2.0 capable de détecter
sa propre dégradation.

Phases 2/3 peuvent partiellement paralléliser avec Phase 1 (différentes dimensions).
Phase 6 peut tourner en parallèle de Phase 4/5.

## ACCEPTANCE

Voir `../ACCEPTANCE.md` — **54 criteria exécutables** (49 initiaux + ACC-50..54 Phase 9
CLI coverage) couvrant 54/54 DEVs, 34/34 patterns, 8/8 DESIGN sections,
Phase 0 + Phases 1-10. Chaque criterion est une commande shell avec output attendu.
Le sketch des 15 criteria clés est en `../DESIGN.md` §6.

Status par criterion (✅/❌/🟡) à marquer au fil des phases — finalisation au gate Phase 8.9.

## Implementation conventions

> **Pour les agents indépendants (sub-phase dispatch)** : **READ FIRST** →
> `../AGENT_BRIEFING.md` (règles transverses + baseline BDD + gotchas + read order). Ce
> document est la première lecture obligatoire pour tout sub-agent Sonnet dispatché par
> `/implement:sub-phase`. Sans ça, plusieurs trous critiques peuvent casser l'exécution
> (cross-repo Phase 0/7, Plan A manual launch entre 1.9 et 1.10, ordre Phase 5 logique
> aligné numérique, test ERROR vs FAILED, etc.).

- Chaque sous-phase = 1 commit avec scope `(tech-debt)` (ou `(pipeline-monitor)` pour les
  commits sur `.claude/` — Phase 0 et Phase 7).
- Commits suivent Conventional Commits : `fix(tech-debt): ...`, `feat(tech-debt): ...`,
  `test(tech-debt): ...`, `docs(tech-debt): ...`.
- Phase gate = `chore(tech-debt): phase N gate — <description>` après que toutes les
  sous-phases sont vertes.
- `make check` (lint + test + module-size + typed-api) doit passer à chaque phase gate.
  Voir AGENT_BRIEFING §6.4 pour l'évolution de `make check` au fil des phases.
- Cross-repo phases (0 et 7) : exécution **manuelle** par l'opérateur, NOT for
  `/implement:phase`. Voir banners dans phase-00 et phase-07.
