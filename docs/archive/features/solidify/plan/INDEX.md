# Plan — solidify: Architecture Consolidation (SOLID/DRY, backend + frontend)

Single long-lived branch `refactor/solidify` off `origin/main` in an isolated git
worktree; ONE PR at the end (manual squash by the operator). The plan executes the
fourteen phases P0–P13 defined in [`../DESIGN.md`](../DESIGN.md) §7 — 1:1, in order,
never merged, split, or reordered. Each phase collapses one of the ten consolidation
seams T1–T10 (or a standalone-major batch) into a single-owner implementation, lands
its conformity fixes F1–F8 test-first (failing regression test written and proven to
fail before the fix), and ends green on the full gate. Behaviour is byte-identical
outside the eight enumerated conformity fixes (§6). Every phase-gate commit passes
`make lint && make test && make check` plus phase-targeted residual-import greps and a
smoke import; frontend phases add `npm run lint && npm run typecheck && npx vitest run`;
route/model-changing phases add `make openapi` + committing the regenerated files.
`origin/main` is merged into the branch at any phase boundary where main moved; the
final reintegration merge + PR happens in P13 (operator directive).

## Phases

| # | Phase | File | Status |
|---|-------|------|--------|
| 0 | Worktree safety net + gate parity | phase-00-safety-net.md | [ ] |
| 1 | Pipeline step-spec + shared reporter (T2) | phase-01-step-spec.md | [ ] |
| 2 | Dispatch item template + journal parity (T3) | phase-02-dispatch-template.md | [ ] |
| 3 | CLI boundary + composition root (T7) | phase-03-cli-boundary.md | [ ] |
| 4 | Scraper flow unification (T1) | phase-04-scraper-unification.md | [ ] |
| 5 | Completeness read-model (T4) | phase-05-completeness-readmodel.md | [ ] |
| 6 | Trailers ownership + single truth (T5) | phase-06-trailers.md | [ ] |
| 7 | Scanner walk skeleton (T8) | phase-07-scanner-walker.md | [ ] |
| 8 | API honesty + tracker symmetry + dry-run (standalone) | phase-08-api-honesty.md | [ ] |
| 9 | Web runner engine + acquire hygiene (T6) | phase-09-web-runner-acquire.md | [ ] |
| 10 | Frontend data kit (T9a) | phase-10-frontend-data-kit.md | [ ] |
| 11 | Frontend component decomposition (T9b) | phase-11-frontend-components.md | [ ] |
| 12 | Tests-architecture consolidation (tests) | phase-12-tests-arch.md | [ ] |
| 13 | Docs, gates, module-size zero, reintegration + PR (T10) | phase-13-docs-gates-pr.md | [ ] |

## Dependencies and ordering

The phase order is dependency-correct and binding. Rationale for the ordering:

- **P0 precedes everything.** It installs the safety net (characterization goldens,
  gate parity, memtrace bridge-symbol snapshot) that pins current behaviour before any
  move. No consolidation phase may start until P0's gate is green.
- **P1 → P2.** The dispatch template (P2) uses the shared `record()` reporter and
  status enum introduced in P1; P2's F1 journal parity rides on P1's real-lifecycle
  emission plumbing.
- **P1, P2 → P3.** The CLI boundary decorator (P3) wraps the pipeline commands that,
  by then, call the single-owner `run_*` functions consolidated in P1/P2 (permit/journal
  parity already in place), so the decorator has one call-shape to own.
- **P4 → P5 → P6.** Scraper unification (P4) settles `scraper/` module boundaries first;
  the completeness read-model (P5) is then consumed by the unified scraper, verify,
  indexer, rescraper and web; trailers (P6) consumes T4 `media_completeness` for trailer
  presence and moves modules OUT of `scraper/` after P4 has stopped churning it.
- **P7** (scanner walk skeleton) is largely independent but sequenced after P5 because
  the enrich visitor writes the single `artwork_json`/NFO truth defined in P5.
- **P8** (API/tracker/dry-run) is standalone; **P9** (web runner engine + acquire) is
  sequenced after P8 so the web runners and acquire subscribers consume the neutral
  torrent-error hierarchy P8 introduces.
- **P10 → P11.** Frontend components (P11) consume the hooks, query-key factories and
  formatters extracted in P10.
- **P12** (tests-arch) runs after the backend/frontend seams have settled so the
  consolidated harnesses target the final module shapes.
- **P13** is last: docs sweep, module-size zero-findings assertion, `origin/main`
  reintegration merge, full gate, and the single PR.

## Main-reintegration rule (operator directive)

The branch stays releasable. At **every phase boundary where `origin/main` has moved**
(PR #300 and others may land during this long-lived branch), merge `origin/main` into
`refactor/solidify` (merge, NOT rebase — this is a squash PR), re-run the full gate, and
only then start the next phase. The **final reintegration merge** is performed in **P13**
immediately before opening the PR, followed by a complete gate run and the executable
acceptance criteria ACC-01..15 (DESIGN §10). A finding that fails re-confirmation at the
start of its phase is dropped with a note in `IMPLEMENTATION.md` — never silently.
