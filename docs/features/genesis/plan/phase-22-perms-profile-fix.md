# Phase 22 — Permission-profile regression fix (restore the PoC's per-stage profiles)

**Trigger:** an adversarial review (helm prep, 2026-06-09) found, grounded against `src/`, that
genesis collapsed the PoC's 5 permission profiles (`docs/prepare/dev/check/merge`) to
`safe/trusted` in `adapters/perms.py`, but the shipped `DEFAULT_TRANSITIONS` still use
`docs/prepare/dev/check`. Since none of those are in `("safe","trusted")`, `allow_list` falls
back to `safe` for **every** launch → the `dev` agent (`/implement:phase`, fix-CI, pr-review)
cannot push/PR/`make`, and `trusted` is dead code. PoC-conformance regression + functional bug,
undetected because the live test never ran.

**Decision (operator-delegated):** restore the PoC's per-stage profiles (Option A) — maximal
PoC fidelity + least-privilege. Keep the two deliberate, endorsed genesis changes: the `merge`
profile stays **removed** (merge = human-only) and the universal deny-list (merge denied for ALL
profiles) stays. Source of truth: `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/engine/perms.py`.

## Sub-phase 22.1 — Restore the 4 PoC profiles (atomic; one green change)

This change is inherently atomic: changing `PROFILES`/`_PROFILE_ALLOW` without updating the
floor references + tests would leave `make check` red. Land it all together.

**Files (write):**

- `src/kanbanmate/adapters/perms.py` — the catalog + docstrings.
- `src/kanbanmate/app/actions.py` — the kill-switch floor (`DEFAULT_PROFILE`).
- `src/kanbanmate/core/decide.py` — docstring only (kill-switch "downgrade to safe" → "to docs").
- `src/kanbanmate/core/transitions.py` — `Transition.profile` docstring (safe/trusted → the 4).
- `docs/features/genesis/DESIGN.md` — §8 profile column, §10, H4/H5 reconciled to the 4 profiles.
- `tests/test_perms.py` — rewrite to the 4 profiles (port the PoC `tests/test_perms.py` assertions).
- Any other test under `tests/` that uses `"safe"`/`"trusted"` as a **profile value** (NOT the
  word "safe" in prose): reconcile to a real profile (`docs`/`prepare`/`dev`/`check`).

**Target state (perms.py) — port verbatim from the PoC, dropping `merge`:**

- `PROFILES = ("docs", "prepare", "dev", "check")`.
- `_PROFILE_ALLOW`:
  - `docs`: `Read, Edit, Bash(git add*), Bash(git commit*), Bash(git status*), Bash(git log*), Bash(git diff*), Bash(gh issue*), Bash(kanban-comment*), Bash(kanban-move*), Bash(kanban-progress*)` (no push, no PR).
  - `prepare`: `Read, Edit, Bash(git *), Bash(kanban-comment*), Bash(kanban-move*), Bash(kanban-progress*)` (full git incl. push for create-branch; no gh).
  - `dev`: `Read, Edit, Bash(git *), Bash(gh *), Bash(make *), Bash(kanban-comment*), Bash(kanban-move*), Bash(kanban-progress*), Bash` (push/PR/make/broad).
  - `check`: `Read, Bash(gh *), Bash(git *)` (read-only-ish; script gate profile).
- `allow_list` fallback → `_PROFILE_ALLOW["docs"]` (the MOST RESTRICTIVE floor — a deliberate,
  documented improvement over the PoC's `dev` fallback: degrade-safe on an unknown profile name,
  consistent with the genesis security stance). The shipped transitions name all 4, so the
  fallback is a safety net only.
- `_PINNED_MODE` = all four → `"auto"`; `_FALLBACK_MODE = "auto"` (unchanged headless-safe mode).
- Keep `deny_list()` universal (merge denied for ALL profiles — NO per-profile merge exception;
  the PoC's `_MERGE_DENY_ENTRIES` removal is NOT ported, since the `merge` profile is gone).
- `build_settings` / `materialise_settings` / heartbeat hook / non-root guard / `bypass` ban /
  `provision_worktree_skills` / `ensure_manual_merge_mode` — **unchanged**.
- Update the module docstring: "Four profiles (`docs/prepare/dev/check`) …" and the kill-switch
  line ("downgrades every profile to `docs`, the minimal floor"); note the `merge` profile is
  deliberately absent (merge = human-only).

**Floor reconciliation:**

- `app/actions.py` `DEFAULT_PROFILE = "safe"` → `"docs"` (+ the two nearby comments). If
  `DEFAULT_PROFILE` is now dead (phase 20 made profile transition-only + fail-loud), still
  reconcile the literal so no `safe` floor reference remains; note its status in the report.
- `core/decide.py` kill-switch docstring "downgrade all profiles to safe" → "to docs" (no logic
  change — under PAUSE no LaunchAction is produced).

**DESIGN reconciliation:** §8 `profile` column (`docs/prepare/dev/check/merge` → drop `merge`);
§10 (`safe` profile = … → the 4 profiles; floor = `docs`); H4/H5 (`safe`/`trusted` + kill-switch
"downgrade to safe" → the 4 profiles + "downgrade to `docs`"). Keep merge=human-only language.

**Acceptance:**

- `rm -rf .mypy_cache && make check` — green (ruff + mypy + tests + size guards).
- `allow_list("dev")` contains `Bash(git *)`, `Bash(gh *)`, `Bash(make *)`; `allow_list("docs")`
  contains NO `git push`/`gh pr`/`make` and NO merge entry.
- For EVERY profile in `PROFILES`, `deny_list()` still bans `gh pr merge` (merge human-only).
- `allow_list("unknown")` == `allow_list("docs")` (degrade-safe).
- No `"safe"`/`"trusted"` profile **value** remains anywhere in `src/` (prose "safe" OK).
- The shipped `DEFAULT_TRANSITIONS` profiles (`docs/prepare/dev/check`) now all resolve to a
  concrete, distinct allow-list (a test materialising each profile asserts the right scope).

### Phase gate

`rm -rf .mypy_cache && make check` green; diff scope confined to the files above + tests; PoC
fidelity verified against the PoC `perms.py`; `python -c "import kanbanmate"` smoke test.
