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
quality gate. If run manually, the operator iterates the `ACC-NN` commands from
`docs/features/{codename}/ACCEPTANCE.md` by hand, comparing each output to its
`Expected:` annotation. There is no repo-wide acceptance-check script (see
`docs/reference/runbook-post-merge.md` §Step 10) — if a feature ships its own
executable acceptance script under `docs/features/{codename}/`, run that
instead.

### Deferred criteria (🟡)

A criterion may be deferred only when the work item it covers is explicitly
moved to a future version in the plan. The deferral must appear in the criterion
comment:

```markdown
**Status**: 🟡 DEFERRED — acceptance-check backfill deferred to 0.17+
(see `docs/archive/features/tech-debt/audit/11-global-synthesis.md@79ccebe2` §out-of-scope)
```

Undocumented deferrals are treated as ❌ at merge time.

---

## 4. ACCEPTANCE_FAIL Alerting (open item — never shipped)

A dedicated CI check for acceptance criteria was planned (originally targeted
at 0.17.0) but was never built, and no target version is currently set. It
remains an open item; the intended shape is recorded here so it is not lost:

- A dedicated CI job would run every `ACC-NN` command on each PR that touches
  `personalscraper/`, `tests/`, or `docs/reference/`.
- Any criterion that exits non-zero would fail the job and block merge.
- Criteria that require live state (real DB, real API keys) would be tagged
  `@live` and skipped in CI; they would remain in the operator's manual
  checklist.

Today, re-exercise is manual (see §3).

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
3. `docs/reference/promises.md` tracks active versioned promises with their
   target version and current status (today it tracks the module-size
   promise; new versioned promises must be added there).

---

## 6. A superseded design is history

A design that a later feature invalidates is not annotated: it left the tree when its wave
merged, and `docs/reference/` is the only authority on the present. What a reader must know
about the change is in the reference document the later feature updated. Reading an old design
is `git show <sha>:<path>`; the citation form is `docs/reference/documentation-model.md` § 2.

---

## 7. Implementation Workflow — the `implement:*` skills

12 `implement:*` skills manage the full feature lifecycle, with per-skill model
allocation (see each skill's description; **Sonnet is forbidden as a dispatch
target**). Original design (archived):
`docs/archive/superpowers/specs/2026-04-22-implement-skills-refactor-design.md@79ccebe2`.

**Entry point**: `/implement:feature` — archive prev, brainstorm, derive codename
+ SemVer type, create branch, generate plan.

**Per phase**: `/implement:phase` — loop on sub-phases, dispatching
`/implement:sub-phase` + `/implement:check` (verification). Auto-invokes
`/implement:feature-pr` at the last phase (gate + push + PR + CI poll), then
`/implement:pr-review` (review + track-scaled fix cycles: full=5, lite=2,
express=1 + squash merge).

| Aspect         | Rule                                                      |
| -------------- | --------------------------------------------------------- |
| Branches       | `feat/{codename}` or `fix/{codename}`                     |
| Commits        | Conventional Commits with `(codename)` scope              |
| SemVer bump    | at create-branch: bugfix → Z+1, minor → Y+1, major → X+1  |
| Merge          | squash, mode chosen at feature start (manual / auto)      |

**Milestone commits** (used by `/implement:phase`) include the codename as scope:

```
chore(my-feature): phase 3 gate — scraper refactor
```

This is the ONLY place a codename appears in milestone commits.

### Phase-gate verification detail

Beyond the checklist in `CLAUDE.md`:

- **If `make test` shows any ERROR (not just FAILED)**: the test COLLECTION
  crashed — every test after that point is skipped. Fix imports before
  proceeding.
- **After any module deletion**: grep `tests/` for the old path.
  `rg "old.module.path" tests/` must return zero matches.
- **After any constructor signature change**: grep `tests/` for the old call
  pattern and update all test fixtures/mocks.

### Working a KanbanMate ticket

Roadmap items are tracked as **KanbanMate tickets** (historical example: the
web-UI waves S1 `#158` through S7, all shipped since). Never start coding
directly — claim the ticket first so the autonomous KanbanMate daemon stays out
of the way, then advance the card as the work progresses:

1. **Claim + sync** — invoke `/kanban-work <ticket>` (skill
   `kanban:kanban-work`). This reclaims the ticket from the autonomous daemon
   and syncs the local session with the board.
2. **Advance the card** — move it through the KanbanMate columns as work
   progresses (board/CLI ops via `/kanban`; health sweep via `/kanban-monitor`).
3. **Then** run the normal implementation flow (`/implement:feature` → phases →
   PR), keeping the card's column in step with actual progress.

---

## 8. Quick Reference

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
- `docs/archive/superpowers/specs/2026-04-22-implement-skills-refactor-design.md@79ccebe2` —
  implement:\* skill architecture and phase flow
