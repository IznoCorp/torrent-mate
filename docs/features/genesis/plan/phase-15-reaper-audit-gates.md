# Phase 15 — Reaper retry + dispatch audit log + mechanical script gates

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Restores three CONFIRMED feature losses (POC_PARITY_AUDIT.md): the **reaper relaunch-once retry**
> before parking a stale agent in Blocked, the **append-only per-dispatch JSON audit log**, and the
> **mechanical (no-LLM) script-transition family** — the `run_script` action (auto-advance / on_fail /
> fix-CI cap) AND the script-as-GATE that vetoes a launch when its gate script fails — together with
> the two shipped check scripts (`check-pr-ready.sh` / `check-merge-ready.sh`) ported into NEW's `bin/`.
>
> PoC source of truth (ABSOLUTE OLD root —
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/`):
> `<OLD>/kanbanmate/engine/reaper.py` (`RETRY_LIMIT = 1` :22; `apply` block-retry-once :106-184;
> `_move_to_blocked` :67-103) ·
> `<OLD>/kanbanmate/audit.py` (`append_dispatch` :14-30) +
> `<OLD>/kanbanmate/engine/launch.py` (`append_dispatch(...)` call site :297-309) ·
> `<OLD>/kanbanmate/engine/scripts.py` (`run_transition_script` :26-68) ·
> `<OLD>/kanbanmate/dispatch.py` (`run_script` verdict :68-79; `launch`-carries-`script` gate :80-92) ·
> `<OLD>/kanbanmate/runner.py` (`_apply_script` :595-622; `_apply_launch` gate :625-654;
> `_on_fail` :536-570; `_auto_move` :230-250; `_park_blocked` :212-227; `_discover_branch` :573-582;
> `_script_env` :585-592; `_FIXCI_CAP = 2` :45-47; `_fixci_key` :97-105) ·
> `<OLD>/kanbanmate/transitions.py` (`Transition.script/advance/on_fail`, `has_action` :25-41) ·
> `<OLD>/kanbanmate/state.py` (`bump_retry`/`reset_retry` :205-225) ·
> `<OLD>/bin/check-pr-ready.sh`, `<OLD>/bin/check-merge-ready.sh` (the two gate scripts).
> NEW root: `/Users/izno/dev/KanbanMate/src/kanbanmate/`; NEW shipped scripts root:
> `/Users/izno/dev/KanbanMate/bin/`.

**Goal**: bring NEW to behavioural parity with the PoC on three orchestration capabilities that the
extraction dropped, none of which relate to the n8n→polling pivot (so all are unauthorised drift per
DESIGN §11):

1. **Reaper relaunch-once retry** (audit "RUNNER" §, [LOW] reaper block-with-retry-relaunch;
   reaper.py:22,106-184). A stale/dead running session is relaunched **at most `RETRY_LIMIT = 1`** time
   — kill the dead session, bump `retries`, REFRESH the heartbeat so the next sweep does not
   immediately re-block — before it is moved to Blocked. NEW's reap goes straight to Blocked on the
   first miss; DESIGN §8.3 (line 307) STILL promises the retry, so the implementation contradicts the
   design.
2. **Per-dispatch append-only audit log** (audit "RUNNER" §, [LOW] per-launch AUDIT log; audit.py:14-30,
   launch.py:297-309). One structured JSON record per launch under `<root>/log/dispatch.jsonl`, stamped
   with `logged_at`. NEW writes only a generic `daemon.jsonl`; the dedicated launch schema (issue / repo
   / to-column / profile / session / worktree / tmux / ts) is gone.
3. **Mechanical script gates** (audit "engine" §, [HIGH] run_transition_script; "TRANSITION/DISPATCH" §,
   [HIGH] run_script verdict / script-as-GATE / on_fail / advance:auto). The whole script-transition
   family: `run_transition_script` (subprocess, 120 s, merged stdout+stderr), the `RunScriptAction`
   (run a script-only transition → exit 0 auto-advances / records, exit ≠0 → on_fail move:/rollback,
   bounded by the fix-CI cap N=2 → park Blocked), AND the script-as-GATE on a launch (the gate runs
   FIRST; exit 0 launches with `{{script_output}}`, exit ≠0 → on_fail → NO agent). Plus the two shipped
   check scripts ported into `bin/`.

> **Provenance note (faithful port, deliberate divergences).** Three PoC concepts have no NEW data-model
> home today and must be threaded in: (a) `Transition.script/advance/on_fail` — NEW's `Column`
> (core/domain.py:34-46) carries no per-transition action payload, so 15.5 WIDENS the column model
> (`load_columns` already silently drops `prompt`/`script`/etc. per the audit); (b) the per-(item,key)
> retry ledger (`bump_retry`/`reset_retry`, state.py:205-225) backing the fix-CI cap; (c) the runner
> `_auto_move` triggering-bot-move. NEW keys everything by **issue number**, not content-node-id (the
> standing 8.1.d invariant) — every breadcrumb/ledger/audit key in this phase is the issue number.

---

## ⚠️ RE-SCOPE (2026-06-08, operator-approved) — §15.4–15.8 retargeted onto the existing Transition model

**Discovery during execution.** §15.4–15.7 were authored against a stale view of the code: they
assume NEW has **no** script infrastructure (`rg run_transition_script|script_runner → zero`) and
propose a **per-Column** model (`Column.script/advance/on_fail` + `ColumnClass.SCRIPT`). That premise
is **false** — phases 12–13 already shipped the whole script-transition family on a **per-`(from,to)`
Transition** model (the PoC's actual shape):

- `core/transitions.py::Transition.script/advance/on_fail` (+ `has_action`, parsing).
- `core/transitions_defaults.py::DEFAULT_TRANSITIONS` already wires **both** check scripts:
  `InProgress→PRCI` (`script: bin/check-pr-ready.sh`, `on_fail: move:InProgress`),
  `Review→Merge` (`script: bin/check-merge-ready.sh`, `on_fail: move:Review`), plus the capped
  fix-CI loop `PRCI→InProgress` (`_FIXCI_PROMPT` with `{{script_output}}`, `advance: auto:PRCI`).
- `core/domain.py::ActionKind.RUN_SCRIPT` + `ROLLBACK`; `core/decide.py` already emits both and
  threads `script`/`on_fail`/`advance` onto every `Action`.
- `app/actions.py::RunScriptAction`, `RollbackAction`, and the `LaunchAction.script/on_fail/advance`
  gate fields; `app/tick.py::_build_action` already builds them.
- `ports/workspace.py::Workspace.run_transition_script` + the worktree adapter impl (the script seam).

**The ONLY genuine remaining gap** is the **routing EXECUTION**: `RunScriptAction.execute` runs the
script but _only logs_ the verdict (_"Phase 13 consumes on_fail/advance from here"_), `LaunchAction`
never runs its `script` gate, and there is no fix-CI cap (`rg _FIXCI|park_blocked|auto_move → zero`).

**Operator decision (Option A):** drop the duplicate, re-scope onto the existing Transition model.

| sub-phase | re-scoped meaning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **15.4**  | **DONE — REVERTED.** Commit `a23a15a` removed the duplicate `ports/scripts.py` + `SubprocessScriptRunner` (superseded by `Workspace.run_transition_script`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **15.5**  | **NO-OP — already shipped.** The board wires both check scripts onto transitions (above). `Column` widening / `ColumnClass.SCRIPT` are NOT done (Transition is the model).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **15.6**  | **Script routing EXECUTION (keystone).** In the tick (it owns `next_columns`/`antiloop`/move-recording — mirror the PoC runner) + a new `app/script_route.py`: act on a RUN_SCRIPT/launch-gate verdict. exit 0 → reset fix-CI ledger + `advance:auto:<col>` triggering move (or record column) + finalize LEFT stage ✅; exit ≠0 → `on_fail:move:<col>` (bump the 15.1 `bump_retry(issue, "onfail:<col>")` ledger; `> _FIXCI_CAP=2` → reset + park Blocked) / `on_fail:rollback` → `RollbackAction` to `from_col`. LaunchAction runs its `script` gate FIRST (exit ≠0 → veto + on_fail, no agent; exit 0 → reset + capture `script_output`). Keep `tick.py` < 1000 LOC (extract the reaper to `app/reaper.py` if needed). |
| **15.7**  | **`{{script_output}}` capture → fix-CI prompt.** Persist the failing check's output so the subsequent fix-CI launch fills `{{script_output}}` (the one prompt that references it). If 15.6 already lands the capture+sink cleanly, fold here.                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **15.8**  | **Unchanged** — re-sync `bin/check-pr-ready.sh` / `check-merge-ready.sh` + env-guard tests.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |

Keys are by **issue number** throughout (the 8.1.d invariant); the fix-CI ledger is 15.1's
`retries/<issue>__onfail:<col>`. Auto-moves (`advance:auto` / `on_fail:move`) are TRIGGERING bot
moves (leave the diff baseline at the script column so the next poll re-fires; record against the
move rate-limit, NOT anti-loop-suppressed); park-Blocked / rollback are bookkeeping (set the baseline
to the bounce target so they do NOT re-fire — the NEW analog of the PoC `record_bot_move`).

---

## Gate

Phases 1–14 complete; branch `feat/genesis`; `make check` green at start. Re-sync confirmed (DESIGN §11
pre-implementation gate): the PoC reaper-retry, `audit.append_dispatch`, `engine/scripts.py`, and the
two `bin/check-*.sh` scripts are present in `.claude/skills/kanban/` and read for this port. The
8.1.d advance-breadcrumb + the 8.2.a PR port are already landed (this phase builds on them).

**IMPORTANT before any gate check**: `rm -rf .mypy_cache` — this repo's incremental mypy cache has
masked real errors; always clear it before an authoritative `make lint` / `make check`.

---

## 15.1 — Reaper retry ledger: widen `TicketState` (`retries`) + fs-store bump/reset

**The gap.** OLD's reaper relaunch-once is backed by a `retries` counter persisted on the running
ticket (`data["retries"]`, reaper.py:155-166) plus the `bump_retry`/`reset_retry` ledger (state.py:205-225,
used by the fix-CI cap too). NEW's `TicketState` (`ports/store.py:39-82`) has NO `retries` field, and the
fs store has no bump/reset; `rg --type py "retries|retry" src/` finds zero reaper-retry logic. This
sub-phase adds the persistence ONLY (the reap-step wiring is 15.2; the fix-CI cap reuses the same ledger
in 15.7).

**Layer**: `ports/` (extend `TicketState` + the `StateStore` Protocol — pure) · `adapters/store/` (fs
ledger, mirrors the PoC `retries/` impl). **Files**: `src/kanbanmate/ports/store.py` (extend),
`src/kanbanmate/adapters/store/fs_store.py` (add `retries/` dir + the two methods + purge in
`release_slot`), `tests/adapters/test_fs_store.py` (extend), `tests/app/test_actions.py` (extend — the
widened `TicketState` round-trip via `LaunchAction.save`).

- [ ] **WIDEN `TicketState`** with one defaulted field (so old-format on-disk state still loads via
      `TicketState(**data)` — assert the absent-field load): `retries: int = 0` — how many times the
      reaper has relaunched this stale session (reaper relaunch-once budget; capped at
      `reaper.RETRY_LIMIT`). English docstring. Defaulted last, after the 8.1.d metadata fields.
- [ ] Add the per-(issue,key) retry ledger to the `StateStore` Protocol + the fs adapter, ported from
      the PoC `state.py:205-225` but **RE-KEYED by issue number** (the standing 8.1.d invariant; OLD
      keyed by `<safe-item>__<key>`). The marker file is `<root>/retries/<issue>__<key>`:
  - `bump_retry(self, issue_number: int, key: str) -> int` — increment the per-(issue,key) counter
    (starts at 1 on first bump, matching OLD's `bump_retry`), persist `{"n": count}`, return the new
    count. Atomic temp-file + `os.replace` like every other fs-store write.
  - `reset_retry(self, issue_number: int, key: str) -> None` — unlink the marker; no-op if absent
    (swallow `FileNotFoundError`, mirror the PoC).
  - Constructor creates `<root>/retries/` alongside `state/`, `slots/`, `advances/` (fs_store.py:56-59).
  - `release_slot` must ALSO purge this issue's retry markers (a cancelled/finished ticket leaves no
    stale ledger — mirror OLD's `purge_ticket` cleanup of `retries/`). Glob `<root>/retries/<issue>__*`
    and unlink-if-exists / no-raise (idempotent; called on both cancel + clean-exit paths).
- [ ] **Key-shape note (load-bearing).** The reaper retry (15.2) uses the bare ledger field
      `TicketState.retries` (a per-ticket count, not the `(issue,key)` ledger), while the fix-CI cap
      (15.7) uses `bump_retry(issue, "onfail:<col>")`. BOTH live in this fs store; document in the
      method docstrings that the reaper-retry counter rides on `TicketState.retries` (refreshed via
      `save`) and the fix-CI cap rides on the `retries/<issue>__onfail:<col>` ledger — two distinct
      counters, never conflated (the PoC also kept them separate: `data["retries"]` vs `bump_retry`).
- [ ] Tests: a saved-then-loaded `TicketState` round-trips `retries`; an old-format state file WITHOUT
      `retries` still loads (default 0); `bump_retry(issue, "onfail:PR Ready")` returns 1 then 2 then 3;
      `reset_retry` removes the marker (no-op when absent); `release_slot` purges BOTH `advances/` (8.1.d)
      AND `retries/<issue>__*`; the two ledgers (per-issue `retries` vs `onfail:<col>`) do not collide.
- [ ] Verify: `make check` green; layering guard sees the new field/methods stay within
      `ports/`+`adapters/store/` (no upward import).

```bash
git commit -m "feat(genesis): widen TicketState (retries) + fs-store retry ledger (bump/reset, purge on release)"
```

---

## 15.2 — Reaper relaunches a stale session ONCE before Blocked (`RETRY_LIMIT = 1`)

**The gap.** OLD `engine/reaper.py:22,106-184`: on a `block` action, if `launch_next is not None and
retries < RETRY_LIMIT`, it KILLS the dead session, bumps `data["retries"]`, sets status back to
`running`, REFRESHES the heartbeat (`data["heartbeat"] = now`) so the next sweep does not immediately
re-block, and calls `launch_next(issue)` to relaunch; a relaunch that RAISES is caught and parks the
ticket in Blocked (reaper.py:173-182). Only when `retries >= RETRY_LIMIT` (or no launcher) does it fall
through to `_move_to_blocked`. NEW's `_reap_stale_agents` (`app/tick.py:321-423`) reaps straight to
Blocked on the first miss — NO retry counter, NO single relaunch, NO heartbeat refresh — contradicting
DESIGN §8.3 line 307 ("A retry refreshes the heartbeat so the next tick does not immediately re-block it").

**Layer**: `app/` (the imperative shell — needs the live store + writer + a launcher). **Files**:
`src/kanbanmate/app/tick.py` (`_reap_stale_agents` + a `RETRY_LIMIT` constant + a relaunch helper),
`tests/app/test_tick.py` (extend).

- [ ] Add `RETRY_LIMIT = 1` at module scope in `tick.py` (port `reaper.RETRY_LIMIT`; English docstring
      comment: a stale/dead running session is relaunched at most this many times before Blocked).
- [ ] Rework `_reap_stale_agents`: for each stale `state` (heartbeat past `config.heartbeat_ttl`), decide
      RETRY vs BLOCK **before** the existing block+teardown+move+⛔ sequence:
  - **RETRY branch** (`state.retries < RETRY_LIMIT`): post the stall reason comment (BlockAction, as
    today, so the operator sees WHY a relaunch happened), then KILL the dead tmux session if alive
    (`deps.sessions.is_alive`/`kill` guard — mirror the PoC's `tmux.has_session`/`kill`), then
    `deps.store.save(replace(state, retries=state.retries + 1, status=RUNNING, heartbeat=now))` — the
    heartbeat REFRESH is load-bearing (DESIGN §8.3; without it the very next sweep re-blocks the freshly
    retried ticket). Then dispatch a fresh `LaunchAction(ticket)` for the SAME stage so the agent
    restarts (reconstruct the `Ticket` with `column_key=state.stage` so the relaunch re-enters the
    correct column). Wrap `LaunchAction.execute` in try/except: **a relaunch that raises falls through
    to the BLOCK branch** (port reaper.py:173-182 — one bad retry must not starve the sweep; the ticket
    gets a visible Blocked signal). Count a successful retry as `reaped += 1` is WRONG — it was NOT
    reaped; count it separately (extend `TickResult`/tally with a `relaunched` count, or fold into
    `actions_executed`; do not inflate `reaped`). The retry re-uses the dead session's IDEMPOTENT slot —
    it never reserves a new one (port the reaper.py:167-172 note).
  - **BLOCK branch** (`state.retries >= RETRY_LIMIT`, OR a relaunch raised): the EXISTING NEW flow
    unchanged — BlockAction comment + TeardownAction (kill/remove worktree/release slot, which also
    resets retries via 15.1's `release_slot` purge) + `_ReapMove` to `config.blocked_column` + record the
    anti-loop move + the ⛔ sticky flip via `header_from_state(state, …, "blocked", finished=…)`.
- [ ] **Launcher seam.** `_reap_stale_agents` must be able to relaunch. Reuse the SAME `LaunchAction`
      path the decided-action loop uses (do NOT invent a second launch path): construct
      `LaunchAction(ticket=Ticket(item_id=state.item_id, issue_number=state.issue_number,
  title=f"ticket-{state.issue_number}", column_key=state.stage))` and run it under the existing
      `_run_with_watchdog(executor, …)` so a hung relaunch cannot freeze the sweep. If `state.stage == ""`
      (old-format state with no recorded stage), SKIP the retry and go straight to BLOCK (a relaunch with
      no column would re-enter nothing — fail-soft).
- [ ] Tests: a stale agent with `retries == 0` is RELAUNCHED once — assert the dead session is killed, a
      fresh `LaunchAction` runs for `state.stage`, the saved state has `retries == 1` + `status==RUNNING` + `heartbeat == now` (refreshed), and the card is NOT moved to Blocked; a SECOND stale sweep
      (`retries == 1 >= RETRY_LIMIT`) goes to Blocked (the existing flow, ⛔ flip, slot released); a
      relaunch that RAISES parks the ticket in Blocked (caught, sweep continues); a stale agent with
      `stage == ""` skips the retry and blocks directly; the `relaunched` count is reported separately
      from `reaped`.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): reaper relaunches a stale session once before Blocked (port reaper RETRY_LIMIT)"
```

---

## 15.3 — Per-dispatch append-only audit log (`dispatch.jsonl`)

**The gap.** OLD `audit.append_dispatch` (audit.py:14-30) writes ONE structured JSON record per launch to
`<root>/log/dispatch.jsonl`, shallow-copied + stamped with `logged_at` (epoch). It is CALLED on every
launch (launch.py:297-309) with `{issue, repo, to, permission_profile, session_uuid, worktree, tmux, ts}`.
NEW has NO `append_dispatch` / `dispatch.jsonl` — only a generic `daemon.jsonl` (daemon/jsonl_log.py)
which captures logging records, missing every structured launch field. `LaunchAction.execute` writes no
audit record. `rg --type py "dispatch.jsonl|append_dispatch|logged_at" src` → zero matches today.

**Layer**: a fs-store side-effect (the audit log lives under the `~/.kanban` root the store owns). To keep
`LaunchAction` pure of path/JSON I/O, the append goes through a port. **Files**:
`src/kanbanmate/ports/store.py` (add `append_dispatch` to the `StateStore` Protocol),
`src/kanbanmate/adapters/store/fs_store.py` (implement it — `<root>/log/dispatch.jsonl`),
`src/kanbanmate/app/actions.py` (`LaunchAction.execute` step 6 — write the record),
`tests/adapters/test_fs_store.py` (extend), `tests/app/test_actions.py` (extend).

- [ ] Add `append_dispatch(self, record: dict[str, object]) -> None` to the `StateStore` Protocol. English
      docstring: append one JSON line per dispatch to `<root>/log/dispatch.jsonl`; the record is
      shallow-copied + stamped with `logged_at` (epoch) before write, so callers may pass a literal dict
      without mutation surprises. Fail-soft is the CALLER's responsibility (see step on `LaunchAction`).
- [ ] Implement it on the fs adapter, ported verbatim-in-spirit from `audit.py:24-30`: `mkdir -p
  <root>/log`, `stamped = dict(record); stamped["logged_at"] = time.time()`,
      `json.dumps(stamped, ensure_ascii=False)`, append-open + write the line + `"\n"`. Encoding `utf-8`.
      (Use the store's injected clock if one exists for determinism; otherwise `time.time()` matching OLD
      — but PREFER threading `now` from the caller so the test can assert the field, see next bullet.)
  - **Determinism**: OLD stamps `logged_at` with `time.time()` INTERNALLY. NEW already injects a `Clock`
    everywhere for testability — but `append_dispatch` is on the STORE, not the action. Keep the OLD
    shape (`time.time()` inside the adapter) so the port stays clock-free, AND have `LaunchAction` put
    `ts=now` (the injected clock's now) IN the record — the test asserts `ts` (deterministic) and only
    that `logged_at` EXISTS (a float), not its exact value. Document this split.
- [ ] `LaunchAction.execute` step 6 (after the 🟡 sticky, step 5): write the dispatch record. Mirror OLD's
      launch.py:297-309 field set, mapped to NEW: `{"issue": issue, "repo": <repo>, "to":
  self.ticket.column_key, "permission_profile": deps.profile, "session_uuid": session_id, "worktree":
  str(worktree), "tmux": session_name, "ts": now}`. **Repo source**: `LaunchAction`/`Deps` carries no
      `repo` today — add a `repo: str = ""` policy field to `Deps` (wired from `WiringConfig.repo` in
      `build_deps`, the same `config.repo` already passed to `GithubClient`), so the audit record carries
      the repo OLD recorded. **FAIL-SOFT**: wrap the `deps.store.append_dispatch(...)` in its own
      try/except → `logger.exception(...)` + continue; an audit-log write failure must NEVER break a
      launch (the agent already started). Place it LAST so even a failure leaves a fully-launched ticket.
- [ ] Wire `Deps.repo` in `app/wiring.py::build_deps` (`repo=config.repo`); keep `Deps` frozen. Update the
      reaper-relaunch `LaunchAction` (15.2) — it reuses the same `Deps`, so the relaunch ALSO appends a
      dispatch record (faithful: OLD's `launch_next` went through `start_session` → `append_dispatch` too).
- [ ] Tests: a successful `LaunchAction` appends exactly one JSON line to `<root>/log/dispatch.jsonl`
      carrying issue/repo/to/permission_profile/session_uuid/worktree/tmux/ts, plus a `logged_at` float;
      a second launch appends a SECOND line (append-only, not overwrite); an `append_dispatch` failure
      (inject a store raiser) is swallowed and the launch still completes (state saved, sticky posted);
      `ensure_ascii=False` (a non-ASCII repo/title round-trips).
- [ ] Verify: `make check` green. Residual grep: `rg --type py "dispatch.jsonl" src` matches only the fs
      adapter; `rg --type py "append_dispatch" src` matches the port + adapter + `LaunchAction`.

```bash
git commit -m "feat(genesis): per-dispatch append-only audit log (dispatch.jsonl, port append_dispatch)"
```

---

## 15.4 — `run_transition_script` adapter + `ScriptRunner` port (mechanical subprocess seam)

**The gap.** OLD `engine/scripts.py::run_transition_script` (scripts.py:26-68) runs a plain subprocess (no
claude session), merges `env` over `os.environ` (caller wins), 120 s timeout, returns `(exit_code,
stdout+stderr)`, resolves a RELATIVE script path against the skill root. NEW has NO script runner at all
(`rg --type py "run_transition_script|script_runner" src` → zero); `core/domain.py` ActionKind has no
`RUN_SCRIPT`. This sub-phase ports the runner BEHIND a port (the action stays subprocess-free, hexagonal),
landing the lowest layer first so 15.5–15.6 can wire it.

**Layer**: `ports/` (new `ScriptRunner` Protocol — pure) · `adapters/` (new subprocess adapter
implementing it). **Files**: `src/kanbanmate/ports/scripts.py` (new — the `ScriptRunner` Protocol),
`src/kanbanmate/adapters/scripts/__init__.py` (new), `src/kanbanmate/adapters/scripts/runner.py` (new —
`SubprocessScriptRunner`, port of `engine/scripts.py`), `tests/ports/` (or fold into the adapter test),
`tests/adapters/test_scripts.py` (new).

- [ ] Add `ports/scripts.py` with a `ScriptRunner` Protocol:
      `run(self, script_path: str, *, env: dict[str, str], timeout: int = 120) -> tuple[int, str]` —
      returns `(exit_code, combined_output)` (stdout + stderr merged so on_fail/advance logic sees both,
      port scripts.py:67). English docstring documenting the merged-output contract + the 120 s default +
      `subprocess.TimeoutExpired` raise on overrun.
- [ ] Add `adapters/scripts/runner.py::SubprocessScriptRunner` implementing it, ported from
      `engine/scripts.py:26-68`:
  - `_TIMEOUT = 120` (port scripts.py:23, the same comment rationale: long enough for `gh pr checks`,
    short enough to fail fast on a hung network).
  - Resolve a relative `script_path` against a configured ROOT. **Divergence from OLD**: OLD's `_SKILL_ROOT`
    is `Path(__file__).resolve().parent.parent.parent` (the `skills/kanban/` dir). NEW's scripts ship at
    the REPO `bin/` root (`/Users/izno/dev/KanbanMate/bin/`), NOT under `src/kanbanmate/`. Make the root
    INJECTABLE: `SubprocessScriptRunner(scripts_root: Path)` — `build_deps`/wiring passes the per-clone
    worktree's repo root (or the installed package's repo root) so a config entry like
    `"bin/check-pr-ready.sh"` resolves to the shipped script. Absolute paths are used verbatim
    (`path.is_absolute()` guard, port scripts.py:54-56). Document the root divergence.
  - `merged_env = {**os.environ, **env}` (caller wins, port scripts.py:58).
  - `subprocess.run([str(path)], env=merged_env, capture_output=True, text=True, timeout=timeout)` with the
    `# nosec B603` marker (port scripts.py:60); return `(result.returncode, result.stdout + result.stderr)`.
  - **CLAUDE.md network safety**: the 120 s timeout is the per-script wall-clock bound (the check scripts
    shell out to `gh`); document that the timeout is mandatory and never unbounded.
- [ ] Tests: a 0-exit script returns `(0, combined)`; a non-zero exit returns the code + merged output; a
      relative path resolves against the injected root; an absolute path is used verbatim; injected env
      vars reach the script (a script echoing `$KANBAN_REPO` returns it); a sleeping script over `timeout`
      raises `subprocess.TimeoutExpired` (use a tiny `timeout=1` + `sleep 2` fixture). Keep test scripts as
      `tmp_path` shell files (chmod +x) — do NOT depend on the real `bin/check-*.sh` (those need `gh`).
- [ ] Verify: `make check` green; layering guard sees `ports/scripts.py` import nothing with I/O and
      `adapters/scripts/` implement the port (downward-only).

```bash
git commit -m "feat(genesis): ScriptRunner port + subprocess adapter (port run_transition_script)"
```

---

## 15.5 — Widen the column/transition model to carry `script` / `advance` / `on_fail`

**The gap.** OLD `Transition` carries `script` / `advance("stop"|"auto:<col>")` / `on_fail("" |
move:<col> | rollback)` + `has_action = prompt OR script` (transitions.py:25-41). NEW's `Column`
(core/domain.py:34-46) and `load_columns` (core/columns.py:50-89) parse ONLY `key/name/triggers_agent/
action` and SILENTLY DROP every richer key (the audit's repeated finding). With no data-model home a
script transition is unrepresentable. This sub-phase widens the column model so a column can carry a
mechanical script + its advance/on_fail policy (NEW's per-COLUMN model is the chosen shape — a script
column is a column whose `script` is set, mirroring how `triggers_agent`/`action` already classify).

> **Per-column vs per-(from,to) note.** The audit flags that NEW's per-column model cannot express two
> DIFFERENT scripts landing in the SAME destination from two origins (OLD's per-(from,to) whitelist could).
> That broader whitelist/rollback restoration is OUT OF SCOPE for THIS phase (it is its own audit cluster).
> Here we restore ONLY the script-gate / advance / on_fail vocabulary on the per-column model — the shipped
> board (`Implement→PR Ready` check, `Review→Merge` gate) needs exactly one script per destination column,
> which the per-column model expresses faithfully. Document this scoping in the column docstring.

**Layer**: `core/` (pure — extend `Column` + `load_columns`). **Files**: `src/kanbanmate/core/domain.py`
(extend `Column`), `src/kanbanmate/core/columns.py` (parse the new keys), `tests/core/test_columns.py`
(extend), `src/kanbanmate/assets/columns.yml.tmpl` (wire the two shipped scripts onto the right columns).

- [ ] Extend `Column` (core/domain.py:34-46) with three defaulted fields (defaults keep every existing
      `Column(key, name, column_class)` construction valid):
  - `script: str = ""` — a mechanical gate/transition script path (relative to the scripts root, 15.4).
    A column with a non-empty `script` is a SCRIPT column (run mechanically) UNLESS it is also an AGENT
    column, in which case the script is a pre-launch GATE (15.6). English docstring.
  - `advance: str = "stop"` — `"stop"` | `"auto:<column>"`: on a successful script run, auto-move the card
    to `<column>` (a triggering bot move, 15.7). Port `Transition.advance`.
  - `on_fail: str = ""` — `""` | `"move:<column>"` | `"rollback"`: routing when the script exits non-zero
    (15.7). Port `Transition.on_fail`.
- [ ] Extend `load_columns` (core/columns.py:78-89) to parse `script` / `advance` / `on_fail` off each
      entry (string-typed; default `""`/`"stop"`/`""`). Keep the existing `key`/`name`/`triggers_agent`/
      `action` parse + the `_resolve_class` precedence unchanged. NB this also stops silently dropping
      `script` — the audit's documented bug. Do NOT parse `prompt`/`permission_profile`/`interactive_only`
      here (those are separate audit clusters; only the script-gate trio is in scope).
- [ ] **Column-class interaction (load-bearing).** A column with `script` set but `triggers_agent: false`
      and no `action: teardown` must classify as a NEW class so `decide` (15.6) can route it mechanically.
      Add `ColumnClass.SCRIPT` to `core/domain.py` and have `_resolve_class` return it when `script` is set
      and `triggers_agent` is falsy (port OLD's `dispatch.py:68` "script and not prompt → run_script";
      here "script and not triggers_agent → SCRIPT"). An AGENT column that ALSO carries `script` stays
      AGENT (the script is its launch GATE, 15.6) — agent-flag-wins precedence is preserved. Document the
      truth table in `_resolve_class`.
- [ ] Wire the shipped board (`assets/columns.yml.tmpl`): set `script: bin/check-pr-ready.sh` +
      `on_fail: move:InProgress` on the `PR Ready`-equivalent CHECK column (a SCRIPT column — mechanical,
      no agent), and `script: bin/check-merge-ready.sh` + `on_fail: move:Review` on the `Merge`-equivalent
      AGENT column (a launch GATE before the squash-merge agent). Mirror OLD's transitions_yaml.py:117-145
      semantics onto NEW's column names. (If the template lacks a dedicated check column, add one INERT→
      SCRIPT column matching the shipped board; keep the column count consistent with the DESIGN §9 board.)
- [ ] Tests: `load_columns` parses `script`/`advance`/`on_fail`; a `script`-only column classifies SCRIPT;
      a `triggers_agent` column with a `script` stays AGENT (gate); a plain column keeps `script==""` and
      classifies INERT; the shipped template parses with the two check scripts on the right columns.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): widen Column model with script/advance/on_fail + ColumnClass.SCRIPT"
```

---

## 15.6 — `decide` emits `RUN_SCRIPT` + `RunScriptAction` + the launch GATE veto

**The gap.** OLD `dispatch.py:68-79` returns `Decision("run_script")` for a script-only transition (the
runner runs it via `_apply_script`, runner.py:595-622), and `dispatch.py:80-92` packs `script=t.script`
onto a `launch` Decision so `_apply_launch` (runner.py:625-654) runs that GATE FIRST — exit ≠0 → on_fail →
NO agent; exit 0 → launch with `{{script_output}}`. NEW's `decide` (core/decide.py:133-226) only ever emits
LAUNCH/TEARDOWN/RESET/BLOCK/NOOP; `LaunchAction` (app/actions.py:114-173) launches UNCONDITIONALLY (no
gate). This sub-phase wires the SCRIPT class into `decide` + a `RunScriptAction` + the pre-launch gate.

> **Scope split.** The on_fail/advance EXECUTION (move:/rollback/auto + fix-CI cap) is 15.7. THIS sub-phase
> wires (a) the `RUN_SCRIPT` verdict + `RunScriptAction` skeleton that RUNS the script and reports exit, and
> (b) the launch GATE veto. 15.7 layers the routing on top. Keeping them separate keeps each commit's
> `make check` self-contained.

**Layer**: `core/` (decide) + `app/` (actions + tick wiring). **Files**: `src/kanbanmate/core/domain.py`
(`ActionKind.RUN_SCRIPT`), `src/kanbanmate/core/decide.py` (SCRIPT-class branch), `src/kanbanmate/app/
actions.py` (`Deps.script_runner`, `RunScriptAction`, `LaunchAction` gate step 0), `src/kanbanmate/app/
tick.py` (`_build_action` RUN_SCRIPT branch + execute), `src/kanbanmate/app/wiring.py` (wire the script
runner), `tests/core/test_decide.py`, `tests/app/test_actions.py`, `tests/app/test_tick.py` (extend).

- [ ] `core/domain.py`: add `ActionKind.RUN_SCRIPT = "run_script"` (port OLD's `run_script` kind). Extend
      the enum docstring.
- [ ] `core/decide.py`: when the destination resolves to a `ColumnClass.SCRIPT` column, return
      `Action(kind=ActionKind.RUN_SCRIPT, ticket=…, reason="script")` (port dispatch.py:68-79's "script and
      not prompt → run_script"). The SCRIPT branch sits ALONGSIDE the existing AGENT/REACTIVE/INERT
      classification; keep `decide` PURE (it only classifies — the runner/action runs the subprocess).
      The kill-switch / anti-loop / unattended-window guards do NOT apply to a mechanical SCRIPT run (it
      spends no agent) — gate ONLY the LAUNCH branch as today; a SCRIPT run is always emitted (the
      read-only check may run while paused, mirroring OLD's `_apply_launch` gate-may-run-while-paused note,
      runner.py:656-658). Document this.
- [ ] `app/actions.py`: add `script_runner: ScriptRunner` to `Deps` (frozen; wired in 15.4's adapter). Add
      `RunScriptAction(ticket)`:
  - resolve the column's `script` + the per-ticket worktree BRANCH: call
    `deps.workspace.ensure_worktree(issue, base=deps.base)` then `deps.workspace.discover_branch(issue)`
    (port `_discover_branch`, runner.py:573-582 — a freshly-DETACHED worktree reports `"HEAD"`, an honest
    answer that correctly FAILS a PR check and takes on_fail).
  - build the script env `{"KANBAN_REPO": deps.repo, "KANBAN_BRANCH": branch}` (port `_script_env`,
    runner.py:585-592 — the check scripts hard-require both via `: "${KANBAN_REPO:?}"`).
  - run `code, out = deps.script_runner.run(script, env=env)`.
  - **THIS sub-phase**: on exit 0, the script SUCCEEDED — finalize the LEFT stage ✅ via the existing
    `_finalize_left_stage` seam (port runner.py:618-620: an accepted non-rollback forward script move
    finalizes the LEFT stage; the advance:auto move itself is 15.7) and return; on exit ≠0, log + return
    (the on_fail ROUTING is 15.7 — for now a failed script just logs and takes no board action, a safe
    intermediate state the 15.7 commit replaces). Document the TODO-for-15.7 in the action docstring so
    the reviewer knows the routing lands next.
- [ ] **Launch GATE (port `_apply_launch`, runner.py:625-654).** `LaunchAction.execute`: BEFORE step 1
      (worktree) runs the SAME worktree+branch discovery, then if the column carries a `script`, run it as
      a GATE FIRST: `code, out = deps.script_runner.run(script, env={"KANBAN_REPO": deps.repo,
  "KANBAN_BRANCH": branch})`. Exit ≠0 → **VETO the launch**: do NOT materialise settings, do NOT launch
      tmux, do NOT save running state, do NOT post 🟡 — return early (the on_fail routing is 15.7; here the
      veto just aborts the launch + logs). Exit 0 → keep `out` as `script_output` (stash it for the agent
      prompt — NEW's prompt is a static `agent_command` today, so `script_output` has no placeholder sink
      yet; record it in the dispatch audit record's `script_output` field for observability and document
      that prompt-placeholder wiring is a separate audit cluster). The GATE needs the column on the
      `Ticket`; thread the resolved `Column` (with `script`) into the action via `_build_action` (it
      already has `config.columns`).
- [ ] `app/tick.py::_build_action`: add a `RUN_SCRIPT` branch → `RunScriptAction(ticket=action.ticket)`;
      resolve the column so the action sees its `script`/`advance`/`on_fail` (pass the `Column` or look it
      up via `resolve_column(config.columns, to_column)` inside the action's deps — prefer threading the
      resolved `Column` onto the action to keep it pure of `config`). Execute it under the existing
      `_run_with_watchdog` (a check script that shells out to `gh` must be watchdog-bounded). A `RUN_SCRIPT`
      transition advances the diff baseline like any other (the script ran; the next diff compares against
      the new column).
- [ ] `app/wiring.py`: construct `SubprocessScriptRunner(scripts_root=…)` and pass it into `Deps`
      (`script_runner=…`). Thread `scripts_root` from `WiringConfig` (the repo/clone root where `bin/` lives).
- [ ] Tests: `decide` emits `RUN_SCRIPT` for a SCRIPT column; `RunScriptAction` runs the script with
      `KANBAN_REPO`+`KANBAN_BRANCH` from the discovered branch (a detached worktree → `KANBAN_BRANCH=HEAD`);
      on exit 0 the LEFT stage is finalized ✅; the LAUNCH GATE vetoes the launch on a non-zero gate script
      (assert NO tmux launch, NO state saved, NO 🟡) and proceeds on exit 0 (launch happens, `script_output`
      captured); a script transition runs under the watchdog.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): decide emits RUN_SCRIPT + RunScriptAction + pre-launch gate veto (port _apply_script/_apply_launch gate)"
```

---

## 15.7 — `on_fail` routing + `advance:auto` + the fix-CI cap (N=2 → park Blocked)

**The gap.** OLD wires the failure/success ROUTING around the script run: `_on_fail` (runner.py:536-570) —
`on_fail="move:<col>"` is an AUTO bot move that DOES re-trigger, bounded by `_FIXCI_CAP = 2` per-loop
(keyed by destination column, `_fixci_key`); beyond the cap → `_park_blocked` (runner.py:212-227);
`on_fail="rollback"`/`""` → guarded rollback to `from`. On SUCCESS, `_apply_script` (runner.py:607-617)
reads `advance`: `auto:<col>` → `_auto_move` (a triggering bot move, runner.py:230-250); else just record
the column. NEW has NONE of this (`rg --type py "on_fail|advance:auto|_FIXCI" src` → zero). This sub-phase
completes the script family: success-advance + failure-routing + the bounded retry cap.

**Layer**: `app/` (the routing is imperative — it issues board moves + reads the 15.1 ledger). **Files**:
`src/kanbanmate/app/actions.py` (`RunScriptAction` routing + `LaunchAction` gate on_fail), a small
`app/script_route.py` helper (new — the on_fail/advance logic, reused by the run_script path AND the gate
path), `src/kanbanmate/app/tick.py` (the moves it issues feed `record_move`), `tests/app/test_actions.py`,
`tests/app/test_script_route.py` (new), `tests/app/test_tick.py` (extend).

- [ ] Add `app/script_route.py` with the two routing helpers (port `_on_fail` + `_auto_move` + the cap),
      keyed by ISSUE number:
  - `_FIXCI_CAP = 2` (port runner.py:45-47 — distinct from any concurrency cap; English comment).
  - `fixci_key(column: str) -> str` → `f"onfail:{column}"` (port `_fixci_key`, runner.py:97-105 — per-loop
    budget so two on_fail loops never share one budget).
  - `apply_on_fail(deps, ticket, column: Column, *, now) -> None` — port `_on_fail`:
    - `on_fail = column.on_fail or ""`.
    - `move:<target>` → `count = deps.store.bump_retry(issue, fixci_key(column.key))`; if
      `count > _FIXCI_CAP`: `deps.store.reset_retry(issue, fixci_key(column.key))` + PARK in Blocked
      (`deps.board_writer.move_card(item_id, blocked_column)` + a recap comment "check {col} failed after
      {N} attempts — parked in Blocked", port `_park_blocked`, runner.py:212-227); else AUTO-MOVE the card
      to `<target>` (`move_card(item_id, target)` — a triggering bot move that DOES re-enter the board, so
      the next diff reacts; record it via the tick's `record_move` so the anti-loop guard recognises the
      daemon's own move, mirroring the 15.2 reaper-move pattern). **NB**: the auto-move must NOT be
      anti-loop-dedup-suppressed (port `_auto_move`'s explicit "NOT recorded as a recent bot move"
      note, runner.py:233-235) — it FEEDS the rate-limit backstop but is re-processed normally.
    - `rollback` / `""` → move the card back to `from_column` as a bookkeeping move (port the guarded
      rollback target = `from`, runner.py:565-570). NEW has no ROLLBACK ActionKind (out of scope), so
      express this as a `move_card(item_id, from_column)` + a "check failed — returned to {from}" comment;
      record it as a bot move that does NOT re-trigger (it returns to the origin). Document that the full
      guarded-rollback restoration is a separate audit cluster; here it is a best-effort return-to-origin.
  - `apply_advance(deps, ticket, column: Column, *, now) -> None` — port the success path
    (runner.py:607-617): `deps.store.reset_retry(issue, fixci_key(column.key))` (reset THIS loop's counter
    on success), then if `column.advance.startswith("auto:")`: `target = column.advance[len("auto:"):].
strip()`; AUTO-MOVE to `<target>` (triggering bot move, recorded for the rate-limit). Else: no move
    (the card already sits in the script column; the daemon recorded its column on the diff baseline).
- [ ] `RunScriptAction` (15.6): replace the 15.6 placeholder — on exit 0 → `apply_advance(...)` THEN
      `_finalize_left_stage` ✅; on exit ≠0 → `apply_on_fail(...)`. Keep each branch fail-soft (per-step
      try/except → `logger.exception`).
- [ ] `LaunchAction` GATE (15.6): on a non-zero gate exit, call `apply_on_fail(deps, ticket, column, …)`
      instead of the bare 15.6 veto-and-log (the gate's on_fail is the SAME routing — port
      `_apply_launch`'s `return _on_fail(...)`, runner.py:650-652). The launch is still vetoed (the
      on_fail move/rollback replaces the launch).
- [ ] **fix-CI cap budget keying (load-bearing).** The two on_fail loops (`Implement→PR Ready` and
      `Review→Merge`) must have INDEPENDENT budgets — `fixci_key` keys on the SCRIPT/destination column's
      key, never a shared constant (port runner.py:546-548). Assert two columns' budgets do not collide.
- [ ] Tests (`test_script_route.py` + extend `test_actions.py`): a script success with `advance:auto:Next`
      moves the card to `Next` (triggering bot move, recorded); a script success with `advance:stop` issues
      no move; a failure with `on_fail:move:Back` bumps the retry counter and moves to `Back`; the 3rd
      consecutive failure (count > 2) parks in Blocked + resets the counter; a failure with
      `on_fail:rollback` returns the card to `from_column`; the two on_fail loops keep independent budgets;
      every routing step is fail-soft (a writer raise is swallowed); the LAUNCH gate's on_fail routes the
      same way (no agent launched).
- [ ] Verify: `make check` green. Residual grep: `rg --type py "on_fail|advance:auto|_FIXCI|fixci" src`
      matches only the new script-route helper + the column model + tests (no stray references).

```bash
git commit -m "feat(genesis): script on_fail routing + advance:auto + fix-CI cap (port _on_fail/_auto_move/_park_blocked)"
```

---

## 15.8 — Sync the two check scripts into `bin/` (port-faithful, agent + gate dual-use)

**The gap.** OLD ships `bin/check-pr-ready.sh` (mechanical Implement→PR Ready check: PR exists + CI green)
and `bin/check-merge-ready.sh` (Review→Merge gate: PR open + reviews resolved/approved + CI green). NEW's
`bin/` already has both files (`ls /Users/izno/dev/KanbanMate/bin/`), but per the audit they were RELABELED
"agent-facing readiness check" and are NO LONGER wired as a daemon gate. Now that 15.5–15.7 wire the
mechanical gate, the scripts must be the FAITHFUL PoC versions (the daemon runs them via `KANBAN_REPO` +
`KANBAN_BRANCH`, the exact env contract `_script_env` provides) — re-sync them against the PoC source so
the daemon-gate contract holds, while staying usable as an agent-facing tool too.

**Layer**: shipped scripts (no Python). **Files**: `/Users/izno/dev/KanbanMate/bin/check-pr-ready.sh`,
`/Users/izno/dev/KanbanMate/bin/check-merge-ready.sh`, `tests/test_check_scripts.py` (new — port OLD's
`tests/cli/test_check_scripts.py`: assert the env-var guards + exit-code contract without hitting `gh`).

- [ ] Re-sync `bin/check-pr-ready.sh` against the PoC (`<OLD>/bin/check-pr-ready.sh`): the
      `: "${KANBAN_REPO:?}"` + `: "${KANBAN_BRANCH:?...}"` guards (the daemon-gate env contract), the
      `gh pr view "$KANBAN_BRANCH"` PR lookup, the `gh pr checks` CI-green parse (failing + pending checks),
      exit 0 = PR open & CI green, exit 1 = PR missing / CI not green. `set -euo pipefail`. Keep the
      `#!/usr/bin/env bash` shebang + executable bit (`chmod +x`). Update the header comment to name BOTH
      roles: the daemon's mechanical SCRIPT-column check (15.5–15.7) AND an agent-facing readiness tool.
- [ ] Re-sync `bin/check-merge-ready.sh` against the PoC (`<OLD>/bin/check-merge-ready.sh`): the same env
      guards, PR-open check, `reviewDecision` gate (`CHANGES_REQUESTED`/`REVIEW_REQUIRED` → fail), the
      unresolved-review-threads parse, the CI-green parse; exit 0 = reviews resolved/approved + CI green
      (safe to merge), exit 1 otherwise. Same shebang/exec-bit. This is the LAUNCH GATE the merge agent
      column runs (15.6); document the dual role in the header.
- [ ] **No `gh` in tests.** Port OLD's `tests/cli/test_check_scripts.py` shape: assert that running the
      script with NO `KANBAN_REPO` exits non-zero (the `:?` guard fires) and with NO `KANBAN_BRANCH`/`PR`
      exits non-zero — using a stub `gh` on `PATH` (a `tmp_path` shim that echoes fixture JSON) so the
      script's exit-code contract is exercised WITHOUT a network round-trip. Do NOT call the real `gh`.
      (CLAUDE.md network-safety: never let a test hit the GitHub API.)
- [ ] **Determinism note**: the scripts call `python3 -c "..."` to parse `gh` JSON (port OLD verbatim) —
      keep that, it is the PoC contract; the test's `gh` stub returns canned JSON so the parse path is
      deterministic.
- [ ] Verify: `make check` green; both scripts are executable (`test -x bin/check-pr-ready.sh`); the
      env-guard tests pass without `gh`.

```bash
git commit -m "test(genesis): re-sync check-pr-ready/check-merge-ready scripts + env-guard tests (port PoC gate scripts)"
```

---

### Phase 15 Gate

1. `rm -rf .mypy_cache` (mandatory — the incremental cache masks real errors), then `make lint` — zero
   errors (ruff + `mypy src tests`).
2. `make test` — all pass (check the summary line; any ERROR = collection crash, fix imports first).
3. `make check` — clean (lint + test + module-size guards; the new `app/script_route.py` /
   `adapters/scripts/runner.py` stay under the ~800 LOC soft cap).
4. Residual / parity greps (all `--type py` per CLAUDE.md search-safety):
   - `rg --type py "RETRY_LIMIT" src` → matches the reaper-retry constant in `app/tick.py` and the
     `release_slot`/fs-store retry-purge docstrings only (no stray).
   - `rg --type py "dispatch.jsonl|append_dispatch" src` → matches the fs adapter + the `StateStore` port
     - `LaunchAction` only.
   - `rg --type py "run_script|RunScriptAction|run_transition|ScriptRunner" src` → matches the new
     domain/decide/action/port/adapter set (no orphan reference).
   - `rg --type py "on_fail|advance:auto|_FIXCI|fixci" src` → matches `core/domain.py` (column fields) +
     `core/columns.py` (parse) + `app/script_route.py` (routing) only.
5. Parity check — exercised in tests:
   - **Reaper retry**: a stale agent is relaunched ONCE (dead session killed, `retries→1`, heartbeat
     refreshed, NOT moved to Blocked); the SECOND stale sweep parks it in Blocked; a raising relaunch
     parks it in Blocked.
   - **Audit log**: each launch (decided AND reaper-relaunch) appends one structured JSON line to
     `<root>/log/dispatch.jsonl` with the full PoC field set + `logged_at`; append-only; fail-soft.
   - **Script gates**: a SCRIPT column runs `run_transition_script` mechanically (no agent) with
     `KANBAN_REPO`+`KANBAN_BRANCH`; exit 0 → `advance:auto:<col>` triggering move + ✅ left-stage finalize;
     exit ≠0 → `on_fail:move:<col>` bounded by the fix-CI cap N=2 → park Blocked, or `rollback` →
     return-to-origin; a launch GATE vetoes the agent on a non-zero gate exit and routes its on_fail.
6. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 15 gate — reaper retry + dispatch audit log + mechanical script gates"
```
