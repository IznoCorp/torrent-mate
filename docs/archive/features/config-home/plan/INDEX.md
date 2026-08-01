# Config Home — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `/implement:phase` to execute this plan phase-by-phase. Each phase produces independently-testable deliverables. Sub-phases are one commit each; commit scope is `config-home`.

**Goal:** Relocate the canonical config directory outside every git working tree to `~/.torrentmate/config`, eliminating the "branch arms a prod boot-break" vector.

**Architecture:** Five phases — (1) additive sync engine with golden tests, (2) config_git mini-repo helper + S4 auto-commit, (3) verify check + ecosystem test pins + worktree-invariant, (4) migration script + config pointer changes + reference docs, (5) ACCEPTANCE.md + final gate.

**Tech Stack:** Python 3.12+, json5, typer, pytest, bash, git, PM2, Node (ecosystem.config.js).

## Global Constraints

- Config models stay `extra="forbid"` (strictness is a deliberate choice — DESIGN §4).
- No per-env config copies (operator decision D2 — §2).
- No backward compatibility (<1.0.0 — config/DB/NFO move together — §4).
- Overlay composition semantics unchanged (`config-overlay-layout.md` — §4).
- `resolve_config_path()` untouched (env-first already — §3.1).
- Every `rg` command MUST carry `-t py` / `-g '*.ext'` filter (search-safety rule).
- Every `curl` command MUST carry `--connect-timeout N --max-time N` (network-safety rule).
- Tests are test-first (project convention).
- Commit messages use Conventional Commits with `(config-home)` scope.

---

## Phases

| #   | Phase                                                                                                            | File                                                                 | Status |
| --- | ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------ |
| 1   | Sync engine — additive JSON5 deep-merge + `init-config --sync` CLI + golden tests                                | [phase-01-sync-engine.md](phase-01-sync-engine.md)                   | [ ]    |
| 2   | Config git mini-repo — `config_git.py` helper + S4 auto-commit hook + unit tests                                 | [phase-02-config-git.md](phase-02-config-git.md)                     | [ ]    |
| 3   | Verify + ecosystem tests — `config_home` check + ecosystem test pins + worktree-invariant + integration tests    | [phase-03-verify-and-tests.md](phase-03-verify-and-tests.md)         | [ ]    |
| 4   | Migration + config changes — `migrate-config-home.sh` + `ecosystem.config.js` + `deploy.sh` + git untrack + docs | [phase-04-migration-and-config.md](phase-04-migration-and-config.md) | [ ]    |
| 5   | ACCEPTANCE + final gate — ACCEPTANCE.md (ACC-01..06) + `make check`                                              | [phase-05-acceptance-and-gate.md](phase-05-acceptance-and-gate.md)   | [ ]    |

## Phase Dependencies

```
Phase 1 (sync engine) ──► Phase 2 (config_git) ──► Phase 5 (ACCEPTANCE + gate)
                              │
Phase 1 (sync engine) ──► Phase 3 (verify + tests)
                              │
                              ├──► Phase 4 (migration + config changes)
```

- Phase 2 and Phase 3 both depend on Phase 1 (the sync engine).
- Phase 4 depends on Phase 1 (migration script uses the sync engine).
- Phase 2 and Phase 4 can run in parallel after Phase 1 is complete.
- Phase 5 depends on Phases 2, 3, and 4 (final gate covers all).

## Design Coverage

| DESIGN Section                      | Phase         | How                                                                   |
| ----------------------------------- | ------------- | --------------------------------------------------------------------- |
| §3.3 `init-config --sync`           | Phase 1       | Additive deep-merge engine + CLI + golden tests                       |
| §3.2 Canonical mini-repo            | Phase 2       | `config_git.py` + S4 auto-commit                                      |
| §3.4 Migration + guard tests        | Phase 3       | Verify check + ecosystem test pins + worktree-invariant               |
| §3.1 Relocation (D1, D2)            | Phase 4       | Migration script + ecosystem.config.js + deploy.sh + git ops          |
| §3.4 Migration + guard tests (docs) | Phase 4       | Reference docs, runbook, CLAUDE.md pointers                           |
| §5 ACCEPTANCE criteria              | Phase 5       | ACCEPTANCE.md with ACC-01..06                                         |
| §6 Test plan                        | Phase 1, 2, 3 | Golden tests (P1), unit tests (P2), ecosystem + integration (P3)      |
| §7 Risks                            | Phase 4       | Migration window mitigated by scripted order; comment loss documented |
