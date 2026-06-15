# Phase 31 — Operator UX (audit ranks #11-12, M-cost)

**Source of truth:** the coherence-audit JSON at
`/private/tmp/claude-501/-Users-izno-dev-KanbanMate/55eac608-91ab-46b8-9c7a-ea73bfc8db9f/tasks/wpjhhjbe2.output`
(ranks 13/14 in the synthesis + the verdict corrections). Runs AFTER phase 30 (it consumes the
phase-30 heartbeat JSON).

## 31.1 — `kanban status` single pane of glass + pause/resume

- Extend status rendering with: a PAUSED banner (PAUSE sentinel), daemon last-tick age + OK/FAILING
  (from the phase-30 heartbeat JSON), the queued issue list with ages (markers already persisted),
  per-agent heartbeat age (collected, never rendered), and a concrete `tmux attach -t ticket-<n>`
  hint per running/waiting agent.
- New `kanban pause` / `kanban resume` Typer commands wrapping the PAUSE sentinel (create/remove),
  echoing the resulting state.

## 31.2 — WAITING lifecycle hardening (NO age-based reap — operator-rejected)

- Match waiting markers only in the LAST ~15 pane lines (stale-scrollback false-positive fix).
- On WAITING→RUNNING restore, upsert the 🟡 running header (today the ⏳ sticky goes stale).
- Append the concrete `tmux attach -t ticket-<n>` command to the ⏳ sticky AND the dashboard line.
- Optional (cheap): a shorter waiting-probe TTL (~180s) so a human prompt is signalled quickly, not
  after the 1800s reaper TTL.
- Explicitly DROPPED: the 24h WAITING cap (a solo operator legitimately exceeds it; escalate
  visibility instead — dashboard ⚠ past a threshold is acceptable, never an auto-reap).

## Constraints

Same as phase 30 (layering, timeouts, LOC ceilings, commit discipline, untouchables). Gate each
sub-phase with `rm -rf .mypy_cache && make check`.
