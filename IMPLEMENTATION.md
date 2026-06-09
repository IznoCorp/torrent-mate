# Implementation Progress — acquire-lobe

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP5c — acquire/ lobe + single injection handle (minor)
**Version bump**: 0.24.0 → 0.25.0
**Branch**: feat/acquire-lobe
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/143
**Design**: docs/features/acquire-lobe/DESIGN.md
**Master plan**: docs/features/acquire-lobe/plan/INDEX.md

## Phases

| #   | Phase                                                             | File                             | Status |
| --- | ----------------------------------------------------------------- | -------------------------------- | ------ |
| 1   | acquire/ skeleton + AcquireStore + AcquireContext + close() tests | phase-01-package-skeleton.md     | [x]    |
| 2   | build_acquire_context factory + tests                             | phase-02-factory.md              | [x]    |
| 3   | AppContext swap + cli_helpers wiring + wiring tests               | phase-03-appcontext-wiring.md    | [x]    |
| 4   | Layering guard extension (acquire/ → never triage)                | phase-04-layering-guard.md       | [x]    |
| 5   | ACCEPTANCE.md + architecture.md update + make check gate          | phase-05-acceptance-docs-gate.md | [x]    |

## Review cycles

### Cycle 1

- Toolkit: 5 agents (code-reviewer, pr-test-analyzer, type-design-analyzer, silent-failure-hunter, comment-analyzer) on the feat/acquire-lobe diff (PR #143).
- Verdict: faithful, well-tested, DESIGN-conformant skeleton. code-reviewer: 0 findings ≥80% confidence. pr-test-analyzer **independently mutation-verified** the close() non-ownership guard (injected `torrent_client.close()` → 2 tests RED → reverted) + the per_step_boundary None-guard; 0 critical gaps, 0 vacuous tests. silent-failure: no critical silent failure introduced (TrackerConfigError surfaces correctly, close() None-guards correct).
- Retained findings (all **minor** for RP5c — latent/cosmetic): (1) `AcquireContext.close()` docstring "Raises: Nothing" over-promised (3-agent convergence) — holds today (tracker_registry fail-soft, store always None) but inaccurate for a future RP3 raising store; (2) `acquire/__init__` docstring `sort`→`sorter` (no `sort` package); (3) `cb_policy` docstring missing the "reserved/not-yet-threaded" note.
- Ignored (filtered vs DESIGN): per_step_boundary `finally` masking = **pre-existing on main** (not a regression; fault-isolation flagged for RP3, out of RP5c blast radius); pipeline_events/pipeline_protocol guard gap = in-spec (DESIGN §3 enumeration); test/type minors = design-sanctioned (`| None` optionality per §4.4, `runtime_checkable` marker, exact field-set assertion).
- Decision: **Case A** (no critical/major/medium). Applied the 3 doc-only fixes in commit `450bcaa9` (zero behaviour change, 18 acquire tests pass). Loop terminal-clean. merge=manual → handoff to operator for squash merge.

## Next action

All 5 phases done + PR #143 created + CI green + review cycle 1 terminal-clean (3 doc-only fixes applied). **Ready for MANUAL squash merge** (`gh pr merge 143 --squash` or GitHub UI). After merge: next `/implement:feature` archives acquire-lobe.
