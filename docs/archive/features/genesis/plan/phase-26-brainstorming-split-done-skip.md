# Phase 26 — Split brainstorming↔spec, add Plan column, allow early skip-to-Done (e2e-driven)

**Trigger (operator):** the first live e2e (#91) showed two things — (1) the interactive
`/implement:brainstorm` HANGS an unattended orchestrated agent (it asks the user a question and
waits → reaped), and (2) an already-shipped ticket can be RECOGNISED by the agent but can't be
marked Done (the agent's `Spec→Done` was rolled back — un-whitelisted). Fix both by restructuring
the front of the flow so only ONE step is interactive, and by whitelisting an early skip-to-Done.

## Target flow (operator-approved)

Two NEW columns — **`Brainstorming`** (after Backlog) and **`Plan`** (after Spec). `Spec` is
repurposed to the autonomous **design** step; `Planned` is repurposed to a **human checkpoint**.

| from → to                                                            | kind                       | prompt / action                                                                                                                                          | profile | autonomy                                         |
| -------------------------------------------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------ |
| Backlog → Brainstorming                                              | agent                      | `/implement:brainstorm` — gather requirements + derive codename + write the brainstorm output to the ticket body; do **not** write the formal design yet | docs    | **INTERACTIVE** (human `tmux attach`s to answer) |
| Brainstorming → Spec                                                 | agent                      | autonomous **design**: read the brainstorm output from the ticket, write `design.md`; **no questions, make reasonable assumptions**                      | docs    | autonomous                                       |
| Spec → Plan                                                          | agent                      | `/implement:plan` — write the plan files; **no questions**                                                                                               | docs    | autonomous                                       |
| Plan → Planned                                                       | no-op                      | (autonomous design+plans done; lands in `Planned` for human review)                                                                                      | —       | —                                                |
| Planned → ReadyToDev                                                 | no-op                      | human checkpoint/gate                                                                                                                                    | —       | —                                                |
| ReadyToDev → PrepareFeature                                          | agent                      | `/implement:create-branch`                                                                                                                               | prepare | autonomous                                       |
| PrepareFeature → InProgress                                          | agent                      | `/implement:phase`                                                                                                                                       | dev     | autonomous (advance auto:PRCI)                   |
| InProgress → PRCI                                                    | script                     | `bin/check-pr-ready.sh`                                                                                                                                  | check   | on_fail move:InProgress                          |
| PRCI → InProgress                                                    | agent                      | fix-CI prompt                                                                                                                                            | dev     | autonomous (advance auto:PRCI)                   |
| PRCI → Review                                                        | agent                      | `/implement:pr-review`                                                                                                                                   | dev     | autonomous                                       |
| Review → Merge                                                       | script                     | `bin/check-merge-ready.sh`                                                                                                                               | check   | on_fail rollback                                 |
| Merge → Done                                                         | no-op                      | terminal                                                                                                                                                 | —       | —                                                |
| **[Backlog, Brainstorming, Spec, Plan, Planned, ReadyToDev] → Done** | **no-op (whitelist only)** | lets an agent/human mark an ALREADY-DONE ticket as Done without a rollback                                                                               | —       | —                                                |
| \* → Cancel                                                          | reactive                   | teardown                                                                                                                                                 | —       | —                                                |
| Cancel → Backlog                                                     | reactive                   | reset                                                                                                                                                    | —       | —                                                |
| _ → Blocked / Blocked → _                                            | (unchanged)                |                                                                                                                                                          |         |                                                  |

**Why the skip-to-Done is bounded at PrepareFeature:** from PrepareFeature onward a worktree/branch
exists, so retirement must go through Cancel (teardown). Before PrepareFeature there's nothing to
tear down, so a direct → Done is safe. Hence Done is whitelisted ONLY from the six pre-PrepareFeature
columns (NOT from PrepareFeature/InProgress/PRCI/Review/Merge).

## Autonomy (addresses the interactive-hang)

Only `Backlog→Brainstorming` is interactive. EVERY other agent prompt (Brainstorming→Spec, Spec→Plan,
the dev/fix/review prompts) MUST carry an explicit instruction: **"Run fully autonomously — do NOT ask
the user any questions; make reasonable assumptions and proceed; do NOT invoke an interactive
brainstorming Q&A."** This keeps the unattended steps from hanging on a clarifying question (the
reaper would otherwise churn them). The brainstorm (interactive) is the one place the human attaches.

## Sub-phase 26.1 — Column model + transitions + prompts (code)

- `src/kanbanmate/assets/columns.yml.tmpl`: insert `Brainstorming` (key `Brainstorming`, name
  "Brainstorming") after Backlog, and `Plan` (key `Plan`, name "Plan") after Spec. Keep `Planned`
  (now a checkpoint — still INERT, no launch). Document order = the flow order above.
- `src/kanbanmate/core/transitions_defaults.py`: rewrite `DEFAULT_TRANSITIONS` to the target table.
  - New/changed prompt constants: keep `_DESIGN_PROMPT`? — REPLACE the front: a `_BRAINSTORM_PROMPT`
    (interactive, Backlog→Brainstorming), a `_DESIGN_PROMPT` (autonomous design, Brainstorming→Spec),
    keep `_PLAN_PROMPT` (Spec→Plan) + add the autonomous instruction. Reuse `_PREPARE_PROMPT`,
    `_IMPLEMENT_PROMPT`, `_FIXCI_PROMPT`, `_REVIEW_PROMPT` (add the autonomy instruction to each).
  - The skip-to-Done: a single list-expanded entry
    `from: [Backlog, Brainstorming, Spec, Plan, Planned, ReadyToDev], to: Done` (NO prompt/script →
    no-op whitelist; cartesian-expands to 6 explicit edges).
  - Adjust `DEFAULT_RESET_TARGET` / column-class constants if they reference the old column set.
- `render_transitions_yaml` + the column template: ensure the rendered YAML carries the new flow.
- Update `core/columns.py` / `core/decide.py` if any column-name constants are hardcoded
  (e.g. the Blocked/Cancel/Backlog/Done reset targets; the launch-target derivation).
- Tests: `tests/core/test_transitions_defaults.py` (new flow + the 6 skip-to-Done edges + that Done is
  NOT whitelisted from PrepareFeature+), `tests/core/test_columns.py` (14 columns incl. Brainstorming +
  Plan), decide/transitions tests for the new edges + the skip-to-Done no-op. `make check` green.

**Acceptance:** `make check` green; `DEFAULT_TRANSITIONS` matches the table; `[6 cols]→Done` resolve
to no-op (no rollback, no launch); `PrepareFeature→Done` is NOT whitelisted (→ rollback); only
Backlog→Brainstorming carries an interactive prompt, all other agent prompts carry the autonomy
instruction; 14-column template parses.

## Sub-phase 26.2 — Live board migration (operator/me, like phase 21)

- Add the `Brainstorming` + `Plan` Status options to the live `IznoCorp/personal-scraper` board
  (preserve existing option ids — `updateProjectV2Field` REPLACE with the full set incl. the new
  ones, in flow order). Re-render `<clone>/.claude/kanban/transitions.yml` + the bare `columns.yml`.
  Refresh the registry option_map. Restart the PM2 daemon. `kanban doctor` clean.
- Pre-req: cancel/retire any in-flight test agent (#91) first so the migration is clean.

## Sub-phase 26.3 — DESIGN update

- `docs/features/genesis/DESIGN.md`: update §8/§9 (the flow table) + the columns list to the new
  14-column flow; document the interactive-vs-autonomous split (only Brainstorming interactive) and
  the bounded skip-to-Done (≤ ReadyToDev). Note the worktree-on-Done residue as a known minor (a
  skip-to-Done before PrepareFeature has no worktree, so no residue; from Spec/Plan an agent that
  created a worktree then moves to Done leaves it — acceptable, Done is inert).

### Phase gate

`rm -rf .mypy_cache && make check` green; diff confined to the sub-phase files (NEVER the helm prep /
ROADMAP / IMPLEMENTATION / the phase-26 plan); `python -c "import kanbanmate"` smoke; then the live
board migration + daemon restart (26.2).
