# Phase 9 — Permission mode `auto` (headless-safe default)

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §10 (permission profiles; merge is human-only), H4 (settings materialised with
> a pinned `defaultMode`), §8.3 (the PostToolUse heartbeat hook lives in the same settings file).
> PoC source of truth (ABSOLUTE OLD root):
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/engine/perms.py`
> (`_DEFAULT_MODE = "auto"`).

**Goal**: change NEW's pinned permission `defaultMode` from `acceptEdits` to **`auto`** — the
headless-safe mode the PoC settled on (the unattended-hang reason). Keep every safety invariant:
`bypassPermissions` banned everywhere, the universal deny-list intact, the PostToolUse heartbeat
hook intact, the non-root materialisation guard intact. Verify `auto` is what actually lands in
every worktree's `.claude/settings.json`, and that an unattended agent cannot hang on a prompt
under it while deny still wins.

---

## Gate

Phase 8 complete; `make check` green; PR #1 open. Branch `feat/genesis`.

---

> **Why `auto`, not `acceptEdits` (the gap).** NEW's `src/kanbanmate/adapters/perms.py` pins
> `_PINNED_MODE = {"safe": "acceptEdits", "trusted": "acceptEdits"}` and `_FALLBACK_MODE =
"acceptEdits"`. Its own docstring claims `acceptEdits` "keeps the agent headless-safe (it never
> hangs on an edit prompt)" — but the PoC found `acceptEdits` does NOT cover the full unattended
> surface: it auto-accepts file edits yet still prompts on other permission decisions the
> orchestrated workflow hits, so an UNATTENDED agent can hang. The PoC's `_DEFAULT_MODE = "auto"`
> is the headless-safe mode (auto-approves the orchestrated surface while STILL enforcing
> `permissions.deny`). `bypassPermissions` is NOT the answer (it skips the deny layer — banned,
> §10). This phase flips NEW to `auto` to match the PoC's hardened default.

---

### 9.1 — Flip the pinned mode to `auto` (both profiles + fallback)

**Files**: `src/kanbanmate/adapters/perms.py`, `tests/test_perms.py` (extend).

- [ ] `_PINNED_MODE`: `{"safe": "auto", "trusted": "auto"}`. `_FALLBACK_MODE = "auto"`.
- [ ] Update the module docstring + the `_PINNED_MODE` block comment: replace the `acceptEdits`
      rationale with the `auto` one — _"`auto` keeps the agent headless-safe (it never hangs on a
      permission prompt for the orchestrated surface) while STILL honouring the concrete
      `permissions.deny` below. `acceptEdits` only auto-accepts edits and can still hang an
      unattended agent on other prompts (the PoC's unattended-hang reason). `bypassPermissions` is
      never a value here — it would skip the deny layer (banned, §10)."_ Keep the bug #39057
      pinning rationale.
- [ ] `pinned_mode(profile)` is unchanged in shape (still reads `_PINNED_MODE` with the fallback);
      no signature change. The `build_settings`/`materialise_settings` flow is unchanged — only the
      pinned VALUE differs.
- [ ] `tests/test_perms.py`: the existing mode assertions go through the `pinned_mode(profile)`
      indirection (e.g. `perms["defaultMode"] == pinned_mode(profile)`), so there is **NO literal
      `"acceptEdits"` string to "update" today** (audit fix — `rg --type py acceptEdits tests` is
      currently empty); flipping the constant makes those pass against `auto` automatically. So ADD
      explicit literal-`"auto"` assertions: `pinned_mode("safe") == "auto"`, `pinned_mode("trusted")
  == "auto"`, `pinned_mode("unknown") == "auto"` (fallback), and
      `build_settings(p)["permissions"]["defaultMode"] == "auto"` for both profiles. Add an explicit
      regression assertion: NO profile, NO fallback, EVER yields `"acceptEdits"` (`pinned_mode` over
      `PROFILES + ("bogus",)` is always `"auto"`). These negative assertions are what make the
      phase-9-gate src-only `acceptEdits` grep meaningful (they legitimately name the banned value in
      `tests/`).
- [ ] Verify: `make test` pass; `make lint` zero errors.

```bash
git commit -m "feat(genesis): pin permission defaultMode to auto (headless-safe; acceptEdits can hang unattended)"
```

---

### 9.2 — Verify `auto` is what lands in every worktree settings file

**The gap.** Pinning the constant is necessary but not sufficient — the design invariant (DESIGN
§10 H4) is that the mode is written EXPLICITLY into each worktree's `.claude/settings.json`. Add a
test that exercises the real write path (`materialise_settings`) and asserts the on-disk file.

**Files**: `tests/test_perms.py` (extend; uses `tmp_path` so no real worktree is touched),
`tests/app/test_actions.py` (the `LaunchAction` materialise call — assert the mode it writes).

- [ ] `materialise_settings` round-trip test: write to a `tmp_path` worktree for `safe` and
      `trusted` (with and without `issue=`), read the file back, assert
      `settings["permissions"]["defaultMode"] == "auto"`, `bypassPermissions is False`, the deny-list
      is present and non-empty, and (with `issue=`) the `hooks.PostToolUse[0].hooks[0].command`
      still ends with `kanban-heartbeat <issue>` (the heartbeat hook is unaffected by the mode flip).
- [ ] `LaunchAction` test: assert that the settings written by `materialise_settings(deps.profile,
  worktree, issue=issue)` during launch carry `defaultMode == "auto"` (drive it through the
      action with a `tmp_path` worktree, or assert the call args). This proves `auto` is the mode an
      UNATTENDED launched agent boots under.
- [ ] Verify: `make test` pass.

```bash
git commit -m "test(genesis): verify auto defaultMode lands in every materialised worktree settings file"
```

---

### 9.3 — Prove deny still wins + no-hang under `auto`

**The gap.** Flipping to a more permissive default mode must NOT weaken the merge/force-push/history
ban. Add explicit tests that the deny-list is byte-identical under `auto` and that the settings
carry NO interactive-prompt-requiring mode (the no-hang invariant, expressed at the settings level
— a real Claude session is out of scope for a unit test).

**Files**: `tests/test_perms.py` (extend).

- [ ] **Deny-holds-under-auto** test: for each profile, `build_settings(p)["permissions"]["deny"]
  == deny_list()` and the deny-list still contains every merge path (`gh pr merge*`,
      `*pr-merge*`, `gh api*merge*`, `*mergePullRequest*`), every force-push form, branch/ref
      deletion, and history rewrite — i.e. the mode flip stripped NOTHING. (Deny wins over allow
      regardless of `defaultMode`; this locks it in.)
- [ ] **No-hang invariant** test: assert `defaultMode == "auto"` and `defaultMode != "acceptEdits"`
      and `"bypass" not in defaultMode.lower()` for every profile — i.e. the settings pin the one
      mode that is BOTH unattended-safe AND deny-enforcing. Document that the _runtime_ no-hang is
      validated end-to-end in the phase-11 e2e (`claude` launched headless against a real card),
      not in this unit (no real agent runs here).
- [ ] **Bypass-still-banned** regression: `build_settings("bypassXYZ")` raises `ValueError`;
      `materialise_settings` under a faked root uid 0 raises `PermissionError` (the existing guards
      are unaffected by the mode flip — assert they still hold).
- [ ] Verify: `make check` green.

```bash
git commit -m "test(genesis): deny-list and bypass ban still hold under auto defaultMode"
```

---

### Phase 9 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`).
2. `make test` — all pass.
3. `make check` — clean.
4. Residual grep — PRODUCTION ONLY: `rg --type py "acceptEdits" src` → zero matches (the production
   mode is fully flipped). The grep is scoped to `src` ON PURPOSE: §9.1 and §9.3 add negative-assertion
   tests that NAME the banned value `"acceptEdits"` (e.g. `defaultMode != "acceptEdits"`, "NO fallback
   EVER yields `acceptEdits`"), so `tests/` legitimately contains the string. Test files MAY name the
   banned value in negative assertions; production code (`src/`) must not contain it at all. Do NOT
   widen this grep to `src tests` — that would make the gate unsatisfiable against the very regression
   tests this phase adds. (Keep the §9.1/§9.3 negative tests.) **Positive check (audit fix):**
   `rg --type py "acceptEdits" tests` → **≥1 match** — the negative-assertion regression tests MUST
   exist; zero matches means §9.1/§9.3's tests were dropped, so FAIL the gate.
5. `build_settings` for both profiles writes `defaultMode == "auto"`, `bypassPermissions == false`,
   and the full deny-list (proven by test).
6. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 9 gate — permission mode auto (headless-safe default)"
```
