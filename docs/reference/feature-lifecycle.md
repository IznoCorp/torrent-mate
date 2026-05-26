# Feature Lifecycle Reference

Conventions for managing feature implementation from design to merge. Covers
phase-gate semantics, ACCEPTANCE criteria format, post-merge re-exercise, and
the rule that prevents silent criterion drift.

---

## 1. Phase Gate ≠ Deployment

A **phase gate commit** (`chore({codename}): phase N gate — …`) marks that one
implementation phase is complete and all its items are committed. It is **not**
a deployment trigger and **not** a proof that the shipped functionality is
observable in production.

What the phase gate guarantees:

| Guarantee                           | How verified                           |
| ----------------------------------- | -------------------------------------- |
| `make check` passes (lint + test)   | Run before milestone commit            |
| No collection errors in `make test` | Summary line: `NNNN passed, 0 failed`  |
| Module size within limits           | `python3 scripts/check-module-size.py` |
| Import smoke test passes            | `python -c "import personalscraper"`   |

What the phase gate does **not** guarantee:

- That the feature is exercised against a live database or real API.
- That ACCEPTANCE criteria pass end-to-end (only confirmed at the final PR gate).
- That downstream consumers of the changed API have been notified.

**Consequence**: marking ACCEPTANCE ✅ at a phase gate is prohibited unless the
criterion is purely a `make test -k <name>` invocation (unit or integration
test). Shell commands that exercise live state must be deferred to the PR gate
re-exercise step.

---

## 2. ACCEPTANCE Criteria Format Rule

Every ACCEPTANCE criterion **must** be an executable shell command with a
documented expected output. Non-executable prose is not a valid criterion.

### Canonical format

````markdown
### ACC-NN — Short description (DEV #NN or SH-NN)

```bash
<shell command>
# Expected: <output or condition>
```
````

**Status**: SHIPPED | PENDING | DONE_WITH_CONCERNS

````

### Valid criterion

```bash
rg "^class MetadataProvider\b" personalscraper/ --type py
# Expected: zero matches
````

### Invalid criterion (prose, not executable)

> "MetadataProvider has been removed and all callers have been migrated."

Prose criteria cannot be re-run automatically. They drift silently. Reject them
at design review.

### Required fields

| Field     | Rule                                                               |
| --------- | ------------------------------------------------------------------ |
| Command   | Runnable verbatim in the project root without manual setup         |
| Expected  | Specific: exit code, count, exact string, or "zero rows"           |
| Scope tag | Must reference at least one DEV #NN, SH-NN, MUST-NN, or CF-NN item |
| Status    | Updated at each phase gate and at the final PR gate                |

---

## 3. Post-Merge ACCEPTANCE Re-Exercise (mandatory)

At the **final PR gate** (before squash merge), every ACCEPTANCE criterion whose
command exercises live state must be re-run. This is distinct from the phase
gate, which only runs `make check`.

### Re-exercise procedure

1. Checkout the feature branch locally (or use the CI gate environment).
2. Run each `ACC-NN` command from `ACCEPTANCE.md` in order.
3. Compare actual output to the `Expected:` annotation.
4. Mark each criterion ✅ (passes), ❌ (fails), or 🟡 (pending — deferred to a
   later feature, which must be documented with a target version).
5. If any criterion is ❌ and not explicitly deferred: **block merge**. Open a
   sub-phase in `plan/phase-NN-pr-fixes.md` and fix before merging.

### Who runs it

The `/implement:feature-pr` skill triggers re-exercise as part of the local
quality gate. If run manually, the operator runs `bash
docs/features/{codename}/scripts/acceptance-check.sh` (created in the final
phase) or iterates criteria by hand.

### Deferred criteria (🟡)

A criterion may be deferred only when the work item it covers is explicitly
moved to a future version in the plan. The deferral must appear in the criterion
comment:

```markdown
**Status**: 🟡 DEFERRED — acceptance-check backfill deferred to 0.17+
(see docs/features/tech-debt/audit/11-global-synthesis.md §out-of-scope)
```

Undocumented deferrals are treated as ❌ at merge time.

---

## 4. ACCEPTANCE_FAIL Alerting (0.17+ roadmap)

The following CI check is planned but not yet shipped (target: 0.17.0):

- A dedicated CI job runs `acceptance-check.sh` on every PR that touches
  `personalscraper/`, `tests/`, or `docs/reference/`.
- Any criterion that exits non-zero fails the job and blocks merge.
- Criteria that require live state (real DB, real API keys) are tagged
  `@live` and skipped in CI; they remain in the operator's manual checklist.

Until 0.17.0, re-exercise is manual (see §3).

---

## 5. Versioned Promise Discipline

A **versioned promise** is any claim in a DESIGN.md of the form "this will be
done by version X.Y.Z". Examples seen in tech-debt audit:

- `check-module-size.py` promoted to hard-block "in 0.10.0" — stalled for 5
  versions (DEV #46).
- provider-ids Plan A reset+rescrape "after merge" — never executed (DEV #27).

### Rules

1. Every versioned promise in a DESIGN.md **must** have a corresponding
   ACCEPTANCE criterion that fails if the promise is not honored by the target
   version.
2. Promises without a CI-enforceable check are considered **aspirational**, not
   binding. Document them in the DESIGN as `(aspirational — 0.17+ roadmap)`
   rather than as a hard commitment.
3. `docs/reference/promises.md` (to be created in 0.17.0) will track all
   active versioned promises with their target version and current status.

---

## 6. Cross-Feature DESIGN Drift

When a refactor or new feature invalidates a claim in a previously archived
DESIGN.md, the archived file must be updated with a banner:

```markdown
> **STATUS**: superseded by `feat/{new-codename}` (merged {date}).
> See `docs/reference/{relevant-ref}.md` for the current authoritative state.
> Symbols renamed/removed: `OldClass` → `NewClass` (see {new-codename} §NN).
```

Reference docs under `docs/reference/` are the authoritative source for the
current codebase. Archived docs under `docs/archive/features/` are historical
snapshots — never authoritative for the present state.

---

## 7. Quick Reference

```
Phase gate commit        make check + smoke import + milestone commit
ACCEPTANCE format        shell command + expected output + status field
Post-merge re-exercise   run every ACC-NN, block merge on ❌
Deferred criterion       🟡 + explicit target version in comment
Versioned promise        must have ACC-NN or it is aspirational only
Archived DESIGN drift    add STATUS banner + old→new symbol table
```

See also:

- `docs/features/{codename}/ACCEPTANCE.md` — per-feature criteria list
- `docs/reference/testing.md` — test taxonomy and runtime budgets
- `docs/reference/commands.md` — CLI reference (all commands with --help)
- `docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md` —
  implement:\* skill architecture and phase flow
