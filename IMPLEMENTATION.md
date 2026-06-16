# Implementation Progress — cockpit-unify-nudge (0.3.0 → 0.4.0)

> For Claude: read this file at session start. Current feature tracker.

**Feature**: cockpit-unify-nudge — two contained engine features promoted from the zero-deferrals
"out-of-scope future scope" list (items 2 + 3) into a single minor release.
**ITEM 2 (move-unification)**: route the agent `kanban-move` through the SAME intent queue the
operator uses, so there is ONE audited board-write path with uniform daemon-derived authority (the
agent helper stops calling `GithubClient.move_card` directly and becomes network-free).
**ITEM 3 (sleep-interrupt nudge)**: wake the daemon's inter-tick sleep immediately when an intent is
enqueued, via a cross-process `intents/.nudge` mtime sentinel polled by an interruptible slice-sleep —
without lowering the poll interval (no API-quota cost).
**Version bump**: minor (Y+1) — 0.3.0 → 0.4.0 (two new capabilities).
**Branch**: `feat/cockpit-unify-nudge`
**PR merge**: manual (human-only).
**Design**: `docs/features/cockpit-unify-nudge/DESIGN.md`
**Master plan**: single feature branch — sub-phases below.

Built in an isolated worktree + isolated venv (`/Users/izno/.pyenv/versions/3.12.4/bin/python`); the
live PM2 daemons (editable install from the MAIN worktree) were never touched.

## Phases

| Phase | Scope | Status | Commit |
|-------|-------|--------|--------|
| A | ITEM 2 move-unification: rewrite `bin/kanban_move.py:main()` → enqueue a `move` intent (`caller="agent"`, column KEY) + nudge + synchronous advance breadcrumb + default `--wait` (clears breadcrumb on `rejected`) / `--no-wait`; drop `GithubClient`/`load_token` (network-free); docstring deltas in `core/intent.py` + `app/intents.py` (agent-move is LIVE); tests rewritten (`tests/bin/test_kanban_move.py`) + agent-authority e2e added (`tests/app/test_intents.py`: own-issue executes, Merge deny, R1, security-heart caller-not-trusted, PAUSE held) | DONE | `feat(cockpit-unify-nudge): route agent kanban-move through the intent queue` |
| B | ITEM 3 sleep-interrupt nudge: `ports/store_intents.py` `nudge_daemon`/`nudge_mtime` stubs; `adapters/store/fs_intents.py` impl (atomic `.nudge` touch + fail-soft stat); `daemon/loop.py` `_interruptible_sleep` + `_make_nudge_reader` replacing the tail `sleep(delay)`; enqueue-side nudge wiring in `cli/move.py` + `bin/kanban_move.py`; tests (`tests/adapters/test_fs_intents.py`, `tests/daemon/test_loop.py`, `tests/cli/test_move.py`) | DONE | `feat(cockpit-unify-nudge): cross-process daemon sleep-interrupt nudge` |
| C | Version bump 0.3.0 → 0.4.0 across all 5 pins (VERSION, pyproject, `__init__`, marketplace.json, plugin.json) + manifest lockstep test; DESIGN + this tracker | DONE | `docs(cockpit-unify-nudge): DESIGN + IMPLEMENTATION + version bump 0.4.0` |

## Behaviour deltas (gate requirement)

- **Agent moves are now audited through the single write path.** `kanban-move` enqueues a `move`
  intent into `~/.kanban/intents/` instead of calling GitHub directly; the daemon is the SOLE board
  writer for agent moves, deriving agent-authority from its running-set bookkeeping (NEVER from the
  advisory `caller` field) and re-validating R1 / Merge-deny / wildcard-aware re-fire. The helper is
  now network-free (`GithubClient`/`load_token` imports dropped — a layering simplification).
- **Advance-breadcrumb semantic shift (documented).** The breadcrumb, still written synchronously by
  the helper before `claude` exits (load-bearing for the session-end ✅/⚠️ split race), now means
  "the agent REQUESTED its advance" rather than "the move LANDED". A daemon `rejected` result (under
  default `--wait`) CLEARS the breadcrumb so a refused move leaves no false ✅-signal.
- **Operator move unchanged** except for a single `nudge_daemon()` call after enqueue.
- **Daemon wakes near-instantly on enqueue.** A new `intents/.nudge` mtime sentinel (touched by every
  `enqueue_intent` via `nudge_daemon`) is polled by an interruptible 0.5 s slice-sleep, so an
  enqueued intent is drained within ~0.5 s instead of up to a full poll interval — with no interval
  reduction (no API cost). Fail-soft (a sentinel read failure degrades to the full-interval sleep) and
  cross-process (a `threading.Event` cannot bridge the separate enqueuer/daemon processes). Bonus:
  SIGTERM during the inter-tick sleep now exits within ≤0.5 s; the nudge also interrupts the geometric
  failure back-off sleep (an operator intent wakes a backed-off daemon within a slice). Convention:
  **every `enqueue_intent()` pairs with `nudge_daemon()`** (PR3 enqueuers follow).

## Phase gate

- `make check` → exit 0 (ruff + `ruff format --check` + mypy strict + 1778 pytest passed / 9 skipped /
  1 deselected + module-size guard pass; no module over the 1000-LOC hard ceiling — largest touched
  file `daemon/loop.py` at 689).
- `python -c "import kanbanmate"` → version `0.4.0`.
- Manifest lockstep test (`tests/test_plugin_manifest.py`) → 12 passed.
- Residual-import grep for `GithubClient`/`load_token` in `bin/kanban_move.py` → zero live refs (only
  docstring/comment mentions + a test asserting their absence).

## Deferred

- **Nothing in this feature's scope deferred.** Both items shipped fully tested and fail-soft.
- (Pre-existing, unchanged) Post-merge cutover / engine PoC-conformance remains a separate effort.
