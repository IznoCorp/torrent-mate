# Registry Feature — Retrospective

**Feature**: ProviderRegistry (Scraper Orchestrator Decoupling)
**Branch**: `feat/registry` (merged to main via PR #27 on 2026-05-26)
**Audit date**: 2026-05-27

Honest audit of process / structural / discipline lapses during the registry feature. Items captured here are NOT actionable as remediation phases — they're lessons for future features. Each item names a behavior, why it happened, and how to prevent it.

---

## Process items (not addressable by code phases)

### Item #3 — DESIGN was repeatedly amended mid-execution

**What happened**: DESIGN.md §5.3 (LockedProvider sentinel-token), §6.2 (chain semantics enumeration of trigger reasons), §6.3 (FanOutResult shape), and §7.2 (validate_config aggregated families) all received material edits during cycles 1+2 fix-up commits — AFTER initial DESIGN review approval.

**Why it happened**: PR review found real architectural gaps. The choice was either (a) update DESIGN to match new understanding, or (b) ship implementation that contradicted DESIGN. Cycle 2 chose (a).

**Why it's a problem**: DESIGN.md is supposed to be the immutable contract that the implementation aims at. When DESIGN drifts under implementation pressure, the contract loses meaning. Future readers can't tell "what was originally planned vs what survived contact with reality."

**Lesson**: Add a `## Revision history` section to DESIGN.md from day 1. Every cycle-2 amendment goes in that section with a one-line note explaining what the original gap was. Reviewers can then trust DESIGN.md as the current-truth document while preserving traceability.

**Prevention next time**: At Phase 0.5 (validation phase), force a "Are we sure DESIGN is complete?" gate. If gaps surface in cycle 2, the contract was incomplete — log a retrospective entry on the original DESIGN review process.

---

### Item #9 — DeepSeek truncations happened 4 times without process improvement

**What happened**: Sub-phases 0.2, 0.4, 5.2, 5.5 all hit DeepSeek truncation budgets (max_turns or 10-min wrapper timeout). Each was handled individually (rollback + Opus retry, inline commit + continuation, etc.) but the orchestrator never adjusted its routing heuristics mid-feature.

**Why it happened**: The decision tree in `references/scope-sizing.md` was applied per-sub-phase. After 2-3 truncations, a smarter orchestrator would have raised the bar (route 3-file scopes to Opus, not just 7+).

**Lesson**: Track per-feature truncation rate. After 3 truncations in one feature, escalate the routing threshold by 1 file. The threshold becomes feature-adaptive instead of static.

**Prevention next time**: Add a counter to IMPLEMENTATION.md: "DeepSeek truncations: N". If N ≥ 3, automatically raise routing bar for remaining sub-phases.

---

### Item #10 — Main session committed source code 3 times in violation of spec

**What happened**: `/implement:phase` spec explicitly states "The main session never commits source code — only IMPLEMENTATION.md updates. All source code commits are made by Sonnet subagents via /implement:sub-phase." This was violated when DeepSeek truncations forced inline continuation by Opus main session.

**Why it happened**: Truncation recovery required Opus to finish work mid-flow. The cleanest path was inline commits rather than re-dispatching DeepSeek (which would re-truncate).

**Why it's a problem**: Erodes the discipline boundary. If Opus can commit "in emergencies," the rule becomes negotiable. Next time, the threshold drops.

**Lesson**: When DeepSeek truncates mid-edit, do NOT inline-commit from main session. Instead: (a) recover working state, (b) re-shard the sub-phase into 2 smaller dispatches, (c) re-dispatch DeepSeek (or escalate to Opus subagent). The "Opus inline commits" path should not exist — and didn't, until cycle 1.

**Prevention next time**: Add a hook that blocks `git commit` from main session except when staged files match `^(IMPLEMENTATION\.md|docs/features/[^/]+/(plan|RETROSPECTIVE)\.md|docs/features/[^/]+/plan/.*\.md)$`. Source files staged + main session commit = hook refuses.

---

### Item #11 — Continuous flow conflicted with "always --dry-run first" memory rule

**What happened**: User memory `feedback_pipeline_dry_run_first.md` mandates `--dry-run` before every personalscraper pipeline step. During registry implementation, no production pipeline runs were attempted — but the continuous-flow execution between phases meant the user had no checkpoint to redirect even if registry behavior had caused dispatch issues.

**Why it happened**: Registry is plumbing — no pipeline test path was exercised end-to-end. The dry-run rule is about pipeline operations, not about implementation phases.

**Why it's a problem**: The two rules ("continuous flow between phases" + "always dry-run first") are compatible only IF the orchestrator distinguishes implementation phases from operations phases. Currently they're enforced uniformly by `/implement:phase` which doesn't know about dry-run.

**Lesson**: For features that touch pipeline behavior (registry, dispatch, ingest, sort, process), Phase N should include a "Pipeline smoke test (dry-run)" sub-phase that's explicitly NOT skipped in continuous flow. The user is asked to validate the dry-run output before proceeding.

**Prevention next time**: When a feature touches pipeline step semantics, mandate one sub-phase per affected step with a dry-run gate. Registry didn't trigger this because no pipeline step semantics actually changed (chain semantics never reached production — see Phase 7 remediation plan).

---

### Item #23 — Phase 0.5a violated `feedback_event_bus_no_deferral` mid-feature

**What happened**: Sub-phase 0.5a used `event_bus: EventBus | None` to "defer wiring to a later phase." This violated the absolute rule `feedback_event_bus_no_deferral` saying every step must wire event_bus immediately. Caught by `test_event_bus_required_signatures.py` at gate time.

**Why it happened**: The sub-phase author (DeepSeek) reasoned "I'll get tests passing first, wire event_bus at 0.5b." That's local-optimal thinking incompatible with the absolute rule.

**Why it's a problem**: Absolute rules require constant vigilance. Local optimization for "make this sub-phase pass" defeats them.

**Lesson**: The memory `feedback_event_bus_no_deferral.md` must be injected into every sub-phase prompt that touches event-bus-relevant code, not just trusted to be remembered.

**Prevention next time**: Add to `/implement:sub-phase` prompt template:

```
ABSOLUTE RULES (memory-pinned, no exceptions):
- event_bus: EventBus (NOT EventBus | None) — must be wired immediately in any signature change
- Tests must verify the wired emission, not just construction
```

---

### Item #24 — `feedback_regression_test_per_bug` honored inconsistently

**What happened**: Two real bugs were detected during the feature:

- Test pollution from sub-phase 2.5 (module-level monkeypatches) → fix landed but no regression test was added.
- DeepSeek truncation in 5.2 leaving working-tree dirty → handled by manual recovery, no test/safeguard added.

The memory `feedback_regression_test_per_bug.md` says every bug detected must have a regression test. Both fixes broke this rule.

**Why it happened**: Time pressure inside cycle 2 fix-up commits. Adding a regression test for a process bug ("DeepSeek truncated, manually recovered") doesn't map cleanly to a pytest test.

**Why it's a problem**: Process bugs without regression tests reoccur. We had 4 DeepSeek truncations in this feature alone — each handled ad-hoc.

**Lesson**: For code bugs → regression pytest test (cleanly fits the rule). For process bugs → regression entry in `docs/process-regressions.md` (or similar) with: incident description + detection method + recovery procedure. A "regression test" for a process bug is documentation of how to detect-and-recover next time.

**Prevention next time**: When a fix is committed, the post-commit hook (or human checklist) should ask: "Is there a test that would have caught this? If no, add one (or document why none is possible)."

---

### Item #25 — IMPLEMENTATION.md update granularity drifted

**What happened**: IMPLEMENTATION.md was updated at every phase gate (correct per spec) but the in-flight sub-phase rows showed `[ ]` even when work was 80% done. Cycle 2 also added phase rows AFTER the work landed (Phase 6 doc-only) rather than before, breaking the "plan first, execute second" invariant.

**Why it happened**: Cycle 2 fix-ups were reactive (PR review surfaced gaps; the fix happened immediately; the plan caught up after). Convenient but reverses the discipline.

**Why it's a problem**: A reader of IMPLEMENTATION.md can't tell "this row was a planned phase" vs "this row was a reactive cleanup." The plan retroactively becomes a log instead of a forward declaration.

**Lesson**: When cycle-2 work is identified, add the phase row to IMPLEMENTATION.md FIRST with a `[ ]` status + brief description, commit, THEN dispatch. The commit history shows plan-first, work-second.

**Prevention next time**: Add to `/implement:pr-review` Step 5: "Before dispatching `/implement:phase` for the fix phase, write the IMPLEMENTATION.md row + commit it. The phase row is a contract, not a log entry."

---

### Item #26 — Cost estimates absent from sub-phase plans

**What happened**: The original phase plans (Phase 0-5) had no cost estimates ("DeepSeek ~10 min", "Opus 1M ~30 min"). At the post-merge audit, the supplementary phase plans (7-13) DO have cost estimates. The original ones didn't because the costing discipline wasn't established at feature-design time.

**Why it's a problem**: Without cost estimates, scope decisions are made blind. "Is this sub-phase worth 30 min of DeepSeek or 5 min of Opus?" can't be answered.

**Lesson**: Every sub-phase plan must include a one-line cost estimate. The estimate is rough (≤ 15 min / 15-30 min / 30+ min buckets) but its presence forces the question.

**Prevention next time**: Add to `/implement:plan` Sonnet prompt template: "Each sub-phase plan must include a `## Cost estimate` section with dispatcher + time estimate."

---

### Item #27 — Drafts/ preservation worked but was never used

**What happened**: The `/implement:sub-phase` prompt template includes a "drift-mid-task preservation" instruction: out-of-scope findings should be written to `docs/features/{codename}/drafts/`. During this feature, ZERO drafts were created. Either there were no drift findings (unlikely — cycle 1 review found 8) or they were silently absorbed into the current phase.

**Why it happened**: Most likely: drift findings during sub-phase execution were silently in-scoped because they were small and "felt like cleanup." This violates the scope-discipline norm.

**Why it's a problem**: The drafts/ folder is a release valve for "this is valuable but out-of-scope." When ignored, scope creep happens silently.

**Lesson**: Audit drafts/ folder at every phase gate. If empty after a long feature, ask: "Did we silently in-scope drift findings? List them."

**Prevention next time**: Add to `/implement:check` Check 4 (scope drift): if drift detected, REQUIRE writing to drafts/ before accepting the sub-phase. No silent in-scoping.

---

## Structural items (architectural lessons)

### Lesson — Framework-only features need explicit "production consumer" phase

The registry was the first feature in this codebase that shipped a framework without a production consumer migration in the same PR. Phase 1+2 delivered the framework; Phase 3 was characterization tests for the OLD system; Phase 4 was a doc consolidation. Production migration was deferred to "later" — but never planned.

This is structurally broken: framework-only features look complete (tests pass, docs exist) but deliver zero user-visible value. The next feature of this shape MUST include a "migrate first consumer" phase in the original plan, not as remediation.

### Lesson — Capability protocols need usage examples, not just definitions

The 11 capability protocols are defined in `personalscraper/api/contracts/capabilities.py` with method signatures + docstrings. But NO doc shows a complete usage example end-to-end. New contributors will struggle to know "when do I use chain vs fan_out vs locked vs direct vs cross_ref?" without examples.

`docs/reference/scraping.md` should have a "Capability Cookbook" section with 4-6 worked examples (one per Mode partition + cross_ref + locked) showing real call sites.

### Lesson — TDD with `@pytest.mark.xfail(strict=True)` is powerful but underused

Sub-phase 0.5b empirically proved chain iteration worked against fake providers. But the test was written AFTER the framework was scaffolded, not before. Real TDD would have:

1. Write `test_chain_falls_back_on_5xx` with `@pytest.mark.xfail(strict=True)` — fails because the framework doesn't exist yet.
2. Implement framework.
3. Remove `xfail` marker — test goes green.

This is the discipline the brainstorm phase promised but the implementation didn't deliver. Next feature: enforce TDD-first by writing the xfail-strict test as Phase 1 sub-phase 1, and the implementation as sub-phase 2.

---

## Items deferred to supplementary phases (NOT covered here)

The following items ARE actionable as code phases — see the supplementary phase plans:

| Item #                  | Phase            | Title                                            |
| ----------------------- | ---------------- | ------------------------------------------------ |
| #1, #2, #12, #29, #30   | Phase 7          | Chain semantics in production (THE BIG ONE)      |
| #4, #5, #6, #7, #8, #28 | Phase 8          | Type design hardening                            |
| #13, #14, #15, #16, #17 | Phase 9          | Test infrastructure cleanup                      |
| #20                     | Phase 10         | Module size extraction (`existing_validator.py`) |
| #18                     | Phase 11         | Indexer migration                                |
| #19                     | Phase 12         | ROADMAP entries for deferrals                    |
| #21                     | Phase 13         | Pre-existing fixes (flaky test)                  |
| #22                     | (done in-flight) | `TRAKT_CLIENT_ID` added to `.env.example`        |

The 9 retrospective items above (#3, #9, #10, #11, #23, #24, #25, #26, #27) cover the process/discipline gaps that don't fit a code phase.

---

## Summary scorecard

| Dimension              | Grade | Note                                                                           |
| ---------------------- | ----- | ------------------------------------------------------------------------------ |
| Framework completeness | A     | All 6 operations + 11 capabilities + 5 events shipped                          |
| Production migration   | D     | Framework is unused in production (Phase 7 remediation needed)                 |
| Type design rigor      | B-    | Static guarantees promised in DESIGN not delivered (Phase 8)                   |
| Test infrastructure    | C+    | Coverage adequate, but autouse fixture + Fake\* heuristic are smells (Phase 9) |
| Process discipline     | C     | 4 truncations, 3 main-session source commits, 0 drafts/ entries                |
| Documentation          | A-    | DESIGN + ACCEPTANCE + 11 reference doc additions                               |
| ROADMAP follow-through | F     | 3 deferrals had no ROADMAP entry created (Phase 12 remediation)                |

**Overall**: a framework that looks complete but isn't, shipped fast with process shortcuts. The supplementary phases (7-13) bring the feature to "actually complete." The retrospective items (#3, #9, #10, #11, #23, #24, #25, #26, #27) are for the next feature, not this one.

---

## How this retrospective will be used

1. **Phase 7-13 plans**: ready to dispatch in priority order. Phase 7 (chain semantics) is highest value.
2. **Process improvements**: items #9, #10, #25, #26, #27 should be folded into `/implement:*` skill spec updates. Open a separate tech-debt PR after Phase 7-13 lands.
3. **Next feature kickoff**: read this RETROSPECTIVE.md during `/implement:brainstorm` to avoid repeating mistakes.
4. **DESIGN review hardening**: the cycle-1 review caught real gaps. Document the patterns reviewers should look for going forward (separate doc, not part of this retrospective).
