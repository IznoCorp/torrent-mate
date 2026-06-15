# Phase 5 — Features + Cutover

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §8.1 (sticky comments), §8.2 (Cancel column), §8.3 (heartbeat #67), §11 (cutover).

**Goal**: Wire sticky comments, Cancel column teardown+resume, and agent liveness heartbeat to the
column-class/action model. Write user-facing docs. Decommission the old PoC location.

---

## Gate

Phase 4 complete: H6 fixtures + H7 integration CI committed, `make check` green.
Pre-cutover: confirm no active agent sessions running against the PoC location.

---

### 5.1 — Sticky comments per step (`kanban-comment --sticky`)

**Files**: `src/kanbanmate/bin/kanban_comment.py`, `bin/kanban-comment` (shim),
`tests/bin/__init__.py`, `tests/bin/test_kanban_comment.py`.

- [ ] Port from PoC `bin/kanban-comment` + `engine/stage_comment.py`. Logic:
      list issue comments via REST; find comment with HTML marker
      `<!-- kanban:step=<column-key> -->`; **edit** existing or **create** if absent.
      Append mode (`--append`) for free-form notes (no marker lookup).
- [ ] `bin/kanban-comment`: thin shim — `#!/usr/bin/env python3` invoking `kanban_comment.main()`.
      Listed in `pyproject.toml` `[project.scripts]` as `kanban-comment`.
- [ ] `test_kanban_comment.py`: mock REST adapter; assert edit called on existing marker;
      assert create called when absent; assert marker format correct; assert `--append` skips lookup.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): §8.1 sticky comments (kanban-comment --sticky, edit-in-place via HTML marker)"
```

---

### 5.2 — Cancel column teardown + resume (`ResetAction`)

**Files**: `src/kanbanmate/app/actions.py` (extend `TeardownAction` + `ResetAction`),
`tests/app/test_actions.py` (extend).

- [ ] `TeardownAction.execute()` for Cancel destination: kill tmux session; `worktree remove`
      (no `--force`); release slot; drop in-flight guard; clear/transition persisted state;
      post final sticky comment. Port from PoC `engine/teardown.py` + `cli/plan_cancel.py`.
- [ ] `ResetAction.execute()` for Cancel→Backlog transition: purge ticket to clean re-startable
      state (clear uuid/worktree path from state, keep issue metadata). Next agent-column move
      gets a fresh uuid + fresh worktree. Port from PoC equivalent.
- [ ] `columns.py` / `decide.py`: confirm Cancel column has `ColumnClass.REACTIVE`; confirm
      Cancel→Backlog transition resolves to `ActionKind.RESET` (already in decide, verify wired).
- [ ] Tests: mock deps; assert TeardownAction kills session + removes worktree + posts comment;
      assert ResetAction clears state without deleting issue; assert neither action relaunches agent.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): §8.2 Cancel column teardown + Cancel→Backlog resume (ResetAction)"
```

---

### 5.3 — Agent liveness heartbeat (`kanban-heartbeat` + reaper)

**Files**: `src/kanbanmate/bin/kanban_heartbeat.py`, `bin/kanban-heartbeat` (shim),
`src/kanbanmate/app/tick.py` (extend reap step),
`tests/bin/test_kanban_heartbeat.py`, `tests/app/test_tick.py` (extend).

- [ ] `kanban_heartbeat.py`: parse `argv[1]` to `int` **before** importing `kanbanmate` (cold-start
      guard per DESIGN §8.3); on bad/missing arg → exit 0 silently. Call
      `store.touch_heartbeat(issue, time.time())`; swallow all exceptions with bare `try/except`;
      **always exits 0** (exit 2 would block the agent — never emitted).
- [ ] `bin/kanban-heartbeat`: shim listed in `pyproject.toml` scripts as `kanban-heartbeat`.
- [ ] Reaper step in `tick.py`: for each `running` ticket whose `state.heartbeat` is older than
      `HEARTBEAT_TTL` (default 1800 s) → post sticky comment + move to Blocked + kill session +
      release slot. Port from PoC `engine/reaper.py`.
- [ ] `test_kanban_heartbeat.py`: bad arg → exits 0, no store call; good arg → `touch_heartbeat`
      called; exception in store → still exits 0.
- [ ] `test_tick.py` (extend): stale heartbeat → reaper moves ticket to Blocked; fresh heartbeat
      → no reap.
- [ ] Verify: `make test` pass. `make lint` zero errors.

```bash
git commit -m "feat(genesis): §8.3 agent liveness heartbeat (kanban-heartbeat shim + reaper in tick)"
```

---

### 5.4 — Remaining agent helper bins

**Files**: `bin/kanban-move`, `bin/kanban-progress`, `bin/kanban-session-end`,
`bin/kanban-update-main`, `bin/check-pr-ready.sh`, `bin/check-merge-ready.sh`,
`src/kanbanmate/bin/{kanban_move,kanban_progress,kanban_session_end,kanban_update_main}.py`.

- [x] Port each from PoC `bin/`. All urllib calls must set connect + read timeouts (inherited via
      the github client transport). `kanban-move` refuses agent-column targets (anti-loop guard —
      DESIGN §8): it resolves the target column's `ColumnClass` from the clone's `columns.yml` and
      refuses (exit 1, no `move_card`) when the target is AGENT.
- [x] List all in `pyproject.toml` `[project.scripts]` so `pip install` places them on PATH
      (kanban-move, kanban-progress, kanban-session-end, kanban-update-main). The `.sh` scripts
      (check-pr-ready, check-merge-ready) stay as repo `bin/` files referenced by path.
- [x] Tests: `test_kanban_move.py` — assert refuses agent target (no `move_card` call, exit 1);
      assert calls `BoardWriter.move_card` for inert/reactive target. Light tests added for
      progress / session-end / update-main too.
- [x] Verify: `make test` pass.

> **Plan-drift note**: the PoC `kanban-session-end` and `kanban-update-main` were bash scripts;
> here they are ported to **Python bins** (with thin `bin/` shims + `[project.scripts]` entries) to
> match the new engine pattern and stay testable. `kanban-session-end` calls the new store's
> `release_slot` (which removes the running state _and_ frees the cap slot — the new store folds
> "mark idle" + "release slot" into one idempotent op). `kanban-progress` gains an explicit
> `--stage <key>` (the new `TicketState` carries no column, unlike the PoC which read the stage
> from per-item state); without `--stage` it posts a free-form timestamped note.

```bash
git commit -m "feat(genesis): remaining agent helper bins (kanban-move, progress, session-end, update-main)"
```

---

### 5.5 — User-facing docs

**Files**: `README.md`, `docs/install.md`, `docs/how-it-works.md`, `docs/columns.md`, `ROADMAP.md`.

- [ ] `README.md`: what/why + 5-minute quickstart (`pip install kanbanmate`, `kanban install`,
      `kanban init --repo org/repo`, `kanban seed ROADMAP.md`).
- [ ] `docs/install.md`: detailed 3-tier install walkthrough (DESIGN §4), PM2 supervision,
      `kanban doctor` output reference.
- [ ] `docs/how-it-works.md`: polling loop diagram (DESIGN §3.1 ASCII art), column classes,
      action model, heartbeat, kill-switch.
- [ ] `docs/columns.md`: `columns.yml` reference — all fields, default template walkthrough.
- [ ] `ROADMAP.md`: deferred items from DESIGN §13 (webhook adapter, GitHub App, MCP helpers).
- [ ] Verify: no broken internal links. `make check` still green (docs not scanned by lint).

```bash
git add -f README.md docs/ ROADMAP.md
git commit -m "docs(genesis): user-facing docs (README, install, how-it-works, columns, roadmap)"
```

---

### 5.6 — Cutover + decommission (DESIGN §11)

**Files**: changes in `PersonnalScaper/.claude/` repo (separate git operation) +
`src/kanbanmate/cli/install.py` (extend uninstall to remove launchd plist).

- [ ] `kanban uninstall`: add step to remove old launchd reaper plist
      `xyz.iznogoudatall.kanban-reaper` if present (`launchctl unload` + `rm`). Idempotent.
- [ ] In `PersonnalScaper` repo (separate commit, not part of KanbanMate history):
      remove `skills/kanban/` directory; clean `.claude/CLAUDE.md` refs to the old skill;
      commit: `chore: decommission kanban skill (extracted to KanbanMate)`.
- [ ] Verify KanbanMate `make check` still green after uninstall logic added.
- [ ] Verify `kanban doctor` reports clean after cutover.

```bash
git commit -m "feat(genesis): cutover — remove old launchd reaper plist from kanban uninstall"
```

---

### 5.7 — Gate hardening (mypy strict on tests)

**The gap.** `CLAUDE.md` mandates mypy-strict over the codebase and "harden the PoC" is this
feature's headline goal, but the `Makefile` `lint` target only ran `mypy src`. The test suite was
never type-checked by the gate, so it had quietly accumulated **14 mypy-strict errors across 6
files** that `make lint` / `make check` never surfaced. (The `lint` target's own header comment
already claimed "mypy (strict) on src **and tests**" — the recipe had drifted from its contract.)

**The 14 errors fixed (by file).**

- `tests/test_perms.py` (6): `_read_settings` returned `Any` from `json.loads` while declared
  `-> dict[str, object]` (`no-any-return`), and five chained subscripts
  (`settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]`) indexed/`in`-tested values typed
  `object` (`index` / `operator`). Fixed with an `isinstance` narrowing in `_read_settings` plus two
  typed accessor helpers — `_post_tool_use_entries` and `_first_heartbeat_hook` — that drill the
  nested structure with per-level assertions and return typed dicts. Assertion strength preserved
  (the `command`-is-`str` checks already existed elsewhere in the file).
- `tests/core/test_domain.py` (4): four per-pair `ActionKind.X is not ActionKind.Y` assertions on
  distinct enum literals (`comparison-overlap` — mypy knows they can never be identical).
  Restructured to a single set-distinctness assertion
  (`len({LAUNCH, TEARDOWN, RESET, BLOCK, NOOP}) == 5`), which proves mutual distinctness without
  per-pair identity checks. The "exactly five members" iteration assertion is retained.
- `tests/test_plugin_manifest.py` (1): `import yaml  # type: ignore[import-untyped]` was an
  `unused-ignore` — `types-PyYAML` is installed, so the import is typed. Removed the stale comment.
- `tests/bin/test_kanban_update_main.py` (1): `monkeypatch.setattr(kanban_update_main.subprocess,
…)` reached through the module's re-exported `subprocess` (`attr-defined` — not explicitly
  exported). Switched to the string-target form
  `monkeypatch.setattr("kanbanmate.bin.kanban_update_main.subprocess.run", …)`.
- `tests/bin/test_kanban_progress.py` (1): same `attr-defined` on `kanban_progress.time`. Switched
  to the string-target form `"kanbanmate.bin.kanban_progress.time.time"`.
- `tests/adapters/test_workspace.py` (1): `_completed_process` was annotated with the bare generic
  `subprocess.CompletedProcess` (`type-arg`). Parameterised to `CompletedProcess[str]` (the fixture
  passes `str` stdout/stderr).

No `# type: ignore` blanket suppressions were added; no test behaviour or assertion strength was
weakened (types only). No `src/` change was needed — every error was test-side.

**The Makefile change.** Flipped the `lint` recipe `mypy src` → `mypy src tests`, so `make lint`
and `make check` now type-check the whole codebase and lock in the hardening going forward.

**Verification.** `python -m mypy tests/` → 0 errors; `python -m mypy src tests` → 0 errors;
`make lint` → clean; `make check` → clean (366 passed, 7 skipped, 1 deselected — counts unchanged);
`python -c "import kanbanmate"` → exit 0.

---

### Phase 5 Gate — Final gate before feature-pr

1. `make lint` — zero errors
2. `make test` — all pass
3. `make check` — clean
4. `rg --type py "NotImplementedError" src/kanbanmate/cli/` — zero matches (all stubs filled)
5. `python -c "import kanbanmate"` — exits 0
6. `kanban --help` — lists all commands (install, uninstall, doctor, init, seed, status,
   sessions, cancel, logs, reset, poll, run)
7. `claude plugin validate . --strict` (marketplace) AND
   `claude plugin validate ./plugin --strict` (plugin) — both exit 0

```bash
git commit --allow-empty -m "chore(genesis): phase 5 gate — features + cutover complete"
```
