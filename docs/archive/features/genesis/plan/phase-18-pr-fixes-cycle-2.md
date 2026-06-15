# Phase 18 — PR-review fixes (cycle 2): PoC-conformance gaps + correctness defects

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Source: the cycle-2 PoC-conformance PR review (6-dimension workflow, 2026-06-08). Operator decision
> 2026-06-08: **fix ALL** (majors + mediums + minors) — "rien ne doit être laissé derrière".
> PoC root: `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`. NEW: `src/kanbanmate/`.
> Merge is HUMAN-ONLY (merge_mode=manual) — phase 18 ends green; the human squash-merges PR #1.
> **Clear `.mypy_cache` before every gate** (`rm -rf .mypy_cache && make check`).

**Verified RESTORED (review, info/conformant)**: the 26 behaviour changes (phase 17) are all conformant
(0 findings); the bulk of feature-losses (whitelist+rollback, run_script/gate, on_fail/fix-CI cap,
advance:auto, cap+queue+drain, ensure_clone+credential-helper, per-repo flock, reaper retry,
session-uuid+session-end, provision_worktree_skills, disk rate-limit & retry ledger) are faithfully
restored + tested. Phase 18 closes the 5 genuine defects + the long-tail minors the review found.

---

## 18.1 — M1a: restore cross-stage prompt context (`parse_ticket_fields` → codename/design_path/plan_paths)

**The gap (MAJOR, feature_DROPPED).** `LaunchAction._launch_context` (actions.py:439-441) hard-defaults
`codename`/`design_path`/`plan_paths` to `""`. The PoC's multi-stage flow is self-referential: the DESIGN
agent writes `**codename**:` / `**design**:` / `**plans**:` into the ticket body, and `parse_ticket_fields`
(PoC runner.py:82-93) reads them back so the PLAN/IMPLEMENT/FIXCI/REVIEW prompts fill those placeholders.
NEW has NO `parse_ticket_fields` (`rg parse_ticket_fields src/` = zero). Consequence: the PLAN agent is
launched as `/implement:plan ... for #N () from the design  and main` — empty codename + design path.

**Layer**: `core/` (pure parser) + `app/actions.py` (consume in `_launch_context`).
**Files**: `src/kanbanmate/core/ticket_fields.py` (NEW pure parser), `src/kanbanmate/app/actions.py`
(`_launch_context` reads the ticket body → fills the 3 keys), `tests/core/test_ticket_fields.py` (NEW),
`tests/app/test_actions.py` (extend).

- [ ] Port `parse_ticket_fields(body: str) -> dict[str, str]` into `core/ticket_fields.py` (pure, I/O-free;
      port PoC runner.py:82-93) — parse `**codename**:` / `**design**:` (→ design_path) / `**plans**:`
      (→ plan_paths) markers from the ticket body; missing markers → "". English docstrings.
- [ ] `LaunchAction._launch_context`: fill `codename`/`design_path`/`plan_paths` from
      `parse_ticket_fields(self.ticket.body or "")` instead of the hardcoded "". Keep "" when a marker is
      absent (back-compat: a first-contact ticket with no markers fills "" — the DESIGN agent does not
      reference them). Update the docstring (drop "until those phases land" for these 3 keys).
- [ ] Tests: a ticket body with the 3 markers fills the placeholders; a body without them → "" (no crash);
      the PLAN prompt renders the real codename + design path end-to-end.
- [ ] Verify: `rm -rf .mypy_cache && make check` green; layering guard (core/ticket_fields.py I/O-free).

```bash
git commit -m "fix(genesis): restore parse_ticket_fields → fill codename/design_path/plan_paths in launch prompts"
```

---

## 18.2 — M1b: wire `issue_context` into the launch path (fill `{{issue_body}}`/`{{comments}}`)

**The gap (MAJOR, feature_DROPPED).** `LaunchAction._launch_context` hard-defaults `issue_body`/`comments`
to `""` (actions.py:437-438). Phase 16.1 ported `GithubClient.issue_context` (client.py:588) + the GraphQL
query + the `IssueContext` parser FAITHFULLY but left it as DEAD CODE: it has ZERO consumers, is not on any
port (`rg issue_context src/kanbanmate/ports/` = zero). The PoC fed every launch prompt with the linked
cross-referenced issue body (`{{issue_body}}`) + the full comment history (`{{comments}}`, joined by
`\n---\n`) via `gh.issue_context()` (PoC runner.py:663-704). The shipped `_DESIGN_PROMPT`
(transitions_defaults.py:70-71) references both — so the Design agent launches with them EMPTY every time.

**Layer**: `ports/board.py` (add `issue_context` to the board-READ Protocol) + `app/actions.py` (consume,
fail-soft). **Files**: `src/kanbanmate/ports/board.py` (add `issue_context` to `BoardReader`),
`src/kanbanmate/app/actions.py` (`_launch_context` calls `deps.board_reader.issue_context(issue)`,
fail-soft), `src/kanbanmate/app/wiring.py` / `Deps` (ensure the launch path has the board READER handle —
it already has `board_reader` for the gate fallback from 17.3; reuse it), tests.

- [ ] Add `issue_context(self, number: int) -> IssueContext` to the `BoardReader` Protocol in
      `ports/board.py` (the GithubClient already implements it — client.py:588). Cite that 16.1 left it
      unwired. Update structural board-reader fakes in tests with the stub (necessary fan-out).
- [ ] `LaunchAction._launch_context`: call `deps.board_reader.issue_context(issue)` and fill
      `issue_body = ctx.linked_issue_body or ""` and `comments = "\n---\n".join(ctx.comments)` (port the PoC
      join). **FAIL-SOFT**: wrap in try/except → on error, fall back to "" + `logger.exception` (a GraphQL
      hiccup must NOT break a launch). The `issue_context` GraphQL call inherits the client's mandatory
      connect+read timeouts. Confirm the launch path has a `board_reader` handle on `Deps` (added 17.3 for
      the #13 gate fallback); if not, thread it.
- [ ] Tests: a launch fills `{{issue_body}}` from the linked issue + `{{comments}}` from the joined comment
      bodies; a throwing `issue_context` → "" fallback + the launch still completes (state saved, sticky
      posted); the Design prompt renders the enriched context end-to-end.
- [ ] Verify: `rm -rf .mypy_cache && make check` green. Residual: `rg --type py "\.issue_context\(" src`
      now matches a REAL consumer in actions.py (no longer dead code).

```bash
git commit -m "fix(genesis): consume issue_context in the launch path → fill {{issue_body}}/{{comments}} (no more dead adapter)"
```

> **KEYSTONE — adversarial-verify 18.1+18.2** after they land: prompt-fill correctness, fail-soft on the
> GraphQL call, no regression to the phase-12 filled-prompt path, the placeholders all resolve (no leftover
> `{{...}}`), and `base_clone`/`dev_repo_path` remain justified-"" (no `_MERGE_PROMPT` references them).

---

## 18.3 — M2: launch-gate runs AFTER the worktree exists (port PoC "bug #1" fix)

**The gap (MAJOR, deviation_UNJUSTIFIED).** When a LAUNCH transition carries a `script` gate, the tick runs
`run_check_script(deps, issue, gate_script)` (tick.py:667-671) BEFORE `LaunchAction.execute` creates the
worktree (actions.py:256 `ensure_worktree`). `run_check_script` → `discover_branch` → `git -C
<worktrees/ticket-N> rev-parse` with `check=True` on a NON-EXISTENT dir → raises → watchdog returns
`ok_gate=False` → the launch is vetoed + baseline advanced → the agent NEVER launches (circular deadlock).
The PoC's `_apply_launch` creates the worktree BEFORE the gate (PoC runner.py:643-652, docstring "Ordering
(bug #1)"). The shipped board has no prompt+script transition (unaffected), but the gated-launch capability
(DESIGN §8.3, plan 15.7) is broken for any custom board. A test passed via a MagicMock workspace that
masked the real-adapter ordering (false confidence).

**Files**: `src/kanbanmate/app/tick.py` (create/ensure the worktree before the gate), `tests/app/test_tick.py`
(a REAL-adapter or faithfully-faked ordering test, not a MagicMock that hides the bug).

- [ ] In the tick's LAUNCH-with-gate branch, ensure the per-ticket worktree exists (idempotent
      `ensure_worktree`) + discover the branch BEFORE `run_check_script`. Mirror the PoC ordering: worktree
      → branch → gate → (exit 0) launch / (exit ≠0) on_fail. The idempotent `ensure_worktree` is the same
      step the launch needs anyway, so no half-state.
- [ ] Fix the masking test: assert the ordering with a fake workspace whose `discover_branch` FAILS when
      `ensure_worktree` was not called first (so a regression of the order fails the test).
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "fix(genesis): create the worktree before the launch-gate script (port PoC bug #1 ordering)"
```

---

## 18.4 — M3 + #12: breadcrumb on schema-corrupt state (not just JSON-corrupt)

**The gap (MAJOR / minor, deviation_UNJUSTIFIED).** `list_running()` (fs_store.py:358-365), `list_all()`
(392-399) and `load()` (138-145) call `_warn_corrupt_state` ONLY on the `json.loads` failure (the #17 fix).
The SUBSEQUENT validation branches — `data["status"] = TicketStatus(data["status"])` raising
(ValueError/KeyError) and `TicketState(**data)` raising TypeError — `continue`/`return None` SILENTLY. A
state file that is valid JSON but schema-broken (unknown status enum, renamed field) is dropped from the
reaper's source of truth (`list_running`) with ZERO breadcrumb → a stale agent escapes the reaper unseen.

**Files**: `src/kanbanmate/adapters/store/fs_store.py` (call `_warn_corrupt_state` on the status-enum +
`TicketState(**data)` except branches in `load`/`list_running`/`list_all`), `tests/adapters/test_fs_store.py`.

- [ ] Emit `_warn_corrupt_state(path, err)` before the `continue`/`return None` on BOTH schema branches in
      all three readers (keep skip-don't-raise). Update the docstring (the H1 net now warns on schema
      corruption too, not just JSON).
- [ ] Tests: a valid-JSON-but-unknown-status file in `list_running` is skipped WITH a named stderr line; a
      `TicketState(**data)` TypeError likewise; `load` of such a file returns None WITH a breadcrumb.
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "fix(genesis): warn on schema-corrupt state files (not just JSON) so the reaper never silently drops a stale agent"
```

---

## 18.5 — Md1: restore the cross-loop move-rate-limit PARK gate (counter is write-only)

**The gap (MEDIUM, feature_DROPPED).** The durable per-item move counter (`record_move_for_item`) is FED by
the auto-advance (script_route.py:221) and within-cap on_fail (script_route.py:302) moves, but NOTHING reads
`move_count_for_item_last_hour >= move_rate_limit_per_hour` to PARK a runaway. The sole consumer
(`reaper._rate_limited`, reaper.py:93) only avoids double-recording the reaper's own park. The PoC ran the
cap gate BEFORE every run_script/launch (PoC runner.py:504-518 `if count >= cap: _park_blocked()`). The
per-loop `_FIXCI_CAP=2` is the only bound; multiple INDEPENDENT auto/on_fail loops (distinct `onfail:<col>`
keys) can churn a card faster than the cap with no backstop. The phase-13 "#16" justification ("the reaper
is the only daemon AUTO move") went STALE when phase 15 added the auto/on_fail moves.

**Files**: `src/kanbanmate/app/script_route.py` (gate the auto/on_fail moves on the cap → park in Blocked
when exceeded) and/or `src/kanbanmate/app/tick.py`, `tests/app/test_script_route.py`.

- [ ] Before issuing an auto-advance / on_fail triggering move, check
      `deps.store.move_count_for_item_last_hour(issue) >= config.move_rate_limit_per_hour`; if exceeded,
      PARK the card in `blocked_column` (+ recap comment, anti-loop record) instead of the move — port PoC
      `_park_blocked` semantics into the script-route path. Keep the per-loop `_FIXCI_CAP` as the inner
      bound; this is the OUTER cross-loop backstop. Document the "AUTO/bot moves only" rule.
- [ ] Tests: N independent auto/on_fail loops that together exceed `move_rate_limit_per_hour` → the card is
      parked in Blocked (not churned forever); a within-limit single loop is unaffected.
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "fix(genesis): park a runaway card when move_rate_limit_per_hour is exceeded (restore the cross-loop backstop gate)"
```

---

## 18.6 — Md2: `_drain_queue` must not release a LIVE ticket's slot

**The gap (MEDIUM, deviation_UNJUSTIFIED).** In `_drain_queue`, for an already-RUNNING queued issue the code
does `reserve_slot(issue, cap)` (idempotent → reserves nothing when the issue already holds a slot) then
`clear_queued` + `release_slot(issue)` "without re-dispatching" (tick.py:917-930). But `release_slot`
unconditionally unlinks `slots/ticket-<issue>` AND every `retries/<issue>__*` — so it strips the LIVE
ticket's pre-existing slot + fix-CI counters → the cap undercounts (an extra agent can exceed
`concurrency_cap`) + in-flight retry budgets are zeroed.

**Files**: `src/kanbanmate/app/tick.py` (`_drain_queue` already-running guard), `tests/app/test_tick.py`.

- [ ] Reorder/guard: detect the already-RUNNING state BEFORE `reserve_slot` — if the issue already has a
      RUNNING persisted state, just `clear_queued(issue)` and skip (do NOT reserve, do NOT release the live
      slot). Only release a slot this iteration actually reserved for a non-running ticket. Document the
      precondition.
- [ ] Tests: a queue marker coexisting with a RUNNING state → the live slot + retries SURVIVE the drain
      (assert the slot marker + `retries/<issue>__*` still exist); a genuinely-stale queue marker (no
      running state) is still drained/launched normally.
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "fix(genesis): drain guard no longer releases a live running ticket's slot + fix-CI budgets"
```

---

## 18.7 — Minors + cleanup (review long-tail)

**The cluster (minors/info).** Bundle the cheap, low-risk fixes the review flagged:

**Files**: `src/kanbanmate/app/tick.py` (decision-time rate-limit config), `src/kanbanmate/cli/seed.py`
(Backlog guard), `src/kanbanmate/core/columns.py` + `core/domain.py` + `core/decide.py` (interactive_only),
`src/kanbanmate/app/actions.py` (remove dead `quote_command`; agent_command docstring),
`src/kanbanmate/daemon/loop.py` (heartbeat log), `src/kanbanmate/adapters/store/fs_store.py`
(move_count breadcrumb), `src/kanbanmate/adapters/github/client.py` (class docstring),
`src/kanbanmate/core/domain.py` (Optional → `X | None`), + the matching tests.

- [ ] **#6** thread `move_rate_limit_per_hour` into the decision-time `DecideContext`/`AntiLoopConfig` so the
      configured value (columns.yml defaults) reaches the in-memory `is_blocked` guard, not just the disk
      counter (tick.py:522-532 builds DecideContext without `antiloop_config`).
- [ ] **#3** seed: pre-check the `Backlog` Status option EXISTS before creating ANY issue (port PoC
      runners.py:252-258) → fail clean, no half-seed. Add a missing-Backlog test.
- [ ] **#5** restore per-column `interactive_only`: parse it in `load_columns` → `Column.interactive_only`
      field → `decide` honours it (a column flagged interactive_only never launches unattended, regardless of
      the global `unattended_hours`). Wire the shipped `columns.yml.tmpl` flags (already declared).
- [ ] **#15** remove the dead `quote_command` (actions.py:762; superseded by `wrap_with_session_end`; the
      phase-12 wire-in gate is moot — no caller). Residual-grep zero after removal.
- [ ] **#14** add a first-occurrence `logger.warning` to the daemon heartbeat-marker write swallow
      (loop.py:397-400) so a persistent write failure is diagnosable.
- [ ] **#13** add a `_warn_corrupt_state`-style breadcrumb to `move_count_for_item_last_hour`'s corrupt→0
      degrade (fs_store.py:671-675) so a corrupt rate-limit file is visible.
- [ ] **#16/#17** correct the stale docstrings: `Deps.agent_command` (vestigial, not the launch body) +
      `GithubClient` class docstring (it satisfies BoardReader+BoardWriter+PullRequests+Seeder+doctor, not
      just "BoardReader + BoardWriter").
- [ ] **#18** `core/domain.py`: replace the residual `Optional[...]` with `X | None` (drop the `typing`
      import) for consistency (`from __future__ import annotations` is present).
- [ ] Tests for the behavioural minors (#6 configured-value reaches the guard; #3 fail-clean; #5
      interactive_only gating). Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "fix(genesis): review long-tail (rate-limit config wiring, seed Backlog guard, interactive_only, dead-code + docstrings)"
```

---

### Phase 18 Gate

1. `rm -rf .mypy_cache && make lint` — zero (ruff + mypy src tests).
2. `make test` — all pass. `make check` — clean (module-size: watch client.py 994 / tick.py 989 — extract
   if M1/Md1 push either over ~998; the reaper is already in app/reaper.py, the gate-resolver in app/depgate.py).
3. Residual / parity greps:
   - `rg --type py "parse_ticket_fields" src` → core/ticket_fields.py + actions.py (the consumer).
   - `rg --type py "\.issue_context\(" src` → a REAL consumer in actions.py (no longer dead).
   - `rg --type py "quote_command" src tests` → ZERO (dead helper removed).
   - `rg --type py "move_count_for_item_last_hour" src` → now READ by a park gate (script_route/tick), not
     just the reaper double-record guard.
4. Parity check — exercised in tests: a launched agent's prompt carries the real issue body / comments /
   codename / design path; a gated launch creates the worktree first; a schema-corrupt state warns; a
   runaway card is parked; the drain preserves a live slot.
5. `python -c "import kanbanmate"` — exits 0.
6. **Adversarial verification (ultracode)** on 18.1+18.2 (prompt enrichment keystone) + 18.5 (rate-limit
   park gate) + 18.6 (drain slot guard) before the milestone.

```bash
git commit --allow-empty -m "chore(genesis): phase 18 gate — PR-review fixes cycle 2 (prompt enrichment + correctness defects + long-tail)"
```
