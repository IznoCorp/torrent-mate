# Phase 28 — Teardown on Done (e2e-driven)

**Trigger (live e2e #91):** the operator skip-to-Done'd #91 (`Plan→Done`) while its agent was
running. The daemon purged the state (slot released) but did NOT tear the agent down: the tmux
session `ticket-91` and the worktree stayed alive (orphans), and the sticky stayed
`⏳ Spec — waiting for your input` (never finalized). Since the skip-to-Done's primary use case is
"an agent recognises the feature is already shipped and marks the ticket Done", **an agent is
usually RUNNING when a card lands in Done** — so Done must tear it down.

## Rule (operator-approved)

**Arrival in `Done` with a live agent (RUNNING or WAITING) → full teardown:** kill the tmux
session, remove the worktree (+ local branch per the existing teardown), finalize the sticky
(a ✅/done header — NOT the "cancelled… move the card to Backlog" cancel text), release the slot,
purge the state. The card STAYS in Done (no reset move). No agent → arrival in Done is a pure
no-op (replay-safe: zero errors, zero side effects).

## Sub-phase 28.1 — Implement + replay-safe teardown

- **Mechanism** (implementer's choice, but config-aligned): either classify `Done` as a teardown
  column in `columns.yml` (like Cancel) with a DONE-flavoured finalize (the cancel comment text and
  the Cancel→Backlog reset edge must NOT apply to Done), or branch in the tick/decide where a
  transition lands in Done and the persisted state shows a live agent → run the teardown action with
  a `done` finalize. Keep the transitions-only model intact (Done stays un-launchable; the
  whitelist is untouched).
- **Sticky finalize:** on teardown-for-Done, upsert the stage sticky to a terminal done header
  (e.g. `### ✅ <stage> — done (ticket closed as already-shipped/complete)`), preserving the
  Progress body. Reuse the existing finalizer seams.
- **Comment:** post a short "ticket #N moved to Done — agent torn down (worktree/session removed)"
  instead of the cancel wording.
- **Replay-safety (fixes the earlier finding too):** every teardown step must SKIP cleanly when its
  target is already gone (worktree absent → skip discover/remove without `git -C` exit-128 noise;
  session absent → skip kill). A second teardown = clean no-op, no ERROR logs.
- **Tests:** Done-arrival with a running agent → session killed + worktree removed + sticky
  finalized ✅ + state purged + card NOT moved; Done-arrival with no agent → pure no-op (no errors);
  WAITING agent → same teardown; replay (second Done teardown) → no-op without error logs; the
  cancel path (`*→Cancel`) keeps its existing wording/reset.

### Phase gate

`rm -rf .mypy_cache && make check` green; diff confined (NEVER the helm prep / ROADMAP /
IMPLEMENTATION / this plan); `python -c "import kanbanmate"` smoke; restart the live daemon.
