# Phase 20 — Transitions-only engine (remove the column-class model; `from`/`to` list syntax)

> Re-architecture decided 2026-06-09 (supersedes the phase-12.6 HYBRID). DESIGN §8.0.1/§8.0.2/§8.0.6/§9
> rewritten. The agent launches **at the transition**, never at a column. `transitions.yml` is the SOLE
> trigger model; `columns.yml` carries NO launch config. `from`/`to` accept single | list | `*`.
> Each sub-phase = ONE commit `<type>(genesis): <description>`. **Clear `.mypy_cache` before every gate.**
> PoC source of truth: `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/` (`transitions.py`,
> `cli/transitions_yaml.py`: columns are a bare name list, ALL launch config on the transitions).

**Ordering is INCREMENTAL-GREEN** (each sub-phase passes `make check` on its own): first ADD the
DEFAULT_TRANSITIONS fallback (additive), then STOP READING the column launch fields (decide, actions —
the fields still exist, unread), and ONLY THEN REMOVE the now-dead fields + fix the test fan-out. Never
remove a field while a reader still references it.

**Invariant for the whole phase:** strict PoC fidelity — a whitelisted prompt-transition that passes the
BLOCK guards LAUNCHes unconditionally (no per-column gate, no dormant stage).

---

## 20.1 — `core/transitions.py`: `from`/`to` list expansion (cartesian) + duplicate rejection

**Additive — green on its own (the existing single/wildcard model is unchanged).**
**Files**: `src/kanbanmate/core/transitions.py`, `tests/core/test_transitions.py`.

- [ ] In `load_transitions`, before building the lookup tables, NORMALISE each raw entry: `from`/`to` may be a
      `str`, a `list[str]`, or `"*"`. A list expands to the **cartesian product** of `(from × to)` concrete
      edges, each becoming an ordinary explicit `Transition` (action fields copied). Validate: a list is a
      non-empty list of non-empty `str`; `"*"` may NOT appear inside a list; `"*" → "*"` still rejected.
- [ ] **Duplicate-pair rejection**: expansion (or two explicit rows) producing the SAME `(from_col, to_col)`
      → `ValueError` (no silent last-wins). Precedence UNCHANGED (`get()` untouched: explicit > wild_from >
      wild_to); list expansion only feeds the `_explicit` table.
- [ ] Tests: `[a,b,c] → d` ⇒ 3 edges same action; `[a,b] → [c,d]` ⇒ 4 edges; list member wins over `(*, d)`;
      duplicate `(a,d)` → ValueError; `"*"` inside a list → ValueError; single + bare `"*"` unchanged.
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "feat(genesis): transitions.yml from/to accept lists (cartesian expansion) + duplicate-pair rejection"
```

---

## 20.2 — `app/wiring.py` + `daemon/loop.py`: no-`transitions.yml` → `DEFAULT_TRANSITIONS` fallback

**Additive — green (the column-class path still exists; this only ensures a whitelist is ALWAYS supplied).**
**Files**: `src/kanbanmate/app/wiring.py`, `src/kanbanmate/daemon/loop.py`,
`src/kanbanmate/core/transitions_defaults.py` (a `default_transition_config()` / render helper if useful),
tests (`tests/app/test_wiring*`, `tests/daemon/test_loop.py`).

- [ ] When the config resolution finds no `transitions.yml`, build the `TransitionConfig` from
      `DEFAULT_TRANSITIONS` (render via `transitions_defaults` → `load_transitions`) instead of leaving
      `transitions=None`. The daemon NEVER ticks without a whitelist. Keep the explicit-`transitions.yml` path.
- [ ] Tests: a wiring/config with no transitions.yml yields a `TransitionConfig` equal to the DEFAULT flow
      (assert a known edge, e.g. `Backlog→Spec` has the brainstorm prompt); the explicit path still wins.
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "feat(genesis): no transitions.yml falls back to DEFAULT_TRANSITIONS (a whitelist is always supplied)"
```

---

## 20.3 — `core/decide.py`: transitions-only LAUNCH (stop reading the column-class gate)

**Green — the `Column` launch fields still EXIST (unread by decide after this); they are removed in 20.5.**
**Files**: `src/kanbanmate/core/decide.py`, `tests/core/test_decide.py`.

- [ ] Remove the agent-class launch gate: a prompt-bearing whitelisted transition that passes the BLOCK guards
      returns `LAUNCH` **unconditionally** — delete the `triggers_agent`/`_launch_is_blocked` destination-class
      check + the "inert destination → NOOP-instead-of-LAUNCH" branch. Reactive→TEARDOWN (precedence 1) +
      Cancel→Backlog→RESET stay. The anti-loop / dependency-gate BLOCK guards stay. **Drop the
      `interactive_only` gate** (it was the column autonomy switch; PoC parity = every stage launches). Keep
      `unattended_hours` ONLY if it is a genuine PoC feature — verify against the PoC; if not, note for removal
      (do NOT remove the field in this sub-phase if other code reads it — note it).
- [ ] Remove the `ctx.transitions is None` legacy column-class path: after 20.2 a whitelist is always supplied,
      so make `transitions is None` a hard error (or assert non-None) — it must NEVER silently use a column
      model. Update/remove the `test_decide` cases that drove the `transitions=None` legacy path.
- [ ] Update the module docstring (transitions-only; delete the hybrid/legacy prose).
- [ ] Tests: a prompt-transition into a (formerly-inert) column now LAUNCHes (invert the old "dormant" test);
      reactive Cancel still TEARDOWN; un-whitelisted → ROLLBACK; the column-class path is gone.
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "feat(genesis): decide is transitions-only — prompt-transition always launches, no column-class gate or None-fallback"
```

---

## 20.4 — `app/actions.py`: profile resolves from the transition only

**Green — drops the column-default tier; the `Column.permission_profile` field still exists (removed in 20.5).**
**Files**: `src/kanbanmate/app/actions.py`, `tests/app/test_actions.py`, `tests/test_perms.py` (if it
exercises the two-tier resolution).

- [ ] `_resolve_profile`: profile = the matched **transition's** `profile` ONLY. Drop the column-default tier
      (`self.column_permission_profile` / the `deps`-side column default). Fail loud when the transition leaves
      `profile` empty (no silent global default — unchanged contract). Drop the `column_permission_profile`
      field/plumbing from `LaunchAction` + the queue payload (it was the two-tier column default; it becomes
      dead now and is removed here since it lives in actions, not the Column model).
- [ ] Tests: a launch resolves its profile from the transition; an empty transition profile fails loud; the
      queue/drain payload no longer carries `column_permission_profile`.
- [ ] Verify: `rm -rf .mypy_cache && make check` green.

```bash
git commit -m "feat(genesis): launch profile resolves from the transition only (drop the column-default tier)"
```

---

## 20.5 — re-home the `kanban-move` anti-loop guard (`ColumnClass.AGENT` → launch-transition target)

**Why (gap found by the 20.5-blocked agent).** `bin/kanban_move.py` refuses an agent's outbound move into
a `ColumnClass.AGENT` column (anti-loop: the agent must not re-trigger its own stage). In the transitions-only
model there IS no AGENT column — but the anti-loop concern REMAINS (a move into a launch-target column re-fires
that transition). DESIGN §8.0.5 ALREADY specifies the correct model: _the refusal is keyed on the transition
whitelist (a launch target), NOT on a static column class._ This sub-phase re-homes the guard accordingly,
which also removes `kanban_move.py`'s `ColumnClass.AGENT` dependency (the prerequisite for 20.6's enum removal).
GREEN: `ColumnClass.AGENT` still EXISTS after this (kanban_move just stops reading it); it is deleted in 20.6.

**Files**: `src/kanbanmate/bin/kanban_move.py`, `tests/bin/test_kanban_move.py`.

- [ ] Add `_load_clone_transitions(entry)` mirroring `_load_clone_columns`: read `<clone>/.claude/kanban/
    transitions.yml` via `load_transitions` when present, else `default_transition_config()` (the same
      DEFAULT_TRANSITIONS fallback the daemon uses, 20.2). Compute the **launch-target column set** =
      `{ t.to_col for t in <whitelist prompt-bearing transitions> }` (the destinations of every transition
      that has a `prompt`; include the `from='*'` wild_to prompt entries' `to_col`). Expose it from the
      `TransitionConfig` (a small `launch_target_columns()` accessor on `TransitionConfig`, OR compute in
      kanban_move from the parsed entries — prefer a `TransitionConfig` accessor so it is tested in core).
- [ ] Replace the guard `if column.column_class is ColumnClass.AGENT:` with `if target_column in
    launch_targets:` — refuse the move (exit 1, same stderr shape, BEFORE any GitHub call) when the
      destination is a launch-transition target. Update the docstring (DESIGN §8.0.5: keyed on the whitelist,
      not a column class). Resolve `target` to its column key/name consistently (reuse `resolve_target_column`
      for name→key, then test membership by the column the transitions use — keys).
- [ ] `kanban_move.py` no longer imports/reads `ColumnClass` (verify). It still loads `columns` only if needed
      for name→key resolution; otherwise it can resolve the target against the launch-target key set directly.
- [ ] Tests (test*kanban_move.py): a move into a launch-target column (e.g. `InProgress`/`PRCI`/`Review` — a
      prompt-transition `to`) is REFUSED (exit 1, no move_card, no breadcrumb); a move into an inert/terminal
      column (e.g. `Backlog`, `Done`, `Ready to dev`) is ALLOWED; a move into the INERT `Merge` is ALLOWED
      (merge stays human + Review→Merge is a SCRIPT gate, not a prompt — so Merge is NOT a launch target).
      Re-specify the old `test_refuses_agent_column_target*\*` tests to the launch-target contract (do NOT
      vacuously weaken).
- [ ] Verify: `rm -rf .mypy_cache && make check` green. (`ColumnClass.AGENT` still exists; removed in 20.6.)

```bash
git commit -m "feat(genesis): kanban-move anti-loop guard keys on launch-transition targets, not ColumnClass.AGENT (DESIGN §8.0.5)"
```

---

## 20.6 — remove the now-dead column launch fields + the bare `columns.yml.tmpl`

**Green — nothing reads these fields anymore (20.3/20.4 stopped). This deletes them + fixes the test fan-out.**
**Files**: `src/kanbanmate/core/domain.py` (`Column`, `ColumnClass`), `src/kanbanmate/core/columns.py`
(`load_columns`, remove `column_profile_for_stage`), `src/kanbanmate/assets/columns.yml.tmpl`,
`tests/core/test_domain.py`, `tests/core/test_columns.py`, + any test constructing `Column(...)` with the
removed fields (fan-out — mypy/pytest will surface them).

- [ ] `Column` (domain.py): remove `triggers_agent`, `interactive_only`, `permission_profile`. Keep `key`,
      `name`, `column_class`. `ColumnClass`: remove `AGENT` (no column is an agent column now); keep `REACTIVE`
      (teardown) + `INERT`.
- [ ] `load_columns` (columns.py): parse only `key`, `name`, `action: teardown` (→ REACTIVE; else INERT). Keep
      `BoardDefaults`. **Remove `column_profile_for_stage`** (17.5) — residual-grep ZERO in src + tests.
- [ ] `columns.yml.tmpl`: the 12 columns as a bare set (`key` + `name`), `Cancel` with `action: teardown`, a
      header noting columns carry NO launch config (it lives in `transitions.yml`). Remove every
      `triggers_agent` / `permission_profile` / `interactive_only` / `prompt`.
- [ ] Fix the test fan-out: every `Column(...)` / columns.yml fixture that set the removed fields. Add a test
      asserting the tmpl has NO launch fields + the 12-column set.
- [ ] Verify: `rm -rf .mypy_cache && make check` green. Residual greps: `rg --type py
  "triggers_agent|interactive_only|column_profile_for_stage|ColumnClass.AGENT|column_permission_profile"
  src tests` → ZERO; `rg -g '*.tmpl' "triggers_agent|permission_profile|prompt:" src` → ZERO.

```bash
git commit -m "refactor(genesis): remove the dead column launch fields + AGENT class; columns.yml.tmpl ships a bare set"
```

---

### Phase 20 Gate

1. `rm -rf .mypy_cache && make lint` — zero. 2. `make test` all pass; `make check` clean (module-size; layering).
2. Residual greps (as 20.5) → ZERO. `from`/`to` list-expansion + DEFAULT_TRANSITIONS fallback exercised.
3. Parity: a prompt-transition into any column launches; no transitions.yml → DEFAULT_TRANSITIONS; `[a,b]→c`
   expands to 2 edges; columns.yml is a bare set; profile from the transition.
4. `python -c "import kanbanmate"` exits 0.
5. **Adversarial verification (ultracode)** on 20.3 (transitions-only decide — keystone) + 20.4 (profile) +
   20.1 (list expansion correctness) before the milestone.

```bash
git commit --allow-empty -m "chore(genesis): phase 20 gate — transitions-only engine (remove column-class model; from/to list syntax)"
```
