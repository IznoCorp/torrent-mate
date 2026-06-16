# DESIGN — hybrid-flow (robustness batch 2: make the HYBRID autonomous lifecycle flow)

> **Codename**: `hybrid-flow` · **Branch**: `feat/hybrid-flow` · **Version**: 0.1.1 → **0.2.0** (minor)
> **Base**: `main` @ ~7122fd6 (v0.1.1, full 2026-06-16 board-fix arc + robustness batch 1).

## 0. Purpose & operator decision

KanbanMate's autonomous lifecycle was wired so each pre-create / build stage launched an agent, but
the chain only advanced if the agent itself ran `kanban-move` — and the persisted
`advance:auto:<col>` directive on launch stages was **dead config** (consumed only by the SCRIPT
route). The agent prompts also auto-chained into a denied `gh pr merge`, and cross-stage artifacts
(the design doc) were written **uncommitted** into a worktree the next stage never saw.

The operator decision is a **HYBRID** lifecycle: auto through Plan, a **single human review gate at
Planned**, human drag `Planned → ReadyToDev`, then auto-build through PR creation, a CI gate that
auto-promotes to Review, **Review stops** for the human, and **merge = human only** (`gh pr merge`
banned, never lifted).

This feature makes five coordinated changes that turn that decision into a working flow.

## 1. HYBRID lifecycle — the 11 transitions, advance directives, and the two human gates

| Transition | Kind | `advance` | Consumer | Effect |
|---|---|---|---|---|
| Backlog → Brainstorming | LAUNCH | `auto:Spec` | session-end backstop | brainstorm done → engine moves to Spec |
| Brainstorming → Spec | LAUNCH | `auto:Plan` | session-end backstop | design done → engine moves to Plan |
| Spec → Plan | LAUNCH | `auto:Planned` | session-end backstop | plan done → engine moves to Planned |
| **Plan → Planned** | no-op | *(none → `stop`)* | — | **HUMAN REVIEW GATE — card STOPS** |
| **Planned → ReadyToDev** | no-op | *(none → `stop`)* | — | **HUMAN drags after reviewing the plan** |
| ReadyToDev → PrepareFeature | LAUNCH | `auto:InProgress` | session-end backstop | create-branch done → engine moves to InProgress |
| PrepareFeature → InProgress | LAUNCH | `auto:PRCI` | session-end backstop | implement + PR → engine moves to PR/CI |
| InProgress → PRCI | SCRIPT | `auto:Review` | `script_route._route_success` | green CI → auto-promote to Review (fires pr-review) |
| **PRCI → Review** | LAUNCH | `stop` | — | **Review STOPS for the human** |
| PRCI → InProgress | LAUNCH (fix-CI) | `auto:PRCI` | session-end backstop | red CI → fix loop re-gates |
| Review → InProgress | LAUNCH (rework) | `auto:PRCI` | session-end backstop | human rework → re-gates |
| **Review → Merge** | SCRIPT gate | `stop` | — | **MERGE = HUMAN ONLY (`gh pr merge` banned)** |

**Safety invariant (the core HYBRID property):** `Plan → Planned` and `Planned → ReadyToDev` MUST
carry NO auto-advance directive. They are no-op whitelist edges; their `advance` defaults to `stop`,
which `auto_advance_target` maps to `None` (no engine move). Auto-advancing either would bypass the
single pre-build human review gate. Pinned by `TestHybridAdvanceDirectives.test_human_gates_carry_no_auto_advance`.

Blocked/Cancel wildcards + the 6-edge skip-to-Done are unchanged.

## 2. Engine-honored `advance:auto:<col>` on launch stages (the session-end backstop)

**Where:** `bin/kanban_session_end.py`, a new `_auto_advance` helper called from a NEW branch **4c**
inside the existing `if done:` block — **after** the ✅ sticky finalize, **before** its `return 0`.
4c lives strictly between the done-without-advance branch (4b) and the neither-breadcrumb interrupt
branch (5). It mirrors `app/script_route._route_success` verbatim where it can.

**Discipline (verified):**

- **(a) clean-done-only.** 4c is reached only inside `if done:` and only when `not advanced`. An
  interrupt (neither breadcrumb) falls to branch 5 (⚠️); an agent self-move set `advanced=True` and
  returned at branch 4. So the engine moves ONLY when the agent ran `kanban-done` as its terminal
  step AND did not move its own card — never a double move.
- **(b) idempotent + fail-soft.** Reuses the SAME fail-soft `GithubClient` wired once for the 4b
  sticky. Every board op is wrapped (warn-to-stderr, never a non-zero exit of the always-run
  session-end). Idempotent because a move to the column the card already sits in is a GitHub no-op,
  and a session-end re-run hits the purged-state early return (branch 1 — no breadcrumb, no move).
- **(c) records the move, NOT an agent advance.** A successful move calls
  `store.record_move_for_item(issue)` — feeding the per-issue rate limit AND making the daemon's
  next `diff(persisted, snapshot)` see `(stage → target)` so `decide` fires the next stage. It
  MUST NOT call `record_agent_advance` (that breadcrumb is the ✅/⚠️ discriminator; the engine move
  is not an agent advance, and the sticky is already ✅).
- **(d) rate-limit + anti-loop.** Before the move, an OUTER per-issue rate-limit gate:
  `move_count_for_item_last_hour(issue) >= move_rate_limit_per_hour` (read from the loaded clone
  transitions config; the `DEFAULT_TRANSITIONS` fallback is 10) parks the card in Blocked instead
  (+ a recap comment + `record_move_for_item`). This bounds a runaway auto-advance chain
  (Brainstorming→Spec→Plan→Planned is 3 engine moves, well under 10/hr). The engine move is the
  **sanctioned** mover (same status as the script-route auto-move): it calls `client.move_card`
  **directly**, NEVER `kanban_move.main()` (whose agent anti-loop guard would refuse a launch-target
  column — that is the point of the backstop).
- **KEY → NAME.** The directive carries a column KEY; `_auto_advance` resolves it to the board's
  display NAME via `core.columns.resolve_column` (the `script_route._to_board_name` pattern) so a
  multiword column ("PR/CI") lands.

**Shared loaders.** `_resolve_entry` / `_load_clone_columns` / `_load_clone_transitions` were lifted
out of `bin/kanban_move.py` into a new `bin/_clone_config.py` (single source of truth; `kanban_move`
re-imports them under their original names for back-compat, listed in `__all__` for an explicit
re-export). `_clone_config.auto_advance_target` is the pure `"auto:<col>" → "<col>"` parser shared by
the session-end backstop and the test suite.

**LOC:** `kanban_session_end.py` 250 → 405; the two lifted loaders moved OUT of `kanban_move` (183
LOC) into `_clone_config.py` (137 LOC). No module crossed the 1000 ceiling.

## 3. Durable cross-stage context carry (the per-ticket WIP branch)

**The gap:** the design stage wrote `docs/features/<codename>/DESIGN.md` into its worktree
UNCOMMITTED; the next stage got a FRESH worktree (detached off `origin/<base>`) without it, and the
markers were ABSOLUTE worktree paths the next worktree could not resolve.

**The fix — a per-ticket WIP branch `kanban/ticket-<issue>`:**

1. **`adapters/workspace/worktree.py::ensure_worktree`** no longer checks out a detached
   `origin/<base>`. After the timed `git fetch origin <base>` it probes
   `git rev-parse --verify --quiet refs/heads/kanban/ticket-<n>`:
   - branch EXISTS (a prior stage created it) → `git worktree add <target> kanban/ticket-<n>`
     (reuse the branch WITH its committed artifacts);
   - else → `git worktree add -b kanban/ticket-<n> <target> origin/<base>` (first stage).
   Worktrees share ONE `.git` object store + ref namespace, so a local commit on the branch by stage
   N is in stage N+1's working tree on checkout — no push, no fetch, no re-materialise. The WIP
   branch name has one source of truth: `worktree.wip_branch(ticket)`.
2. **Stage commits.** `_DESIGN_PROMPT` and `_PLAN_PROMPT` gained an explicit COMMIT step: after
   writing the artifact, the agent runs the stage and the commit as TWO SEPARATE commands —
   `git add docs/features/<codename>/` then `git commit -m "docs(<codename>): design"` (resp.
   `plan`). They are SEPARATE (not a compound `git add … && git commit …`) because the `docs`
   profile allows `Bash(git add*)` and `Bash(git commit*)` as DISTINCT allow-patterns under
   `permission_mode: auto`; a single compound command matches neither and is DENIED headlessly,
   silently breaking the carry. The prompt also guards the empty-codename case: the add/commit
   runs ONLY once `docs/features/<codename>/` exists with the codename set (an empty codename would
   stage the whole `docs/features/` tree). Both are LOCAL commits, no push.
   **Commit identity:** `ensure_worktree` sets a LOCAL fallback git identity (`kanbanmate` /
   `kanbanmate@localhost`) in the clone when none is configured, so `git commit` never aborts on a
   fresh clone with no global identity — an existing operator identity is left untouched (fail-soft).
   Brainstorming writes only the ticket body → no commit.
3. **Repo-relative markers.** The prompts now record `--set-field design
   docs/features/<codename>/DESIGN.md` and `--set-field plans docs/features/<codename>/plan/...`
   (repo-relative, not absolute). `core/ticket_fields.parse_ticket_fields` is unchanged (it maps
   `**design**` → `design_path` verbatim); only the VALUE convention changed. The `_PLAN_PROMPT`
   precondition now describes a real repo-relative path the next worktree can `cat`.
4. **create-branch reconciliation (SKILL.md, NOT engine — see §6 deferred).** With the carry the
   PrepareFeature worktree is already ON `kanban/ticket-<issue>` with DESIGN.md + plan/ committed;
   `git checkout -b feat/<codename>` branches OFF it, inheriting the history. The `mv` Step 4 becomes
   "use in place when `docs/features/<codename>/DESIGN.md` already exists (carry case); `mv` only when
   absent (standalone)".

**Teardown / discovery.** Since the worktree is now ON `kanban/ticket-<issue>` (no longer detached),
`discover_branch` returns the WIP branch on Cancel, so `delete_branch` WOULD now delete it — which
would DESTROY the committed design/plan the carry exists to protect. **Decision: `TeardownAction`
PRESERVES the per-ticket WIP branch on Cancel/Done** (it skips `delete_branch` when the discovered
branch equals `wip_branch(issue)`), mirroring the teardown's existing "remote branch kept" philosophy
(close ≠ delete-ref): a cancelled ticket re-armed to Backlog (or recovered by the operator) keeps its
artifacts. A `feat/<codename>` branch (post create-branch) is STILL force-deleted as before — only the
WIP branch is preserved. The Cancel recap is honest about it (`WIP branch '…' is KEPT`). The earlier
"the WIP branch should go" plan is REVERSED here: preserving it matches the prior pre-create-branch
behaviour (detached → `delete_branch` no-op → branch kept) and avoids silent artifact loss.
`discover_branch` needs no change: it now HONESTLY reports the named branch
(`kanban/ticket-<n>` pre-create, `feat/<codename>` post-create) where it previously reported
`"HEAD"`→`None` — a strict improvement: the InProgress→PRCI gate's `KANBAN_BRANCH` is populated
earlier. `has_unpushed_work`'s `@{u}..HEAD` / `origin/HEAD..HEAD` probes still work on a named branch.

**Why WIP-branch, not runtime-root re-materialize:** the WIP branch reuses git's native shared-object
store (zero copy, zero new store API, the branch ref pins the commits against GC) and dovetails with
create-branch's own branch creation (`feat/<codename>` simply branches off it). The runtime-root
alternative needs a new store API + a re-materialize step in `LaunchAction.execute` + still has to
reconcile git history — strictly more surface for the same outcome. Rejected.

## 4. Implement-stage prompt guards

`_IMPLEMENT_PROMPT` (mirroring `_REVIEW_PROMPT`'s merge-skip block) gained:
- **STOP-AT-PR-CREATION**: `/implement:phase` auto-chains to feature-pr → pr-review, which ends in
  `gh pr merge` (DENIED). The prompt now tells the agent to STOP after the PR is created and CI is
  pushed, and NEVER run `gh pr merge` (or any merge command), then `kanban-move <code> 'PR/CI'` +
  `kanban-done`.
- **CI-not-green TERMINAL branch**: if CI is red or times out, comment the failing checks via
  `kanban-comment`, then `kanban-move <code> 'PR/CI'` ANYWAY (the PRCI gate + fix-CI loop own the
  retry) + `kanban-done`. Do NOT idle waiting on CI inside the session — an idling session drops no
  done breadcrumb → parks WAITING forever, and then the §2 backstop never fires either.

`_FIXCI_PROMPT` gained the same "never `gh pr merge`, move PR/CI + kanban-done even if still
running/red, do not idle on CI" terminal discipline (on top of its existing green-fast-path).

> Prompt wording is load-bearing but has empirically failed (#91, helm #5); the deny-list
> (`gh pr merge` banned) stays the real mechanism. These guards reduce the stall at the source.

## 5. docs profile shell

`adapters/perms.py::_PROFILE_ALLOW["docs"]` gained the MINIMUM shell the doc stages need:
`Bash(mkdir*)`, `Bash(ls*)`, `Bash(cat*)` — so a headless `mkdir -p docs/features/<codename>/plan`
or a `cat` of a carried artifact is not DENIED (which would stall the stage). NOT a broad `Bash`:
docs still has no push / gh-write, so the blast radius stays local-FS read + dir-create (consistent
with the documented "not a sandbox" caveat). `git add`/`git commit` were already allowed (§3 needs no
new git subcommand). The universal deny-list still applies.

## 6. Deferred — create-branch SKILL.md reconciliation

The `implement:create-branch` SKILL.md change (§3.4) is a **portable-config** edit, NOT engine code.
The `.claude/` directory is a SEPARATE git repo, gitignored by KanbanMate and shared across all
worktrees + the live PM2 daemons (which provision skills into agent worktrees). Editing it from an
isolated worktree would (a) not be captured by this feature branch and (b) mutate live-system config.
Per the safety mandate (never touch the main worktree / live daemons), the exact required edit is
documented here for the operator (or the create-branch stage itself) to apply against
`.claude/skills/implement:create-branch/SKILL.md`:

- **Step 3** (`git checkout -b "$BRANCH"`): now branches OFF the current `kanban/ticket-<issue>` HEAD
  (inheriting the design + plan commits), so `feat/<codename>` carries the history — no orphan
  reconciliation.
- **Step 4** (the `mv "$DESIGN_DOC_PATH" docs/features/${CODENAME}/DESIGN.md`): becomes idempotent —
  if `docs/features/${CODENAME}/DESIGN.md` already exists (the carry case), USE IT IN PLACE (skip the
  `mv`); the `$DESIGN_DOC_PATH` mv is the fallback only for the standalone/non-orchestrated
  invocation. Step 7's `git add docs/features/${CODENAME}/DESIGN.md` is then a harmless no-op (the
  design is already committed on the WIP branch).
- **Error-handling row** "`design_doc_path` not found": gains the carry exception — if the design
  already exists at `docs/features/${CODENAME}/DESIGN.md` (carried by the orchestrator's WIP branch),
  it is NOT an error; use it in place.

## 7. Test plan (all green in `make check`)

- **C1 backstop** — `tests/bin/test_kanban_session_end.py`: done+`auto:Spec`+not-advanced → move to
  Spec once + `record_move_for_item` (not `record_agent_advance`); `stop`/empty → no move; advanced →
  branch-4 return, no engine move; neither breadcrumb → ⚠️, no move; rate-limit `>= cap` → park in
  Blocked; KEY→NAME (`auto:PRCI` → "PR/CI"); `move_card` raises → fail-soft exit 0, no loop; unknown
  target → fail-soft no-op; multi-root `KANBAN_ROOT` honoured. Pure parser in
  `tests/bin/test_clone_config.py`.
- **C2 transition table** — `tests/core/test_transitions_defaults.py::TestHybridAdvanceDirectives`:
  each transition's `advance` per §1; the two human gates carry no auto-advance; `default_transition_config()`
  still parses.
- **C3 WIP branch** — `tests/adapters/test_workspace.py`: fresh ticket → `add -b kanban/ticket-<n>
  origin/<base>`; existing branch → `add <target> kanban/ticket-<n>` (no `-b`); a shared-`.git`
  integration test (commit on the branch in worktree A is visible in a re-created worktree B);
  `discover_branch` returns the WIP branch. create-branch SKILL.md reconciliation is doc-only (§6).
- **C4 prompts** — `TestImplementStagePromptGuards` + `TestDurableCarryPromptWording`: the
  stop-at-PR / never-merge / CI-red-terminal / do-not-idle strings + the commit + repo-relative
  markers.
- **C5 perms** — `tests/test_perms.py`: `allow_list("docs")` includes `mkdir`/`ls`/`cat`, still
  excludes push/`gh pr`/broad `Bash`.

## 8. Phase gate

`make check` (ruff + ruff format --check + mypy + pytest + size guard) exits 0; `python -c "import
kanbanmate"`; no module crossed the 1000-LOC ceiling (the backstop lives in `session_end` 405 LOC +
the new `_clone_config.py` 137 LOC; the near-ceiling modules were untouched). All work in an isolated
worktree + isolated venv; the live PM2 daemons (editable install from the MAIN worktree) were never
touched or restarted.
