# Implementation Progress — tech-debt

**Feature**: Tech-Debt (Global Cross-Feature Fixes) (type: minor)
**Version bump**: 0.15.1 → 0.16.0 (decision item 13 §5)
**Branch**: fix/tech-debt
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/24
**Design**: `docs/features/tech-debt/DESIGN.md` (9 sections + ACCEPTANCE sketch)
**Acceptance**: `docs/features/tech-debt/ACCEPTANCE.md` (73 criteria exécutables — 49 initiaux + ACC-50..54 Phase 9 CLI coverage + ACC-NFO-FIX + ACC-INIT-CANONICAL-SEEDS + ACC-OMDB-QUOTA Phase 8.10.b/c/d + ACC-46..49 Phase 10)
**Master plan**: `docs/features/tech-debt/plan/INDEX.md` (DEV/Pattern/Section cross-tables)

> **HANDOVER.md deleted in Phase 10.4 closure** (was transient session-context doc, obsolete
> post-implementation). Historical context lives in: commits + `audit/01..16.md` (permanent)
>
> - global `MEMORY.md` (user feedback). This IMPLEMENTATION.md is the single tracker.

## Statut actuel

**✅ Audit pré-design 14 items COMPLET** (certains REDO à profondeur audit-quality).
**✅ Coverage 100% atteinte** : 54/54 DEVs + 34/34 patterns + 8/8 sections DESIGN.
**✅ 4 fixes critiques déjà shipped** : DEV #9, #11, #13, #14.

### Known flaky / env-dependent tests (NOT introduced by tech-debt 0.16.0)

Identified on baseline `a5420d8` by parallel worktree run; intermittent on
HEAD too. None block phase gates — re-run usually clears them. Cited here so
future sessions don't waste time chasing them as new regressions.

**Env-dependent** (3 — fail under `make test`, pass in isolation; missing
`_mock_cli_config_load` autouse fixture; failure message "No config.json5
found"):

- `tests/skill/test_matrix_cli_refs.py::test_matrix_file_exists`
- `tests/skill/test_matrix_cli_refs.py::test_matrix_cli_ref_valid[info ...]`
- `tests/indexer/scanner/test_init_canonical.py::test_library_init_canonical_cli_command_exists`

**Test pollution** (2 — pass in isolation, fail in full suite under
pytest-xdist; ordering / shared module state):

- `tests/unit/test_qbittorrent.py::TestBuildClient::test_returns_authenticated_client`
- `tests/unit/test_qbittorrent.py::TestQBitClient::test_login_logout`

**Mitigations applied 2026-05-23 (commit pending)**:

- Env-dependent 3 **mitigated**: extended `_mock_cli_config_load` autouse
  fixture in `tests/conftest.py` to also cover `test_matrix_cli_refs.py` +
  `test_init_canonical.py` (was previously scoped to test_cli.py /
  test_logger_cli.py only). 4 consecutive `make test` runs post-fix:
  4969 passed each.
- Test pollution 2 **NOT yet mitigated** — not reproducible on HEAD in
  4 consecutive runs. Suspected root cause: xdist worker state leak from
  a prior test that patches `httpx.Client` or `aiohttp.ClientSession`
  module-level without proper teardown. Future work (Phase 8 candidate):
  add a `_qbit_module_reset` autouse fixture in `tests/unit/conftest.py`
  that re-imports `personalscraper.api.torrent.qbittorrent` between tests.

DESIGN.md + ACCEPTANCE.md + plan/ (9 phases) produits et committed. Estimate revised :
**19-27 jours séquentiel, 15-22 jours parallélisable**.

**Prochaine action** : Phase 0 sur `.claude/` (DEV #1 promu), puis `/implement:phase` pour Phase 1 (Foundations BDD/indexer +
PRAGMA + bonus DEVs #50-#54).

4 fix commits déjà shipped sur priorité absolue user (DEV #9, #11, #13, #14). 6 phases doc
audit committed (items 5-13).

## Audit pré-design (14 items)

Méthode : un par un, validation utilisateur entre chaque, communication en français, rien hors scope.

| #   | Item                                                   | Type           | Output attendu                        | Status                                                                                                                                                                                                                                                                                                        |
| --- | ------------------------------------------------------ | -------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Étude des dérives des plans (cross-feature)            | Analyse        | Rapport patterns + causes racines     | [x] (audit/01-plan-drift.md)                                                                                                                                                                                                                                                                                  |
| 2   | Étude du pipeline et de son fonctionnement             | Analyse        | Carto pipeline + invariants           | [x] (audit/02-pipeline-cartography.md)                                                                                                                                                                                                                                                                        |
| 3   | Brainstorm MAJ skill pipeline-monitor                  | Brainstorm     | Liste changements à apporter          | [x] (audit/03-skill-update-brainstorm.md + Q1-Q10 décidées)                                                                                                                                                                                                                                                   |
| 4   | MAJ skill pipeline-monitor                             | Implémentation | Skill mise à jour committée           | [x] (matrix v2.0 + SIGINT + 4 agents + SKILL.md + host.py)                                                                                                                                                                                                                                                    |
| 5   | Run pipeline-monitor (avec skill mise à jour)          | Analyse        | DEVIATION LIST + Conformity Check     | [x] (docs/pipeline-runs/2026-05-21-17h16-pipeline-run.md — 12 DEV ; DEV #9 critique data-loss + DEV #11 majeur merkle non-déterministe traités hors-scope sur priorité absolue user)                                                                                                                          |
| 6   | Brainstorm améliorations suite au pipeline-monitor     | Brainstorm     | Liste items pour le design            | [x] (audit/04-pipeline-monitor-brainstorm.md — 10 patterns P1-P10 + 33 items A-AG triés must/should/nice)                                                                                                                                                                                                     |
| 7   | Check BDD (intégrité, conformité, cohérence, améliors) | Analyse        | Rapport BDD                           | [x] (audit/05-bdd-audit.md — DEV #15-#19 nouveaux ; cause racine décomposée pour DEV #12 ; 4 nouveaux patterns P11-P14)                                                                                                                                                                                       |
| 8   | Brainstorm améliorations BDD                           | Brainstorm     | Liste items pour le design            | [x] (audit/06-bdd-brainstorm.md — 37 items BD-A..BD-AK + 3 nouveaux patterns P15-P17 + plan 5 phases BDD 9-14j)                                                                                                                                                                                               |
| 9   | Analyse commandes CLI (bugs, design, améliorations)    | Analyse        | Rapport CLI                           | [x] (audit/07-cli-audit.md — 31 entry points inventoriés ; 4 DEV #20-#23 ; 3 patterns P20-P22 ; 20 items CL-A..CL-T)                                                                                                                                                                                          |
| 10  | Brainstorm améliorations CLI                           | Brainstorm     | Liste items pour le design            | [x] (audit/08-cli-brainstorm.md — 14 items exploratoires CL-U..CL-AN ajoutés ; plan 7 phases CLI ; tableau global multi-dim 13-22j)                                                                                                                                                                           |
| 11  | Analyse app + conformité design                        | Analyse        | Rapport conformité globale            | [x] **REDO audit-quality** (audit/09-conformity.md — 13 features audités exhaustivement ; 235 claims vérifiées ; 26 DEVs #24-#49 + 5 BONUS DEVs #50-#54 trouvés en reindex BDD attempt 2026-05-21 ; 5 patterns P30-P34 ; provider-ids ACCEPTANCE re-grade 4/10 ✅→❌🟡 ; +2-3 j → +3-4 j sur estimate 0.16.0) |
| 12  | Analyse critique design + architecture                 | Analyse        | Rapport critique structurel           | [x] (audit/10-architecture-critique.md — 7 critiques structurelles A-G ; 4 patterns P26-P29 ; 7 items AR-A..AR-G ; net 1-2 j 0.16.0)                                                                                                                                                                          |
| 13  | Brainstorm améliorations globales                      | Brainstorm     | Synthèse de tous les brainstorms      | [x] (audit/11-global-synthesis.md — 15 MUST + 26 SHOULD + ~39 NICE déférés ; 29 patterns P1-P29 tous mappés ; plan 8 phases ; 13-19 j estimés)                                                                                                                                                                |
| 14  | Challenge final du design + plan tech-debt             | Validation     | DESIGN.md + plan/ propres (non-draft) | [x] (DESIGN.md + plan/INDEX.md + 8 phase files ; drafts supprimés ; 15 ACCEPTANCE criteria executables ; bump 0.16.0 MINOR decided)                                                                                                                                                                           |

## Phases d'implémentation

Voir `docs/features/tech-debt/plan/INDEX.md` pour le détail. **10 phases** (Phase 0 ajoutée
2026-05-22 — DEV #1 promu pré-foundations sur la review opérateur) ordonnées par dépendances :

| #    | Phase                                                                                                                                     | File                      | Effort  | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0    | Pre-Foundations: skill safety net (DEV #1)                                                                                                | phase-00-skill-safety.md  | 0.5 j   | [x] `66943ce` (.claude/personal-scraper)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 1    | Foundations BDD/indexer + PRAGMA + bonus                                                                                                  | phase-01-foundations.md   | 3-4 j   | [x] gate `83446f9`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 2    | CLI gaps + backfill-ids first run                                                                                                         | phase-02-cli-gaps.md      | 2 j     | [x] gate `1ccba80`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 3    | Observability (broadened DEV #6 → 7 cmds)                                                                                                 | phase-03-observability.md | 2 j     | [x] gate `3a5930f`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 4    | Path + paranoia branch (DEV #31)                                                                                                          | phase-04-path-cleanup.md  | 2-3 j   | [x] gate `f331252`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 5    | Conformity (drop Protocols + Pydantic)                                                                                                    | phase-05-conformity.md    | 2-3 j   | [x] gate `0b8b052`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 5.9  | NTFS cache pressure (audit/12 integration)                                                                                                | (no formal phase file)    | 1 j     | [x] gate `4787b64`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 5.10 | Process Hardening (drift-detect + phase-gate + briefing v2 + drafts)                                                                      | (no formal phase file)    | 1 j     | [x] gate `f3e5684`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 5.11 | Corrections (IMPL+ACC+plan sync + ACC-NTFS + drift-detect refine)                                                                         | (no formal phase file)    | 0.5 j   | [x] gate `3ae51c3`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 5.12 | Incident response BDD (BD-D #1 + #2 + BD-INIT-CANONICAL + relink tx rollback)                                                             | (no formal phase file)    | 0.5 j   | [x] 4 fix commits + 22 regression tests : `c5e2bbd` cascade hard-delete path / `00599f8` merkle refresh + detector empty-set / `3df78e0` init_canonical fallback imdb→tmdb + observability / `9997f70` relink BEGIN IMMEDIATE wrap for dry-run rollback                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 6    | Format + heavy doc work                                                                                                                   | phase-06-format-docs.md   | 3-4 j   | [x] gate `f1f4fe3` (--format flag + commands.md 39 entries + architecture state ownership + indexer lifecycle + backfill runbook + ENFORCE/PROCESS doc)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 7    | Matrix v2.1 + agents matrix-aware                                                                                                         | phase-07-matrix-v21.md    | 1-2 j   | [x] gate `a1eb322` (.claude/personal-scraper — matrix v2.1 + skill v2.1 + 7 agents matrix-aware + CHANGELOG)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 8    | Polish + Plan A reset + size hard-block                                                                                                   | phase-08-polish.md        | 3-4 j   | [x] 14/15 sub-phases DONE + 1 PARTIAL (8.10 Plan A retry = operator action, runbook ready at `audit/16`). Sub-phase commits: 8.1 `5426826` / 8.2 `ba47124` / 8.3 `017ea7b` / 8.4 `92c4d11` / 8.5 `771e630` / 8.6 `0c6886d` / 8.8 `0376222` / 8.9 `addab31` / 8.10 `0da47b1` (PARTIAL) / 8.11 `58c63d3` / 8.12 `bcb2065` / 8.13 `fb96adb` / 8.14 `15a5a2e`+`b27de8b`+`0c3bc33` / 8.15 `60d910d`+`df723b5`+`1cd653a`. Pre-gate: format pass `5e4e183` + test allowlist fix-up `<pending>`. Known: 3 pre-existing lint-logging ERRORs in `cli_helpers/output.py` (legit user-facing prints — needs `check_logging.py` exception mechanism, Phase 10 candidate); 3 pre-existing test failures (#1 `test_entry_exists`, #2 `test_jumanji`, #3 `test_verify_disk_filter` — none Phase 8 introduced).                                                                                                                                                                   |
| 9    | CLI Test Coverage (NEW — absorbe 8.7 SH-25 ; **20/20 library + 7/7 pipeline + 4/4 trailers/config + 4/4 non-library + 20/20 harmonized**) | phase-09-cli-coverage.md  | 1.5-2 j | [x] all sub-phases DONE. 9.1 helpers+pin (`f32848b`+`a66c411`, 40 pin tests, 26 helpers); 9.2.a (`dfd3d64`+`f80a0a4`+`8d0ba32`, 31 tests); 9.2.b (`fb28464`+`cb30da8`+`300520a`, 36 tests); 9.2.c (`c2b39da`, 18 tests); 9.5 (`d66c048`+`e877902`+`42f1a5c`+`efce0fe`, 47 tests); 9.6 (`a8549be`+`804bb19`+`5d5c30b`+`294cf76`, 17 tests); 9.7.a/1 5 commits c3d8b07..e39cbca +27 tests; 9.7.a/2 `5c52e2a` +27 tests; 9.7.a/3 5 commits c99f169..96dcbe8 +24 tests; 9.7.a/4 5 commits d902f34..bc56856 +26 tests; 9.7.b script+matrix+Makefile (`ea6a04d`+`eeb4745`); 9.7.b/fix close 22 gaps (`0c0e737`+`274fb20`+`265b21d`). Pre-gate: format pass `640845a` + cli_helpers/output.py typer.echo + fix_nfo PRAGMA `3876636`. Total Phase 9 = +261 new tests + cli-coverage-report tool. ACC-50..54 all ✅. Known: 3 pre-existing test failures from Phase 8 still present (test_entry_exists, test_jumanji, test_verify_disk_filter — none Phase 9 introduced). |
| 10   | Archive DESIGN.md updates (**8 features** — arch-cleanup added)                                                                           | phase-10-archive-docs.md  | 1-2 j   | [x] all DONE. Sub-phase commits: 10.1/1 (`9c2c801`+`5350b54`+`8f38a92`+`693acb5`) event-bus/provider-ids/media-indexer; 10.1/2 (`7064713`+`05b64da`+`5fadadc`+`0e64616`+`6af0218`) pipeline-obs/trailer/logging(MISSED-in-329afbc)/legacy-cleanup + ACC-46 ✅; 10.2 (`cbbc408`+`4a73e5c`+`2e917a9`) `_exclusions.py` placeholder + 5 alpha refs archived to `docs/archive/legacy-alpha/` + 4 inline rewrites; 10.3 (`651726c`+`3a89ba5`) arch-cleanup 8th banner + ACC-49 ✅ (DEV #45+#47+#24 closed); 10.4 (`fb36cd9`+`74219f2`) HANDOVER.md deleted + IMPL header cleaned. Gate: `<this commit>`. 8/8 archive banners, 0 VX leaks outside `docs/archive/`, ACC-46..49 all ✅.                                                                                                                                                                                                                                                                                  |
| 11   | Aggregated DeepSeek 5-angle review fixes (18 findings)                                                                                    | phase-11-review-fixes.md  | 2-3 j   | [ ] 7 sub-phases : 11.1 durability fsync (M1+S1+S2), 11.2 stats ordering (M2+M3), 11.3 AppleDouble filter shared+everywhere (M4), 11.4 pytest.raises narrow (M5), 11.5 regex+misc (S3+N1+N2+N3), 11.6 module decomposition (S4+S5 — Opus 1M), 11.7 polish (S6+N4..N9). Source : review parallèle 5 agents DeepSeek 2026-05-24.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |

**Total post coverage-fix + Phase 9 CLI Coverage** : **20.5-29 jours séquentiel,
16.5-24 jours parallélisable** (Phase 9 révisée 2026-05-23 — 1.5-2 j au lieu de 2-3 j
après audit révélant 11 harnesses library E2E déjà shippés par l'agent d'implémentation
parallèle ; scope restant = 17 critiques + 6 non-critiques + harmonisation 11 existants).

Coverage finale : **54/54 DEVs** couverts + **34/34 patterns P1-P34** leveraged + **8/8
sections DESIGN §9-§16** implémentées. 0 différé à 0.17+ (directive opérateur 2026-05-22).

Voir `docs/features/tech-debt/plan/INDEX.md` § "DEV coverage matrix" + § "Patterns P1-P34
→ leverage phases" + § "DESIGN sections §9-§16 → phases" pour les cross-tables exhaustives.
54 ACCEPTANCE criteria exécutables en `docs/features/tech-debt/ACCEPTANCE.md`
(49 initiaux + ACC-50..54 Phase 9 CLI coverage).

## Already shipped (priority absolue user, hors-plan)

| SHA       | DEV | Description                                                       |
| --------- | --- | ----------------------------------------------------------------- |
| `268cbee` | #9  | repair_root_duplicate inversion fix (data-loss)                   |
| `29c4953` | #11 | compute_merkle_root sort-key determinism                          |
| `fc39f77` | #13 | \_recreate_indexes IF NOT EXISTS (C5 race workers)                |
| `3993487` | #14 | \_build_disk_fingerprints + \_sample_fresh_fingerprints alignment |

## Phase 1 sub-phase progress

Phase 1 partially shipped tactically (2026-05-23) before handing off to
`/implement:phase` :

| Sub-phase | SHA       | DEV | Description                                                  |
| --------- | --------- | --- | ------------------------------------------------------------ |
| 1.1       | `38cdcd6` | #18 | wire mark_missed_files into library-index CLI flow           |
| 1.2       | `1320efc` | #19 | pre-check FK orphans at open_db, raise IndexerFKOrphansError |

Remaining Phase 1 sub-phases to dispatch via `/implement:phase` :
1.3 (E2E miss-strike lifecycle test), 1.4 (E2E scan→reconcile=clean test),
1.5 (schema_version row 3 backfill + migration 006), 1.6 (PRAGMA integrity_check
at boot), 1.7 (\_ensure_disk_row UUID fix, DEV #50), 1.8 (oshash retry,
DEV #51+#52), 1.9 (init-canonical CLI, DEV #54), 1.10 (PRAGMA discipline
multi-site, DEV #33+#34).

**Inter-sub-phase action between 1.9 and 1.10** : operator launches Plan A
backfill in background (see `phase-01-foundations.md` §1.9 post-commit note).
`/implement:phase` must NOT auto-continue to 1.10 — it will surface to the
operator as a checkpoint.

## Item 4 — clos (2026-05-21)

Réalisé en 5 sous-phases, 2 repos en parallèle. Branches : `.claude/personal-scraper`
(skill + agents + matrix) et `personalscraper/fix/tech-debt` (pipeline.py).

| Sous-phase | Repo                            | SHA       | Livrable                                                                                                                                                                                                                                                      |
| ---------- | ------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.1        | `.claude/personal-scraper`      | `110f3ae` | Matrix v2.0 : 9 StepReports, 5 catégories (ACCEPTANCE_FAIL), 19 invariants AD–AV, pré-recovery, connexes                                                                                                                                                      |
| 4.2        | `personalscraper/fix/tech-debt` | `f0208e4` | SIGINT inter-step : `Pipeline.request_shutdown()`, `_PipelineInterrupted`, handler installé en `run()`, restauré en finally. 11 tests de régression.                                                                                                          |
| 4.3        | `.claude/personal-scraper`      | `77b7946` | 4 agents : `pipeline-event-monitor`, `pipeline-invariant-checker`, `pipeline-bdd-validator`, `pipeline-matrix-stale-detector`                                                                                                                                 |
| 4.4        | `.claude/personal-scraper`      | `df19183` | SKILL.md v2.0 : `MATRIX_VERSION` assertion, 9 StepReports, 5 catégories, `--remediate` flag (read-only par défaut), wrapping process (Q5), simulation mode (BJ), weird outputs log (BK), library-reconcile cross-correlation (BL), compare précédent run (BM) |
| 4.5        | `.claude/personal-scraper`      | `d0a666b` | `host.py` (wrapping Python + JSONL dump), `CHANGELOG.md`, sync matrix↔skill, doc dans `.claude/CLAUDE.md`. Audits config-health-checker + skill-dependency-checker : HEALTHY.                                                                                 |

Méthode : validation utilisateur entre chaque sous-phase respectée.

## Review cycles

_(rempli par implement:pr-review — max 3 cycles)_

## Next action

Audit pré-design terminé + review terminée (2026-05-22). **Démarrer Phase 0** (pré-foundations,
DEV #1 promu) sur le repo `.claude/` branche `personal-scraper` AVANT de lancer
`/implement:phase` pour Phase 1+.

Lectures préalables avant Phase 0/1 :

- `docs/features/tech-debt/DESIGN.md` (sections §9 BDD, §10 CLI, §11 architecture)
- `docs/features/tech-debt/plan/INDEX.md` (graphe de dépendances)
- `docs/features/tech-debt/plan/phase-00-skill-safety.md` (DEV #1 promu)
- `docs/features/tech-debt/plan/phase-01-foundations.md`
- `docs/features/tech-debt/audit/11-global-synthesis.md` (master backlog)

Méthode : continuer la validation par phase utilisateur (cohérent avec la méthodologie
audit). Chaque phase = N sous-phases + phase gate commit + `make check` vert.

## Branch coverage re-measured (2026-05-24, Phase 8.14, DEV #41)

**Measured**: `make test-cov` on `fix/tech-debt` at baseline `fb96adb`.
Coverage XML `branch-rate`: **87.09 %** (4809 covered / 5522 valid branches).
Line coverage: 93.26 % (17891 / 19184). Combined metric (what `--cov-fail-under=90`
checks): 91.88 % — gate passes. Total: 4843 passed, 4 failed (pre-existing, see below),
4 skipped, 2 xfailed.

**Historical reference**: 91 % branch coverage claimed at test-coverage Phase 1
final gate (`71c8926`). Delta: **-3.91 pp** → within the ±5 pp acceptable drift
band. No follow-up audit triggered.

**4 pre-existing test failures** (all reproduce in isolation, not introduced by
tech-debt 0.16.0):

- `tests/dispatch/test_dispatcher.py::TestResolveExistingOnFilesystem::test_entry_exists_and_path_valid_returns_entry`
- `tests/dispatch/test_media_index.py::TestFuzzyGuards::test_jumanji_matches_jumanji`
- `tests/commands/test_library_verify_e2e.py::test_verify_disk_filter_restricts_scope`
- `tests/scripts/test_audit_cli_coverage.py::test_domain_cli_coverage_no_warnings_on_current_codebase`

**fail_under**: 90 (verified via `python3 scripts/get_coverage_threshold.py`).
