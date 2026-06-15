# Phase 3 — Hardening H3–H5

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §6 (hardening table), §8.3 (heartbeat), §10 (security).

**Goal**: H3 GraphQL pagination · H4 permission profiles materialised into worktree
`.claude/settings.json` + PostToolUse heartbeat hook · H5 kill-switch `~/.kanban/PAUSE`.

---

## Gate

Phase 2 complete: all CLI commands functional, plugin marketplace validated,
`make check` green.

---

### 3.1 — H3: GraphQL cursor pagination

**Files**: `src/kanbanmate/adapters/github/client.py` (extend),
`src/kanbanmate/adapters/github/_queries.py` (extend),
`tests/adapters/github/test_pagination.py`.

- [ ] Replace the Phase 1 page-1 stub with full cursor-follow pagination on `projectItems`.
      Pattern: loop `while pageInfo.hasNextPage: fetch(after: endCursor)`, accumulate items,
      return complete `BoardSnapshot`. Connect + read timeouts remain mandatory on every request.
- [ ] `test_pagination.py`: inject fake transport with a two-page fixture sequence (page 1 returns
      `hasNextPage: true, endCursor: "cur1"`; page 2 returns `hasNextPage: false`). Assert all items
      from both pages appear in the returned `BoardSnapshot`. Use fixtures from PoC
      `tests/github/fixtures/resolve_item_page1.json` + `resolve_item_page2.json` as reference shapes.
- [ ] Verify: `make test` pass. `make lint` zero errors.

```bash
git commit -m "fix(genesis): H3 GraphQL cursor pagination (board with >100 items no longer truncates)"
```

---

### 3.2 — H4: permission profiles materialised into worktree `.claude/settings.json`

**Files**: `src/kanbanmate/engine/perms.py` (new, under `adapters/` or `app/`),
`tests/test_perms.py`.

- [ ] Port from PoC `engine/perms.py`. `materialise_settings(issue, profile, worktree_path, store)`
      writes `.claude/settings.json` into the worktree with:
  - `defaultMode` pinned to profile value (mitigates mid-session reset #39057).
  - `safe`: concrete `permissions.allow` list; bans `gh pr merge`, `git push --force`,
    history rewrite across all profiles (DESIGN §10).
  - `trusted`: expanded allow list; same bans.
  - `bypassPermissions: false` (refuses under root).
- [ ] `LaunchAction.execute()` calls `materialise_settings` before launching the tmux session —
      update `src/kanbanmate/app/actions.py`.
- [ ] `test_perms.py`: `tmp_path` worktree; assert `settings.json` written; assert `defaultMode`
      pinned; assert banned commands absent from allow list for both profiles.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): H4 permission profiles materialised into worktree .claude/settings.json"
```

---

### 3.3 — H4 cont.: PostToolUse heartbeat hook in worktree settings

**Files**: `src/kanbanmate/engine/perms.py` (extend), `tests/test_perms.py` (extend).

- [ ] `materialise_settings` also injects a `PostToolUse` hook entry into `.claude/settings.json`
      with matcher `"*"` and command string `kanban-heartbeat <issue>` (command-string form, **not**
      exec-form array — per DESIGN §8.3 and PoC `bin/kanban-heartbeat`).
- [ ] The issue number is baked in by the dispatcher at launch time.
- [ ] `test_perms.py`: assert `hooks.PostToolUse` entry present; assert command is a string
      containing `kanban-heartbeat`; assert matcher is `"*"`.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): H4 PostToolUse heartbeat hook baked into worktree settings"
```

---

### 3.4 — H5: kill-switch `~/.kanban/PAUSE` + unattended-hours window

> **Plan-drift correction (applied during execution of 3.4):**
>
> - The decide context dataclass is named **`DecideContext`** (not `DecideCtx`).
> - `kill_switch: bool` and the `kill_switch → BLOCK` precedence over LAUNCH were
>   **already added in sub-phase 1.6** — 3.4 does NOT re-add them.
> - 3.4's actual delta is: `kill_switch_active()` on the store (+ the `StateStore`
>   Protocol), `unattended_hours` on `DecideContext` + the window check in `decide()`,
>   and the tick wiring that reads the live PAUSE sentinel each cycle.
> - The "downgrade all profiles to safe" intent is realised operatively: under PAUSE
>   `decide()` yields no `LaunchAction`, so nothing runs at an elevated profile (the
>   daemon separately forces the safe profile). The tested behaviour is **PAUSE ⇒ no LaunchAction**.

**Files**: `src/kanbanmate/core/decide.py` (extend `DecideContext`),
`src/kanbanmate/adapters/store/fs_store.py` (extend),
`src/kanbanmate/ports/store.py` (declare `kill_switch_active` on the Protocol),
`src/kanbanmate/app/tick.py` (wire the live PAUSE read),
`tests/core/test_decide.py` (extend), `tests/test_killswitch.py`.

- [x] `fs_store.py`: add `kill_switch_active() → bool` — returns `True` when `<root>/PAUSE`
      exists. Pure read, no side effects, no exceptions on absence. Declared on the `StateStore`
      Protocol too so the tick reads it through the port.
- [x] `DecideContext` (in `core/decide.py`): `kill_switch: bool` already present (1.6); add
      `unattended_hours: tuple[int,int] | None`. `decide()`: when `kill_switch` is True → BLOCK any
      LAUNCH (already present, 1.6). When outside the `unattended_hours` window → BLOCK the LAUNCH
      (human not present for interactive-only columns). Hour derived purely from `ctx.now` via
      `datetime.fromtimestamp` (no clock read — core stays pure). Wrap-around windows supported.
- [x] `tick.py`: populate `ctx.kill_switch` from `store.kill_switch_active()` each tick (OR-ed with
      the static `TickConfig.kill_switch`), and `unattended_hours` from `TickConfig`. A PAUSE file
      appearing between ticks stops launches on the next tick.
- [x] `test_killswitch.py`: create `PAUSE` file in a `tmp_path` store root; run tick; assert no
      LaunchAction executed. Remove file; assert LaunchAction resumes.
- [x] Verify: `make test` pass. `make lint` zero errors.

```bash
git commit -m "feat(genesis): H5 kill-switch (PAUSE file + unattended-hours blocks launches)"
```

---

### Phase 3 Gate

1. `make lint` — zero errors
2. `make test` — all pass
3. `make check` — clean
4. `rg --type py "H3\|H4\|H5" src/` — confirm no TODO stubs remain
5. `python -c "import kanbanmate"` — exits 0

```bash
git commit --allow-empty -m "chore(genesis): phase 3 gate — hardening H3–H5"
```
